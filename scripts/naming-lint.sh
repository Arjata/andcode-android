#!/usr/bin/env bash
# naming-lint.sh — 命名规范 CI 门禁(NAMING §8)
# 用法: naming-lint.sh --bundle-dir <解包后的 andcode/> [--blacklist <system-bin-snapshot>]
set -euo pipefail

DIR="" BLACKLIST=""
while [ $# -gt 0 ]; do
  case "$1" in
    --bundle-dir) DIR="$2"; shift 2 ;;
    --blacklist) BLACKLIST="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done
[ -n "$DIR" ] || { grep '^# 用法' -A2 "$0"; exit 2; }

fail=0

# 1. manifest 存在且物理名合规(data 类物理名占位 "-",docs/LFS 与 NAMING §6.2)
[ -f "$DIR/manifest" ] || { echo "[FAIL] 缺少 manifest"; exit 1; }
while IFS=$'\t' read -r lp phys kind lic ver up; do
  case "$lp" in '#'*|"") continue ;; esac
  if [ "$kind" = "data" ]; then
    [ "$phys" = "-" ] || { echo "[FAIL] data 类物理名必须为 '-': $lp"; fail=1; }
    continue
  fi
  printf '%s' "$phys" | grep -qE '^libandcode-[a-z0-9-]+\.so$' \
    || { echo "[FAIL] 物理名: '$phys' ← $lp"; fail=1; }
  [ ${#phys} -le 64 ] || { echo "[FAIL] 物理名超 64 字符: $phys"; fail=1; }
  printf '%s' "$kind" | grep -qE '^(elf-exec|wrapper-sh|launcher|glibc-lib|preload-lib|script|data|alias)$' \
    || { echo "[FAIL] kind: '$kind' ← $lp"; fail=1; }
done < "$DIR/manifest"

# 2. bundle 内路径名规则([a-z0-9-],.bin 双名与 soname/数据文件等模板例外)
while IFS= read -r -d '' f; do
  rel="${f#$DIR/}"
  case "$rel" in
    manifest|root/etc/*|root/home/*|root/tmp/*|root/lib/*|etc/*|home/*|tmp/*|lib/*|shim/*|*.so*) continue ;;
  esac
  n="$(basename "$rel")"
  case "$n" in
    *.bin) printf '%s' "${n%.bin}" | grep -qE '^[a-z0-9-]+$' \
             || { echo "[FAIL] .bin 名: $rel"; fail=1; } ;;
    libandcode-*) : ;;   # shim 等,合法
    *) printf '%s' "$n" | grep -qE '^[a-z0-9-]+$' \
         || { echo "[FAIL] 文件名: $rel"; fail=1; } ;;
  esac
done < <(find "$DIR" -type f -print0)

# 3. toybox 黑名单(链接农场禁令,NAMING §6.4)
if [ -n "$BLACKLIST" ] && [ -f "$BLACKLIST" ]; then
  while IFS= read -r -d '' f; do
    n="$(basename "$f")"
    if grep -qx "$n" "$BLACKLIST"; then
      echo "[FAIL] 与 /system/bin 冲突的逻辑名: $n"; fail=1
    fi
  done < <(find "$DIR/bin" "$DIR/sbin" -type f -print0 2>/dev/null || true)
fi

# 4. 仓库脚本位置规则(.sh 仅 scripts/;magisk-module 为 Magisk 平台约定豁免)
off="$(find . -name '*.sh' ! -path './scripts/*' ! -path './baseline/*' ! -path './bundle/*' ! -path './runtime/*' ! -path './magisk-module/*' ! -path './work/*' ! -path './.git/*' 2>/dev/null || true)"
if [ -n "$off" ]; then
  # 豁免:模板/模块目录内文件不检查;其余违规
  echo "[提示] scripts 之外的 .sh(人工复核): $off"
fi

echo "naming-lint: $([ $fail -eq 0 ] && echo PASS || echo FAIL)"
exit $fail
