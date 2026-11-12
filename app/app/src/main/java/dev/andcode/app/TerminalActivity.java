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
 * 终端页(Termux 式):打开交互式 shell,不自动拉起 opencode TUI——
 * 用户输入 `opencode` 即进入 AI 编码代理(ENV profile 提供 shell 函数,
 * 经补丁 loader 执行,规避应用域 seccomp / 数据目录禁 exec 约束)。
 *
 * - 会话持久化:TerminalSession 存静态引用,离开页面不杀进程,返回页面
 *   重新挂载;进程被系统回收时会话自然结束,下次进入自动新建。
 *   (SessionService 前台服务保活进程,会话通常全程存活。)
 * - 悬浮球 + 共享抽屉(与 WebActivity 同款,andapi 模式)。
 * - 依赖 ServeManager 同一套二进制解析(jniLibs 优先,/data/local/tmp 回退);
 *   无部署时仍是可用的普通 shell。
 */
public class TerminalActivity extends AppCompatActivity {

    /** 跨页面保持的终端会话(静态 = 应用进程生命周期) */
    private static TerminalSession sSession;
    /** 回调桥:会话常驻而 Activity 会重建,回调始终委托给前台实例 */
    private static ClientBridge sBridge;

    private TerminalView mTerminalView;
    private DrawerLayout mDrawer;
    private TerminalExtraKeys mExtraKeys;
    private File mRuntimeRoot;
    private String mRuntimeError;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setContentView(R.layout.activity_terminal);
        mTerminalView = findViewById(R.id.terminal_view);
        // attachSession 可能在已布局的 View 上立即初始化模拟器,先绑定 client。
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

        // 悬浮抽屉球(与 WebActivity 共用停靠位置)
        FrameLayout content = findViewById(R.id.termContent);
        androidx.core.view.ViewCompat.setOnApplyWindowInsetsListener(content, (view, insets) -> {
            androidx.core.graphics.Insets bars = insets.getInsets(
                androidx.core.view.WindowInsetsCompat.Type.systemBars()
                    | androidx.core.view.WindowInsetsCompat.Type.displayCutout());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });
        mExtraKeys = new TerminalExtraKeys(findViewById(R.id.terminalExtraKeys), mTerminalView);
        content.addView(new FloatingMenuBall(this, content, "menu_ball",
            () -> mDrawer.openDrawer(GravityCompat.START)));
        NavDrawer.bind(this, mDrawer, new NavDrawer.Callbacks() {
            @Override public void onHomeSelected() { NavDrawer.goHome(TerminalActivity.this); }
            @Override public void onTerminalSelected() { /* 当前页 */ }
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
        // 首帧布局完成后确保尺寸与绘制已就绪,不通过注入回车伪造提示符。
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
        // 不杀会话:离开页面(Termux 式)进程继续运行,返回时重挂
        if (sBridge != null && sBridge.activity == this) sBridge.activity = null;
    }

    /** 分别生成系统 sh 和 Bash 的只读启动配置,不覆盖用户 ~/.bashrc。 */
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
        sb.append("if [ -n \"${BASH_VERSION:-}\" ]; then\n");
        sb.append("  PS1='\\W \\$ '; HISTFILE=\"$HOME/.bash_history\"\n");
        sb.append("  shopt -s checkwinsize\n");
        // ANDCODE_BASHRC set means this profile is being sourced from ~/.bashrc;
        // skip sourcing back to avoid infinite recursion.
        sb.append("  [ -n \"$ANDCODE_BASHRC\" ] || [ ! -r \"$HOME/.bashrc\" ] || . \"$HOME/.bashrc\"\n");
        sb.append("else\n");
        sb.append("  [ ! -r /system/etc/mkshrc ] || . /system/etc/mkshrc\n");
        sb.append("  PS1='$PWD $ '\n");
        sb.append("  printf '%s\\n' 'Bash 未部署，当前使用系统 sh。'\n");
        sb.append("fi\n");
        sb.append("printf '%s\\n' 'andcode 终端 · 输入 opencode 启动 AI 编码代理'\n");
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
        sb.append("printf '%s\\n' 'Ubuntu 开发实例：andcode-ubuntu-proot [loopback-proxy]；未安装时明确报错。'\n");
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

    /** 只解释脚本;不 su、不 relabel、不自动下载/解包、不把模型接入特权维护入口。 */
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

        // PATH:bundle 部署存在则前置(git/ssh 等),否则纯系统
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
            "BUN_TMPDIR=" + new File(files, "tmp").getAbsolutePath(), // Bun 原生库提取目录
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
            // glibc 子进程(opencode-pty、git 等)的库解析;文件名与 bionic 不冲突
            env.add("LD_LIBRARY_PATH=" + p.lib);
            // 插件二进制指路(见 ServeManager.spawn 内注释):
            // 终端里跑的 opencode TUI 自身也会 spawn opencode-pty
            String ptyBin = ServeManager.ptyBinPath(this);
            if (ptyBin != null) env.add("OPENCODE_PTY_BIN=" + ptyBin);
            env.add("OPENCODE_PTY_SOCKET_DIR=" + ServeManager.ptySocketDir(this));
        }

        String[] command = bashCommand(files);
        // 子进程直接 exec 的 SHELL 仍需可用的 PT_INTERP;Bash 本体依赖显式 loader。
        // 默认交互会话用 command 拉起 Bash,不把裸 glibc ELF 暴露给子进程。
        env.add("SHELL=/system/bin/sh");
        if (command == null) command = new String[]{"/system/bin/sh", "-i"};
        File selected = AppSettings.selectedProject(this);
        // Preserve a stale/invalid selection for launcher validation rather than
        // silently losing the requested project and executing from guest /root.
        String projectName = AppSettings.prefs(this).getString("selected-project", "");
        if (projectName != null && !projectName.isEmpty())
            env.add("ANDCODE_UBUNTU_PROJECT_NAME=" + projectName);
        if (AppSettings.ubuntuTerminal(this)) {
            // 单 APK:实例缺失时后台提取,会话内等待 digest 标记后进入;无内置
            // 归档的开发构建仍由启动器显式报错,不静默换环境。
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

    /** 不执行 filesDir ELF、不查找第三方宿主;补丁 loader 显式拉起预置 Bash。 */
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
     * 会话回调桥(静态):TerminalSession 持有构造时的 client,而 Activity
     * 随导航反复重建——桥只持有"当前前台实例",重建时换绑,会话无需重建。
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
            if (s == sSession) sSession = null; // 下次进入自动新建
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

    /** TerminalViewClient 最小实现(每 Activity 一份,轻量) */
    private class ViewClient implements TerminalViewClient {
        @Override public float onScale(float scale) {
            // TerminalView 累积缩放比例;越过阈值调整 1 sp 后重置,避免抖动。
            if (scale > 1.1f || scale < 0.9f) {
                int current = AppSettings.terminalSize(TerminalActivity.this);
                int next = Math.max(10, Math.min(28, current + (scale > 1f ? 1 : -1)));
                if (next != current) {
                    AppSettings.prefs(TerminalActivity.this).edit().putInt("terminal-size", next).apply();
                    applyTerminalSize();
                }
                // 到达边界也重置,反向手势无需抵消先前累计的比例。
                return 1f;
            }
            return scale;
        }
        @Override public void onSingleTapUp(MotionEvent e) {
            if (mTerminalView.requestFocus()) {
                // 自绘 TerminalView 不是 EditText:获得焦点不会自动显示输入法。
                // 先让焦点/InputConnection 生效,再按用户点击明确请求显示。
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
