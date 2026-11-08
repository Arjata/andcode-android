package dev.andcode.app;

import android.content.Context;
import android.content.SharedPreferences;
import java.io.File;

/** 应用级偏好;不与上游 opencode 配置或凭据混用。 */
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

    static boolean ubuntuTerminal(Context context) {
        return "ubuntu-proot".equals(prefs(context).getString("terminal-backend", "bash"));
    }

    static boolean ubuntuProxy(Context context) {
        return prefs(context).getBoolean("ubuntu-loopback-proxy", false);
    }

    static boolean ubuntuAvailable(Context context) {
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
