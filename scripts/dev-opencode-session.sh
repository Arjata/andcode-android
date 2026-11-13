#!/system/bin/sh
# dev-opencode-session.sh — Real opencode coding session on a device (P0 final acceptance)
# Prerequisite: configuration pushed to /data/local/tmp/oc-config.json (includes provider/model; do not commit).
ROOT=/data/local/tmp/andcode
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
P="$ROOT/usr/lib/proot/proot"
export PROOT_LOADER="$ROOT/usr/lib/proot/loader"

mkdir -p "$HOME/.config/opencode"
cp /data/local/tmp/oc-config.json "$HOME/.config/opencode/opencode.json"
mkdir -p "$HOME/demo" && cd "$HOME/demo" || exit 1
[ -d .git ] || { git init -q .; git config user.email t@t; git config user.name t; echo "# demo" > README.md; git add README.md; git commit -qm init; }
rm -f fib.py

echo "== opencode run(glm-5.3-flash, 经 proot)=="
timeout 300 opencode run "Create a file named fib.py containing a Python function fib(n) that returns the nth Fibonacci number iteratively, then print fib(10) under if __name__ == '__main__'." 2>&1 | tail -n 15
echo "run rc=$?"

echo "== 验证产物 =="
ls -la fib.py 2>&1
[ -f fib.py ] && head -n 20 fib.py
python -c "import fib; print('fib(10) =', fib.fib(10))" 2>/dev/null || echo "(设备无 python,语法留待人工核验)"
