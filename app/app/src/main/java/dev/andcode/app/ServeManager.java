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
 * 托管 opencode V2 serve 进程(桌面级 Web UI 的后端,DESIGN §4 Tier P)。
 *
 * - 二进制执行走 bundle 的补丁 loader(seccomp 兼容,见 scripts/patch-seccomp.sh):
 *   <LD> --library-path <LIB> --inhibit-cache <OC2> serve --port 4096 --hostname 127.0.0.1
 * - Parse the server password from stdout; drain output to files/oc2-serve.log
 *   without writing password lines to the log.
 * - 就绪判定:GET http://127.0.0.1:4096/ 返回 200。
 * - 兼容两种部署:jniLibs(nativeLibraryDir/libandcode-oc2.so + 同目录补丁 loader)
 *   或开发期 /data/local/tmp(与 scripts/app-launch-oc.sh 同环境)。
 */
public final class ServeManager {

    public static final int PORT = 4096;
    public static final String BASE_URL = "http://127.0.0.1:" + PORT;

    private static String sPassword;
    private static volatile boolean sStarting;
    private static Process sProcess;

    /** 就绪回调(主线程) */
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

    /** 当前已知密码(可能为 null:server 是上一轮遗留、stdout 未见) */
    public static synchronized String getPassword() {
        return sPassword;
    }

    /** 探测 server 是否已就绪 */
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

    /** 异步探测,主线程回调(主页状态轮询用) */
    public static void pingAsync(java.util.function.Consumer<Boolean> cb) {
        new Thread(() -> {
            final boolean up = ping();
            runOnMain(() -> cb.accept(up));
        }, "oc2-ping").start();
    }

    /**
     * 停止 serve:优先销毁本进程拉起的子进程;遗留实例(如 run-as 起的)
     * 退而 pkill 兜底。停止后旧 password 即失效,一并清空;
     * 同时复位 sStarting,保证随后可立即再次启动。
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
     * 确保 serve 已启动并在就绪后回调。若已在运行则直接回调成功。
     * 幂等:并发调用只触发一次启动流程。
     */
    public static void ensureStarted(Context ctx, ReadyCallback cb) {
        synchronized (ServeManager.class) {
            if (sStarting) {
                // 已有启动流程在跑,轮询等它完成
                waitReady(cb, null);
                return;
            }
            sStarting = true;
        }
        final Context app = ctx.getApplicationContext();
        new Thread(() -> {
            android.util.Log.i("andcode", "ensureStarted: starter thread running");
            // 初始探测也在后台做(ping 是网络调用,禁止主线程)
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

    /** 启动 serve 子进程;返回 null=成功,否则错误信息 */
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
        // 配置迁移:bundle 内预置 opencode.json(provider/key)→ 应用 HOME(仅首次)
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
        env.put("BUN_TMPDIR", tmp.getAbsolutePath()); // Bun 内嵌原生库提取目录,必须应用可写
        env.put("ANDCODE_IN_PROOT", "1");
        env.put("GLIBC_TUNABLES", "glibc.pthread.rseq=0"); // zygote seccomp 对 rseq 直接 SIGSYS
        env.put("LD_LIBRARY_PATH", p.lib); // glibc 子进程(opencode-pty、git 等)的库解析
        // opencode-pty 插件二进制"预置副本 + 指路"(DESIGN §1.2):官方支持
        // OPENCODE_PTY_BIN 覆盖(packages/core/src/persistent-pty/binary.bun.ts
        // resolveBinary 首行),设置后跳过缓存目录下载/校验,直接 exec 指定路径——
        // 避开应用域禁 exec 应用数据文件的 targetSdk 37.2 约束(EACCES posix_spawn)
        String ptyBin = ptyBinPath(app);
        if (ptyBin != null) env.put("OPENCODE_PTY_BIN", ptyBin);
        // v0.4.0 默认把 socket 放在 /tmp(忽略 TMPDIR),Android 下不可写。
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
            // 代理地址与协议由用户配置;未配置时不注入任何假设值。
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
            // 单 APK(DESIGN v0.4.55):实例缺失时先从内置 canonical rootfs 归档
            // 提取(本线程即 oc2-serve-starter 后台线程,主页处于"启动中"状态);
            // 无内置载荷的开发构建保留原报错。
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
        // 设备存储:FUSE 视图受平台权限约束(Download/媒体已实测可读写)。
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
     * 轮询就绪(最长 40s)。serve 进程退出则快速失败(附日志尾部定位原因)。
     * 无论成功失败,结束时都复位 sStarting——否则停止后再启动会永远
     * 走进"已有启动流程"分支,卡 40s 超时(修复:重启失败且无原因)。
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
                    // 进程已退出:再观察 1.5s 确认没有残留监听,然后快速失败
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

    /** 结束一次启动流程:复位 sStarting 并主线程回调 */
    private static void finishStart(ReadyCallback cb, String failure) {
        synchronized (ServeManager.class) { sStarting = false; }
        if (failure == null) {
            runOnMain(() -> cb.onReady(getPassword()));
        } else {
            runOnMain(() -> cb.onFailed(failure));
        }
    }

    /** serve 日志尾部(末尾 4KB 内最后 3 行,截 200 字符),失败时给界面展示原因 */
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
     * opencode-pty 预置副本路径(指路用,见 spawn 内 OPENCODE_PTY_BIN 注释):
     * 优先 jniLibs(Tier P,打包链须已完成 interp 改写),回退
     * /data/local/tmp 开发部署(interp 已指向 /data/local/tmp/ld、
     * 库解析走 LD_LIBRARY_PATH)。null = 无预置副本(首次会 EACCES)。
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

    /** 短且应用私有的 socket 基目录;与上游追加的 uid/hash 后缀一起检查 sun_path。 */
    static String ptySocketDir(Context app) {
        // 不放 cacheDir:缓存清理可能 unlink 活跃 socket,导致新连接 ENOENT。
        String base = app.getFilesDir().getAbsolutePath();
        String socket = base + "/opencode-pty-" + android.os.Process.myUid()
            + "/00000000000000000000000000000000.sock";
        if (socket.getBytes(java.nio.charset.StandardCharsets.UTF_8).length >= 104) {
            throw new IllegalStateException("PTY socket 路径过长: " + socket);
        }
        return base;
    }

    /** 二进制/loader 路径解析:优先 jniLibs,回退 /data/local/tmp 开发部署(终端页复用) */
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
        // 2) 开发期:/data/local/tmp(与 scripts/app-launch-oc.sh / Tier A 同部署)
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
