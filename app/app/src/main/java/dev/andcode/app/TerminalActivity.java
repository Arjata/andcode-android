package dev.andcode.app;

import android.annotation.SuppressLint;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.GravityCompat;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.drawerlayout.widget.DrawerLayout;

import com.termux.terminal.TerminalEmulator;
import com.termux.terminal.TerminalSession;
import com.termux.terminal.TerminalSessionClient;
import com.termux.view.TerminalView;
import com.termux.view.TerminalViewClient;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Terminal page (Termux-style): open an interactive shell without automatically starting opencode TUI.
 * Users enter `opencode` to launch the AI coding agent (a shell function in the ENV profile
 * uses the patched loader to work around app-domain seccomp and data-directory exec restrictions).
 *
 * - Session persistence: a static TerminalSession reference keeps the process alive across page exits
 *   and reattaches on return. System process reclamation ends the session; the next visit creates one.
 *   (The SessionService foreground service keeps the process alive, so sessions usually persist.)
 * - Floating ball and shared drawer (as in WebActivity, following the andapi pattern).
 * - Uses ServeManager binary resolution (jniLibs first, /data/local/tmp fallback);
 *   a normal shell remains available without a deployment.
 */
public class TerminalActivity extends AppCompatActivity {

    /** Terminal session retained across pages (static means app-process lifetime). */
    private static TerminalSession sSession;
    /** Callback bridge: the session persists while Activities are recreated; delegate to the foreground instance. */
    private static ClientBridge sBridge;

