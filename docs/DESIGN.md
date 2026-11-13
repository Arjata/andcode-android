# andcode — Design for porting opencode to Android arm64

> Version: v0.4.56 (design draft) · Date: 2026-11-14
> v0.4.56 change: documentation scope corrections only. Clarify Android-native Bionic versus Linux/glibc artifact boundaries, scoped data-directory execution and PRoot behavior, current managed-PRoot and jniLibs integration status, and repository/acceptance status. No code behavior changed.
> v0.4.55 (2026-11-11):
> v0.4.55 change: adopt the single-APK release goal. One CI-built canonical
> rootfs archive (dev-complete Ubuntu 24.04 arm64, gzip + SHA-256 + dpkg
> manifest) becomes the shared BUILD artifact for chroot and PRoot; device
> instances remain separate per tier (section 4.8 unchanged) and acceptance
> gates stay dual. The release APK embeds the archive in assets; first launch
> extracts it with a dependency-free in-app Java gzip/tar extractor that
> enforces the existing rootfs-tar safety checks, skips re-extraction on
> digest match and fails explicitly on error. No new third-party dependency
> and no native extractor binary are introduced. The legacy opencode v1
> payload (libandcode-opencode.so) is removed from the APK; the TUI already
> runs oc2 v2 through the opencode() shell function. Distribution is GitHub
> Release sideload only (Play channels do not fit this form factor). Tier M
> may later adopt the same archive as a directory-based chroot, pending
> device verification; the existing ubuntu.img and all device instances stay
> untouched.
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
> Single-APK first-launch validation (device 8c8da214, over WiFi adb after
> a USB flap): the CI artifact APK (640.5 MB, v1 payloads absent, the
> 193 MB .tgz stored verbatim) was installed with no prior data; the first
> start tap auto-extracted the embedded archive into a 566 MB proot-rootfs
> with the digest marker, published it, and brought up the proot -> guest
> loader -> oc2 serve chain with Web 200. Guest sanity via the session
> shell API: uname aarch64, gcc 13.3.0, git 2.43.0 and an /usr/bin/mawk
> alternatives symlink all resolved (exit 0). App storage after install is
> roughly 2.2 GB (APK + extracted native libs + rootfs). Terminal
> auto-entry and storage bind (same day): the terminal backend defaults
> to the Ubuntu rootfs when the canonical instance is ready (a missing
> instance auto-extracts in the background with an in-session wait), and
> both the serve guest and the terminal session bind /storage/emulated/0
> at /mnt/sdcard (Download verified read-write from the guest; the FUSE
> permission view governs visibility).
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
> v0.4.42 change (verification-boundary update): in the real app domain with explicit proxy+CA,
> a fresh session completed two consecutive full tool round trips; old sessions still return HTTP 400.
> No protocol changes or history deletion; no root-cause fix is claimed. Diagnostic PID8198 was
> terminated; default PID20163 retains CA disabled and original sessions. Excluding the GPL-noticed
> CRC object from OpenTUI passed Linux CI and 2304 CRC comparisons; license/relink/Android remain unapproved.
> v0.4.41 change (OpenTUI source experiment): pin standalone Zig 0.17.0 and existing OpenTUI/FFmpeg/
> zlib sources; enforce the video branch and 16K alignment at build time, gate ABI/exports/dependencies
> before full TUI staged-maps verification. No production APK integration; source/relink/license and
> Android approvals remain false. Optional CA device checks covered default-off/SAF/wrong-digest rejection/
> disabled-after-import/enabled and disabled restart environments. With explicit loopback proxy, CA-off
> rejects the certificate; CA-on passes streaming/interruption/resume. Tools execute but result continuation
> returns provider HTTP 400; full tool round trips failed. Direct connections still fail with DNS EAI_AGAIN.
> v0.4.40 change (optional CA): Tier P settings offer SAF single-PEM CA import/file-digest verification
> and a default-off additional-trust switch. Set NODE_EXTRA_CA_CERTS only for newly started OpenCode Web
> backends; retain built-in roots/hostname checks, without changing Android global/WebView/standalone
> terminal/Ubuntu trust. Import does not enable trust or fetch CA online; missing/changed/expired files
> block enabled startup. Disabling does not restart sessions; manually stop/start the backend. Local
> 26 Java checks, APK build/lint and Bun 1.4.4 real TLS on/off/hostname-rejection tests passed. CI
> 42609380415 (regular) and 42609429688 (source experiment) succeeded; arm64 logs confirm these CA gates;
> pending P0/P3 on-device verification.
> v0.4.39 change (experimental fff provenance): pin fff source/lock, zlob feature and Zig 0.16.0
> tool digest; offline Cargo rebuild checks ELF/16K/exports and real Bun indexing/search/glob before
> replacing experimental inputs. Retain selected crate archives, Cargo messages and GNU LOAD map/available
> input digests; explicitly record missing temporary inputs, without claiming per-section attribution or
> source/license closure. CI 42602199884 passed Linux experimental gates; the artifact's 3956 digests and
> manifest set were rechecked locally. Production APK unchanged; Android pending P0/P3 on-device verification.
> GNU synthetic linker stubs are listed separately, not misreported as missing physical inputs.
> v0.4.38 change (experimental watcher provenance): pin Parcel watcher source, node-addon-api and
> Node N-API header archives; compile an explicit Linux source list. Replace experimental inputs only
> after 16K/glibc/export checks and real Bun inotify creation-event/unsubscription tests. Reports distinguish
> npm and rebuilt provenance; failure does not replace inputs. Production APK unchanged; license and Android admission unapproved.
> v0.4.37 change (experimental native provenance): offline-build pinned bun-pty source/lock in arm64
> Linux CI (fetch first); replace only experimental npm glibc inputs after 16K/glibc/export gates. Bun
> then prestages by the new digest; ordinary PTY must actually map that copy. Retain build inputs/commands/
> tools/outputs; no proof of original npm ELF reproducibility or distribution/Android admission approval;
> production APK unchanged.
> v0.4.36 change (source-experiment closure): collect glibc/GCC shared libraries from an independent
> Ubuntu 24.04 CI sysroot; record image/dpkg/copyright/digests and recursively check NEEDED/required
> symbol versions. Run experimental serve/TUI with fixed experimental PT_INTERP/library directory and
> inspect mappings (explicit loader affects upstream self-spawn and is not equivalent). Production payload
> unchanged; distribution and Android admission remain unapproved.
> v0.4.35 change (Android libtinfo): actual initialization gates disproved v0.4.34 interception (internal
> binding bypasses shim); removed it. Build pinned Ubuntu ncurses source/security patches with
> HAVE_SETFSUID disabled, retaining upstream identity-preserving safe-open and kernel permission checks.
> Standard Linux bundle unchanged; Android replacement library/copyright/config/manifest synchronized.
> CI run 42524341097 and old-device real-app-domain default interactive Bash/persistent PTY input/
> resize/reconnect/PRoot development gates all passed.
> v0.4.34 change (Tier P shim): real-app-domain trace confirms unconditional libtinfo safe-open
> setfsuid/setfsgid calls trigger SIGSYS. Intercept only two ncurses open entry points; directly kernel-open
> only after checking all thread real/effective/saved/fs identities match, are non-root and have empty
> capabilities. Reject identity mismatch; pass through outside Tier P. No setfsuid interception/faking or
> device-policy changes. Pending CI/device verification.
> v0.4.33 change (Tier P shell entry): persistent PTY system-sh WebSocket/resize/reconnect verified,
> but daemon direct exec of the Bash shebang wrapper exits immediately. Replace bin/bash with a static
> ELF entry under the same physical name, finding loader/Bash/shim via /proc/self/exe and using single-process
> --preload. No ELF extraction or Ubuntu backend integration; add Linux execution/argument tests;
> pending new-APK acceptance.
> v0.4.32 change (wrappers): real Bash children still inherit wrapper-set LD_PRELOAD; stop relying
> on the shim constructor to clean the environment. Direct branch uses loader --preload for single-process
> injection and removes LD_PRELOAD from env; PRoot bind branch unchanged. Add Linux/app-domain Bionic-child
> gates; new APK pending successful CI/device retest.
> v0.4.31 change (experimental gates): source-prestage experiment excludes the pinned bun-pty musl branch
> with explicit rejection; .so require retains CommonJS string exports. Persistent PTY binding must specify
> the prestaged entry, no longer embedding extensionless ELF. Add Bun-graph no-ELF/digest/dependency/16K/glibc
> static gates and Linux shell/ordinary and persistent PTY execution; experimental APK integration unapproved.
> v0.4.30 change (delivery chain): Git preload isolation fix passed real APK app-domain gates; native
> PRoot full apt/compile/Git HTTPS/PTY acceptance passed without explicit proxy. Add a manual pinned-source
> build experiment replacing .so/.node imports with explicit prestaged paths during Bun compilation,
> without impersonating Bun temporary files. Diagnostic artifacts only; no production replacement before
> closure/license/Android admission gates pass.
> v0.4.29 change (delivery chain): native APK app-domain Bash/V2/PTY version execution passed. Git launcher
> clears glibc LD_PRELOAD before Bionic PRoot, providing /etc via bind to avoid Android linker loading
> the glibc shim. Add direct/PRoot environment assertions; Git awaits new-artifact device testing.
> v0.4.28 change (§4.6): clone3 patch no longer borrows the close_range syscall number; replace the call-site
> svc directly with mov x0,#-ENOSYS, avoiding failed fallback on modern kernels implementing close_range.
> Accept existing patched syscall numbers but still verify instructions; retain CI/app-domain execution gates.
> v0.4.27 change (delivery chain): validate section-table/LOAD mappings and repair Bun ET_EXEC when patchelf
> moves version definitions but leaves stale DT_VERDEF; change only the dynamic-table address. Device diagnostic
> directory V2.2.6 and static-entry PTY 0.4.0/protocol 7 execute after repair; CI/real app-domain acceptance pending.
> v0.4.26 change (§4.8): root installer/manager adds explicit fixed ci-validation instance, using only
> /data/adb/andcode-ubuntu-ci, accepting no arbitrary path or overwrite of existing development instances.
> For independent device acceptance of trusted CI images; does not resolve non-root networking blockage
> or expose privileged APK interfaces.
> v0.4.25 change (delivery chain): include fixed-digest V2.2.6 and process-daemon 0.4.0 in native payloads.
> Own static PTY entry finds sibling loader/daemon via /proc/self/exe; no random APK install path fixed in ELF
> PT_INTERP or executable extraction. Add V2/PTY version-execution gates; CI/real-app-domain checks pending,
> without prematurely claiming self-contained Web/tool/native-library closure.
> v0.4.24 change (§4.4/delivery chain): APK first launch atomically publishes a data/native-directory-link
> farm keyed by manifest/nativeLibraryDir identity. Reject escapes/symlink parents/ELF data/manifest conflicts;
> retain old versions. Native mode forbids development-payload fallback; remove default proxy and TLS bypass.
> Bash started from nativeLibraryDir in the old device's real app domain without relabeling. Initial Git test
> found and fixed stale PRoot private-library search paths; CI/device rerun pending. V2/PTY/production signing/
> locked delivery remain incomplete.
> v0.4.23 change (delivery chain): source confirms glibc loader identifies libc by libc.so.6 SONAME to call
> __libc_early_init; retain libc's own SONAME and rewrite only callers' NEEDED to physical names. The preceding
> duplicate-loader explanation is an unverified hypothesis, not confirmed root cause; actual Bash execution remains mandatory.
> v0.4.22 change (delivery chain): execution gate found Tier P Bash SIGSEGV; static audit alone cannot pass it.
> Retain original loader SONAME and libc's NEEDED for it, changing only physical filename for explicit loading
> to avoid duplicate ld.so. CI validation pending; PRoot IME round-trip resize/SIGWINCH verified on device.
> v0.4.21 change (§4.4/CI): add native-artifact-dependent debug APK build/Lint/bytewise payload checks;
> explicit 16K LOAD alignment for own terminal JNI; correct V2 loader path to registered physical name.
> Still an intermediate APK; no completed V2/PTY/first-launch initialization/signing/locked-device delivery claim.
> v0.4.20 change (delivery chain): Tier P rewrites PRoot Bionic private-library SONAME/NEEDED together;
> sanitize glibc names by registered slug. CI/device checks required; guest Ubuntu ELF unchanged.
> v0.4.19 change (§4.4/delivery chain): Gradle explicitly accepts CI native intermediate artifacts, preserves
> physical-name ELF without stripping, requires extraction to nativeLibraryDir at install; data uses assets
> separately with no ELF. Packaging wiring, not usable self-contained delivery; V2/PTY/launchers/app first-launch
> data initialization remain incomplete.
> v0.4.18 change (delivery chain): fix manifest kind/SONAME mapping for flat lib/, misclassified launchers/
> third-party licenses and duplicate Git physical names; physical collisions must fail. Fix launcher PRoot argv
> array overflow; add Linux ASan/UBSan argument-fidelity tests and export Tier P native intermediate artifacts.
> First native Ubuntu arm64 CI passed; trusted CI-image device installation and locked APK remain unverified.
> v0.4.17 change (§4.8): read-only diagnostics confirm old-device restricted-network mode/BPF RESTRICTED_MATCH
> blocks UID 60000 while APK UID has an allow bit. No network-policy changes or borrowed-UID bypass; chroot networking still fails.
> v0.4.16 change (§4.8/delivery chain): CI adds an Android-specific bundle copy; Tier P physicalization follows
> seven seccomp checks and unchanged-digest repeat-run gate. Standard Linux bundle unpatched. First CI run pending;
> offset mismatches must fail, with no guessed offsets or patching apt-updated systems.
> v0.4.15 change (§4.8): new PRoot terminals snapshot one private project and bind /workspace/<project-name>,
> rejecting links/escapes/missing projects; fix false rejection of Android /data/user/0 and /data/data aliases.
> Default direct UDP DNS timed out; TCP DNS enabled app-domain HTTPS/strict apt update/Git. Direct means no explicit
> HTTP proxy, not disabling the device's existing VPN. Chroot network identity remains unresolved.
> v0.4.14 change (§4.8): settings offer lightweight Bash/Ubuntu PRoot development selection for new terminals
> only, default Bash. Reject selection when Ubuntu instance missing; explicit startup failure rather than silent
> backend switch. Ubuntu proxy is a separate default-off opt-in; existing terminals/OpenCode/Web PTY unchanged, no project mapping.
> v0.4.13 change (§4.8): independent PRoot Ubuntu under real untrusted_app/Seccomp=2/Enforcing passed explicit-proxy
> HTTPS/apt, hello, freshly compiled ELF, PTY/children and libc update without guest ELF modification. Add terminal
> andcode-ubuntu-proot development entry returning to lightweight Bash on exit, without OpenCode/root-service integration
> or project mapping. Default direct mode, production self-containment and other devices remain unverified.
> v0.4.12 change (§4.8): chroot device tests passed proxy HTTPS/apt hello installation and libc update; non-root
> compilation/16K LOAD/cleared capabilities/no-new-privs/PTY/exit code/stdin/foreground cleanup passed. UID 60000 proxy
> networking timed out, so no full-pass claim. Use isolated devpts newinstance to avoid Android host ptmxmode=000.
> PRoot app-domain Seccomp=2 passed unmodified Base Bash/id; development archive materializes hardlinks and normalizes
> absolute links. Full apt/compilation verification ongoing.
> v0.4.11 change (§4.8): user cleanup freed about 54 GiB, removing the space blocker. Add fixed-digest Ubuntu Base
> device-development bootstrap, not Docker/CI-image validation. Old Toybox bind mount unsuitable; use a root-private
> copy of existing bundle BusyBox. Allocate loop explicitly and check kernel auto-detach after unmount to avoid
> treating ENXIO as leakage. Chroot network/apt/compile device checks ongoing; PRoot/APK backend integration pending.
> v0.4.10 change (§4.8): start Ubuntu dual-backend work with same-source Ubuntu 24.04 arm64 development-image recipe
> and root-only chroot prototype. Sessions use private mount namespace/serial lock; default setpriv non-root user
> with capabilities cleared, admin only by explicit manual entry. No privileged APK/model entry. PRoot app-domain
> admission pending; lightweight Bash unchanged. Only 0.9 GiB free on device; full image/apt/compile pending P0/P3
> on-device verification; Linux CI does not replace Android validation.
> v0.4.9 change (§4.4): terminal defaults to prestaged Bash --noprofile --rcfile term-bashrc -i via patched loader;
> absent payload explicitly announces system sh -i fallback. Bind client/sync size and drawing on first frame,
> configure prompt, add two extra-key rows with sticky CTRL/ALT and terminal-protocol arrows. Old app domain traps
> Bash faccessat2(439) permission probes; patch-seccomp.sh adds verified -ENOSYS fallback, failing nonzero on any
> of seven checks. Device tests show prompt without Enter; Bash 5.2.21/interactive flag/PTY/extra keys and same-PID
> cross-page retention pass. CI adds Bash/dependencies/licenses; full packaging/other devices pending P3 verification.
> v0.4.8 change (§4.4): add project/settings drawer icons; wire standalone-terminal pinch callbacks to stepwise
> 10–28 sp font adjustment/persistence; settings foreground resumption syncs slider/preview. Old-device two-finger
> injection verified zoom in/out, bounds, reversal and font synchronization on returning to existing settings;
> icons confirmed by screenshots. Gesture feel on other devices pending P3 on-device verification.
> v0.4.7 change (§4.4): add native project import/export and settings. SAF ZIP/directories copy to filesDir/projects,
> publish after staging without overwrite; ZIP traversal protection, limits 512 MiB / 20000 entries / 64 levels.
> Export skips links/special files, excludes .git by default, explicitly warns of hidden files. Settings retain font,
> keep-screen-on and export-.git preferences; new terminals use selected project, no automatic cd in existing sessions.
> Old device verified SAF ZIP content round trip, directory import, preferences and project terminal cwd;
> other providers/Android versions/large-project boundaries pending P3 on-device verification.
> v0.4.6 change (§4.4): Web/terminal drawer Home explicitly opens HomeActivity and clears its upper back stack,
> rather than assuming Home exists with finish(). Cancel pairing retries before Web page destruction; late service/
> page callbacks check Activity liveness; detach WebView before destroy. Old device tested missing-Home back stack
> and normal round trips with app/serve PID retained, no new fatal errors or destroyed-WebView warnings;
> other Android/WebView versions pending P3 on-device verification.
> v0.4.5 change (§4.4): add Android IME hints/local backspace sentinel to Web terminal, fixing invisible LatinIME
> English whole-word composition and empty-hidden-textarea backspace failure. Old-device soft keyboard verified
> character input, space, backspace, Enter and echo output; Chinese candidates/other third-party IMEs pending P3
> on-device verification. Successful paste is not an IME test substitute.
> v0.4.4 change (§4.4): terminal becomes an interactive shell with manual opencode launch; retain TerminalSession
> across pages within one process. Terminal/Web pages have floating navigation. Web PTY uses upstream
> `OPENCODE_PTY_BIN` for executable prestaged copy and `OPENCODE_PTY_SOCKET_DIR` for filesDir (full socket path
> <104 bytes, avoiding evictable cacheDir). Old-device app domain created a terminal and echoed `ANDCODE_PTY_OK`;
> current root-assisted development deployment is not complete locked-device self-contained APK delivery.
> Production jniLibs/CI closure integration remains pending.
> v0.4.3 change (Tier P desktop Web UI, §4.4 expanded): deliver OpenCode 2.0 desktop UI as
> **"on-device serve + WebView"** — `opencode serve --port 4096
> --hostname 127.0.0.1` managed by ServeManager in the app domain (direct patched-loader launch, same environment
> as scripts/app-launch-oc.sh), kept resident by SessionService (specialUse FGS). WebView renders the SPA;
> networkSecurityConfig permits cleartext only for `127.0.0.1` (all other traffic still requires https).
> **Automated pairing**: each serve start generates a new server password; ServeManager captures stdout live and
> injects polling JS for automatic WebView password pairing. With direct ld-linux exec, Bun self-respawn treats
> arguments as ELF because /proc/self/exe points to loader; direct single-process serve avoids it, but pair/
> self-respawn still require an ELF launcher wrapper (see TODO). Device tests passed automatic pairing and
> end-to-end model session (arjata/gpt-oss-120b) inside APK; Web shares V1 data directory/session history.
> v0.4.2 change (Tier P real-app-domain work, §4.4/§4.6 expanded): ①**restore wrapper-rendered `#!` prefix**
> (pack-bundle printf omitted `#!`, making bare `/bin/sh` interactive on a real tty and hanging the chain);
> ②fix launcher proot argv shift (argv[0] must be proot/loader itself); ③**app-domain seccomp compatibility**:
> some 4.9-perf kernels + GSI zygote seccomp directly TRAP(SIGSYS) set_robust_list/rseq/clone3, killing glibc
> binaries on startup. Bundle ld.so/libc.so.6 require compatibility patch (scripts/patch-seccomp.sh,
> set_robust_list/rseq→sched_yield, clone3→close_range to trigger ENOSYS fallback) plus
> `GLIBC_TUNABLES=glibc.pthread.rseq=0`; ④**BUN_TMPDIR must be app-writable** (Bun uses BUN_TMPDIR, not TMPDIR,
> to extract embedded native libraries such as libopentui; otherwise dlopen receives /$bunfs virtual paths and
> fails ENOENT); ⑤TUI skips proot (ANDCODE_IN_PROOT=1); all writable state (HOME/TMPDIR/PROOT_TMP_DIR) lives
> in app filesDir (bundle apk_data_file is read-only). Device test: opencode TUI fully renders and sessions
> work in our APK terminal.
> v0.4.1 change (three P0 device findings, §4.5 rewritten): ①**LD_PRELOAD cannot intercept glibc-internal
> fopen("/etc/resolv.conf")**; shim cannot redirect internal /etc reads. Tier A/M uses **proot userspace bind**
> (Termux bionic build, independent GPL-2.0 aggregation), retaining shim as defense in depth; ②git helpers use
> **static musl launcher** to avoid shell-spawn anomalies; ③**mobile/managed networks often block UDP 53**;
> force `options use-vc` (TCP DNS). Android 13 GSI device passed smoke 7/7, opencode execution and full Git HTTPS chain.
> v0.4 change: **pin Android 12+ (minSdk 31), APK targetSdk/compileSdk 37.2**; remove targetSdk 28 workaround,
> use jniLibs extraction (executable nativeLibraryDir) for Tier P, and add W^X/JIT, 16K alignment and FGS-type adaptations.
> v0.3 change: **remove dependency on standalone host apps such as Termux**; all three delivery forms are
> self-contained (Magisk module / adb package / own minimal APK). Termux becomes an optional appendix alternative.
> v0.2 change: switch build baseline to Ubuntu 24.04 arm64 (glibc 2.39).
>
> Goal: run opencode (terminal AI coding agent) on Android arm64 and provide a
> **compatible Linux arm64 build environment** (baseline: Ubuntu 24.04 arm64), whose native outputs run directly on standard Linux arm64
> devices with glibc ≥ 2.39 (Ubuntu 24.04+/Debian 13+/cloud servers, etc.).

