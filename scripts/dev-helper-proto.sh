#!/system/bin/sh
# dev-helper-proto.sh — Feed helper protocol frames manually to verify the helper itself
ROOT=/data/local/tmp/andcode
H="$ROOT/usr/libexec/git-core"
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export PATH="$ROOT/bin:$ROOT/usr/bin:$H:$PATH"
export HOME="$ROOT/home"

echo "== 恢复 wrapper(从 .bin 同目录重建)=="
# The decoy overwrote git-remote-https; rebuild for git-remote-https.bin by copying the git-remote-http wrapper (same helper mode).
if [ ! -x "$H/git-remote-https" ] || grep -q BAIT "$H/git-remote-https" 2>/dev/null; then
  # Use the loader directly to verify that the .bin responds to capabilities.
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
