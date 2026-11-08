package dev.andcode.app;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.GravityCompat;
import androidx.drawerlayout.widget.DrawerLayout;

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
    private String mPassword;
    private DrawerLayout mDrawer;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setContentView(R.layout.activity_web);
        mWebView = findViewById(R.id.web_view);
        mStatus = findViewById(R.id.web_status);
        mDrawer = findViewById(R.id.rootDrawer);

        // 悬浮抽屉球:可拖拽、贴边自动隐藏,点击打开共享抽屉(需 content 引用)
        FrameLayout content = findViewById(R.id.webContent);
        content.addView(new FloatingMenuBall(this, content, "menu_ball",
            () -> mDrawer.openDrawer(GravityCompat.START)));
        NavDrawer.bind(this, mDrawer, new NavDrawer.Callbacks() {
            @Override public void onHomeSelected() { finish(); }
            @Override public void onTerminalSelected() {
                startActivity(new Intent(WebActivity.this, TerminalActivity.class));
            }
            @Override public void onWebSelected() { /* 当前页 */ }
        });

        WebSettings s = mWebView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true); // 配对凭证存 localStorage
        s.setAllowFileAccess(false);
        mWebView.setWebViewClient(new Client());

        // FGS 承接常驻(DESIGN §4.4):应用切后台后 serve 存活
        startForegroundService(new Intent(this, SessionService.class));

        mStatus.setText("正在启动 opencode 服务…");
        ServeManager.ensureStarted(this, new ServeManager.ReadyCallback() {
            @Override public void onReady(String password) {
                mPassword = password;
                mStatus.setVisibility(View.GONE);
                mWebView.loadUrl(ServeManager.BASE_URL + "/");
                // serve 的 stdout 先打 "server listening"(ping 即通)后打
                // "server password":就绪回调时密码可能尚未解析。定期重试注入,
                // 页面侧 __acPair 守卫保证真正生效的只有第一次。
                for (int i = 1; i <= 15; i++) {
                    mWebView.postDelayed(() -> tryAutoPair(), i * 2000L);
                }
            }
            @Override public void onFailed(String reason) {
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
        if (mPassword == null || mPassword.isEmpty()) return;
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

    private class Client extends WebViewClient {
        @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
            // 仅本机 serve 的导航留在 WebView 内
            return !req.getUrl().getHost().equals("127.0.0.1");
        }
        @Override public void onPageFinished(WebView view, String url) {
            tryAutoPair();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        // WebView 不销毁进程级状态;serve 由 SessionService/ServeManager 生命周期管理
        if (mWebView != null) mWebView.destroy();
    }

    @Override
    public void onBackPressed() {
        // 抽屉开着先关抽屉;WebView 有历史则回退;否则退出本页
        if (mDrawer != null && mDrawer.isDrawerOpen(GravityCompat.START)) {
            mDrawer.closeDrawer(GravityCompat.START);
        } else if (mWebView != null && mWebView.canGoBack()) {
            mWebView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
