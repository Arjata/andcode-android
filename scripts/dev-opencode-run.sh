#!/system/bin/sh
# dev-opencode-run.sh — Full opencode startup verification on a device (Tier A, via proot)
ROOT=/data/local/tmp/andcode
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
cd "$ROOT/home"
echo "== opencode --help =="
timeout 60 opencode --help 2>&1 | head -n 8
echo "rc=$?"
echo "== git init 测试仓库 + opencode 可见性 =="
mkdir -p "$ROOT/home/demo" && cd "$ROOT/home/demo"
[ -d .git ] || git init -q . 2>&1
git config user.email t@t; git config user.name t
echo hello > a.txt && git add a.txt && git commit -qm init 2>&1 | head -n 2
git log --oneline | head -n 2
