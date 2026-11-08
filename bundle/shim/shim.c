/*
 * libandcode-shim.so — andcode LD_PRELOAD 重定向 shim(DESIGN §4.5, AGPL-3.0)
 *
 * 背景:Android 的 /etc 只读。glibc 运行期需读取 resolv.conf / passwd / group /
 * hosts / nsswitch.conf 等,本 shim 把对这些路径的 open/stat/access 重定向到
 * $ANDCODE_ETC_DIR 下的副本(由 andcode-mkresolv / entry 预生成)。
 *
 * 构建: make -C bundle/shim CC=aarch64-linux-gnu-gcc
 * 用法: LD_PRELOAD=$ROOT/shim/libandcode-shim.so  ANDCODE_ETC_DIR=$ROOT/etc
 *
 * 设计约束(see docs/REUSE.md §2.1 termux-exec 参照):
 *  - 仅拦截面内行为,其余全部 RTLD_NEXT 透传;
 *  - 未设 ANDCODE_ETC_DIR 时完全透明;
 *  - 重定向仅在 $ANDCODE_ETC_DIR/<basename> 存在时生效,否则回落原路径。
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

static const char *const REDIRECT_BASENAMES[] = {
    "resolv.conf", "hosts", "host.conf", "nsswitch.conf",
    "passwd", "group", "services", NULL,
};

static int getenv_flag(void) { return getenv("ANDCODE_ETC_DIR") != NULL; }

/*
 * 自清构造器:本 shim 经 LD_PRELOAD 注入 glibc 进程后,立即从环境中移除
 * LD_PRELOAD。否则该进程派生的 Android Bionic 子进程(/system/bin/sh 等)
 * 会继承 LD_PRELOAD 并因无法加载 glibc 依赖而拒绝执行(真机实测:
 * CANNOT LINK EXECUTABLE "/bin/sh": libc.so.6 not found)。子进程若需
 * shim(如 git 助手包装器)由各自 wrapper 重新设置。
 */
__attribute__((constructor)) static void andcode_shim_sanitize(void) {
    unsetenv("LD_PRELOAD");
}

/* /etc/ssl/ 整段前缀重定向(CA 证书树;pack-bundle 已收入 $ANDCODE_ETC_DIR/ssl) */
static int redirect_ssl(const char *path, char *buf, size_t buflen) {
    const char *dir;
    size_t n;
    if (!path || !getenv_flag()) return 0;
    if (strncmp(path, "/etc/ssl/", 9) != 0) return 0;
    dir = getenv("ANDCODE_ETC_DIR");
    n = (size_t)snprintf(buf, buflen, "%s/ssl/%s", dir, path + 9);
    if (n >= buflen) return 0;
    { struct stat st; if (stat(buf, &st) != 0) return 0; } /* 副本存在才重定向 */
    return 1;
}

/* 返回重定向后的路径;不需重定向返回 NULL */
static const char *redirect_path(const char *path, char *buf, size_t buflen) {
    if (!path || !getenv_flag()) return NULL;
    if (redirect_ssl(path, buf, buflen)) return buf;   /* /etc/ssl/ 前缀整段 */
    /* 只处理绝对 /etc/<name>;符号链接与相对路径透传 */
    if (strncmp(path, "/etc/", 5) != 0 || strchr(path + 5, '/')) return NULL;
    const char *base = path + 5;
    for (int i = 0; REDIRECT_BASENAMES[i]; i++) {
        if (strcmp(base, REDIRECT_BASENAMES[i]) == 0) {
            const char *dir = getenv("ANDCODE_ETC_DIR");
            int n = snprintf(buf, buflen, "%s/%s", dir, base);
            if (n > 0 && (size_t)n < buflen) {
                struct stat st;
                if (stat(buf, &st) == 0) return buf; /* 副本存在才重定向 */
            }
            return NULL;
        }
    }
    return NULL;
}

