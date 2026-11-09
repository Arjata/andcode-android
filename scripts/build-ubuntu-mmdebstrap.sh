#!/usr/bin/env bash
# Build-only native arm64 candidate; never installs to an Android device.
set -euo pipefail
[ "$#" = 1 ] || { echo 'usage: build-ubuntu-mmdebstrap.sh <new-output-dir>' >&2; exit 1; }
[ "$(uname -m)" = aarch64 ] || { echo 'arm64 runner required' >&2; exit 1; }
OUT="$1"
[ ! -e "$OUT" ] && [ ! -L "$OUT" ] || { echo 'output must be new' >&2; exit 1; }
command -v mmdebstrap >/dev/null
KEY=/usr/share/keyrings/ubuntu-archive-keyring.gpg
[ -f "$KEY" ] || { echo 'Ubuntu archive keyring required' >&2; exit 1; }
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
cleanup() {
  # Never traverse mounts when deleting the one freshly allocated CI tree.
  if sudo findmnt -rn -o TARGET | grep -Fq "$WORK/"; then
    echo "refusing cleanup of mounted work tree: $WORK" >&2
    return
  fi
  sudo rm -rf --one-file-system -- "$WORK"
}
trap cleanup EXIT
{
  printf 'builder=mmdebstrap\nrecipe-commit=%s\n' "$(git -C "$REPO" rev-parse HEAD)"
  printf 'scope=Linux experiment; source closure and Android acceptance pending\n'
  dpkg-query -W '-f=${binary:Package}\t${Version}\n' mmdebstrap ubuntu-keyring apt dpkg e2fsprogs
  sha256sum "$KEY"
} > "$OUT/andcode-ubuntu-build.txt"
cp /usr/share/doc/mmdebstrap/copyright "$OUT/mmdebstrap-copyright"
for suite in noble noble-updates noble-security; do
  printf 'deb [arch=arm64 signed-by=%s] https://ports.ubuntu.com/ubuntu-ports %s main universe\n' "$KEY" "$suite"
done > "$OUT/ubuntu-sources.list"
# Use root mode only in a private mount namespace on the disposable CI runner.
sudo unshare --mount --propagation private mmdebstrap --mode=root --format=directory \
  --variant=minbase --architectures=arm64 --keyring="$KEY" \
  --include=apt,bash,ca-certificates,curl,git,build-essential,python3,util-linux,passwd,ubuntu-keyring \
  --aptopt='APT::Update::Error-Mode "any"' \
  --aptopt='Acquire::Languages "none"' --skip=cleanup/apt/lists \
  --logfile="$OUT/mmdebstrap.log" noble "$WORK/rootfs" "$OUT/ubuntu-sources.list"
ROOT="$WORK/rootfs"
mkdir "$OUT/ubuntu-indexes"
# Retain the actual authenticated indexes used for the bootstrap, not a later
# refresh that might have observed different repository contents.
sudo find "$ROOT/var/lib/apt/lists" -maxdepth 1 -type f ! -name lock \
  -exec cp -t "$OUT/ubuntu-indexes" -- {} +
sudo chroot "$ROOT" /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin \
  DEBIAN_FRONTEND=noninteractive LC_ALL=C /bin/bash -euc '
  groupadd -g 60000 andcode
  groupadd -g 3003 android-inet
  useradd -u 60000 -g 60000 -G 3003 -m -s /bin/bash andcode
  usermod -g 3003 _apt
  mkdir -p /workspace /dev/pts /dev/shm /proc /sys /run /tmp
  chmod 1777 /tmp
  chown 60000:60000 /workspace
  printf "format=1\nsuite=noble\narch=arm64\n" > /etc/andcode-image
  find / -xdev -perm /6000 -exec chmod a-s {} +
  apt-get clean
'
[ "$(find "$OUT/ubuntu-indexes" -type f -name '*InRelease' | wc -l)" -ge 3 ]
(cd "$OUT" && find ubuntu-indexes -type f -print0 | sort -z | xargs -0 sha256sum) \
  >> "$OUT/andcode-ubuntu-build.txt"
sudo chroot "$ROOT" dpkg-query -W '-f=${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n' \
  > "$OUT/andcode-ubuntu-packages.tsv"
# Remove only build-created package indexes and device nodes in this new tree.
sudo find "$ROOT/var/lib/apt/lists" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
sudo find "$ROOT/dev" -xdev \( -type b -o -type c -o -type p -o -type s \) -delete
for pair in 'ptmx pts/ptmx' 'fd /proc/self/fd' 'stdin /proc/self/fd/0' 'stdout /proc/self/fd/1' 'stderr /proc/self/fd/2'; do
  read -r name target <<< "$pair"
  sudo ln -sfn "$target" "$ROOT/dev/$name"
done
for name in resolv.conf hosts; do
  [ ! -L "$ROOT/etc/$name" ] && [ -f "$ROOT/etc/$name" ] || { echo "invalid etc/$name" >&2; exit 1; }
done
printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\noptions use-vc\n' | sudo tee "$ROOT/etc/resolv.conf" >/dev/null
printf '127.0.0.1 localhost\n::1 localhost\n' | sudo tee "$ROOT/etc/hosts" >/dev/null
sudo tar --numeric-owner -C "$ROOT" -cf "$WORK/rootfs.tar" .
python3 "$REPO/scripts/validate-ubuntu-rootfs.py" "$WORK/rootfs.tar"
gzip -1 -c "$WORK/rootfs.tar" > "$OUT/andcode-ubuntu-rootfs.tar.gz"
truncate -s 4G "$WORK/ubuntu.img"
sudo mkfs.ext4 -q -F -L andcode-ubuntu -O '^metadata_csum_seed,^orphan_file' \
  -E lazy_itable_init=0,lazy_journal_init=0 -d "$ROOT" "$WORK/ubuntu.img"
sudo e2fsck -fn "$WORK/ubuntu.img"
gzip -1 -c "$WORK/ubuntu.img" > "$OUT/andcode-ubuntu-arm64.img.gz"
(cd "$OUT" && sha256sum andcode-ubuntu-rootfs.tar.gz > andcode-ubuntu-rootfs.tar.gz.sha256)
(cd "$OUT" && sha256sum andcode-ubuntu-arm64.img.gz > andcode-ubuntu-arm64.img.gz.sha256)
echo 'mmdebstrap Linux candidate built; Android installation and distribution NOT approved.'
