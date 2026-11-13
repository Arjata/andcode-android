#!/usr/bin/env bash
# make-rootfs.sh — Generate the Ubuntu 24.04 (noble) arm64 baseline rootfs (DESIGN §3.2)
# Usage:
#   make-rootfs.sh <output-dir>
# Environment (choose one):
#   a) Native arm64 (run debootstrap directly)
#   b) x86 PC: requires binfmt + qemu-user-static (included in the Dockerfile image)
# Note: `docker export ubuntu:24.04` is faster on PCs (used by CI). This script
#       supports device/offline use; both paths provide the official noble userland.
set -euo pipefail

OUT="${1:?usage: make-rootfs.sh <output-dir>}"
SUITE=noble
ARCH=arm64
MIRROR="${MIRROR:-http://ports.ubuntu.com/ubuntu-ports}"

mkdir -p "$OUT"
[ -e "$OUT/bin/sh" ] && { echo "输出目录非空,跳过?删除后重试: $OUT"; exit 1; }

export DEBIAN_FRONTEND=noninteractive
debootstrap --arch="$ARCH" --variant=minbase --include=ca-certificates,git,zstd,xz-utils \
  "$SUITE" "$OUT" "$MIRROR"

rm -rf "$OUT/debootstrap"
# DNS inside chroot (build-time only; andcode-mkresolv generates the bundle's etc/ at runtime)
printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\n' > "$OUT/etc/resolv.conf"

echo "rootfs 就绪: $OUT"
echo "自检: chroot \"$OUT\" /bin/bash -c 'dpkg -l | head'"
