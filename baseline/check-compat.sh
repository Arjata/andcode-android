#!/usr/bin/env bash
# check-compat.sh — andcode 兼容性审计门禁(DESIGN §3.3, NAMING §8)
# 用法: check-compat.sh [--page-align] <elf-or-dir> [more...]
#   审计每个 aarch64 ELF:
#     1) glibc 符号版本上限 ≤ $MAX_GLIBC(默认 2.39)
#     2) NEEDED 依赖列表输出(人工/脚本复核是否已捆绑)
#     3) --page-align: 校验 PT_LOAD p_align ≥ 16384(16K 页设备,DESIGN §1.2.8)
# 任一违规 → 退出码 1。
set -euo pipefail

MAX_GLIBC="${MAX_GLIBC:-2.39}"
PAGE_ALIGN=0
TARGETS=()
for arg in "$@"; do
  case "$arg" in
    --page-align) PAGE_ALIGN=1 ;;
    -h|--help) echo "usage: $0 [--page-align] <elf-or-dir>..."; exit 0 ;;
    *) TARGETS+=("$arg") ;;
  esac
done
[ ${#TARGETS[@]} -gt 0 ] || { echo "no targets"; exit 2; }

ver_le() { # $1,$2 版本比较, $1 ≤ $2 → 0
  [ "$(printf '%s\n' "$1" "$2" | sort -V | head -n1)" = "$1" ]
}

collect_elfs() {
  for t in "${TARGETS[@]}"; do
    if [ -d "$t" ]; then
      find "$t" -type f -print0
    else
      printf '%s\0' "$t"
    fi
  done | while IFS= read -r -d '' f; do
    if file -b "$f" | grep -q 'ELF 64-bit.*ARM aarch64'; then printf '%s\0' "$f"; fi
  done
}

fail=0; n_elf=0
while IFS= read -r -d '' elf; do
  n_elf=$((n_elf+1))
  # 1) glibc 符号版本
  maxver="$(objdump -T "$elf" 2>/dev/null | grep -oE 'GLIBC_[0-9.]+' | sed 's/^GLIBC_//' | sort -uV | tail -n1 || true)"
  if [ -n "$maxver" ]; then
    if ver_le "$maxver" "$MAX_GLIBC"; then
      echo "[ok]   glibc $maxver ≤ $MAX_GLIBC  $elf"
    else
      echo "[FAIL] glibc $maxver > $MAX_GLIBC  $elf"; fail=1
    fi
  else
    echo "[info] 无 GLIBC 符号引用(静态或非 glibc)  $elf"
  fi
  # 2) NEEDED 清单
  needed="$(readelf -d "$elf" 2>/dev/null | grep -oE 'NEEDED.*\[(.+)\]' | sed 's/.*\[\(.*\)\]/\1/' | tr '\n' ' ' || true)"
  [ -n "$needed" ] && echo "       NEEDED: $needed"
  # 3) 16K 段对齐(数值比较;0x10000=64K 是合规的,勿用前缀通配)
  if [ "$PAGE_ALIGN" = 1 ]; then
    min=""
    for a in $(readelf -lW "$elf" 2>/dev/null | awk '/LOAD/{print $NF}'); do
      d="$(printf '%d' "$a" 2>/dev/null)" || continue
      if [ -z "$min" ] || [ "$d" -lt "$min" ]; then min="$d"; fi
    done
    if [ -z "$min" ]; then
      echo "[info] 无 LOAD 段(非 ELF?)  $elf"
    elif [ "$min" -lt 16384 ]; then
      echo "[FAIL] PT_LOAD p_align=$min < 16K(16K 页设备不可加载)  $elf"; fail=1
    else
      echo "[ok]   PT_LOAD p_align=$min ≥ 16K  $elf"
    fi
  fi
done < <(collect_elfs)

echo "----"
echo "审计 ELF 总数: $n_elf,结果: $([ $fail -eq 0 ] && echo PASS || echo FAIL)"
exit $fail
