# andcode — 将 opencode 移植到 Android arm64 的设计方案

> Version: v0.4.54 (design draft) · Date: 2026-11-11
> v0.4.54 change: add the explicit default-off `serve-proot-backend` preference.
> Newly started managed servers run through PRoot and the Ubuntu guest loader;
> missing APK payloads, runtime farm or guest instance fail without direct fallback.
> Bind native payloads, farm, optional imported CA and app home into the guest;
> rebuild the guest environment, preserve TLS verification and share loopback 4096.
> On device 8c8da214, the app-spawned untrusted_app backend served Web/API, returned
> `ANDCODE_PROOT_SERVE_OK` from arjata/gpt-oss-120b, executed shell commands in
> Ubuntu 24.04.4 with /usr/bin/bash and completed a Web PTY command/exit-0 probe.
> Guest /root writes persisted in files/home. Stop removed the serve process tree,
> env fragment and listener; the service was restarted with PRoot/proxy/CA enabled.
> Tool commands returned exit 0, but provider continuation still failed with HTTP
> 400 openai_error or 503. Full model/tool round trips remain unresolved; no protocol
> workaround or session deletion is claimed. Review restores direct-backend CA
> environment cleanup, strips outer PRoot preload/trust overrides and prevents stale
> stdout from restoring stopped-process credentials. New password lines are no
> longer written to the serve log. Other devices remain pending P0/P3 verification.
> Reinstall retest (same day, device 8c8da214): the reviewed build was installed
> over the previous one with data preserved; all three opt-ins (PRoot backend,
> loopback proxy, custom CA) survived, the PRoot process chain and binds matched
> the reviewed argv, the Web UI answered 200, and new serve-log lines contain no
> password record. The managed serve reported the same opencode 2.2.6 payload.
> A fresh-session API probe reproduced both boundaries exactly: the plain-text
> reply succeeded (`ANDCODE_REVIEW_OK`), the shell tool executed with a completed
> state, and the provider rejected the tool-result continuation with HTTP 400
> `openai_error`; three further fresh sessions failed the same way (400, 503,
> 400). The 400/503 is therefore reproducible with the reviewed build, not
> introduced by this change, and its cause remains unresolved. Follow-up
> isolation on the same day narrows the defect to the provider's
> gpt-oss-120b tool path: a two-turn plain-text conversation that resends
> turn-1 history containing `reasoning_content` succeeds, and a full agentic
> tool round trip (shell tool executed, result resent, model replied
> `ANDCODE_MODEL_TOOL_OK`, outcome succeeded) passes on `arjata/glm-5.2`
> through the same PRoot backend and opencode serialization. gpt-oss-120b
> keeps failing the tool-result continuation (5/5 fresh sessions, 400/503)
> while its plain replies stay fine. Agentic work on this gateway should use
> a model whose tool path works (e.g. glm-5.2) until the provider fixes the
> gpt-oss-120b route. A five-step agentic toolchain chain then passed end to
> end on glm-5.2 through the same backend: write hello.c, gcc compile, run the
> aarch64 binary and readelf-verify Machine: AArch64, all tools exit 0 with a
> successful continuation; other gateway models answer provider.no-route.
> External arm64 executables then ran in the guest: an adb-staged musl-static
> busybox (applets identified by argv[0]), the APK musl-static pty launcher
> and the glibc oc2 via the guest loader, all exit 0, including
> model-dispatched execution of the first two. A model-driven multi-library
> dynamic build then passed: gcc -lm -lpthread -ldl -lz, runtime dlopen of
> libm, zlib compression and a DT_NEEDED list of libz + libc + loader, with
> the model recovering from a missing zlib.h header via apt on its own
> (glibc 2.34+ merges math/pthread/dl into libc, hence no separate NEEDED).
> v0.4.53 change: two Tier P networking closures, both probed on device
> 8c8da214. First, an Ubuntu PRoot feasibility probe: with the native payload
> directory (libandcode-oc2.so), the glibc farm and files/term-serve.env bound
> into the guest, oc2 runs directly under the guest's own
> /lib/ld-linux-aarch64.so.1 with --library-path farm/lib:nativeLibraryDir —
> `opencode v2.2.6` prints without the patched loader (Ubuntu glibc 2.39
> satisfies the symbol floor). The guest reaches the managed serve over the
> shared loopback (TCP probe to 127.0.0.1:4096 OK), so a TUI/serve split
> across the PRoot boundary is viable. Guest DNS (nameserver 1.1.1.1, use-vc)
> resolves public names but not the provider domain, which exists only in the
> device VPN's DNS view; through the loopback proxy 127.0.0.1:7890 the
> endpoint answers 401 over TLS. The endpoint certificate is issued by the
> private "Arjata Fundamental Public Endpoint Issuer" CA with 8-day rotating
> leaf certificates, confirming that CA trust must come from the imported-CA
> mechanism. Second, productize the previously diagnostic-only proxy path:
> the managed serve now honors a new explicit opt-in preference
> `serve-loopback-proxy` (default off) that injects
> http(s)_proxy=http://127.0.0.1:7890 into the serve environment instead of
> stripping proxy variables unconditionally; TLS verification is never
> disabled (NODE_TLS_REJECT_UNAUTHORIZED stays stripped) and CA trust remains
> with the existing CustomCa NODE_EXTRA_CA_CERTS mechanism. Preference key and
> env names registered in NAMING.md. On device 8c8da214, SAF import and explicit
> CA enablement followed by a manual serve restart produced the expected TUI
> reply `ANDCODE_PROXY_CA_OK` from `arjata/gpt-oss-120b` (3.7 seconds shown).
> The app-spawned serve had all four proxy variables and NODE_EXTRA_CA_CERTS,
> no NODE_TLS_REJECT_UNAUTHORIZED, UID10356, Seccomp=2 and untrusted_app under
> enforcing SELinux. A subsequent shell tool returned its expected marker,
> but the provider rejected the tool-result continuation with HTTP 400
> (provider.invalid-request/openai_error); a separate fresh-session tool probe
> reproduced the same failure. Plain-text model traffic passed;
> full tool round trips remain unresolved. PC-side debugging of the
> managed serve needs no new port: `adb forward tcp:<host> tcp:4096` reached
> the loopback serve with HTTP 200. Re-verified on device 8c8da214 after the
> v0.4.53 reinstall: the serve publishes the OpenCode 2.0 web GUI at `/`,
> the JSON API lives under `/api/*`, and API calls require HTTP Basic auth
> (any username, password = the `OPENCODE_PASSWORD` recorded in the managed
> serve env file; Bearer tokens are rejected with 401). The credential must
> never be echoed into shared logs or transcripts.
> v0.4.52 change: on-device probe of the Tier P terminal TUI extra keys and
> clean exit (device 8c8da214, normal/idle state). First, a measurement caveat
> that invalidates earlier negative conclusions: screencap PNGs are full
> 1080x2340 device pixels while the analysis previews were 892x1992, so tap
> coordinates derived from preview pixels missed the keys entirely (a
> "left-arrow" tap actually landed on the TUI cwd line and opened its
> Working-directory dialog). Earlier "ESC did not interrupt the retry state"
> results are retracted as unproven, not negative. Second, IME interference:
> with Fcitx5 pinyin active, `input text`/keyevents were captured by the
> composition layer and the candidate bar overlaid the extra-key row; switching
> the default IME to AOSP Latin (English) restored direct injection (probe done
> with the IME hidden after switching). Verified with corrected device-pixel
> coordinates (extra-key row 1 y≈2086 without IME; keys ≈136 px apart: ESC≈75,
> TAB≈211, CTRL≈345, ALT≈481, ←≈616): hardware keyevents reach the TUI editor
> ("abc"/"z"); the ← extra key moves the cursor ("abc" + two ← taps + "z" →
> "azbc", cursor after z); the ESC extra key closes the TUI command menu
> (opened via "/") — visible open/close contrast; the CTRL sticky key shows a
> purple highlight and works (first Ctrl+C clears the editor line, a
> subsequent Ctrl+C exits), and the TUI exits cleanly back to the shell prompt.
> TAB in the empty editor produced no visible change (inconclusive, not a
> failure). Conclusion: in the TUI normal state, the extra-key row and adb
> key injection are fully reachable; the previous retry-state ESC probe must
> be redone with device-pixel coordinates before claiming any negative result.
> v0.4.51 change: complete the Bun release-profile build experiment. The
> pinned-source Bun build (commit `38afee6c…`, pinned toolchain, pinned focal
> glibc sysroot) now passes end to end on the native `ubuntu-24.04-arm` runner:
> the release profile links `build/release/bun-profile` (244 MB, symbols) and
> strips to `build/release/bun` (107.6 MB, ELF aarch64, PT_INTERP
> `/lib/ld-linux-aarch64.so.1`, symbol-version floor GNU/Linux 3.7.0 — within
> the ≤2.39 red line); smoke runs `bun --version` → 1.4.4 and a JS eval
> (`andcode-bun-release-smoke-ok 42`). Earlier failure was a workflow bug: the
> smoke step expected a nonexistent `bun-release` artifact name (upstream names
> the plain release link `bun-profile` and the stripped copy `bun`); the
> smoke/evidence/upload paths now target `bun`. This experiment does not by
> itself claim ELF-correspondence with the shipped payload, license closure or
> redistribution approval (see the diagnostic-only header of the workflow).
> v0.4.50 change: fix the Tier P terminal TUI startup chain (three defects, all
> verified on device). (1) The interactive bash session died with SIGSEGV
> (session toast "exit -11"): the newly created `~/.bashrc` sourced
> `term-bashrc`, whose bash branch sources `$HOME/.bashrc` back — infinite
> mutual recursion → stack overflow. The profile now skips the back-source
> when `ANDCODE_BASHRC` is set, and the bootstrap `~/.bashrc` exports it;
> the early unguarded template is replaced on sight. (2) `opencode` in the
> terminal now connects to the managed serve via `--server`: serve writes a
> 0600 `term-serve.env` (URL + password, NAMING-registered) on readiness and
> removes it on stop; the shell function sources it after a `toybox nc`
> probe, avoiding the loader-semantics self-spawn failure (execPath is the
> loader itself). (3) The Bun-extracted OpenTUI shared object resolves its
> plain-name deps (`libm.so.6`) via the runtime farm's plain-name symlinks:
> the patched loader rewrites `LD_LIBRARY_PATH` to the `--library-path`
> value, so the farm lib dir must be passed in `--library-path` itself
> (dual path: farm/lib:nativeLibraryDir); plain names never resolved in the
> app domain before this (the earlier CI TUI probe only passed on the Linux
> runner where system plain-name glibc exists). On-device results: TUI
> renders fully in the app terminal, adb-injected text reaches the TUI and
> submits, a session is created and the model call starts; the model round
> trip still fails with `EAI_AGAIN` because the managed serve strips proxy
> env by design (v0.4.48 provider DNS constraint) — Tier P proxy wiring
> remains open. Also recorded: the runtime farm identity includes the
> nativeLibraryDir path string, so every `install -r` creates a new farm
> directory and stale farms accumulate (cleanup pending).
> v0.4.49 change: record the fresh-install regression and the CI debug-keystore
> drift finding. The current CI runner's auto-generated debug key
> (`2bf7e722…`) no longer matches the device install signed by the local
> machine debug keystore (`86d13d4b…`), so CI debug APKs are not upgrade-capable
> over time; stable updates require the release-signing secrets path
> (`andcode-apk-release`). The local rebuild from the trusted CI native payload
> is byte-identical to the installed APK (deterministic payload + same source),
> and the authorized uninstall/reinstall regression passed end to end: first
> launch bootstraps a new runtime farm, the backend serves 2.2.6 on 4096, the
> restored session DB returns all 12 sessions, the app-domain persistent PTY
> runs and exits 0, the PRoot rootfs gate passes in `untrusted_app` with
> Seccomp=2 (`ubuntu-base-exit=0`), and the full development gate passes with
> `development-exit=0 network-mode=direct` (apt, toolchain, compile, PTY).
> The app data UID changed 10348→10356 as expected after uninstall.
> v0.4.48 change: record the Tier M proxy+CA retest milestone and the provider
> DNS constraint. The gateway hostname resolves only through the host proxy's
> fake-IP TUN DNS (198.18.0.0/15); any on-device direct connection therefore
> fails by design (app-domain `EAI_AGAIN`, root shell `ENOTFOUND` via public
> resolvers), so the explicit-proxy path is required for model traffic until a
> publicly resolvable provider endpoint exists. Tier M (`/data/adb/andcode`)
> retested on device after the model-flag fix: two complete model round-trips
> (text reply and bash tool with correct arithmetic) succeeded via
> `HTTPS_PROXY` + `NODE_EXTRA_CA_CERTS` through an adb-reverse loopback proxy;
> the earlier "500" root cause (wrong `--model openai/...` flag) is confirmed
> fixed. This is a manual root-shell diagnostic, not an app-domain result.
> v0.4.47 change: add authenticated deb-src indexes and exact installed source-
> version download evidence to the optional snapshot experiment. Retain .dsc,
> archives, apt commands/logs and hashes outside the rootfs; no source extraction,
> build execution, complete-source or redistribution approval is implied.
> v0.4.46 change: pin the isolated mmdebstrap candidate's guest package origin
> to official HTTPS snapshot `20261110T000000Z`, with explicit signed-by sources.
> Keep apt authentication/expiry policy intact; do not claim byte reproducibility
> or complete corresponding source. Docker and device instances stay unchanged.
> v0.4.45 change: gate the optional mmdebstrap artifact on a read-only comparison
> of the original ext4 tree against the canonical archive, before release upload.
> Compare paths, types, modes, owners, file bytes and links; exclude times/ACLs/xattrs.
> Linux CI verification and Android installation remain separate requirements.
> v0.4.44 change: add build-time trusted canonical-rootfs to PRoot archive
> conversion with bounded hardlink materialization and unchanged file/ELF bytes.
> The fixed Ubuntu Base gate stays the default; Android installation remains pending.
> v0.4.43 change: add an isolated mmdebstrap CI candidate producing a validated
> canonical rootfs archive and ext4 image from signed Ubuntu repositories.
> Docker remains the default; no existing Android instance is modified.
> Snapshot pinning, corresponding source and Android acceptance remain pending.
> v0.4.42 变更(验证边界更新):真实应用域、显式代理+CA 下新会话连续两轮完整
> 工具往返成功,旧会话仍 HTTP 400;未修改协议或删除历史,不能声称根因已修复。
> 诊断 PID8198 已终止,默认 PID20163 保持 CA 关闭及原会话。OpenTUI 排除 GPL
> 声明 CRC 对象后 Linux CI 与 2304 组 CRC 对照通过,许可/重链接/Android 仍未批准。
> v0.4.41 变更(OpenTUI 源码实验):固定独立 Zig 0.17.0 与既有 OpenTUI/FFmpeg/
> zlib 源码,构建期强制视频分支及 16K 对齐,先做 ABI/导出/依赖门禁,后走完整
> TUI staged maps 验证;不接入正式 APK,源码/重链接/许可与 Android 批准仍为 false。
> 可选 CA 实机完成默认关闭/SAF/错误摘要拒绝/导入后关闭/启用及关闭重启环境验证;
> 显式回环代理下关闭 CA 拒绝证书、开启后模型流式/中断/恢复成功,工具执行成功但
> 结果回传后 provider HTTP 400,完整工具往返未通过。直连仍 DNS EAI_AGAIN。
> v0.4.40 变更(可选 CA):Tier P 设置提供 SAF 单 PEM CA 导入/文件摘要核对与
> 默认关闭的追加信任开关;仅新启动 OpenCode Web 后端设置 NODE_EXTRA_CA_CERTS,
> 保留内置根/主机名校验,不改 Android 全局/WebView/独立终端/Ubuntu 信任。
> 导入不自动启用,不联网获取 CA,启用后文件缺失/摘要改变/过期拒绝启动;
> 停用不重启既有会话,需手动停止/启动后端。本机 26 项 Java 校验、APK build/lint
> 及 Bun 1.4.4 真实 TLS 开/关/主机名拒绝通过;CI 42609380415(常规)与
> 42609429688(源码实验)已成功,arm64 日志确认上述 CA 门禁;待 P0/P3 实机验证。
> v0.4.39 变更(实验 fff 来源):固定 fff 源码/lock、zlob feature 和 Zig 0.16.0
> 工具摘要;离线 Cargo 重建后校验 ELF/16K/导出及 Bun 真实索引/搜索/glob,成功才
> 替换实验输入。保留选中 crate 归档、Cargo 消息和 GNU LOAD map/可用输入摘要,
> 临时输入缺失明确记录,不冒称逐节归属或源码/许可闭环;CI 42602199884 已通过
> Linux 实验门禁,工件 3956 项摘要与清单集合已本机复核,正式 APK 不变,
> Android 待 P0/P3 实机验证。GNU 合成 linker stubs 单列,不冒称缺失物理输入。
> v0.4.38 变更(实验 watcher 来源):固定 Parcel watcher 源码、node-addon-api 及
> Node N-API 头文件归档,显式编译 Linux 源文件列表;16K/glibc/导出检查及 Bun
> 真实 inotify 创建事件/取消订阅后才替换实验输入。报告区分 npm 与重建来源,
> 失败不替换,正式 APK 不变,许可与 Android 准入仍未批准。
> v0.4.37 变更(实验原生来源):固定 bun-pty 源码/lock 在 arm64 Linux CI 离线
> 构建(先 fetch),16K/glibc/导出门禁后仅替换实验 npm glibc 输入;Bun 再按新摘要
> 预置,普通 PTY 必须实际映射该副本。保留构建输入/命令/工具/输出,不证明原 npm
> ELF 可重现,不批准分发或 Android 准入;正式 APK 不变。
> v0.4.36 变更(源码实验闭包):从独立 Ubuntu 24.04 CI sysroot 收集 glibc/GCC
> 动态库,记录 image/dpkg/版权/摘要,递归检查 NEEDED 与所需符号版本;实验服务/TUI
> 固定实验 PT_INTERP 与库目录执行并检查映射(显式 loader 影响上游 self-spawn,
> 不可等价替代)。不修改正式载荷,仍不批准分发或 Android 准入。
> v0.4.35 变更(Android libtinfo):v0.4.34 拦截方案被实际初始化门禁证伪(内部绑定
> 绕过 shim),已移除。改用固定 Ubuntu ncurses 源码/安全补丁自编译,关闭
> HAVE_SETFSUID,保留上游无身份变更 safe-open 分支与内核权限检查;标准 Linux
> bundle 不改,Android 替换库与版权/配置/manifest 同步。CI run 42524341097 与旧设备
> 真实应用域默认交互 Bash/持久 PTY 输入/resize/reconnect/PRoot 开发门禁均已通过。
> v0.4.34 变更(Tier P shim):真实应用域 trace 确认 libtinfo safe-open 无条件调用
> setfsuid/setfsgid 触发 SIGSYS;仅拦截 ncurses 两个打开入口,逐次确认线程全部
> real/effective/saved/fs 身份一致且非 root、capabilities 全空后直接内核 open。
> 身份不符拒绝,非 Tier P 透传;不拦截或伪造 setfsuid,不改设备策略。待 CI/设备验证。
> v0.4.33 变更(Tier P shell 入口):持久 PTY 系统 sh 的 WebSocket/resize/reconnect
> 已实测,但 daemon 直接 exec Bash shebang 包装器立即退出;bin/bash 改用同物理名
> 静态 ELF 入口,从 /proc/self/exe 定位 loader/Bash/shim 并单进程 --preload,
> 不释放 ELF、不接入 Ubuntu 后端;新增 Linux 实际执行/参数测试,待新版 APK 验收。
> v0.4.32 变更(包装器):真实 Bash 子进程仍能继承 wrapper 设置的 LD_PRELOAD,
> 不再依赖 shim 构造器清环境;direct 分支改用 loader --preload 单进程注入,
> 环境中移除 LD_PRELOAD,PRoot bind 分支不变。新增 Linux 与应用域 Bionic 子进程
> 门禁;新版 APK 尚待成功 CI/实机复测。
> v0.4.31 变更(实验门禁):源码预置实验排除固定 bun-pty musl 分支并保留显式拒绝,
> .so require 保留 CommonJS 字符串导出;持久 PTY 绑定必须指定预置入口,不再嵌入
> extensionless ELF。新增 Bun graph 无 ELF/摘要/依赖/16K/glibc 静态门禁与 Linux
> shell/普通及持久 PTY 实际执行,仍不批准实验产物集成 APK。
> v0.4.30 变更(交付链):Git preload 隔离修复已通过 APK 真实应用域门禁,原生
> PRoot 完整 apt/编译/Git HTTPS/PTY 无显式代理验收通过。新增手动固定源码
> 构建实验,在 Bun 编译期将 .so/.node 导入换成显式预置路径,不伪装 Bun 临时文件;
> 产物仅诊断,未通过闭包/许可/Android 准入前不得替换正式工件。
> v0.4.29 变更(交付链):原生 APK 应用域 Bash/V2/PTY 版本执行通过;Git launcher
> 进入 Bionic PRoot 前清除 glibc LD_PRELOAD,由 bind 提供 /etc,避免 Android
> linker 加载 glibc shim。新增直接/PRoot 分支环境断言,Git 待新版工件实测。
> v0.4.28 变更(§4.6):clone3 补丁不再借 close_range 系统调用号,直接将该调用点
> svc 改为 mov x0,#-ENOSYS,避免现代内核实现 close_range 后回退失效;兼容已有
> 补丁的调用号但仍校验指令,继续由 CI 和应用域执行门禁确认。
> v0.4.27 变更(交付链):对 patchelf 搬迁版本定义节却遗留 DT_VERDEF 旧地址的
> Bun ET_EXEC 增加节表/LOAD 映射校验后修复,仅改动态表地址;修复后设备诊断目录
> V2.2.6 与静态入口 PTY 0.4.0/protocol 7 实际执行成功,仍待 CI/真实应用域验收。
> v0.4.26 变更(§4.8):root 安装器/manager 新增显式 ci-validation 固定实例,
> 仅使用 /data/adb/andcode-ubuntu-ci,不接受任意路径、不覆盖现有开发实例;
> 用于可信 CI 镜像的独立实机验收,不改变普通用户联网阻塞或开放 APK 特权接口。
> v0.4.25 变更(交付链):固定摘要 V2.2.6 与 process-daemon 0.4.0 纳入原生载荷,
> PTY 通过自有静态入口从 /proc/self/exe 定位同目录 loader/daemon,不在 ELF
> PT_INTERP 固化随机 APK 安装路径,不解包可执行体。新增 V2/PTY 版本执行门禁,
> 待 CI/真实应用域验证,不提前声称 Web/工具/原生库闭包已自包含完成。
> v0.4.24 变更(§4.4/交付链):APK 首启动按 manifest/nativeLibraryDir 身份原子发布
> 只含数据和原生目录链接的农场,拒绝越界/链接父目录/ELF 数据/manifest 冲突,不删除旧版本。
> 原生模式禁止回退开发载荷,移除默认代理与禁 TLS 校验;Bash 已在旧设备真实应用域
> 从 nativeLibraryDir 启动,无需 relabel。Git 首测发现 PRoot 私有库搜索旧路径并已修正,
> 待 CI/实机重跑;V2/PTY/正式签名/locked 交付仍未闭合。
> v0.4.23 变更(交付链):源码核实 glibc loader 用 libc.so.6 SONAME 识别 libc 并
> 调用 __libc_early_init,因此 libc 自身 SONAME 也必须保留,仅调用者 NEEDED 改物理名。
> 上条的重复 loader 是待证假设,不是已证实根因;实际 Bash 执行仍是强制门禁。
> v0.4.22 变更(交付链):实际执行门禁发现 Tier P Bash SIGSEGV,不允许只靠静态
> 审计放行;保留 loader 原 SONAME 及 libc 对它的 NEEDED,显式加载仅改物理文件名,
> 避免重复加载 ld.so。该修正仍需 CI 验证;PRoot IME 往返 resize/SIGWINCH 已实测。
> v0.4.21 变更(§4.4/CI):新增依赖原生工件的 debug APK 构建/Lint/逐字节载荷核验,
> 自有终端 JNI 显式 16K LOAD 对齐;修正 V2 loader 路径为注册物理名。仍是中间 APK,
> 未宣称 V2/PTY/首启动初始化/签名/locked 实机交付已完成。
> v0.4.20 变更(交付链):Tier P 同步改写 PRoot Bionic 私有共享库 SONAME/NEEDED,
> glibc 库名按已注册 slug 净化;均需 CI/实机验证,不改变 guest Ubuntu ELF。
> v0.4.19 变更(§4.4/交付链):Gradle 可显式接收 CI native 中间工件,保留物理名 ELF
> 不剥离并要求安装解压至 nativeLibraryDir;数据单独经 assets,禁止 ELF 混入数据。
> 此为打包接线而非可用自包含交付,V2/PTY/启动器/应用首启动数据初始化仍待闭合。
> v0.4.18 变更(交付链):修复 manifest 对扁平 lib/ 的 kind/SONAME 映射、launcher
> 与第三方许可证误分类及 git 重复物理名;物理冲突必须失败。修复 launcher PRoot
> argv 数组越界,新增 Linux ASan/UBSan 参数保真测试,导出 Tier P native 中间工件。
> Ubuntu 原生 arm64 CI 首跑已通过;仍未验证可信 CI 镜像设备安装或 locked APK。
> v0.4.17 变更(§4.8):只读诊断确认旧设备受限网络模式/BPF RESTRICTED_MATCH
> 阻断 UID 60000;APK UID 有放行位。不改网络策略或借 UID 绕过,chroot 联网仍失败。
> v0.4.16 变更(§4.8/交付链):CI 增加 Android 专用 bundle 副本,seccomp 七处校验
> 与重复执行摘要不变门禁后才 Tier P 物理化;标准 Linux bundle 不打补丁。
> 该链仍待 CI 首跑,偏移不匹配必须失败,不动态猜偏移或给 apt 更新后的系统套补丁。
> v0.4.15 变更(§4.8):PRoot 新终端快照单个私有项目并映射 /workspace/项目名,
> 拒绝链接/越界/丢失项目;修复 Android /data/user/0 与 /data/data 别名误拒绝。
> 默认直连 UDP DNS 超时,改 TCP DNS 后应用域 HTTPS/严格 apt update/Git 成功;
> 此处直连仅指不使用显式 HTTP 代理,未停用设备现有 VPN。chroot 网络身份仍未解决。
> v0.4.14 变更(§4.8):设置页提供仅新终端生效的轻量 Bash/Ubuntu PRoot 开发选择,
> 默认 Bash;Ubuntu 缺实例拒绝设置,启动时失效明确失败,不静默切后端。
> Ubuntu 代理默认关闭且单独显式选择,不改已有终端/OpenCode/Web PTY,不映射项目。
> v0.4.13 变更(§4.8):真实 untrusted_app/Seccomp=2/Enforcing 下独立 PRoot
> Ubuntu 已通过显式代理 HTTPS/apt、hello、新编译 ELF、PTY/子进程和 libc 更新;
> 全程不修改 guest ELF。新增终端 andcode-ubuntu-proot 开发入口,退出返回轻量 Bash,
> 不接入 OpenCode/root 服务、不映射项目。默认直连、正式自包含与其它设备仍待验证。
> v0.4.12 变更(§4.8):chroot 实测代理 HTTPS/apt 安装 hello 与 libc 更新通过;
> 普通用户编译/16K LOAD/capabilities 清零/no-new-privs/PTY/退出码/stdin/前台清理通过,
> 但 UID 60000 代理网络超时,不得声称完整通过。devpts 改独立 newinstance,
> 避免 Android 宿主 ptmxmode=000。PRoot 应用域 Seccomp=2 下未修改 ELF 的 Base
> Bash/id 通过;开发归档将硬链接展开副本并规范绝对链接,完整 apt/编译仍在验证。
> v0.4.11 变更(§4.8):用户清理后设备可用空间约 54 GiB,解除空间阻塞。
> 增加固定摘要 Ubuntu Base 设备开发引导路径,不冒充 Docker/CI 镜像验证;
> 旧系统 Toybox bind mount 不适用,改用已有 bundle BusyBox 的 root 私有副本。
> loop 显式分配,卸载后检查内核是否已自动 detach,避免将 ENXIO 误判为泄漏。
> chroot 网络/apt/编译正在实机验证,PRoot 与 APK 后端接入仍待验证。
> v0.4.10 变更(§4.8):启动 Ubuntu 双后端工作,新增同源 Ubuntu 24.04 arm64
> 开发镜像配方与 root-only chroot 原型。会话使用私有 mount namespace/串行锁,
> 默认 setpriv 普通用户且清除 capabilities;admin 仅显式人工入口。不把特权入口
> 暴露给 APK 或模型。PRoot 仍为待应用域准入,轻量 Bash 不变。设备仅余 0.9 GiB,
> 完整镜像/apt/编译尚待 P0/P3 实机验证;Linux CI 不替代 Android 验证。
> v0.4.9 变更(§4.4):终端默认经补丁 loader 拉起预置 Bash --noprofile --rcfile
> term-bashrc -i;无载荷时明确提示回退系统 sh -i。首帧绑定 client/同步尺寸与绘制,
> 显式配置提示符;增加两行附加键,CTRL/ALT 点击锁定,方向键使用终端协议。
> 旧设备应用域发现 Bash 权限探测调用 faccessat2(439) 被 seccomp TRAP;
> patch-seccomp.sh 增加校验后的 -ENOSYS 回退,七处校验失败即非零退出。
> 实测新会话无需按回车即显示提示符,Bash 5.2.21/交互标志/PTY、附加键与跨页
> 同 PID 保留通过。CI 新增 Bash/依赖/许可收录,全打包与其它设备仍待 P3 验证。
> v0.4.8 变更(§4.4):共享抽屉补齐项目/设置图标;独立终端接通既有双指缩放
> 回调,按阈值逐级调整并保存 10–28 sp 字号,设置页恢复前台时同步滑块与预览。
> 旧设备已通过双指触控注入验证放大/缩小、上下界及反向调整、返回既有设置页
> 同步字号;导航图标已截图确认。其它设备的手势手感仍待 P3 实机验证。
> v0.4.7 变更(§4.4):新增原生项目导入/导出与设置页。SAF ZIP/目录复制到
> filesDir/projects,暂存完成后发布且不覆盖;ZIP 防路径穿越,限制 512 MiB /
> 20000 项/64 层;导出跳过链接/特殊文件,默认排除 .git,明确提示隐藏文件风险。
> 设置保存终端字号、亮屏、导出 .git 偏好;新终端使用选中项目,旧会话不自动 cd。
> 旧设备已验证 SAF ZIP 导入/导出内容往返、目录导入、偏好保存及项目终端起始目录;
> 其它文档提供器/Android 版本及大项目边界待 P3 实机验证。
> v0.4.6 变更(§4.4):Web/终端抽屉“主页”显式跳转 HomeActivity 并清理其上返回栈,
> 不再以 finish() 假定主页存在。Web 页销毁前取消自动配对重试,迟到的服务回调/
> 页面回调检查 Activity 存活状态;WebView 从父视图移除后再 destroy。
> 旧设备验证无主页返回栈及正常往返场景,应用/serve PID 保持,无新致命异常或
> destroyed WebView 警告;其它 Android/WebView 版本仍待 P3 实机验证。
> v0.4.5 变更(§4.4):Web 终端增加 Android IME hints 与本地退格哨兵;
> 解决 LatinIME 英文整词组合不可见及隐藏 textarea 为空导致退格失效。
> 旧设备已用屏幕软键盘验证逐字输入、空格、退格、回车和 echo 回显;
> 中文候选词及其它第三方输入法待 P3 实机验证,不以粘贴成功代替输入法测试。
> v0.4.4 变更(§4.4):终端页改为手动启动 opencode 的交互 shell,同进程内跨页面
> 保留 TerminalSession;终端/Web 页均有悬浮球导航。Web PTY 改用上游
> `OPENCODE_PTY_BIN` 指向可执行预置副本,`OPENCODE_PTY_SOCKET_DIR` 指向
> filesDir(完整 socket 路径 <104 字节,不使用易清理的 cacheDir)。旧设备应用域
> 实测创建终端并回显 `ANDCODE_PTY_OK`;当前依赖 root 辅助的开发部署,不代表
> locked 设备完整自包含 APK 已交付。正式 jniLibs/CI 闭包集成仍待完成。
> v0.4.3 变更(Tier P 桌面级 Web UI 落地,§4.4 扩充): OpenCode 2.0 桌面界面以
> **"on-device serve + WebView"** 形态交付——`opencode serve --port 4096
> --hostname 127.0.0.1` 由 ServeManager 在应用域托管(补丁 loader 直拉,环境同
> scripts/app-launch-oc.sh),SessionService(specialUse FGS)承接常驻;前端
> SPA 在 WebView 渲染,`127.0.0.1` 明文仅经 networkSecurityConfig 定向放行
> (其余流量仍强制 https)。**配对自动化**: serve 每次启动都生成新的 server
> password,ServeManager 从 serve stdout 实时捕获并注入轮询式 JS,WebView 自动
> 完成"使用密码"配对(serve 经 ld-linux 直 exec 时 Bun 自 respawn 会把参数当
> ELF 加载,/proc/self/exe 指向 loader——serve 单进程直跑可绕开,pair 及
> 自 respawn 场景仍需 launcher ELF 包装,见待办)。真机实测:自动配对 +
> 端到端模型会话(arjata/gpt-oss-120b)于 APK 内全通,Web 端复用 V1 同一
> 数据目录(会话历史互通)。
> v0.4.2 变更(真机 Tier P 应用域攻坚,§4.4/§4.6 扩充): ①**wrapper 渲染补回
> `#!` 前缀**(pack-bundle printf 丢 `#!` 导致真 tty 下裸 `/bin/sh` 变交互式
> shell 卡死整条链);②launcher proot 分支 argv 错位修复(argv[0] 槽位必须
> 是 proot/loader 本身);③**应用域 seccomp 兼容**: 部分 4.9-perf 内核 + GSI
> 的 zygote seccomp 策略对 set_robust_list/rseq/clone3 直接 TRAP(SIGSYS),
> glibc 二进制启动即死 —— bundle 的 ld.so/libc.so.6 需打 seccomp 兼容补丁
> (scripts/patch-seccomp.sh,set_robust_list/rseq→sched_yield、clone3→
> close_range 触发 ENOSYS 回退)+ `GLIBC_TUNABLES=glibc.pthread.rseq=0`;
> ④**BUN_TMPDIR 必须指向应用可写目录**(Bun 提取 libopentui 等内嵌原生库
> 用 BUN_TMPDIR 而非 TMPDIR,否则 dlopen 拿到 /$bunfs 虚拟路径报 ENOENT);
> ⑤TUI 模式跳过 proot(ANDCODE_IN_PROOT=1),可写状态(HOME/TMPDIR/
> PROOT_TMP_DIR)全部位于应用 filesDir(bundle 本体 apk_data_file 只读)。
> 真机实测:opencode TUI 于自研 APK 终端内完整渲染并可用会话。
> v0.4.1 变更(真机 P0 三大发现,§4.5 重写): ①**LD_PRELOAD 无法拦截 glibc 内部
> fopen("/etc/resolv.conf")**,shim 对 glibc-internal /etc 读取无效 → Tier A/M 的
> /etc 重定向改由 **proot 用户态 bind**(Termux bionic 构建,GPL-2.0 独立聚合)承担,
> shim 保留为深层防御;②git 助手改**静态 musl launcher**(规避 shell spawn 异常);
> ③**移动/受管网络常阻断 UDP 53**,resolv.conf 强制 `options use-vc`(TCP DNS)。
> 真机(Android 13 GSI)实测:冒烟 7/7、opencode 运行、git https 全链路打通。
> v0.4 变更: **平台基线钉死 Android 12+ (minSdk 31)、APK targetSdk/compileSdk 37.2**;
> 移除 targetSdk 28 取巧,Tier P 改用 jniLibs 提取(nativeLibraryDir 可执行)方案,
> 新增 W^X/JIT、16K 页对齐、前台服务类型等适配项。
> v0.3 变更: **去除对 Termux 等独立宿主 App 的依赖**,三种交付形态全部自包含
> (Magisk 模块 / adb 包 / 自研最小 APK)。Termux 降级为附录中的可选替代。
> v0.2 变更: 构建基线切换为 Ubuntu 24.04 arm64 (glibc 2.39)。
>
> 目标: 在 Android arm64 设备上运行 opencode(终端 AI 编码代理),并提供一套
> **兼容性 Linux arm64 构建环境**(基线: Ubuntu 24.04 arm64)——该环境下构建出的原生程序可在 glibc ≥ 2.39 的标准 Linux arm64
> 设备(Ubuntu 24.04+/Debian 13+/云服务器等)上直接运行。