---

## 1. Goals and hard constraints

### 1.1 Design principles, platform baseline and device matrix

**Core principle (self-contained)**: users need no third-party standalone program beyond Android
(no Termux or proot-distro distribution scripts). All host capabilities (terminal, SSH,
autostart and process supervision) come from system entry points or are embedded in our deliverables.

**Platform baseline (fixed)**:

| Item | Value | Meaning |
|---|---|---|
| Minimum OS | **Android 12 (API 31)** | Phantom Process Killer (introduced in 12) applies throughout; every form must include mitigations |
| APK compileSdk | **37.2** | Build with the latest SDK for current APIs/behavior |
| APK targetSdk | **37.2** | Accept current platform behavior including data-directory execution policy, mandatory FGS types and edge-to-edge; runtime W^X/JIT is a separate concern; **no targetSdk 28 workaround** |
| Artifact runtime | arm64-only | Includes 4K and 16K page devices (see §1.2.8) |

| Device class | Root | Available entry points | Applicable delivery forms |
|---|---|---|---|
| A. Bootloader locked | ✗ | ① adb shell (including Android 11+ wireless debugging, no cable); ② sideload/store-install our APK | Tier A (adb bundle) / Tier P (custom APK) |
| B. Bootloader unlocked + root | ✓ | All above + su/Magisk/boot scripts | **Tier M (Magisk module, preferred)**, also supports A/P |

