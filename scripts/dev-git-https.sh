#!/system/bin/sh
# dev-git-https.sh — 真机 git https 链路验证(Tier A)v2
ROOT=/data/local/tmp/andcode
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
cd "$ROOT"
echo "== which git =="; command -v git
echo "== ls-remote =="
timeout 90 git ls-remote https://github.com/git/git.git HEAD 2>&1 | head -n 4
echo "rc=$?"
