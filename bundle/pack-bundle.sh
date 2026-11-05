#!/usr/bin/env bash
# pack-bundle.sh — 组装自包含交付包(DESIGN §4.1, NAMING §6.1)
#
# 用法:
#   pack-bundle.sh --rootfs <baseline-rootfs> --stage <payload-stage> \
#                  --out <bundle.tar.gz> [--shebang /system/bin/sh] [--name <ver>]
#
# --rootfs: baseline/make-rootfs.sh 或 `docker export ubuntu:24.04` 的产物
# --stage:  上游载荷树,相对布局即规范布局(root/ 之外可省略 root/ 前缀):
#             bin/opencode.bin            # opencode 官方 linux-arm64 ELF(必须)
#             usr/bin/…  usr/libexec/git-core/…   # git 前缀(必须)
#             sbin/dropbear  sbin/dbclient        # 可选
#             bin/rg  bin/busybox(静态)…         # 可选
# 规则(NAMING):
#   - 每个 glibc ELF 改名 <name>.bin,并在原路径生成包装器脚本(动态链接的
#     git libexec 助手同样处理,git 经 GIT_EXEC_PATH 按原名调用包装器);
#   - 静态 ELF(如 busybox)保持原名直通;
#   - glibc 依赖闭包(lddtree)收进 root/lib,保持 soname 原名(路线乙;
#     Tier P 的路线甲重写由 pack-apk-libs.sh 处理);
#   - 生成 TSV manifest(NAMING §7.2),供 naming-lint 与 notices 使用。
set -euo pipefail

ROOTFS="" STAGE="" OUT="" SHEBANG="/system/bin/sh" VER="0.0.0+dev"
while [ $# -gt 0 ]; do
  case "$1" in
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --stage)  STAGE="$2";  shift 2 ;;
    --out)    OUT="$2";    shift 2 ;;
    --shebang) SHEBANG="$2"; shift 2 ;;
    --name)   VER="$2";    shift 2 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done
[ -n "$ROOTFS" ] && [ -n "$STAGE" ] && [ -n "$OUT" ] || { grep '^# 用法' -A3 "$0"; exit 2; }

command -v readelf >/dev/null || { echo "需要 binutils(readelf)"; exit 1; }
BUNDLE_TPL="$(dirname "$0")/wrapper.sh.tpl"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
B="$WORK/andcode"; mkdir -p "$B"

# ── 1. 载荷 + overlay + ELF→.bin/包装器变换 ──────────────────────────────
cp -a "$STAGE/." "$B/"
if [ -d "$B/root" ]; then mv "$B/root/." "$B/"; rmdir "$B/root"; fi
# 本仓库维护的 sbin 入口脚本(命名规范 NAMING §4.2)
if [ -d "$(dirname "$0")/overlay" ]; then
  cp -a "$(dirname "$0")/overlay/." "$B/"
fi

is_static() { file -b "$1" | grep -q 'statically linked\|static-pie'; }

# 深度优先处理:静态直通;动态 ELF 改名 .bin 并在原路径生成包装器
while IFS= read -r -d '' f; do
  if is_static "$f"; then
    echo "[直通] 静态 ELF: ${f#$B/}"
  else
    mv "$f" "$f.bin"
    cmd="$(basename "$f")"
    sed -e "s|@ROOT@|ROOT=\"\$(CDPATH= cd -- \"\$(dirname -- \"\$0\")/../..\" \&\& pwd)\"|" \
        -e "s|@EXEDIR@|\$ROOT|" \
        -e "s|@TARGET@|$cmd.bin|" \
        -e "s|@TIER@|a|" \
        "$BUNDLE_TPL" > "$f"
    chmod 0755 "$f"
    echo "[包装] $cmd → $cmd.bin(位于 ${f#$B/} 目录)"
  fi
done < <(find "$B" -type f ! -name '*.bin' -print0 | while IFS= read -r -d '' f; do
  file -b "$f" | grep -q 'ELF 64-bit.*ARM aarch64' && printf '%s\0' "$f"
done)

