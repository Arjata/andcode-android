"""Exercise our launcher argv construction on Linux with address/UB sanitizers."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class LauncherTest(unittest.TestCase):
    def test_argv_with_and_without_proot(self):
        source = Path(__file__).resolve().parents[1] / 'bundle/launcher/launcher.c'
        # Redirect only OS boundary calls in the test translation unit. Do not
        # execute proot, mount anything, or require Android on the Linux runner.
        harness = r'''
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
static int fake_access(const char *path, int mode) { (void)path; (void)mode; return 0; }
static int fake_execv(const char *path, char *const args[]) {
    const char *direct[] = {"/fixture/lib/ld-linux-aarch64.so.1", "--library-path",
        "/fixture/lib", "--inhibit-cache", "/fixture/usr/libexec/git-core/git-remote-https.bin"};
    const char *prefix[] = {"/fixture/usr/lib/proot/proot",
        "-b", "/fixture/etc/resolv.conf:/etc/resolv.conf",
        "-b", "/fixture/etc/ssl:/etc/ssl", "-b", "/fixture/etc/ssl:/usr/lib/ssl",
        "-b", "/fixture/etc/passwd:/etc/passwd", "-b", "/fixture/etc/group:/etc/group",
        "-b", "/fixture/etc/nsswitch.conf:/etc/nsswitch.conf", "-w"};
    int i = 0;
    if (!getenv("TEST_DIRECT")) {
        for (size_t j = 0; j < sizeof(prefix)/sizeof(prefix[0]); ++j)
            if (!args[i] || strcmp(args[i++], prefix[j])) exit(10);
        if (!args[i] || args[i++][0] != '/') exit(11);  /* getcwd */
    }
    for (size_t j = 0; j < sizeof(direct)/sizeof(direct[0]); ++j)
        if (!args[i] || strcmp(args[i++], direct[j])) exit(12);
    const char *user[] = {"origin", "https://example.test/a b", "", "semi;dollar$"};
    for (size_t j = 0; j < sizeof(user)/sizeof(user[0]); ++j)
        if (!args[i] || strcmp(args[i++], user[j])) exit(13);
    if (args[i] != NULL || strcmp(path, args[0])) exit(14);
    if (!getenv("TEST_DIRECT")) {
        const char *lib = getenv("LD_LIBRARY_PATH");
        if (!lib || strcmp(lib, getenv("TEST_TIER_P") ? "/native" : "/fixture/usr/lib/proot")) exit(15);
        if (getenv("LD_PRELOAD")) exit(16);
    } else {
        const char *preload = getenv("LD_PRELOAD");
        if (!preload || strcmp(preload, "/fixture/shim/libandcode-shim.so")) exit(17);
    }
    exit(0);
}
#define access fake_access
#define execv fake_execv
#define main launcher_main
#include "LAUNCHER_SOURCE"
#undef main
int main(void) {
    setenv("ANDCODE_ROOT", "/fixture", 1);
    if (getenv("TEST_TIER_P")) {
        setenv("ANDCODE_TIER", "p", 1); setenv("ANDCODE_EXE_DIR", "/native", 1);
    } else { unsetenv("ANDCODE_TIER"); unsetenv("ANDCODE_EXE_DIR"); }
    unsetenv("ANDCODE_LOADER"); unsetenv("ANDCODE_LIBPATH");
    unsetenv("ANDCODE_SHIM");
    if (getenv("TEST_DIRECT")) setenv("ANDCODE_IN_PROOT", "1", 1);
    else unsetenv("ANDCODE_IN_PROOT");
    char *args[] = {"/farm/git-remote-https", "origin", "https://example.test/a b", "", "semi;dollar$", NULL};
    return launcher_main(5, args);
}
'''.replace('LAUNCHER_SOURCE', source.as_posix())
        with tempfile.TemporaryDirectory(prefix='andcode-launcher-') as work:
            c = Path(work) / 'test.c'
            binary = Path(work) / 'test'
            c.write_text(harness, encoding='utf-8')
            subprocess.run(['cc', '-D_GNU_SOURCE', '-g', '-O1', '-fsanitize=address,undefined',
                            '-fno-omit-frame-pointer', str(c), '-o', str(binary)], check=True)
            for direct, tier_p in ((False, False), (True, False), (False, True), (True, True)):
                with self.subTest(direct=direct, tier_p=tier_p):
                    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
                    env.pop('TEST_DIRECT', None)
                    env.pop('TEST_TIER_P', None)
                    if tier_p:
                        env['TEST_TIER_P'] = '1'
                    if direct:
                        env['TEST_DIRECT'] = '1'
                    subprocess.run([str(binary)], env=env, check=True, timeout=15)


if __name__ == '__main__':
    unittest.main()
