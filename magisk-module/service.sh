# service.sh — 开机自启(Tier M,DESIGN §4.2/§4.6)
# Magisk 在 boot 完成后以 root 执行本脚本(阻塞谨慎:后台化)
(
  until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 2; done

  INSTALL_DIR=/data/adb/andcode
  [ -d "$INSTALL_DIR" ] || exit 0

  # phantom-killer 对策复查(部分 ROM 重启后重置,DESIGN §7 R9)
  device_config put activity_manager max_phantom_processes 2147483647 2>/dev/null || true

  # 刷新 DNS(网络在 boot 后才就绪,延迟重试)
  n=0
  until ANDCODE_ROOT="$INSTALL_DIR" ANDCODE_TIER=m \
        sh "$INSTALL_DIR/sbin/andcode-mkresolv" >/dev/null 2>&1; do
    n=$((n+1)); [ $n -ge 15 ] && break; sleep 4
  done

  # 默认 bundle 模式(loader 包装器);若存在 rootfs/(可选,CI 不注入)
  # 则可切换真 chroot 模式以消除 proot/包装器开销 —— 由运维脚本负责组装。
  ANDCODE_ROOT="$INSTALL_DIR" ANDCODE_TIER=m \
    nohup sh "$INSTALL_DIR/sbin/andcode-entry" sshd >/data/adb/andcode/sshd.log 2>&1 &
) &
