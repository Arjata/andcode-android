# uninstall.sh — Magisk uninstall cleanup (Tier M)
pkill -f dropbear 2>/dev/null || true
rm -rf /data/adb/andcode
