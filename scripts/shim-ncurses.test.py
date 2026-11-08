"""Linux CI: real libtinfo must not call fsuid setters through Tier P shim."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


FIXTURE = r'''
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/fsuid.h>
#include <unistd.h>
static int transitions;
int setfsuid(uid_t uid) { (void)uid; transitions++; return -1; }
int setfsgid(gid_t gid) { (void)gid; transitions++; return -1; }
int main(int argc, char **argv) {
    if (argc != 2) return 90;
    void *lib = dlopen("libtinfo.so.6", RTLD_NOW | RTLD_GLOBAL);
    if (!lib) return 91;
    int (*safe)(const char *, int, mode_t) = dlsym(RTLD_DEFAULT, "_nc_safe_open3");
    FILE *(*safe_fopen)(const char *, const char *) = dlsym(RTLD_DEFAULT, "_nc_safe_fopen");
    int (*setup)(const char *, int, int *) = dlsym(lib, "setupterm");
    if (!safe || !safe_fopen || !setup) return 92;
    if (!strcmp(argv[1], "deny")) {
        errno = 0;
        if (safe("/dev/null", O_RDONLY, 0) != -1 || errno != EPERM) return 93;
        errno = 0;
        if (safe_fopen("/dev/null", "r") != NULL || errno != EPERM) return 94;
    } else {
        int fd = safe("/dev/null", O_RDONLY, 0);
        if (fd < 0) return 95;
        close(fd);
        FILE *f = safe_fopen("/dev/null", "r");
        if (!f) return 96;
        fclose(f);
        if (!strcmp(argv[1], "allow")) {
            errno = 0;
            if (safe("/root/andcode-forbidden", O_RDONLY, 0) != -1 || errno != EACCES) return 97;
            int err;
            if (setup("xterm-256color", STDOUT_FILENO, &err) != 0 || err != 1) return 98;
        }
    }
    if ((!strcmp(argv[1], "passthrough")) != (transitions > 0)) return 99;
    puts("NCURSES_IDENTITY_KERNEL_CHECK_OK");
    return 0;
}
'''


class NcursesShimTest(unittest.TestCase):
    def test_real_libtinfo_identity_and_kernel_permissions(self):
        with tempfile.TemporaryDirectory(prefix='andcode-ncurses-') as work:
            root = Path(work)
            root.chmod(0o755)
            shim = root / 'shim.so'
            source = Path(__file__).resolve().parents[1] / 'bundle/shim/shim.c'
            subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror', str(source), '-ldl', '-o', str(shim)], check=True)
            fixture = root / 'fixture.c'
            fixture.write_text(FIXTURE)
            exe = root / 'fixture'
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-rdynamic', str(fixture), '-ldl', '-o', str(exe)], check=True)
            env = dict(os.environ, LD_PRELOAD=str(shim), ANDCODE_TIER='p')
            subprocess.run([str(exe), 'allow'], env=env, check=True)
            subprocess.run([str(exe), 'passthrough'], env=dict(env, ANDCODE_TIER='a'), check=True)
            subprocess.run(['sudo', '-n', 'env', 'ANDCODE_TIER=p', 'LD_PRELOAD=' + str(shim), str(exe), 'deny'], check=True)


if __name__ == '__main__':
    unittest.main()
