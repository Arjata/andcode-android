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
 * Web 图形界面(OpenCode 2.0):WebView 承载本机 serve 的 SPA(DESIGN §4 Tier P)。
 * - serve 由 {@link ServeManager} 托管;就绪前显示状态文本。
 * - 首次配对:页面自带"使用密码"登录;尝试 JS 自动填充,失败则用户手动一次,
 *   之后 localStorage 持久(与 Chrome 行为一致)。
 * - 全屏 WebView 上叠加 {@link FloatingMenuBall} 悬浮球 + 共享抽屉导航
 *   (对齐 andapi ChatActivity 模式)。
 * - 127.0.0.1 明文仅经 networkSecurityConfig 放行,其余流量仍强制 https。
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
                // 抽屉优先,然后 Web 历史,最后交回 Activity 默认导航。
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

        // 悬浮抽屉球:可拖拽、贴边自动隐藏,点击打开共享抽屉(需 content 引用)
        FrameLayout content = findViewById(R.id.webContent);
        content.addView(new FloatingMenuBall(this, content, "menu_ball",
            () -> mDrawer.openDrawer(GravityCompat.START)));
        NavDrawer.bind(this, mDrawer, new NavDrawer.Callbacks() {
            @Override public void onHomeSelected() { NavDrawer.goHome(WebActivity.this); }
            @Override public void onTerminalSelected() {
                startActivity(new Intent(WebActivity.this, TerminalActivity.class));
            }
            @Override public void onWebSelected() { /* 当前页 */ }
        });

        WebSettings s = mWebView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true); // 配对凭证存 localStorage
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
        // opencode 附件按钮最终触发 <input type=file>;WebView 没有
        // WebChromeClient.onShowFileChooser 时该点击静默无响应。
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

        // FGS 承接常驻(DESIGN §4.4):应用切后台后 serve 存活
        startForegroundService(new Intent(this, SessionService.class));

        mStatus.setText("正在启动 opencode 服务…");
        ServeManager.ensureStarted(this, new ServeManager.ReadyCallback() {
            @Override public void onReady(String password) {
                if (!hasLiveWebView()) return;
                mPassword = password;
                mStatus.setVisibility(View.GONE);
                mWebView.loadUrl(ServeManager.BASE_URL + "/");
                // serve 的 stdout 先打 "server listening"(ping 即通)后打
                // "server password":就绪回调时密码可能尚未解析。定期重试注入,
                // 页面侧 __acPair 守卫保证真正生效的只有第一次。
                for (int i = 1; i <= 15; i++) {
                    mUiHandler.postDelayed(() -> tryAutoPair(), i * 2000L);
                }
            }
            @Override public void onFailed(String reason) {
                if (!hasLiveWebView()) return;
                mStatus.setText("启动失败:" + reason);
            }
        });
    }

    /**
     * 注入轮询式自动配对 JS(SPA 异步渲染,onPageFinished 时表单往往未挂载,必须轮询)。
     * 每 500ms 探测一次,共 40s:有"使用密码"入口先点开;密码框出现后用 React 原生
     * setter 填值 + input 事件 + 点连接。已登录(localStorage 有效)时页面无密码框,自然空转。
     * 点击选择器覆盖 button/a/[role]/span/div,取 textContent 最短(最内层)元素——
     * click 事件会冒泡到真正的处理器;兼容中英文两种界面文案。
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
            // 仅本机 serve 的导航留在 WebView 内
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
        // 先断开 Activity 回调与视图树,再销毁;serve 生命周期不受页面退出影响。
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
