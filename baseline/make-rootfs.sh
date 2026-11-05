#!/usr/bin/env bash
# make-rootfs.sh — 生成 Ubuntu 24.04 (noble) arm64 基线 rootfs(DESIGN §3.2)
# 用法:
#   make-rootfs.sh <output-dir>
# 环境(二选一):
#   a) arm64 原生(debootstrap 直接跑)
#   b) x86 PC:需 binfmt + qemu-user-static(Dockerfile 镜像已含)
# 注意:PC 上更快的替代是 `docker export ubuntu:24.04`(CI 采用该路径),本脚本
#       供设备端/离线场景使用,产物与 Docker 路径同为官方 noble 用户态。
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
# chroot 内 DNS(供构建期使用;交付包的 etc/ 由 andcode-mkresolv 运行期生成)
printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\n' > "$OUT/etc/resolv.conf"

echo "rootfs 就绪: $OUT"
echo "自检: chroot \"$OUT\" /bin/bash -c 'dpkg -l | head'"
