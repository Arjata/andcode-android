#!/system/bin/sh
# Invoke with sh FROM the application terminal. adb/run-as is not evidence.
set -eu
: "${ANDCODE_APP_DATA:?application terminal required}"
umask 077
exec > "$ANDCODE_APP_DATA/native-payload-test.txt" 2>&1
case "$(cat /proc/self/attr/current)" in
  *:untrusted_app:*) ;;
  *) echo 'REJECTED: not real application domain'; exit 1 ;;
esac
cat /proc/self/attr/current
grep -E '^(Uid|Gid|Seccomp|NoNewPrivs):' /proc/self/status
grep -q '^Seccomp:[[:space:]]*2$' /proc/self/status
if enforcement=$(getenforce 2>/dev/null); then
  test "$enforcement" = Enforcing
else
  echo 'SELinux status unreadable in app domain; verify Enforcing separately with adb.'
fi
case "$ANDCODE_ROOT" in "$ANDCODE_APP_DATA"/andcode-runtime-*) ;; *) exit 1 ;; esac
case "$ANDCODE_LOADER" in /data/app/*/lib/arm64/libandcode-ld-linux.so) ;; *) exit 1 ;; esac
test "$ANDCODE_LIBPATH" = "$ANDCODE_EXE_DIR"
test "$ANDCODE_LOADER" = "$ANDCODE_EXE_DIR/libandcode-ld-linux.so"
test -z "${NODE_TLS_REJECT_UNAUTHORIZED:-}"
test -z "${HTTPS_PROXY:-}${https_proxy:-}${HTTP_PROXY:-}${http_proxy:-}${ALL_PROXY:-}${all_proxy:-}"
"$ANDCODE_LOADER" --library-path "$ANDCODE_LIBPATH" --inhibit-cache \
  "$ANDCODE_EXE_DIR/libandcode-bash.so" --noprofile --norc -c 'echo "BASH=$BASH_VERSION"'
"$ANDCODE_LOADER" --library-path "$ANDCODE_LIBPATH" --inhibit-cache \
  "$ANDCODE_EXE_DIR/libandcode-oc2.so" --version
"$ANDCODE_EXE_DIR/libandcode-opencode-pty.so" --version
git --version
# Exercise the real Bash wrapper, not only a direct loader version probe.
# A glibc LD_PRELOAD inherited by the Bionic system child must fail this gate.
"$ANDCODE_ROOT/bin/bash" --noprofile --norc -c '
  test -z "${LD_PRELOAD:-}" || exit 1
  /system/bin/id
  echo ANDCODE_NATIVE_BIONIC_CHILD_OK
'
PROOT="$ANDCODE_EXE_DIR/libandcode-usr-lib-proot-proot.so"
PROOT_LOADER="$ANDCODE_EXE_DIR/libandcode-usr-lib-proot-loader.so" \
LD_LIBRARY_PATH="$ANDCODE_EXE_DIR" PROOT_TMP_DIR="$ANDCODE_APP_DATA/tmp" \
  /system/bin/toybox timeout 15 "$PROOT" /system/bin/sh -c 'echo ANDCODE_NATIVE_PROOT_CHILD_OK'
echo ANDCODE_NATIVE_PAYLOAD_OK