### 1.2 Hard Android platform constraints (mandatory for the design)

1. **Different libc**: Android userspace uses Bionic, not glibc. Android-native JNI/platform
   code may use the Android NDK and Bionic. Linux compatibility payloads use glibc symbols
   no newer than 2.39 and carry their own dynamic linker/libraries (our **glibc sysroot +
   loader wrapper**, §4.1), or run inside a Linux guest. A glibc Linux artifact must never
   link against Bionic.
2. **/sdcard mounts are noexec**: executables must reside in app-private directories,
   `/data/local/tmp` or `/data/adb/`. **No approach may place ELF in shared storage.**
3. **Data-directory execution boundary**:
   - The targetSdk data-directory exec prohibition forbids direct execution of ELF from
     app-writable data directories. Tier P packaged executables are preinstalled by Android from
     `jniLibs/arm64-v8a/` into `nativeLibraryDir`; executable ELF is not extracted there at runtime.
   - **Tier P packaged payload solution: JNI library extraction** — package executable payloads (opencode, glibc loader,
     git, busybox, dropbear and their .so files) as `lib*.so` in APK
     `jniLibs/arm64-v8a/`; the system extracts them at install into `nativeLibraryDir`
     (`/data/app/.../lib/arm64/`).
   - Tested Ubuntu guest ELF may execute only through the validated PRoot path in §4.8. This is
     a scoped device-tested path, not blanket permission to execute ELF from app-writable data.
   - Android platform/SELinux execution policy and runtime W^X/JIT policy are distinct concerns.
     If runtime W^X policy rejects Bun JIT, assess `BUN_JSC_useJIT=0` on-device.
   - Benefit: targetSdk 37.2 makes the APK technically **eligible for Google Play** (subject to §1.2.8's 16K
     requirement). The current release channel is GitHub Release sideload; Play and F-Droid distribution are not currently enabled.
