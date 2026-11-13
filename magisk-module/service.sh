# service.sh — Boot autostart (Tier M, DESIGN §4.2/§4.6)
# Magisk runs this script as root after boot (avoid blocking: run in the background).
(
  until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 2; done

  INSTALL_DIR=/data/adb/andcode
  [ -d "$INSTALL_DIR" ] || exit 0

  # Recheck the phantom-killer mitigation (some ROMs reset it after reboot, DESIGN §7 R9).
  device_config put activity_manager max_phantom_processes 2147483647 2>/dev/null || true

  # Refresh DNS (network becomes ready after boot; retry with a delay).
  n=0
  until ANDCODE_ROOT="$INSTALL_DIR" ANDCODE_TIER=m \
        sh "$INSTALL_DIR/sbin/andcode-mkresolv" >/dev/null 2>&1; do
    n=$((n+1)); [ $n -ge 15 ] && break; sleep 4
  done

  # Default to bundle mode (loader wrappers); if rootfs/ exists (optional, not injected by CI),
  # a true chroot mode can remove proot/wrapper overhead; operational scripts assemble it.
  ANDCODE_ROOT="$INSTALL_DIR" ANDCODE_TIER=m \
    nohup sh "$INSTALL_DIR/sbin/andcode-entry" sshd >/data/adb/andcode/sshd.log 2>&1 &
) &