#define DEF(fn, ret, args, ...)                                               \
    static ret (*real_##fn) args = NULL;                                      \
    static void init_##fn(void) {                                             \
        if (!real_##fn) real_##fn = dlsym(RTLD_NEXT, #fn);                    \
    }

DEF(open, int, (const char *, int, ...))
DEF(open64, int, (const char *, int, ...))
DEF(openat, int, (int, const char *, int, ...))
DEF(stat, int, (const char *, struct stat *))
DEF(stat64, int, (const char *, struct stat64 *))
DEF(access, int, (const char *, int))

int open(const char *path, int flags, ...) {
    init_open();
    char buf[PATH_MAX];
    const char *r = redirect_path(path, buf, sizeof buf);
    mode_t mode = 0;
    if (flags & (O_CREAT | O_TMPFILE)) {
        va_list ap; va_start(ap, flags); mode = va_arg(ap, mode_t); va_end(ap);
    }
    return real_open(r ? r : path, flags, mode);
}

int open64(const char *path, int flags, ...) {
    init_open64();
    char buf[PATH_MAX];
    const char *r = redirect_path(path, buf, sizeof buf);
    mode_t mode = 0;
    if (flags & (O_CREAT | O_TMPFILE)) {
        va_list ap; va_start(ap, flags); mode = va_arg(ap, mode_t); va_end(ap);
    }
    return real_open64(r ? r : path, flags, mode);
}

int openat(int dirfd, const char *path, int flags, ...) {
    init_openat();
    char buf[PATH_MAX];
    const char *r = redirect_path(path, buf, sizeof buf);
    mode_t mode = 0;
    if (flags & (O_CREAT | O_TMPFILE)) {
        va_list ap; va_start(ap, flags); mode = va_arg(ap, mode_t); va_end(ap);
    }
    return real_openat(dirfd, r ? r : path, flags, mode);
}

int stat(const char *path, struct stat *st) {
    init_stat();
    char buf[PATH_MAX];
    const char *r = redirect_path(path, buf, sizeof buf);
    return real_stat(r ? r : path, st);
}

#if defined(__GLIBC__) && __GLIBC__ >= 2 && defined(_LARGEFILE64_SOURCE)
int stat64(const char *path, struct stat64 *st) {
    init_stat64();
    char buf[PATH_MAX];
    const char *r = redirect_path(path, buf, sizeof buf);
    return real_stat64(r ? r : path, st);
}
#endif

int access(const char *path, int mode) {
    init_access();
    char buf[PATH_MAX];
    const char *r = redirect_path(path, buf, sizeof buf);
    return real_access(r ? r : path, mode);
}

/* ncurses safe-open normally lowers fsuid/fsgid even when already unprivileged.
 * Zygote seccomp traps those calls. Do NOT intercept/fake setfsuid itself.
 * Only Tier P's ncurses entry points may skip that redundant transition, after
 * checking this THREAD's real/effective/saved/fs IDs and capabilities. Opening
 * the file still uses normal kernel DAC/SELinux checks. No elevated fallback. */
static int ncurses_app_identity(void) {
    char text[8192];
    int fd = (int)syscall(SYS_openat, AT_FDCWD, "/proc/thread-self/status", O_RDONLY | O_CLOEXEC, 0);
    if (fd < 0) return 0;
    ssize_t n = read(fd, text, sizeof(text) - 1);
    close(fd);
    if (n <= 0 || n == (ssize_t)sizeof(text) - 1) return 0;
    text[n] = 0;
    unsigned long u[4], g[4];
    unsigned long long inh, prm, eff, amb;
    char *uid = strstr(text, "\nUid:"), *gid = strstr(text, "\nGid:");
    char *ci = strstr(text, "\nCapInh:"), *cp = strstr(text, "\nCapPrm:");
    char *ce = strstr(text, "\nCapEff:"), *ca = strstr(text, "\nCapAmb:");
    if (!uid || !gid || !ci || !cp || !ce || !ca
        || sscanf(uid, "\nUid: %lu %lu %lu %lu", &u[0], &u[1], &u[2], &u[3]) != 4
        || sscanf(gid, "\nGid: %lu %lu %lu %lu", &g[0], &g[1], &g[2], &g[3]) != 4
        || sscanf(ci, "\nCapInh: %llx", &inh) != 1
        || sscanf(cp, "\nCapPrm: %llx", &prm) != 1
        || sscanf(ce, "\nCapEff: %llx", &eff) != 1
        || sscanf(ca, "\nCapAmb: %llx", &amb) != 1) return 0;
    if (u[0] == 0 || g[0] == 0 || inh || prm || eff || amb) return 0;
    for (int i = 1; i < 4; i++)
        if (u[i] != u[0] || g[i] != g[0]) return 0;
    return 1;
}

static int ncurses_tier_p(void) {
    const char *tier = getenv("ANDCODE_TIER");
    return tier && strcmp(tier, "p") == 0;
}

int _nc_safe_open3(const char *path, int flags, mode_t mode) {
    if (!ncurses_tier_p()) {
        int (*next)(const char *, int, mode_t) = dlsym(RTLD_NEXT, "_nc_safe_open3");
        if (next) return next(path, flags, mode);
        errno = ENOSYS; return -1;
    }
    if (!ncurses_app_identity()) { errno = EPERM; return -1; }
    return open(path, flags, mode);
}

FILE *_nc_safe_fopen(const char *path, const char *mode) {
    if (!ncurses_tier_p()) {
        FILE *(*next)(const char *, const char *) = dlsym(RTLD_NEXT, "_nc_safe_fopen");
        if (next) return next(path, mode);
        errno = ENOSYS; return NULL;
    }
    if (!ncurses_app_identity()) { errno = EPERM; return NULL; }
    /* fopen is not one of the general /etc redirect entry points. */
    char buf[PATH_MAX];
    const char *r = redirect_path(path, buf, sizeof buf);
    return fopen(r ? r : path, mode);
}
