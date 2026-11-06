#!/system/bin/sh
# patch-entry-libpath.sh — andcode-entry 的 proot 分支补 LD_LIBRARY_PATH
ROOT=/data/local/tmp/andcode
F="$ROOT/sbin/andcode-entry"
OLD='export PROOT_LOADER="$ROOT/usr/lib/proot/loader"'
NEW='export PROOT_LOADER="$ROOT/usr/lib/proot/loader"
export LD_LIBRARY_PATH="$ROOT/usr/lib/proot${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"'
ln=$(grep -nF "$OLD" "$F" | head -n 1 | cut -d: -f1)
[ -n "$ln" ] || { echo "marker not found"; exit 1; }
head -n $((ln - 1)) "$F" > "$F.tmp"
printf '%s\n' "$NEW" >> "$F.tmp"
tail -n +$((ln + 1)) "$F" >> "$F.tmp"
cat "$F.tmp" > "$F"
rm -f "$F.tmp"
chmod 0755 "$F"
grep -c LD_LIBRARY_PATH "$F"
