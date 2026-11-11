package dev.andcode.app;

import android.os.Bundle;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.LinearLayout;
import android.graphics.Typeface;
import com.google.android.material.switchmaterial.SwitchMaterial;

public class SettingsActivity extends UtilityActivity {
    private SeekBar mSizeSlider;
    private TextView mCaStatus;
    private SwitchMaterial mCaSwitch;
    private boolean mRefreshingCa;
    private final androidx.activity.result.ActivityResultLauncher<String[]> caPicker = registerForActivityResult(
        new androidx.activity.result.contract.ActivityResultContracts.OpenDocument(), uri -> {
            if (uri == null) return;
            new Thread(() -> {
                try (java.io.InputStream in = getContentResolver().openInputStream(uri)) {
                    byte[] bytes = CustomCa.read(in);
                    CustomCa.Info info = CustomCa.inspect(bytes);
                    runOnUiThread(() -> { if (!isFinishing() && !isDestroyed()) confirmCa(bytes, info); });
                } catch (Exception error) {
                    runOnUiThread(() -> caMessage("读取 CA 失败：" + error.getMessage()));
                }
            }, "andcode-ca-import").start();
        });

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        pageTitle("设置", "让工作区适合你的使用习惯");
        section("终端与显示", "返回页面后生效");
        LinearLayout display = card(body, false);
        LinearLayout sizeRow = row();
        sizeRow.addView(label("终端字号", 16, true, false), new LinearLayout.LayoutParams(0, -2, 1));
        TextView size = badge(AppSettings.terminalSize(this) + " sp");
        sizeRow.addView(size);
        display.addView(sizeRow);
        gap(display, 8);
        display.addView(label("终端内也可双指缩放；不影响 Web 内终端", 12, false, true));
        gap(display, 12);
        LinearLayout previewCard = card(display, true);
        TextView preview = label("$ opencode\n准备好，开始创造。", AppSettings.terminalSize(this), false, false);
        preview.setTypeface(Typeface.MONOSPACE);
        preview.setTextColor(color(com.google.android.material.R.attr.colorOnSecondaryContainer));
        preview.setMinHeight(dp(66));
        previewCard.addView(preview);
        SeekBar slider = new SeekBar(this);
        mSizeSlider = slider;
        slider.setMax(18);
        slider.setProgress(AppSettings.terminalSize(this) - 10);
        slider.setContentDescription("终端字号，10 至 28 sp");
        display.addView(slider, new LinearLayout.LayoutParams(-1, dp(40)));
        LinearLayout range = row();
        range.addView(label("10 sp", 11, false, true), new LinearLayout.LayoutParams(0, -2, 1));
        range.addView(label("28 sp", 11, false, true));
        display.addView(range);
        slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            public void onProgressChanged(SeekBar bar, int progress, boolean fromUser) {
                int sp = progress + 10;
                size.setText(sp + " sp");
                preview.setTextSize(sp);
                if (fromUser) AppSettings.prefs(SettingsActivity.this).edit().putInt("terminal-size", sp).apply();
            }
            public void onStartTrackingTouch(SeekBar bar) {}
            public void onStopTrackingTouch(SeekBar bar) {}
        });
        divider(display);
        toggle(display, "保持亮屏", "在终端和 Web 页面中防止屏幕休眠", "keep-screen-on", AppSettings.keepScreenOn(this));

        section("终端环境", "开发预览 · 仅新会话生效");
        LinearLayout backend = card(body, false);
        TextView selectedBackend = label(AppSettings.ubuntuTerminal(this)
            ? "Ubuntu PRoot · 开发实例" : "轻量 Bash · 默认", 16, true, false);
        backend.addView(selectedBackend);
        gap(backend, 8);
        backend.addView(label("不重启已有终端，不改变 OpenCode / Web PTY。Ubuntu 将选中的私有项目映射到"
            + " /workspace/项目名；未选项目从 /root 起步。fake root 不是宿主 root，也不是安全沙箱。", 12, false, true));
        gap(backend, 12);
        backend.addView(action("选择新终端环境", false, () -> {
            String[] choices = {"轻量 Bash（默认）", "Ubuntu PRoot（开发实例）"};
            new com.google.android.material.dialog.MaterialAlertDialogBuilder(this)
                .setTitle("新终端环境")
                .setSingleChoiceItems(choices, AppSettings.ubuntuTerminal(this) ? 1 : 0, (dialog, which) -> {
                    if (which == 1 && !AppSettings.ubuntuAvailable(this)) {
                        android.widget.Toast.makeText(this, "Ubuntu 开发实例未安装；未更改设置。",
                            android.widget.Toast.LENGTH_LONG).show();
                        return;
                    }
                    AppSettings.prefs(this).edit().putString("terminal-backend", which == 1 ? "ubuntu-proot" : "bash").apply();
                    selectedBackend.setText(which == 1 ? "Ubuntu PRoot · 开发实例" : "轻量 Bash · 默认");
                    dialog.dismiss();
                    android.widget.Toast.makeText(this, "已有终端不变；退出 shell 后重新进入终端生效。",
                        android.widget.Toast.LENGTH_LONG).show();
                }).setNegativeButton("取消", null).show();
        }), new LinearLayout.LayoutParams(-1, -2));
        divider(backend);
        toggle(backend, "Ubuntu 显式使用设备代理", "仅新 Ubuntu 会话使用 127.0.0.1:7890；默认关闭，"
            + "需设备自行提供代理，不关闭 TLS 校验。", "ubuntu-loopback-proxy", AppSettings.ubuntuProxy(this));

        section("OpenCode 网络信任", "可选 · 默认关闭 · 下次后端启动生效");
        LinearLayout trust = card(body, false);
        trust.addView(label("自定义 CA", 16, true, false));
        gap(trust, 8);
        trust.addView(label("仅追加信任到新启动的 OpenCode Web 后端及继承环境的子进程；保留默认根证书。"
            + "不修改 Android / WebView、独立终端、Ubuntu 或系统证书库。此 CA 可为任意站点签发证书，"
            + "请通过独立可信渠道核对文件 SHA-256；不自动下载，不关闭 TLS 校验。", 12, false, true));
        gap(trust, 10);
        mCaStatus = label("", 12, false, true);
        mCaStatus.setTextIsSelectable(true);
        trust.addView(mCaStatus);
        mCaSwitch = new SwitchMaterial(this);
        mCaSwitch.setText("追加信任已导入的 CA");
        mCaSwitch.setContentDescription("追加信任已导入的 CA，默认关闭");
        mCaSwitch.setMinimumHeight(dp(48));
        trust.addView(mCaSwitch);
        mCaSwitch.setOnCheckedChangeListener((button, enabled) -> {
            if (mRefreshingCa) return;
            if (enabled) {
                try { CustomCa.verify(getFilesDir().toPath(), AppSettings.customCaDigest(this)); }
                catch (java.io.IOException error) {
                    mCaSwitch.setChecked(false);
                    caMessage("不能启用：" + error.getMessage());
                    return;
                }
            }
            AppSettings.prefs(this).edit().putBoolean("custom-ca-enabled", enabled).apply();
            refreshCa();
            caMessage("已有服务不变；请在主页手动停止并重新启动 OpenCode 服务。");
        });
        trust.addView(action("导入 CA PEM 并核对摘要", false,
            () -> caPicker.launch(new String[]{"*/*"})), new LinearLayout.LayoutParams(-1, -2));
        trust.addView(action("停用并清除 CA 选择", false, () -> {
            AppSettings.prefs(this).edit().putBoolean("custom-ca-enabled", false).remove("custom-ca-sha256").apply();
            refreshCa();
            caMessage("已清除选择；旧副本保留供运行中服务读取。重启后端后不再追加信任。");
        }), new LinearLayout.LayoutParams(-1, -2));
        divider(trust);
        toggle(trust, "后端使用设备回环代理", "仅新启动的 OpenCode 后端向 http://127.0.0.1:7890 注入"
            + "代理环境变量；默认关闭，需设备自行提供本地代理（如 VPN 客户端混合端口）；"
            + "不关闭 TLS 校验，证书信任仍由上方自定义 CA 控制。更改后请在主页手动停止并重新启动服务。", "serve-loopback-proxy",
            AppSettings.serveLoopbackProxy(this));
        divider(trust);
        toggle(trust, "OpenCode 服务进入 Ubuntu PRoot（实验）",
            "仅新启动的 OpenCode 后端经 PRoot 在 Ubuntu 开发实例内运行，"
            + "会话工具链（bash/git 等）来自 guest；实例缺失时首次启动服务会自动"
            + "从内置归档提取（需数分钟与足够存储），失败则明确报错。"
            + "网络代理与自定义 CA 需按所用网络另行开启。"
            + "更改后请在主页手动停止并重新启动服务。", "serve-proot-backend",
            AppSettings.serveProotBackend(this));
        refreshCa();

        section("导出与隐私", "ZIP 归档");
        LinearLayout archive = card(body, false);
        toggle(archive, "包含 Git 历史", "导出时保留 .git 目录，默认关闭", "include-git", AppSettings.includeGit(this));
        divider(archive);
        archive.addView(label("导出前检查敏感文件", 13, true, false));
        gap(archive, 6);
        archive.addView(label(".env 等隐藏文件仍会导出；符号链接和特殊文件始终跳过。", 12, false, true));

        section("工作区", "应用私有存储");
        LinearLayout workspace = card(body, false);
        workspace.addView(label("新终端起始目录", 16, true, false));
        java.io.File selected = AppSettings.selectedProject(this);
        TextView current = label(selected == null ? "HOME · 默认目录" : selected.getName(), 13, false, true);
        gap(workspace, 6);
        workspace.addView(current);
        gap(workspace, 12);
        workspace.addView(action("恢复 HOME 目录", false, () -> {
            AppSettings.prefs(this).edit().remove("selected-project").apply();
            current.setText("HOME · 默认目录");
            android.widget.Toast.makeText(this, "已恢复；不会切换已有终端目录", android.widget.Toast.LENGTH_LONG).show();
        }), new LinearLayout.LayoutParams(-1, -2));
        divider(workspace);
        workspace.addView(label("项目存储位置", 12, true, true));
        gap(workspace, 6);
        TextView paths = label(AppSettings.projectsDir(this).toString(), 12, false, true);
        paths.setTypeface(Typeface.MONOSPACE);
        paths.setTextIsSelectable(true);
        workspace.addView(paths);
        gap(workspace, 12);
        workspace.addView(label("本机服务  ·  " + ServeManager.BASE_URL, 12, false, true));
        TextView footnote = label("模型与提供商请在 Web 图形界面中管理。\n本页不存储 API key，也不会重启现有会话。", 12, false, true);
        footnote.setPadding(dp(4), dp(4), dp(4), 0);
        body.addView(footnote);
    }

    @Override protected void onResume() {
        super.onResume();
        // 页面可被复用;同步终端双指手势保存的字号及其预览。
        mSizeSlider.setProgress(AppSettings.terminalSize(this) - 10);
        refreshCa();
    }

    private void caMessage(String text) {
        if (!isFinishing() && !isDestroyed()) android.widget.Toast.makeText(this, text,
            android.widget.Toast.LENGTH_LONG).show();
    }

    private void refreshCa() {
        if (mCaStatus == null) return;
        String digest = AppSettings.customCaDigest(this);
        boolean enabled = AppSettings.customCaEnabled(this);
        mCaStatus.setText((enabled ? "已启用（下次启动）" : "未启用（使用默认信任）")
            + (digest.isEmpty() ? "\n尚未导入 CA" : "\nPEM 文件 SHA-256：\n" + digest));
        mRefreshingCa = true;
        mCaSwitch.setChecked(enabled);
        mRefreshingCa = false;
    }

    private void confirmCa(byte[] bytes, CustomCa.Info info) {
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(24), dp(8), dp(24), 0);
        TextView details = label("主体：" + info.subject + "\n有效期至：" + info.expires
            + "\n证书 DER SHA-256：\n" + info.fingerprint
            + "\n\n请输入从独立可信渠道取得的 PEM 文件 SHA-256；导入不自动启用。", 12, false, true);
        details.setTextIsSelectable(true);
        content.addView(details);
        com.google.android.material.textfield.TextInputLayout field = new com.google.android.material.textfield.TextInputLayout(this);
        field.setHint("预期 PEM 文件 SHA-256（64 位）");
        com.google.android.material.textfield.TextInputEditText expected = new com.google.android.material.textfield.TextInputEditText(this);
        expected.setSingleLine(true);
        expected.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        field.addView(expected);
        content.addView(field);
        android.widget.ScrollView scroll = new android.widget.ScrollView(this);
        scroll.addView(content);
        androidx.appcompat.app.AlertDialog dialog = new com.google.android.material.dialog.MaterialAlertDialogBuilder(this)
            .setTitle("确认导入自定义 CA").setView(scroll)
            .setNegativeButton("取消", null).setPositiveButton("核对并导入", null).create();
        dialog.setOnShowListener(ignored -> dialog.getButton(androidx.appcompat.app.AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            try {
                CustomCa.Info installed = CustomCa.install(getFilesDir().toPath(), bytes, expected.getText().toString());
                AppSettings.prefs(this).edit().putString("custom-ca-sha256", installed.sha256)
                    .putBoolean("custom-ca-enabled", false).apply();
                refreshCa();
                dialog.dismiss();
                caMessage("已导入且保持关闭；需要时显式开启，手动重启后端生效。");
            } catch (java.io.IOException error) { field.setError(error.getMessage()); }
        }));
        dialog.show();
    }

    private void toggle(LinearLayout parent, String title, String detail, String key, boolean checked) {
        LinearLayout row = row();
        LinearLayout copy = column();
        copy.addView(label(title, 15, true, false));
        gap(copy, 5);
        copy.addView(label(detail, 12, false, true));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, -2, 1);
        params.setMarginEnd(dp(12));
        row.addView(copy, params);
        SwitchMaterial view = new SwitchMaterial(this);
        view.setContentDescription(title);
        view.setChecked(checked);
        view.setMinimumHeight(dp(48));
        row.addView(view);
        parent.addView(row);
        row.setOnClickListener(v -> view.setChecked(!view.isChecked()));
        view.setOnCheckedChangeListener((button, value) ->
            AppSettings.prefs(this).edit().putBoolean(key, value).apply());
    }
}