4. **Android 12+ Phantom Process Killer**: background-app children exceeding thresholds (default
   32 processes / 10 minutes idle) are silently killed. opencode spawns LSP, git, shell and other children,
   making it high risk and requiring mitigation (§4.6).
5. **SELinux**: on locked devices, shell domain can execute ELF in `/data/local/tmp`; APK domain
   can execute ELF in `nativeLibraryDir` (jniLibs extraction, §1.2.3). Neither can use
   absolute interpreter paths such as `/lib/ld-linux-aarch64.so.1` (always invoke loader explicitly).
6. **Read-only /etc**: Android `/etc` is unwritable. The shim can redirect external
   glibc-object PLT calls to selected `/etc` paths; it cannot intercept glibc-internal calls
   that bypass the PLT. Managed Ubuntu PRoot uses guest bind mounts for guest `/etc`.
   The shim is useful but not a universal `/etc` solution; see §4.5.
7. **Real root (chroot) avoids most of these issues**; Tier M prefers real chroot.
8. **16K-page devices (some Android 15+ devices; Play requires this for apps with NDK code)**:
   - Debian/Ubuntu arm64 toolchains default to `-z max-page-size=65536`; baseline glibc/sysroot
     ELF already has ≥16K alignment, **no rebuild required**;
   - Own APK NDK code (jackpal-fork native library) must compile with 16K alignment
     (`-Wl,-z,max-page-size=16384`), checked in CI;
   - jniLibs-extracted glibc ELF benefits from the same baseline alignment and runs directly.

### 1.3 Assumptions about opencode (verify individually in Phase 0)

- opencode combines a TypeScript core (single executable via Bun `--compile`) and
  a Go Bubble Tea TUI; official releases include **linux-arm64 (glibc)** artifacts.
- Runtime dependencies: `git` (required), `rg`, etc. (enhancements); authentication defaults to browser OAuth,
  but supports API-key/environment injection (fully bypassing the browser).
- Predecessor `claude-code-termux` (MIT) claims Bun-compiled outputs run in glibc without proot,
  supporting feasibility of the lightest "loader wrapper + shim" approach.
