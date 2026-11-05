#!/system/bin/sh
# wrapper.sh.tpl — loader 包装器模板(DESIGN §4.1.2, NAMING §6.1/§6.3.2)
# 占位符由 pack-bundle.sh(规范布局)/ pack-apk-libs.sh(Tier P 物理化)渲染:
#   @ROOT@      逻辑根:规范布局渲染为运行期自推导表达式;Tier P 渲染为固定路径
#   @EXEDIR@    可执行物理目录:规范布局 = $ROOT;Tier P = nativeLibraryDir 绝对路径
#   @TARGET@    @EXEDIR@ 内被 exec 的 ELF 物理名(如 opencode.bin / libandcode-opencode.so)
#   @TIER@      m | a | p
#
# Tier P 约束(NAMING §6.3.2):脚本本体随 jniLibs 分发(物理名 libandcode-cmd-<cmd>.so),
# 首行解释器必须是 Android 自带 shell;逻辑名由链接农场符号链接提供。
set -eu

@ROOT@
EXEDIR="@EXEDIR@"
export ANDCODE_ROOT="$ROOT"
export ANDCODE_EXE_DIR="$EXEDIR"
export ANDCODE_TIER="@TIER@"

SHIM="$ROOT/shim/libandcode-shim.so"

# 仅设置 NAMING §5 登记的运行时变量;不覆盖用户显式设置的 OPENCODE_*
: "${HOME:=$ROOT/home}"; export HOME
TMPDIR="$ROOT/tmp"; mkdir -p "$TMPDIR" 2>/dev/null || true; export TMPDIR
PATH="$ROOT/bin:$ROOT/usr/bin:$PATH"; export PATH
LD_LIBRARY_PATH="$EXEDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; export LD_LIBRARY_PATH
if [ -f "$SHIM" ]; then
  LD_PRELOAD="$SHIM${LD_PRELOAD:+:$LD_PRELOAD}"
  export LD_PRELOAD
  ANDCODE_ETC_DIR="$ROOT/etc"; export ANDCODE_ETC_DIR
fi
GIT_EXEC_PATH="$ROOT/usr/libexec/git-core"; export GIT_EXEC_PATH

exec "$EXEDIR/libandcode-ld-linux.so" \
     --library-path "$EXEDIR" \
     --inhibit-cache \
     "$EXEDIR/@TARGET@" "$@"
