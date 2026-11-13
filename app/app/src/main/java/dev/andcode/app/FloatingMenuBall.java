package dev.andcode.app;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Rect;
import android.os.Build;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.ViewConfiguration;
import android.widget.FrameLayout;
import androidx.appcompat.widget.AppCompatImageButton;

import com.google.android.material.color.MaterialColors;

/**
 * Floating drawer ball (ported from andapi FloatingMenuBall): a draggable menu
 * entry over the fullscreen WebView. On release, it snaps to the nearest side
 * and hides (half offscreen and dimmed), avoiding the page's own header menu.
 * Touch to reveal: the first tap only reveals it, and the second invokes onOpen.
 * Docking side and vertical position persist in "andcode_ui" preferences across pages.
 *
 * On API 29+, exclude its rectangle from system back gestures: when docked,
 * it sits within the gesture inset, which would otherwise intercept the initial drag.
 */
public class FloatingMenuBall extends AppCompatImageButton {

    private static final String UI_PREFS = "andcode_ui";
    private static final float BALL_HIDE_SLIDE = 0.55f;
    private static final float BALL_HIDE_ALPHA = 0.35f;
    private static final int SIDE_LEFT = 0;
    private static final int SIDE_RIGHT = 1;

    private final String mKeySide;
    private final String mKeyYFrac;
    private final android.content.SharedPreferences mPrefs;
    private final float mSlop = ViewConfiguration.get(getContext()).getScaledTouchSlop();
    private final FrameLayout mContent;
    private final Runnable mOpenAction;

    private int mSide;
    private float mDownRawX;
    private float mDownRawY;
    private float mStartX;
    private float mStartY;
    private boolean mDragging;
    private boolean mWasHiddenOnDown;

    public FloatingMenuBall(Context context, FrameLayout content,
                            String prefPrefix, Runnable onOpen) {
        super(context);
        mContent = content;
        mOpenAction = onOpen;
        mKeySide = prefPrefix + "_side";
        mKeyYFrac = prefPrefix + "_yfrac";
        mPrefs = context.getSharedPreferences(UI_PREFS, Context.MODE_PRIVATE);
        mSide = mPrefs.getInt(mKeySide, SIDE_RIGHT);

        setImageResource(R.drawable.ic_menu);
        setBackground(context.getDrawable(R.drawable.bg_back_fab));
        setImageTintList(ColorStateList.valueOf(MaterialColors.getColor(
            this, com.google.android.material.R.attr.colorOnSurfaceVariant)));
        setElevation(8f);
        setContentDescription(context.getString(R.string.nav_open_menu));
        setLayoutParams(new FrameLayout.LayoutParams(dp(44), dp(44),
            Gravity.TOP | Gravity.START));
        setOnClickListener(v -> mOpenAction.run());
        content.post(this::applyPersisted);

        setOnTouchListener((v, ev) -> {
            switch (ev.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    mDownRawX = ev.getRawX();
                    mDownRawY = ev.getRawY();
                    mStartX = v.getTranslationX();
                    mStartY = v.getTranslationY();
                    mWasHiddenOnDown = v.getAlpha() < 0.99f;
                    mDragging = false;
                    reveal();
                    return true;
                case MotionEvent.ACTION_MOVE: {
                    float dx = ev.getRawX() - mDownRawX;
                    float dy = ev.getRawY() - mDownRawY;
                    if (!mDragging && (Math.abs(dx) > mSlop || Math.abs(dy) > mSlop)) {
                        // Leaving the tap region: snap to the revealed dock position before dragging to avoid jumps.
                        mDragging = true;
                        reveal();
                        mDownRawX = ev.getRawX();
                        mDownRawY = ev.getRawY();
                    }
                    if (mDragging) {
                        v.setTranslationX(clamp(mStartX + dx, 0, maxX()));
                        v.setTranslationY(clamp(mStartY + dy, 0, maxY()));
                        updateGestureExclusion();
                    }
                    return true;
                }
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL:
                    if (ev.getActionMasked() == MotionEvent.ACTION_UP && !mDragging) {
                        if (!mWasHiddenOnDown) {
                            v.performClick();
                        }
                        // The first tap while hidden only reveals it (see reveal); the second opens the drawer.
                    } else {
                        mSide = (v.getTranslationX() + v.getWidth() / 2f
                            < mContent.getWidth() / 2f) ? SIDE_LEFT : SIDE_RIGHT;
                        mPrefs.edit()
                            .putInt(mKeySide, mSide)
                            .putFloat(mKeyYFrac,
                                clamp(v.getTranslationY() / Math.max(maxY(), 1f), 0f, 1f))
                            .apply();
                        animate()
                            .translationX(dockX(false))
                            .alpha(BALL_HIDE_ALPHA)
                            .setDuration(180)
                            .withEndAction(this::updateGestureExclusion)
                            .start();
                    }
                    return true;
                default:
                    return false;
            }
        });
    }

    private float maxX() { return Math.max(mContent.getWidth() - getWidth(), 0f); }

    private float maxY() { return Math.max(mContent.getHeight() - getHeight(), 0f); }

    /** Docked x coordinate on [side]; slide half the ball offscreen when hidden. */
    private float dockX(boolean revealed) {
        if (mSide == SIDE_LEFT) {
            return revealed ? 0f : -getWidth() * BALL_HIDE_SLIDE;
        }
        return revealed ? maxX() : maxX() + getWidth() * BALL_HIDE_SLIDE;
    }

    private void reveal() {
        animate().cancel();
        setTranslationX(dockX(true));
        setAlpha(1f);
        post(this::updateGestureExclusion);
    }

    private void applyPersisted() {
        boolean docked = mPrefs.contains(mKeySide);
        float yFrac = docked ? mPrefs.getFloat(mKeyYFrac, 0.12f) : 0.12f;
        setTranslationX(dockX(!docked));
        setTranslationY(clamp(yFrac * maxY(), 0, maxY()));
        setAlpha(docked ? BALL_HIDE_ALPHA : 1f);
        updateGestureExclusion();
    }

    /** Keep the ball usable within the back-gesture inset (view-local coordinates; the system converts them). */
    private void updateGestureExclusion() {
        if (Build.VERSION.SDK_INT < 29) return;
        setSystemGestureExclusionRects(
            java.util.Collections.singletonList(new Rect(0, 0, getWidth(), getHeight())));
    }

    private static float clamp(float v, float min, float max) {
        return Math.min(Math.max(v, min), max);
    }

    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density); }
}
