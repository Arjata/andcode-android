package dev.andcode.app;

import android.annotation.SuppressLint;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.LayoutInflater;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.termux.terminal.TerminalEmulator;
import com.termux.terminal.TerminalSession;
import com.termux.terminal.TerminalSessionClient;
import com.termux.view.TerminalView;
import com.termux.view.TerminalViewClient;

import java.io.File;

/**
 * Tier P MVP: 内嵌终端承载 opencode TUI。
 * 会话命令: andcode-entry shell(bundle 部署于 /data/local/tmp/andcode 时)
 * 回退:      /system/bin/sh
 */
public class MainActivity extends AppCompatActivity {

    private static final String BUNDLE_ROOT = "/data/local/tmp/andcode";
    private TerminalView mTerminalView;
    private TerminalSession mSession;

    @Override
    @SuppressLint("SetJavaScriptEnabled")
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setContentView(R.layout.activity_main);
        mTerminalView = findViewById(R.id.terminal_view);

        String entry = BUNDLE_ROOT + "/sbin/andcode-entry";
        String shellCmd;
        if (new File(entry).exists()) {
            shellCmd = "exec " + entry + " shell";
        } else {
            Toast.makeText(this, "bundle 未部署(adb 推送),回退普通 shell", Toast.LENGTH_LONG).show();
            shellCmd = "echo 'andcode bundle not deployed; plain shell fallback'";
        }

        String[] env = {
            "HOME=" + getFilesDir().getAbsolutePath(),
            "PATH=/system/bin:/system/xbin",
            "TERM=xterm-256color",
            "LANG=en_US.UTF-8"
        };

        mSession = new TerminalSession(
            "/system/bin/sh",
            getFilesDir().getAbsolutePath(),
            new String[]{"/system/bin/sh", "-c", shellCmd},
            env,
            null,
            new TerminalClient()
        );
        mTerminalView.attachSession(mSession);
        mTerminalView.setTerminalViewClient(new ViewClient());
        mTerminalView.requestFocus();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (mSession != null) mSession.finishIfRunning();
    }

    /** TerminalSessionClient 最小实现 */
    private class TerminalClient implements TerminalSessionClient {
        @Override public void onTextChanged(@NonNull TerminalSession changedSession) {
            runOnUiThread(() -> mTerminalView.onScreenUpdated());
        }
        @Override public void onTitleChanged(@NonNull TerminalSession changedSession) {
            runOnUiThread(() -> setTitle(changedSession.getTitle()));
        }
        @Override public void onSessionFinished(@NonNull TerminalSession finishedSession) {
            runOnUiThread(() -> Toast.makeText(MainActivity.this,
                "会话结束(exit " + finishedSession.getExitStatus() + ")", Toast.LENGTH_LONG).show());
        }
        @Override public void onCopyTextToClipboard(@NonNull TerminalSession session, String text) {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            cm.setPrimaryClip(new ClipData("andcode", new String[]{"text/plain"}, new ClipData.Item(text)));
        }
        @Override public void onPasteTextFromClipboard(@Nullable TerminalSession session) {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            ClipData cd = cm.getPrimaryClip();
            if (cd != null && cd.getItemCount() > 0) {
                CharSequence text = cd.getItemAt(0).getText();
                if (text != null) {
                    byte[] b = text.toString().getBytes();
                    mSession.write(b, 0, b.length);
                }
            }
        }
        @Override public void onBell(@NonNull TerminalSession session) { }
        @Override public void onColorsChanged(@NonNull TerminalSession session) {
            mTerminalView.onScreenUpdated();
        }
        @Override public void onTerminalCursorStateChange(boolean state) { }
        @Override public void setTerminalShellPid(@NonNull TerminalSession session, int pid) { }
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

    /** TerminalViewClient 最小实现 */
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
