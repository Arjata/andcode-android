/*
 * andcode-launcher — 静态 musl 启动器(DESIGN §4.5 候选①, AGPL-3.0)
 *
 * 用途: 取代 git-core 助手的 shell wrapper。git 以 execvp 调用本启动器
 * (argv[0] = "git-remote-https" 等裸名),启动器按 ANDCODE_* 环境变量
 * 组装 loader 参数并 execve 真正的 .bin ELF。执行链中不存在 shell,
 * 规避真机实测的 spawn 异常(dash 从 stdin 读协议帧)与 LD_PRELOAD
 * 泄漏(shim 构造器自清)。
 *
 * 构建: musl-gcc -static -O2 -o launcher launcher.c   (基线容器 musl-tools)
 * 环境: ANDCODE_ROOT(必须)、ANDCODE_EXE_DIR(默认 ROOT)、
 *       ANDCODE_LOADER(默认 $ROOT/lib/ld-linux-aarch64.so.1)、
 *       ANDCODE_LIBPATH(默认 $ROOT/lib)、ANDCODE_SHIM(可选)
 */
#define _GNU_SOURCE
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define CAP 4096

static char *xstrdup(const char *s) {
    char *p = strdup(s);
    if (!p) { fprintf(stderr, "andcode-launcher: OOM\n"); exit(127); }
    return p;
}

int main(int argc, char **argv) {
    const char *root = getenv("ANDCODE_ROOT");
    if (!root) { fprintf(stderr, "andcode-launcher: ANDCODE_ROOT not set\n"); return 127; }
    const char *exedir = getenv("ANDCODE_EXE_DIR");
    if (!exedir) exedir = root;

    /* 目标 .bin: $ROOT/usr/libexec/git-core/<argv0 基名>.bin */
    const char *a0 = strrchr(argv[0], '/');
    a0 = a0 ? a0 + 1 : argv[0];
    char self[CAP];
    snprintf(self, sizeof self, "%s/usr/libexec/git-core/%s.bin", root, a0);

    char loader[CAP], libdir[CAP], shim[CAP];
    const char *ld = getenv("ANDCODE_LOADER");
    snprintf(loader, sizeof loader, "%s", ld ? ld : "");
    if (!ld || !*ld) snprintf(loader, sizeof loader, "%s/lib/ld-linux-aarch64.so.1", root);
    const char *lp = getenv("ANDCODE_LIBPATH");
    snprintf(libdir, sizeof libdir, "%s", lp ? lp : "");
    if (!lp || !*lp) snprintf(libdir, sizeof libdir, "%s/lib", root);
    const char *sh = getenv("ANDCODE_SHIM");
    snprintf(shim, sizeof shim, "%s", sh ? sh : "");
    if (!sh || !*sh) snprintf(shim, sizeof shim, "%s/shim/libandcode-shim.so", root);

    /* 为 exec 设置 shim/ETC_DIR;shim 构造器会在加载后自行清除 LD_PRELOAD,
     * 因此本进程派生的 Bionic 子进程不受影响 */
    setenv("LD_PRELOAD", shim, 1);
    {
        char etc[CAP];
        snprintf(etc, sizeof etc, "%s/etc", root);
        setenv("ANDCODE_ETC_DIR", etc, 0);
    }

    /* argv: loader --library-path LIBPATH --inhibit-cache SELF argv[1..] */
    char **nargv = malloc(sizeof(char *) * (size_t)(argc + 5));
    if (!nargv) { fprintf(stderr, "andcode-launcher: OOM\n"); return 127; }
    int i = 0;
    nargv[i++] = loader;
    nargv[i++] = (char *)"--library-path";
    nargv[i++] = libdir;
    nargv[i++] = (char *)"--inhibit-cache";
    nargv[i++] = self;
    for (int k = 1; k < argc; k++) nargv[i++] = argv[k];
    nargv[i] = NULL;

    execv(loader, nargv);
    fprintf(stderr, "andcode-launcher: exec %s failed: %s\n", loader, strerror(errno));
    return 127;
}
