#!/system/bin/sh
grep -E 'level=ERROR' /data/adb/andcode/home/.local/share/opencode/log/opencode.log 2>/dev/null | tail -n 2 | tail -c 1200
