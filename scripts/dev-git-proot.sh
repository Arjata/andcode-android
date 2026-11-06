#!/system/bin/sh
# dev-git-proot.sh — Tier A 修复验证:proot bind /etc + git ls-remote https
ROOT=/data/local/tmp/andcode
P=/data/local/tmp/andcode-proot
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
export LD_LIBRARY_PATH="$P/lib"
export PROOT_LOADER="$P/libexec/proot/loader"

"$P/proot" --version 2>&1 | head -n 1

echo "== git ls-remote under proot =="
timeout 90 "$P/proot" \
  -0 \
  -b "$ROOT/etc/resolv.conf:/etc/resolv.conf" \
  -b "$ROOT/etc/ssl:/etc/ssl" \
  -b "$ROOT/etc/passwd:/etc/passwd" \
  -b "$ROOT/etc/group:/etc/group" \
  -b "$ROOT/etc/nsswitch.conf:/etc/nsswitch.conf" \
  -w "$ROOT" \
  git ls-remote https://github.com/git/git.git HEAD 2>&1 | head -n 4
echo "rc=$?"