---

## 1. 目标与硬约束

### 1.1 设计原则、平台基线与设备矩阵

**核心原则(自包含)**:除 Android 系统本身外,不要求用户安装任何第三方独立程式
(不用 Termux、不依赖 proot-distro 发行版脚本)。所有宿主能力(终端、SSH、
自启动、进程守护)要么由系统入口提供,要么内嵌在我们的交付物里。

**平台基线(钉死)**:

| 项 | 取值 | 含义 |
|---|---|---|
| 最低系统 | **Android 12 (API 31)** | Phantom Process Killer(12 引入)全程伴随,必须在所有形态内置对策 |
| APK compileSdk | **37.2** | 按最新 SDK 构建,可用最新 API/行为 |
| APK targetSdk | **37.2** | 全量接受新平台行为:数据目录 exec 禁令、W^X、FGS 类型强制、edge-to-edge 等;**不使用 targetSdk 28 取巧** |
| 交付物运行环境 | arm64-only | 含 4K 与 16K 页设备(见 §1.2.8) |

| 设备类别 | Root | 可用入口 | 适用交付形态 |
|---|---|---|---|
| A. Bootloader locked | ✗ | ① adb shell(含 Android 11+ 无线调试,免数据线);② 侧载/商店安装我们的 APK | Tier A(adb 包)/ Tier P(自研 APK) |
| B. Bootloader unlocked + root | ✓ | 上述全部 + su/Magisk/开机脚本 | **Tier M(Magisk 模块,首选)**,兼容 A/P |

