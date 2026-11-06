#!/system/bin/sh
# dev-helper-debug.sh — 真机定位 git helper 执行路径(ROOT)
ROOT=/data/local/tmp/andcode
H="$ROOT/usr/libexec/git-core"
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export PATH="$ROOT/bin:$ROOT/usr/bin:$H:$PATH"
export HOME="$ROOT/home"

echo "== wrapper 文件 =="
wc -c "$H/git-remote-https"; head -n 2 "$H/git-remote-https"
echo "== 直接 sh -x 跑 wrapper(stdin 关闭) =="
sh -x "$H/git-remote-https" '' https://github.com/git/git.git </dev/null 2>&1 | head -n 30
echo "== 诱饵: helper 换探针 =="
printf '#!/system/bin/sh\necho "BAIT $0 $*" >&2\nexit 42\n' > "$H/git-remote-https"
chmod +x "$H/git-remote-https"
timeout 20 git ls-remote https://github.com/git/git.git HEAD 2>&1 | head -n 8
echo "== 恢复 wrapper 后再跑 =="
sh "$ROOT/bin/andcode-doctor" >/dev/null 2>&1 || true
