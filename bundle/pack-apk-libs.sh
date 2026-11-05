#!/usr/bin/env bash
# pack-apk-libs.sh — 规范布局 bundle → Tier P jniLibs 物理化(NAMING §6.2/§6.3,路线甲)
#
# 用法: pack-apk-libs.sh --bundle <andcode-bundle.tar.gz> --out <jniLibs-dir> [--no-rewrite]
#
# 步骤:
#   1. 解包,按 manifest 逐行把 root/... 映射为 libandcode-*.so 物理名;
#   2. 路线甲(默认):patchelf 全量重写 glibc 闭包的 SONAME/NEEDED
#      (libc.so.6 → libandcode-libc.so …),依赖与物理名一一对应;
#   3. loader 特例:ld-linux-aarch64.so.1 → libandcode-ld-linux.so(显式调用,可改名);
#   4. 校验每个产物:名称符合 ^libandcode-[a-z0-9-]+\.so$,长度 ≤ 64;
#   5. 输出 link-farm 清单(manifest.farm)供 APK 首启动建农场(NAMING §6.4)。
set -euo pipefail

BUNDLE="" OUT="" REWRITE=1
while [ $# -gt 0 ]; do
  case "$1" in
    --bundle) BUNDLE="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --no-rewrite) REWRITE=0; shift ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done
[ -n "$BUNDLE" ] && [ -n "$OUT" ] || { grep '^# 用法' -A3 "$0"; exit 1; }
command -v patchelf >/dev/null || { echo "需要 patchelf"; exit 1; }

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
tar -xzf "$BUNDLE" -C "$WORK"
B="$WORK/andcode"
LIBS="$OUT/arm64-v8a"
mkdir -p "$LIBS"

# ── 1+2+3. 映射与重写 ─────────────────────────────────────────────────────
TPL="$(dirname "$0")/wrapper.sh.tpl"
declare -A SONAME_MAP=() ELF_PHYS=()   # ELF_PHYS: 逻辑路径(.bin) → jniLibs 物理名
while IFS=$'\t' read -r lp phys kind lic ver up; do
  case "$lp" in '#'*|"") continue ;; esac
  ELF_PHYS["$lp"]="$phys"
done < "$B/manifest"
while IFS=$'\t' read -r lp phys kind lic ver up; do
  case "$lp" in '#'*|"") continue ;; esac
  case "$kind" in
    data) continue ;;   # data 不进 jniLibs(NAMING §6.2;APK assets 原样落位 filesDir)
    glibc-lib|preload-lib|elf-exec|wrapper-sh|script|alias) ;;
    *) echo "[FAIL] manifest 未知 kind: $kind($lp)"; exit 1 ;;
  esac
  # 物理名门禁(NAMING §8)
  if ! printf '%s' "$phys" | grep -qE '^libandcode-[a-z0-9-]+\.so$' || [ ${#phys} -gt 64 ]; then
    echo "[FAIL] 物理名不合规: '$phys' ← $lp"; exit 1
  fi
  src="$B/$lp"
  [ -f "$src" ] || { echo "[FAIL] manifest 指向缺失文件: $lp"; exit 1; }

  case "$kind" in
    glibc-lib)
      base="$(basename "$lp")"
      case "$base" in
        ld-linux*) : ;;  # loader 无需 SONAME 重写(显式路径调用)
        *)
          newsoname="$phys"
          if [ "$REWRITE" = 1 ]; then
            patchelf --set-soname "$newsoname" "$src"
            SONAME_MAP["$base"]="$newsoname"
          fi
          ;;
      esac
      cp -f "$src" "$LIBS/$phys"
      ;;
    wrapper-sh)
      # Tier P 重渲染(NAMING §6.3):ROOT/EXEDIR 来自 APK 注入的环境变量,
      # loader/target 用 jniLibs 物理名
      target="${ELF_PHYS["$lp.bin"]:-}"
      [ -n "$target" ] || { echo "[FAIL] wrapper 缺少配对 .bin manifest 行: $lp"; exit 1; }
      sed -e "s|@ROOT@|ROOT=\"\${ANDCODE_ROOT:?}\"|" \
          -e "s|@EXEDIR@|\$ANDCODE_EXE_DIR|" \
          -e "s|@LOADER@|\$ANDCODE_EXE_DIR/libandcode-ld-linux.so|" \
          -e "s|@LIBPATH@|\$ANDCODE_EXE_DIR|" \
          -e "s|@TARGET@|$target|" \
          -e "s|@TIER@|p|" \
          "$TPL" > "$LIBS/$phys"
      chmod 0755 "$LIBS/$phys"
      ;;
    *)
      cp -f "$src" "$LIBS/$phys"
      ;;
  esac
done < <(sort -t$'\t' -k3 "$B/manifest")

# 二遍:用完成的映射重写全部 exec/lib 的 NEEDED
if [ "$REWRITE" = 1 ]; then
  while IFS=$'\t' read -r lp phys kind lic ver up; do
    case "$lp" in '#'*|"") continue ;; esac
    case "$kind" in glibc-lib|elf-exec|preload-lib) ;; *) continue ;; esac
    dst="$LIBS/$phys"
    for old in "${!SONAME_MAP[@]}"; do
      if readelf -d "$dst" 2>/dev/null | grep -q "\[$old\]"; then
        patchelf --replace-needed "$old" "${SONAME_MAP[$old]}" "$dst"
      fi
    done
  done < <(sort -t$'\t' -k3 "$B/manifest")
fi

# ── 4. 结果校验(check-compat 兼容审计同样适用,由 CI 串联)──────────────
bad=0
for f in "$LIBS"/*.so; do
  n="$(basename "$f")"
  if ! printf '%s' "$n" | grep -qE '^libandcode-[a-z0-9-]+\.so$'; then
    echo "[FAIL] 产物名不合规: $n"; bad=1
  fi
done
[ $bad -eq 0 ] || exit 1

# ── 5. link-farm 清单(逻辑路径 → 物理名;data 类排除,物理为 "-")────────
awk -F'\t' '$1 !~ /^#/ && $1 != "" && $2 != "-" {print $1 "\t" $2}' "$B/manifest" > "$OUT/manifest.farm"
echo "jniLibs 就绪: $LIBS($(ls "$LIBS" | wc -l) 项);farm 清单: $OUT/manifest.farm"