### 1.2 Android 平台硬约束(设计必须遵守)

1. **libc 不同**:Android 用户态是 Bionic,不是 glibc。glibc 链接的二进制必须
   携带自己的动态链接器与库(本设计的 **glibc sysroot + loader 包装器**,见 §4.1),
   或运行在 chroot 内。
2. **/sdcard 系挂载为 noexec**:所有可执行文件必须放在应用私有目录、
   `/data/local/tmp` 或 `/data/adb/` 下。**任何方案都不允许把 ELF 放在共享存储。**
3. **数据目录 exec 禁令与 W^X(targetSdk ≥ 29 全量生效)**:
   - targetSdk ≥ 29 的应用被 SELinux 域禁止 exec 应用可写数据目录内的 ELF;
     同时强制 W^X(不得匿名 RWX 映射)。
   - **Tier P 的标准解法:JNI 库提取**——所有随包 ELF(opencode、glibc loader、
     git、busybox、dropbear 及其 .so)以 `lib*.so` 形式打入 APK 的
     `jniLibs/arm64-v8a/`,安装时由系统解压到 `nativeLibraryDir`
     (`/data/app/.../lib/arm64/`),该目录**允许 exec**。
   - JIT(JSC):若 Bun 的 JIT 在 W^X 下被拒,回退 `BUN_JSC_useJIT=0`
     (Bun 支持 `BUN_JSC_*` 环境变量),P0 实测定级。
   - 收益:targetSdk 37.2 使 APK **可上架 Google Play**(需满足 §1.2.8 的 16K
     页要求);发布渠道双轨:Play + GitHub Releases/F-Droid。
