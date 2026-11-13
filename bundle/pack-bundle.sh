#!/usr/bin/env bash
# pack-bundle.sh — Assemble a self-contained distribution bundle (DESIGN §4.1, NAMING §6.1)
#
# Usage:
#   pack-bundle.sh --rootfs <baseline-rootfs> --stage <payload-stage> \
#                  --out <bundle.tar.gz> [--shebang /system/bin/sh] [--name <ver>]
#
# --rootfs: output of baseline/make-rootfs.sh or `docker export ubuntu:24.04`
# --stage: upstream payload tree in canonical relative layout (the root/ prefix may be omitted):
#             bin/opencode.bin            # Official opencode linux-arm64 ELF (required)
#             usr/bin/…  usr/libexec/git-core/…   # Git prefix (required)
#             sbin/dropbear  sbin/dbclient        # Optional
#             bin/rg  bin/busybox (static)…       # Optional
# Rules (NAMING):
#   - Rename each glibc ELF to <name>.bin and generate a wrapper at its original path (also
#     applies to dynamically linked git libexec helpers; git calls wrappers by original name via GIT_EXEC_PATH);
#   - Keep static ELFs (such as busybox) unchanged under their original names;
#   - Collect the glibc dependency closure (lddtree) in root/lib, preserving sonames (route B;
#     pack-apk-libs.sh handles Tier P route A rewriting);
#   - Generate a TSV manifest (NAMING §7.2) for naming-lint and notices.
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
[ -n "$ROOTFS" ] && [ -n "$STAGE" ] && [ -n "$OUT" ] || { grep '^# Usage' -A3 "$0"; exit 2; }