- **Key P0 checks** (whether §4.1's "no runtime executable writes" constraint can be met):
  whether opencode extracts/invokes ELF at runtime (e.g. Go TUI binary),
  and whether prestaged-path/environment mechanisms can point to our installed copies.
- If any assumption fails, see §7 for risks and alternatives.

---

## 2. Overall architecture

In one sentence: **one build baseline, one self-contained bundle, three installation forms.**

```
                    ┌────────────────────────────────────────┐
                    │  Compatibility baseline (baseline/)    │
                    │  Ubuntu 24.04 arm64 · glibc 2.39 · GCC13 │
                    └───────────────┬────────────────────────┘
                                    │
                     ┌──────────────▼───────────────┐
                     │ Self-contained andcode-bundle│
                     │ (§4.1: same data, three hosts)│
                     └──┬──────────────┬──────────┬─┘
                        ▼              ▼          ▼
          ┌──────────────────┐ ┌────────────────┐ ┌──────────────────┐
          │ Tier M (root)    │ │ Tier A (locked)│ │ Tier P (locked)  │
          │ Magisk module    │ │ adb-push bundle│ │ Own minimal APK  │
          │ /data/adb/andcode│ │ /data/local/tmp│ │ Bundle + terminal│
          │ Real chroot      │ │ loader wrapper │ │ targetSdk 37.2   │
          │ Boot-start sshd  │ │ sshd (dropbear)│ │ Sideload GitHub/F-Droid│
          │ No app dependency│ │ No app dependency│ │ Sole output=1 APK│
          └──────────────────┘ └────────────────┘ └──────────────────┘
```

- **The bundle is the same tarball**: glibc sysroot closure + opencode + git + busybox +
  dropbear + shim, extracted by three hosts (module installer / adb push script / APK assets).
- Two interaction paths: **local terminal** (bundled only in Tier P) and **SSH** (all three bundle
  dropbear; any SSH client works; ConnectBot and others are optional clients, not dependencies).
- For rooted devices, Tier M is the optimal zero-dependency, zero-app, ready-at-boot solution.

---

## 3. Compatible Linux arm64 build baseline (core deliverable)

### 3.1 Baseline specifications

| Item | Value | Rationale |
|---|---|---|
| Baseline distribution | **Ubuntu 24.04 LTS (Noble) arm64** | LTS through 2029; recent LLVM/GCC/Go/Bun ecosystem; native GitHub Actions `ubuntu-24.04-arm` runner matches baseline, allowing bytewise CI/local comparison |
| libc | glibc 2.39 (mandatory symbol-version audit) | Ubuntu 24.04 bundled version |
| libstdc++ | Bundled GCC 13, or shipped with artifacts | Required by bun and others |
| Triple | `aarch64-unknown-linux-gnu` | Standard GNU |
| Prohibited | Linux compatibility artifacts linking against Bionic; introducing glibc symbols ≥ 2.40 | Android-native JNI/platform code may use NDK/Bionic |

> **Compatibility floor (cost of Ubuntu 24.04)**: artifacts require target glibc ≥ 2.39,
> hence standard Linux arm64 must use Ubuntu ≥ 24.04 / Debian ≥ 13 (trixie) / contemporary distributions.
> **No effect on Android** — all three forms bundle baseline glibc and are self-contained.
> Supporting older standard devices later (e.g. Raspberry Pi OS Bookworm with glibc 2.36)
> would require a second baseline/release tier, outside current scope.

### 3.2 Three equivalent build entry points (same sysroot and outputs)

1. **Native device build**: build directly after `apt install build-essential` in real chroot (Tier M)
   or qemu — part of the capability to "develop for Linux arm64 on Android" itself.
2. **PC QEMU build**: `debootstrap --arch=arm64 noble` + `qemu-user-static`
   (binfmt), producing outputs on x86 PCs bytewise-comparable with device builds.
3. **CI build**: native GitHub Actions `ubuntu-24.04-arm` runner (matching baseline distribution,
   no QEMU; local/device builds fall back to QEMU or hardware), running `baseline/Dockerfile`.

### 3.3 Compatibility audit (mandatory gate)

`baseline/check-compat.sh` checks every delivered ELF:
- `file` confirms `aarch64`;
- `objdump -T <elf> | grep -oE 'GLIBC_[0-9.]+' | sort -uV | last ≤ 2.39`;
- `readelf -d` lists NEEDED, each verified as "from baseline rootfs or bundled in `lib/`";
- Interpreter check: all bundled glibc binaries start through **relative-loader wrapper scripts**
  (§4.1), without relying on `/lib/ld-linux-aarch64.so.1`.

---

## 4. Self-contained bundle and three installation forms

### 4.1 Shared foundation: self-contained bundle `andcode-bundle-arm64.tar.zst`

```
andcode/
├── root/
│   ├── lib/                  # Baseline glibc 2.39 ld-linux-aarch64.so.1 + all NEEDED libraries
│   ├── bin/opencode.bin*     # Main opencode ELF
│   ├── bin/opencode          # Loader wrapper from §4.1.2
│   ├── bin/opencode-tui*     # **Prestaged** TUI binary (see runtime-write constraint below)
│   └── usr/                  # git, rg, dropbear/dbclient, busybox, etc. (also glibc builds)
├── shim/libandcode-shim.so   # §4.5 LD_PRELOAD redirection shim
├── etc/                      # resolv.conf / passwd / group / nsswitch.conf
├── sbin/andcode-entry        # Unified entry (naming: docs/NAMING.md §4.2)
└── manifest                  # Versions, checksums, component origins (for notices generation)
```

> All naming (logical/physical names, slugs, environment variables) follows **docs/NAMING.md**;
> that specification defines Tier P jniLibs physical names and link farms.

**No runtime executable writes constraint**: with targetSdk 37.2, ELF written to an app-writable
data directory must not be directly executed (data-directory exec prohibition, §1.2.3). Therefore:
- Any opencode runtime extraction (e.g. Go TUI into `~/.opencode/bin`) must be bypassed:
  prestage all child binaries in the bundle and redirect supported path/PATH mechanisms to them
  (verify exact mechanism in P0 and record in §1.3 checklist);
- `TMPDIR` and `HOME` may be writable, provided no **files that will be exec'd** are written there.

#### 4.1.2 Loader wrapper (core of running glibc binaries without proot or root)

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

- `--inhibit-cache` + `--library-path` bypass `/etc/ld.so.cache` and absolute interpreter;
- busybox (static, GPL-2.0) supplies script glue without glibc (sh/readlink/tar, etc.),
  distributed as **aggregation of an independent program** with source URL (REUSE.md §3.4).

### 4.2 Tier M — Magisk module (preferred for rooted devices, no app dependency)

```
magisk-module/
├── module.prop
├── customize.sh              # Extract bundle to /data/adb/andcode and create chroot
├── service.sh                # Boot: mount chroot → start dropbear → optionally start opencode serve
└── uninstall.sh
```

- Execution: **real chroot** (best performance, no proot translation overhead), bind-mount
  `/dev`, `/proc`, `/sys`; optionally bind `/sdcard/Download` as workspace (source only, no ELF).
- Magisk `service.d` handles boot startup, **no app required**.
- Management: `su -c /data/adb/andcode/sbin/andcode-entry`, or `ssh localhost` (dropbear).
- 2026-11-11 device retest (v0.4.48): model traffic requires explicit proxy — gateway hostname resolves only
  in host-proxy fake-IP DNS, not device-direct public DNS/netd. Root shell completed two full text/bash-tool
  round trips through `HTTPS_PROXY` (adb reverse loopback) + `NODE_EXTRA_CA_CERTS`.
  This is manual root diagnostics, not equivalent to app-domain acceptance;
  `home/.config/opencode/opencode.json` (0600) contains the arjata provider configuration written for this test.

### 4.3 Tier A — adb-pushed bundle (locked devices, no app dependency)

```bash
# scripts/deploy-adb.sh
adb push andcode-bundle-arm64.tar.zst /data/local/tmp/
adb shell "cd /data/local/tmp && busybox-arm-static tar --zstd -xf ... && ./sbin/andcode-entry sshd"
```

- Target `/data/local/tmp`: writable/executable by shell uid, available on locked devices;
  Android 11+ wireless debugging needs no cable.
- Interaction: direct PC `adb shell`, or bundled dropbear local sshd with any SSH
  client connecting to `127.0.0.1:2222` (adb `tcp` forwarding or LAN).
- Limitation: adbd disconnect leaves nohup processes intact, but reboot requires re-push/re-run
  (acceptable: Tier A is the "developer's secondary form").

### 4.4 Tier P — Custom minimal APK (user-facing form for locked devices)

Platform parameters: `minSdk 31 · targetSdk/compileSdk 37.2 · arm64-v8a` (§1.1).

- **One APK contains everything, including the bundle**. Because of the data-directory exec prohibition (§1.2.3),
  split the bundle by executability:
  - **Read-only executables → `jniLibs/arm64-v8a/`, named `lib*.so`** (e.g.
    `libopencode.so`, `libgit.so`, `libbusybox.so`, `libld-linux.so` and glibc
    `lib*.so` dependencies): system installation extracts them to executable `nativeLibraryDir`;
    first launch writes wrapper scripts, `etc/` and shim configuration to `filesDir`, pointing back
    to executables in `nativeLibraryDir`;
  - **Writable data** (`HOME`, `TMPDIR`, git repositories, configuration, generated `resolv.conf`)
     → `filesDir`, never writing ELF there for subsequent exec.
- **Packaging wiring (v0.4.19)**: `pack-apk-libs.sh` emits `arm64-v8a`, `manifest.farm`
  and data-only `assets/andcode-runtime`; Gradle accepts them explicitly through
  `-PandcodeNativeDir=<artifact-directory>`, requiring basic payloads without automatic downloads. Use
  legacy packaging for system extraction into nativeLibraryDir at install; retain `libandcode-*`
  bytes without stripping. This intermediate artifact is not full V2/PTY closure or a claimed usable self-contained APK.
- **Single-APK release form (v0.4.55, implemented; device scope recorded in the changelog)**: release APK embeds
  `assets/andcode-rootfs/` (canonical dev-complete rootfs gzip archive using
  `.tgz` suffix — AGP asset merging automatically decompresses `.gz` assets; `noCompress tgz`
  retains archive bytes in APK, plus SHA-256 and dpkg version manifest). First launch uses an in-app pure Java
  gzip/tar extractor to install into
  `files/proot-rootfs` — no new third-party dependency or native extractor; the app itself does not extract
  and execute data-directory ELF (guest binaries run through the verified proot execution path). Enforce
  §4.8 rootfs-tar safety checks before extraction (paths/duplicates/escaping symlinks/special files; count stripped
  setuid/setgid bits; retain Debian alternatives and usrmerge symlinks according to proot translation semantics).
  Skip on digest match (no repeat extraction on in-place upgrade), fail explicitly; PRoot serve gate semantics
  remain unchanged (missing → explicit failure, no fallback). Exclude legacy opencode v1 (`libandcode-opencode.so`
  and wrapper) through `pack-apk-libs.sh --exclude` — both TUI
  `opencode()` and serve run oc2 v2; removal requires CI assertions and terminal-entry regression tests.
  Size budget: release APK about 700–800 MB (CI measurements authoritative), about 2 GB installed storage;
  GitHub Release sideload only, no Play channel. Release version bumps follow bundle
  `--name` consistently, eliminating hardcoding.
- Terminal UI now embeds Termux terminal-emulator/terminal-view modules
  (GPLv3, with copyright and license notices retained; AGPL-3.0-only does not relicense these components; REUSE §2.1),
  without requiring users to install Termux App.
- **targetSdk 37.2 platform-behavior adaptation checklist**:
  - Foreground services must declare a type: `specialUse` (property explanation: long development-tool sessions),
    and request runtime `POST_NOTIFICATIONS` permission for visible notifications;
  - Mandatory edge-to-edge (targetSdk 35+): terminal adapts using WindowInsets;
  - Predictive back (Android 16+): disabled in terminal to avoid accidental exit;
  - Scoped storage: SAF-selected ZIPs/folders are **copied** to `filesDir/projects`,
    without treating content URIs as POSIX paths, bidirectional source sync, or all-files storage permission.
- Residency: foreground service (specialUse) + wake-lock for `opencode serve`/long sessions (§4.6).
- **Dual UI (v0.4.4)**:
  - **Terminal page (v0.4.9)**: Termux view defaults to bundled interactive Bash, without auto-starting TUI;
    explicit patched loader + `bash --noprofile --rcfile <files/term-bashrc> -i`; prestaged copy
    preferably nativeLibraryDir/libandcode-bash.so, development bundle/bin/bash.bin;
    no third-party host. Configure short prompt `\W \$ ` and HISTFILE, read user ~/.bashrc,
    provide `opencode` function (foreground execution returns to shell rather than exec-replacing it). Without Bash,
    fall back to `/system/bin/sh -i`; ENV reads system mkshrc and explicitly announces degraded mode.
    SHELL remains directly executable system sh, avoiding downstream bare-glibc-Bash spawn PT_INTERP failures;
    production Bash launcher is in the packaged native payload; locked-delivery matrix remains pending device verification.
    Bind TerminalViewClient before first frame; sync size/drawing after layout, without injecting Enter to fake a prompt.
    Two bottom extra-key rows include ESC/TAB/CTRL/ALT/four arrows, HOME/END/PGUP/PGDN, `/`/`-`/
    Enter/IME; CTRL/ALT are highlighted sticky keys (tap again to release), other non-text keys encoded by TerminalView
    according to application mode. Touch keys do not steal terminal focus; adjustResize keeps them above the keyboard.
    Extra keys and injection are reachable on-device in normal TUI state (v0.4.52 probe, top changelog):
    ← moves cursor, ESC closes TUI overlay, sticky CTRL (purple highlight) + hardware c gives Ctrl+C
    (first clears editor line; repeat when empty exits); TUI returns cleanly to shell prompt.
    Coordinates must use actual device pixels (full-resolution screencap); scaled-preview coordinates miss entirely.
    Pinyin IME composition intercepts injected text and candidate bar covers extra keys; switch to English IME before probes.
    Bash depends on libtinfo; baseline CI records both copyright texts/GPLv3 and actual dpkg versions.
    Old-kernel faccessat2(439) TRAP is handled by synthesized -ENOSYS at libc call site, entering native fallback;
    patch pins Ubuntu libc6 2.39-0ubuntu8.9 bytes/offsets and must fail on mismatch.
    Static TerminalSession + delegated ClientBridge
    reuse process/buffer across Activity departure/recreation; SessionService keeps host resident.
    This is same-app-process retention only, not recovery after force-stop/system process kill.
    Both terminal and Web floating buttons open drawer navigation;
    drawer Home explicitly launches HomeActivity through shared `NavDrawer.goHome`
    (`CLEAR_TOP | SINGLE_TOP`, Home is singleTask), closing source page. Even if a development entry
    launched the source directly with no Home in back stack, bare finish() no longer drops to system launcher.
  - **Desktop Web page (v0.4.3, device-verified)**: `opencode serve --port 4096
    --hostname 127.0.0.1` backs OpenCode 2.0 desktop UI; WebView renders the SPA from
    `http://127.0.0.1:4096/`. Key points:
    - `ServeManager` manages serve in app domain via direct patched-loader launch
      (`ld-linux --library-path … --inhibit-cache <oc2> serve …`), with environment matching
      scripts/app-launch-oc.sh (HOME/TMPDIR/BUN_TMPDIR in filesDir,
      `GLIBC_TUNABLES=glibc.pthread.rseq=0`, device-local proxy). All stdout goes to
      files/oc2-serve.log (unconsumed output fills pipe and hangs serve), parsed for
      server password;
    - Binary-path resolution supports jniLibs (`nativeLibraryDir/libandcode-oc2.so`
      + sibling patched loader, final form) / `/data/local/tmp` (development, currently tested path);
    - **Loopback cleartext allowlist**: manifest networkSecurityConfig permits cleartext only for
      `127.0.0.1`/`localhost`; all other domains require https;
    - **Automated pairing**: each serve start generates a new password (old credentials expire),
      captured live from stdout. WebView polling JS (500ms × 20s, React native setter)
      automatically completes password pairing; localStorage persists login
      (same as desktop browser);
    - Known gap: direct ld-linux exec of `oc2` makes `/proc/self/exe` point to loader;
      Bun self-respawn (e.g. `pair`) treats subcommand arguments as ELF paths and fails.
      Single-process serve avoids this; pair/background respawn needs an oc2 launcher
      ELF wrapper (reuse bundle/launcher/launcher.c pattern, as bin/git).
    - **Web PTY (v0.4.4)**: prestage process-daemon v0.4.0 (protocol 7, REUSE §2.1);
      serve/terminal set `OPENCODE_PTY_BIN` to executable copy, not cached symlink
      (upstream rejects symlinks and checks uid/sha256). Upstream also supports
      `OPENCODE_PTY_SOCKET_DIR`, set to `Context.getFilesDir()`; daemon appends
      `opencode-pty-<uid>/<32 hex>.sock`, retaining non-symlink/uid/0700 checks.
      Java checks full UTF-8 path <104 bytes before injection. Unset defaults to `/tmp`,
      where Android mkdir returns EROFS; daemon exits and frontend reports service.json ENOENT.
      TMPDIR alone has no effect. Active sockets were observed unlinked in cacheDir, so it is not used for endpoints.
    - **Web page exit (v0.4.6)**: pairing retries use Activity-owned main-thread Handler;
      onDestroy clears queue first. Service-start success/failure, onPageFinished and pairing entry check
      isFinishing/isDestroyed and WebView reference. Destruction nulls reference first, stops loading,
      replaces Activity-holding WebViewClient, detaches from parent ViewGroup, then destroys;
      SessionService/serve keep running. Before fix, old device reproduced exit to system launcher; logs also had
      “Application attempted to call on a destroyed WebView” and attached-destroy warnings,
      but no app-process fatal exception was observed this round; warnings are not a confirmed crash stack.
    - **Web IME (v0.4.5)**: `WebActivity` injects APK asset
      `andcode-terminal-ime.js` after local page load; MutationObserver handles newly mounted SPA terminal tabs.
      Match only ghostty `textarea[aria-label="Terminal input"]`, setting
      `inputmode=url` (LatinIME English character input) and `enterkeyhint=enter`;
      no chat-field changes, password type, native JS bridge, or custom PTY character forwarding.
      Hidden textarea retains a local space sentinel so IME produces backspace beforeinput;
      restore in a microtask after upstream handling, without value changes during composition. Upstream retains
      beforeinput/composition/paste deduplication and transport. Current LatinIME device test:
      `echo okx` → backspace → Enter yields `ok`; Chinese candidates/other IMEs **pending P3 on-device verification**.
    - **Development deployment/delivery boundary**: old device currently uses root to label prestaged ELF/dependencies
      apk_data_file; PTY PT_INTERP points to patched loader **regular file**
      `/data/local/tmp/ld` (original symlink unreachable in app domain; PTY relabel alone cannot fix EACCES).
      Libraries resolve via LD_LIBRARY_PATH; glibc 2.39 librt.so.1/libutil.so.1 must be included.
      Device verified real untrusted_app daemon → shell → Web-pasted command → echo;
      adb input text is garbled through device IME and is not evidence for normal touchscreen input.
      Production Tier P must use nativeLibraryDir prestaged copies and launcher/loader redirection;
      root/chcon or fixed `/data/local/tmp/ld` must not become locked-device release solutions.
      jniLibs/CI packaging is integrated; locked-delivery and other-device acceptance remain **pending P0/P3**.
- **Projects/settings pages (v0.4.7)**: shared drawer adds Projects · Import / Export and Settings.
  - Project/settings navigation icons match other entries' size and theme tint.
    Standalone-terminal pinch adjusts font by 1 sp when accumulated scale >1.1 / <0.9, then resets;
    reaching 10–28 sp bounds also resets scale for immediate reverse response. Persist in the same preferences;
    settings foreground resumption syncs slider/preview without recreating terminal session; Web zoom unchanged.
  - Native Material 3 top bar/grouped cards follow DayNight; import entries sit side by side. Project cards
    retain Open terminal primary action, default-project indicator and collapsed long path; copy/export use More menu.
    Settings group terminal display/export privacy/workspace, with live font preview and whole-row switches.
  - Unique project names; first write random `import-` staging under filesDir, then move to
    projects on success. Failure cleans only this task's staging; no overwrite. ViewModel retains background work
    across Activity rotation, not guaranteed across process death; abnormal exit may leave staging directories.
  - ZIP rejects absolute paths, backslashes, `.`/`..`, duplicates and directory data; import/export limits:
    512 MiB raw data, 20000 entries, 64 levels. Directory import uses DocumentsContract.
    ZIP restores no Unix permissions/symlink metadata, copies data only, and does not relax data-directory exec prohibition.
  - Export creates a SAF ZIP including project root; default excludes .git, does not follow symlinks,
    skips sockets/special files, and best-effort deletes partial output on failure. Not an atomic live-project snapshot;
    other hidden files such as .env are not filtered; UI explicitly prompts key review. Import preserves ZIP directory layout.
  - Copy project absolute path to Web Open project; use as new-terminal cwd without injecting cd or killing
    existing terminal processes. ENV profile no longer forces cd HOME.
  - `andcode-settings` stores terminal font (10–28 sp), terminal/Web keep-screen-on,
    and export-.git preference. onResume applies display settings without restart; Web-terminal font unaffected.
    Upstream Web UI still manages API keys/providers; this page adds no credential storage.
- **Optional backend CA (v0.4.40–v0.4.42)**: SAF imports a single PEM; user supplies file SHA-256 from an independent
  trusted channel. Limit 64 KiB; validate single certificate/CA signing usage/validity, reject private keys,
  certificate bundles and links. Private copy is digest-named; recheck digest/certificate conditions before each enabled start.
  Import does not enable trust; product defaults off. Set `NODE_EXTRA_CA_CERTS` only for new OpenCode Web backends
  and inheriting children, retaining Bun roots/hostname checks. Disabled mode clears inherited CA/TLS/Bun
  overrides without changing system/WebView/standalone-terminal/Ubuntu trust. Import/toggle/clear selection do not
  stop existing backends; manual stop/start applies changes. Clearing selection retains old copies for running processes.
  - 2026-11-09 same-signature in-place install preserved data; real `untrusted_app`, UID10348,
    Seccomp=2, SELinux Enforcing verified default off, wrong-digest rejection and remaining off after correct SAF import.
    Explicit enable/manual restart gave new backend CA environment with no TLS bypass.
  - Default direct model requests still fail `getaddrinfo EAI_AGAIN one.ai.api.service.arjata`: DNS-stage failure,
    not certificate evidence. Isolated diagnostic backend with explicit `127.0.0.1:7890` returns
    `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` with CA disabled; enabled `arjata/gpt-oss-120b` returns expected
    text, with SSE incremental text, interruption and same-session resume observed. Proxy success is not direct
    success, and diagnostic proxy is not the product default.
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
  - Model-invoked side-effect-free shell command returned expected marker, but provider continuation after tool result
    returned HTTP 400 (`provider.invalid-request/openai_error`); full tool round trip failed, root cause pending.
    After acceptance, stop diagnostic backend, restore CA-off setting; manually restarted default PID20163 has no
    `NODE_EXTRA_CA_CERTS` or TLS bypass. Retain imported CA and all test sessions; no user
    data deleted.
  - After authorized device `8c8da214` reconnected on 2026-11-10, default PID20163/model/CA-off
    environment remained unchanged. Start independent diagnostic PID8198 through that backend shell; recheck real
    `untrusted_app`, UID10348, Seccomp=2. With explicit proxy/existing CA, fresh session
    `ses_e3ef3e479ffeeWTmyr2HK8a566` completed two consecutive constrained `printf` executions, result continuations
    and final markers; each SSE round completed two steps with tool.success/execution.succeeded,
    no provider errors. Old session `ses_e3fa8bb82ffeqj5z8cksogpUPH` still returned HTTP 400
    before tool invocation. Full tool round trips therefore pass only under these fresh-session/network conditions;
    history-replay root cause remains unresolved. Retry success is not a protocol fix or restored default direct connectivity.
  - HTTP API format comparisons reconstructed from existing synthetic acceptance messages through explicit proxy executed no tools,
    retaining no credentials/raw messages. Minimal empty/NULL-content and reasoning-field comparisons succeeded;
    historical-message comparisons also fluctuated 200/400. These are not captured exact OpenCode requests and
    do not justify deleting fields or silently modifying old sessions. PID8198 terminated and diagnostic forwarding
    removed afterward; PID20163 remains available without CA/TLS bypass. CA files, all sessions, projects and Ubuntu
    instances retained. Other devices/networks/IMEs and old-session recovery pending P0/P3 on-device verification.
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
- UI: Home dashboard + terminal + desktop Web + projects + settings; extended settings such as sshd management/
  phantom-killer guidance remain planned, not delivered.

### 4.5 /etc redirection: proot bind (primary) + LD_PRELOAD shim (secondary)

**Architecture correction (v0.4.1, device-tested)**: LD_PRELOAD intercepts only **cross-object PLT calls**;
`fopen("/etc/resolv.conf")` and similar originate **directly inside glibc** (hidden aliases, no PLT),
bypassing shim — confirmed by device TEST-NET probe's immediate 244ms disconnect. Therefore:

| Layer | /etc redirection mechanism |
|---|---|
| **Tier A PRoot path** | **PRoot userspace bind**: bind selected guest files such as resolv.conf and SSL configuration for that guest process tree; PRoot components are independent aggregation recorded in the manifest |
| **Tier P managed Ubuntu guest** | PRoot guest binds provide guest `/etc`; this is the default-off managed backend in §4.4/§4.8, not a generic host `/etc` mechanism |
| **Tier M (root, optional)** | Real bind mount (`mount --bind`), zero overhead |
| **shim (secondary)** | Supports external glibc-object PLT calls, including calls from non-glibc objects; it cannot intercept glibc-internal calls that bypass PLT. It self-clears LD_PRELOAD to protect Bionic children |

**Known constraints**: ①proot ptrace interception **cannot nest** — wrapper/entry guards with
`ANDCODE_IN_PROOT`, never nesting proot inside proot; ②mobile/managed networks often block outbound UDP 53 —
`andcode-mkresolv` forces `options use-vc timeout:3
attempts:2` in resolv.conf (TCP DNS, device-proven necessary); ③managed Tier P Ubuntu serve now uses
the default-off PRoot backend described in §4.4/§4.8. Guest bind mounts provide guest `/etc`; this does
not make PRoot the universal host `/etc` solution. The v0.4.1 device evidence above remains historical.

### 4.6 Android 12+ Phantom Process Killer mitigation (all three forms)

```bash
adb shell "cmd device_config set_sync_disabled_for_tests persistent"
adb shell "device_config put activity_manager max_phantom_processes 2147483647"
```

- Tier M (root): persist these settings with root at install (adapting ROM-specific private switches),
  recheck with service.sh after reboot — **the only automatically persistent form**.
- Tier P (APK): settings guide users to execute copyable adb commands, including wireless-debugging
  guidance; foreground service further reduces kill probability. Android 12+ is our minimum, so this
  mitigation applies to all targets; no "older OS does not need it" branch.
- Tier A: deployment script also executes it; document rerun after reboot.

### 4.7 Authentication and interaction

1. **Authentication**: a) copy OAuth URL from terminal to any browser and paste callback back; b) API key /
   environment injection (paste directly in Tier P settings, no browser); c) Tier P can use
   Intent to launch default browser for callback.
