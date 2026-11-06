#!/system/bin/sh
# dev-helper-proto.sh — 手动喂 helper 协议帧,验证 helper 自身是否正常
ROOT=/data/local/tmp/andcode
H="$ROOT/usr/libexec/git-core"
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export PATH="$ROOT/bin:$ROOT/usr/bin:$H:$PATH"
export HOME="$ROOT/home"

echo "== 恢复 wrapper(从 .bin 同目录重建)=="
# 诱饵覆盖了 git-remote-https;从 git-remote-https.bin 同配置重建:直接拷贝 git-remote-http 的 wrapper 内容(同为 helper 形态)
if [ ! -x "$H/git-remote-https" ] || grep -q BAIT "$H/git-remote-https" 2>/dev/null; then
  # 用 loader 直接验证 .bin 是否能应答 capabilities
  echo "== 手动协议: capabilities 帧 → helper .bin =="
  printf 'capabilities\n\n' | \
    LD_PRELOAD="$ROOT/shim/libandcode-shim.so" \
    ANDCODE_ETC_DIR="$ROOT/etc" \
    GIT_EXEC_PATH="$H" \
    timeout 30 "$ROOT/lib/ld-linux-aarch64.so.1" \
      --library-path "$ROOT/lib" --inhibit-cache \
      "$H/git-remote-https.bin" origin https://github.com/git/git.git \
      2>/tmp/herr | head -n 5
  echo "rc=$?"
  echo "-- stderr:"; head -n 8 /tmp/herr
fi
