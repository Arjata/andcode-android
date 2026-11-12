#!/system/bin/sh
# Development backend, not a security boundary. Read with /system/bin/sh.
set -eu
FILES=${ANDCODE_APP_DATA:?missing app files directory}
ROOT=$FILES/proot-rootfs
P=/data/local/tmp/andcode/usr/lib/proot
PLIB=$P
if [ -n "${ANDCODE_ROOT:-}" ] && [ "${ANDCODE_TIER:-}" = p ]; then
    P=$ANDCODE_ROOT/usr/lib/proot
    PLIB=${ANDCODE_EXE_DIR:?missing native payload directory}
fi
proxy=''
wait_install=0
while [ $# -gt 0 ]; do
    case "$1" in
        loopback-proxy) proxy=http://127.0.0.1:7890 ;;
        wait-install) wait_install=1 ;;
    esac
    shift
done
[ -f "$ROOT/usr/bin/bash" ] && [ -f "$P/proot" ] && [ -f "$P/loader" ] || {
    if [ "$wait_install" = 1 ]; then
        echo '正在准备 Ubuntu 实例（首次约 1-2 分钟）...' >&2
        n=0
        while [ ! -f "$ROOT.digest" ] && [ "$n" -lt 300 ]; do sleep 2; n=$((n+2)); done
        [ -f "$ROOT/usr/bin/bash" ] || { echo 'Ubuntu 实例提取失败；会话未启动。' >&2; exit 1; }
        [ -f "$P/proot" ] && [ -f "$P/loader" ] || { echo 'PRoot 载荷缺失。' >&2; exit 1; }
        echo 'Ubuntu 实例就绪。' >&2
    else
        echo 'Ubuntu PRoot 实例未安装；会话未启动。' >&2
        exit 1
    fi
}
echo 'Ubuntu PRoot 开发后端：fake root 非宿主 root；不是安全沙箱。' >&2
[ "$#" -gt 0 ] || set -- /bin/bash --noprofile --norc -i
set -- /usr/bin/env -i HOME=/root USER=root LOGNAME=root SHELL=/bin/bash \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    TERM=xterm-256color LANG=C.UTF-8 GLIBC_TUNABLES=glibc.pthread.rseq=0 \
    http_proxy="$proxy" https_proxy="$proxy" "$@"
WORK=/root
NAME=${ANDCODE_UBUNTU_PROJECT_NAME:-}
if [ -n "$NAME" ]; then
    case "$NAME" in .|..|*/*|*\\*|*:*) echo '拒绝无效项目名。' >&2; exit 1 ;; esac
    PROJECT=$FILES/projects/$NAME
    # Reject symlink roots and aliases; never silently run in a different cwd.
    [ ! -L "$FILES/projects" ] && [ ! -L "$PROJECT" ] && [ -d "$PROJECT" ] \
        && [ "$(/system/bin/toybox realpath "$PROJECT")" = "$(/system/bin/toybox realpath "$FILES")/projects/$NAME" ] || {
        echo '选中项目不存在或路径不安全；会话未启动。' >&2
        exit 1
    }
    WORK=/workspace/$NAME
    set -- -b "$PROJECT:$WORK" -w "$WORK" "$@"
else
    set -- -w "$WORK" "$@"
fi
export PROOT_LOADER="$P/loader" LD_LIBRARY_PATH="$PLIB" PROOT_TMP_DIR="$FILES/tmp"
export GLIBC_TUNABLES=glibc.pthread.rseq=0
# 设备存储:FUSE 视图受平台权限约束(Download/媒体已实测可读写)。
SDCARD=/storage/emulated/0
[ -d "$SDCARD" ] && set -- -b "$SDCARD:/mnt/sdcard" "$@"
exec "$P/proot" --kill-on-exit -l -0 -r "$ROOT" -b /dev -b /proc "$@"