2. **Headless/remote**: `opencode serve` + bundled dropbear → any SSH client or PC
   browser on the same LAN. "opencode on a phone" can thus be fully PC-driven;
   touchscreen TUI is an optional entry, not a requirement.

---

### 4.8 Dual Ubuntu development backends (implemented; acceptance scope stated below)

**Current status (2026-11-14).** Single-APK rootfs extraction and the opt-in, default-off managed
PRoot serve backend are integrated. On device `8c8da214`, the embedded Ubuntu 24.04.4 arm64 rootfs
was installed on first launch; managed serve passed Web/API, guest shell execution, Web PTY and
guest-file persistence checks. `arjata/glm-5.2` completed an agentic tool round trip through this
backend. The same provider's `gpt-oss-120b` tool-result continuation still fails with HTTP 400/503;
plain-text replies and tool execution itself were observed. This is tracked as a provider-side
defect, with no client protocol workaround. Other-device acceptance, the locked-delivery matrix,
root chroot integration with the canonical archive, and abnormal-stop/recovery acceptance remain
pending P0/P3 device verification. The implementation and acceptance boundaries are distinct:
Linux CI does not substitute for these Android/device checks.

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
  (v0.4.55: this canonical archive becomes the embedded first-launch install
  payload inside release APKs. It is extracted only by the dedicated jniLibs-side
  extractor enforcing the tar safety checks below; the project ZIP importer
  stays excluded, and existing device instances are never replaced in place.)
  The optional image audit now compares the immutable original ext4 tree to the
  canonical archive, not the image copy modified by apt/compiler smoke tests.
  It rejects path/type/mode/owner/content/link drift and permits only mkfs's
  empty root-owned mode-0700 `lost+found` when absent from the archive. It does
  not certify timestamps, ACLs, xattrs or complete source delivery.

