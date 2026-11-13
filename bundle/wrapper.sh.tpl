#!/system/bin/sh
# wrapper.sh.tpl — loader wrapper template (DESIGN §4.1.2, NAMING §6.1/§6.3.2)
# Placeholders:
#   @ROOT@      Logical root: canonical layout=runtime-derived expression; Tier P=ANDCODE_ROOT reference
#   @EXEDIR@    Physical executable directory: canonical layout=$ROOT; Tier P=$ANDCODE_EXE_DIR(nativeLibraryDir)
#   @LOADER@    Dynamic linker path: canonical layout=$ROOT/lib/ld-linux-aarch64.so.1;
#               Tier P=$ANDCODE_EXE_DIR/libandcode-ld-linux.so(NAMING §6.3)
#   @LIBPATH@   --library-path: canonical layout=$ROOT/lib; Tier P=$ANDCODE_EXE_DIR(route A: all libraries in jniLibs)
#   @TARGET@    Physical name of the ELF to exec within @EXEDIR@ (opencode.bin / libandcode-opencode.so)
#   @TIER@      m | a | p
set -eu

@ROOT@
EXEDIR="@EXEDIR@"
export ANDCODE_ROOT="$ROOT"
export ANDCODE_EXE_DIR="$EXEDIR"
export ANDCODE_TIER="@TIER@"

SHIM="$ROOT/shim/libandcode-shim.so"

# Set only runtime variables registered in NAMING §5; preserve explicit user OPENCODE_* settings
# Force empty or / HOME to $ROOT/home (HOME=/ in a root adb shell makes Bun write /.local → EROFS)
case "${HOME:-}" in
  ""|"/") HOME="$ROOT/home" ;;
esac
export HOME
TMPDIR="$ROOT/tmp"; mkdir -p "$TMPDIR" 2>/dev/null || true; export TMPDIR
PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"; export PATH
LD_LIBRARY_PATH="$EXEDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; export LD_LIBRARY_PATH
if [ -f "$SHIM" ]; then
  ANDCODE_ETC_DIR="$ROOT/etc"; export ANDCODE_ETC_DIR
fi
GIT_EXEC_PATH="$ROOT/usr/libexec/git-core"; export GIT_EXEC_PATH

LOADER_PATH="@LOADER@"
LIBPATH_VALUE="@LIBPATH@"
TARGET_PATH="$EXEDIR/@TARGET@"

# proot (the correct Tier A/M solution): redirect /etc through userspace bind; LD_PRELOAD cannot intercept
# glibc's internal fopen("/etc/resolv.conf") (confirmed in P0 device testing). Enable only on Android
# (when /system/bin/sh exists); container smoke tests fall back to the old path.
PROOT="$ROOT/usr/lib/proot/proot"
if [ -x "$PROOT" ] && [ -e /system/bin/sh ] && [ -z "${ANDCODE_IN_PROOT:-}" ]; then
  export PROOT_LOADER="$ROOT/usr/lib/proot/loader"
  export ANDCODE_IN_PROOT=1
  export LD_LIBRARY_PATH="$ROOT/usr/lib/proot${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  unset LD_PRELOAD
  export PROOT_TMP_DIR="${ANDCODE_APP_DATA:-$ROOT/tmp}"
  exec "$PROOT" \
       -b "$ROOT/etc/resolv.conf:/etc/resolv.conf" \
       -b "$ROOT/etc/ssl:/etc/ssl" \
       -b "$ROOT/etc/ssl:/usr/lib/ssl" \
       -b "$ROOT/etc/passwd:/etc/passwd" \
       -b "$ROOT/etc/group:/etc/group" \
       -b "$ROOT/etc/nsswitch.conf:/etc/nsswitch.conf" \
       -w "$PWD" \
       "$LOADER_PATH" --library-path "$LIBPATH_VALUE" --inhibit-cache "$TARGET_PATH" "$@"
fi

# Loader-only preload never enters Bash's exported startup environment. Relying
# on a constructor unsetenv left LD_PRELOAD visible in Bash on the real device,
# breaking Bionic children such as /system/bin/id before their main() ran.
unset LD_PRELOAD
if [ -f "$SHIM" ]; then
  exec "$LOADER_PATH" \
       --library-path "$LIBPATH_VALUE" \
       --inhibit-cache --preload "$SHIM" \
       "$TARGET_PATH" "$@"
fi
exec "$LOADER_PATH" \
     --library-path "$LIBPATH_VALUE" \
     --inhibit-cache \
     "$TARGET_PATH" "$@"
