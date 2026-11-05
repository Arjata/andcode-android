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
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static const char *const REDIRECT_BASENAMES[] = {
    "resolv.conf", "hosts", "host.conf", "nsswitch.conf",
    "passwd", "group", "services", NULL,
};

static int getenv_flag(void) { return getenv("ANDCODE_ETC_DIR") != NULL; }

/* 返回重定向后的路径;不需重定向返回 NULL */
static const char *redirect_path(const char *path, char *buf, size_t buflen) {
    if (!path || !getenv_flag()) return NULL;
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