- Retain lightweight Bash; Ubuntu 24.04 arm64 comes from the same official image/repositories. Chroot uses
  a separate ext4 image, PRoot a separate writable instance; no shared `/etc`, `/usr` or dpkg database.
  **Unified build-artifact layer (v0.4.55)**: canonical rootfs archive (single-APK plan's
  `andcode-rootfs.tar.zst`) is the shared chroot/PRoot build source — one CI build,
  one digest/manifest, distributed per tier to separate storage (app-private / root-side). Device instances
  remain independent; dual acceptance gates remain (app-domain PRoot + root chroot).
  Tier M may later evaluate extracting the same archive into directory-based chroot instead of ext4;
  this behavior change requires P0/P3 device verification before replacement. Existing `ubuntu.img` and all instances stay intact.
- `scripts/build-ubuntu-rootfs.sh` produces a compressed 4 GiB ext4 image in native arm64 CI,
  SHA-256, dpkg source/binary version inventory, Docker digest and recipe commit; retain licenses.
  Rootfs tar is only a trusted CI intermediate; check paths, duplicates, link ancestors, special files and
  setuid/setgid bits before extraction. Never use the APK project ZIP importer to install rootfs.
- Root-only `runtime/ubuntu/andcode-ubuntu-install` installs only to
  `/data/adb/andcode-ubuntu`, checking out-of-band digest, arm64, ≥5 GiB free and exact image size;
  reject overwrite, retain private remnants on failure for inspection, never auto-delete user data.
- Management entry `andcode-ubuntu` gives each foreground session a separate recursively private mount namespace,
  binding minimal `/dev` nodes, PTY and proc, with temporary mounts for `/run` and `/dev/shm`; no whole
  Android `/data`, `/system` or `/sys` binds or SELinux changes. Image/entry are root-private;
  serial lock prevents concurrent mounts of one filesystem. Normal exit unmounts in reverse; no forced/lazy
  unmount of busy mounts. Failed cleanup retains lock for manual recovery; automatic background-process cleanup is not claimed solved.
- `shell`/`exec` run as UID/GID 60000 with Android inet supplementary group 3003, clear inherited environment,
  capability bounding/inheritable/ambient sets and set no-new-privs; `/workspace`
  belongs to that user. `admin` is explicit manual maintenance only, allowing apt but exposing no sudo/root to models.
  **Chroot is not a security sandbox**: shared host UID, proc visibility, shared kernel and root administration retain risks.
- Root APK IPC is not integrated: any future privileged bridge requires signature/peer-credential authenticated channels,
  project-scoped mappings and real-device admission; concatenated `su -c` strings are not a production service.
- PRoot admission must test apt, newly installed/compiled ELF, PTY/children,
  DNS/HTTPS and libc upgrades in real zygote app domain; adb root/run-as cannot substitute, nor can lower targetSdk
  or disabled SELinux hide issues. Old-device real app domain passed explicit-proxy apt/HTTPS, hello,
  freshly gcc-compiled ELF, PTY/children and execution after libc 2.39-0ubuntu8.7 → 8.9 upgrade, without
  guest ELF patches. This is development admission, not certification of the full locked-delivery matrix.
