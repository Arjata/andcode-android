package dev.andcode.app;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.ImageButton;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.drawerlayout.widget.DrawerLayout;

import com.google.android.material.button.MaterialButton;

/**
 * 主页仪表盘(布局对齐 andapi):服务状态卡(状态点/地址/启停)+ 双入口卡
 * (桌面 UI / TUI 终端),DrawerLayout 抽屉导航。状态每 2s 轮询刷新。
 */
public class HomeActivity extends AppCompatActivity {

    private View mStatusDot;
    private TextView mStatusText;
    private TextView mDetailText;
    private TextView mAddressText;
    private MaterialButton mStartButton;
    private MaterialButton mStopButton;
    private DrawerLayout mDrawer;

    /** 用户点了启动、尚未 ping 通的过渡态 */
    private boolean mWaitingStart;
    private boolean mPolling;

    private final Runnable mPoll = new Runnable() {
        @Override public void run() {
            ServeManager.pingAsync(up -> {
                render(up, null);
                if (mPolling) {
                    mStatusDot.postDelayed(this, 2000);
                }
            });
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);
        applyInsets();

        mStatusDot = findViewById(R.id.statusDot);
        mStatusText = findViewById(R.id.statusText);
        mDetailText = findViewById(R.id.detailText);
        mAddressText = findViewById(R.id.addressText);
        mStartButton = findViewById(R.id.startButton);
        mStopButton = findViewById(R.id.stopButton);
        mDrawer = findViewById(R.id.rootDrawer);

        ImageButton menuButton = findViewById(R.id.menuButton);
        menuButton.setOnClickListener(v -> mDrawer.openDrawer(androidx.core.view.GravityCompat.START));
        NavDrawer.bind(this, mDrawer, new NavDrawer.Callbacks() {
            @Override public void onHomeSelected() { /* already home */ }
            @Override public void onTerminalSelected() {
                startActivity(new Intent(HomeActivity.this, TerminalActivity.class));
            }
            @Override public void onWebSelected() {
                startActivity(new Intent(HomeActivity.this, WebActivity.class));
            }
        });

        mStartButton.setOnClickListener(v -> requestStart());
        mStopButton.setOnClickListener(v -> {
            mWaitingStart = false;
            ServeManager.stop(this);
            render(false, null);
        });

        findViewById(R.id.webButton).setOnClickListener(v ->
            startActivity(new Intent(this, WebActivity.class)));
        findViewById(R.id.terminalButton).setOnClickListener(v ->
            startActivity(new Intent(this, TerminalActivity.class)));

        render(false, null);
    }

    /** edge-to-edge:内容避开状态栏/键盘/导航栏(andapi 同款处理) */
    private void applyInsets() {
        View root = findViewById(R.id.rootScroll);
        ViewCompat.setOnApplyWindowInsetsListener(root, (view, insets) -> {
            androidx.core.graphics.Insets bars = insets.getInsets(
                WindowInsetsCompat.Type.statusBars() | WindowInsetsCompat.Type.displayCutout());
            int bottom = Math.max(
                insets.getInsets(WindowInsetsCompat.Type.ime()).bottom,
                insets.getInsets(WindowInsetsCompat.Type.navigationBars()).bottom);
            view.setPadding(bars.left, bars.top, bars.right, bottom);
            return insets;
        });
    }

    /** 启动 serve:走 SessionService FGS 承接常驻,再确保进程拉起 */
    private void requestStart() {
        mWaitingStart = true;
        render(null, getString(R.string.state_starting));
        startForegroundService(new Intent(this, SessionService.class));
        ServeManager.ensureStarted(this, new ServeManager.ReadyCallback() {
            @Override public void onReady(String password) {
                mWaitingStart = false;
                render(true, null);
            }
            @Override public void onFailed(String reason) {
                mWaitingStart = false;
                render(false, reason);
            }
        });
    }

    /**
     * 渲染状态。up 为 null 表示只更新文案(过渡态),不改变状态点。
     * 传入非 null 时:绿=运行,灰=停止;detail 非空时以错误色显示。
     */
    private void render(Boolean up, String detail) {
        if (up == null) {
            mStatusText.setText(detail != null ? detail : getString(R.string.state_stopped));
            mDetailText.setText(detail == null ? "" : getString(R.string.detail_prefix) + detail);
            return;
        }
        mStatusText.setText(up ? R.string.state_running : R.string.state_stopped);
        mStatusDot.setBackgroundResource(up ? R.drawable.dot_green : R.drawable.dot_gray);
        mAddressText.setText(up ? ServeManager.BASE_URL : getString(R.string.address_hint));
        mDetailText.setText("");
        mStartButton.setEnabled(!up);
        mStopButton.setEnabled(up);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (mWaitingStart) return; // 启动流程已在轮询
        mPolling = true;
        mStatusDot.post(mPoll);
    }

    @Override
    protected void onPause() {
        super.onPause();
        mPolling = false;
        mStatusDot.removeCallbacks(mPoll);
    }
}
