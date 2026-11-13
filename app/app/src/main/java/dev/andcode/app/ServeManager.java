package dev.andcode.app;

import android.content.Context;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * Manage the opencode V2 serve process (desktop Web UI backend, DESIGN §4 Tier P).
 *
 * - Execute binaries through the bundle's patched loader (seccomp compatibility; see scripts/patch-seccomp.sh):
 *   <LD> --library-path <LIB> --inhibit-cache <OC2> serve --port 4096 --hostname 127.0.0.1
 * - Parse the server password from stdout; drain output to files/oc2-serve.log
 *   without writing password lines to the log.
 * - Readiness: GET http://127.0.0.1:4096/ returns 200.
 * - Support jniLibs (nativeLibraryDir/libandcode-oc2.so and a patched loader alongside it)
 *   or development deployment in /data/local/tmp (same environment as scripts/app-launch-oc.sh).
 */
public final class ServeManager {

    public static final int PORT = 4096;
    public static final String BASE_URL = "http://127.0.0.1:" + PORT;

    private static String sPassword;
    private static volatile boolean sStarting;
    private static Process sProcess;

    /** Readiness callback (main thread). */
    public interface ReadyCallback {
        void onReady(String password);
        void onFailed(String reason);
    }

    private ServeManager() {}

    /** Null means a payload-free developer APK. Partial native installs fail closed. */
    static File prepareRuntime(Context app) throws IOException {
        String nat = app.getApplicationInfo().nativeLibraryDir;
        if (!RuntimePayload.present(nat == null ? null : new File(nat).toPath())) return null;
        for (String required : new String[]{"libandcode-ld-linux.so", "libandcode-bash.so"}) {
            if (!new File(nat, required).isFile()) throw new IOException("Missing native payload: " + required);
        }
        return RuntimePayload.prepare(app.getFilesDir().toPath(), new File(nat).toPath(),
            name -> app.getAssets().open("andcode-runtime/" + name)).toFile();
    }

    /** Currently known password (may be null for a leftover server whose stdout was not observed). */
    public static synchronized String getPassword() {
        return sPassword;
    }

