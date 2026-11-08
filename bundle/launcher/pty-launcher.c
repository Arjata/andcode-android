/* AGPL-3.0-only. Static entry for a preinstalled glibc PTY daemon.
 * Resolve immutable APK install location, not argv[0] or caller environment. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char dir[4096], loader[4096], daemon[4096];
    ssize_t n = readlink("/proc/self/exe", dir, sizeof(dir) - 1);
    if (n < 0 || n >= (ssize_t)sizeof(dir) - 1) return 127;
    dir[n] = 0;
    char *slash = strrchr(dir, '/');
    if (!slash) return 127;
    *slash = 0;
    if (snprintf(loader, sizeof(loader), "%s/libandcode-ld-linux.so", dir) >= (int)sizeof(loader)
        || snprintf(daemon, sizeof(daemon), "%s/libandcode-usr-lib-opencode-pty-opencode-pty.so", dir) >= (int)sizeof(daemon)) return 127;
    char **args = calloc((size_t)argc + 5, sizeof(char *));
    if (!args) return 127;
    args[0] = loader; args[1] = "--library-path"; args[2] = dir;
    args[3] = "--inhibit-cache"; args[4] = daemon;
    for (int i = 1; i < argc; i++) args[i + 4] = argv[i];
    execv(loader, args);
    perror("andcode PTY loader");
    return 127;
}
