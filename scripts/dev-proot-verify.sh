#!/system/bin/sh
# dev-proot-verify.sh — Verify /etc visibility inside proot and layered DNS behavior
ROOT=/data/local/tmp/andcode
P="$ROOT/usr/lib/proot/proot"
export ANDCODE_ROOT="$ROOT" ANDCODE_TIER=a
export PATH="$ROOT/bin:$ROOT/usr/bin:$ROOT/usr/libexec/git-core:$PATH"
export HOME="$ROOT/home"
unset LD_PRELOAD
export PROOT_LOADER="$ROOT/usr/lib/proot/loader"

echo "== resolv.conf(设备侧实体)=="
cat "$ROOT/etc/resolv.conf"

echo "== proot 内: /etc/resolv.conf 与 /etc/ssl =="
"$P" -b "$ROOT/etc/resolv.conf:/etc/resolv.conf" \
     -b "$ROOT/etc/ssl:/etc/ssl" \
     -b "$ROOT/etc/ssl:/usr/lib/ssl" \
     -b "$ROOT/etc/passwd:/etc/passwd" \
     -b "$ROOT/etc/group:/etc/group" \
     -b "$ROOT/etc/nsswitch.conf:/etc/nsswitch.conf" \
     -w /data/local/tmp \
     /system/bin/sh -c 'cat /etc/resolv.conf; ls /etc/ssl | head -n 3' 2>&1 | head -n 10

echo "== proot 内: git ls-remote(verbose)=="
"$P" -b "$ROOT/etc/resolv.conf:/etc/resolv.conf" \
     -b "$ROOT/etc/ssl:/etc/ssl" \
     -b "$ROOT/etc/ssl:/usr/lib/ssl" \
     -b "$ROOT/etc/passwd:/etc/passwd" \
     -b "$ROOT/etc/group:/etc/group" \
     -b "$ROOT/etc/nsswitch.conf:/etc/nsswitch.conf" \
     -w /data/local/tmp \
     /system/bin/sh -c 'GIT_CURL_VERBOSE=1 timeout 60 git ls-remote https://github.com/git/git.git HEAD 2>&1' | grep -iE 'info|fatal|error|resolve|Could' | head -n 8
