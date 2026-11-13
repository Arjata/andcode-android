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
        pageTitle(getString(R.string.s_page_title), getString(R.string.s_page_subtitle));
        section(getString(R.string.s_sec_display), getString(R.string.s_sec_display_hint));
        LinearLayout display = card(body, false);
        LinearLayout sizeRow = row();
        sizeRow.addView(label(getString(R.string.s_font_size), 16, true, false), new LinearLayout.LayoutParams(0, -2, 1));
        TextView size = badge(AppSettings.terminalSize(this) + " sp");
        sizeRow.addView(size);
        display.addView(sizeRow);
        gap(display, 8);
        display.addView(label(getString(R.string.s_pinch_hint), 12, false, true));
        gap(display, 12);
        LinearLayout previewCard = card(display, true);
        TextView preview = label("$ opencode\n" + getString(R.string.s_start_dir_home), AppSettings.terminalSize(this), false, false);
        preview.setTypeface(Typeface.MONOSPACE);
        preview.setTextColor(color(com.google.android.material.R.attr.colorOnSecondaryContainer));
        preview.setMinHeight(dp(66));
        previewCard.addView(preview);
        SeekBar slider = new SeekBar(this);
        mSizeSlider = slider;
        slider.setMax(18);
        slider.setProgress(AppSettings.terminalSize(this) - 10);
        slider.setContentDescription(getString(R.string.s_font_size) + ", 10-28 sp");
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
        toggle(display, getString(R.string.s_keep_awake), getString(R.string.s_keep_awake_desc), "keep-screen-on", AppSettings.keepScreenOn(this));

        section(getString(R.string.s_sec_backend), getString(R.string.s_sec_backend_hint));
        LinearLayout backend = card(body, false);
        TextView selectedBackend = label(AppSettings.ubuntuTerminal(this)
            ? getString(R.string.s_backend_ubuntu) : getString(R.string.s_backend_bash), 16, true, false);
        backend.addView(selectedBackend);
        gap(backend, 8);
        backend.addView(label(getString(R.string.s_backend_desc), 12, false, true));
        gap(backend, 12);
        backend.addView(action(getString(R.string.s_backend_pick), false, () -> {
            String[] choices = {getString(R.string.s_backend_bash_choice), getString(R.string.s_backend_ubuntu_choice)};
            new com.google.android.material.dialog.MaterialAlertDialogBuilder(this)
                .setTitle(getString(R.string.s_backend_dialog_title))
                .setSingleChoiceItems(choices, AppSettings.ubuntuTerminal(this) ? 1 : 0, (dialog, which) -> {
                    if (which == 1 && !AppSettings.ubuntuAvailable(this)) {
                        // Single APK: allow selection when only the bundled archive exists; extract on first terminal entry.
                        boolean embedded = true;
                        try {
                            getAssets().open("andcode-rootfs/andcode-rootfs-arm64.tgz.sha256").close();
                        } catch (java.io.IOException error) {
                            embedded = false;
                        }
                        if (!embedded) {
                            android.widget.Toast.makeText(this, getString(R.string.s_backend_missing),
                                android.widget.Toast.LENGTH_LONG).show();
                            return;
                        }
                        android.widget.Toast.makeText(this, getString(R.string.s_backend_auto_extract),
                            android.widget.Toast.LENGTH_LONG).show();
                    }
                    AppSettings.prefs(this).edit().putString("terminal-backend", which == 1 ? "ubuntu-proot" : "bash").apply();
                    selectedBackend.setText(which == 1 ? getString(R.string.s_backend_ubuntu) : getString(R.string.s_backend_bash));
                    dialog.dismiss();
                    android.widget.Toast.makeText(this, getString(R.string.s_backend_applied),
                        android.widget.Toast.LENGTH_LONG).show();
                }).setNegativeButton("取消", null).show();
        }), new LinearLayout.LayoutParams(-1, -2));
        divider(backend);
        toggle(backend, getString(R.string.s_term_proxy), getString(R.string.s_term_proxy_desc), "ubuntu-loopback-proxy", AppSettings.ubuntuProxy(this));

        section(getString(R.string.s_sec_trust), getString(R.string.s_sec_trust_hint));
        LinearLayout trust = card(body, false);
        trust.addView(label(getString(R.string.s_ca_title), 16, true, false));
        gap(trust, 8);
        trust.addView(label(getString(R.string.s_ca_desc), 12, false, true));
        gap(trust, 10);
        mCaStatus = label("", 12, false, true);
        mCaStatus.setTextIsSelectable(true);
        trust.addView(mCaStatus);
        mCaSwitch = new SwitchMaterial(this);
        mCaSwitch.setText(getString(R.string.s_ca_switch));
        mCaSwitch.setContentDescription(getString(R.string.s_ca_switch_cd));
        mCaSwitch.setMinimumHeight(dp(48));
        trust.addView(mCaSwitch);
        mCaSwitch.setOnCheckedChangeListener((button, enabled) -> {
            if (mRefreshingCa) return;
            if (enabled) {
                try { CustomCa.verify(getFilesDir().toPath(), AppSettings.customCaDigest(this)); }
                catch (java.io.IOException error) {
                    mCaSwitch.setChecked(false);
                    caMessage(getString(R.string.s_ca_enable_fail) + error.getMessage());
                    return;
                }
            }
            AppSettings.prefs(this).edit().putBoolean("custom-ca-enabled", enabled).apply();
            refreshCa();
            caMessage(getString(R.string.s_ca_toggle_msg));
        });
        trust.addView(action(getString(R.string.s_ca_import), false,
            () -> caPicker.launch(new String[]{"*/*"})), new LinearLayout.LayoutParams(-1, -2));
        trust.addView(action(getString(R.string.s_ca_clear), false, () -> {
            AppSettings.prefs(this).edit().putBoolean("custom-ca-enabled", false).remove("custom-ca-sha256").apply();
            refreshCa();
            caMessage(getString(R.string.s_ca_clear_msg));
        }), new LinearLayout.LayoutParams(-1, -2));
        divider(trust);
        trust.addView(label(getString(R.string.settings_proxy_title), 16, true, false));
        gap(trust, 6);
        TextView proxyValue = label(AppSettings.proxyUrl(this).isEmpty()
            ? getString(R.string.settings_proxy_unset) : AppSettings.proxyUrl(this), 13, false, true);
        proxyValue.setTypeface(Typeface.MONOSPACE);
        trust.addView(proxyValue);
        gap(trust, 10);
        trust.addView(action(getString(R.string.settings_proxy_action), false, () -> {
            android.widget.EditText input = new android.widget.EditText(this);
            input.setSingleLine(true);
            input.setText(AppSettings.proxyUrl(this));
            input.setHint(getString(R.string.settings_proxy_hint));
            new com.google.android.material.dialog.MaterialAlertDialogBuilder(this)
                .setTitle(getString(R.string.settings_proxy_dialog_title))
                .setView(input)
                .setPositiveButton("保存", (d, w) -> {
                    String v = input.getText().toString().trim();
                    if (!v.isEmpty() && !v.contains("://")) {
                        android.widget.Toast.makeText(this, getString(R.string.settings_proxy_need_scheme),
                            android.widget.Toast.LENGTH_LONG).show();
                        return;
                    }
                    AppSettings.prefs(this).edit().putString("proxy-url", v).apply();
                    proxyValue.setText(v.isEmpty() ? getString(R.string.settings_proxy_unset) : v);
                    android.widget.Toast.makeText(this, getString(R.string.settings_proxy_saved),
                        android.widget.Toast.LENGTH_LONG).show();
                })
                .setNegativeButton("取消", null).show();
        }), new LinearLayout.LayoutParams(-1, -2));
        gap(trust, 8);
        divider(trust);
        toggle(trust, getString(R.string.s_serve_proxy), getString(R.string.s_serve_proxy_desc), "serve-loopback-proxy",
            AppSettings.serveLoopbackProxy(this));
        divider(trust);
        toggle(trust, getString(R.string.s_serve_proot), getString(R.string.s_serve_proot_desc), "serve-proot-backend", AppSettings.serveProotBackend(this));
        refreshCa();

        section(getString(R.string.s_sec_archive), getString(R.string.s_sec_archive_hint));
        LinearLayout archive = card(body, false);
        toggle(archive, getString(R.string.s_keep_git), getString(R.string.s_keep_git_desc), "include-git", AppSettings.includeGit(this));
        divider(archive);
        archive.addView(label(getString(R.string.s_sensitive_check), 13, true, false));
        gap(archive, 6);
        archive.addView(label(getString(R.string.s_sensitive_desc), 12, false, true));

        section(getString(R.string.s_sec_workspace), getString(R.string.s_sec_workspace_hint));
        LinearLayout workspace = card(body, false);
        workspace.addView(label(getString(R.string.s_start_dir), 16, true, false));
        java.io.File selected = AppSettings.selectedProject(this);
        TextView current = label(selected == null ? getString(R.string.s_start_dir_home) : selected.getName(), 13, false, true);
        gap(workspace, 6);
        workspace.addView(current);
        gap(workspace, 12);
        workspace.addView(action(getString(R.string.s_start_dir_reset), false, () -> {
            AppSettings.prefs(this).edit().remove("selected-project").apply();
            current.setText(getString(R.string.s_start_dir_home));
            android.widget.Toast.makeText(this, getString(R.string.s_start_dir_reset_msg), android.widget.Toast.LENGTH_LONG).show();
        }), new LinearLayout.LayoutParams(-1, -2));
        divider(workspace);
        workspace.addView(label(getString(R.string.s_projects_loc), 12, true, true));
        gap(workspace, 6);
        TextView paths = label(AppSettings.projectsDir(this).toString(), 12, false, true);
        paths.setTypeface(Typeface.MONOSPACE);
        paths.setTextIsSelectable(true);
        workspace.addView(paths);
        gap(workspace, 12);
        workspace.addView(label(getString(R.string.s_local_service) + ServeManager.BASE_URL, 12, false, true));
        section(getString(R.string.settings_language_section), getString(R.string.settings_language_hint));
        LinearLayout langCard = card(body, false);
        langCard.addView(label(getString(R.string.settings_language_desc), 12, false, true));
        gap(langCard, 10);
        langCard.addView(action(getString(R.string.settings_language_action), false, () -> {
            String[] tags = {"", "zh", "en"};
            String[] labels = {getString(R.string.settings_language_system),
                "简体中文", "English"};
            androidx.core.os.LocaleListCompat cur =
                androidx.appcompat.app.AppCompatDelegate.getApplicationLocales();
            int checked = 0;
            if (!cur.isEmpty()) {
                String tag = cur.get(0).getLanguage();
                checked = "en".equals(tag) ? 2 : ("zh".equals(tag) ? 1 : 0);
            }
            new com.google.android.material.dialog.MaterialAlertDialogBuilder(this)
                .setTitle(getString(R.string.settings_language_title))
                .setSingleChoiceItems(labels, checked, (d, w) -> {
                    if (tags[w].isEmpty()) {
                        androidx.appcompat.app.AppCompatDelegate
                            .setApplicationLocales(
                                androidx.core.os.LocaleListCompat.getEmptyLocaleList());
                    } else {
                        androidx.appcompat.app.AppCompatDelegate
                            .setApplicationLocales(
                                androidx.core.os.LocaleListCompat.forLanguageTags(tags[w]));
                    }
                    android.widget.Toast.makeText(this,
                        getString(R.string.settings_language_saved),
                        android.widget.Toast.LENGTH_LONG).show();
                    d.dismiss();
                })
                .setNegativeButton(getString(android.R.string.cancel), null).show();
        }), new LinearLayout.LayoutParams(-1, -2));
        gap(body, 12);
        TextView footnote = label(getString(R.string.s_footnote), 12, false, true);
        footnote.setPadding(dp(4), dp(4), dp(4), 0);
        body.addView(footnote);
    }

    @Override protected void onResume() {
        super.onResume();
        // The page may be reused; refresh the font size saved by terminal pinch gestures and its preview.
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
        mCaStatus.setText((enabled ? getString(R.string.s_ca_status_on) : getString(R.string.s_ca_status_off))
            + (digest.isEmpty() ? getString(R.string.s_ca_status_no_pem) : getString(R.string.s_ca_status_digest) + digest));
        mRefreshingCa = true;
        mCaSwitch.setChecked(enabled);
        mRefreshingCa = false;
    }

    private void confirmCa(byte[] bytes, CustomCa.Info info) {
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(24), dp(8), dp(24), 0);
        TextView details = label(getString(R.string.s_ca_confirm_details, info.subject, info.expires, info.fingerprint), 12, false, true);
        details.setTextIsSelectable(true);
        content.addView(details);
        com.google.android.material.textfield.TextInputLayout field = new com.google.android.material.textfield.TextInputLayout(this);
        field.setHint(getString(R.string.s_ca_confirm_hint));
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
        LinearLayout option = column();
        LinearLayout header = row();
        TextView heading = label(title, 15, true, false);
        LinearLayout.LayoutParams headingParams = new LinearLayout.LayoutParams(0, -2, 1);
        headingParams.setMarginEnd(dp(12));
        header.addView(heading, headingParams);
        SwitchMaterial view = new SwitchMaterial(this);
        view.setContentDescription(title);
        view.setChecked(checked);
        view.setMinimumHeight(dp(48));
        header.addView(view, new LinearLayout.LayoutParams(-2, -2));
        option.addView(header, new LinearLayout.LayoutParams(-1, -2));
        TextView description = label(detail, 12, false, true);
        LinearLayout.LayoutParams descriptionParams = new LinearLayout.LayoutParams(-1, -2);
        descriptionParams.topMargin = dp(4);
        option.addView(description, descriptionParams);
        parent.addView(option, new LinearLayout.LayoutParams(-1, -2));
        option.setOnClickListener(v -> view.setChecked(!view.isChecked()));
        view.setOnCheckedChangeListener((button, value) ->
            AppSettings.prefs(this).edit().putBoolean(key, value).apply());
    }
}
