package dev.andcode.app;

import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.KeyEvent;
import android.view.inputmethod.InputMethodManager;
import android.widget.LinearLayout;
import com.google.android.material.button.MaterialButton;
import com.termux.terminal.KeyHandler;
import com.termux.view.TerminalView;

/** Two custom extra-key rows; non-text keys use the terminal protocol, not IME string injection. Tap CTRL/ALT to latch. */
final class TerminalExtraKeys {
    private final TerminalView terminal;
    private final LinearLayout host;
    private MaterialButton ctrl, alt;

    TerminalExtraKeys(LinearLayout host, TerminalView terminal) {
        this.host = host;
        this.terminal = terminal;
        host.setBackgroundColor(Color.rgb(24, 24, 28));
        host.setPadding(dp(2), dp(3), dp(2), dp(3));
        LinearLayout first = row();
        key(first, "ESC", "Escape", KeyEvent.KEYCODE_ESCAPE);
        key(first, "TAB", "Tab 补全", KeyEvent.KEYCODE_TAB);
        ctrl = modifier(first, "CTRL", "Control 锁定");
        alt = modifier(first, "ALT", "Alt 锁定");
        key(first, "←", "向左", KeyEvent.KEYCODE_DPAD_LEFT);
        key(first, "↓", "向下", KeyEvent.KEYCODE_DPAD_DOWN);
        key(first, "↑", "向上", KeyEvent.KEYCODE_DPAD_UP);
        key(first, "→", "向右", KeyEvent.KEYCODE_DPAD_RIGHT);
        LinearLayout second = row();
        key(second, "HOME", "行首", KeyEvent.KEYCODE_MOVE_HOME);
        key(second, "END", "行尾", KeyEvent.KEYCODE_MOVE_END);
        key(second, "PGUP", "上一页", KeyEvent.KEYCODE_PAGE_UP);
        key(second, "PGDN", "下一页", KeyEvent.KEYCODE_PAGE_DOWN);
        button(second, "/", "斜杠", () -> terminal.inputCodePoint(0, '/', false, false));
        button(second, "-", "连字符", () -> terminal.inputCodePoint(0, '-', false, false));
        key(second, "↵", "回车", KeyEvent.KEYCODE_ENTER);
        button(second, "IME", "显示或隐藏软键盘", () -> {
            terminal.requestFocus();
            InputMethodManager imm = host.getContext().getSystemService(InputMethodManager.class);
            if (imm != null) {
                if (androidx.core.view.ViewCompat.getRootWindowInsets(terminal) != null
                        && androidx.core.view.ViewCompat.getRootWindowInsets(terminal)
                            .isVisible(androidx.core.view.WindowInsetsCompat.Type.ime()))
                    imm.hideSoftInputFromWindow(terminal.getWindowToken(), 0);
                else imm.showSoftInput(terminal, InputMethodManager.SHOW_IMPLICIT);
            }
        });
    }

    boolean controlDown() { return ctrl.isChecked(); }
    boolean altDown() { return alt.isChecked(); }

    private int dp(int value) {
        return Math.round(value * host.getResources().getDisplayMetrics().density);
    }

    private LinearLayout row() {
        LinearLayout row = new LinearLayout(host.getContext());
        row.setOrientation(LinearLayout.HORIZONTAL);
        host.addView(row, new LinearLayout.LayoutParams(-1, -2));
        return row;
    }

    private MaterialButton button(LinearLayout row, String title, String description, Runnable action) {
        MaterialButton button = new MaterialButton(host.getContext());
        button.setText(title);
        button.setContentDescription(description);
        button.setTextSize(11);
        button.setTypeface(Typeface.MONOSPACE);
        button.setAllCaps(false);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setMinHeight(dp(48));
        button.setMinimumHeight(dp(48));
        button.setPadding(0, 0, 0, 0);
        button.setInsetTop(dp(2));
        button.setInsetBottom(dp(2));
        button.setCornerRadius(dp(5));
        button.setBackgroundTintList(new ColorStateList(new int[][]{
            {android.R.attr.state_checked}, {}}, new int[]{Color.rgb(103, 80, 164), Color.rgb(36, 36, 42)}));
        button.setTextColor(Color.rgb(235, 230, 240));
        // Extra keys must not steal the terminal's InputConnection or force the keyboard open.
        button.setFocusable(false);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dp(48), 1);
        params.setMarginStart(dp(1));
        params.setMarginEnd(dp(1));
        row.addView(button, params);
        button.setOnClickListener(v -> {
            terminal.requestFocus();
            if (action != null) action.run();
        });
        return button;
    }

    private MaterialButton modifier(LinearLayout row, String title, String description) {
        MaterialButton button = button(row, title, description, null);
        button.setCheckable(true);
        return button;
    }

    private void key(LinearLayout row, String title, String description, int code) {
        button(row, title, description, () -> {
            if (terminal.getCurrentSession() == null || terminal.getCurrentSession().getEmulator() == null) return;
            int modifiers = (controlDown() ? KeyHandler.KEYMOD_CTRL : 0)
                | (altDown() ? KeyHandler.KEYMOD_ALT : 0);
            terminal.handleKeyCode(code, modifiers);
        });
    }
}
