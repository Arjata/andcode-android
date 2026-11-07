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
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

/**
 * 桌面级 Web UI(OpenCode 2.0):WebView 承载本机 serve 的 SPA(DESIGN §4 Tier P)。
 * - serve 由 {@link ServeManager} 托管;就绪前显示状态文本。
 * - 首次配对:页面自带"使用密码"登录;尝试 JS 自动填充,失败则用户手动一次,
 *   之后 localStorage 持久(与 Chrome 行为一致)。
 * - 127.0.0.1 明文仅经 networkSecurityConfig 放行,其余流量仍强制 https。
 */
public class WebActivity extends AppCompatActivity {

    private WebView mWebView;
    private TextView mStatus;
    private String mPassword;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setContentView(R.layout.activity_web);
        mWebView = findViewById(R.id.web_view);
        mStatus = findViewById(R.id.web_status);

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
            }
            @Override public void onFailed(String reason) {
                mStatus.setText("启动失败:" + reason);
            }
        });
    }

    /**
     * 注入轮询式自动配对 JS(SPA 异步渲染,onPageFinished 时表单往往未挂载,必须轮询)。
     * 每 500ms 探测一次,共 20s:有"使用密码"入口先点开;密码框出现后用 React 原生
     * setter 填值 + input 事件 + 点连接。已登录(localStorage 有效)时页面无密码框,自然空转。
     */
    private void tryAutoPair() {
        if (mPassword == null || mPassword.isEmpty()) return;
        String js = "(function(){" +
            "if(window.__acPair)return;window.__acPair=1;" +
            "var n=0;" +
            "var t=setInterval(function(){" +
            "n++;if(n>40){clearInterval(t);return;}" +
            "var ins=document.querySelectorAll('input');" +
            "var pw=null;" +
            "for(var i=0;i<ins.length;i++){" +
            "if(ins[i].type==='password'||/密码|password/i.test(ins[i].placeholder||'')){pw=ins[i];break;}}" +
            "if(!pw){" +
            "var els=document.querySelectorAll('button,a,[role=button]');" +
            "for(var j=0;j<els.length;j++){" +
            "if(/使用密码|password/i.test(els[j].textContent||'')){els[j].click();break;}}" +
            "return;}" +
            "if(pw.value)return;" +
            "var set=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;" +
            "set.call(pw,'" + mPassword + "');" +
            "pw.dispatchEvent(new Event('input',{bubbles:true}));" +
            "setTimeout(function(){" +
            "var bs=document.querySelectorAll('button');" +
            "for(var k=0;k<bs.length;k++){" +
            "if(/连接|connect/i.test(bs[k].textContent||'')){bs[k].click();break;}}" +
            "},200);" +
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
        if (mWebView != null && mWebView.canGoBack()) {
            mWebView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
