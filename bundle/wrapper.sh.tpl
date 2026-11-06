#!/system/bin/sh
# wrapper.sh.tpl — loader 包装器模板(DESIGN §4.1.2, NAMING §6.1/§6.3.2)
# 占位符:
#   @ROOT@      逻辑根:规范布局=运行期自推导表达式;Tier P=ANDCODE_ROOT 引用
#   @EXEDIR@    可执行物理目录:规范布局=$ROOT;Tier P=$ANDCODE_EXE_DIR(nativeLibraryDir)
#   @LOADER@    动态链接器路径:规范布局=$ROOT/lib/ld-linux-aarch64.so.1;
#               Tier P=$ANDCODE_EXE_DIR/libandcode-ld-linux.so(NAMING §6.3)
#   @LIBPATH@   --library-path:规范布局=$ROOT/lib;Tier P=$ANDCODE_EXE_DIR(路线甲:库全在 jniLibs)
#   @TARGET@    @EXEDIR@ 内被 exec 的 ELF 物理名(opencode.bin / libandcode-opencode.so)
#   @TIER@      m | a | p
set -eu

@ROOT@
EXEDIR="@EXEDIR@"
export ANDCODE_ROOT="$ROOT"
export ANDCODE_EXE_DIR="$EXEDIR"
export ANDCODE_TIER="@TIER@"

SHIM="$ROOT/shim/libandcode-shim.so"

# 仅设置 NAMING §5 登记的运行时变量;不覆盖用户显式设置的 OPENCODE_*
# HOME 为空或 / 时强制落到 $ROOT/home(adb shell root 环境 HOME=/ 会导致 Bun 写 /.local → EROFS)
case "${HOME:-}" in
  ""|"/") HOME="$ROOT/home" ;;
esac
export HOME
TMPDIR="$ROOT/tmp"; mkdir -p "$TMPDIR" 2>/dev/null || true; export TMPDIR
PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"; export PATH
LD_LIBRARY_PATH="$EXEDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; export LD_LIBRARY_PATH
if [ -f "$SHIM" ]; then
  LD_PRELOAD="$SHIM${LD_PRELOAD:+:$LD_PRELOAD}"
  export LD_PRELOAD
  ANDCODE_ETC_DIR="$ROOT/etc"; export ANDCODE_ETC_DIR
fi
GIT_EXEC_PATH="$ROOT/usr/libexec/git-core"; export GIT_EXEC_PATH

LOADER_PATH="@LOADER@"
LIBPATH_VALUE="@LIBPATH@"
TARGET_PATH="$EXEDIR/@TARGET@"

# proot(Tier A/M 正解):/etc 重定向走用户态 bind——LD_PRELOAD 无法拦截
# glibc 内部 fopen("/etc/resolv.conf")(真机 P0 实测)。仅 Android 运行时
# (存在 /system/bin/sh)启用;容器冒烟回退旧链路。
PROOT="$ROOT/usr/lib/proot/proot"
if [ -x "$PROOT" ] && [ -e /system/bin/sh ] && [ -z "${ANDCODE_IN_PROOT:-}" ]; then
  export PROOT_LOADER="$ROOT/usr/lib/proot/loader"
  export ANDCODE_IN_PROOT=1
  export LD_LIBRARY_PATH="$ROOT/usr/lib/proot${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
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

exec "$LOADER_PATH" \
     --library-path "$LIBPATH_VALUE" \
     --inhibit-cache \
     "$TARGET_PATH" "$@"
