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
 * Home dashboard (layout matching andapi): service status card (dot/address/start-stop)
 * and desktop UI / TUI terminal entry cards, with DrawerLayout navigation. Poll status every 2s.
 */
public class HomeActivity extends AppCompatActivity {

    private View mStatusDot;
    private TextView mStatusText;
    private TextView mDetailText;
    private TextView mAddressText;
    private MaterialButton mStartButton;
    private MaterialButton mStopButton;
    private DrawerLayout mDrawer;

    /** Transitional state after the user starts the service, before ping succeeds. */
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
            // Stop the FGS too: START_STICKY would recreate it and call ensureStarted, restarting serve.
            stopService(new Intent(this, SessionService.class));
            render(false, null);
        });

        findViewById(R.id.webButton).setOnClickListener(v ->
            startActivity(new Intent(this, WebActivity.class)));
        findViewById(R.id.terminalButton).setOnClickListener(v ->
            startActivity(new Intent(this, TerminalActivity.class)));

        render(false, null);
    }

    /** Edge-to-edge: keep content clear of the status bar, keyboard, and navigation bar (as in andapi). */
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

    /** Start serve: use the SessionService FGS to keep it alive, then ensure the process is started. */
    private void requestStart() {
        android.util.Log.i("andcode", "requestStart: start button clicked");
        mWaitingStart = true;
        render(null, getString(R.string.state_starting));
        startForegroundService(new Intent(this, SessionService.class));
        ServeManager.ensureStarted(this, new ServeManager.ReadyCallback() {
            @Override public void onReady(String password) {
                android.util.Log.i("andcode", "serve onReady");
                mWaitingStart = false;
                render(true, null);
                resumePoll();
            }
            @Override public void onFailed(String reason) {
                android.util.Log.i("andcode", "serve onFailed: " + reason);
                mWaitingStart = false;
                render(false, reason);
                resumePoll();
            }
        });
    }

    /** Resume 2s status polling after startup (mWaitingStart makes onResume skip it during startup). */
    private void resumePoll() {
        mPolling = true;
        mStatusDot.removeCallbacks(mPoll);
        mStatusDot.post(mPoll);
    }

    /**
     * Render status. A null up updates text only (transition), leaving the status dot unchanged.
     * Otherwise, green means running and gray means stopped; nonempty detail uses the error color
     * (failure reasons must remain visible rather than being overwritten by the status line).
     */
    private void render(Boolean up, String detail) {
        mDetailText.setText(detail != null
            ? getString(R.string.detail_prefix) + detail : "");
        if (up == null) {
            mStatusText.setText(detail != null ? detail : getString(R.string.state_stopped));
            return;
        }
        mStatusText.setText(up ? R.string.state_running : R.string.state_stopped);
        mStatusDot.setBackgroundResource(up ? R.drawable.dot_green : R.drawable.dot_gray);
        mAddressText.setText(up ? ServeManager.BASE_URL : getString(R.string.address_hint));
        mStartButton.setEnabled(!up);
        mStopButton.setEnabled(up);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (mWaitingStart) return; // Startup is already polling.
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
