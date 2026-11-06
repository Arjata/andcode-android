#!/system/bin/sh
# dev-serve-env.sh — 启动 opencode serve,抓 server 进程环境(验证 env 继承)
ROOT=/data/local/tmp/andcode
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export ANDCODE_APP_DATA=/data/data/dev.andcode.app/files
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
export HTTPS_PROXY="http://127.0.0.1:7890"
export HTTP_PROXY="http://127.0.0.1:7890"
cd "$ROOT/home/demo" || exit 1

opencode serve --port 4096 >/data/local/tmp/serve.log 2>&1 &
SPID=$!
sleep 6
echo "== serve 进程 =="
for p in $(pidof opencode 2>/dev/null); do
  echo "pid $p:"; tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -E '^(ANDCODE_ROOT|PATH|HOME)=' | head -n 3
done
echo "== 本机探针: 建会话 =="
busybox wget -q -O /data/local/tmp/sess.json \
  --header="Content-Type: application/json" \
  --post-data='{"directory":"/data/local/tmp/andcode/home/demo"}' \
  "http://127.0.0.1:4096/session" 2>&1 | head -n 2
head -c 300 /data/local/tmp/sess.json 2>/dev/null; echo
kill $SPID 2>/dev/null