4. **Android 12+ Phantom Process Killer**:后台 app 的子进程超过阈值(默认
   32 个 / 10 分钟空闲)会被静默杀掉。opencode 会派生 LSP、git、shell 等子进程,
   属于高危场景,需要规避(见 §4.6)。
5. **SELinux**:locked 设备上 shell 域可执行 `/data/local/tmp` 内的 ELF;APK 域
   可执行 `nativeLibraryDir` 内的 ELF(经 jniLibs 提取,见 §1.2.3);都不能碰
   `/lib/ld-linux-aarch64.so.1` 这类绝对 interpreter 路径(一律显式 loader 调用)。
6. **只读的 /etc**:glibc 运行期要读 `/etc/resolv.conf`、`/etc/passwd` 等,
   Android 的 `/etc` 不可写。用我们自研的 **LD_PRELOAD 重定向 shim** 解决(§4.5),
   不为此引入 proot。
7. **真 root(chroot)无上述大部分问题**,Tier M 优先用真 chroot。
8. **16K 页大小设备(Android 15+ 部分机型,Play 对含 NDK 代码应用强制)**:
   - Debian/Ubuntu arm64 工具链默认 `-z max-page-size=65536`,基线 glibc/sysroot
     的 ELF 天然 ≥16K 对齐,**无需重编**;
   - APK 内自有 NDK 代码(jackpal fork 的本地库)必须以 16K 对齐编译
     (`-Wl,-z,max-page-size=16384`),CI 加对齐检查;
   - jniLibs 提取的 glibc ELF 同样受益于上述基线对齐,直接可跑。

### 1.3 opencode 侧的事实假设(Phase 0 逐条验证)

- opencode 由 TypeScript 核心(以 Bun `--compile` 打包为单一可执行文件)+
  Go 编写的 Bubble Tea TUI 组成,官方发布 **linux-arm64 (glibc)** 产物。
- 运行期依赖:`git`(必需)、`rg` 等(增强);认证默认走浏览器 OAuth,
  但支持 API key / 环境变量注入(可完全绕开浏览器)。
- 先行者 `claude-code-termux`(MIT)宣称 Bun 编译产物可在无 proot 的
  glibc 环境下跑通——支持"loader 包装器 + shim"这条最轻路径的可行性。
- **待 P0 核实的关键项**(§4.1 "运行期不落盘"约束是否可满足):
  opencode 是否存在运行期释放/调用 ELF 的行为(如释放 Go TUI 二进制),
  以及是否有预置路径/环境变量机制可指向我们预装的副本。
- 若上述任一假设不成立,风险与备选见 §7。

---

## 2. 总体架构

一句话:**一套构建基线,一个自包含交付包,三种安装形态。**

```
                    ┌────────────────────────────────────────┐
                    │  兼容性构建基线 (baseline/)              │
                    │  Ubuntu 24.04 arm64 · glibc 2.39 · GCC13 │
                    └───────────────┬────────────────────────┘
                                    │
                     ┌──────────────▼───────────────┐
                     │  自包含交付包 andcode-bundle   │
                     │  (§4.1: 同一份内容,三种宿主)  │
                     └──┬──────────────┬──────────┬─┘
                        ▼              ▼          ▼
          ┌──────────────────┐ ┌────────────────┐ ┌──────────────────┐
          │ Tier M (root)    │ │ Tier A (locked)│ │ Tier P (locked)  │
          │ Magisk 模块      │ │ adb 直推包      │ │ 自研最小 APK      │
          │ /data/adb/andcode│ │ /data/local/tmp│ │ 内嵌交付包+终端   │
          │ 真 chroot        │ │ loader 包装器   │ │ targetSdk 37.2   │
          │ 开机自启 sshd    │ │ sshd (dropbear)│ │ 侧载 GitHub/F-Droid│
          │ 零 App 依赖      │ │ 零 App 依赖     │ │ 唯一交付物=1 个 APK│
          └──────────────────┘ └────────────────┘ └──────────────────┘
```

- **交付包是同一个 tarball**:glibc sysroot 闭包 + opencode + git + busybox +
  dropbear + shim,由三种宿主(模块安装脚本 / adb 推送脚本 / APK 资产)释放。
- 交互统一走两条路:**本机终端**(仅 Tier P 自带)与 **SSH**(三种形态都内置
  dropbear,任何 SSH 客户端可连,ConnectBot 等为可选客户端而非依赖)。
- 对 rooted 设备,Tier M 是零依赖、零 App、开机即用的最优解。

---

## 3. 兼容性 Linux arm64 构建基线(核心交付物)

### 3.1 基线规格

| 项 | 取值 | 理由 |
|---|---|---|
| 基线发行版 | **Ubuntu 24.04 LTS (Noble) arm64** | LTS 支持到 2029;LLVM/GCC/Go/Bun 生态新;GitHub Actions 原生 `ubuntu-24.04-arm` runner 与基线同构,CI 产物与本地逐字节可比 |
| libc | glibc 2.39(符号版本审计强制) | Ubuntu 24.04 自带版本 |
| libstdc++ | GCC 13 随包,或随产物捆绑 | bun 等需要 |
| 三元组 | `aarch64-unknown-linux-gnu` | 标准gnu |
| 禁止项 | 不得链接 Android NDK/Bionic;不得引入 ≥ 2.40 的 glibc 符号 | 兼容性红线 |

