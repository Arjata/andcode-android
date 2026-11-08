#!/usr/bin/env bash
# Build the fixed Ubuntu ncurses security baseline without trapped fs-ID calls.
# CI/Linux only. Usage: build-android-tinfo.sh <fresh-work-dir> <android-bundle>
set -euo pipefail
WORK="$(realpath -m "$1")"
BUNDLE="$(realpath "$2")"
[ ! -e "$WORK" ] || { echo 'Refusing existing ncurses build directory' >&2; exit 1; }
mkdir -p "$WORK/src" "$WORK/build"
BASE=https://ports.ubuntu.com/pool/main/n/ncurses
curl -fLSs "$BASE/ncurses_6.4+20240113.orig.tar.gz" -o "$WORK/source.tar.gz"
curl -fLSs "$BASE/ncurses_6.4+20240113-1ubuntu2.2.debian.tar.xz" -o "$WORK/debian.tar.xz"
echo "37a12a0f8ae2605012c9a164dd286b0cfa02b51b5055836d09eb3d597fc351b1  $WORK/source.tar.gz" | sha256sum -c -
echo "c7bbb8483d7ec358fb925a370575d8ebef63d6e455edce140de2ca7b86cf98d1  $WORK/debian.tar.xz" | sha256sum -c -
tar -xzf "$WORK/source.tar.gz" -C "$WORK/src" --strip-components=1
tar -xJf "$WORK/debian.tar.xz" -C "$WORK/src"
while read -r patch rest; do
  case "$patch" in ''|'#'*) continue ;; esac
  [ -z "$rest" ] || { echo 'Unexpected patch options' >&2; exit 1; }
  patch -d "$WORK/src" -p1 < "$WORK/src/debian/patches/$patch"
done < "$WORK/src/debian/patches/series"
cd "$WORK/build"
# Use ncurses' own !HAVE_SETFSUID path, NOT USE_ROOT_ACCESS. Match Ubuntu's
# wide tinfo ABI and versioned symbols. All files still face kernel permissions.
ac_cv_func_setfsuid=no CFLAGS='-O2 -fPIC' LDFLAGS='-Wl,-z,max-page-size=16384' \
  ../src/configure --prefix=/usr --with-shared --without-normal \
  --without-debug --without-profile --without-ada --without-tests --without-progs \
  --without-cxx --without-cxx-binding --without-gpm --enable-widec \
  --with-termlib=tinfo --with-versioned-syms --disable-root-access \
  --disable-setuid-environ --disable-termcap --disable-rpath --enable-const \
  --with-default-terminfo-dir=/etc/terminfo \
  --with-terminfo-dirs='/etc/terminfo:/lib/terminfo:/usr/share/terminfo'
make -j2
# ncurses_cfg.h only emits detected features; ncurses_def.h supplies zero
# defaults. Verify the effective compiler configuration, not one header's text.
cc -dM -E -Iinclude -I../src/include -include ncurses_cfg.h - </dev/null > "$WORK/macros.txt"
grep -q '^#define HAVE_SETFSUID 0$' "$WORK/macros.txt"
if grep -q '^#define USE_ROOT_ACCESS' "$WORK/macros.txt"; then
  echo 'Unsafe root-access configuration' >&2; exit 1
fi
LIB="$WORK/build/lib/libtinfo.so.6.4"
test -s "$LIB"
readelf -Ws "$LIB" > "$WORK/symbols.txt"
if grep -Eq 'UND.*setfs[ug]id' "$WORK/symbols.txt"; then
  echo 'Forbidden filesystem identity dependency' >&2; exit 1
fi
mkdir -p "$BUNDLE/etc/third-party"
cp "$LIB" "$BUNDLE/lib/libtinfo.so.6"
cp "$WORK/src/COPYING" "$BUNDLE/etc/third-party/ncurses-upstream-copying"
cat > "$BUNDLE/etc/third-party/ncurses-build.txt" <<'EOF'
ncurses 6.4+20240113-1ubuntu2.2 (Android no-setfsuid build)
https://ports.ubuntu.com/pool/main/n/ncurses/
source SHA-256: 37a12a0f8ae2605012c9a164dd286b0cfa02b51b5055836d09eb3d597fc351b1
Ubuntu patch archive SHA-256: c7bbb8483d7ec358fb925a370575d8ebef63d6e455edce140de2ca7b86cf98d1
All patches in Debian series applied; ac_cv_func_setfsuid=no.
Upstream safe-open fallback; root-access disabled; no syscall emulation.
Recipe: scripts/build-android-tinfo.sh in andcode-android source.
EOF
# Re-register the replaced library and its data notices with truthful provenance.
awk -F '\t' 'BEGIN {OFS="\t"}
  $1 == "lib/libtinfo.so.6" {$5="6.4+20240113-1ubuntu2.2-android-no-setfsuid"}
  {print}' "$BUNDLE/manifest" > "$WORK/manifest"
for name in ncurses-build.txt ncurses-upstream-copying; do
  printf 'etc/third-party/%s\t-\tdata\tMIT\t6.4+20240113-1ubuntu2.2-android-no-setfsuid\t%s/\n' "$name" "$BASE" >> "$WORK/manifest"
done
mv "$WORK/manifest" "$BUNDLE/manifest"
