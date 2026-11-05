#!/usr/bin/env bash
# deploy-adb.sh — Tier A:经 adb 部署 bundle 到 /data/local/tmp(DESIGN §4.3)
# 用法: deploy-adb.sh [--serial <ser>] [--bundle <tar.gz>] [--no-smoke]
# 说明: 使用 .tar.gz(toybox tar 原生支持 gzip;zstd 不保证存在于旧 toybox)
set -euo pipefail

SERIAL="" BUNDLE="" SMOKE=1
while [ $# -gt 0 ]; do
  case "$1" in
    --serial) SERIAL="$2"; shift 2 ;;
    --bundle) BUNDLE="$2"; shift 2 ;;
    --no-smoke) SMOKE=0; shift ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done
ADB=(adb); [ -n "$SERIAL" ] && ADB+=(-s "$SERIAL")

# 找产物:显式指定 > 仓库 dist/ 最新
if [ -z "$BUNDLE" ]; then
  BUNDLE="$(ls -t dist/andcode-bundle-arm64-*.tar.gz 2>/dev/null | head -n1 || true)"
  [ -n "$BUNDLE" ] || { echo "未找到 bundle,先跑 CI 或 pack-bundle.sh"; exit 1; }
fi

DEST=/data/local/tmp/andcode
echo "== 1/4 推送 $BUNDLE"
"${ADB[@]}" push "$BUNDLE" /data/local/tmp/andcode-bundle.tar.gz

echo "== 2/4 解包(静态 busybox 兜底,见 NAMING/REUSE busybox 条目)"
"${ADB[@]}" shell "rm -rf $DEST && mkdir -p $DEST && \
  cd /data/local/tmp && (command -v zstd >/dev/null 2>&1 && echo zstd || true) && \
  tar -xzf andcode-bundle.tar.gz -C $DEST --strip-components=1 && \
  chmod -R 0755 $DEST/bin $DEST/sbin $DEST/usr/bin"

echo "== 3/4 Phantom Process Killer 对策(DESIGN §4.6;重启后需重跑)"
"${ADB[@]}" shell "cmd device_config set_sync_disabled_for_tests persistent || true"
"${ADB[@]}" shell "device_config put activity_manager max_phantom_processes 2147483647 || true"

echo "== 4/4 自检"
if [ "$SMOKE" = 1 ]; then
  "${ADB[@]}" shell "ANDCODE_ROOT=$DEST ANDCODE_TIER=a sh $DEST/bin/andcode-doctor"
else
  "${ADB[@]}" shell "ls $DEST/bin"
fi
echo "部署完成。交互入口:"
echo "  ${ADB[*]} shell '$DEST/sbin/andcode-entry shell'"
echo "  ${ADB[*]} shell '$DEST/sbin/andcode-entry sshd'  # 之后 ssh 127.0.0.1:2222"
