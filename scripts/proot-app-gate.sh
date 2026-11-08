#!/system/bin/sh
# Run FROM the existing application's terminal, never adb shell/run-as as proof.
set -u
OUT=/data/data/dev.andcode.app/files/proot-gate.txt
umask 077
exec > "$OUT" 2>&1
echo 'gate=ptrace-only; ubuntu-rootfs=not-tested'
id
cat /proc/self/attr/current
grep -E '^(Uid|Gid|Seccomp|NoNewPrivs):' /proc/self/status
case "$(cat /proc/self/attr/current)" in
  *:untrusted_app:*) ;;
  *) echo 'REJECTED: not real application domain'; exit 1 ;;
esac
P=/data/local/tmp/andcode/usr/lib/proot
export PROOT_LOADER="$P/loader"
export LD_LIBRARY_PATH="$P"
export PROOT_TMP_DIR=/data/data/dev.andcode.app/files/tmp
/system/bin/toybox timeout 15 "$P/proot" -v 1 /system/bin/sh -c 'echo ANDCODE_PROOT_APP_CHILD_OK; id; cat /proc/self/attr/current'
result=$?
echo "proot-exit=$result"
exit "$result"
