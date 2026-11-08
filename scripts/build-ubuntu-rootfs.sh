#!/usr/bin/env bash
# Native Linux arm64 only. Artifacts are trusted CI inputs, never repository files.
set -euo pipefail
OUT="${1:?usage: build-ubuntu-rootfs.sh <new-output-dir>}"
[ "$(uname -m)" = aarch64 ] || { echo 'arm64 runner required' >&2; exit 1; }
[ ! -e "$OUT" ] || { echo 'output must not exist' >&2; exit 1; }
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
CID=""
cleanup() {
  [ -z "$CID" ] || docker rm -f "$CID" >/dev/null 2>&1 || true
  sudo rm -rf -- "$WORK"
}
trap cleanup EXIT
docker pull --platform linux/arm64 ubuntu:24.04
docker image inspect ubuntu:24.04 --format '{{json .RepoDigests}}' > "$OUT/andcode-ubuntu-build.txt"
printf 'recipe-commit=%s\n' "$(git -C "$REPO" rev-parse HEAD)" >> "$OUT/andcode-ubuntu-build.txt"
CID="$(docker create --platform linux/arm64 ubuntu:24.04 sleep infinity)"
docker start "$CID" >/dev/null
docker exec -e DEBIAN_FRONTEND=noninteractive "$CID" bash -euc '
  apt-get -o APT::Update::Error-Mode=any update
  apt-get install -y --no-install-recommends bash ca-certificates curl git build-essential python3 util-linux
  # A dedicated non-root identity, no sudo or privileged binaries in this image.
  groupadd -g 60000 andcode
  groupadd -g 3003 android-inet
  useradd -u 60000 -g 60000 -G 3003 -m -s /bin/bash andcode
  # apt drops supplementary groups when entering its download sandbox.
  usermod -g 3003 _apt
  mkdir -p /workspace /dev/pts /dev/shm /proc /sys /run /tmp
  ln -sfn /proc/self/fd /dev/fd
  ln -sfn /proc/self/fd/0 /dev/stdin
  ln -sfn /proc/self/fd/1 /dev/stdout
  ln -sfn /proc/self/fd/2 /dev/stderr
  chmod 1777 /tmp
  chown 60000:60000 /workspace
  printf "format=1\nsuite=noble\narch=arm64\n" > /etc/andcode-image
  printf "nameserver 1.1.1.1\nnameserver 8.8.8.8\noptions use-vc\n" > /etc/resolv.conf
  printf "127.0.0.1 localhost\n::1 localhost\n" > /etc/hosts
  find / -xdev -perm /6000 -exec chmod a-s {} + 2>/dev/null
  apt-get clean
  rm -rf /var/lib/apt/lists/*
'
docker exec "$CID" dpkg-query -W '-f=${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n' \
  > "$OUT/andcode-ubuntu-packages.tsv"
docker export "$CID" -o "$WORK/rootfs.tar"
python3 "$REPO/scripts/validate-ubuntu-rootfs.py" "$WORK/rootfs.tar"
mkdir "$WORK/rootfs"
sudo tar --numeric-owner --same-owner -xf "$WORK/rootfs.tar" -C "$WORK/rootfs"
# docker export excludes mounted /dev contents. Recreate guest pseudo-filesystem
# mountpoints in the exported tree, rather than relying on container /dev changes.
sudo mkdir -p "$WORK/rootfs/dev/pts" "$WORK/rootfs/dev/shm" "$WORK/rootfs/proc" "$WORK/rootfs/run"
for pair in 'ptmx pts/ptmx' 'fd /proc/self/fd' 'stdin /proc/self/fd/0' 'stdout /proc/self/fd/1' 'stderr /proc/self/fd/2'; do
  read -r name target <<< "$pair"
  sudo ln -sfn "$target" "$WORK/rootfs/dev/$name"
done
# Docker manages these files as mounts, so set the exported guest copies explicitly.
for f in resolv.conf hosts; do
  [ ! -L "$WORK/rootfs/etc/$f" ] && [ -f "$WORK/rootfs/etc/$f" ] || { echo "invalid etc/$f" >&2; exit 1; }
done
printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\noptions use-vc\n' | sudo tee "$WORK/rootfs/etc/resolv.conf" >/dev/null
printf '127.0.0.1 localhost\n::1 localhost\n' | sudo tee "$WORK/rootfs/etc/hosts" >/dev/null
# ext4 preserves Unix metadata and links. No APK ZIP importer is involved.
truncate -s 4G "$WORK/ubuntu.img"
sudo mkfs.ext4 -q -F -L andcode-ubuntu -O '^metadata_csum_seed,^orphan_file' \
  -E lazy_itable_init=0,lazy_journal_init=0 -d "$WORK/rootfs" "$WORK/ubuntu.img"
sudo e2fsck -fn "$WORK/ubuntu.img"
gzip -1 -c "$WORK/ubuntu.img" > "$OUT/andcode-ubuntu-arm64.img.gz"
(cd "$OUT" && sha256sum andcode-ubuntu-arm64.img.gz > andcode-ubuntu-arm64.img.gz.sha256)
echo 'Ubuntu image built; Android application-domain support is NOT certified.'
