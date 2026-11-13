#!/system/bin/sh
# dev-session-proxy.sh — Real opencode coding session (via the host Clash HTTP proxy)
ROOT=/data/local/tmp/andcode
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export ANDCODE_APP_DATA=/data/data/dev.andcode.app/files
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
export HTTPS_PROXY="http://127.0.0.1:7890"
export HTTP_PROXY="http://127.0.0.1:7890"
export NODE_TLS_REJECT_UNAUTHORIZED="0"
mkdir -p "$HOME/.config/opencode"
cp /data/local/tmp/oc-config.json "$HOME/.config/opencode/opencode.json" 2>/dev/null
mkdir -p "$HOME/demo" && cd "$HOME/demo" || exit 1
[ -d .git ] || { git init -q .; git config user.email t@t; git config user.name t; echo "# demo" > README.md; git add README.md; git commit -qm init; }
rm -f fib.py
timeout 300 opencode run "Create a file named fib.py containing a Python function fib(n) returning the nth Fibonacci number iteratively, and print fib(10) under if __name__ == '__main__'." 2>&1 | tail -n 12
echo "----"
ls -la fib.py 2>&1
head -n 15 fib.py 2>/dev/null