command -v readelf >/dev/null || { echo "需要 binutils(readelf)"; exit 1; }
BUNDLE_TPL="$(dirname "$0")/wrapper.sh.tpl"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
ORIG_PWD="$PWD"
case "$OUT" in /*) ABS_OUT="$OUT" ;; *) ABS_OUT="$ORIG_PWD/$OUT" ;; esac
B="$WORK/andcode"; mkdir -p "$B"

# ── 1. Payload + overlay + ELF→.bin/wrapper conversion ─────────────────────
cp -a "$STAGE/." "$B/"
if [ -d "$B/root" ]; then mv "$B/root/." "$B/"; rmdir "$B/root"; fi
# Repository-maintained sbin entry scripts (naming rules: NAMING §4.2)
if [ -d "$(dirname "$0")/overlay" ]; then
  cp -a "$(dirname "$0")/overlay/." "$B/"
fi

# Dereference symlinks within the tree (such as git-core's git-remote-https → git-remote-http):
# otherwise find -type f skips them, leaving helpers unwrapped and breaking HTTPS.
while IFS= read -r -d '' l; do
  tgt="$(readlink -f "$l")" || continue
  [ -f "$tgt" ] || continue
  cp -f --remove-destination "$tgt" "$l"
  echo "[解引用] ${l#$B/} → ${tgt#$B/}"
done < <(find "$B" -type l -print0)

is_static() { file -b "$1" | grep -q 'statically linked\|static-pie'; }

# Process depth-first: keep static ELFs; rename dynamic ELFs to .bin and generate wrappers at original paths.
# ROOT inference depth equals directory depth beneath root/ (bin/x → 1 level → "../"; repeat for deeper paths).
while IFS= read -r -d '' f; do
  if is_static "$f"; then
    echo "[直通] 静态 ELF: ${f#$B/}"
  else
    mv "$f" "$f.bin"
    cmd="$(basename "$f")"
    rel="${f#"$B/"}"                     # For example, bin/opencode or usr/libexec/git-core/git-remote-https
    depth="$(printf '%s' "$rel" | awk -F'/' '{print NF-1}')"
    up=""; i=0; while [ $i -lt $depth ]; do up="${up}../"; i=$((i+1)); done
    if [ -n "$LAUNCHER" ] && [ -f "$LAUNCHER" ] && case "$rel" in usr/libexec/git-core/*) true ;; *) false ;; esac; then
      # Launcher mode (NAMING §6.2): a static musl launcher replaces the shell wrapper,
      # avoiding the git spawn shell chain (device P0: capabilities not found).
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
  # opencode invokes 'git' with posix_spawn (no shell; Bun does not fall back to /bin/sh):
  # bin/git must be an ELF launcher (target = usr/libexec/git-core/git.bin).
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

# bin/git is the canonical ELF spawn entry when a launcher was supplied.
# Omit only our freshly rendered redundant usr/bin/git wrapper: both logical
# names otherwise map to libandcode-cmd-git.so and silently overwrite in Tier P.
if [ -n "$LAUNCHER" ] && [ -f "$LAUNCHER" ] && [ -f "$B/usr/bin/git.bin" ]; then
  rm -f "$B/usr/bin/git"
fi
if [ -f "$B/bin/opencode-pty" ] && [ -f "$B/usr/lib/opencode-pty/opencode-pty.bin" ]; then
  # Tier P static entry invokes the daemon through the explicit loader.
  rm -f "$B/usr/lib/opencode-pty/opencode-pty"
fi

# ── 2. glibc closure (root/lib, preserving sonames) ─────────────────────────
mkdir -p "$B/lib"
declare -A COPIED=()
# Dependency resolution order: --extralib (upstream container private libraries) → baseline rootfs;
# -L follows symlinks; library destinations use original sonames (route B).
resolve_in_rootfs() { # $1 = library filename → print absolute path
  local name="$1" d p
  for d in "${EXTRA_LIBS[@]:-}"; do
    [ -n "$d" ] || continue
    p="$(find -L "$d" -name "$name" -type f 2>/dev/null | head -n1)"
    [ -n "$p" ] && { printf '%s\n' "$p"; return 0; }
  done
  find -L "$ROOTFS/lib" "$ROOTFS/usr/lib" "$ROOTFS/usr/lib/aarch64-linux-gnu" \
       -name "$name" -type f 2>/dev/null | head -n1
}
copy_deps() { # $1 = ELF path (must resolve from the rootfs chroot perspective)
  local elf="$1" needed name path
  # Capture all DT_NEEDED entries (both ld-linux and lib prefixes, not just lib*).
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
          copy_deps "$path"   # Recursively collect transitive dependencies.
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

# ── 3. proot (bionic build, Tier A/M /etc redirection solution) + shim + etc templates ──
# Rationale (device P0 findings): LD_PRELOAD cannot intercept glibc-internal fopen("/etc/resolv.conf");
# the shim cannot redirect glibc-internal /etc reads; proot userspace binds provide the rootless solution.
# Components: Termux proot (bionic) + loader + libtalloc + libandroid-shmem, aggregated independently.
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
  printf '# Overridden at runtime by andcode-mkresolv\nnameserver 1.1.1.1\n' > "$B/etc/resolv.conf"

# CA certificates (required for git/HTTPS; shim redirects the entire /etc/ssl/ prefix, DESIGN §4.5)
# Dereference with -L: /etc/ssl/certs is often a symlink, with internal hash links pointing elsewhere in rootfs.
if [ -e "$ROOTFS/etc/ssl/certs" ] || [ -e "$ROOTFS/usr/lib/ssl/certs" ]; then
  SRC="$ROOTFS/etc/ssl/certs"; [ -e "$SRC" ] || SRC="$ROOTFS/usr/lib/ssl/certs"
  mkdir -p "$B/etc/ssl"
  cp -aL "$SRC" "$B/etc/ssl/certs" 2>/dev/null || cp -aL "$SRC/." "$B/etc/ssl/certs/"
  cp -fL "$ROOTFS/etc/ssl/openssl.cnf" "$B/etc/ssl/" 2>/dev/null || true
  echo "[etc] CA 证书已收录($(find "$B/etc/ssl/certs" -type f | wc -l) 项)"
fi

# ── 4. Manifest (NAMING §7.2; kind/physical-name rules: NAMING §6.2) ─────────
MF="$B/manifest"
printf '# logical-path\tphysical-tier-p\tkind\tlicense\tversion\tupstream\n' > "$MF"
# Read versions from the actual baseline package database, not the bundle version, for Bash/ncurses.
package_version() {
  awk -v package="$1" 'BEGIN { RS=""; FS="\n" }
    { matched=0; version=""; for (i=1; i<=NF; i++) {
      if ($i == "Package: " package) matched=1;
      if ($i ~ /^Version: /) version=substr($i,10);
    } if (matched) { print version; exit } }' "$ROOTFS/var/lib/dpkg/status"
}

slug() { # $1 = bundle logical path (relative to root/) → physical name (NAMING §6.2)
  local p="${1#root/}" base s
  case "$p" in
    *.bin) base="${p%.bin}" ;;                      # ELF payload: strip .bin
    *)    base="$p" ;;
  esac
  case "$base" in
    bin/*|usr/bin/*|sbin/*) p="${base#bin/}"; p="${p#usr/bin/}"; p="${p#sbin/}" ;;
    *)                      p="$base" ;;
  esac
  s="$(printf '%s' "$p" | tr '/' '-')"
  s="$(printf '%s' "$s" | tr -c 'a-z0-9A-Z-' '-')"   # Sanitize characters (NAMING §6.2)
  printf 'libandcode-%s.so' "$s"
}
lib_slug() { # $1 = root/lib/<soname> → physical name (loader exception; strip .so.N version suffix)
  local b="$(basename "$1")"
  case "$b" in
    ld-linux*) printf 'libandcode-ld-linux.so' ;;
    *)         b="${b%.so.*}"; b="${b%.so}"
               b="$(printf '%s' "$b" | tr -c 'a-z0-9-' '-')"
               printf 'libandcode-%s.so' "$b" ;;
  esac
}

wrapper_slug() { # $1 = logical path → wrapper/launcher physical name (strip bin|usr/bin|libexec|sbin prefix, NAMING §6.2)
  local p="${1#root/}"
  case "$p" in usr/libexec/git-core/*)
    printf 'libandcode-git-core-%s.so' "${p#usr/libexec/git-core/}"
    return ;;
  esac
  case "$p" in
    bin/*|usr/bin/*|usr/libexec/git-core/*|sbin/*) p="${p#bin/}"; p="${p#usr/bin/}"; p="${p#usr/libexec/git-core/}"; p="${p#sbin/}" ;;
  esac
  p="$(printf '%s' "$p" | tr '/' '-' | tr -c 'a-z0-9A-Z-' '-')"
  case "${1#root/}" in
    bin/*|usr/bin/*) printf 'libandcode-cmd-%s.so' "$p" ;;
    *) printf 'libandcode-%s.so' "$p" ;;
  esac
}

declare -A KINDMAP=()
declare -A PHYSICAL_PATHS=()
if [ -f "$B/.kindmap" ]; then
  while IFS=$'\t' read -r rel k; do KINDMAP["$rel"]="$k"; done < "$B/.kindmap"
fi
while IFS= read -r -d '' f; do
  lp="${f#$B/}"
  case "$lp" in
    root/home/*|root/tmp/*|manifest|.kindmap) continue ;;
  esac
  lic=AGPL-3.0-only; up=andcode; ver="$VER"
  if [ "${lp#lib/}" != "$lp" ]; then
    kind=glibc-lib; phys="$(lib_slug "$lp")"; lic=LGPL-2.1; up=glibc-2.39
  elif [ "${lp#root/etc/}" != "$lp" ] || [ "${lp#etc/}" != "$lp" ]; then
    # Data bypasses jniLibs (read-only data is copied unchanged from APK assets to filesDir); physical-name placeholder is "-".
    kind=data; phys="-"
  elif [ "$lp" = "shim/libandcode-shim.so" ]; then
    kind=preload-lib; phys="libandcode-shim.so"
  elif [ -n "${KINDMAP[$lp]:-}" ]; then
    phys="$(wrapper_slug "$lp")"
    case "${KINDMAP[$lp]}" in
      launcher) kind=launcher; lic=AGPL-3.0-only; up=andcode ;;
      *)        kind=wrapper-sh ;;
    esac
  elif file -b "$f" | grep -q 'ELF 64-bit.*ARM aarch64'; then
    kind=elf-exec; phys="$(slug "$lp")"
    case "$lp" in
      bin/opencode-pty) lic=AGPL-3.0-only; up=andcode ;;
      bin/oc2.bin) lic=MIT; up=anomalyco/opencode; ver=2.2.6 ;;
      usr/lib/opencode-pty/opencode-pty.bin) lic=MIT; up=anomalyco/opencode-process-daemon; ver=0.4.0 ;;
      bin/busybox*)        lic=GPL-2.0;            up=busybox.net/alpine ;;
      sbin/dropbear*|bin/dbclient*) lic=MIT;        up=mkj/dropbear ;;
      usr/bin/git*|usr/libexec/git-core/*) lic=GPL-2.0-or-later; up=git/git ;;
      usr/lib/proot/proot|usr/lib/proot/loader) lic=GPL-2.0; up=proot-me/proot\(termux-build\) ;;
      usr/lib/proot/libtalloc*) lic=LGPL-3.0-or-later; up=samba.org/talloc ;;
      usr/lib/proot/libandroid-shmem*) lic=BSD-2-Clause; up=termux/libandroid-shmem ;;
      *)                   lic=MIT;                up=sst/opencode ;;
    esac
  elif [ -f "$f.bin" ]; then
    # A matching .bin indicates an upstream command wrapper (shell mode, fallback for entries absent from kindmap).
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
  if [ "$phys" != "-" ]; then
    [ -z "${PHYSICAL_PATHS[$phys]:-}" ] || {
      echo "[FAIL] Tier P physical collision: $phys ($lp / ${PHYSICAL_PATHS[$phys]})" >&2
      exit 1
    }
    PHYSICAL_PATHS["$phys"]="$lp"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$lp" "$phys" "$kind" "$lic" "$ver" "$up" >> "$MF"
done < <(find "$B" -type f -print0 | sort -z)

# ── 5. Packaging ──────────────────────────────────────────────────────────
rm -f "$B/.kindmap"
mkdir -p "$(dirname "$ABS_OUT")"
( cd "$WORK" && tar -czf "$ABS_OUT" andcode )
sha256sum "$ABS_OUT" | tee "$ABS_OUT.sha256"
echo "bundle 就绪: $ABS_OUT(条目 $(wc -l < "$MF") )"