    private TerminalView mTerminalView;
    private DrawerLayout mDrawer;
    private TerminalExtraKeys mExtraKeys;
    private File mRuntimeRoot;
    private String mRuntimeError;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // Android 15/16 edge-to-edge no longer guarantees that adjustResize
        // shrinks the content view. Apply IME insets to the terminal container
        // so the extra-key rows remain above the keyboard on every API level.
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setContentView(R.layout.activity_terminal);
        mTerminalView = findViewById(R.id.terminal_view);
        // attachSession may initialize the emulator immediately on a laid-out View; bind the client first.
        mTerminalView.setTerminalViewClient(new ViewClient());
        applyTerminalSize();
        mDrawer = findViewById(R.id.rootDrawer);
        getOnBackPressedDispatcher().addCallback(this, new androidx.activity.OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                if (mDrawer.isDrawerOpen(GravityCompat.START)) {
                    mDrawer.closeDrawer(GravityCompat.START);
                } else {
                    setEnabled(false);
                    try { getOnBackPressedDispatcher().onBackPressed(); }
                    finally { setEnabled(true); }
                }
            }
        });

        // Floating drawer ball (shares its dock position with WebActivity).
        FrameLayout content = findViewById(R.id.termContent);
        ViewCompat.setOnApplyWindowInsetsListener(content, (view, insets) -> {
            androidx.core.graphics.Insets system = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            androidx.core.graphics.Insets ime = insets.getInsets(WindowInsetsCompat.Type.ime());
            int bottom = Math.max(system.bottom, ime.bottom);
            view.setPadding(system.left, system.top, system.right, bottom);
            return insets;
        });
        ViewCompat.requestApplyInsets(content);
        mExtraKeys = new TerminalExtraKeys(findViewById(R.id.terminalExtraKeys), mTerminalView);
        content.addView(new FloatingMenuBall(this, content, "menu_ball",
            () -> mDrawer.openDrawer(GravityCompat.START)));
        NavDrawer.bind(this, mDrawer, new NavDrawer.Callbacks() {
            @Override public void onHomeSelected() { NavDrawer.goHome(TerminalActivity.this); }
            @Override public void onTerminalSelected() { /* Current page. */ }
            @Override public void onWebSelected() {
                startActivity(new Intent(TerminalActivity.this, WebActivity.class));
            }
        });

        prepareEnv();

        if (sBridge == null) sBridge = new ClientBridge();
        sBridge.activity = this;

        if (sSession == null || !sSession.isRunning()) {
            sSession = createSession();
        }
        mTerminalView.attachSession(sSession);
        // Ensure sizing and rendering are ready after the first layout; do not fake a prompt by injecting Enter.
        mTerminalView.post(() -> {
            if (isFinishing() || isDestroyed()) return;
            mTerminalView.updateSize();
            mTerminalView.onScreenUpdated();
        });
        mTerminalView.requestFocus();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (sBridge != null) sBridge.activity = this;
        if (AppSettings.keepScreenOn(this)) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        applyTerminalSize();
        // A reused Activity may still display an exited session. Returning to the
        // page must apply the new backend preference rather than attach dead PTY.
        if (sSession == null) {
            sSession = createSession();
            mTerminalView.attachSession(sSession);
            mTerminalView.updateSize();
            mTerminalView.onScreenUpdated();
        }
    }

    private void applyTerminalSize() {
        mTerminalView.setTextSize(Math.round(AppSettings.terminalSize(this)
            * getResources().getDisplayMetrics().scaledDensity));
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        // Keep the session alive when leaving (Termux-style); reattach on return.
        if (sBridge != null && sBridge.activity == this) sBridge.activity = null;
    }

    /** Generate separate read-only startup profiles for system sh and Bash without overwriting the user's ~/.bashrc. */
    private void prepareEnv() {
        File files = getFilesDir();
        try { mRuntimeRoot = ServeManager.prepareRuntime(this); }
        catch (java.io.IOException error) { mRuntimeError = "原生载荷初始化失败: " + error.getMessage(); }
        File home = new File(files, "home");
        File tmp = new File(files, "tmp");
        if (!home.isDirectory()) home.mkdirs();
        if (!tmp.isDirectory()) tmp.mkdirs();

        ServeManager.Paths p = ServeManager.resolvePaths(this);
        StringBuilder sb = new StringBuilder();
        sb.append("# andcode terminal profile\n");
        // Print one-time output before sourcing ~/.bashrc. The bootstrap marks
        // ANDCODE_BASHRC before sourcing this profile again, so the nested load
        // suppresses duplicate startup output.
        sb.append("if [ -z \"${ANDCODE_BASHRC:-}\" ]; then\n");
        sb.append("cat <<'ANDCODE_BANNER'\n")
           .append(buildBanner())
           .append("ANDCODE_BANNER\n");
        sb.append("printf '%s\\n' 'Ubuntu dev instance: andcode-ubuntu-proot [proxy=<url>]; errors out if missing.'\n");
        sb.append("fi\n");
        sb.append("if [ -n \"${BASH_VERSION:-}\" ]; then\n");
        sb.append("  PS1='\\W \\$ '; HISTFILE=\"$HOME/.bash_history\"\n");
        sb.append("  shopt -s checkwinsize\n");
        // ANDCODE_BASHRC set means this profile is being sourced from ~/.bashrc;
        // skip sourcing back to avoid infinite recursion.
        sb.append("  [ -n \"$ANDCODE_BASHRC\" ] || [ ! -r \"$HOME/.bashrc\" ] || . \"$HOME/.bashrc\"\n");
        sb.append("else\n");
        sb.append("  [ ! -r /system/etc/mkshrc ] || . /system/etc/mkshrc\n");
        sb.append("  PS1='$PWD $ '\n");
        sb.append("  printf '%s\\n' 'Bash payload not installed; using the system sh.'\n");
        sb.append("fi\n");
        if (mRuntimeRoot != null)
            sb.append("export ANDCODE_RUNTIME_ROOT=\"").append(mRuntimeRoot.getAbsolutePath()).append("\"\n");
        // Shell function, not an executable: app data dirs forbid exec (targetSdk 37.2);
        // loader/oc2 live in nativeLibraryDir or /data/local/tmp where exec is allowed.
        // Connect via --server when the managed serve is online (self-spawn breaks
        // under loader semantics, see DESIGN v0.4.49).
        if (p != null) {
            sb.append("opencode() {\n");
            sb.append("  srv=''\n");
            sb.append("  if [ -r \"$ANDCODE_APP_DATA/term-serve.env\" ] && /system/bin/toybox nc -w1 127.0.0.1 4096 </dev/null >/dev/null 2>&1; then\n");
            sb.append("    . \"$ANDCODE_APP_DATA/term-serve.env\"\n");
            sb.append("    export OPENCODE_PASSWORD\n");
            sb.append("    srv=\"--server $OPENCODE_SERVER_URL\"\n");
            sb.append("  fi\n");
            sb.append("  export LD_LIBRARY_PATH=\"${ANDCODE_RUNTIME_ROOT:-}/lib:").append(p.lib).append("\"\n");
            sb.append("  export TMPDIR=\"$ANDCODE_APP_DATA/tmp\" BUN_TMPDIR=\"$ANDCODE_APP_DATA/tmp\"\n");
            sb.append("  GLIBC_TUNABLES=glibc.pthread.rseq=0 \"").append(p.ld)
              .append("\" --library-path \"${ANDCODE_RUNTIME_ROOT:-}/lib:").append(p.lib)
              .append("\" --inhibit-cache \"").append(p.oc2).append("\" \"$@\" $srv\n");
            sb.append("}\n");
        }
        sb.append("andcode-ubuntu-proot() { /system/bin/sh \"$ANDCODE_APP_DATA/term-ubuntu-proot\" \"$@\"; }\n");
        prepareUbuntuProot(files);
        writeFile(new File(files, "term-env.sh"), sb.toString());
        writeFile(new File(files, "term-bashrc"), sb.toString());
        // Interactive bash only reads ~/.bashrc (never ENV); create a bootstrap file when
        // missing so the opencode() function applies to bash sessions too. Never overwrite
        // a user-provided file. ANDCODE_BASHRC=1 lets the profile skip sourcing back,
        // preventing infinite .bashrc <-> profile recursion.
        File bashrc = new File(home, ".bashrc");
        String bashrcWanted = "ANDCODE_BASHRC=1\n"
            + "[ -r \"$ANDCODE_APP_DATA/term-bashrc\" ] && . \"$ANDCODE_APP_DATA/term-bashrc\"\n";
        // The early unguarded v0.4.49 template recursed with the profile; replace it on sight.
        String bashrcLegacy = "[ -r \"$ANDCODE_APP_DATA/term-bashrc\" ] && . \"$ANDCODE_APP_DATA/term-bashrc\"\n";
        if (!bashrc.exists() || bashrcLegacy.equals(readSmallFile(bashrc))) {
            writeFile(bashrc, bashrcWanted);
        }
    }

    /** Armbian-style banner: ASCII art and device information; all terminal prompts are in English. */
    private String buildBanner() {
        StringBuilder b = new StringBuilder();
        b.append("\n");
        b.append("\n");
        b.append(" ####  ####   ##   #  #  #  #  ####\n");
        b.append("#   # # # # #   # #     #  # #   # #\n");
        b.append("##### #  ## #   # #     #  # #   # ####\n");
        b.append("#   # #   # #   # #     #  # #   # #\n");
        b.append("#   #  ####   #   #  ###  #  #  ####\n");
        b.append(" andcode · opencode AI coding agent on Android\n");
        b.append("\n");
        b.append(" Android ").append(android.os.Build.VERSION.RELEASE)
          .append(" (SDK ").append(android.os.Build.VERSION.SDK_INT)
          .append(") · ").append(android.os.Build.MODEL.substring(0,
              Math.min(24, android.os.Build.MODEL.length()))).append("\n");
        b.append(" Linux ").append(System.getProperty("os.version", ""))
          .append("\n");
        long memTotal = 0, memAvail = 0;
        try (java.io.BufferedReader r = new java.io.BufferedReader(
                new java.io.FileReader("/proc/meminfo"))) {
            String line;
            while ((line = r.readLine()) != null) {
                if (line.startsWith("MemTotal:"))
                    memTotal = Long.parseLong(line.replaceAll("[^0-9]", ""));
                if (line.startsWith("MemAvailable:"))
                    memAvail = Long.parseLong(line.replaceAll("[^0-9]", ""));
            }
        } catch (Exception ignored) {
        }
        if (memTotal > 0) {
            b.append(" Memory: ").append(memTotal / 1048576).append(" GB total / ")
              .append(memAvail / 1048576).append(" GB available\n");
        }
        long free = getFilesDir().getUsableSpace();
        b.append(" Storage free: ")
          .append(String.format(java.util.Locale.US, "%.1f", free / 1073741824.0))
          .append(" GB\n");
        b.append("\n");
        b.append(" Type opencode to start the AI coding agent.\n");
        b.append("\n");
        return b.toString();
    }

    /** Interpret the script only: no su, relabeling, automatic download/extraction, or model access to privileged maintenance. */
    private void prepareUbuntuProot(File files) {
        try (InputStream in = getAssets().open("term-ubuntu-proot.sh");
             OutputStream out = new FileOutputStream(new File(files, "term-ubuntu-proot"))) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = in.read(buffer)) != -1) out.write(buffer, 0, count);
        } catch (java.io.IOException error) {
            throw new IllegalStateException("无法准备 Ubuntu 启动入口", error);
        }
    }

    private TerminalSession createSession() {
        File files = getFilesDir();
        File home = new File(files, "home");
        ServeManager.Paths p = ServeManager.resolvePaths(this);

        // PATH: prepend the bundle deployment when present (git/ssh etc.); otherwise use system paths only.
        StringBuilder path = new StringBuilder("/system/bin:/system/xbin");
        String[] bundleBins = {"/data/local/tmp/andcode/usr/bin", "/data/local/tmp/andcode/bin"};
        if (mRuntimeRoot != null) {
            path.insert(0, mRuntimeRoot + "/bin:" + mRuntimeRoot + "/usr/bin:");
        } else if (mRuntimeError == null) {
            for (String b : bundleBins) {
                if (new File(b).isDirectory()) path.insert(0, b + ":");
            }
        }

        List<String> env = new ArrayList<>(List.of(
            "HOME=" + home.getAbsolutePath(),
            "PATH=" + path,
            "TERM=xterm-256color",
            "GLIBC_TUNABLES=glibc.pthread.rseq=0",
            "LANG=en_US.UTF-8",
            "TMPDIR=" + new File(files, "tmp").getAbsolutePath(),
            "BUN_TMPDIR=" + new File(files, "tmp").getAbsolutePath(), // Bun native library extraction directory.
            "ENV=" + new File(files, "term-env.sh").getAbsolutePath(),
            "ANDCODE_APP_DATA=" + files.getAbsolutePath(),
            "ANDCODE_TIER=p"));
        if (mRuntimeRoot != null) {
            String nat = getApplicationInfo().nativeLibraryDir;
            env.add("ANDCODE_ROOT=" + mRuntimeRoot.getAbsolutePath());
            env.add("ANDCODE_EXE_DIR=" + nat);
            env.add("ANDCODE_LOADER=" + nat + "/libandcode-ld-linux.so");
            env.add("ANDCODE_LIBPATH=" + nat);
            env.add("GIT_EXEC_PATH=" + mRuntimeRoot + "/usr/libexec/git-core");
            env.add("LD_LIBRARY_PATH=" + nat);
        }
        if (p != null) {
            // Library resolution for glibc children (opencode-pty, git, etc.); filenames do not conflict with bionic.
            env.add("LD_LIBRARY_PATH=" + p.lib);
            // Point to the plugin binary (see comments in ServeManager.spawn):
            // opencode TUI running in the terminal also spawns opencode-pty.
            String ptyBin = ServeManager.ptyBinPath(this);
            if (ptyBin != null) env.add("OPENCODE_PTY_BIN=" + ptyBin);
            env.add("OPENCODE_PTY_SOCKET_DIR=" + ServeManager.ptySocketDir(this));
        }

        String[] command = bashCommand(files);
        // SHELL executed directly by children still needs a valid PT_INTERP; Bash requires an explicit loader.
        // The default interactive session starts Bash via command, without exposing a bare glibc ELF to children.
        env.add("SHELL=/system/bin/sh");
        if (command == null) command = new String[]{"/system/bin/sh", "-i"};
        File selected = AppSettings.selectedProject(this);
        // Preserve a stale/invalid selection for launcher validation rather than
        // silently losing the requested project and executing from guest /root.
        String projectName = AppSettings.prefs(this).getString("selected-project", "");
        if (projectName != null && !projectName.isEmpty())
            env.add("ANDCODE_UBUNTU_PROJECT_NAME=" + projectName);
        if (AppSettings.ubuntuTerminal(this)) {
            // Single APK: extract a missing instance in the background; the session waits for the digest marker.
            // Development builds without a bundled archive report a launcher error rather than silently switching environments.
            List<String> ubuntu = new ArrayList<>(List.of("/system/bin/sh",
                new File(files, "term-ubuntu-proot").getAbsolutePath()));
            if (AppSettings.ubuntuProxy(this)) {
                String proxyUrl = AppSettings.proxyUrl(this).trim();
                if (!proxyUrl.isEmpty()) ubuntu.add("proxy=" + proxyUrl);
            }
            if (!new File(files, "proot-rootfs/usr/bin/bash").isFile()) {
                boolean embedded = false;
                try {
                    getAssets().open("andcode-rootfs/andcode-rootfs-arm64.tgz.sha256").close();
                    embedded = true;
                } catch (java.io.IOException ignored) {
                }
                if (embedded) {
                    ubuntu.add("wait-install");
                    RootfsInstaller.logger = m ->
                        android.util.Log.i("andcode", "rootfs: " + m);
                    new Thread(() -> {
                        try {
                            RootfsInstaller.install(files.toPath(),
                                getAssets()::open, null);
                        } catch (Exception e) {
                            android.util.Log.e("andcode",
                                "terminal rootfs install failed", e);
                        }
                    }, "terminal-rootfs-install").start();
                }
            }
            command = ubuntu.toArray(new String[0]);
            selected = null; // Host cwd is not the guest cwd; launcher owns the binding.
        }
        if (mRuntimeError != null) {
            // Print through argv, never interpolate an error into shell source.
            command = new String[]{"/system/bin/sh", "-c", "printf '%s\\n' \"$1\" >&2; exit 1",
                "andcode", mRuntimeError};
        }
        return new TerminalSession(
            command[0],
            selected != null ? selected.getAbsolutePath() : home.getAbsolutePath(),
            command,
            env.toArray(new String[0]),
            null,
            sBridge
        );
    }

    /** No filesDir ELF execution or third-party host lookup; the patched loader explicitly starts bundled Bash. */
    private String[] bashCommand(File files) {
        String nat = getApplicationInfo().nativeLibraryDir;
        String[][] candidates = {
            {nat + "/libandcode-ld-linux.so", nat, nat + "/libandcode-bash.so"},
            {nat + "/libandcode-loader.so", nat, nat + "/libandcode-bash.so"},
            {"/data/local/tmp/andcode/lib/ld-linux-aarch64.so.1",
                "/data/local/tmp/andcode/lib", "/data/local/tmp/andcode/bin/bash.bin"}
        };
        for (String[] candidate : candidates) {
            if (mRuntimeRoot != null && !candidate[0].equals(nat + "/libandcode-ld-linux.so")) continue;
            if (new File(candidate[0]).isFile() && new File(candidate[2]).isFile())
                return new String[]{candidate[0], "--library-path", candidate[1], "--inhibit-cache",
                    candidate[2], "--noprofile", "--rcfile", new File(files, "term-bashrc").getAbsolutePath(), "-i"};
        }
        return null;
    }

    private static void writeFile(File dst, String text) {
        try (OutputStream out = new FileOutputStream(dst)) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {
        }
    }

    /** Reads a small file fully; returns an empty string on failure (treated as content mismatch). */
    private static String readSmallFile(File src) {
        try (java.io.InputStream in = new java.io.FileInputStream(src)) {
            java.io.ByteArrayOutputStream buf = new java.io.ByteArrayOutputStream();
            byte[] chunk = new byte[4096];
            int n;
            while ((n = in.read(chunk)) != -1) buf.write(chunk, 0, n);
            return new String(buf.toByteArray(), StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            return "";
        }
    }

    /**
     * Static session callback bridge: TerminalSession retains its original client while navigation
     * recreates Activities. Rebind only the current foreground instance, without recreating the session.
     */
    private static class ClientBridge implements TerminalSessionClient {
        TerminalActivity activity;

        @Override public void onTextChanged(@NonNull TerminalSession s) {
            TerminalActivity a = activity;
            if (a != null) a.runOnUiThread(a.mTerminalView::onScreenUpdated);
        }
        @Override public void onTitleChanged(@NonNull TerminalSession s) {
            TerminalActivity a = activity;
            if (a != null) a.runOnUiThread(() -> a.setTitle(s.getTitle()));
        }
        @Override public void onSessionFinished(@NonNull TerminalSession s) {
            if (s == sSession) sSession = null; // Create a new session on the next visit.
            TerminalActivity a = activity;
            if (a != null) a.runOnUiThread(() -> Toast.makeText(a,
                "会话结束(exit " + s.getExitStatus() + ")", Toast.LENGTH_LONG).show());
        }
        @Override public void onCopyTextToClipboard(@NonNull TerminalSession s, String text) {
            TerminalActivity a = activity;
            if (a == null) return;
            ClipboardManager cm = (ClipboardManager) a.getSystemService(Context.CLIPBOARD_SERVICE);
            cm.setPrimaryClip(new ClipData("andcode", new String[]{"text/plain"},
                new ClipData.Item(text)));
        }
        @Override public void onPasteTextFromClipboard(@Nullable TerminalSession s) {
            TerminalActivity a = activity;
            if (a == null || s == null) return;
            ClipData cd = a.getSystemService(ClipboardManager.class).getPrimaryClip();
            if (cd != null && cd.getItemCount() > 0) {
                CharSequence text = cd.getItemAt(0).getText();
                if (text != null) {
                    byte[] b = text.toString().getBytes();
                    s.write(b, 0, b.length);
                }
            }
        }
        @Override public void onBell(@NonNull TerminalSession s) { }
        @Override public void onColorsChanged(@NonNull TerminalSession s) {
            TerminalActivity a = activity;
            if (a != null) a.runOnUiThread(a.mTerminalView::onScreenUpdated);
        }
        @Override public void onTerminalCursorStateChange(boolean state) { }
        @Override public void setTerminalShellPid(@NonNull TerminalSession s, int pid) { }
        @Override public Integer getTerminalCursorStyle() {
            return TerminalEmulator.DEFAULT_TERMINAL_CURSOR_STYLE;
        }
        @Override public void logError(String tag, String message) { }
        @Override public void logWarn(String tag, String message) { }
        @Override public void logInfo(String tag, String message) { }
        @Override public void logDebug(String tag, String message) { }
        @Override public void logVerbose(String tag, String message) { }
        @Override public void logStackTraceWithMessage(String tag, String message, Exception e) { }
        @Override public void logStackTrace(String tag, Exception e) { }
    }

    /** Minimal, lightweight TerminalViewClient implementation, one per Activity. */
    private class ViewClient implements TerminalViewClient {
        @Override public float onScale(float scale) {
            // TerminalView accumulates scale; adjust by 1 sp past the threshold, then reset to avoid jitter.
            if (scale > 1.1f || scale < 0.9f) {
                int current = AppSettings.terminalSize(TerminalActivity.this);
                int next = Math.max(10, Math.min(28, current + (scale > 1f ? 1 : -1)));
                if (next != current) {
                    AppSettings.prefs(TerminalActivity.this).edit().putInt("terminal-size", next).apply();
                    applyTerminalSize();
                }
                // Reset at the bounds too, so reverse gestures need not cancel the previously accumulated scale.
                return 1f;
            }
            return scale;
        }
        @Override public void onSingleTapUp(MotionEvent e) {
            if (mTerminalView.requestFocus()) {
                // The custom-drawn TerminalView is not an EditText; focus does not automatically show the IME.
                // Let focus/InputConnection take effect, then explicitly request the keyboard for the user's tap.
                mTerminalView.post(() -> {
                    if (isFinishing() || isDestroyed() || !mTerminalView.hasWindowFocus()) return;
                    InputMethodManager imm = getSystemService(InputMethodManager.class);
                    if (imm != null) imm.showSoftInput(mTerminalView, InputMethodManager.SHOW_IMPLICIT);
                });
            }
        }
        @Override public boolean shouldBackButtonBeMappedToEscape() { return false; }
        @Override public boolean shouldEnforceCharBasedInput() { return true; }
        @Override public boolean shouldUseCtrlSpaceWorkaround() { return true; }
        @Override public boolean isTerminalViewSelected() { return true; }
        @Override public void copyModeChanged(boolean copyMode) { }
        @Override public boolean onKeyDown(int keyCode, KeyEvent e, TerminalSession session) {
            if (keyCode == KeyEvent.KEYCODE_ENTER && !session.isRunning()) {
                sSession = createSession();
                mTerminalView.attachSession(sSession);
                mTerminalView.updateSize();
                mTerminalView.onScreenUpdated();
                return true;
            }
            return false;
        }
        @Override public boolean onKeyUp(int keyCode, KeyEvent e) { return false; }
        @Override public boolean onLongPress(MotionEvent event) { return false; }
        @Override public boolean readControlKey() { return mExtraKeys != null && mExtraKeys.controlDown(); }
        @Override public boolean readAltKey() { return mExtraKeys != null && mExtraKeys.altDown(); }
        @Override public boolean readShiftKey() { return false; }
        @Override public boolean readFnKey() { return false; }
        @Override public boolean onCodePoint(int codePoint, boolean ctrlDown, TerminalSession session) { return false; }
        @Override public void onEmulatorSet() { mTerminalView.onScreenUpdated(); }
        @Override public void logError(String tag, String message) { }
        @Override public void logWarn(String tag, String message) { }
        @Override public void logInfo(String tag, String message) { }
        @Override public void logDebug(String tag, String message) { }
        @Override public void logVerbose(String tag, String message) { }
        @Override public void logStackTraceWithMessage(String tag, String message, Exception e) { }
        @Override public void logStackTrace(String tag, Exception e) { }
    }
}
