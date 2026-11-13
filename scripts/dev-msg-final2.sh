#!/system/bin/sh
# dev-msg-final2.sh — Absolute busybox path + full model loop trigger
ROOT=/data/local/tmp/andcode
BB="$ROOT/bin/busybox"
SID=$(sed 's/.*"id":"\([^"]*\)".*/\1/' /data/local/tmp/sess.json)
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
echo "session: $SID"
timeout 60 "$BB" wget -q -O /data/local/tmp/msg.json \
  --header="Content-Type: application/json" \
  --post-data="{\"parts\":[{\"type\":\"text\",\"text\":\"Create fib.py with an iterative fib(n), print fib(10)\"}],\"model\":{\"providerID\":\"arjata\",\"modelID\":\"gpt-oss-120b\"},\"agent\":\"build\"}" \
  "http://127.0.0.1:4096/session/$SID/message" 2>&1 | head -n 3
sleep 35
echo "== server 侧 ERROR =="
grep -E 'level=ERROR' "$ROOT/home/.local/share/opencode/log/opencode.log" 2>/dev/null | tail -n 1 | tail -c 900
echo "== fib.py =="
ls -la "$ROOT/home/demo/fib.py" 2>&1
