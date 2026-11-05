#!/system/bin/sh
# wrapper.sh.tpl — loader 包装器模板(DESIGN §4.1.2, NAMING §6.1/§6.3.2)
# 占位符:
#   @ROOT@      逻辑根:规范布局=运行期自推导表达式;Tier P=ANDCODE_ROOT 引用
#   @EXEDIR@    可执行物理目录:规范布局=$ROOT;Tier P=$ANDCODE_EXE_DIR(nativeLibraryDir)
#   @LOADER@    动态链接器路径:规范布局=$ROOT/lib/ld-linux-aarch64.so.1;
#               Tier P=$ANDCODE_EXE_DIR/libandcode-ld-linux.so(NAMING §6.3)
#   @LIBPATH@   --library-path:规范布局=$ROOT/lib;Tier P=$ANDCODE_EXE_DIR(路线甲:库全在 jniLibs)
#   @TARGET@    @EXEDIR@ 内被 exec 的 ELF 物理名(opencode.bin / libandcode-opencode.so)
#   @TIER@      m | a | p
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

exec "@LOADER@" \
     --library-path "@LIBPATH@" \
     --inhibit-cache \
     "$EXEDIR/@TARGET@" "$@"
