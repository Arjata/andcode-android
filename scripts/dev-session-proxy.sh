#!/system/bin/sh
# dev-session-proxy.sh — opencode 真实会话(经本机 Clash HTTP 代理)
ROOT=/data/local/tmp/andcode
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export ANDCODE_APP_DATA=/data/data/dev.andcode.app/files
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
export HTTPS_PROXY="http://127.0.0.1:7890"
export HTTP_PROXY="http://127.0.0.1:7890"
cd "$HOME/demo" || exit 1
rm -f fib.py
timeout 300 opencode run "Create a file named fib.py containing a Python function fib(n) returning the nth Fibonacci number iteratively, and print fib(10) under if __name__ == '__main__'." 2>&1 | tail -n 12
echo "----"
ls -la fib.py 2>&1
head -n 15 fib.py 2>/dev/null
