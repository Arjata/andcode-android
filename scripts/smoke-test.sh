#!/usr/bin/env bash
# smoke-test.sh — 三形态共用验收(DESIGN §6;Tier A 由 deploy-adb.sh 调用,
# Tier M 在设备上直跑,Tier P 由 APK 设置页等价触发)
# 设备侧用法: ANDCODE_ROOT=<安装目录> ANDCODE_TIER=<m|a|p> sh smoke-test.sh
# 说明: 本脚本设计为 POSIX sh 兼容,便于直接 `adb shell sh ...` 执行。
set -u
ROOT="${ANDCODE_ROOT:?ANDCODE_ROOT 未设置}"
TIER="${ANDCODE_TIER:-a}"
fail=0

ok()   { echo "[PASS] $1"; }
bad()  { echo "[FAIL] $1"; fail=$((fail+1)); }

t() { # $1=描述 其余=命令;失败时回显输出便于 CI 诊断
  d="$1"; shift
  out="$("$@" 2>&1)"
  if [ $? -eq 0 ]; then ok "$d"; else bad "$d"; printf '%s\n' "$out" | head -n 5 | sed 's/^/       | /'; fi
}

t "loader 可执行(--version)"   "$ROOT/lib/ld-linux-aarch64.so.1" --version
t "shim 存在"                   test -f "$ROOT/shim/libandcode-shim.so"
t "resolv.conf 已生成"          test -s "$ROOT/etc/resolv.conf"
t "opencode --version"          "$ROOT/bin/opencode" --version
t "git --version"               "$ROOT/usr/bin/git" --version
t "DNS 解析(bundle resolv.conf)" sh -c "PATH=$ROOT/bin:$ROOT/usr/bin:\$PATH getent hosts github.com || getent hosts github.com"
t "git https 助手(wrapper 链路)" sh -c "PATH=$ROOT/bin:$ROOT/usr/bin:\$PATH GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=30 timeout 90 git ls-remote https://github.com/git/git.git HEAD"
t "busybox 可用"                "$ROOT/bin/busybox" true
t "andcode-entry doctor"        sh "$ROOT/bin/andcode-doctor"

# P0 专项(允许失败,仅报告):
echo "----"
if "$ROOT/bin/opencode" --version >/dev/null 2>&1; then
  echo "[INFO] JIT 定级: 详见 P0 结论(BUN_JSC_useJIT 未自动探测)"
fi
echo "smoke-test($TIER): $([ $fail -eq 0 ] && echo ALL-PASS || echo "$fail FAILED")"
if [ "$fail" -ne 0 ]; then
  echo "---- 诊断 ----"
  ls -la "$ROOT" 2>&1 | head -n 12
  ls "$ROOT/lib" 2>&1 | head -n 8
  ls "$ROOT/bin" 2>&1 | head -n 8
  ls "$ROOT/usr/bin" 2>&1 | head -n 5
  head -n 1 "$ROOT/bin/opencode" 2>&1
fi
exit $([ "$fail" -eq 0 ] && echo 0 || echo 1)