> **兼容性下限提示(选 Ubuntu 24.04 的代价)**:产物要求目标机 glibc ≥ 2.39,
> 即标准 Linux arm64 设备需为 Ubuntu ≥ 24.04 / Debian ≥ 13 (trixie) / 同代发行版。
> 对 Android 侧**无影响**——三种交付形态都随包携带基线 glibc,自包含。
> 若日后需要支持更老的标准设备(如 glibc 2.36 的 Raspberry Pi OS Bookworm),
> 追加第二条基线分层发布,不在本期范围。

### 3.2 三个等价构建入口(同一 sysroot,产物一致)

1. **设备端原生构建**:真 chroot(Tier M)或 qemu 内 `apt install build-essential`
   后直接构建——这也是"在 Android 上为 Linux arm64 开发"能力本身的一部分。
2. **PC 端 QEMU 构建**:`debootstrap --arch=arm64 noble` + `qemu-user-static`
   (binfmt),在 x86 PC 上跑出与设备端逐字节可比的产物。
3. **CI 构建**:GitHub Actions 原生 `ubuntu-24.04-arm` runner(与基线发行版同构,
   无需 QEMU;本地/设备端构建走 QEMU 或真机回退),跑 `baseline/Dockerfile`。

### 3.3 兼容性审计(强制门禁)

`baseline/check-compat.sh` 对每个交付 ELF:
- `file` 确认 `aarch64`;
- `objdump -T <elf> | grep -oE 'GLIBC_[0-9.]+' | sort -uV | last ≤ 2.39`;
- `readelf -d` 列出 NEEDED,逐个确认"来自基线 rootfs 或已捆绑到 `lib/`";
- interpreter 校验:交付包内的 glibc 二进制一律以**相对 loader 包装脚本**启动
  (见 §4.1),不依赖 `/lib/ld-linux-aarch64.so.1`。

---

## 4. 自包含交付包与三种安装形态

### 4.1 共同底座:自包含交付包 `andcode-bundle-arm64.tar.zst`

```
andcode/
├── root/
│   ├── lib/                  # 基线 glibc 2.39 的 ld-linux-aarch64.so.1 + 全部 NEEDED 库
│   ├── bin/opencode.bin*     # opencode 主体(ELF)
│   ├── bin/opencode          # §4.1.2 的 loader 包装器
│   ├── bin/opencode-tui*     # TUI 二进制**预置**(见下方"运行期不落盘"约束)
│   └── usr/                  # git、rg、dropbear/dbclient、busybox 等配套(同样 glibc 版)
├── shim/libandcode-shim.so   # §4.5 LD_PRELOAD 重定向 shim
├── etc/                      # resolv.conf / passwd / group / nsswitch.conf
├── sbin/andcode-entry        # 统一入口(命名规范见 docs/NAMING.md §4.2)
└── manifest                  # 版本、校验和、组件来源(供 notices 生成)
```

> 命名(逻辑名/物理名/slug/环境变量)一律遵循 **docs/NAMING.md**;
> Tier P 的 jniLibs 物理名与链接农场由该规范定义。

**运行期不落盘(exec)约束**:targetSdk 37.2 下,任何**运行时才写出的 ELF 都
不可执行**(数据目录 exec 禁令,§1.2.3)。因此:
- opencode 如有运行期解包行为(如把 Go TUI 二进制释放到 `~/.opencode/bin`),
  必须绕开:预置全部子二进制到交付包,并通过其支持的路径/PATH 机制指向预置版
  (具体机制在 P0 核实,记入 §1.3 验证清单);
- `TMPDIR`、`HOME` 指向可写目录没有问题——只要不往那里写**会被 exec 的文件**。

#### 4.1.2 loader 包装器(无 proot、无 root 运行 glibc 二进制的核心)

```sh
#!/system/bin/sh
ROOT="$(dirname "$(readlink -f "$0")")/../.."
export LD_PRELOAD="$ROOT/shim/libandcode-shim.so"
export HOME="$HOME" TMPDIR="$HOME/tmp" PATH="$ROOT/usr/bin:$PATH"
exec "$ROOT/lib/ld-linux-aarch64.so.1" \
     --library-path "$ROOT/lib" \
     --inhibit-cache \
     "$ROOT/bin/opencode.bin" "$@"
```

- `--inhibit-cache` + `--library-path` 绕开 `/etc/ld.so.cache` 与绝对 interpreter;
- busybox(静态、GPL-2.0)承担无 glibc 环境下的脚本粘合(sh/readlink/tar 等),
  以**独立程序聚合**方式随包分发(附源码获取地址,见 REUSE.md §3.4)。

### 4.2 Tier M — Magisk 模块(rooted 设备首选,零 App 依赖)

```
magisk-module/
├── module.prop
├── customize.sh              # 释放 bundle 到 /data/adb/andcode,生成 chroot
├── service.sh                # 开机:组装 chroot 挂载 → 起 dropbear → 起 opencode serve(可选)
└── uninstall.sh
```

- 运行方式:**真 chroot**(性能最优,无 proot 翻译开销),bind-mount
  `/dev`、`/proc`、`/sys`,可选 bind `/sdcard/Download` 为工作区(只放源码不放 ELF)。
- 开机自启由 Magisk `service.d` 机制完成,**无需任何 App**。
- 管理入口:`su -c /data/adb/andcode/sbin/andcode-entry`,或 `ssh localhost`(dropbear)。
- 2026-11-11 真机复测(v0.4.48):模型流量必须走显式代理——网关主机名仅在宿主
  代理侧 fake-IP DNS 可解析,设备直连(public DNS 或 netd)均无法解析;root shell
  经 `HTTPS_PROXY`(adb reverse loopback)+ `NODE_EXTRA_CA_CERTS` 完成文本与
  bash 工具两轮完整往返。该结果属 root 手动诊断,不等价于应用域验收;
  `home/.config/opencode/opencode.json`(0600)为本次写入的 arjata provider 配置。

### 4.3 Tier A — adb 直推包(locked 设备,零 App 依赖)

```bash
# scripts/deploy-adb.sh
adb push andcode-bundle-arm64.tar.zst /data/local/tmp/
adb shell "cd /data/local/tmp && busybox-arm-static tar --zstd -xf ... && ./sbin/andcode-entry sshd"
```

- 目标目录 `/data/local/tmp`:shell uid 可写可执行,locked 设备即可用;
  Android 11+ 可用无线调试,免数据线。
- 交互:PC 端 `adb shell` 直连,或包内 dropbear 起本地 sshd 后用任意 SSH
  客户端连 `127.0.0.1:2222`(adb `tcp` 转发或局域网)。
- 局限:adbd 断开不影响已 nohup 的进程,但设备重启后需重推/重跑(可接受,
  Tier A 定位为"开发者的第二形态")。

### 4.4 Tier P — 自研最小 APK(locked 设备的面向用户形态)

平台参数:`minSdk 31 · targetSdk/compileSdk 37.2 · arm64-v8a`(见 §1.1)。

- **一个 APK 即全部,内嵌交付包**。因数据目录 exec 禁令(§1.2.3),交付包按
  可执行性一分为二:
  - **只读执行体 → `jniLibs/arm64-v8a/`,以 `lib*.so` 命名**(如
    `libopencode.so`、`libgit.so`、`libbusybox.so`、`libld-linux.so` 及 glibc 的
    `lib*.so` 依赖):安装时系统自动解压到 `nativeLibraryDir`(可 exec);
    首启动把包装脚本、`etc/`、shim 配置写入 `filesDir` 并回指
    `nativeLibraryDir` 内的执行体;
  - **可写数据**(`HOME`、`TMPDIR`、git 仓库、配置、生成的 `resolv.conf`)
     → `filesDir`,绝无 ELF 落盘后 exec。
- **打包接线(v0.4.19)**:`pack-apk-libs.sh` 输出 `arm64-v8a`、`manifest.farm`
  与只含 data 的 `assets/andcode-runtime`;Gradle 显式
  `-PandcodeNativeDir=<工件目录>` 接收,要求基本载荷存在,不自动下载。使用
  legacy packaging 让系统安装时提取到 nativeLibraryDir,保留 `libandcode-*`
  文件内容不 strip。此中间工件尚非 V2/PTY 完整闭包,未宣称可用的自包含 APK。
- 终端 UI 已改用内嵌的 Termux terminal-emulator/terminal-view 模块
  (GPLv3,保留版权与 NOTICE,合并作品 AGPL-3.0-only,见 REUSE §2.1),
  不依赖用户安装 Termux App。
- **targetSdk 37.2 平台行为适配清单**:
  - 前台服务必须声明类型:用 `specialUse`(属性说明:承载开发工具长会话),
    并申请 `POST_NOTIFICATIONS` 运行时权限(通知才可见);
  - edge-to-edge 强制(targetSdk 35+):终端页按 WindowInsets 适配;
  - 预测性返回手势(Android 16+):终端页禁用 predictive back 以防误退;
  - scoped storage:项目通过 SAF 选择 ZIP 或文件夹,**复制**到 `filesDir/projects`,
    不把 content URI 当 POSIX 路径、不做源目录双向同步、不申请全盘存储权限。