- APK terminal offers explicit development entry `andcode-ubuntu-proot [loopback-proxy] [command...]`;
  no arguments starts interactive Bash, exit returns to lightweight Bash, missing instance fails explicitly. No auto-install or su.
  This terminal entry is separate from the managed OpenCode/Web PTY backend.
  APK native payloads use the runtime farm; payload-free development uses
  `/data/local/tmp` PRoot.
  Settings select lightweight Bash (default) or Ubuntu PRoot for new terminals, with separate default-off proxy.
  Existing sessions are not restarted; new sessions snapshot selected project name, bind only `files/projects/<project-name>` to
  `/workspace/<project-name>` and start there, or `/root` without selection. Reject project-root/parent symlinks,
  escaping names/PRoot bind separators/missing paths. No recursive internal-link checks; app UID host permissions
  remain unchanged, so no security-isolation claim. Missing instance blocks selection; missing instance/project at startup
  fails explicitly without silent host-execution fallback. OpenCode/Web PTY does not use this mapping.
  Old-device app domain verified project writeback/argument fidelity/stdin/exit codes and invalid-project rejection.
  Public UDP DNS times out; TCP DNS answers normally. With `use-vc`, HTTPS, strict apt update and Git HTTPS pass
  without explicit proxy, still relying on existing device VPN/network; not a VPN-disabled test.
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
- CI copies standard bundle separately for Tier P, verifies/patches seven seccomp byte sites, reruns and
  verifies unchanged loader/libc SHA-256 before repackaging/physicalization. Standard Linux bundle unchanged;
  new-baseline byte mismatch fails build; patches never apply to PRoot guest or apt-updated libc.
  Android-specific artifact chain is integrated: `pack-apk-libs` output passes through CI artifacts to
  Gradle via `-PandcodeNativeDir`; conditional release signing verifies with `apksigner` when all required
  secrets are configured. Locked-form/device matrix acceptance remains pending P0/P3.
- Independent Linux CI workflow tests only rootfs apt/non-root compilation/execution, privilege reduction and compatibility,
  not Android support. After user cleanup on 2026-11-09, old device had about 54 GiB free.
  No local Docker; add native-device development bootstrap with official fixed-SHA-256 Ubuntu Base,
  not equivalent to CI build validation. Copy existing independent BusyBox to root-private directory for bind mount,
  no third-party app; old Toybox incorrectly attempts loop for character-device bind. Allocate loop explicitly,
  do not detach again after kernel auto-detach. Chroot UID 60000 networking still fails; canonical-archive
  chroot integration, authenticated root service and recovery remain **pending P0/P3 on-device verification**.
  Operations/acceptance: `docs/UBUNTU.md`.

## 5. Repository structure (current top-level layout)

```
andcode/
├── docs/                     # Design, naming, reuse, Ubuntu and LFS documentation
├── baseline/                 # Ubuntu arm64 baseline and compatibility audit
├── bundle/                   # Bundle packers, pack-apk-libs, launchers, overlay and shim
├── runtime/ubuntu/           # Root-side Ubuntu chroot installation/management
├── app/                      # Android application and terminal modules
├── magisk-module/            # Tier M module integration
├── scripts/                  # Packaging, rootfs, audits, CI and device gates
├── ci/                       # CI integration assets and helpers
└── .github/workflows/        # Build, artifact transfer, APK and release workflows
```

---

## 6. Historical plan and current acceptance status

The phase table below is retained as the original project plan, not a statement of current
implementation status. Current acceptance scope is summarized here; device claims are limited
to the explicitly tested device and paths.

| Area | Current status |
|---|---|
| Tier P Web/TUI and packaged native payload | Integrated; single-APK rootfs installation and managed PRoot serve passed stated checks on device `8c8da214` |
| Linux compatibility baseline and CI artifact chain | Integrated, including `pack-apk-libs` to Gradle `-PandcodeNativeDir` transfer |
| Managed PRoot serve | Implemented, default off; device scope and gpt-oss-120b continuation defect are recorded in §4.4/§4.8 |
| Other-device and locked-delivery matrix | Pending P0/P3 device verification |
| Root chroot integration/recovery using canonical archive | Pending P0/P3 device verification |
| Tier M model/tool tests | Two text+bash tool round trips passed with explicit proxy and CA; manual root diagnostic scope only (§4.2) |

Original phase plan:

| Phase | Content | Acceptance criteria |
|---|---|---|
| **P0 Feasibility (2–3 days)** | Manual adb bundle (Tier A): static busybox + sysroot + loader wrapper runs official opencode; closely review `claude-code-termux` for no-proot approach; **also test jniLibs extraction + W^X/JSC JIT + TUI extraction behavior** (three Tier P prerequisites) | Complete a real coding session on any locked physical device; mark §1.3 assumptions ✓/✗ individually; establish shim gaps/JIT assessment |
| **P1 Baseline/bundle (1 week)** | Three `baseline/` components + `bundle/pack-bundle.sh` + shim v1 + CI | Pass `check-compat.sh`; same tarball runs in Tier A, real chroot and native Ubuntu 24.04 arm64 |
| **P2 Tier M (1 week)** | Magisk module + service.sh boot startup + persistent phantom-killer settings | After flashing class B device: reboot auto-starts sshd, `ssh` session ready to use; no third-party app throughout |
| **P3 Tier P APK (2–3 weeks)** | APK (minSdk 31 / targetSdk 37.2), jniLibs packaging, minimal jackpal terminal fork, settings, specialUse foreground service | One sideloaded APK on class A completes install→authenticate→session; survives 30 minutes backgrounded; runs on 16K-page device (or developer-option simulation) |
| **P4 Polish** | DNS/network reconnection, OAuth callback, `serve`+SSH fallback, multiple sessions, release engineering (notices, F-Droid metadata) | All-green smoke matrix (REUSE/CI) |

---

## 7. Risks and alternatives

| # | Risk | Impact | Alternative |
|---|---|---|---|
| R1 | Bun/opencode needs uncovered system files in "bare glibc sysroot without proot" (shim gaps), or JSC JIT restricted beyond targetSdk 28 | Tier A/P main path blocked | ① Device-test/fill shim gaps in P0; ② introduce one static proot binary for bind (independent GPL-2.0 aggregation + source provision); ③ Tier M real chroot unaffected |
| R2 | Ubuntu 24.04 raises standard-device floor to glibc ≥ 2.39 | Narrower standard Linux targets | ① Android unaffected (bundled glibc); ② add Debian 12 second baseline/release tier; ③ static musl for simple tools |
| R3 | Android data-directory execution policy and runtime W^X/JIT constraints are distinct; runtime ELF extraction may require redirection | Tier P launch or JIT may be affected | ① Package executables in jniLibs (`lib*.so` → `nativeLibraryDir`); ② use the validated guest PRoot path for Ubuntu ELF only; ③ assess `BUN_JSC_useJIT=0` if runtime W^X policy rejects JIT; ④ redirect runtime extraction to prestaged copies where supported |
| R4 | ROM differences (vendor background killing, locked device_config) | Process survival | Prefer persistent root Tier M; `serve`+SSH fallback; document mainstream ROM adaptation commands |
| R5 | Rapid upstream opencode changes and artifact-layout shifts | Maintenance cost | Regular CI P0 smoke reruns; encode assumptions in `scripts/smoke-test.sh` |
| R6 | Unmaintained jackpal terminal library; new Android (targetSdk 35+ behavior) regressions | Tier P terminal experience | Maintain minimal fork with edge-to-edge/predictive-back adaptation; terminal is one entry, SSH/serve fallback; evaluate Termux terminal if needed (GPLv3, separate fork repository required) |
| R7 | adb unavailable on locked device (USB debugging disabled) | Tier A unavailable | Tier P requires no adb and is default for locked devices |
| R8 | Some non-baseline-toolchain components have incompatible 4K alignment on 16K devices | Failure on some Android 15+ devices | Baseline glibc/Ubuntu default 64K alignment is theoretically immune (§1.2.8); CI `readelf -l` segment checks; enforce 16K for own NDK code |
| R9 | Android 14+/15+ restricts `device_config` writes (some ROMs require root) | Weaker Tier A/P phantom-killer mitigation | Foreground service + session child-process count control; prefer persistent root Tier M; document ROM differences |

---

## 8. Explicit exclusions (scope boundaries)

- **No dependency on third-party host apps such as Termux/proot-distro**: appendix-only optional
  alternatives; all deliverables self-contained (static busybox + bundled sysroot + dropbear + own shim).
- No native Android Bionic port (relinking opencode to bionic): extremely costly and defeats
  the goal of running artifacts on standard Linux arm64.
- No x86/emulator path: all target devices are arm64.
- No Android system-partition modifications: all approaches stay within `/data` and app sandbox.

---

## Appendix: optional alternatives (record only, not the main design)

- **Termux + proot-distro**: most mature community host, for users who prefer not to sideload the APK
  and can install F-Droid Termux. Our bundle should theoretically run directly in proot Debian/Ubuntu
  (`bundle/` deliberately makes no host assumptions). See REUSE.md for Termux-family license obligations.
- **Third-party SSH clients such as ConnectBot**: recommended for Tier A/M, but optional tools,
  not dependencies.