    /** Probe whether the server is ready. */
    public static boolean ping() {
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(BASE_URL + "/").openConnection();
            c.setConnectTimeout(800);
            c.setReadTimeout(800);
            int code = c.getResponseCode();
            c.disconnect();
            return code == 200;
        } catch (IOException e) {
            return false;
        }
    }

    /** Asynchronous probe with a main-thread callback (for home-page status polling). */
    public static void pingAsync(java.util.function.Consumer<Boolean> cb) {
        new Thread(() -> {
            final boolean up = ping();
            runOnMain(() -> cb.accept(up));
        }, "oc2-ping").start();
    }

    /**
     * Stop serve: destroy our own child process first, falling back to pkill for leftover
     * instances (such as those started by run-as). Clear the now-invalid password as well.
     * Reset sStarting so another startup can begin immediately.
     */
    public static synchronized void stop(Context ctx) {
        Process p = sProcess;
        if (p != null) {
            p.destroy();
            sProcess = null;
        }
        try {
            // Match direct and PRoot command lines, including the embedded guest argv.
            new ProcessBuilder("pkill", "-f", "oc2.*serve").start();
        } catch (IOException ignored) {
        }
        sPassword = null;
        sStarting = false;
        // The old password is invalid; remove the terminal direct-connect fragment too
        new File(ctx.getApplicationContext().getFilesDir(), SERVE_ENV_NAME).delete();
    }

    /** Env fragment file name for the terminal opencode() direct connect (NAMING: term-serve.env). */
    static final String SERVE_ENV_NAME = "term-serve.env";

    /** Writes the 0600 URL+password fragment; failure is ignored and never affects serve itself. */
    private static void writeServeEnv(File files, String password) {
        File f = new File(files, SERVE_ENV_NAME);
        try (java.io.FileOutputStream out = new java.io.FileOutputStream(f)) {
            out.write(("OPENCODE_SERVER_URL=http://127.0.0.1:" + PORT + "\n"
                + "OPENCODE_PASSWORD=" + password + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
            // A new file may carry group/other bits from umask; the password fragment must be 0600 (384).
            android.system.Os.chmod(f.getAbsolutePath(), 384);
        } catch (Exception ignored) {
        }
    }

    /**
     * Ensure serve is started and invoke the callback when ready; report success immediately if already running.
     * Idempotent: concurrent calls trigger only one startup sequence.
     */
    public static void ensureStarted(Context ctx, ReadyCallback cb) {
        synchronized (ServeManager.class) {
            if (sStarting) {
                // A startup sequence is already running; poll until it completes.
                waitReady(cb, null);
                return;
            }
            sStarting = true;
        }
        final Context app = ctx.getApplicationContext();
        new Thread(() -> {
            android.util.Log.i("andcode", "ensureStarted: starter thread running");
            // Run the initial probe in the background too (ping is a network call, forbidden on the main thread).
            if (ping()) {
                synchronized (ServeManager.class) { sStarting = false; }
                runOnMain(() -> cb.onReady(sPassword));
                return;
            }
            String err = null;
            try {
                err = spawn(app);
            } catch (Exception e) {
                android.util.Log.e("ServeManager", "spawn failed", e);
                err = "spawn failed: " + e;
            }
            final String failure = err;
            if (failure != null) {
                synchronized (ServeManager.class) { sStarting = false; }
                runOnMain(() -> cb.onFailed(failure));
                return;
            }
            waitReady(cb, new File(app.getFilesDir(), "oc2-serve.log"));
        }, "oc2-serve-starter").start();
    }

    /** Start the serve child process; return null on success, otherwise an error message. */
    private static String spawn(Context app) throws IOException {
        File files = app.getFilesDir();
        File runtime = prepareRuntime(app);
        File home = new File(files, "home");
        File tmp = new File(files, "tmp");
        File demo = new File(home, "demo");
        File cfg = new File(home, ".config/opencode");
        if (!cfg.isDirectory()) cfg.mkdirs();
        if (!tmp.isDirectory()) tmp.mkdirs();
        if (!demo.isDirectory()) demo.mkdirs();
        // Migrate bundled opencode.json (provider/key) to app HOME on the first run only.
        File dstCfg = new File(cfg, "opencode.json");
        if (runtime == null && !dstCfg.exists()) {
            File srcCfg = new File("/data/local/tmp/andcode/home/.config/opencode/opencode.json");
            if (srcCfg.exists()) copy(srcCfg, dstCfg);
        }

        // The opt-in PRoot backend uses the guest toolchain (DESIGN sections 4.4/4.8).
        // Missing payloads or instances fail explicitly; never fall back to direct execution.
        android.util.Log.i("andcode", "spawn: serveProotBackend="
            + AppSettings.serveProotBackend(app));
        ProcessBuilder pb = AppSettings.serveProotBackend(app)
            ? prootServe(app, files, runtime)
            : directServe(app, files, runtime, demo, tmp, home);
        if (pb == null) return "opencode V2 二进制或补丁 loader 未部署";

        final Process proc = pb.redirectErrorStream(true).start();
        synchronized (ServeManager.class) { sProcess = proc; sPassword = null; }
        // Drain stdout continuously so a full pipe cannot stall the backend.
        final File log = new File(files, "oc2-serve.log");
        new Thread(() -> {
            try (InputStream in = proc.getInputStream();
                 OutputStream out = new FileOutputStream(log, true)) {
                BufferedReader r = new BufferedReader(new InputStreamReader(in), 8192);
                String line;
                while ((line = r.readLine()) != null) {
                    if (line.startsWith("server password ")) {
                        synchronized (ServeManager.class) {
                            if (sProcess != proc) continue;
                            sPassword = line.substring("server password ".length()).trim();
                            // Publish only for the current process; stop must not leave stale credentials.
                            writeServeEnv(files, sPassword);
                        }
                        continue;
                    }
                    out.write((line + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
                    out.flush();
                }
            } catch (IOException ignored) {
            }
        }, "oc2-serve-stdout").start();
        return null;
    }

    /**
     * Default direct backend using the patched loader. Null means missing binaries.
     */
    private static ProcessBuilder directServe(Context app, File files, File runtime,
                                              File demo, File tmp, File home) throws IOException {
        Paths p = resolvePaths(app);
        if (p == null) return null;
        List<String> cmd = Arrays.asList(
            p.ld, "--library-path", p.lib, "--inhibit-cache", p.oc2,
            "serve", "--port", String.valueOf(PORT), "--hostname", "127.0.0.1");
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(demo);
        Map<String, String> env = pb.environment();
        String root = runtime == null ? "/data/local/tmp/andcode" : runtime.getAbsolutePath();
        env.put("ANDCODE_ROOT", root);
        env.put("ANDCODE_TIER", runtime == null ? "a" : "p");
        env.put("ANDCODE_EXE_DIR", p.lib);
        env.put("ANDCODE_LOADER", p.ld);
        env.put("ANDCODE_LIBPATH", p.lib);
        env.put("GIT_EXEC_PATH", root + "/usr/libexec/git-core");
        env.put("ANDCODE_APP_DATA", files.getAbsolutePath());
        env.put("PATH", root + "/bin:" + root + "/usr/bin:/system/bin");
        env.put("HOME", home.getAbsolutePath());
        env.put("TMPDIR", tmp.getAbsolutePath());
        env.put("BUN_TMPDIR", tmp.getAbsolutePath()); // Bun embedded native library extraction directory; must be app-writable.
        env.put("ANDCODE_IN_PROOT", "1");
        env.put("GLIBC_TUNABLES", "glibc.pthread.rseq=0"); // Zygote seccomp immediately raises SIGSYS for rseq.
        env.put("LD_LIBRARY_PATH", p.lib); // Library resolution for glibc children (opencode-pty, git, etc.).
        // Bundle and point to the opencode-pty plugin binary (DESIGN §1.2): upstream supports
        // OPENCODE_PTY_BIN (first line of resolveBinary in packages/core/src/persistent-pty/binary.bun.ts).
        // Setting it skips cache-directory downloads/verification and directly executes the specified path,
        // avoiding targetSdk 37.2 restrictions on executing app-data files (EACCES posix_spawn).
        String ptyBin = ptyBinPath(app);
        if (ptyBin != null) env.put("OPENCODE_PTY_BIN", ptyBin);
        // v0.4.0 defaults to sockets in /tmp (ignoring TMPDIR), which is not writable on Android.
        env.put("OPENCODE_PTY_SOCKET_DIR", ptySocketDir(app));

        // Never inherit a disabled TLS verifier from the surrounding app process.
        for (String key : new String[]{"HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                "ALL_PROXY", "all_proxy", "NODE_TLS_REJECT_UNAUTHORIZED"}) env.remove(key);
        // Opt-in loopback proxy (serve-loopback-proxy, default off): provider
        // domains may only resolve through the device VPN's local DNS view
        // (direct getaddrinfo fails with EAI_AGAIN, DESIGN §4.4). When the user
        // explicitly enables the setting, point outbound traffic at the device's
        // local mixed-port proxy; TLS verification is never disabled and CA
        // trust stays with the CustomCa NODE_EXTRA_CA_CERTS mechanism below.
        if (AppSettings.serveLoopbackProxy(app)) {
            // Users configure the proxy address and scheme; do not inject assumed values when unset.
            String proxy = AppSettings.proxyUrl(app).trim();
            if (!proxy.isEmpty()) {
                env.put("http_proxy", proxy);
                env.put("https_proxy", proxy);
                env.put("HTTP_PROXY", proxy);
                env.put("HTTPS_PROXY", proxy);
                env.put("ALL_PROXY", proxy);
                env.put("all_proxy", proxy);
            }
        }
        CustomCa.apply(env, files.toPath(), AppSettings.customCaEnabled(app), AppSettings.customCaDigest(app));
        return pb;
    }

    /**
     * Opt-in PRoot backend: proot -> guest loader -> oc2 serve (DESIGN sections 4.4/4.8).
     * Bind native payloads, the runtime farm, optional CA data and app home into the guest
     * (NAMING section 3). Guest /root persists configuration and sessions in files/home.
     * Rebuild the guest environment with env -i; preserve TLS verification and share loopback
     * with Web/TUI clients. Bun extraction and PTY sockets use writable guest /tmp.
     */
    private static ProcessBuilder prootServe(Context app, File files, File runtime) throws IOException {
        Paths p = resolvePaths(app);
        if (p == null || runtime == null || !new File(p.lib, "libandcode-oc2.so").isFile())
            throw new IOException("opencode V2 APK 载荷或 runtime farm 未部署");
        File prootBin = new File(runtime, "usr/lib/proot/proot");
        File prootLoader = new File(runtime, "usr/lib/proot/loader");
        if (!prootBin.isFile() || !prootLoader.isFile()) throw new IOException("PRoot 载荷未部署");
        File rootfs = new File(files, "proot-rootfs");
        android.util.Log.i("andcode", "prootServe: rootfs gate=" + rootfs);
        if (!new File(rootfs, "usr/bin/bash").isFile()) {
            // Single APK (DESIGN v0.4.55): extract a missing instance from the bundled canonical rootfs
            // archive first (on this oc2-serve-starter background thread, while home shows the starting state).
            // Development builds without a bundled payload retain the original error.
            try {
                android.util.Log.i("andcode", "prootServe: auto-install starting");
                RootfsInstaller.logger = message ->
                    android.util.Log.i("andcode", "rootfs: " + message);
                RootfsInstaller.install(files.toPath(),
                    app.getAssets()::open,
                    new RootfsInstaller.Progress() {
                        @Override public void onPhase(String phase) {
                            android.util.Log.i("andcode", "rootfs install phase: " + phase);
                        }
                        @Override public void onBytes(long extracted) {
                            android.util.Log.i("andcode", "rootfs install bytes: " + extracted);
                        }
                    });
                android.util.Log.i("andcode", "prootServe: auto-install done");
            } catch (IOException e) {
                android.util.Log.e("andcode", "prootServe: auto-install failed", e);
                throw new IOException("Ubuntu PRoot 实例未安装且内置归档提取失败: " + e.getMessage(), e);
            }
            if (!new File(rootfs, "usr/bin/bash").isFile()) {
                throw new IOException("Ubuntu PRoot 实例未安装");
            }
        }

        String exe = p.lib;
        String farm = runtime.getAbsolutePath();
        List<String> cmd = new ArrayList<>(Arrays.asList(
            prootBin.getAbsolutePath(),
            "--kill-on-exit", "-l", "-0",
            "-w", "/root",
            "-r", rootfs.getAbsolutePath(),
            "-b", "/dev", "-b", "/proc",
            "-b", exe + ":/mnt/andcode-exe",
            "-b", farm + ":/mnt/andcode-farm",
            "-b", new File(files, "home").getAbsolutePath() + ":/root"));
        // Device storage: the FUSE view follows platform permissions (Download/media read/write tested).
        File sdcard = new File("/storage/emulated/0");
        if (sdcard.isDirectory()) {
            cmd.add("-b");
            cmd.add(sdcard.getAbsolutePath() + ":/mnt/sdcard");
        }
        List<String> guest = new ArrayList<>(Arrays.asList(
            "/usr/bin/env", "-i",
            "HOME=/root", "USER=root", "LOGNAME=root", "SHELL=/bin/bash",
            "TERM=xterm-256color", "LANG=C.UTF-8",
            "GLIBC_TUNABLES=glibc.pthread.rseq=0", // Avoid rseq SIGSYS under zygote seccomp.
            "ANDCODE_IN_PROOT=1",
            "LD_LIBRARY_PATH=/mnt/andcode-farm/lib:/mnt/andcode-exe", // Prebuilt glibc helpers.
            "TMPDIR=/tmp", "BUN_TMPDIR=/tmp", // Bun requires writable guest storage.
            "OPENCODE_PTY_SOCKET_DIR=/tmp",
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"));
        if (new File(exe, "libandcode-opencode-pty.so").isFile()) {
            guest.add("OPENCODE_PTY_BIN=/mnt/andcode-exe/libandcode-opencode-pty.so");
        }
        if (AppSettings.serveLoopbackProxy(app)) {
            String proxy = "http://127.0.0.1:7890";
            guest.add("http_proxy=" + proxy);
            guest.add("https_proxy=" + proxy);
            guest.add("HTTP_PROXY=" + proxy);
            guest.add("HTTPS_PROXY=" + proxy);
        }
        String caPath = customCaFile(app, files);
        if (caPath != null) {
            cmd.add("-b");
            cmd.add(new File(caPath).getParent() + ":/mnt/andcode-ca");
            guest.add("NODE_EXTRA_CA_CERTS=/mnt/andcode-ca/" + new File(caPath).getName());
        }
        cmd.addAll(guest);
        cmd.add("/lib/ld-linux-aarch64.so.1");
        cmd.add("--library-path");
        cmd.add("/mnt/andcode-farm/lib:/mnt/andcode-exe");
        cmd.add("/mnt/andcode-exe/libandcode-oc2.so");
        cmd.add("serve");
        cmd.add("--port");
        cmd.add(String.valueOf(PORT));
        cmd.add("--hostname");
        cmd.add("127.0.0.1");

        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(new File(files, "tmp"));
        Map<String, String> env = pb.environment();
        // The outer process is Bionic; do not inherit glibc preload or trust overrides.
        env.remove("LD_PRELOAD");
        for (String key : new String[]{"HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                "ALL_PROXY", "all_proxy"}) env.remove(key);
        CustomCa.apply(env, files.toPath(), false, "");
        env.put("PROOT_LOADER", prootLoader.getAbsolutePath());
        env.put("LD_LIBRARY_PATH", exe); // Resolve renamed Bionic dependencies such as libtalloc.
        env.put("PROOT_TMP_DIR", new File(files, "tmp").getAbsolutePath());
        env.put("GLIBC_TUNABLES", "glibc.pthread.rseq=0");
        return pb;
    }

    /**
     * Resolve explicitly enabled CA data for its guest bind; never disable TLS verification.
     */
    private static String customCaFile(Context app, File files) throws IOException {
        java.util.Map<String, String> ca = new java.util.HashMap<>();
        CustomCa.apply(ca, files.toPath(), AppSettings.customCaEnabled(app), AppSettings.customCaDigest(app));
        return ca.get("NODE_EXTRA_CA_CERTS");
    }

    /**
     * Poll readiness for up to 40s. Fail fast if serve exits, including the log tail for diagnosis.
     * Reset sStarting on both success and failure; otherwise, restarting after a stop always enters
     * the existing-startup branch and times out after 40s (fixes unexplained restart failure).
     */
    private static void waitReady(ReadyCallback cb, File log) {
        new Thread(() -> {
            long deadline = System.currentTimeMillis() + 40_000;
            while (System.currentTimeMillis() < deadline) {
                if (ping()) {
                    finishStart(cb, null);
                    return;
                }
                Process p = sProcess;
                if (p != null && !p.isAlive()) {
                    // Process exited: watch for another 1.5s for a remaining listener, then fail fast.
                    long grace = System.currentTimeMillis() + 1_500;
                    boolean revived = false;
                    while (System.currentTimeMillis() < grace) {
                        if (ping()) { revived = true; break; }
                        try { Thread.sleep(300); } catch (InterruptedException ignored) { return; }
                    }
                    finishStart(cb, revived ? null : "serve 进程已退出" + tailOfLog(log));
                    return;
                }
                try { Thread.sleep(500); } catch (InterruptedException ignored) { return; }
            }
            finishStart(cb, "serve 启动超时(40s)" + tailOfLog(log));
        }, "oc2-serve-wait").start();
    }

    /** Finish a startup sequence: reset sStarting and invoke the callback on the main thread. */
    private static void finishStart(ReadyCallback cb, String failure) {
        synchronized (ServeManager.class) { sStarting = false; }
        if (failure == null) {
            runOnMain(() -> cb.onReady(getPassword()));
        } else {
            runOnMain(() -> cb.onFailed(failure));
        }
    }

    /** serve log tail (last 3 lines within the final 4KB, capped at 200 characters) for displaying failure reasons. */
    private static String tailOfLog(File log) {
        if (log == null || !log.exists()) return "";
        try (java.io.RandomAccessFile raf = new java.io.RandomAccessFile(log, "r")) {
            long len = raf.length();
            int want = (int) Math.min(len, 4096);
            raf.seek(len - want);
            byte[] buf = new byte[want];
            raf.readFully(buf);
            String[] lines = new String(buf, java.nio.charset.StandardCharsets.UTF_8).split("\n");
            StringBuilder sb = new StringBuilder();
            int taken = 0;
            for (int i = lines.length - 1; i >= 0 && taken < 3; i--) {
                String l = lines[i].trim();
                if (l.isEmpty()) continue;
                sb.insert(0, l + " ⏎ ");
                taken++;
            }
            String s = sb.toString().trim();
            if (s.length() > 200) s = "…" + s.substring(s.length() - 200);
            return s.isEmpty() ? "" : " | 日志尾部: " + s;
        } catch (IOException e) {
            return "";
        }
    }

    static void runOnMain(Runnable r) {
        new android.os.Handler(android.os.Looper.getMainLooper()).post(r);
    }

    private static void copy(File src, File dst) throws IOException {
        try (InputStream in = new java.io.FileInputStream(src);
             OutputStream out = new FileOutputStream(dst)) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        }
    }

    /**
     * Bundled opencode-pty path (see OPENCODE_PTY_BIN comments in spawn):
     * prefer jniLibs (Tier P; packaging must have rewritten interp), then fall back to
     * development deployment in /data/local/tmp (interp points to /data/local/tmp/ld,
     * with libraries resolved via LD_LIBRARY_PATH). Null means no bundled copy (first run hits EACCES).
     */
    static String ptyBinPath(Context app) {
        String nat = app.getApplicationInfo().nativeLibraryDir;
        if (nat != null) {
            File f = new File(nat, "libandcode-opencode-pty.so");
            if (f.exists()) return f.getAbsolutePath();
            if (new File(nat, "libandcode-ld-linux.so").isFile()) return null;
        }
        File f = new File("/data/local/tmp/andcode/lib/opencode-pty");
        return f.exists() ? f.getAbsolutePath() : null;
    }

    /** Short, app-private socket base directory; check sun_path including the upstream uid/hash suffix. */
    static String ptySocketDir(Context app) {
        // Avoid cacheDir: cache cleanup may unlink active sockets, causing ENOENT for new connections.
        String base = app.getFilesDir().getAbsolutePath();
        String socket = base + "/opencode-pty-" + android.os.Process.myUid()
            + "/00000000000000000000000000000000.sock";
        if (socket.getBytes(java.nio.charset.StandardCharsets.UTF_8).length >= 104) {
            throw new IllegalStateException("PTY socket 路径过长: " + socket);
        }
        return base;
    }

    /** Resolve binary/loader paths: prefer jniLibs, then /data/local/tmp development deployment (shared by the terminal page). */
    static Paths resolvePaths(Context app) {
        List<Paths> candidates = new ArrayList<>();
         // 1) jniLibs V2 deployment. Loader name follows NAMING §6.2;
         // do not treat the legacy V1 libandcode-opencode.so as a Web backend.
        String nat = app.getApplicationInfo().nativeLibraryDir;
        if (nat != null) {
            if (new File(nat, "libandcode-ld-linux.so").isFile()) {
                Paths nativePaths = new Paths(nat + "/libandcode-ld-linux.so", nat,
                    nat + "/libandcode-oc2.so");
                return new File(nativePaths.oc2).isFile() ? nativePaths : null;
            }
            candidates.add(new Paths(
                 nat + "/libandcode-ld-linux.so",
                nat,
                nat + "/libandcode-oc2.so"));
        }
        // 2) Development: /data/local/tmp (same deployment as scripts/app-launch-oc.sh / Tier A).
        candidates.add(new Paths(
            "/data/local/tmp/andcode/lib/ld-linux-aarch64.so.1",
            "/data/local/tmp/andcode/lib",
            "/data/local/tmp/oc2"));
        for (Paths p : candidates) {
            if (new File(p.ld).exists() && new File(p.oc2).exists()) return p;
        }
        return null;
    }

    static final class Paths {
        final String ld;
        final String lib;
        final String oc2;
        Paths(String ld, String lib, String oc2) {
            this.ld = ld;
            this.lib = lib;
            this.oc2 = oc2;
        }
    }
}
