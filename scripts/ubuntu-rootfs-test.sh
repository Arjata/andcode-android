#!/usr/bin/env bash
# Linux CI smoke only; does not establish Android SELinux/seccomp compatibility.
set -euo pipefail
IMAGE="${1:?usage: ubuntu-rootfs-test.sh <ubuntu.img>}"
[ "$(id -u)" = 0 ] || { echo 'root required' >&2; exit 1; }
ROOT="$(mktemp -d)"
cleanup() {
  for p in proc dev/pts dev/urandom dev/zero dev/null; do umount "$ROOT/$p" 2>/dev/null || true; done
  umount "$ROOT" || return
  rmdir "$ROOT"
}
trap cleanup EXIT
mount -o loop,nosuid,nodev "$IMAGE" "$ROOT"
for n in null zero urandom; do
  touch "$ROOT/dev/$n"
  mount --bind "/dev/$n" "$ROOT/dev/$n"
done
mount --bind /dev/pts "$ROOT/dev/pts"
mount -t proc -o nosuid,nodev,noexec proc "$ROOT/proc"
grep -qx 'suite=noble' "$ROOT/etc/andcode-image"
chroot "$ROOT" /usr/bin/dpkg --print-architecture | grep -qx arm64
chroot "$ROOT" /bin/bash -euc '
  test "$(getconf GNU_LIBC_VERSION)" = "glibc 2.39"
  curl --fail --silent --show-error --max-time 30 https://ports.ubuntu.com/ubuntu-ports/dists/noble/Release -o /tmp/ubuntu-release
  grep -q "^Codename: noble$" /tmp/ubuntu-release
  rm /tmp/ubuntu-release
  apt-get -o APT::Update::Error-Mode=any update
  apt-get install -y --no-install-recommends hello
  hello | grep -q Hello
  apt-get clean
  rm -rf /var/lib/apt/lists/*
'
chroot "$ROOT" /usr/bin/setpriv --reuid=60000 --regid=60000 --groups=3003 \
  --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs \
  /usr/bin/env -i HOME=/home/andcode USER=andcode LOGNAME=andcode \
  PATH=/usr/local/bin:/usr/bin:/bin TERM=xterm-256color /bin/bash --noprofile --norc -euc '
    test "$(id -u)" = 60000
    grep -Eq "^Cap(Eff|Prm|Bnd):[[:space:]]+0+$" /proc/self/status
    test "$(grep -Ec "^Cap(Eff|Prm|Bnd):[[:space:]]+0+$" /proc/self/status)" = 3
    grep -Eq "^NoNewPrivs:[[:space:]]+1$" /proc/self/status
    cd /workspace
    printf "#include <stdio.h>\nint main(void){puts(\"ANDCODE_COMPILE_OK\");return 0;}\n" > hello.c
    gcc -Wl,-z,max-page-size=16384 -o hello hello.c
    ./hello | grep -qx ANDCODE_COMPILE_OK
    python3 -c "import ssl, sqlite3; print(ssl.OPENSSL_VERSION)"
    ! touch /etc/andcode-user-must-not-write
    rm hello hello.c
  '
echo 'Linux rootfs apt / installed ELF / non-root compile and execute: PASS'