- 常驻:前台服务(specialUse)+ wake-lock 承载 `opencode serve`/长会话(§4.6)。
- **双 UI(v0.4.4)**:
  - **终端页(v0.4.9)**:Termux 终端视图默认承载随包 Bash 交互 shell,不自动启动 TUI;
    显式补丁 loader + `bash --noprofile --rcfile <files/term-bashrc> -i`,预置副本
    优先来自 nativeLibraryDir/libandcode-bash.so,开发期使用 bundle/bin/bash.bin;
    不借用第三方宿主。配置设短提示符 `\W \$ `、HISTFILE,读取用户 ~/.bashrc,
    提供 `opencode` 函数(前台运行后返回 shell,不再 exec 替换 shell)。无 Bash
    时回退 `/system/bin/sh -i`,ENV 读取系统 mkshrc 并明确显示降级提示。
    SHELL 仍为可直接 exec 的系统 sh,避免下游 spawn 裸 glibc Bash 因 PT_INTERP 失败;
    正式 Bash 子 shell 启动器与完整 jniLibs 闭包仍待接线。
    首帧前绑定 TerminalViewClient,布局后同步尺寸与绘制,不注入回车模拟提示符。
    底部两行附加键含 ESC/TAB/CTRL/ALT/四方向、HOME/END/PGUP/PGDN、`/`/`-`/
    回车/IME;CTRL/ALT 为高亮锁定键(再点解除),其它非文本键由 TerminalView
    按应用模式编码,触摸按键不抢终端焦点;键盘展开时随 adjustResize 保持在其上方。
    附加键与注入在 TUI 正常态实机可达(v0.4.52 探针,见文件头 changelog):
    ← 移动光标、ESC 关闭 TUI 弹层、CTRL 粘滞(紫色高亮)+ 硬件 c 组成 Ctrl+C
    (编辑器内首次清行、空态重复按退出),TUI 可干净退回 shell 提示符;
    坐标验证须用设备真实像素(screencap 全分辨率),预览缩放图坐标会整体脱靶;
    拼音 IME 组合层会截走注入文本且候选栏遮挡附加键行,探针前先切英文 IME。
    Bash 依赖 libtinfo;基线 CI 收录二者版权与 GPLv3 文本并以 dpkg 实际版本登记。
    老内核的 faccessat2(439) TRAP 通过 libc 调用点合成 -ENOSYS 进入原生回退;
    补丁锁定 Ubuntu libc6 2.39-0ubuntu8.9 的字节/偏移,不匹配必须失败。
    静态 TerminalSession + 委托 ClientBridge
    让 Activity 离开/重建后复用进程与缓冲区,SessionService 保持宿主常驻;
    这仅是同一应用进程内的会话保留,不承诺 force-stop/系统杀进程后恢复。
    终端页和 Web 页的悬浮球均可打开抽屉导航;
    抽屉“主页”通过共享 `NavDrawer.goHome` 显式启动 HomeActivity
    (`CLEAR_TOP | SINGLE_TOP`,Home 为 singleTask),关闭来源页;即使来源页经
    开发入口直接启动、返回栈没有主页,也不会因裸 finish() 掉回系统桌面。
  - **桌面 Web 页(v0.4.3,已实机验证)**:`opencode serve --port 4096
    --hostname 127.0.0.1` 作为 OpenCode 2.0 桌面界面后端,前端 SPA 由 WebView
    加载 `http://127.0.0.1:4096/` 渲染。要点:
    - serve 由 `ServeManager` 在应用域托管:补丁 loader 直拉
      (`ld-linux --library-path … --inhibit-cache <oc2> serve …`),环境与
      scripts/app-launch-oc.sh 一致(HOME/TMPDIR/BUN_TMPDIR 在 filesDir,
      `GLIBC_TUNABLES=glibc.pthread.rseq=0`,代理走设备本地);stdout 全量落盘
      files/oc2-serve.log(不消费会撑满管道导致 serve 卡死)并从中解析
      server password;
    - 二进制路径解析兼容两种部署:jniLibs(`nativeLibraryDir/libandcode-oc2.so`
      + 同目录补丁 loader,最终形态)/ `/data/local/tmp`(开发期,当前实测路径);
    - **回环明文白名单**:manifest 用 networkSecurityConfig 仅对
      `127.0.0.1`/`localhost` 放行 cleartext,其余域名仍强制 https;
    - **配对自动化**:serve 每次启动生成新 server password(旧凭证失效),
      ServeManager 从 stdout 实时捕获,WebView 注入轮询式 JS(500ms × 20s,
      React 原生 setter 填充)自动完成"使用密码"配对;localStorage 持久登录
      (与桌面浏览器行为一致);
    - 已知缺口:`oc2` 经 ld-linux 直 exec 时 `/proc/self/exe` 指向 loader,
      Bun 自 respawn(如 `pair`)会把子命令参数当 ELF 路径加载而失败——
      serve 单进程直跑不触发;需 pair/后台自拉起时,须给 oc2 加 launcher
      ELF 包装(复用 bundle/launcher/launcher.c 模式,同 bin/git)。
    - **Web PTY(v0.4.4)**:预置 process-daemon v0.4.0(协议 7,REUSE §2.1),
      serve 与终端均设置 `OPENCODE_PTY_BIN` 指向可执行副本,不再用缓存 symlink
      (上游拒绝 symlink,还校验 uid/sha256)。上游另支持
      `OPENCODE_PTY_SOCKET_DIR`,设置为 `Context.getFilesDir()`;daemon 追加
      `opencode-pty-<uid>/<32 hex>.sock`,保留非 symlink/uid/0700 校验;
      Java 注入前检查完整路径 UTF-8 长度 <104 字节。不设置时默认 `/tmp`,
      Android 上 mkdir 返回 EROFS,daemon 退出后前端报 service.json ENOENT;
      单设 TMPDIR 不生效。cacheDir 曾观察到活跃 socket 被 unlink,故不用于端点。
    - **Web 页面退出(v0.4.6)**:配对重试使用 Activity 自有主线程 Handler,
      onDestroy 先清空队列;服务启动成功/失败、onPageFinished 与配对入口均检查
      isFinishing/isDestroyed 及 WebView 引用。销毁时先置空引用,停止加载、
      替换持有 Activity 的 WebViewClient,从父 ViewGroup 移除后再 destroy;
      不停止 SessionService/serve。旧设备修复前可复现退出到系统桌面,日志另有
      “Application attempted to call on a destroyed WebView”与 attached destroy
      警告,但未观察到本轮应用进程致命异常,不把这些警告等同已证实的崩溃栈。
    - **Web 输入法(v0.4.5)**:`WebActivity` 在本机页面加载后注入 APK asset
      `andcode-terminal-ime.js`,以 MutationObserver 适配 SPA 新挂载的终端页签。
      仅匹配 ghostty 的 `textarea[aria-label="Terminal input"]`,设置
      `inputmode=url`(LatinIME 英文逐字输入)与 `enterkeyhint=enter`;
      不修改聊天框、不使用密码类型或原生 JS bridge、不自行向 PTY 转发字符。
      隐藏 textarea 保留一个本地空格哨兵,使 IME 能生成退格 beforeinput;
      在上游事件处理完成后微任务恢复,组合输入期间不改值。上游继续负责
      beforeinput/composition/paste 去重与传输。当前 LatinIME 真机验证
      `echo okx` → 退格 → 回车得到 `ok`;中文候选与其它 IME **待 P3 实机验证**。
    - **开发部署与交付边界**:当前旧设备以 root 给预置 ELF/依赖设置
      apk_data_file 标签;PTY PT_INTERP 指向 `/data/local/tmp/ld` 的补丁 loader
      **普通文件**(原 symlink 在应用域不可达,仅改 PTY 标签不足以修复 EACCES)。
      库通过 LD_LIBRARY_PATH 寻址,须补齐 glibc 2.39 的 librt.so.1/libutil.so.1。
      真机已验证真实 untrusted_app 域 daemon → shell → Web 粘贴命令 → 回显;
      adb input text 经设备 IME 有乱码,不作为正常触屏输入的验证结论。
      正式 Tier P 必须使用 nativeLibraryDir 的预置副本与 launcher/loader 指路,
      禁止把 root/chcon 或固定 `/data/local/tmp/ld` 当成 locked 设备发布方案;
      完整 jniLibs 及 CI 打包后仍**待 P0/P3 实机验证**。
- **项目页/设置页(v0.4.7)**:共享抽屉增加“项目 · 导入 / 导出”和“设置”。
  - 共享导航为项目/设置提供与其它条目等尺寸、同主题 tint 的图标。
    独立终端双指展开/捏合调整字号,累计比例 >1.1 / <0.9 时增减 1 sp 并重置;
    达到 10–28 sp 边界也重置比例,反向缩放可立即响应。字号保存到相同偏好,
    设置页恢复前台时同步滑块与预览,不重建终端会话;不改变 Web 缩放行为。
  - 原生 Material 3 顶栏 + 分组卡片,跟随 DayNight 主题;导入入口并排,项目卡
    保留“打开终端”主操作、默认项目标识与折叠长路径,复制/导出归入更多菜单。
    设置按终端显示/导出隐私/工作区分组,字号提供即时预览,开关行可整行点击。
  - 项目使用唯一名称,先写 filesDir 下随机 `import-` 暂存目录,成功后 move 到
    projects;失败清理本任务暂存目录,不覆盖已有项目。后台任务用 ViewModel
    跨 Activity 旋转保留,不保证进程死亡后续传;异常进程退出可能遗留暂存目录。
  - ZIP 拒绝绝对路径、反斜杠、`.`/`..`、重复路径与目录数据;导入/导出限
    512 MiB 原始数据、20000 项、64 层。目录导入通过 DocumentsContract 读取。
    ZIP 不恢复 Unix 权限/符号链接元数据,仅复制数据文件;并不放宽数据目录 exec 禁令。
  - 导出通过 SAF 新建 ZIP,包含项目根目录;默认排除 .git,不跟随符号链接,
    跳过 socket 等特殊文件,失败尽力删除残缺输出。导出不是运行中项目的原子快照,
    不过滤 .env 等其它隐藏文件,UI 明确提示检查密钥。导入保留 ZIP 内原目录结构。
  - 可复制项目绝对路径到 Web“打开项目”;可设为新终端的 cwd,已有终端会话
    不注入 cd、不杀进程。ENV profile 不再强制 cd HOME。
  - 设置保存到 `andcode-settings`:终端字号(10–28 sp)、终端/Web 亮屏开关、
    导出是否包含 .git。onResume 应用显示设置,不重启会话,Web 内终端字号不受影响;
    API key 与提供商仍由上游 Web UI 管理,本页不新增凭据存储。
- **可选后端 CA(v0.4.40–v0.4.42)**:设置通过 SAF 导入单份 PEM,用户输入来自独立
  可信渠道的文件 SHA-256;64 KiB 上限,验证单证书/CA 签发用途/有效期,拒绝私钥、
  证书集合和链接。私有副本以内容摘要命名,每次启用启动前重新核对摘要及证书条件。
  导入不自动启用,产品默认关闭;只为新 OpenCode Web 后端及继承环境的子进程设置
  `NODE_EXTRA_CA_CERTS`,保留 Bun 内置根与主机名校验。关闭时清除继承的 CA/TLS/Bun
  覆盖参数,不修改系统/WebView/独立终端/Ubuntu 信任。导入、开关、清除选择不自动
  停止已有后端;手动停/启生效,清除选择也保留旧副本供仍在运行的进程读取。
  - 2026-11-09 同签名覆盖安装保留数据后,真实应用域 `untrusted_app`、UID10348、
    Seccomp=2、SELinux Enforcing 下确认默认关闭、错误摘要拒绝、正确 SAF 导入后
    仍关闭;显式启用并手动重启后新后端有 CA 环境变量且没有 TLS bypass。
  - 默认直连模型请求仍 `getaddrinfo EAI_AGAIN one.ai.api.service.arjata`,属于 DNS
    阶段,不是证书验证结论。隔离诊断后端显式使用 `127.0.0.1:7890` 时,关闭 CA
    得到 `UNABLE_TO_GET_ISSUER_CERT_LOCALLY`,启用后 `arjata/gpt-oss-120b` 返回预期
    文本,并观察到 SSE 增量文本、中断事件和同会话恢复成功。不把代理成功冒称直连
    成功,也不把诊断代理写成产品默认值。
  - v0.4.53 exposes that diagnostic proxy path as an explicit preference:
    `serve-loopback-proxy` defaults off in the network-trust settings card.
    A newly started managed serve receives `http_proxy`, `https_proxy`,
    `HTTP_PROXY` and `HTTPS_PROXY`, each set to `http://127.0.0.1:7890`.
    Inherited proxy variables are removed first; `NODE_TLS_REJECT_UNAUTHORIZED`
    remains stripped and trust still uses CustomCa / `NODE_EXTRA_CA_CERTS`.
    Changing the preference requires manually stopping and restarting serve;
    it does not configure a proxy service or change existing terminal sessions.
    On 2026-11-11 device `8c8da214`, SAF import of the independently supplied
    PEM digest `b842e18328d07799669a7286e266701951bc0cf7b5356c81926e12b6eb5e10dd`
    left trust disabled, as intended. Explicitly enabling CA trust and manually
    restarting serve produced `ANDCODE_PROXY_CA_OK` in the TUI (GPT-OSS 120B,
    3.7 seconds). The API confirmed `arjata/gpt-oss-120b`; the app-spawned
    backend had UID10356, Seccomp=2, untrusted_app and enforcing SELinux,
    all four proxy variables plus the digest-named CA file, and no TLS bypass.
    The next prompt executed `printf ANDCODE_PROXY_TOOL_OK` successfully, but
    the provider rejected the tool-result continuation with HTTP 400
    (`provider.invalid-request/openai_error`). A fresh-session API probe
    (`ses_e36211fc5ffeFH6xY2pRdXl5AL`) reproduced that failure after the shell
    executed its requested marker command. This verifies ordinary model
    traffic, not full tool round trips, direct DNS, other devices or networks
    (those remain pending P0/P3 on-device verification). This device retains
    both opt-ins enabled; the product defaults remain off. Evidence: local
    `a-33.png`, `a-34.png`, session `ses_e3626d3fdffeQ01kUkHNqN80Fi`.
  - 模型调用的无副作用 shell 命令返回预期标记,但工具结果回传后的 provider 请求
    HTTP 400(`provider.invalid-request/openai_error`);完整工具往返未通过,根因待查。
    验收后停止诊断后端、恢复设置 CA 关闭,手动重启的默认后端 PID20163 无
    `NODE_EXTRA_CA_CERTS` 或 TLS bypass。保留 CA 导入副本及所有测试会话,未删除
    用户数据。
  - 2026-11-10 授权设备 `8c8da214` 恢复连接后,默认 PID20163、模型及 CA 关闭
    环境保持不变。通过该后端 shell 启动独立诊断 PID8198,再次核对真实
    `untrusted_app`、UID10348、Seccomp=2,显式代理+既有 CA 下新会话
    `ses_e3ef3e479ffeeWTmyr2HK8a566` 连续两轮执行限定 `printf`、回传结果并
    得到最终标记;每轮 SSE 两个步骤完成,均有 tool.success/execution.succeeded,
    无 provider 错误。旧会话 `ses_e3fa8bb82ffeqj5z8cksogpUPH` 新请求仍在
    调用工具前 HTTP 400。故完整工具往返仅在上述新会话/网络条件下通过,历史
    回放根因未闭环,不把重试成功当协议修复或默认直连已恢复。
  - 经显式代理使用已有合成验收消息重建的 HTTP API 格式对照未执行任何工具,不保存凭据或
    原始消息;空/NULL 内容及 reasoning 字段最小对照均能成功,历史消息对照
    也存在 200/400 波动。它不是捕获的精确 OpenCode 请求,不能据此删除字段或
    静默修改旧会话。结束后 PID8198 已终止、诊断转发已移除;PID20163 可用且
    无 CA/TLS bypass,保留 CA 文件、全部会话、项目与 Ubuntu 实例。其它设备、
    网络、IME及旧会话恢复仍待 P0/P3 实机验证。
