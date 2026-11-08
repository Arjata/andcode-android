#!/system/bin/sh
# DEV ONLY: native root device bootstrap using pinned official Ubuntu Base.
# Does not certify the CI Docker recipe, locked APK, or PRoot support.
set -eu
BASE=/data/adb/andcode-ubuntu
ARCHIVE=/data/local/tmp/ubuntu-base-24.04.4-base-arm64.tar.gz
SHA=04207713ece899c3740823d33690441ad3a7f0ded1101aca744e2b0f37ac7ff2
fail() { echo "bootstrap-ubuntu-device: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] && [ "$(uname -m)" = aarch64 ] || fail 'root arm64 required'
proxy=""
case "${2:-}" in '' ) ;; loopback-proxy) proxy=http://127.0.0.1:7890 ;; *) fail 'unknown network mode' ;; esac
if [ "${1:-}" != private-build ]; then
  [ ! -e "$BASE" ] && [ ! -L "$BASE" ] || fail 'refusing existing instance'
  free=$(df -k /data/adb | awk 'END {print $4}')
  [ "$free" -ge 5242880 ] || fail 'need at least 5 GiB free'
  [ -f "$ARCHIVE" ] && [ ! -L "$ARCHIVE" ] || fail 'missing official archive'
  [ "$(stat -c '%u:%g:%a' "$ARCHIVE")" = 0:0:600 ] || fail 'archive must be root:root 0600'
  actual=$(sha256sum "$ARCHIVE")
  [ "${actual%% *}" = "$SHA" ] || fail 'official archive digest mismatch'
  [ -f /data/local/tmp/andcode-ubuntu ] || fail 'reviewed manager missing'
  umask 077
  mkdir "$BASE"
  chown 0:0 "$BASE"
  chmod 0700 "$BASE"
  cp /data/local/tmp/andcode-ubuntu "$BASE/andcode-ubuntu"
  cp /data/local/tmp/andcode/bin/busybox "$BASE/busybox"
  cp "$0" "$BASE/bootstrap-ubuntu-device.sh"
  chmod 0700 "$BASE/andcode-ubuntu" "$BASE/bootstrap-ubuntu-device.sh" "$BASE/busybox"
  printf 'source=https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.4-base-arm64.tar.gz\nsha256=%s\nmode=device-development\nbuild-status=in-progress\n' "$SHA" > "$BASE/andcode-ubuntu-build.txt"
  truncate -s 4294967296 "$BASE/ubuntu.img"
  chmod 0600 "$BASE/ubuntu.img"
  mke2fs -q -F -t ext4 -b 4096 -L andcode-ubuntu \
    -O '^metadata_csum_seed' "$BASE/ubuntu.img"
  mkdir "$BASE/rootfs" "$BASE/session-lock"
  /system/bin/toybox unshare -m /system/bin/sh "$BASE/bootstrap-ubuntu-device.sh" private-build "${2:-}"
  rmdir "$BASE/session-lock"
  echo 'Device development bootstrap complete; CI recipe remains independently unverified.'
  exit 0
fi
[ "$(readlink /proc/self/ns/mnt)" != "$(readlink /proc/$PPID/ns/mnt)" ] || fail 'private namespace required'
ROOT=$BASE/rootfs
mount -o rprivate none /
loop=$(losetup -f -s "$BASE/ubuntu.img")
if ! mount -t ext4 -o rw,nosuid,nodev "$loop" "$ROOT"; then
  losetup -d "$loop"
  exit 1
fi
mounted=""
cleanup() {
  result=$?
  trap - EXIT
  busy=0
  for p in $mounted; do umount "$ROOT/$p" || busy=1; done
  umount "$ROOT" || busy=1
  [ "$busy" = 0 ] || exit 75
  backing=$(cat "/sys/class/block/${loop##*/}/loop/backing_file" 2>/dev/null || true)
  [ -z "$backing" ] || losetup -d "$loop" || exit 75
  exit "$result"
}
trap cleanup EXIT
# Pinned official archive: paths checked on host before deployment, not arbitrary input.
"$BASE/busybox" tar -xzf "$ARCHIVE" -C "$ROOT"
mkdir -p "$ROOT/dev/pts" "$ROOT/dev/shm" "$ROOT/proc" "$ROOT/run" "$ROOT/workspace"
ln -sfn pts/ptmx "$ROOT/dev/ptmx"
for n in null zero random urandom tty; do
  touch "$ROOT/dev/$n"
  "$BASE/busybox" mount -o bind "/dev/$n" "$ROOT/dev/$n"
  mounted="dev/$n $mounted"
done
mount -t devpts -o newinstance,nosuid,noexec,ptmxmode=0666,mode=0620,gid=60000 devpts "$ROOT/dev/pts"
mounted="dev/pts $mounted"
mount -t proc -o nosuid,nodev,noexec proc "$ROOT/proc"
mounted="proc $mounted"
if [ -f /data/local/tmp/andcode/etc/resolv.conf ]; then
  # Development bootstrap reuses the already configured current-network resolver.
  cp /data/local/tmp/andcode/etc/resolv.conf "$ROOT/etc/resolv.conf"
else
  printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\noptions use-vc timeout:3 attempts:2\n' > "$ROOT/etc/resolv.conf"
fi
printf '127.0.0.1 localhost\n::1 localhost\n' > "$ROOT/etc/hosts"
printf 'format=1\nsuite=noble\narch=arm64\n' > "$ROOT/etc/andcode-image"
chroot "$ROOT" /usr/bin/env -i HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin \
  LANG=C.UTF-8 DEBIAN_FRONTEND=noninteractive http_proxy="$proxy" https_proxy="$proxy" /bin/bash --noprofile --norc -euc '
    # Android checks inet supplemental group on kernels with paranoid networking.
    # Configure _apt before its first network operation, not after apt install.
    groupadd -g 3003 android-inet
    usermod -g 3003 _apt
    apt-get -o APT::Update::Error-Mode=any update
    apt-get install -y --no-install-recommends bash ca-certificates curl git build-essential python3 util-linux
    groupadd -g 60000 andcode
    useradd -u 60000 -g 60000 -G 3003 -m -s /bin/bash andcode
    chown 60000:60000 /workspace
    chmod 1777 /tmp
    find / -xdev -perm /6000 -exec chmod a-s {} +
    apt-get clean
    dpkg-query -W '\''-f=${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n'\'' > /etc/andcode-ubuntu-packages.tsv
  '
printf 'build-status=complete\n' >> "$BASE/andcode-ubuntu-build.txt"
