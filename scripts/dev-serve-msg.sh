#!/system/bin/sh
# dev-serve-msg.sh — 经本地 serve API 发消息,捕获 server 侧异常栈
ROOT=/data/local/tmp/andcode
P="$ROOT/usr/lib/proot/proot"
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export ANDCODE_APP_DATA=/data/data/dev.andcode.app/files
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
export HTTPS_PROXY="http://127.0.0.1:7890"
export HTTP_PROXY="http://127.0.0.1:7890"
export PROOT_LOADER="$ROOT/usr/lib/proot/loader"
export LD_LIBRARY_PATH="$ROOT/usr/lib/proot"
export PROOT_TMP_DIR="/data/data/dev.andcode.app/files"
cd "$ROOT/home/demo" || exit 1

"$P" -b "$ROOT/etc/resolv.conf:/etc/resolv.conf" \
     -b "$ROOT/etc/ssl:/etc/ssl" \
     -b "$ROOT/etc/passwd:/etc/passwd" \
     -b "$ROOT/etc/group:/etc/group" \
     -b "$ROOT/etc/nsswitch.conf:/etc/nsswitch.conf" \
     -w "$ROOT/home/demo" \
     opencode serve --port 4096 >/data/local/tmp/serve.log 2>&1 &
sleep 6
SID=$(busybox wget -q -O - --header="Content-Type: application/json" \
  --post-data='{"directory":"/data/local/tmp/andcode/home/demo"}' \
  "http://127.0.0.1:4096/session" 2>/dev/null | sed 's/.*"id":"\([^"]*\)".*/\1/')
echo "session: $SID"
busybox wget -q -O /data/local/tmp/msg.json \
  --header="Content-Type: application/json" \
  --post-data="{\"parts\":[{\"type\":\"text\",\"text\":\"say ok\"}],\"model\":{\"providerID\":\"openai\",\"modelID\":\"gpt-oss-120b\"},\"agent\":\"build\"}" \
  "http://127.0.0.1:4096/session/$SID/message" 2>&1 | head -n 2
echo "== msg resp =="; head -c 400 /data/local/tmp/msg.json 2>/dev/null; echo
echo "== serve.log(server stderr)=="; tail -n 12 /data/local/tmp/serve.log
echo "== opencode.log ERROR =="; grep -E 'level=ERROR' "$HOME/.local/share/opencode/log/opencode.log" | tail -n 1 | tail -c 700
kill $(pidof -s opencode 2>/dev/null) 2>/dev/null
