package dev.andcode.app;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.net.Uri;
import android.webkit.WebChromeClient;
import android.webkit.ValueCallback;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.GravityCompat;
import androidx.drawerlayout.widget.DrawerLayout;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/**
 * Web UI (OpenCode 2.0): WebView hosts the local serve SPA (DESIGN §4 Tier P).
 * - {@link ServeManager} manages serve; show status text until ready.
 * - Initial pairing: try JS autofill for the page's password login; on failure, the user
 *   logs in manually once, then localStorage persists it (as in Chrome).
 * - Overlay the fullscreen WebView with {@link FloatingMenuBall} and shared drawer navigation
 *   (matching the andapi ChatActivity pattern).
 * - networkSecurityConfig allows cleartext only for 127.0.0.1; all other traffic requires HTTPS.
 */
public class WebActivity extends AppCompatActivity {

    private WebView mWebView;
    private TextView mStatus;
    private ValueCallback<Uri[]> mPendingFileChooser;
    private static final int FILE_CHOOSER_REQUEST = 4101;
    private String mPassword;
    private DrawerLayout mDrawer;
    private String mTerminalImeScript;
    // Activity-owned queue: unlike View.postDelayed, all retries can be cancelled
    // before WebView teardown, including when startup completes after navigation.
    private final Handler mUiHandler = new Handler(Looper.getMainLooper());

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setContentView(R.layout.activity_web);
        mWebView = findViewById(R.id.web_view);
        mStatus = findViewById(R.id.web_status);
        mDrawer = findViewById(R.id.rootDrawer);
        getOnBackPressedDispatcher().addCallback(this, new androidx.activity.OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                // Handle the drawer first, then Web history, then default Activity navigation.
                if (mDrawer.isDrawerOpen(GravityCompat.START)) {
                    mDrawer.closeDrawer(GravityCompat.START);
                } else if (mWebView != null && mWebView.canGoBack()) {
                    mWebView.goBack();
                } else {
                    setEnabled(false);
                    try { getOnBackPressedDispatcher().onBackPressed(); }
                    finally { setEnabled(true); }
                }
            }
        });

        // Floating drawer ball: draggable, auto-hides at the edge, and opens the shared drawer on tap (needs content).
        FrameLayout content = findViewById(R.id.webContent);
        content.addView(new FloatingMenuBall(this, content, "menu_ball",
            () -> mDrawer.openDrawer(GravityCompat.START)));
        NavDrawer.bind(this, mDrawer, new NavDrawer.Callbacks() {
            @Override public void onHomeSelected() { NavDrawer.goHome(WebActivity.this); }
            @Override public void onTerminalSelected() {
                startActivity(new Intent(WebActivity.this, TerminalActivity.class));
            }
            @Override public void onWebSelected() { /* Current page. */ }
        });

        WebSettings s = mWebView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true); // Pairing credentials are stored in localStorage.
        s.setAllowFileAccess(false);
        try (InputStream in = getAssets().open("andcode-terminal-ime.js");
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = in.read(buffer)) != -1) out.write(buffer, 0, count);
            mTerminalImeScript = new String(out.toByteArray(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            android.util.Log.e("andcode", "无法加载 Web 终端输入法适配", e);
        }
        // The opencode attachment button triggers <input type=file>; without
        // WebChromeClient.onShowFileChooser, WebView silently ignores the click.
        mWebView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(
                    WebView view, ValueCallback<Uri[]> callback,
                    FileChooserParams params) {
                try {
                    startActivityForResult(
                        params.createIntent(), FILE_CHOOSER_REQUEST);
                } catch (android.content.ActivityNotFoundException e) {
                    android.util.Log.i("andcode", "no file picker activity");
                    callback.onReceiveValue(null);
                    return true;
                }
                mPendingFileChooser = callback;
                return true;
            }
        });
        // Debuggable installs expose the WebView for CDP inspection.
        if ((getApplicationInfo().flags
                & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            android.webkit.WebView.setWebContentsDebuggingEnabled(true);
        }
        mWebView.setWebViewClient(new Client());

        // The FGS keeps serve alive when the app enters the background (DESIGN §4.4).
        startForegroundService(new Intent(this, SessionService.class));

        mStatus.setText(getString(R.string.s_starting_web));
        ServeManager.ensureStarted(this, new ServeManager.ReadyCallback() {
            @Override public void onReady(String password) {
                if (!hasLiveWebView()) return;
                mPassword = password;
                mStatus.setVisibility(View.GONE);
                mWebView.loadUrl(ServeManager.BASE_URL + "/");
                // serve stdout prints "server listening" (ping succeeds) before
                // "server password", so the ready callback may precede password parsing. Retry injection;
                // the page-side __acPair guard ensures only the first successful attempt takes effect.
                for (int i = 1; i <= 15; i++) {
                    mUiHandler.postDelayed(() -> tryAutoPair(), i * 2000L);
                }
            }
            @Override public void onFailed(String reason) {
                if (!hasLiveWebView()) return;
        mStatus.setText(getString(R.string.s_web_failed) + reason);
            }
        });
    }

    /**
     * Inject polling-based pairing JS (async SPA rendering often mounts the form after onPageFinished).
     * Poll every 500ms for 40s: open the password login entry, then fill the password via the native
     * setter for React, fire input, and click connect. With valid localStorage login, no password field appears.
     * Click selectors cover button/a/[role]/span/div, choosing the shortest (innermost) textContent;
     * click bubbles to the actual handler. Supports both English and Chinese UI text.
     */
    private void tryAutoPair() {
        if (!hasLiveWebView() || mPassword == null || mPassword.isEmpty()) return;
        String pw = mPassword;
        String js = "(function(){" +
            "if(window.__acPair)return;window.__acPair=1;" +
            "var n=0;" +
            "function clickText(re){" +
            "var els=document.querySelectorAll('button,a,[role=button],span,div');" +
            "var best=null;" +
            "for(var i=0;i<els.length;i++){" +
            "var t=(els[i].textContent||'').trim();" +
            "if(t&&t.length<=40&&re.test(t)){" +
            "if(!best||t.length<best.textContent.trim().length)best=els[i];}}" +
            "if(best){best.click();return true;}return false;}" +
            "var t=setInterval(function(){" +
            "n++;if(n>80){clearInterval(t);return;}" +
            "var ins=document.querySelectorAll('input');" +
            "var pw=null;" +
            "for(var i=0;i<ins.length;i++){" +
            "if(ins[i].type==='password'||/密码|password/i.test(ins[i].placeholder||'')||/密码|password/i.test(ins[i].name||'')){pw=ins[i];break;}}" +
            "if(!pw){clickText(/使用密码|use password|password/i);return;}" +
            "if(pw.value)return;" +
            "var set=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;" +
            "set.call(pw,'" + pw + "');" +
            "pw.dispatchEvent(new Event('input',{bubbles:true}));" +
            "setTimeout(function(){clickText(/连接|connect/i);},200);" +
            "},500);" +
            "})()";
        mWebView.evaluateJavascript(js, null);
    }

    private boolean hasLiveWebView() {
        return !isFinishing() && !isDestroyed() && mWebView != null;
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST || mPendingFileChooser == null) return;
        Uri[] out = null;
        if (resultCode == RESULT_OK && data != null && data.getData() != null) {
            out = new Uri[]{data.getData()};
        }
        mPendingFileChooser.onReceiveValue(out);
        mPendingFileChooser = null;
    }

    @Override protected void onResume() {
        super.onResume();
        if (AppSettings.keepScreenOn(this)) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private class Client extends WebViewClient {
        @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
            // Keep only local serve navigation inside WebView.
            return !"127.0.0.1".equals(req.getUrl().getHost());
        }
        @Override public void onPageFinished(WebView view, String url) {
            if (!hasLiveWebView() || view != mWebView) return;
            if (url != null && url.startsWith(ServeManager.BASE_URL + "/")
                    && mTerminalImeScript != null) {
                view.evaluateJavascript(mTerminalImeScript, null);
            }
            tryAutoPair();
        }
    }

    @Override
    protected void onDestroy() {
        mUiHandler.removeCallbacksAndMessages(null);
        // Detach Activity callbacks and the view tree before destruction; leaving the page does not affect serve.
        WebView webView = mWebView;
        mWebView = null;
        if (webView != null) {
            webView.stopLoading();
            webView.setWebViewClient(new WebViewClient());
            if (webView.getParent() instanceof ViewGroup) {
                ((ViewGroup) webView.getParent()).removeView(webView);
            }
            webView.destroy();
        }
        super.onDestroy();
    }

}
