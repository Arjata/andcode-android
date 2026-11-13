package dev.andcode.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.IBinder;

import androidx.annotation.Nullable;

/**
 * specialUse foreground service for long sessions (FGS type required by targetSdk 37.2, DESIGN §4.4).
 * MVP: placeholder notification and wake-lock semantics only; later versions keep opencode serve running.
 */
public class SessionService extends Service {

    private static final String CHANNEL_ID = "andcode-session";

    @Override
    public void onCreate() {
        super.onCreate();
        NotificationManager nm = getSystemService(NotificationManager.class);
        NotificationChannel ch = new NotificationChannel(CHANNEL_ID, "andcode session",
            NotificationManager.IMPORTANCE_LOW);
        nm.createNotificationChannel(ch);
        Notification n = new Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("andcode")
            .setContentText("opencode session running")
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .build();
        startForeground(1, n);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        // Keep opencode serve running (desktop Web UI backend); idempotent when already started.
        ServeManager.ensureStarted(this, new ServeManager.ReadyCallback() {
            @Override public void onReady(String password) { }
            @Override public void onFailed(String reason) { }
        });
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        stopForeground(STOP_FOREGROUND_REMOVE);
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
