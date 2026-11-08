#!/system/bin/sh
# patch-seccomp.sh — glibc seccomp 兼容补丁(Tier P 应用上下文,DESIGN v0.4.2)
#
# 背景: 部分设备(4.9-perf 内核 + GSI)的 zygote seccomp 策略对以下 syscall
# 返回 SIGSYS(TRAP),而它们位于 glibc 启动/线程创建的必经之路,导致任何
# glibc 二进制在应用域内启动即死("Bad system call");bionic 自身不调用它们,
# 故普通 App 与 adb root(su 域,无 zygote seccomp)均不受影响:
#   NR 99  set_robust_list — ld.so/libc 线程初始化(主线程 + 每线程)
#   NR 293 rseq            — glibc 2.35+ 每线程注册(裸 syscall,非 libc 符号)
#   NR 435 clone3          — glibc 2.34+ pthread_create(TRAP 使 ENOSYS 回退失效)
#   NR 439 faccessat2      — Bash 交互启动的权限探测(同样阻断 ENOSYS 回退)
#
# 补丁(全部等价/无害替换):
#   set_robust_list → sched_yield(124,恒返 0,即"注册成功"语义)
#   rseq            → sched_yield,叠加 GLIBC_TUNABLES=glibc.pthread.rseq=0 双保险
#   clone3 的 svc   → mov x0,#-38(-ENOSYS),glibc 走传统 clone(220) 回退;
#                     不借用其它系统调用号,兼容新旧内核。
#   faccessat2 的 svc → mov x0,#-38(-ENOSYS),进入 glibc 自带 faccessat 回退。
#     仅修改该调用点,不向其他 syscall 填入 faccessat2 的参数。
#
# 指令编码(aarch64): mov x8,#imm = 0xd2800000 | (imm<<5) | 8
#   #99=680c80d2  #124=880f80d2  #293=a82480d2  #435=683680d2  #436=883680d2
#
# 用法: sh patch-seccomp.sh <bundle-root>
# 幂等: 每处先校验"期望原始字节",已是补丁后字节则跳过,不匹配则报错。
# 注意: 偏移对应本仓库基线构建的 glibc 2.39(busybox 根文件系统),其他
#       glibc 构建必须重新定位(字节校验会拒绝错误基线)。
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
# rtld 线程初始化: set_tid_address(96) / set_robust_list(99) / rseq(293) 三连
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
# Ubuntu libc6_2.39-0ubuntu8.9_arm64: faccessat+0x4c,0xdc94c。
# 前面的 x8=439 保持不变;跳过 svc 并合成 -ENOSYS,后续标准错误处理保持不变。
# 除 svc 字节外同时确认所属 syscall,避免其它构建在同偏移恰好也是 svc。
callnr=$($BB dd if="$LC" bs=1 skip=903480 count=4 2>/dev/null | $BB od -A n -t x1 | $BB tr -d ' \n')
[ "$callnr" = "e83680d2" ] || { echo 'ERROR: faccessat2 调用点基线不匹配'; exit 1; }
patch_one "$LC" 903500 "010000d4" "a0048092" '\xa0\x04\x80\x92' '\x01\x00\x00\xd4' "faccessat2->ENOSYS(faccessat fallback)" && n=$((n+1))

echo "patched: $n 处"
[ "$n" -eq 7 ] || { echo 'ERROR: 补丁未全部通过校验'; exit 1; }
echo "提醒: 会话环境建议含 GLIBC_TUNABLES=glibc.pthread.rseq=0(双保险)"
