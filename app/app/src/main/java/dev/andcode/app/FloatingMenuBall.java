package dev.andcode.app;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Rect;
import android.os.Build;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.ViewConfiguration;
import android.widget.FrameLayout;
import android.widget.ImageButton;

import com.google.android.material.color.MaterialColors;

/**
 * 悬浮抽屉球(自 andapi FloatingMenuBall 移植):悬浮在全屏 WebView 上的
 * 可拖拽菜单入口。完全可拖动;松手吸附到最近左右边缘并自动隐藏
 * (半滑出屏幕 + 变暗),避免压在页面自己的头部菜单上——触摸即恢复显示
 * (隐藏态第一击只恢复,第二击才触发 onOpen)。停靠边与纵向位置持久化
 * 在 "andcode_ui" 偏好里,多页面共用同一位置。
 *
 * API 29+ 将自身矩形从系统返回手势区排除:贴边停靠时球位于手势 inset
 * 内,若不排除,起手拖动会被系统返回手势吞掉。
 */
public class FloatingMenuBall extends ImageButton {

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
                        // 离开点击区:先吸附到已恢复的停靠位再拖,避免跳动
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
                        // 隐藏态第一击只恢复显示(见 reveal),第二击才开抽屉
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

    /** [side] 侧的停靠 x;隐藏态再向屏幕外滑出半个球 */
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

    /** 保证球在系统返回手势 inset 内仍可用(坐标为 view 本地空间,系统自行换算) */
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
