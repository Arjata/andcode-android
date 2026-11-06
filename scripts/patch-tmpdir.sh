#!/system/bin/sh
# patch-tmpdir.sh — andcode-entry 加 PROOT_TMP_DIR(应用 uid 需可写临时目录)
F=/data/local/tmp/andcode/sbin/andcode-entry
OLD='export LD_LIBRARY_PATH="$ROOT/usr/lib/proot${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"'
NEW="$OLD
export PROOT_TMP_DIR=\"\$ROOT/tmp\""
ln=$(grep -nF "$OLD" "$F" | head -n 1 | cut -d: -f1)
[ -n "$ln" ] || { echo "marker not found"; exit 1; }
head -n $((ln)) "$F" > "$F.tmp"
printf '%s\n' "$NEW" >> "$F.tmp"
tail -n +$((ln + 1)) "$F" >> "$F.tmp"
cat "$F.tmp" > "$F"
rm -f "$F.tmp"
chmod 0755 "$F"
grep -c PROOT_TMP_DIR "$F"
