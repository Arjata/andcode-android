#!/usr/bin/env bash
# ci-git-debug.sh — git 助手链路诊断(CI 用;容器内执行,bundle 解包在 $1,默认 /opt)
# 探针: helper wrapper 内容、直接调用、sh -c 复现、诱饵测试(确认 git 实际执行哪个文件)
set -u
ROOT="${1:-/opt}"
export PATH="$ROOT/bin:$ROOT/usr/bin:$PATH"

echo "== helper wrapper head =="
head -n 3 "$ROOT/usr/libexec/git-core/git-remote-https" 2>&1

echo "== wrapper 字节与占位符残留 =="
wc -c "$ROOT/usr/libexec/git-core/git-remote-https" 2>&1
grep -n '@ROOT@\|@EXEDIR@\|@LOADER@\|@LIBPATH@\|@TARGET@\|@TIER@' \
     "$ROOT/usr/libexec/git-core/git-remote-https" 2>&1 | head -n 5 || echo "  (无未渲染占位符)"

echo "== git --exec-path =="
git --exec-path 2>&1

echo "== 直接调用 helper(origin url, stdin 关闭) =="
GIT_EXEC_PATH="$ROOT/usr/libexec/git-core" timeout 12 \
  "$ROOT/usr/libexec/git-core/git-remote-https" origin https://github.com/git/git.git \
  </dev/null 2>/tmp/herr >/tmp/hout
echo "  helper rc=$?"
echo "  -- stderr:"; head -n 5 /tmp/herr | sed 's/^/    | /'
echo "  -- stdout:"; head -n 5 /tmp/hout | sed 's/^/    | /'

echo "== 诱饵测试: 替换 helper 为探针,确认 git 实际 exec 的文件 =="
printf '#!/bin/sh\necho "BAIT argv0=$0 args=$*" >&2\nexit 42\n' > "$ROOT/usr/libexec/git-core/git-remote-https"
chmod +x "$ROOT/usr/libexec/git-core/git-remote-https"
GIT_TRACE=1 timeout 20 git ls-remote https://github.com/git/git.git HEAD 2>&1 | head -n 10

echo "== sh -x 追踪(诱饵前保留的 wrapper 已被覆盖,此处追踪诱饵) =="
ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a sh -x "$ROOT/usr/libexec/git-core/git-remote-https" \
  '' https://github.com/git/git.git </dev/null 2>&1 | head -n 10

echo "== ls-remote 完整 trace(探针仍在) =="
GIT_TRACE=1 timeout 30 git ls-remote https://github.com/git/git.git HEAD 2>&1 | head -n 14
