package dev.andcode.app;

import android.content.Intent;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.View;
import android.view.Gravity;
import android.widget.*;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.*;
import androidx.drawerlayout.widget.DrawerLayout;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.card.MaterialCardView;
import com.google.android.material.color.MaterialColors;
import com.google.android.material.appbar.MaterialToolbar;

/** 项目/设置页共用的 Material 顶栏、卡片与排版。颜色跟随 DayNight 主题。 */
public abstract class UtilityActivity extends AppCompatActivity {
    protected LinearLayout body;
    private DrawerLayout drawer;
    private MaterialToolbar toolbar;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        drawer = new DrawerLayout(this);
        LinearLayout page = column();
        toolbar = new MaterialToolbar(this);
        toolbar.setNavigationIcon(R.drawable.ic_menu);
        toolbar.setNavigationContentDescription(R.string.nav_open_menu);
        toolbar.setNavigationOnClickListener(v -> drawer.openDrawer(GravityCompat.START));
        toolbar.setNavigationIconTint(color(com.google.android.material.R.attr.colorOnSurface));
        page.addView(toolbar, new LinearLayout.LayoutParams(-1, dp(64)));
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setClipToPadding(false);
        body = column();
        body.setPadding(dp(20), dp(8), dp(20), dp(28));
        scroll.addView(body);
        page.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        page.setBackgroundColor(color(com.google.android.material.R.attr.colorSurface));
        drawer.addView(page, new DrawerLayout.LayoutParams(-1, -1));
        getLayoutInflater().inflate(R.layout.nav_drawer, drawer, true);
        setContentView(drawer);
        getOnBackPressedDispatcher().addCallback(this, new androidx.activity.OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                if (drawer.isDrawerOpen(GravityCompat.START)) drawer.closeDrawer(GravityCompat.START);
                else {
                    setEnabled(false);
                    getOnBackPressedDispatcher().onBackPressed();
                    setEnabled(true);
                }
            }
        });
        ViewCompat.setOnApplyWindowInsetsListener(page, (view, insets) -> {
            androidx.core.graphics.Insets bars = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout()
                    | WindowInsetsCompat.Type.ime());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });
        NavDrawer.bind(this, drawer, new NavDrawer.Callbacks() {
            public void onHomeSelected() { NavDrawer.goHome(UtilityActivity.this); }
            public void onTerminalSelected() { startActivity(new Intent(UtilityActivity.this, TerminalActivity.class)); }
            public void onWebSelected() { startActivity(new Intent(UtilityActivity.this, WebActivity.class)); }
        });
    }

    protected int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    protected int color(int attr) { return MaterialColors.getColor(this, attr, "andcode"); }
    protected LinearLayout column() {
        LinearLayout view = new LinearLayout(this);
        view.setOrientation(LinearLayout.VERTICAL);
        return view;
    }
    protected LinearLayout row() {
        LinearLayout view = new LinearLayout(this);
        view.setOrientation(LinearLayout.HORIZONTAL);
        view.setGravity(Gravity.CENTER_VERTICAL);
        return view;
    }
    protected void pageTitle(String title, String subtitle) {
        toolbar.setTitle(title);
        TextView intro = label(subtitle, 14, false, true);
        intro.setPadding(0, dp(2), 0, dp(20));
        body.addView(intro);
    }
    protected TextView label(String value, int size, boolean bold, boolean muted) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color(muted ? com.google.android.material.R.attr.colorOnSurfaceVariant
            : com.google.android.material.R.attr.colorOnSurface));
        if (bold) view.setTypeface(view.getTypeface(), Typeface.BOLD);
        view.setLineSpacing(dp(3), 1);
        return view;
    }
    protected TextView section(String title, String detail) {
        LinearLayout row = row();
        row.setPadding(dp(4), dp(8), dp(4), dp(12));
        TextView heading = label(title, 14, true, false);
        row.addView(heading, new LinearLayout.LayoutParams(0, -2, 1));
        TextView extra = label(detail, 12, false, true);
        row.addView(extra);
        body.addView(row);
        return extra;
    }
    protected LinearLayout card(LinearLayout parent, boolean featured) {
        MaterialCardView card = new MaterialCardView(this);
        card.setRadius(dp(20));
        card.setCardElevation(0);
        card.setStrokeWidth(0);
        card.setCardBackgroundColor(color(featured
            ? com.google.android.material.R.attr.colorSecondaryContainer
            : com.google.android.material.R.attr.colorSurfaceContainerLow));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.bottomMargin = dp(12);
        parent.addView(card, params);
        LinearLayout content = column();
        content.setPadding(dp(18), dp(18), dp(18), dp(18));
        card.addView(content);
        return content;
    }
    protected void gap(LinearLayout parent, int height) {
        parent.addView(new View(this), new LinearLayout.LayoutParams(1, dp(height)));
    }
    protected void divider(LinearLayout parent) {
        View line = new View(this);
        line.setBackgroundColor(color(com.google.android.material.R.attr.colorOutlineVariant));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, dp(1));
        params.topMargin = dp(16);
        params.bottomMargin = dp(16);
        parent.addView(line, params);
    }
    protected TextView badge(String title) {
        TextView view = label(title, 11, true, false);
        view.setTextColor(color(com.google.android.material.R.attr.colorOnSecondaryContainer));
        android.graphics.drawable.GradientDrawable background = new android.graphics.drawable.GradientDrawable();
        background.setColor(color(com.google.android.material.R.attr.colorSecondaryContainer));
        background.setCornerRadius(dp(8));
        view.setBackground(background);
        view.setPadding(dp(10), dp(5), dp(10), dp(5));
        return view;
    }
    protected MaterialButton action(String title, boolean primary, Runnable action) {
        MaterialButton button = new MaterialButton(this, null, primary
            ? com.google.android.material.R.attr.materialButtonStyle
            : com.google.android.material.R.attr.materialButtonOutlinedStyle);
        button.setText(title);
        button.setTextSize(13);
        button.setAllCaps(false);
        button.setMinHeight(dp(48));
        button.setMinimumHeight(dp(48));
        button.setCornerRadius(dp(12));
        button.setInsetTop(dp(3));
        button.setInsetBottom(dp(3));
        button.setPadding(dp(14), 0, dp(14), 0);
        button.setOnClickListener(v -> action.run());
        return button;
    }
}
