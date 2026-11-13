package dev.andcode.app;

import android.content.Context;
import android.content.SharedPreferences;
import java.io.File;

/** App-level preferences, separate from upstream opencode configuration and credentials. */
public final class AppSettings {
    private AppSettings() {}

    static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences("andcode-settings", Context.MODE_PRIVATE);
    }

    static int terminalSize(Context context) {
        return Math.max(10, Math.min(28, prefs(context).getInt("terminal-size", 15)));
    }

    static boolean keepScreenOn(Context context) {
        return prefs(context).getBoolean("keep-screen-on", true);
    }

    static boolean includeGit(Context context) {
        return prefs(context).getBoolean("include-git", false);
    }

    static boolean customCaEnabled(Context context) {
        return prefs(context).getBoolean("custom-ca-enabled", false);
    }

    static String customCaDigest(Context context) {
        return prefs(context).getString("custom-ca-sha256", "");
    }

    /** Terminal backend: without an explicit choice, use Ubuntu when the canonical rootfs is ready (single-APK default). */
    static boolean ubuntuTerminal(Context context) {
        String v = prefs(context).getString("terminal-backend", null);
        if (v != null) return "ubuntu-proot".equals(v);
        return ubuntuAvailable(context);
    }

    static boolean ubuntuProxy(Context context) {
        return prefs(context).getBoolean("ubuntu-loopback-proxy", false);
    }

    /** Opt-in loopback proxy for the managed OpenCode serve (default off). */
    static boolean serveLoopbackProxy(Context context) {
        return prefs(context).getBoolean("serve-loopback-proxy", false);
    }

    /** User-configured proxy URL including its scheme, such as http:// or socks5://; empty means unset, with no injection. */
    static String proxyUrl(Context context) {
        return prefs(context).getString("proxy-url", "");
    }

    /** Opt-in PRoot backend: run the managed OpenCode serve inside the Ubuntu guest (default off). */
    static boolean serveProotBackend(Context context) {
        return prefs(context).getBoolean("serve-proot-backend", false);
    }

    static boolean ubuntuAvailable(Context context) {
        String nat = context.getApplicationInfo().nativeLibraryDir;
        if (nat != null && new File(nat, "libandcode-ld-linux.so").isFile()) {
            return new File(context.getFilesDir(), "proot-rootfs/usr/bin/bash").isFile()
                && new File(nat, "libandcode-usr-lib-proot-proot.so").isFile()
                && new File(nat, "libandcode-usr-lib-proot-loader.so").isFile();
        }
        return new File(context.getFilesDir(), "proot-rootfs/usr/bin/bash").isFile()
            && new File("/data/local/tmp/andcode/usr/lib/proot/proot").isFile()
            && new File("/data/local/tmp/andcode/usr/lib/proot/loader").isFile();
    }

    static File projectsDir(Context context) {
        return new File(context.getFilesDir(), "projects");
    }

    static File selectedProject(Context context) {
        String name = prefs(context).getString("selected-project", "");
        if (name == null || name.isEmpty() || name.contains("/") || name.contains("\\") || name.contains(":")
                || name.equals(".") || name.equals("..")) return null;
        File project = new File(projectsDir(context), name);
        try {
            return !java.nio.file.Files.isSymbolicLink(projectsDir(context).toPath())
                && project.isDirectory() && !java.nio.file.Files.isSymbolicLink(project.toPath())
                && project.getCanonicalFile().equals(new File(context.getFilesDir().getCanonicalFile(),
                    "projects/" + name)) ? project : null;
        } catch (java.io.IOException error) {
            return null;
        }
    }
}
