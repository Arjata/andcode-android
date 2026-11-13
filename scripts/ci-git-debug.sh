#!/usr/bin/env bash
# ci-git-debug.sh — Git helper chain diagnostics (CI; runs in a container, bundle extracted at $1, default /opt)
# Probes: helper wrapper contents, direct invocation, sh -c reproduction, and decoys (identify the file Git actually executes).
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

echo "== 诱饵测试: bin 与 libexec 双探针,确认 git 实际 exec 的文件 =="
printf '#!/bin/sh\necho "BAIT-BIN argv0=$0" >&2\nexit 42\n' > "$ROOT/bin/git-remote-https"
chmod +x "$ROOT/bin/git-remote-https"
printf '#!/bin/sh\necho "BAIT-LIBEXEC argv0=$0" >&2\nexit 42\n' > "$ROOT/usr/libexec/git-core/git-remote-https"
chmod +x "$ROOT/usr/libexec/git-core/git-remote-https"
GIT_TRACE=1 timeout 20 git ls-remote https://github.com/git/git.git HEAD 2>&1 | head -n 10
rm -f "$ROOT/bin/git-remote-https"

echo "== sh -x 追踪(诱饵前保留的 wrapper 已被覆盖,此处追踪诱饵) =="
ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a sh -x "$ROOT/usr/libexec/git-core/git-remote-https" \
  '' https://github.com/git/git.git </dev/null 2>&1 | head -n 10

echo "== ls-remote 完整 trace(探针仍在) =="
GIT_TRACE=1 timeout 30 git ls-remote https://github.com/git/git.git HEAD 2>&1 | head -n 14