- **Managed Ubuntu PRoot serve (v0.4.54)**: `serve-proot-backend` is an independent,
  default-off setting for newly started managed servers. Manually stop and restart
  after changing it. The app requires the APK payload, runtime farm and installed
  `files/proot-rootfs`; failures never fall back to direct execution. PRoot starts
  `/lib/ld-linux-aarch64.so.1` inside Ubuntu to run the prebuilt oc2 payload.
  Native payloads and farm are bound at `/mnt/andcode-exe` and `/mnt/andcode-farm`;
  `files/home` is bound at `/root`, preserving existing configuration and sessions.
  Only explicitly enabled, revalidated CA data is bound at `/mnt/andcode-ca`.
  Guest `env -i` reconstructs PATH/HOME and optional proxy/CA variables; TLS
  verification remains enabled. Bun temporary files and PTY sockets use guest `/tmp`.
  Web/TUI still connect to shared loopback `127.0.0.1:4096`; the terminal-backend
  preference and its selected-project bind are separate and are not inherited here.
  PRoot's apparent root is the Android app UID, not host root; binds are writable
  and PRoot is not a sandbox. It does not modify root chroot instances or images.
  Device `8c8da214` passed Web HTTP 200, authenticated API, plain-text model reply,
  guest shell execution (Ubuntu 24.04.4, `/usr/bin/bash`, marker and exit 0), Web PTY
  `id`/OS/marker commands and exit 0, and `/root` writeback to `files/home`.
  The observed process chain was proot -> guest loader -> oc2 serve in untrusted_app,
  with explicit proxy/CA and no TLS bypass. Stop removed the process tree, port and
  terminal env fragment; restart restored service. Shell results were recorded,
  but model continuation returned provider HTTP 400 `openai_error` or 503; full
  tool round trips remain unresolved. Local evidence: `b-1.png` through `b-9.png`,
  `b-proot-evidence.json`, `b-proot-tool3.json`, `b-proot-osprobe2.json`.
  Review also preserves direct-backend inherited-trust cleanup and strips outer
  Bionic PRoot preload/trust overrides; current-process password handling omits
  password lines from new log entries. Historical logs are not rewritten.
  Other devices, locked delivery and abnormal-stop recovery remain pending P0/P3.
- UI:主页仪表盘 + 终端 + 桌面 Web + 项目 + 设置;sshd 管理/phantom-killer
  引导等扩展设置仍待实现,不把规划当作已经交付。

### 4.5 /etc 重定向:proot bind(主)+ LD_PRELOAD shim(辅)

**架构修正(v0.4.1,真机实测)**:LD_PRELOAD 只能拦截**跨对象 PLT 调用**;
`fopen("/etc/resolv.conf")` 等由 **glibc 内部直接发起**(隐藏别名,不走 PLT),
shim 拦截不到——真机 TEST-NET 探针 244ms 瞬断证实。因此:

| 层 | /etc 重定向机制 |
|---|---|
| **Tier A/M(主)** | **proot 用户态 bind**:`proot -b $ROOT/etc/resolv.conf:/etc/resolv.conf -b $ROOT/etc/ssl:/etc/ssl …`,覆盖一切子孙进程;proot(Termux bionic 构建,GPL-2.0)+ loader + libtalloc + libandroid-shmem 随 bundle 分发(独立聚合,manifest 记录) |
| **Tier M(root,可选)** | 真 bind mount(`mount --bind`),零开销 |
| **shim(辅)** | 保留:拦截**非 glibc 对象**的 /etc 访问(libcrypto/libssl 等走 PLT 的调用);并承担 LD_PRELOAD 自清(Bionic 子进程保护) |

**已知约束**:①proot 的 ptrace 拦截**不可嵌套**——wrapper/entry 以
`ANDCODE_IN_PROOT` 守卫,proot 内不再套 proot;②移动/受管网络常阻断 UDP 53
出站——`andcode-mkresolv` 生成的 resolv.conf 强制 `options use-vc timeout:3
attempts:2`(TCP DNS,真机实测必要);③Tier P(jniLibs + 数据目录)无法用
proot 进程树包住(无终端宿主概念)——Tier P 的 /etc 方案待 P3 设计
(候选:glibc sysconfdir 重编译或应用侧资产落位 + HOME 内配置)。

### 4.6 Android 12+ Phantom Process Killer 对策(三种形态共用)

```bash
adb shell "cmd device_config set_sync_disabled_for_tests persistent"
adb shell "device_config put activity_manager max_phantom_processes 2147483647"
```

- Tier M(root):安装时用 root 直接固化上述设置(并适配个别 ROM 的私有开关),
  重启后由 service.sh 复查——**唯一能自动持久化的形态**。
- Tier P(APK):设置页一键引导用户执行 adb 命令(展示可复制命令,含无线调试
  引导),叠加前台服务降低被杀概率;Android 12+ 为我们支持的最低版本,该对策
  对所有目标设备必然适用,不存在"老系统不需要"的分支。
- Tier A:部署脚本顺带执行;文档注明重启后需重跑。

### 4.7 认证与交互

1. **认证**:a) 从终端复制 OAuth URL 到任意浏览器,回贴回调;b) API key /
   环境变量注入(Tier P 设置页直接粘贴,完全无浏览器);c) Tier P 可用
   Intent 拉起默认浏览器完成回调。
2. **无头/远程**:`opencode serve` + 内置 dropbear → 任何 SSH 客户端或 PC
   浏览器(同 LAN)接入。这使"手机上的 opencode"也可以完全由 PC 驱动,
   触屏 TUI 只是其中一种入口而非必需。

---

### 4.8 Ubuntu 开发环境双后端(实施中,非已交付能力)

- Rootfs tool evaluation: `scripts/build-ubuntu-mmdebstrap.sh` delegates package
  bootstrap/dependency resolution to mmdebstrap in native arm64 CI. It retains
  tool versions/notices, signed indexes and binary/source package versions,
  then emits a validated tar archive and a separate 4 GiB ext4 image from the
  same configured tree. The optional CI experiment uses the existing Linux
  apt/non-root/compatibility gates; Docker stays the default. The archive is
  not an untrusted importer or a certified PRoot installation payload. Device
  instances remain independent and unchanged. The next isolated candidate pins
  all three suites to official HTTPS snapshot `20261110T000000Z`; exact sources,
  snapshot identity and signed indexes are retained without disabling apt checks.
  Earlier live-repository runs are not retroactively pinned. Host build-tool
  packages are version-recorded but not snapshot-pinned; no byte reproducibility
  or complete corresponding-source delivery is claimed.
  The next experiment also enables signed `deb-src` at the same snapshot and
  uses guest apt download-only/only-source mode for each exact installed source
  version. Source inputs and command/log hash inventories stay outside the image
  and repository; successful acquisition alone does not establish complete build
  inputs, applicable notices or source/relinking obligations.
  An additional PRoot archive is generated by the existing bounded link transformer
  using the trusted CI canonical archive digest. It is not an APK importer and
  does not replace any device instance; Android acceptance is still required.
  The optional image audit now compares the immutable original ext4 tree to the
  canonical archive, not the image copy modified by apt/compiler smoke tests.
  It rejects path/type/mode/owner/content/link drift and permits only mkfs's
  empty root-owned mode-0700 `lost+found` when absent from the archive. It does
  not certify timestamps, ACLs, xattrs or complete source delivery.

- 保留现有轻量 Bash;Ubuntu 24.04 arm64 来自同一官方镜像与软件源。chroot 使用
  独立 ext4 镜像,PRoot 使用独立可写实例,不共享 `/etc`、`/usr`、dpkg 数据库。
- `scripts/build-ubuntu-rootfs.sh` 在原生 arm64 CI 生成 4 GiB ext4 压缩镜像、
  SHA-256、dpkg 源包/二进制包版本清单、Docker digest 与配方 commit;保留许可证。
  rootfs tar 仅为可信 CI 中间产物,在提取前检查路径、重复项、链接祖先、特殊文件与
  setuid/setgid 位。APK 项目 ZIP 导入器绝不用于安装 rootfs。
- root-only `runtime/ubuntu/andcode-ubuntu-install` 固定安装至
  `/data/adb/andcode-ubuntu`,校验带外摘要、arm64、≥5 GiB 可用空间与精确镜像大小,
  拒绝覆盖旧实例;失败保留私有残留供检查,不自动删除用户数据。
- 管理入口 `andcode-ubuntu` 每个前台会话使用独立且递归 private 的 mount namespace,
  绑定最小 `/dev` 节点、PTY、proc,为 `/run` 与 `/dev/shm` 提供临时挂载;不绑定
  整个 Android `/data`、`/system` 或 `/sys`,不修改 SELinux。镜像与入口 root 私有,
  串行锁防止并发挂载同一文件系统。正常退出反向卸载,忙挂载不强制/懒卸载;
  清理失败保留锁待人工恢复,不宣称后台进程自动回收已解决。
- `shell`/`exec` 以 UID/GID 60000、Android inet 补充组 3003 运行,清空继承环境,
  清除 capability bounding/inheritable/ambient set 并设置 no-new-privs;目录 `/workspace`
  为该用户所有。`admin` 仅显式人工维护入口,允许 apt,不向模型提供 sudo/root。
  **chroot 不是安全沙箱**:同宿主 UID、proc 可见性、共享内核与 root 管理仍有风险。
