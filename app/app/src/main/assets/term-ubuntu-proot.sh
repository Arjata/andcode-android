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
        proxy=*) proxy=${1#proxy=} ;;
        wait-install) wait_install=1 ;;
    esac
    shift
done
[ -f "$ROOT/usr/bin/bash" ] && [ -f "$P/proot" ] && [ -f "$P/loader" ] || {
    if [ "$wait_install" = 1 ]; then
        echo 'Preparing the Ubuntu instance (first run, 1-2 minutes)...' >&2
        n=0
        while [ ! -f "$ROOT.digest" ] && [ "$n" -lt 300 ]; do sleep 2; n=$((n+2)); done
        [ -f "$ROOT/usr/bin/bash" ] || { echo 'Ubuntu instance extraction failed; session not started.' >&2; exit 1; }
        [ -f "$P/proot" ] && [ -f "$P/loader" ] || { echo 'PRoot payload missing.' >&2; exit 1; }
        echo 'Ubuntu instance ready.' >&2
    else
        echo 'Ubuntu PRoot instance not installed; session not started.' >&2
        exit 1
    fi
}
echo 'Ubuntu PRoot dev backend: fake root, not host root; not a security sandbox.' >&2
[ "$#" -gt 0 ] || set -- /bin/bash --noprofile --norc -i
set -- /usr/bin/env -i HOME=/root USER=root LOGNAME=root SHELL=/bin/bash \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    TERM=xterm-256color LANG=C.UTF-8 GLIBC_TUNABLES=glibc.pthread.rseq=0 \
    http_proxy="$proxy" https_proxy="$proxy" "$@"
WORK=/root
NAME=${ANDCODE_UBUNTU_PROJECT_NAME:-}
if [ -n "$NAME" ]; then
    case "$NAME" in .|..|*/*|*\\*|*:*) echo 'Invalid project name rejected.' >&2; exit 1 ;; esac
    PROJECT=$FILES/projects/$NAME
    # Reject symlink roots and aliases; never silently run in a different cwd.
    [ ! -L "$FILES/projects" ] && [ ! -L "$PROJECT" ] && [ -d "$PROJECT" ] \
        && [ "$(/system/bin/toybox realpath "$PROJECT")" = "$(/system/bin/toybox realpath "$FILES")/projects/$NAME" ] || {
        echo 'Selected project missing or unsafe; session not started.' >&2
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
echo ""
cat <<'ANDCODE_BANNER'

  ##   #    # #####   ####   ####  #####  ######
 #  #  ##   # #    # #    # #    # #    # #
#    # # #  # #    # #      #    # #    # #####
###### #  # # #    # #      #    # #    # #
#    # #   ## #    # #    # #    # #    # #
#    # #    # #####   ####   ####  #####  ######
 andcode · opencode AI coding agent on Android
 Ubuntu 24.04 dev rootfs (single-APK)
ANDCODE_BANNER
REL=$(getprop ro.build.version.release 2>/dev/null | head -1)
[ -n "$REL" ] && echo " Android $REL" >&2
echo " Linux $(uname -r) $(uname -m)" >&2
MEMKB=$(grep MemAvailable /proc/meminfo 2>/dev/null | head -1 | sed "s/[^0-9]//g")
[ -n "$MEMKB" ] && echo " Memory: $((MEMKB / 1048576)).$((MEMKB % 1048576 * 10 / 1048576)) GB available" >&2
FREEKB=$(df -k $FILES 2>/dev/null | tail -1 | sed "s/[^0-9].*//")
[ -n "$FREEKB" ] && echo " Storage free: $((FREEKB / 1048576)) GB" >&2
echo "" >&2
exec "$P/proot" --kill-on-exit -l -0 -r "$ROOT" -b /dev -b /proc "$@"
