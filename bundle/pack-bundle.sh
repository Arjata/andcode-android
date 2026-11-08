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
EXTRA_LIBS=()
LAUNCHER=""
PROOT_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --rootfs) ROOTFS="$2"; shift 2 ;;
    --stage)  STAGE="$2";  shift 2 ;;
    --out)    OUT="$2";    shift 2 ;;
    --shebang) SHEBANG="$2"; shift 2 ;;
    --name)   VER="$2";    shift 2 ;;
    --extralib) EXTRA_LIBS+=("$2"); shift 2 ;;
    --launcher) LAUNCHER="$2"; shift 2 ;;
    --proot)    PROOT_DIR="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done
[ -n "$ROOTFS" ] && [ -n "$STAGE" ] && [ -n "$OUT" ] || { grep '^# 用法' -A3 "$0"; exit 2; }

command -v readelf >/dev/null || { echo "需要 binutils(readelf)"; exit 1; }
BUNDLE_TPL="$(dirname "$0")/wrapper.sh.tpl"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
ORIG_PWD="$PWD"
case "$OUT" in /*) ABS_OUT="$OUT" ;; *) ABS_OUT="$ORIG_PWD/$OUT" ;; esac
B="$WORK/andcode"; mkdir -p "$B"

# ── 1. 载荷 + overlay + ELF→.bin/包装器变换 ──────────────────────────────
cp -a "$STAGE/." "$B/"
if [ -d "$B/root" ]; then mv "$B/root/." "$B/"; rmdir "$B/root"; fi
# 本仓库维护的 sbin 入口脚本(命名规范 NAMING §4.2)
if [ -d "$(dirname "$0")/overlay" ]; then
  cp -a "$(dirname "$0")/overlay/." "$B/"
fi

# 解引用树内符号链接(git-core 的 git-remote-https → git-remote-http 等):
# 否则 find -type f 会跳过它们,导致助手从未被包装 → https 链路断裂
while IFS= read -r -d '' l; do
  tgt="$(readlink -f "$l")" || continue
  [ -f "$tgt" ] || continue
  cp -f --remove-destination "$tgt" "$l"
  echo "[解引用] ${l#$B/} → ${tgt#$B/}"
done < <(find "$B" -type l -print0)

is_static() { file -b "$1" | grep -q 'statically linked\|static-pie'; }

# 深度优先处理:静态直通;动态 ELF 改名 .bin 并在原路径生成包装器
# ROOT 自推导深度 = 路径在 root/ 下的目录层数(bin/x → 1 层 → "../";深路径按层数累加)
while IFS= read -r -d '' f; do
  if is_static "$f"; then
    echo "[直通] 静态 ELF: ${f#$B/}"
  else
    mv "$f" "$f.bin"
    cmd="$(basename "$f")"
    rel="${f#"$B/"}"                     # 如 bin/opencode、usr/libexec/git-core/git-remote-https
    depth="$(printf '%s' "$rel" | awk -F'/' '{print NF-1}')"
    up=""; i=0; while [ $i -lt $depth ]; do up="${up}../"; i=$((i+1)); done
    if [ -n "$LAUNCHER" ] && [ -f "$LAUNCHER" ] && case "$rel" in usr/libexec/git-core/*) true ;; *) false ;; esac; then
      # launcher 形态(NAMING §6.2):静态 musl 启动器取代 shell wrapper,
      # 规避 git spawn 的 shell 链路(真机 P0: capabilities not found)
      cp -f "$LAUNCHER" "$f"
      echo "[包装] $rel → $rel.bin(launcher)"
      printf '%s\tlauncher\n' "$rel" >> "$B/.kindmap"
    else
      sed -e "s|@ROOT@|ROOT=\"\$(CDPATH= cd -- \"\$(dirname -- \"\$0\")/${up}\" \&\& pwd)\"|" \
          -e "s|@EXEDIR@|\$ROOT|" \
          -e "s|@LOADER@|\$ROOT/lib/ld-linux-aarch64.so.1|" \
          -e "s|@LIBPATH@|\$ROOT/lib|" \
          -e "s|@TARGET@|$rel.bin|" \
          -e "s|@TIER@|a|" \
          "$BUNDLE_TPL" | { printf '#!%s\n' "$SHEBANG"; tail -n +2; } > "$f"
      echo "[包装] $rel → $rel.bin(shell,深度 $depth)"
      printf '%s\tshell\n' "$rel" >> "$B/.kindmap"
    fi
    if [ -n "$LAUNCHER" ] && [ -f "$LAUNCHER" ]; then
  # opencode 以 posix_spawn 调 'git'(无 shell,Bun 不回落 /bin/sh):
  # bin/git 必须是 ELF launcher(target = usr/libexec/git-core/git.bin)
  cp -f "$LAUNCHER" "$B/bin/git"
  chmod 0755 "$B/bin/git"
  printf '%s\tlauncher\n' "bin/git" >> "$B/.kindmap"
  echo "[launcher] bin/git(opencode spawn 入口)"
fi
chmod 0755 "$f"
  fi
done < <(find "$B" -type f ! -name '*.bin' -print0 | while IFS= read -r -d '' f; do
  file -b "$f" | grep -q 'ELF 64-bit.*ARM aarch64' && printf '%s\0' "$f"
done)

# ── 2. glibc 闭包(root/lib,保持 soname)─────────────────────────────────
mkdir -p "$B/lib"
declare -A COPIED=()
# 依赖解析顺序: --extralib(上游容器私有库)→ 基线 rootfs;
# -L 跟随符号链接;lib 落点用 soname 原名(路线乙)
resolve_in_rootfs() { # $1 = 库文件名 → 输出绝对路径
  local name="$1" d p
  for d in "${EXTRA_LIBS[@]:-}"; do
    [ -n "$d" ] || continue
    p="$(find -L "$d" -name "$name" -type f 2>/dev/null | head -n1)"
    [ -n "$p" ] && { printf '%s\n' "$p"; return 0; }
  done
  find -L "$ROOTFS/lib" "$ROOTFS/usr/lib" "$ROOTFS/usr/lib/aarch64-linux-gnu" \
       -name "$name" -type f 2>/dev/null | head -n1
}
copy_deps() { # $1 = ELF 路径(必须在 rootfs 的 chroot 视角下解析)
  local elf="$1" needed name path
  # 捕获全部 DT_NEEDED(ld-linux 开头与 lib 开头都要,不能只匹配 lib*)
  needed="$(readelf -d "$elf" 2>/dev/null | grep -oE '\[(lib|ld-linux)[^]]+\]' | tr -d '[]' || true)"
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

# ── 3. proot(bionic 构建,Tier A/M 的 /etc 重定向正解)+ shim + etc 模板 ──
# 依据(真机 P0 结论):LD_PRELOAD 无法拦截 glibc 内部 fopen("/etc/resolv.conf"),
# shim 对 glibc-internal /etc 读取无效;proot 用户态 bind 是无 root 正解。
# 组件:Termux proot(bionic)+ loader + libtalloc + libandroid-shmem,独立聚合。
if [ -n "$PROOT_DIR" ] && [ -d "$PROOT_DIR" ]; then
  mkdir -p "$B/usr/lib/proot"
  cp -f "$PROOT_DIR/proot"  "$B/usr/lib/proot/proot"
  if [ -f "$PROOT_DIR/loader" ]; then
    cp -f "$PROOT_DIR/loader" "$B/usr/lib/proot/loader"
  elif [ -f "$PROOT_DIR/libexec/proot/loader" ]; then
    cp -f "$PROOT_DIR/libexec/proot/loader" "$B/usr/lib/proot/loader"
  fi
  for l in "$PROOT_DIR"/lib/*.so*; do [ -e "$l" ] && cp -f "$l" "$B/usr/lib/proot/"; done
  chmod 0755 "$B/usr/lib/proot/proot" "$B/usr/lib/proot/loader"
fi
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

# CA 证书(git/https 必需;shim 对 /etc/ssl/ 前缀整段重定向,DESIGN §4.5)
# -L 解引用:/etc/ssl/certs 常为符号链接,内部哈希链接指向 rootfs 他处
if [ -e "$ROOTFS/etc/ssl/certs" ] || [ -e "$ROOTFS/usr/lib/ssl/certs" ]; then
  SRC="$ROOTFS/etc/ssl/certs"; [ -e "$SRC" ] || SRC="$ROOTFS/usr/lib/ssl/certs"
  mkdir -p "$B/etc/ssl"
  cp -aL "$SRC" "$B/etc/ssl/certs" 2>/dev/null || cp -aL "$SRC/." "$B/etc/ssl/certs/"
  cp -fL "$ROOTFS/etc/ssl/openssl.cnf" "$B/etc/ssl/" 2>/dev/null || true
  echo "[etc] CA 证书已收录($(find "$B/etc/ssl/certs" -type f | wc -l) 项)"
fi

# ── 4. manifest(NAMING §7.2;kind/物理名判定见 NAMING §6.2)───────────────
MF="$B/manifest"
printf '# logical-path\tphysical-tier-p\tkind\tlicense\tversion\tupstream\n' > "$MF"
# 从真实基线包数据库取版本,不把交付包版本误记为 Bash/ncurses 版本。
package_version() {
  awk -v package="$1" 'BEGIN { RS=""; FS="\n" }
    { matched=0; version=""; for (i=1; i<=NF; i++) {
      if ($i == "Package: " package) matched=1;
      if ($i ~ /^Version: /) version=substr($i,10);
    } if (matched) { print version; exit } }' "$ROOTFS/var/lib/dpkg/status"
}

slug() { # $1 = bundle 内逻辑路径(root/ 相对) → 物理名(NAMING §6.2)
  local p="${1#root/}" base s
  case "$p" in
    *.bin) base="${p%.bin}" ;;                      # ELF 本体:剥 .bin
    *)    base="$p" ;;
  esac
  case "$base" in
    bin/*|usr/bin/*|sbin/*) p="${base#bin/}"; p="${p#usr/bin/}"; p="${p#sbin/}" ;;
    *)                      p="$base" ;;
  esac
  s="$(printf '%s' "$p" | tr '/' '-')"
  s="$(printf '%s' "$s" | tr -c 'a-z0-9A-Z-' '-')"   # 字符净化(NAMING §6.2)
  printf 'libandcode-%s.so' "$s"
}
lib_slug() { # $1 = root/lib/<soname> → 物理名(loader 特例;剥 .so.N 版本尾)
  local b="$(basename "$1")"
  case "$b" in
    ld-linux*) printf 'libandcode-ld-linux.so' ;;
    *)         b="${b%.so.*}"; b="${b%.so}"; printf 'libandcode-%s.so' "$b" ;;
  esac
}

wrapper_slug() { # $1 = 逻辑路径 → wrapper/launcher 物理名(bin|usr/bin|libexec|sbin 剥前缀,NAMING §6.2)
  local p="${1#root/}"
  case "$p" in
    bin/*|usr/bin/*|usr/libexec/git-core/*|sbin/*) p="${p#bin/}"; p="${p#usr/bin/}"; p="${p#usr/libexec/git-core/}"; p="${p#sbin/}" ;;
  esac
  p="$(printf '%s' "$p" | tr '/' '-' | tr -c 'a-z0-9A-Z-' '-')"
  if [ "${1#root/bin/}" != "$1" ] || [ "${1#root/usr/bin/}" != "$1" ]; then
    printf 'libandcode-cmd-%s.so' "$p"
  else
    printf 'libandcode-%s.so' "$p"
  fi
}

declare -A KINDMAP=()
if [ -f "$B/.kindmap" ]; then
  while IFS=$'\t' read -r rel k; do KINDMAP["usr/libexec/git-core/$rel"]="$k"; done < "$B/.kindmap"
fi
while IFS= read -r -d '' f; do
  lp="${f#$B/}"
  case "$lp" in
    root/home/*|root/tmp/*|manifest|.kindmap) continue ;;
  esac
  lic=AGPL-3.0-only; up=andcode; ver="$VER"
  if [ "${lp#root/lib/}" != "$lp" ]; then
    kind=glibc-lib; phys="$(lib_slug "$lp")"; lic=LGPL-2.1; up=glibc-2.39
  elif [ "${lp#root/etc/}" != "$lp" ] || [ "${lp#etc/}" != "$lp" ]; then
    # data 类不进 jniLibs(只读数据经 APK assets → filesDir 原样落位),物理名占位 "-"
    kind=data; phys="-"
  elif [ "$lp" = "shim/libandcode-shim.so" ]; then
    kind=preload-lib; phys="libandcode-shim.so"
  elif file -b "$f" | grep -q 'ELF 64-bit.*ARM aarch64'; then
    kind=elf-exec; phys="$(slug "$lp")"
    case "$(basename "$lp")" in
      busybox*)            lic=GPL-2.0;            up=busybox.net/alpine ;;
      dropbear*|dbclient*) lic=MIT;                up=mkj/dropbear ;;
      *libexec/git-core/*) lic=GPL-2.0-or-later;  up=git/git ;;
      *lib/proot/proot|*lib/proot/loader) lic=GPL-2.0; up=proot-me/proot\(termux-build\) ;;
      *lib/proot/libtalloc*) lic=LGPL-3.0-or-later; up=samba.org/talloc ;;
      *lib/proot/libandroid-shmem*) lic=BSD-2-Clause; up=termux/libandroid-shmem ;;
      *)                   lic=MIT;                up=sst/opencode ;;
    esac
  elif [ -n "${KINDMAP[${lp#root/}]:-}" ]; then
    # wrapper / launcher(NAMING §6.2:bin/usr/bin 下 cmd- 前缀;libexec 直名)
    phys="$(wrapper_slug "$lp")"
    case "${KINDMAP[${lp#root/}]}" in
      launcher) kind=launcher; lic=AGPL-3.0-only; up=andcode ;;
      *)        kind=wrapper-sh ;;
    esac
  elif [ -f "$f.bin" ]; then
    # 有同名 .bin ⇒ 上游命令包装器(shell 形态,未登记 kindmap 的兜底)
    phys="$(wrapper_slug "$lp")"
    kind=wrapper-sh
  else
    kind=script; phys="$(slug "$lp")"
  fi
  case "$lp" in
    bin/bash.bin|bin/bash|etc/third-party/bash-copyright|etc/third-party/gpl-3)
      lic=GPL-3.0-or-later; ver="$(package_version bash)"
      up=https://ports.ubuntu.com/pool/main/b/bash/
      [ -n "$ver" ] || { echo '缺少 Bash 基线包版本' >&2; exit 1; } ;;
    lib/libtinfo.so.*|etc/third-party/ncurses-copyright)
      lic='MIT AND BSD-3-Clause'; ver="$(package_version libtinfo6)"
      up=https://ports.ubuntu.com/pool/main/n/ncurses/
      [ -n "$ver" ] || { echo '缺少 libtinfo6 基线包版本' >&2; exit 1; } ;;
  esac
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$lp" "$phys" "$kind" "$lic" "$ver" "$up" >> "$MF"
done < <(find "$B" -type f -print0 | sort -z)

# ── 5. 打包 ──────────────────────────────────────────────────────────────
rm -f "$B/.kindmap"
mkdir -p "$(dirname "$ABS_OUT")"
( cd "$WORK" && tar -czf "$ABS_OUT" andcode )
sha256sum "$ABS_OUT" | tee "$ABS_OUT.sha256"
echo "bundle 就绪: $ABS_OUT(条目 $(wc -l < "$MF") )"
