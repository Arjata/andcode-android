/*
 * andcode-launcher — static musl launcher (DESIGN §4.5 candidate ①, AGPL-3.0)
 *
 * Purpose: replace shell wrappers for git-core helpers. git invokes this launcher via execvp
 * (argv[0] is a bare name such as "git-remote-https"); the launcher uses ANDCODE_* environment
 * variables to assemble loader arguments and execve the actual .bin ELF. No shell is involved,
 * avoiding spawn failures observed on devices (dash reading protocol frames from stdin) and
 * LD_PRELOAD leakage (the shim constructor clears it).
 *
 * Build: musl-gcc -static -O2 -o launcher launcher.c   (musl-tools in the baseline container)
 * Environment: ANDCODE_ROOT (required), ANDCODE_EXE_DIR (defaults to ROOT),
 *       ANDCODE_LOADER (defaults to $ROOT/lib/ld-linux-aarch64.so.1),
 *       ANDCODE_LIBPATH (defaults to $ROOT/lib), ANDCODE_SHIM (optional)
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

/* Prevent nested proot when already ptrace-traced (by a parent proot). The environment guard
 * (ANDCODE_IN_PROOT) may be lost to upstream spawn environment sanitization; TracerPid is a
 * reliable environment-independent check (nested proot deadlocks were observed on devices). */
static int is_traced(void) {
    FILE *f = fopen("/proc/self/status", "r");
    char line[256];
    if (!f) return 0;
    while (fgets(line, sizeof line, f)) {
        if (strncmp(line, "TracerPid:", 10) == 0) {
            int pid = atoi(line + 10);
            fclose(f);
            return pid != 0;
        }
    }
    fclose(f);
    return 0;
}

int main(int argc, char **argv) {
    const char *root = getenv("ANDCODE_ROOT");
    if (!root) { fprintf(stderr, "andcode-launcher: ANDCODE_ROOT not set\n"); return 127; }
    const char *exedir = getenv("ANDCODE_EXE_DIR");
    if (!exedir) exedir = root;

    /* Target .bin: $ROOT/usr/libexec/git-core/<argv0 basename>.bin */
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

    /* Set shim/ETC_DIR for exec; the shim constructor clears LD_PRELOAD after loading,
     * so Bionic children spawned by this process are unaffected. */
    setenv("LD_PRELOAD", shim, 1);
    {
        char etc[CAP];
        snprintf(etc, sizeof etc, "%s/etc", root);
        setenv("ANDCODE_ETC_DIR", etc, 0);
    }

    /* argv: [proot -b ... -w DIR] loader --library-path LIBPATH --inhibit-cache SELF argv[1..]
     * argv[0] must be proot/loader itself; previously prepending loader options shifted all
     * argv entries at execv(proot) (git.bin received argv[0]=loader, "git: '...proot' is not a git command"). */
    /* Largest prefix: proot + seven option/value pairs + loader/four
     * arguments = 20 entries. Then argc-1 user arguments and the NULL.
     * The former argc+16 allocation overran by four pointers with proot. */
    char **nargv = malloc(sizeof(char *) * ((size_t)argc + 20));
    if (!nargv) { fprintf(stderr, "andcode-launcher: OOM\n"); return 127; }
    int i = 0;

    /* proot bind(/etc): internal glibc reads by helpers (/etc/resolv.conf etc.) can only be
     * redirected via proot userspace bind (DESIGN §4.5 v0.4.1); ANDCODE_IN_PROOT guards against nesting. */
    char proot[CAP], resolv[CAP], ssl[CAP], usrlibssl[CAP], pwdf[CAP], grpf[CAP], nss[CAP], wdir[CAP];
    snprintf(proot, sizeof proot, "%s/usr/lib/proot/proot", root);
    snprintf(resolv, sizeof resolv, "%s/etc/resolv.conf:/etc/resolv.conf", root);
    snprintf(ssl, sizeof ssl, "%s/etc/ssl:/etc/ssl", root);
    snprintf(usrlibssl, sizeof usrlibssl, "%s/etc/ssl:/usr/lib/ssl", root);
    snprintf(pwdf, sizeof pwdf, "%s/etc/passwd:/etc/passwd", root);
    snprintf(grpf, sizeof grpf, "%s/etc/group:/etc/group", root);
    snprintf(nss, sizeof nss, "%s/etc/nsswitch.conf:/etc/nsswitch.conf", root);
    if (!getcwd(wdir, sizeof wdir)) snprintf(wdir, sizeof wdir, "/");

    if (access(proot, X_OK) == 0 && access("/system/bin/sh", F_OK) == 0
        && getenv("ANDCODE_IN_PROOT") == NULL && !is_traced()) {
        char ploader[CAP], plib[CAP];
        snprintf(ploader, sizeof ploader, "%s/usr/lib/proot/loader", root);
        snprintf(plib, sizeof plib, "%s/usr/lib/proot", root);
        if (getenv("ANDCODE_TIER") && strcmp(getenv("ANDCODE_TIER"), "p") == 0)
            snprintf(plib, sizeof plib, "%s", exedir);
        setenv("PROOT_LOADER", ploader, 1);
        setenv("LD_LIBRARY_PATH", plib, 1);
        /* PRoot is Bionic: a glibc preload must not reach its linker. The
         * bind mappings provide /etc for the traced glibc child instead. */
        unsetenv("LD_PRELOAD");
        setenv("ANDCODE_IN_PROOT", "1", 1);
        if (getenv("PROOT_TMP_DIR") == NULL) {
            const char *ad = getenv("ANDCODE_APP_DATA");
            char ptmp[CAP];
            snprintf(ptmp, sizeof ptmp, "%s/tmp", ad ? ad : root);
            setenv("PROOT_TMP_DIR", ptmp, 1);
        }
        nargv[i++] = (char *)proot;
        nargv[i++] = (char *)"-b"; nargv[i++] = (char *)resolv;
        nargv[i++] = (char *)"-b"; nargv[i++] = (char *)ssl;
        nargv[i++] = (char *)"-b"; nargv[i++] = (char *)usrlibssl;
        nargv[i++] = (char *)"-b"; nargv[i++] = (char *)pwdf;
        nargv[i++] = (char *)"-b"; nargv[i++] = (char *)grpf;
        nargv[i++] = (char *)"-b"; nargv[i++] = (char *)nss;
        nargv[i++] = (char *)"-w"; nargv[i++] = (char *)wdir;
    }

    nargv[i++] = (char *)loader;
    nargv[i++] = (char *)"--library-path";
    nargv[i++] = (char *)libdir;
    nargv[i++] = (char *)"--inhibit-cache";
    nargv[i++] = (char *)self;

    for (int k = 1; k < argc; k++) nargv[i++] = argv[k];
    nargv[i] = NULL;

    execv(nargv[0], nargv);
    fprintf(stderr, "andcode-launcher: exec %s failed: %s\n", nargv[0], strerror(errno));
    return 127;
}
