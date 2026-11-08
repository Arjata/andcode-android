package dev.andcode.app;

import android.app.Activity;
import android.content.Intent;
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

    /** “主页”是明确目的地,不能假定 finish() 后返回栈里一定是 HomeActivity。 */
    public static void goHome(Activity activity) {
        activity.startActivity(new Intent(activity, HomeActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP));
        activity.finish();
    }

    public static void bind(Activity activity, DrawerLayout drawer, Callbacks cb) {
        TextView home = drawer.findViewById(R.id.navHome);
        TextView terminal = drawer.findViewById(R.id.navTerminal);
        TextView web = drawer.findViewById(R.id.navWeb);

        home.setOnClickListener(v -> { drawer.closeDrawer(GravityCompat.START); cb.onHomeSelected(); });
        terminal.setOnClickListener(v -> { drawer.closeDrawer(GravityCompat.START); cb.onTerminalSelected(); });
        web.setOnClickListener(v -> { drawer.closeDrawer(GravityCompat.START); cb.onWebSelected(); });
        drawer.findViewById(R.id.navProjects).setOnClickListener(v -> {
            drawer.closeDrawer(GravityCompat.START);
            if (!(activity instanceof ProjectsActivity))
                activity.startActivity(new Intent(activity, ProjectsActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
        });
        drawer.findViewById(R.id.navSettings).setOnClickListener(v -> {
            drawer.closeDrawer(GravityCompat.START);
            if (!(activity instanceof SettingsActivity))
                activity.startActivity(new Intent(activity, SettingsActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
        });

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
