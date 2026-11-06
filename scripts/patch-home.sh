#!/system/bin/sh
# patch-home.sh v2 — 设备侧修补 wrapper 的 HOME 兜底(无 sed,纯 grep/head/tail 拼接)
# 用法: sh patch-home.sh <bundle-root>
set -u
ROOT="${1:?usage: patch-home.sh <bundle-root>}"

OLD=': "${HOME:=$ROOT/home}"; export HOME'
NEW='case "${HOME:-}" in ""|"/") HOME="$ROOT/home" ;; esac; export HOME'

n=0
for f in "$ROOT"/bin/* "$ROOT"/sbin/* "$ROOT"/usr/bin/* "$ROOT"/usr/libexec/git-core/*; do
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
"$ROOT/bin/opencode" --version >/dev/null 2>&1 && echo "opencode --version: OK" || echo "opencode --version: FAIL"
