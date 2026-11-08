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

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setContentView(R.layout.activity_terminal);
        mTerminalView = findViewById(R.id.terminal_view);
        mTerminalView.setTextSize(30);
        mDrawer = findViewById(R.id.rootDrawer);

        // 悬浮抽屉球(与 WebActivity 共用停靠位置)
        FrameLayout content = findViewById(R.id.termContent);
        content.addView(new FloatingMenuBall(this, content, "menu_ball",
            () -> mDrawer.openDrawer(GravityCompat.START)));
        NavDrawer.bind(this, mDrawer, new NavDrawer.Callbacks() {
            @Override public void onHomeSelected() { finish(); }
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
        mTerminalView.setTerminalViewClient(new ViewClient());
        mTerminalView.requestFocus();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        // 不杀会话:离开页面(Termux 式)进程继续运行,返回时重挂
        if (sBridge != null && sBridge.activity == this) sBridge.activity = null;
    }

    @Override
    public void onBackPressed() {
        if (mDrawer != null && mDrawer.isDrawerOpen(GravityCompat.START)) {
            mDrawer.closeDrawer(GravityCompat.START);
        } else {
            super.onBackPressed();
        }
    }

    /** 建 home/tmp 目录并生成 ENV profile(交互 shell 启动时被 mksh source) */
    private void prepareEnv() {
        File files = getFilesDir();
        File home = new File(files, "home");
        File tmp = new File(files, "tmp");
        if (!home.isDirectory()) home.mkdirs();
        if (!tmp.isDirectory()) tmp.mkdirs();

        ServeManager.Paths p = ServeManager.resolvePaths(this);
        if (p == null) return; // 无 glibc 部署:纯系统 shell 仍可用

        StringBuilder sb = new StringBuilder();
        sb.append("# andcode 终端 profile(mksh 交互 shell 启动时 source)\n");
        sb.append("cd \"$HOME\" 2>/dev/null\n");
        sb.append("echo 'andcode 终端 · 输入 opencode 启动 AI 编码代理'\n");
        // shell 函数而非可执行文件:应用数据目录禁 exec(targetSdk 37.2),
        // loader/oc2 在 nativeLibraryDir 或 /data/local/tmp,exec 放行
        sb.append("opencode() {\n");
        sb.append("  GLIBC_TUNABLES=glibc.pthread.rseq=0 exec \"").append(p.ld)
          .append("\" --library-path \"").append(p.lib)
          .append("\" --inhibit-cache \"").append(p.oc2).append("\" \"$@\"\n");
        sb.append("}\n");
        writeFile(new File(files, "term-env.sh"), sb.toString());
    }

    private TerminalSession createSession() {
        File files = getFilesDir();
        File home = new File(files, "home");
        ServeManager.Paths p = ServeManager.resolvePaths(this);

        // PATH:bundle 部署存在则前置(git/ssh 等),否则纯系统
        StringBuilder path = new StringBuilder("/system/bin:/system/xbin");
        String[] bundleBins = {"/data/local/tmp/andcode/usr/bin", "/data/local/tmp/andcode/bin"};
        for (String b : bundleBins) {
            if (new File(b).isDirectory()) path.insert(0, b + ":");
        }

        List<String> env = new ArrayList<>(List.of(
            "HOME=" + home.getAbsolutePath(),
            "PATH=" + path,
            "TERM=xterm-256color",
            "LANG=en_US.UTF-8",
            "TMPDIR=" + new File(files, "tmp").getAbsolutePath(),
            "BUN_TMPDIR=" + new File(files, "tmp").getAbsolutePath(), // Bun 原生库提取目录
            "ENV=" + new File(files, "term-env.sh").getAbsolutePath(),
            "ANDCODE_APP_DATA=" + files.getAbsolutePath(),
            "ANDCODE_TIER=p",
            "HTTP_PROXY=http://127.0.0.1:7890",   // 模型 API 走设备代理
            "HTTPS_PROXY=http://127.0.0.1:7890",
            "NODE_TLS_REJECT_UNAUTHORIZED=0"));
        if (p != null) {
            // glibc 子进程(opencode-pty、git 等)的库解析;文件名与 bionic 不冲突
            env.add("LD_LIBRARY_PATH=" + p.lib);
        }

        return new TerminalSession(
            "/system/bin/sh",
            home.getAbsolutePath(),
            new String[]{"/system/bin/sh"},
            env.toArray(new String[0]),
            null,
            sBridge
        );
    }

    private static void writeFile(File dst, String text) {
        try (OutputStream out = new FileOutputStream(dst)) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {
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
        @Override public float onScale(float scale) { return scale; }
        @Override public void onSingleTapUp(MotionEvent e) {
            mTerminalView.requestFocus();
        }
        @Override public boolean shouldBackButtonBeMappedToEscape() { return false; }
        @Override public boolean shouldEnforceCharBasedInput() { return true; }
        @Override public boolean shouldUseCtrlSpaceWorkaround() { return true; }
        @Override public boolean isTerminalViewSelected() { return true; }
        @Override public void copyModeChanged(boolean copyMode) { }
        @Override public boolean onKeyDown(int keyCode, KeyEvent e, TerminalSession session) { return false; }
        @Override public boolean onKeyUp(int keyCode, KeyEvent e) { return false; }
        @Override public boolean onLongPress(MotionEvent event) { return false; }
        @Override public boolean readControlKey() { return false; }
        @Override public boolean readAltKey() { return false; }
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
