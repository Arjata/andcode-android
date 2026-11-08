#!/system/bin/sh
# Invoke manually from the app terminal, no su/run-as. ELF bytes remain unchanged.
set -eu
FILES=/data/data/dev.andcode.app/files
OUT=$FILES/proot-rootfs-gate.txt
ROOT=$FILES/proot-rootfs
INPUT=/data/local/tmp/ubuntu-base-app-gate.tar.gz
umask 077
exec > "$OUT" 2>&1
echo 'gate=ubuntu-base-unmodified-elf; links=relative; full-development=not-certified'
id
cat /proc/self/attr/current
grep -E '^(Uid|Gid|Seccomp):' /proc/self/status
case "$(cat /proc/self/attr/current)" in
  *:untrusted_app:*) ;;
  *) echo 'REJECTED: not application domain'; exit 1 ;;
esac
[ "$#" = 1 ] || { echo 'prepared input SHA-256 required'; exit 1; }
actual=$(/system/bin/toybox sha256sum "$INPUT")
[ "${actual%% *}" = "$1" ]
[ ! -e "$ROOT" ] || { echo 'refusing existing instance'; exit 1; }
mkdir "$ROOT"
/system/bin/toybox tar -xzf "$INPUT" -C "$ROOT"
P=/data/local/tmp/andcode/usr/lib/proot
export PROOT_LOADER="$P/loader"
export LD_LIBRARY_PATH="$P"
export PROOT_TMP_DIR="$FILES/tmp"
export GLIBC_TUNABLES=glibc.pthread.rseq=0
set +e
/system/bin/toybox timeout 20 "$P/proot" -0 -r "$ROOT" -b /dev -b /proc -w / \
  /bin/bash --noprofile --norc -c 'printf "ANDCODE_PROOT_UBUNTU_OK %s\n" "$BASH_VERSION"; /usr/bin/id'
result=$?
echo "ubuntu-base-exit=$result"
exit "$result"
