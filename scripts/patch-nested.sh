#!/system/bin/sh
# patch-nested.sh — Add a nested-proot guard to wrappers (ANDCODE_IN_PROOT)
# Usage: sh patch-nested.sh <bundle-root>
set -u
ROOT="${1:?usage: patch-nested.sh <bundle-root>}"

OLD1='if [ -x "$PROOT" ] && [ -e /system/bin/sh ]; then'
NEW1='if [ -x "$PROOT" ] && [ -e /system/bin/sh ] && [ -z "${ANDCODE_IN_PROOT:-}" ]; then'
OLD2='export PROOT_LOADER="$ROOT/usr/lib/proot/loader"'
NEW2='export PROOT_LOADER="$ROOT/usr/lib/proot/loader"
export ANDCODE_IN_PROOT=1'

splice() { # $1=file $2=old-line $3=new-block
  ln=$(grep -nF "$2" "$1" 2>/dev/null | head -n 1 | cut -d: -f1)
  [ -n "$ln" ] || return 0
  head -n $((ln - 1)) "$1" > "$1.tmp" 2>/dev/null
  printf '%s\n' "$3" >> "$1.tmp"
  tail -n +$((ln + 1)) "$1" >> "$1.tmp" 2>/dev/null
  cat "$1.tmp" > "$1"
  rm -f "$1.tmp"
  chmod 0755 "$1"
}

n=0
for f in "$ROOT"/bin/* "$ROOT"/sbin/* "$ROOT"/usr/bin/*; do
  [ -f "$f" ] || continue
  grep -qF "$OLD1" "$f" 2>/dev/null || continue
  splice "$f" "$OLD1" "$NEW1"
  splice "$f" "$OLD2" "$NEW2"
  n=$((n + 1))
done
echo "patched: $n wrappers"