- 尚不接入 APK/root IPC 或 OpenCode:需要先通过签名身份/peer-credential 认证通道、
  项目范围映射和真实设备准入,不能把 `su -c` 字符串拼接当作生产服务。
- PRoot 准入必须在真实 zygote 应用域验证 apt、新装 ELF、编译 ELF、PTY/子进程、
  DNS/HTTPS、libc 更新;不能以 adb root/run-as 成功替代,不能降低 targetSdk 或关闭
  SELinux 掩盖问题。旧设备真实应用域已通过显式代理模式的 apt/HTTPS、hello、
  gcc 新编译 ELF、PTY/子进程及 libc 2.39-0ubuntu8.7 → 8.9 更新后执行,guest ELF
  不打补丁。此结果是开发准入,不是默认直连或 locked 自包含交付认证。
- APK 终端提供 `andcode-ubuntu-proot [loopback-proxy] [命令...]` 显式开发入口;
  无参数启动交互 Bash,退出返回轻量 Bash,缺实例明确报错。不自动安装、不 su,
  This terminal entry is separate from the managed OpenCode/Web PTY backend.
  APK native payloads use the runtime farm; payload-free development uses
  `/data/local/tmp` PRoot.
  设置页可为新终端选择轻量 Bash(默认)或 Ubuntu PRoot,独立代理开关默认关闭。
  不重启已有会话;新会话快照选中项目名,入口仅绑定 `files/projects/<项目名>` 至
  `/workspace/<项目名>` 并从该目录起步,未选项目则 `/root`。拒绝项目根/父目录链接、
  越界名/PRoot bind 分隔符与丢失路径。不会递归检查项目内链接,且应用 UID 的宿主
  权限不变,不声称安全隔离。缺实例拒绝选择,启动后实例/项目丢失则明确失败,
  不静默降级到宿主执行。OpenCode/Web PTY 不使用此映射。
  旧设备应用域已验证项目写回/参数保真/stdin/退出码与拒绝错误项目。
  UDP 公共 DNS 超时,TCP DNS 返回正常答案;`use-vc` 后无显式代理的 HTTPS、严格
  apt update 与 Git HTTPS 成功,仍依赖设备现有 VPN/网络,不是 VPN 关闭后的测试。
  - On 2026-11-11 device `8c8da214`, a PRoot feasibility probe bound
    nativeLibraryDir (`libandcode-oc2.so`), the glibc farm and
    `files/term-serve.env` into the guest. The guest's unpatched
    `/lib/ld-linux-aarch64.so.1 --library-path farm/lib:exe` ran oc2 directly
    (`opencode v2.2.6`); shared loopback TCP reached the managed serve at
    `127.0.0.1:4096`. Guest DNS (1.1.1.1, use-vc) resolved public names but
    not the provider's VPN-only domain. The loopback proxy at `127.0.0.1:7890`
    reached that endpoint over TLS (401 without credentials). This initial
    feasibility probe is superseded by the opt-in managed PRoot serve integration
    and bounded on-device acceptance recorded in section 4.4 / v0.4.54.
- CI 为 Tier P 单独复制标准 bundle,执行 seccomp 七处字节校验/修改,再执行一次并
  验证 loader/libc SHA-256 不变,之后才重打包和物理化。标准 Linux bundle 保持原样;
  新基线字节不匹配时构建失败,不把补丁用于 PRoot guest 或 apt 更新后的 libc。
  Android 专用工件链、完整 jniLibs/Gradle 集成仍待 CI 首跑与 P0/P3 实机验证。
- Linux CI 独立 workflow 仅测试 rootfs apt 与普通用户编译运行、权限降级与兼容性,
  不证明 Android 支持。2026-11-09 用户清理后旧设备约有 54 GiB 可用空间。
  本机无 Docker,新增固定官方 SHA-256 Ubuntu Base 的原生设备开发引导路径,
  不等同 CI 构建验证。入口复制现有独立 BusyBox 至 root 私有目录处理 bind mount,
  不依赖第三方 App;旧 Toybox 对字符设备 bind 错误尝试 loop。loop 显式分配,
  内核自动 detach 后不再重复 detach。chroot UID 60000 网络仍失败,认证服务、
  项目映射、OpenCode/Web PTY 与自包含集成**待 P0/P3 实机验证**。
  操作与验收见 `docs/UBUNTU.md`。

## 5. 仓库结构(本仓库交付物)

```
andcode/
├── docs/                     # DESIGN.md · REUSE.md · NAMING.md
├── baseline/                 # 兼容性构建基线(§3)
│   ├── Dockerfile            # ubuntu:24.04 (arm64) + build-essential + git + bun
│   ├── make-rootfs.sh        # debootstrap arm64 rootfs(交付包 sysroot 来源)
│   └── check-compat.sh       # glibc/ELF 兼容性审计门禁
├── bundle/                   # 自包含交付包(§4.1)
│   ├── pack-bundle.sh        # 从基线 rootfs 抽取 glibc 闭包 + 组件 → tarball
│   ├── pack-apk-libs.sh      # 规范布局 → Tier P jniLibs 物理名重打包(NAMING §6.2)
│   ├── wrapper.sh.tpl        # loader 包装器模板
│   └── shim/                 # LD_PRELOAD 重定向 shim(C, AGPL)
├── magisk-module/            # Tier M(§4.2)
├── runtime/ubuntu/           # root chroot 原型管理/安装入口(§4.8)
├── scripts/
│   ├── deploy-adb.sh         # Tier A(§4.3)
│   ├── naming-lint.sh        # 命名规范 CI 门禁(NAMING §8)
│   └── smoke-test.sh         # 三形态共用验收(§6)
├── app/                      # Tier P 自研 APK(§4.4, Kotlin + jackpal 终端库 fork)
├── third_party/              # 指南与补丁(不 vendoring 源码,只放构建配方)
└── .github/workflows/andcode-ci.yml  # 基线 → 交付包 → 审计 → 冒烟 → 发布
```

---

## 6. 阶段计划与验收标准

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| **P0 可行性(2–3 天)** | adb 包(Tier A)手工路径:静态 busybox + sysroot + loader 包装器跑官方 opencode;同时精读 `claude-code-termux` 验证无 proot 路线;**另测 jniLibs 提取 + W^X/JSC JIT + TUI 释放行为**(Tier P 三大前提) | 在真机(任一 locked 设备)上完成一次真实编码会话;§1.3 假设逐条 ✓/✗;shim 缺口与 JIT 定级结论成形 |
| **P1 基线与交付包(1 周)** | `baseline/` 三件套 + `bundle/pack-bundle.sh` + shim v1 + CI | 产物过 `check-compat.sh`;同一 tarball 在 Tier A、真 chroot、原生 Ubuntu 24.04 arm64 三处均可运行 |
| **P2 Tier M(1 周)** | Magisk 模块 + service.sh 开机自启 + phantom-killer 固化 | B 类设备刷入后:重启自动 sshd,`ssh` 进会话即用;全程零第三方 App |
| **P3 Tier P APK(2–3 周)** | APK(minSdk 31 / targetSdk 37.2)、jniLibs 打包、jackpal 终端库最小 fork、设置页、specialUse 前台服务 | A 类设备侧载一个 APK 即完成安装→认证→会话;被切后台 30 分钟进程存活;16K 页设备(或开发者选项模拟)可运行 |
| **P4 打磨** | DNS/断网重连、OAuth 回调、`serve`+SSH 保底、多会话、发布工程(notices、F-Droid 元数据) | 冒烟矩阵全绿(见 REUSE/CI) |

---

## 7. 风险与备选

| # | 风险 | 影响 | 备选方案 |
|---|---|---|---|
| R1 | Bun/opencode 在"无 proot 的裸 glibc sysroot"下依赖未覆盖的系统文件(shim 缺口),或 JSC 在 targetSdk 28 之外的 JIT 受限 | Tier A/P 主路径受阻 | ① P0 即实测并补全 shim;② 引入单个静态 proot 二进制做 bind(GPL-2.0 独立聚合 + 源码提供);③ Tier M 真 chroot 不受影响 |
| R2 | Ubuntu 24.04 基线把标准设备兼容下限抬到 glibc ≥ 2.39 | 标准 Linux 目标面收窄 | ① Android 侧不受影响(bundle 自带 glibc);② 追加 Debian 12 第二基线分层发布;③ 简单工具改静态 musl |
| R3 | targetSdk 37.2 的运行期限制:数据目录 exec 禁令、W^X/JIT、运行期释放 ELF | Tier P 主路径受阻 | ① jniLibs 提取(`lib*.so` → `nativeLibraryDir`),可执行体零落盘(§4.4);② JIT 被拒则 `BUN_JSC_useJIT=0`(性能损失,实测定级);③ opencode 若必须运行期释放 ELF 且无法指向预置副本,为其打补丁改走预置路径(补丁归 AGPL) |
| R4 | ROM 差异(厂商杀后台、device_config 被锁) | 进程存活率 | Tier M root 固化为主推荐;`serve`+SSH 保底;主流 ROM 适配命令文档化 |
| R5 | opencode 上游快速迭代,产物结构变化 | 维护成本 | CI 定期重跑 P0 冒烟;假设以 `scripts/smoke-test.sh` 代码化 |
| R6 | jackpal 终端库停更、新 Android(targetSdk 35+ 行为)兼容性回归 | Tier P 终端体验 | 最小 fork 维持并完成 edge-to-edge/predictive back 适配;终端仅是入口之一,SSH/serve 保底;必要时评估 Termux 终端库(GPLv3,需独立 fork 仓库) |
| R7 | locked 设备 adb 不可用(未开 USB 调试) | Tier A 不可用 | Tier P 不依赖 adb,作为 locked 设备默认形态 |
| R8 | 16K 页设备上个别组件(非基线工具链产物)4K 对齐不兼容 | 部分 Android 15+ 机型失败 | 基线 glibc/Ubuntu 工具链默认 64K 对齐,理论免疫(§1.2.8);CI 加 `readelf -l` 段对齐检查;自有 NDK 代码强制 16K 对齐编译 |
| R9 | Android 14+/15+ 对 `device_config` 写入收紧(部分 ROM 需 root) | Tier A/P 的 phantom-killer 对策退化 | 前台服务 + 会话内子进程数量控制;Tier M root 固化为主推荐形态;文档按 ROM 列差异 |

---

## 8. 明确不做的事(范围边界)

- **不依赖 Termux/proot-distro 等第三方宿主 App**:它们至多出现在附录文档作为
  可选替代;交付物全部自包含(静态 busybox + 自带 sysroot + dropbear + 自研 shim)。
- 不移植到 Android 原生 Bionic(把 opencode 重链到 bionic):成本极高且破坏
  "产物可在标准 Linux arm64 运行"的目标。
- 不做 x86/模拟器路径:目标设备全部是 arm64。
- 不修改 Android 系统分区:所有方案在 `/data` 与应用沙箱内完成。

---

## 附录:可选替代路径(非本设计主路径,仅记录)

- **Termux + proot-distro**:社区最成熟的宿主,适合不想侧载 APK、能装 F-Droid
  Termux 的用户;我们的交付包理论上可直接在 proot Debian/Ubuntu 内运行
  (`bundle/` 设计刻意不假设宿主)。详见 REUSE.md 对 Termux 系许可证义务的分析。
- **ConnectBot 等第三方 SSH 客户端**:Tier A/M 的推荐客户端,但属可选工具,
  不构成依赖。
