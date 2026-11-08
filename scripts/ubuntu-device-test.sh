#!/system/bin/sh
# Android rooted chroot acceptance. No SELinux changes, no application-domain claims.
set -eu
MANAGER=/data/adb/andcode-ubuntu/andcode-ubuntu
BASE=/data/adb/andcode-ubuntu
call() { /system/bin/sh "$MANAGER" "$@"; }
proxy=""
case "${1:-}" in '' ) ;; loopback-proxy) proxy=http://127.0.0.1:7890 ;; *) echo 'unknown network mode' >&2; exit 1 ;; esac
[ "$(id -u)" = 0 ] || exit 1
[ "$(getenforce)" = Enforcing ] || { echo 'SELinux must remain Enforcing' >&2; exit 1; }
call status
call admin /usr/bin/env http_proxy="$proxy" https_proxy="$proxy" /bin/bash --noprofile --norc -euc '
  test "$(dpkg --print-architecture)" = arm64
  test "$(getconf GNU_LIBC_VERSION)" = "glibc 2.39"
  curl --fail --silent --show-error --max-time 45 https://ports.ubuntu.com/ubuntu-ports/dists/noble/Release -o /tmp/andcode-release
  grep -q "^Codename: noble$" /tmp/andcode-release
  rm /tmp/andcode-release
  apt-get -o APT::Update::Error-Mode=any update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends hello
  hello | grep -q Hello
  apt-get clean
  echo ANDCODE_APT_HTTPS_OK
'
call exec /usr/bin/env http_proxy="$proxy" https_proxy="$proxy" /bin/bash --noprofile --norc -euc '
  test "$(id -u)" = 60000
  test "$(id -g)" = 60000
  test "$(pwd)" = /workspace
  test "$(grep -Ec "^Cap(Eff|Prm|Bnd|Amb):[[:space:]]+0+$" /proc/self/status)" = 4
  # Old vendor kernels may implement prctl but omit NoNewPrivs in proc status.
  python3 -c "import ctypes; assert ctypes.CDLL(None).prctl(39, 0, 0, 0, 0) == 1"
  test ! -w /etc
  test ! -e /data/adb
  test ! -e /system/bin
  hello | grep -q Hello
  printf "#include <stdio.h>\nint main(void){puts(\"ANDCODE_DEVICE_COMPILE_OK\");return 0;}\n" > andcode-smoke.c
  gcc -Wl,-z,max-page-size=16384 -o andcode-smoke andcode-smoke.c
  ./andcode-smoke | grep -qx ANDCODE_DEVICE_COMPILE_OK
  readelf -lW andcode-smoke | grep LOAD
  python3 -c "import ssl, sqlite3, subprocess; assert subprocess.check_output([\"/usr/bin/id\",\"-u\"]).strip() == b\"60000\"; print(ssl.OPENSSL_VERSION)"
  python3 -c "import os, pty; a,b=pty.openpty(); os.close(a); os.close(b); print(\"ANDCODE_USER_PTY_OK\")"
  echo ANDCODE_USER_CAPS_COMPILE_OK
  rm andcode-smoke andcode-smoke.c
'
[ ! -d "$BASE/session-lock" ]
if grep -F "$BASE/rootfs" /proc/self/mountinfo; then
  echo 'host namespace mount leak' >&2
  exit 1
fi
call exec /bin/true
[ ! -d "$BASE/session-lock" ]
rc=0
call exec /bin/bash -c 'exit 42' || rc=$?
[ "$rc" = 42 ] || { echo 'guest exit status lost' >&2; exit 1; }
[ ! -d "$BASE/session-lock" ]
printf 'ANDCODE_STDIN_OK\n' | call exec /bin/bash -c 'read -r line; test "$line" = ANDCODE_STDIN_OK'
[ ! -d "$BASE/session-lock" ]
echo ANDCODE_CHROOT_OFFLINE_LIFECYCLE_OK
call exec /usr/bin/env http_proxy="$proxy" https_proxy="$proxy" /usr/bin/curl \
  --fail --silent --show-error --connect-timeout 10 --max-time 45 \
  https://ports.ubuntu.com/ubuntu-ports/dists/noble/Release -o /tmp/andcode-user-release
call exec /bin/rm /tmp/andcode-user-release
echo ANDCODE_CHROOT_DEVICE_SMOKE_OK
echo "network-mode=${1:-direct}"
