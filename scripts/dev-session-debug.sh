#!/system/bin/sh
# dev-session-debug.sh — opencode run with DEBUG logs via proxy session env
ROOT=/data/local/tmp/andcode
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export ANDCODE_APP_DATA=/data/data/dev.andcode.app/files
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
export HTTPS_PROXY="http://127.0.0.1:7890"
export HTTP_PROXY="http://127.0.0.1:7890"
cd "$HOME/demo" || exit 1
timeout 300 opencode run --log-level DEBUG "say ok" 2>&1 | tail -n 4
L="$HOME/.local/share/opencode/log/opencode.log"
echo "== 最后的 ERROR/堆栈 =="
grep -nE 'level=ERROR' "$L" | tail -n 1
awk '/level=ERROR/{n=NR} END{print n}' "$L" > /data/local/tmp/.ln
LN=$(cat /data/local/tmp/.ln)
sed -n "${LN}p" "$L" | tail -c 1200
