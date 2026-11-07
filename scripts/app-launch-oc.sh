#!/system/bin/sh
# opencode TUI(Tier P 应用上下文)
# 1) bundle=apk_data_file 应用只读;可写状态(HOME/TMPDIR/BUN_TMPDIR)在应用 filesDir
# 2) BUN_TMPDIR:Bun 提取内嵌原生库(libopentui)的目录,必须应用可写
# 3) ANDCODE_IN_PROOT=1: TUI 跳过 proot;GLIBC_TUNABLES 关闭 rseq 注册
# 4) ld.so/libc.so.6 已打 seccomp 兼容补丁(set_robust_list/rseq/clone3)
export ANDCODE_ROOT=/data/local/tmp/andcode
export ANDCODE_TIER=a
APP=/data/data/dev.andcode.app/files
export ANDCODE_APP_DATA=$APP
mkdir -p $APP/home/.config/opencode $APP/tmp $APP/home/demo
[ -f $APP/home/.config/opencode/opencode.json ] || cp /data/local/tmp/andcode/home/.config/opencode/opencode.json $APP/home/.config/opencode/ 2>/dev/null
export PATH=/data/local/tmp/andcode/bin:/data/local/tmp/andcode/usr/bin:$PATH
export HOME=$APP/home
export TMPDIR=$APP/tmp
export BUN_TMPDIR=$APP/tmp
export ANDCODE_IN_PROOT=1
export GLIBC_TUNABLES=glibc.pthread.rseq=0
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890
export NODE_TLS_REJECT_UNAUTHORIZED=0
cd $APP/home/demo
exec opencode 2>/data/data/dev.andcode.app/files/tui-stderr.log