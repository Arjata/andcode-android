#!/system/bin/sh
# dev-dns-debug.sh — DNS/网络分层诊断
ROOT=/data/local/tmp/andcode
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
cd "$ROOT"

echo "== 1. IP 直连(排除 DNS): curl 到 1.1.1.1 =="
LD_PRELOAD="$ROOT/shim/libandcode-shim.so" ANDCODE_ETC_DIR="$ROOT/etc" \
  "$ROOT/lib/ld-linux-aarch64.so.1" --library-path "$ROOT/lib" --inhibit-cache \
  "$ROOT/usr/libexec/git-core/git-remote-http.bin" "" https://1.1.1.1/ </dev/null 2>&1 | head -n 3

echo "== 2. git ls-remote 带 curl verbose =="
GIT_CURL_VERBOSE=1 timeout 40 git ls-remote https://github.com/git/git.git HEAD 2>&1 | head -n 12

echo "== 3. resolv.conf 实际生效性: 指向 TEST-NET(不可达)测时延 =="
cp "$ROOT/etc/resolv.conf" /data/local/tmp/resolv.bak
printf 'nameserver 192.0.2.1\noptions timeout:1 attempts:1\n' > "$ROOT/etc/resolv.conf"
S=$(date +%s%N 2>/dev/null || echo 0)
timeout 30 git ls-remote https://github.com/git/git.git HEAD >/dev/null 2>&1
E=$(date +%s%N 2>/dev/null || echo 0)
[ "$S" != "0" ] && echo "  TEST-NET 耗时: $(( (E - S) / 1000000 )) ms(若 ~1-2s 说明读取了我们的 resolv.conf)"
cp /data/local/tmp/resolv.bak "$ROOT/etc/resolv.conf"
