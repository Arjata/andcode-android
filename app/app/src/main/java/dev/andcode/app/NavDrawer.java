package dev.andcode.app;

import android.app.Activity;
import android.content.Intent;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.GravityCompat;
import androidx.drawerlayout.widget.DrawerLayout;

/**
 * Shared drawer navigation (matching the andapi NavDrawer pattern): each page inflates
 * layout/nav_drawer.xml and delegates wiring here for consistent navigation.
 * The current page's entry is a no-op. The version stays at the bottom of the drawer.
 */
public final class NavDrawer {

    public interface Callbacks {
        void onHomeSelected();
        void onTerminalSelected();
        void onWebSelected();
    }

    private NavDrawer() {}

    /** Home is an explicit destination; finish() does not guarantee HomeActivity is next on the back stack. */
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
