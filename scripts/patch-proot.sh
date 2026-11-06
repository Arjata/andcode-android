#!/system/bin/sh
# patch-proot.sh — wrapper proot 分支前清除 LD_PRELOAD(proot 为 Bionic 二进制,
# 不能加载 glibc shim;/etc 重定向已由 proot bind 接管)
# 用法: sh patch-proot.sh <bundle-root>
set -u
ROOT="${1:?usage: patch-proot.sh <bundle-root>}"

OLD='PROOT="$ROOT/usr/lib/proot/proot"'
NEW='PROOT="$ROOT/usr/lib/proot/proot"
unset LD_PRELOAD 2>/dev/null'

n=0
for f in "$ROOT"/bin/* "$ROOT"/sbin/* "$ROOT"/usr/bin/*; do
  [ -f "$f" ] || continue
  grep -qF "$OLD" "$f" 2>/dev/null || continue
  ln=$(grep -nF "$OLD" "$f" | head -n 1 | cut -d: -f1)
  [ -n "$ln" ] || continue
  head -n $((ln - 1)) "$f" > "$f.tmp" 2>/dev/null
  printf '%s\n' "$NEW" >> "$f.tmp"
  tail -n +$((ln + 1)) "$f" >> "$f.tmp" 2>/dev/null
  cat "$f.tmp" > "$f"
  rm -f "$f.tmp"
  chmod 0755 "$f"
  n=$((n + 1))
done
echo "patched: $n wrappers"
