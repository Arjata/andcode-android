#!/system/bin/sh
# patch-seccomp.sh — glibc seccomp compatibility patches (Tier P application context, DESIGN v0.4.2)
#
# Background: on some devices (4.9-perf kernel + GSI), zygote seccomp sends
# SIGSYS (TRAP) for these syscalls, which glibc startup/thread creation requires,
# killing any glibc binary at startup in the app domain ("Bad system call"). Bionic
# does not call them, so ordinary apps and adb root (su domain, no zygote seccomp) are unaffected:
#   NR 99  set_robust_list — ld.so/libc thread initialization (main thread + each thread)
#   NR 293 rseq            — glibc 2.35+ per-thread registration (raw syscall, not a libc symbol)
#   NR 435 clone3          — glibc 2.34+ pthread_create (TRAP prevents ENOSYS fallback)
#   NR 439 faccessat2      — Bash interactive-startup permission checks (also blocks ENOSYS fallback)
#
# Patches (equivalent/harmless replacements):
#   set_robust_list → sched_yield (124, always returns 0, meaning "registration succeeded")
#   rseq            → sched_yield, combined with GLIBC_TUNABLES=glibc.pthread.rseq=0 as a second safeguard
#   clone3 svc      → mov x0,#-38 (-ENOSYS), making glibc fall back to legacy clone (220);
#                     no other syscall number is reused, supporting old and new kernels.
#   faccessat2 svc  → mov x0,#-38 (-ENOSYS), entering glibc's built-in faccessat fallback.
#     Only this call site changes; faccessat2 arguments are not passed to another syscall.
#
# Instruction encoding (aarch64): mov x8,#imm = 0xd2800000 | (imm<<5) | 8
#   #99=680c80d2  #124=880f80d2  #293=a82480d2  #435=683680d2  #436=883680d2
#
# Usage: sh patch-seccomp.sh <bundle-root>
# Idempotent: verify expected original bytes at each site; skip already-patched bytes and report mismatches.
# Note: offsets target this repository's baseline glibc 2.39 build (busybox root filesystem).
#       Other glibc builds need new offsets (byte checks reject an incorrect baseline).
set -u
ROOT="${1:?usage: patch-seccomp.sh <bundle-root>}"
BB="$ROOT/bin/busybox"
[ -x "$BB" ] || BB=busybox

# patch_one <file> <off> <exp_hex> <new_hex> <new_fmt> <exp_fmt> <label>
patch_one() {
    f="$1" off="$2" exp="$3" new="$4" nfmt="$5" efmt="$6" label="$7"
    cur=$($BB dd if="$f" bs=1 skip="$off" count=4 2>/dev/null | $BB od -A n -t x1 | $BB tr -d ' \n')
    if [ "$cur" = "$new" ]; then
        echo "  ok(已补): $label"
        return 0
    fi
    if [ "$cur" != "$exp" ]; then
        echo "  ERROR: $label 期望 $exp 实际 $cur(基线不匹配,跳过)"
        return 1
    fi
    $BB printf "$nfmt" | $BB dd of="$f" bs=1 seek="$off" conv=notrunc 2>/dev/null
    now=$($BB dd if="$f" bs=1 skip="$off" count=4 2>/dev/null | $BB od -A n -t x1 | $BB tr -d ' \n')
    if [ "$now" != "$new" ]; then
        $BB printf "$efmt" | $BB dd of="$f" bs=1 seek="$off" conv=notrunc 2>/dev/null
        echo "  ERROR: $label 写入校验失败(已回滚)"
        return 1
    fi
    chmod 0755 "$f"
    echo "  patched: $label ($exp -> $new)"
}

LD="$ROOT/lib/ld-linux-aarch64.so.1"
LC="$ROOT/lib/libc.so.6"
for f in "$LD" "$LC"; do
    [ -f "$f" ] || { echo "ERROR: 缺少 $f"; exit 1; }
done

n=0
echo "== ld-linux-aarch64.so.1 =="
# rtld thread initialization: set_tid_address(96) / set_robust_list(99) / rseq(293) sequence
patch_one "$LD" 67248 "680c80d2" "880f80d2" '\x88\x0f\x80\xd2' '\x68\x0c\x80\xd2' "set_robust_list->sched_yield" && n=$((n+1))
patch_one "$LD" 67324 "a82480d2" "880f80d2" '\x88\x0f\x80\xd2' '\xa8\x24\x80\xd2' "rseq->sched_yield" && n=$((n+1))

echo "== libc.so.6 =="
patch_one "$LC" 546232 "680c80d2" "880f80d2" '\x88\x0f\x80\xd2' '\x68\x0c\x80\xd2' "set_robust_list->sched_yield(init)" && n=$((n+1))
patch_one "$LC" 775112 "680c80d2" "880f80d2" '\x88\x0f\x80\xd2' '\x68\x0c\x80\xd2' "set_robust_list->sched_yield(public)" && n=$((n+1))
patch_one "$LC" 546884 "a82480d2" "880f80d2" '\x88\x0f\x80\xd2' '\xa8\x24\x80\xd2' "rseq->sched_yield" && n=$((n+1))
# Verify original clone3 or our legacy close_range placeholder, then skip svc.
# A modern kernel implements close_range: borrowing its number is not ENOSYS.
callnr=$($BB dd if="$LC" bs=1 skip=965408 count=4 2>/dev/null | $BB od -A n -t x1 | $BB tr -d ' \n')
case "$callnr" in 683680d2|883680d2) ;; *) echo 'ERROR: clone3 调用点基线不匹配'; exit 1 ;; esac
patch_one "$LC" 965412 "010000d4" "a0048092" '\xa0\x04\x80\x92' '\x01\x00\x00\xd4' "clone3->ENOSYS(clone fallback)" && n=$((n+1))
# Ubuntu libc6_2.39-0ubuntu8.9_arm64: faccessat+0x4c,0xdc94c.
# Keep the preceding x8=439; skip svc and synthesize -ENOSYS, retaining subsequent standard error handling.
# Verify the syscall identity as well as svc bytes in case another build has a different svc at the same offset.
callnr=$($BB dd if="$LC" bs=1 skip=903480 count=4 2>/dev/null | $BB od -A n -t x1 | $BB tr -d ' \n')
[ "$callnr" = "e83680d2" ] || { echo 'ERROR: faccessat2 调用点基线不匹配'; exit 1; }
patch_one "$LC" 903500 "010000d4" "a0048092" '\xa0\x04\x80\x92' '\x01\x00\x00\xd4' "faccessat2->ENOSYS(faccessat fallback)" && n=$((n+1))

echo "patched: $n 处"
[ "$n" -eq 7 ] || { echo 'ERROR: 补丁未全部通过校验'; exit 1; }
echo "提醒: 会话环境建议含 GLIBC_TUNABLES=glibc.pthread.rseq=0(双保险)"