# ── 2. glibc 闭包(root/lib,保持 soname)─────────────────────────────────
mkdir -p "$B/lib"
declare -A COPIED=()
# 在 rootfs 内按 NEEDED 名解析(不经宿主缓存,保证使用基线版本)
resolve_in_rootfs() { # $1 = 库文件名 → 输出 rootfs 内绝对路径
  local name="$1"
  find "$ROOTFS/lib" "$ROOTFS/usr/lib" "$ROOTFS/lib64" -name "$name" -type f 2>/dev/null | head -n1
}
copy_deps() { # $1 = ELF 路径(必须在 rootfs 的 chroot 视角下解析)
  local elf="$1" needed name path
  needed="$(readelf -d "$elf" 2>/dev/null | grep -oE '\[lib[^]]+\]' | tr -d '[]' || true)"
  for name in $needed; do
    [ -n "${COPIED[$name]:-}" ] && continue
    case "$name" in
      ld-linux-aarch64.so.1)
        path="$(resolve_in_rootfs "$name")"
        [ -n "$path" ] && cp -f "$path" "$B/lib/$name" && COPIED[$name]=1
        ;;
      lib*)
        path="$(resolve_in_rootfs "$name")"
        if [ -n "$path" ]; then
          cp -f "$path" "$B/lib/$name"; COPIED[$name]=1
          copy_deps "$path"   # 递归二阶依赖
        else
          echo "[警告] 闭包缺库: $name(被 ${elf#$B/} 需要)" >&2
        fi
        ;;
    esac
  done
}
while IFS= read -r -d '' f; do
  case "$f" in *.bin) copy_deps "$f" ;; esac
done < <(find "$B" -type f -name '*.bin' -print0)

# ── 3. shim + etc 模板 ───────────────────────────────────────────────────
make -C "$(dirname "$0")/shim" CC="${CC:-gcc}" >/dev/null
mkdir -p "$B/shim" "$B/etc" "$B/home" "$B/tmp"
cp "$(dirname "$0")/shim/../libandcode-shim.so" "$B/shim/"
cat > "$B/etc/passwd" <<'EOF'
root:x:0:0:root:/root:/system/bin/sh
andcode:x:10001:10001:andcode:/home:/system/bin/sh
EOF
cat > "$B/etc/group" <<'EOF'
root:x:0:
andcode:x:10001:
EOF
printf 'hosts: files dns\n' > "$B/etc/nsswitch.conf"
printf '# 运行期由 andcode-mkresolv 覆盖\nnameserver 1.1.1.1\n' > "$B/etc/resolv.conf"

# ── 4. manifest(NAMING §7.2)────────────────────────────────────────────
slug() { # $1 = bundle 内逻辑路径(root/ 相对)
  local p="${1#root/}" s
  case "$p" in
    bin/*|usr/bin/*|usr/libexec/git-core/*|sbin/*) p="${p#bin/}"; p="${p#usr/bin/}"; p="${p#usr/libexec/git-core/}"; p="${p#sbin/}" ;;
  esac
  s="$(printf '%s' "$p" | tr '/' '-')"
  printf 'libandcode-%s.so' "$s"
}
MF="$B/manifest"
printf '# logical-path\tphysical-tier-p\tkind\tlicense\tversion\tupstream\n' > "$MF"
while IFS= read -r -d '' f; do
  lp="${f#$B/}"
  case "$lp" in
    root/etc/*|root/home/*|root/tmp/*|manifest) continue ;;
  esac
  phys="$(slug "$lp")"
  case "$lp" in
    *.bin) kind=elf-exec; lic=MIT; up=sst/opencode ;;
    */libexec/git-core/*) kind=elf-exec; lic=GPL-2.0-or-later; up=git/git ;;
    root/lib/*) kind=glibc-lib; lic=LGPL-2.1; up=glibc-2.39 ;;
    */libandcode-shim.so) kind=preload-lib; lic=AGPL-3.0-only; up=andcode ;;
    root/sbin/*|root/bin/*) kind=wrapper-sh; lic=AGPL-3.0-only; up=andcode ;;
    *) kind=script; lic=AGPL-3.0-only; up=andcode ;;
  esac
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$lp" "$phys" "$kind" "$lic" "$VER" "$up" >> "$MF"
done < <(find "$B" -type f -print0 | sort -z)

# ── 5. 打包 ──────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$OUT")"
( cd "$WORK" && tar -czf "$OUT" andcode )
sha256sum "$OUT" | tee "$OUT.sha256"
echo "bundle 就绪: $OUT(条目 $(wc -l < "$MF") )"
