#!/system/bin/sh
# Development only. Run from the app terminal; no su, relabel, or run-as.
set -eu
FILES=/data/data/dev.andcode.app/files
ROOT=$FILES/proot-rootfs
P=/data/local/tmp/andcode/usr/lib/proot
PLIB=$P
if [ "${ANDCODE_TIER:-}" = p ] && [ -n "${ANDCODE_ROOT:-}" ]; then
  P=$ANDCODE_ROOT/usr/lib/proot
  PLIB=${ANDCODE_EXE_DIR:?missing native payload directory}
fi
umask 077
exec > "$FILES/proot-development-gate.txt" 2>&1
id
cat /proc/self/attr/current
grep -E '^(Uid|Gid|Seccomp):' /proc/self/status
case "$(cat /proc/self/attr/current)" in
  *:untrusted_app:*) ;;
  *) echo 'REJECTED: not application domain'; exit 1 ;;
esac
proxy=""
case "${1:-}" in '' ) ;; loopback-proxy) proxy=http://127.0.0.1:7890 ;; *) exit 1 ;; esac
export PROOT_LOADER="$P/loader" LD_LIBRARY_PATH="$PLIB" PROOT_TMP_DIR="$FILES/tmp"
export GLIBC_TUNABLES=glibc.pthread.rseq=0
set +e
/system/bin/toybox timeout 900 "$P/proot" --kill-on-exit -l -0 -r "$ROOT" -b /dev -b /proc -w /root \
  /usr/bin/env -i HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin TERM=xterm-256color \
  LANG=C.UTF-8 GLIBC_TUNABLES=glibc.pthread.rseq=0 DEBIAN_FRONTEND=noninteractive \
  http_proxy="$proxy" https_proxy="$proxy" /bin/bash --noprofile --norc -euc '
    dpkg --configure -a
    printf "nameserver 1.1.1.1\noptions use-vc timeout:3 attempts:2\n" > /etc/resolv.conf
    apt-get -o APT::Update::Error-Mode=any -o Acquire::Retries=1 update
    apt-get install -y --no-install-recommends ca-certificates curl git build-essential python3 hello
    hello | grep -q Hello
    curl --fail --silent --show-error --max-time 45 https://ports.ubuntu.com/ubuntu-ports/dists/noble/Release -o /tmp/andcode-release
    grep -q "^Codename: noble$" /tmp/andcode-release
    printf "#include <stdio.h>\nint main(void){puts(\"ANDCODE_PROOT_COMPILE_OK\");return 0;}\n" > /tmp/andcode-smoke.c
    gcc -Wl,-z,max-page-size=16384 -o /tmp/andcode-smoke /tmp/andcode-smoke.c
    /tmp/andcode-smoke | grep -qx ANDCODE_PROOT_COMPILE_OK
    echo ANDCODE_PROOT_COMPILE_OK
    g++ -x c++ -Wl,-z,max-page-size=16384 -o /tmp/andcode-smoke-cxx /tmp/andcode-smoke.c
    /tmp/andcode-smoke-cxx | grep -qx ANDCODE_PROOT_COMPILE_OK
    git --version
    make --version | head -n 1
    git ls-remote https://github.com/Arjata/andcode-android.git HEAD
    python3 -c "import os, pty, subprocess; a,b=pty.openpty(); os.close(a); os.close(b); assert subprocess.check_output([\"/usr/bin/hello\"]); print(\"ANDCODE_PROOT_PTY_CHILD_OK\")"
    dpkg-query -W libc6
    echo ANDCODE_PROOT_DEVELOPMENT_OK
  ' < /dev/null
result=$?
echo "development-exit=$result network-mode=${1:-direct}"
exit "$result"
