#!/system/bin/sh
# dev-full-session.sh — 全自治: serve 常驻 + 建会话 + glm/gpt-oss 模型循环
ROOT=/data/local/tmp/andcode
P="$ROOT/usr/lib/proot/proot"
BB="$ROOT/bin/busybox"
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export ANDCODE_APP_DATA=/data/data/dev.andcode.app/files
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
export HTTPS_PROXY="http://127.0.0.1:7890"
export HTTP_PROXY="http://127.0.0.1:7890"
export NODE_TLS_REJECT_UNAUTHORIZED="0"
export PROOT_LOADER="$ROOT/usr/lib/proot/loader"
export LD_LIBRARY_PATH="$ROOT/usr/lib/proot"
export PROOT_TMP_DIR="$ROOT/tmp"

pkill -f "opencode serve" 2>/dev/null
sleep 1

"$P" -b "$ROOT/etc/resolv.conf:/etc/resolv.conf" \
     -b "$ROOT/etc/ssl:/etc/ssl" \
     -b "$ROOT/etc/ssl:/usr/lib/ssl" \
     -b "$ROOT/etc/passwd:/etc/passwd" \
     -b "$ROOT/etc/group:/etc/group" \
     -b "$ROOT/etc/nsswitch.conf:/etc/nsswitch.conf" \
     -w "$ROOT/home/demo" \
     opencode serve --port 4096 >/data/local/tmp/serve.log 2>&1 &
setsid $! 2>/dev/null

UP=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  sleep 3
  netstat -tln 2>/dev/null | grep -q 4096 && { UP=1; echo "port up after ${i}x3s"; break; }
done
[ "$UP" = 1 ] || { echo "serve failed:"; cat /data/local/tmp/serve.log; exit 1; }

SID=$("$BB" wget -q -O - --header="Content-Type: application/json" \
  --post-data='{"directory":"/data/local/tmp/andcode/home/demo"}' \
  "http://127.0.0.1:4096/session" | sed 's/.*"id":"\([^"]*\)".*/\1/')
echo "session: $SID"

timeout 60 "$BB" wget -q -O /data/local/tmp/msg.json \
  --header="Content-Type: application/json" \
  --post-data="{\"parts\":[{\"type\":\"text\",\"text\":\"Create fib.py with an iterative fib(n), print fib(10)\"}],\"model\":{\"providerID\":\"arjata\",\"modelID\":\"gpt-oss-120b\"},\"agent\":\"build\"}" \
  "http://127.0.0.1:4096/session/$SID/message" 2>&1 | head -n 3
echo "msg sent; 等待模型循环..."
sleep 40

echo "== ERROR 行 =="
grep -E 'level=ERROR' "$HOME/.local/share/opencode/log/opencode.log" 2>/dev/null | tail -n 1 | tail -c 700
echo "== fib.py =="
ls -la "$ROOT/home/demo/fib.py" 2>&1
head -n 12 "$ROOT/home/demo/fib.py" 2>/dev/null
