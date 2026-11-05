# uninstall.sh — Magisk 卸载清理(Tier M)
pkill -f dropbear 2>/dev/null || true
rm -rf /data/adb/andcode
