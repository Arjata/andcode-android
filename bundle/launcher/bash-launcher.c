/* AGPL-3.0-only. Tier P Bash must be directly executable by the PTY daemon.
 * A shebang wrapper in nativeLibraryDir is not a reliable execvp boundary.
 * Use the immutable installed directory; never extract an executable at runtime. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char dir[4096], loader[4096], bash[4096], shim[4096], etc[4096];
    ssize_t n = readlink("/proc/self/exe", dir, sizeof(dir) - 1);
    if (n < 0 || n >= (ssize_t)sizeof(dir) - 1) return 127;
    dir[n] = 0;
    char *slash = strrchr(dir, '/');
    if (!slash) return 127;
    *slash = 0;
    const char *root = getenv("ANDCODE_ROOT");
    if (!root || root[0] != '/') {
        fprintf(stderr, "andcode Bash: missing absolute ANDCODE_ROOT\n");
        return 127;
    }
    if (snprintf(loader, sizeof(loader), "%s/libandcode-ld-linux.so", dir) >= (int)sizeof(loader)
        || snprintf(bash, sizeof(bash), "%s/libandcode-bash.so", dir) >= (int)sizeof(bash)
        || snprintf(shim, sizeof(shim), "%s/libandcode-shim.so", dir) >= (int)sizeof(shim)
        || snprintf(etc, sizeof(etc), "%s/etc", root) >= (int)sizeof(etc)) return 127;
    if (unsetenv("LD_PRELOAD") || setenv("ANDCODE_ETC_DIR", etc, 1)) return 127;
    char **args = calloc((size_t)argc + 7, sizeof(char *));
    if (!args) return 127;
    args[0] = loader; args[1] = "--library-path"; args[2] = dir;
    args[3] = "--inhibit-cache"; args[4] = "--preload"; args[5] = shim; args[6] = bash;
    for (int i = 1; i < argc; i++) args[i + 6] = argv[i];
    execv(loader, args);
    perror("andcode Bash loader");
    free(args);
    return 127;
}
