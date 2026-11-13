# customize.sh — Magisk installation script (Tier M, DESIGN §4.2)
# Module ZIP contents: scripts from this directory + andcode-bundle-arm64.tar.gz (injected by CI during packaging)
SKIPUNZIP=0
ui_print "- andcode: 释放交付包"
BUNDLE_ZIP="$ZIPFILE"   # Installer variable; the bundle is an additional entry in the ZIP.

# Extract the bundle (for ziptune, CI adds andcode-bundle-*.tar.gz to the module ZIP).
unzip -o "$ZIPFILE" 'andcode-bundle-*.tar.gz' -d "$MODPATH" >/dev/null 2>&1 || true
BK="$(ls "$MODPATH"/andcode-bundle-*.tar.gz 2>/dev/null | head -n1 || true)"
[ -n "$BK" ] || { ui_print "! 未找到 bundle,模块将以空壳安装"; exit 1; }

INSTALL_DIR=/data/adb/andcode
mkdir -p "$INSTALL_DIR"
tar -xzf "$BK" -C "$INSTALL_DIR" --strip-components=1
rm -f "$BK"
chmod -R 0755 "$INSTALL_DIR/bin" "$INSTALL_DIR/sbin" "$INSTALL_DIR/usr/bin"

ui_print "- 初始化运行目录与 resolv.conf"
mkdir -p "$INSTALL_DIR/home" "$INSTALL_DIR/tmp" "$INSTALL_DIR/etc"
ANDCODE_ROOT="$INSTALL_DIR" ANDCODE_TIER=m sh "$INSTALL_DIR/sbin/andcode-mkresolv" || true

ui_print "- 固化 Phantom Process Killer 对策(DESIGN §4.6, root 专属)"
settings put global settings_enable_monitor_phantom_procs false 2>/dev/null || true
setprop persist.device_config.activity_manager.max_phantom_processes 2147483647 2>/dev/null || true
device_config put activity_manager max_phantom_processes 2147483647 2>/dev/null || true

ui_print "- 完成: 重启后由 service.sh 自动启动 sshd(127.0.0.1:2222)"
ui_print "  手动入口: su -c /data/adb/andcode/sbin/andcode-entry doctor"
