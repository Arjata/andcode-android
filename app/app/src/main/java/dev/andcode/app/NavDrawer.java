package dev.andcode.app;

import android.app.Activity;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.GravityCompat;
import androidx.drawerlayout.widget.DrawerLayout;

/**
 * 共享抽屉导航(对齐 andapi NavDrawer 模式):每个页面 inflate
 * layout/nav_drawer.xml 后交给本类接线,导航行为全局一致;
 * 当前页对应条目为空操作。版本号常驻抽屉底部。
 */
public final class NavDrawer {

    public interface Callbacks {
        void onHomeSelected();
        void onTerminalSelected();
        void onWebSelected();
    }

    private NavDrawer() {}

    public static void bind(Activity activity, DrawerLayout drawer, Callbacks cb) {
        TextView home = drawer.findViewById(R.id.navHome);
        TextView terminal = drawer.findViewById(R.id.navTerminal);
        TextView web = drawer.findViewById(R.id.navWeb);

        home.setOnClickListener(v -> { drawer.closeDrawer(GravityCompat.START); cb.onHomeSelected(); });
        terminal.setOnClickListener(v -> { drawer.closeDrawer(GravityCompat.START); cb.onTerminalSelected(); });
        web.setOnClickListener(v -> { drawer.closeDrawer(GravityCompat.START); cb.onWebSelected(); });

        String version;
        try {
            version = activity.getPackageManager()
                .getPackageInfo(activity.getPackageName(), 0).versionName;
        } catch (Exception e) {
            version = "?";
        }
        TextView ver = drawer.findViewById(R.id.navVersion);
        if (ver != null) {
            ver.setText(activity.getString(R.string.app_name) + " v" + version);
        }
    }
}
