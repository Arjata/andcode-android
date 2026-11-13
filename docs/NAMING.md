# Executable tool entry-point naming specification (docs/NAMING.md)

> Version: v1.0 · 2026-11-06 · Applies to: bundles, all Tier M/A/P forms, repository scripts
> This is a **foundational specification**: targetSdk 37.2 `jniLibs` packages only `lib*.so`, data directories prohibit
> exec, and dynamic linking resolves exact sonames. Naming is bound to these three platform constraints (DESIGN §1.2).
> This specification takes precedence in conflicts; changes must synchronize `bundle/manifest` and CI gates (§7).

---

## 1. Terminology

| Term | Definition |
|---|---|
| **Logical name** | Name invoked by users/programs (PATH commands, git exec-path helpers, etc.) |
| **Physical name** | Actual filename in a delivery form (canonical bundle layout or Tier P jniLibs) |
| **Canonical layout** | Unified bundle-tarball directory structure, the shared "source format" for all three forms |
| **Wrapper** | Entry script setting environment (loader/LD_PRELOAD/PATH), then exec'ing upstream ELF |
| **Link farm** | "Logical name → physical name" symlink tree generated in `filesDir` on Tier P first launch |
| **slug** | Physical-name body derived from logical path, satisfying `lib*.so` constraints |

## 2. General rules

1. Command/script/directory names and slugs use **lowercase letters/digits/hyphens** (`[a-z0-9-]`), no spaces,
   underscores or uppercase; longest contiguous segment 32 characters, full name (including `libandcode-`/`.so`) ≤64 characters.
2. Environment-variable exception: `ANDCODE_` + SCREAMING_SNAKE (§5).
3. **Preserve upstream names unchanged** as logical names (`opencode`, `git`, `ssh`, `dropbear`),
   without prefixes/case changes, transparent to users and internal opencode calls (e.g. spawning `git`).
4. All project-owned commands use `andcode-`; **do not occupy upstream namespaces**
   (no hyphenless `andcode` command impersonating upstream, or project nicknames added to upstream commands).
5. Aliases are limited to POSIX standard names: only registered alias is `ssh → dbclient`.
6. Register every new name through §8 before use; CI gates (§7) validate against registry.

## 3. Namespace registry (authoritative allocation)

| Form | Ownership | Example |
|---|---|---|
| `libandcode-*.so` | **Entire Tier P physical namespace**: all jniLibs files (upstream ELF, wrappers, loader, own .so) | `libandcode-git.so` |
| `andcode-*` (no extension) | Project-owned user commands/service entries (bundle `bin/`, `sbin/`) | `andcode-doctor` |
| `*.bin` (canonical layout only) | Upstream ELF coexisting with same-name wrapper | `root/bin/opencode.bin` |
| Original unprefixed name | Upstream logical commands (wrapped or directly exposed) | `opencode`, `git` |
| `ANDCODE_*` | Environment variables | `ANDCODE_TIER` |
| `andcode` | Magisk module id / component identifier | `id=andcode` in `module.prop` |
| `dev.andcode.app` (placeholder, adjustable to release organization) | APK applicationId | `app/build.gradle` |
| `.sh` suffix | **Repository development scripts only** (`scripts/`); bundle/PATH commands have no extension | `scripts/deploy-adb.sh` |
| `andcode-terminal-ime.js` | Own Web-terminal IME adapter in APK assets (not a PATH command) | `app/app/src/main/assets/andcode-terminal-ime.js` |
| `assets/andcode-rootfs/` | Canonical development-rootfs install payload in APK assets: `andcode-rootfs-arm64.tgz` + `.sha256` + `packages.txt` (dpkg versions); dedicated first-launch extractor installs to `files/proot-rootfs`, no data-directory exec | `pack-apk-libs.sh` output/CI canonical-rootfs step, consumed by first-launch extractor |
| `andcode-terminal-ime.test.mjs` | Node built-in tests for that script (development only, not in APK) | `app/tests/andcode-terminal-ime.test.mjs` |
| `projects`, `import-<random-value>` | APK filesDir project/import-staging directories; data only, not executable entries | `files/projects/<project-name>`, `files/import-<random-value>` |
| `andcode-settings` | APK-private SharedPreferences for terminal/export preferences and selected project | No API keys |
| `proxy-url` | User-configured proxy URL including the scheme (e.g. `http://` or `socks5://`); consumed by both proxy switches when enabled; empty means no proxy env is injected and no default is assumed. | APK SharedPreferences |
| `terminal-backend`, `ubuntu-loopback-proxy`, `serve-loopback-proxy`, `serve-proot-backend` | Private preferences: new terminals select `bash`/`ubuntu-proot`; Ubuntu and managed-serve loopback proxies are separate explicit opt-ins, both default off; `serve-proot-backend` (default off) runs a newly started managed serve inside the Ubuntu PRoot guest. Existing processes are unchanged; restart serve manually to apply its preference.; absent key auto-selects Ubuntu when the canonical rootfs is ready | APK SharedPreferences |
| `http_proxy`, `https_proxy`, `HTTP_PROXY`, `HTTPS_PROXY` | Standard proxy variables: Tier P managed serve injects `http://127.0.0.1:7890` only when `serve-loopback-proxy` is enabled, in both direct and PRoot modes. TLS verification remains enabled; additional trust uses `NODE_EXTRA_CA_CERTS`. | ServeManager child environment |
| `/mnt/sdcard` | PRoot guest bind target for device storage: `/storage/emulated/0` bound read-write in the serve guest and the terminal Ubuntu session; access follows the platform FUSE/permission view (Download and media verified read-write). | ServeManager proot argv; term-ubuntu-proot.sh |
| `/mnt/andcode-exe`, `/mnt/andcode-farm`, `/mnt/andcode-ca`, `/root` | PRoot guest bind targets for the managed serve: nativeLibraryDir, the runtime farm root, the imported custom-CA directory (bound only when CA trust is enabled) and the app home (config/sessions persist on the host side). Binds are writable; PRoot is not a sandbox. | ServeManager proot argv |
| `ProjectsActivity.java`, `SettingsActivity.java`, `AppSettings.java`, `ProjectArchive.java`, `ProjectArchiveTest.java`, `UtilityActivity.java` | APK project/settings components, shared page and ZIP safety tests (Java files follow class names) | `dev.andcode.app` |
| `ic_more.xml` | APK project-card More vector icon (existing Android-resource snake_case style) | `res/drawable/ic_more.xml` |
| `ic_nav_projects.xml`, `ic_nav_settings.xml` | Shared-drawer project/settings vector icons (Android-resource snake_case) | `res/drawable/` |
| `ic_launcher.xml` | Adaptive launcher icon, shared by normal and round launcher entries; includes the monochrome layer used on API 33+ | `res/mipmap-anydpi-v26/` |
| `ic_launcher_foreground.xml`, `ic_launcher_monochrome.xml` | Original terminal-prompt launcher artwork; 108 dp viewport with artwork inside the adaptive-icon safe zone | `res/drawable/` |
| `launcher_background` | Launcher background color resource, shared by adaptive icon variants | `res/values/colors.xml` |
| `andcode-icon.svg` | Original scalable project icon matching the Android launcher artwork; text source, not a packaged runtime asset | `docs/img/` |
| `TerminalExtraKeys.java` | Own APK extra-key control, reusing TerminalView input protocol | `dev.andcode.app` |
| `term-env.sh`, `term-bashrc` | Generated system-sh/Bash startup configuration in APK filesDir, shell-read only, not executable | `files/term-env.sh`, `files/term-bashrc` |
| `etc/third-party/bash-copyright`, `etc/third-party/ncurses-copyright` | Ubuntu copyright/license texts for bundled Bash/libtinfo; data excluded from jniLibs | bundle `etc/third-party/` |
| `etc/third-party/gpl-3` | Full GPLv3 referenced by Bash copyright | Bundle data file |
| `build-ubuntu-rootfs.sh` | Native arm64 CI Ubuntu development-image recipe | `scripts/` |
| `andcode-ubuntu` | Root-only chroot prototype manager, excluded from model PATH | `runtime/ubuntu/andcode-ubuntu` |
| `ubuntu-rootfs-test.sh` | Linux CI image/non-root compile and apt smoke tests | `scripts/` |
| `validate-ubuntu-rootfs.py` | Build-time rootfs structure/link validation, not device installer | `scripts/` |
| `andcode-ubuntu-arm64.img.gz`, `andcode-ubuntu-arm64.img.gz.sha256` | 4 GiB ext4 development image/compressed-file digest, CI artifacts only | `dist/` |
| `andcode-ubuntu-packages.tsv`, `andcode-ubuntu-build.txt` | dpkg versions/origins and Docker image identity, CI artifacts only | `dist/` |
| `andcode-ubuntu` (directory) | Root-only instance isolated from lightweight bundle and future PRoot instance | `/data/adb/andcode-ubuntu/` |
| `andcode-ubuntu-ci`, `ci-validation` (first argument) | Independent trusted-CI-image acceptance instance; installer/manager allows only this fixed alternate directory, rejects overwrite/arbitrary paths | `/data/adb/andcode-ubuntu-ci/` |
| `ubuntu.img`, `rootfs`, `session-lock` | Root instance image/mountpoint/concurrency lock, no app-supplied alternate paths | `/data/adb/andcode-ubuntu/` |
| `andcode-image` | Internal image format/distribution/architecture marker | guest `/etc/andcode-image` |
| `ubuntu-development.yml` | Manually triggered image-build/Linux-smoke workflow | `.github/workflows/` |
| `andcode-ubuntu-install` | Root-only trusted-CI-image installer, digest/space/permission checks, no ZIP input | `runtime/ubuntu/andcode-ubuntu-install` |
| `ubuntu-rootfs-validator.test.py` | Synthetic-archive regressions for rootfs build validator | `scripts/` |
| `compare-ubuntu-rootfs.py`, `compare-ubuntu-rootfs.test.py` | Build-only read-only canonical archive / original ext4 tree comparison and synthetic regressions; paths, types, modes, UID/GID, file bytes and links; excludes timestamps, ACLs and xattrs | `scripts/` |
| `andcode-ubuntu-tree-review.json` | Canonical archive / original ext4 tree comparison result; no runtime or source approval | Experimental mmdebstrap artifact |
| `UBUNTU.md` | Dual-backend status, trusted-image installation and device-admission checklist | `docs/` |
| `bootstrap-ubuntu-device.sh` | Root-device development recipe with pinned Ubuntu Base digest, not a production CI-install replacement | `scripts/` |
| `loopback-proxy` (argument value) | Explicitly select existing `http://127.0.0.1:7890` proxy for device-development validation; pass http_proxy/https_proxy only for that invocation, retain TLS checks | Ubuntu bootstrap/device-test argument |
| `ubuntu-device-test.sh` | Root chroot device networking/apt/permissions/compile/exit-cleanup checks, not proof of PRoot success | `scripts/` |
| `ubuntu-network-diagnose.sh` | Manual root read-only Android 13 BPF network-rule/current APK/fixed guest UID checks; no settings/permission-table modification or borrowed-UID execution | `scripts/` |
| `launcher.test.py` | Linux CI builds own launcher; ASan/UBSan checks direct/PRoot argv assembly and argument fidelity | `scripts/` |
| `wrapper.test.py` | Linux CI checks direct-loader --preload single-process injection and Bionic-child environment isolation | `scripts/` |
| `bash-launcher.c`, `bash-launcher.test.py` | Tier P bin/bash static ELF entry/Linux regressions, replacing libandcode-cmd-bash.so script for direct PTY-daemon exec; no new physical command name | `bundle/launcher/`, `scripts/` |
| `build-android-tinfo.sh`, `android-tinfo.test.py` | Android ncurses build and real initialization/kernel-permission/no-identity-call regressions; pinned Ubuntu source/patches, standard Linux bundle unchanged | `scripts/` |
| `collect-opencode-native-sources.py`, `collect-opencode-native-sources.test.py` | Four pinned native extensions' candidate source-archive digests/build inputs/notices/nested dependencies; evidence collection only, no distribution approval | `scripts/` |
| `native-source-evidence`, `native-source-review.json` | Candidate corresponding-source archives/review index for source experiment; CI diagnostics only, not in APK | Experimental stage/ |
| `collect-opencode-native-runtime.py`, `collect-opencode-native-runtime.test.py` | Collect experimental glibc/GCC shared libraries from CI Ubuntu 24.04 sysroot, validate recursive dependencies/versioned symbols; production bundle unchanged | `scripts/` |
| `runtime`, `native-runtime-review.json` | Source-experiment runtime directory and package versions/source packages/digests/dependency evidence; diagnostics only, not license approval | Experimental stage/ |
| `collect-opencode-native-rust.py`, `collect-opencode-native-rust.test.py` | Query Cargo normal/build graph by candidate release target/features, collect lock-digest-verified registry archives; no build-script execution or distribution approval | `scripts/` |
| `native-rust-evidence`, `native-rust-review.json` | Candidate Rust dependency tree, pinned crate source/notice index and tool versions; not proof of actual npm ELF linkage | Experimental stage/ |
| `serial-rs-<commit>.tar.gz` | Pinned upstream source when serial 0.4.0 lacks bundled notices; verify all crate regular files correspond to serial/ subtree | `native-rust-evidence/` |
| `build-opencode-native-pty.py`, `build-opencode-native-pty.test.py` | CI rebuilds arm64 glibc PTY from pinned bun-pty source/lock, replacing only experimental npm input after checks | `scripts/` |
| `native-pty-build`, `native-pty-build-review.json` | Experimental PTY source/build logs/commands/tool versions/before-after ELF digests; no distribution or Android admission approval | Experimental stage/ |
| `build-opencode-native-watcher.py`, `build-opencode-native-watcher.test.py` | Rebuild pinned Parcel watcher Linux source/N-API headers, replace only experimental npm input after real-file-event checks | `scripts/` |
| `native-watcher-build`, `native-watcher-build-review.json` | Pinned watcher source/header archives/compile commands/event probes/old-new ELF digests; CI diagnostics only | Experimental stage/ |
| `native-watcher-build-inputs.json` | Compiler -H observed regular headers/explicit source digests, origin classification and notice leads; not per-file license approval | Experimental stage/ |
| `build-opencode-native-fff.py`, `build-opencode-native-fff.test.py` | Pinned fff source/lock/zlob-feature Linux arm64 diagnostic rebuild and no-replacement-on-failure regressions | `scripts/` |
| `native-fff-build`, `native-fff-build-review.json` | Pinned fff source/selected crate archives, Cargo messages, GNU link map, Bun search/glob probes, before-after digests; no distribution approval | Experimental stage/ |
| `build-opencode-native-opentui.py`, `build-opencode-native-opentui.test.py` | Pinned OpenTUI/Zig 0.17.0/FFmpeg/zlib Linux arm64 diagnostic rebuild; failure never replaces npm input | `scripts/` |
| `native-opentui-build`, `native-opentui-build-review.json` | Pinned OpenTUI source/patches/build commands/logs/FFmpeg configuration/object digests/before-after ELF evidence; no distribution approval | Experimental stage/ |
| `link-inputs` | Objects/static archives/link-time dynamic-stub copies from actual experimental OpenTUI ld.lld command, retained by argument index with original paths/digests; not runtime libraries or license approval | `native-opentui-build/` |
| `zig-library-resources.tar.gz` | Original lib/ resource/root LICENSE/README bytes from pinned Zig 0.17.0 archive, excluding tool executables; candidate toolchain runtime source/notices, not complete corresponding-source approval | `native-opentui-build/` |
| `crc-probe.c`, `crc-probe`, `crc-probe.log` | Own bitwise-reference/chunked CRC comparison probe, temporary Linux CI ELF and compile/run logs; generic FFmpeg CRC only, not in APK | `native-opentui-build/` |
| `link-replay/`, `link.map`, `archive-extraction.tsv`, `link.log`, `abi.log` | Isolated replay using same pinned Zig linker and retained inputs only, with map/archive-extraction/run logs; requires ELF byte equality, not modified-version relink approval | `native-opentui-build/link-replay/` |
| `andcode-library-only` | Experimental OpenTUI Zig option; configure explicit library-target only, excluding unrelated musl test/benchmark graph, retaining selected-library video gate | Build-time `-D` |
| `manifest-opencode-native.py`, `manifest-opencode-native.test.py` | Full-file SHA-256 inventory/regressions for experimental artifacts; follow internal links, reject escapes/cycles/special files, match uploader file set | `scripts/` |
| `ANDCODE_SERVE_PID` | PID for Linux source-experiment API probe to read own server maps; not device-process discovery/termination | Experimental CI |
| `ncurses-build.txt`, `ncurses-upstream-copying` | Android libtinfo pinned-source digest/build configuration/upstream copyright, tracked by bundle manifest | `etc/third-party/` |
| `proot-app-gate.sh` | Manually triggered minimal PRoot/ptrace admission in app terminal; outputs domain/uid/seccomp/exit code, not full Ubuntu support | `scripts/` |
| `proot-rootfs-gate.sh` | App-domain independent original Ubuntu Base Bash admission, no SELinux/glibc modifications | `scripts/` |
| `proot-development-gate.sh`, `proot-development-gate.txt` | App-domain independent Ubuntu apt/toolchain/new-ELF/PTY validation and APK files diagnostics | `scripts/`, APK `files/` |
| `proot-terminal-test.sh`, `proot-terminal-test.txt` | App-domain launcher arguments/single-project mapping/failure rejection/stdin/exit-code regressions; create/clean only own temporary fixtures | `scripts/`, APK `files/` |
| `term-ubuntu-proot`, `term-ubuntu-proot.sh` | APK assets launch template/filesDir copy interpreted by system sh; maps only one private project selected at session creation, no privilege elevation | APK `assets/`, `files/` |
| `proot-gate.txt` | APK-private temporary development diagnostics | `files/` |
| `proot-rootfs`, `proot-rootfs-gate.txt` | Independent Ubuntu Base instance/diagnostics for rootless-backend admission, no shared writable chroot layer | APK `files/` |
| `ubuntu-base-app-gate.tar.gz` | Independent read-only development copy of fixed-digest official Base for real app-domain reading | `/data/local/tmp/` |
| `prepare-proot-gate.py` | Build-time conversion of fixed-digest Ubuntu Base or an explicitly digested trusted CI rootfs; bounded hardlink materialization, guest-relative links, privilege stripping, unchanged ELF bytes; not an APK installer | `scripts/` |
| `prepare-proot-gate.test.py` | Digest, link, content, resource-limit and no-overwrite regression tests for build-time rootfs conversion; no downloads | `scripts/` |
| `busybox` (root-instance copy) | Reuse independent BusyBox payload for Android Toybox-incompatible bind mounts/archive extraction, root:root 0700 | `/data/adb/andcode-ubuntu/busybox` |
| `ubuntu-base-24.04.4-base-arm64.tar.gz` | Official Ubuntu Base 24.04.4 arm64 development bootstrap input, pinned SHA-256 | Development staging `/data/local/tmp/`, not in repository |
| `andcode-bundle-android-arm64-v<semver>.tar.gz` | Android-app-domain seccomp-patched copy and matching `.sha256`; standard Linux original bundle unchanged | CI artifact, not verified locked delivery |
| `andcode-tier-p-native` | CI intermediate: arm64-v8a native physical names, manifest.farm, assets/andcode-runtime data; not complete self-contained APK | Actions artifact |
| `andcode-apk-intermediate` | CI debug APK/Lint report, validating intermediate native packaging only; not production-signed/self-contained product | Actions artifact |
| `andcodeNativeDir` | Explicit Gradle native-artifact directory containing arm64-v8a/manifest.farm/assets; unset retains payload-free development build | `-PandcodeNativeDir=<absolute-directory>` |
| `andcodeReleaseStoreFile`, `andcodeReleaseStorePassword`, `andcodeReleaseKeyAlias`, `andcodeReleaseKeyPassword` | Fail-closed Gradle release-signing properties; all four present or all absent, partial set fails build; no repository keystore (CI secrets injection), changed signing identity cannot overwrite existing debug-signed install | `-PandcodeReleaseStoreFile=<absolute-path> ...` |
| `ANDCODE_RELEASE_STORE_B64`, `ANDCODE_RELEASE_STORE_PASSWORD`, `ANDCODE_RELEASE_KEY_ALIAS`, `ANDCODE_RELEASE_KEY_PASSWORD` | CI release-signing secrets: base64 keystore and three password/alias values; assembleRelease only with all four, otherwise debug intermediate | GitHub Actions secrets |
| `andcode-apk-release` | CI release-signed APK only when all four signing secrets exist; apksigner v2 passes; changed identity cannot overwrite existing debug-signed install | Actions artifact |
| `term-serve.env` | App-private 0600 env fragment: current managed-serve URL/password, written on readiness/deleted on stop; terminal `opencode()` sources after live probe and connects via `--server`, no self-spawn | APK `files/` |
| `andcode-runtime` | CI-generated read-only bundle data/manifest.farm in APK assets, no runtime-extracted ELF | `assets/andcode-runtime/` |
| `RuntimePayload.java`, `RuntimePayloadTest.java` | APK read-only native-payload link-farm initialization/platform-JDK safety regressions | `dev.andcode.app`, `app/tests/` |
| `pty-launcher.c` | Own static musl PTY entry, locating sibling loader/daemon via /proc/self/exe without fixed install path | `bundle/launcher/` |
| `repair-elf-verdef.py`, `repair-elf-verdef.test.py` | Build-time validation/repair of stale DT_VERDEF after patchelf moves version definitions; addresses only from ELF section table, reject ambiguous layouts | `scripts/` |
| `patch-seccomp.test.py` | Linux CI synthetic-byte fixtures for seccomp patches, idempotence, old-patch upgrades and wrong-baseline rejection | `scripts/` |
| `native-payload-device-test.sh` | Native-payload admission from APK terminal; no adb/run-as substitute for app domain, results only in private data logs | `scripts/` |
| `native-payload-test.txt` | Admission log above, no passwords/model configuration | APK filesDir |
| `opencode-native-imports.ts`, `opencode-native-imports.test.ts` | Bun source-build experimental plugin/regressions replacing native imports with explicit prestaged paths; official binary unchanged | `scripts/` |
| `prepare-opencode-native-build.py` | Pinned-upstream-commit source-experiment wiring, rejects mismatched anchors | `scripts/` |
| `audit-opencode-native.py`, `audit-opencode-native.test.py` | Experimental ELF/dependency/alignment/digest audit/regressions, reject residual Bun-embedded ELF or musl closure | `scripts/` |
| `collect-opencode-native-licenses.py`, `collect-opencode-native-licenses.test.py` | Pinned install-tree native-extension package versions/licenses/bundled notices; missing notices explicitly blocked, not release-license approval | `scripts/` |
| `native-license-review.json`, `native-license-evidence/` | Manual-review TODOs/bundled-notice copies for four experimental native extensions, excluded from production APK | Source-experiment artifacts |
| `runtime-declarations/` | Pinned Bun/WebKit declaration bytes, including selected application-link/Rust/codegen/toolchain/allocator rules and Cargo identities; validate the whole selected set before writing files, not complete corresponding source or release notices | `native-source-evidence/` |
| `bun-<commit>.tar.gz`, `bun-source-inventory.json` | Fixed Bun candidate source archive and bounded member inventory; original archive bytes only, no extraction or upstream script execution, not a complete source/relink kit | `native-source-evidence/` |
| `sort-test`, `sort-test.log` | Standalone Rust test ELF/compile/run logs for own standard-library stable-sort adapter; Linux source experiment only, excluded from APK | `native-fff-build/` |
| `ffmpeg-notice-candidates.json` | Candidate-notice comment byte ranges/original text/digests retained from full actual compile dependencies; not production notices or complete license determination | `native-opentui-build/` |
| `zig-generated-sources/` | Original bytes and per-file digests of `b/<hash>/builtin.zig` from the pinned Zig global/local caches after building; generated-input snapshots only, not proof of complete compiler inputs | `native-opentui-build/` |
| `modified-crc-relink/` | Isolated modified FFmpeg CRC source, replacement object, retained-input relink, map and runtime probes; Linux diagnostic only, never a staged APK input | `native-opentui-build/` |
| `media-generator-replay/`, `ops_lookup.gen.c`, `ops_neon.gen.S`, `lookup.log`, `neon.log` | Build-only isolated stdout/logs from fixed FFmpeg `ops_asmgen -lookup` / `-ops`; byte comparison with retained generated inputs, not a license or full-source approval | `native-opentui-build/` |
| `media-generator-rebuild/`, `source/`, `system-headers/`, `ops_asmgen`, `ops_asmgen.o`, `ops_asmgen.d`, `ops_asmgen.i`, `compiler.log`, `compile.log`, `link.log`, `preprocess.log`, `lookup.log`, `neon.log`, `ops_lookup.gen.c`, `ops_neon.gen.S` | Isolated host-generator recompilation, complete observed dependency snapshots, preprocessing and two-mode output comparison; build-only diagnostic, never staged in an APK | `native-opentui-build/` |
| `media-preprocess/`, `inputs/`, `<sha256>`, `<index>.i`, `<index>.s`, `<index>.d`, `<index>.log` | Post-build fixed-Zig preprocessing samples and content-addressed observed dependency snapshots for recorded media translation units; not proof of the original compile-time input set | `native-opentui-build/` |
| `media-object-relink/`, `objects/`, `<index>.o`, `<index>.log`, `libopentui.so`, `link.log`, `link.map`, `archive-extraction.tsv`, `abi.log`, `crc-probe`, `crc-probe.log`, `crc-execution.log` | Isolated recompilation of all sampled media units, with the separately instrumented CRC object substituted for execution probes; no staged APK inputs, original-object byte equality or complete modified-source claim | `native-opentui-build/` |
| `probe-opencode-media-tui.py`, `probe-opencode-media-tui.test.py` | Isolated replacement-library PTY/TUI diagnostic and synthetic rejection tests; never modify the staged native baseline | `scripts/` |
| `media-tui/`, `native/`, `home/`, `tmp/`, `tui.log`, `tui-output.bin`, `tui-maps.txt`, `review.json` | Replacement OpenTUI TUI diagnostic, original-name lookup alias with explicitly different digest, copied other native files, isolated extraction directories and mapping/render evidence; not a valid release payload | `media-object-relink/` |
| `source-rules` | Explicit diagnostic selector for fresh source-rule replacement-library TUI; fixed input/output under modified-media-source-relink, never an arbitrary path override | `probe-opencode-media-tui.py` fourth argument |
| `media-tui/`, `native/`, `home/`, `tmp/`, `tui.log`, `tui-output.bin`, `tui-maps.txt`, `review.json` | Fresh source-rule library TUI evidence isolated from the sampled-object TUI and all staged native inputs; not a release manifest or Android admission | `modified-media-source-relink/` |
| `rebuild-zlib-generators.py`, `rebuild-zlib-generators.test.py` | Isolated host reconstruction of zlib MAKECRCH/MAKEFIXED and a same-translation-unit GEN_TREES_H harness, retained preprocessing inputs and byte-comparison rejection tests | `scripts/` |
| `gentrees/`, `trees-generator.c`, `trees.h` | Own same-translation-unit entry point for the fixed upstream static tree initializer and isolated GEN_TREES_H output; not an upstream standalone build command or release input | `zlib-generator-rebuild/` |
| `swscale-generator-rebuild/`, `build.log`, `run.log`, `uops_macros.h` | Configured source-rule build of libswscale/tests/sws_ops and isolated -macros stdout comparison; test executable remains in the copied media build tree, never a release input | `modified-media-source-rebuild/` |
| `rebuild-modified-media.py`, `rebuild-modified-media.test.py` | Isolated fresh configured FFmpeg/zlib source-rule rebuild with the pinned CRC instrumentation; no sampled-preprocessor reuse or baseline replacement | `scripts/` |
| `modified-media-source-rebuild/`, `native/`, `build.log`, `review.json` | Fresh copied build script, pinned media archives/pristine source trees, modified CRC source, configure/make outputs and full selected-media object evidence; not complete corresponding-source or distribution approval | `native-opentui-build/` |
| `failed-modified-media-source-build` | Failed isolated modified media source-rule inputs, logs and partial outputs; diagnostic evidence only | CI artifacts |
| `relink-modified-media.py`, `relink-modified-media.test.py` | Relink retained non-media OpenTUI inputs with all fresh source-rule media objects, then run isolated ABI/CRC probes; no baseline or APK replacement | `scripts/` |
| `modified-media-source-relink/`, `libopentui.so`, `link.map`, `archive-extraction.tsv`, `link.log`, `abi.log`, `crc-probe`, `crc-compile.log`, `crc-run.log`, `review.json` | Fresh source-rule library substitution and Linux ABI/CRC evidence; not full source, decoder, TUI or legal approval | `native-opentui-build/` |
| `zlib-generator-rebuild/`, `source/`, `system-headers/`, `makecrch/`, `makefixed/`, `generator`, `<index>.i`, `<index>.d`, `<index>.o`, `<index>-preprocess.log`, `<index>-compile.log`, `link.log`, `run.log`, `compiler.log`, `crc32.h`, `inffixed.h`, `review.json` | Copied pristine zlib source, host-header snapshots and isolated generated outputs; never replace media build inputs or assert toolchain/source closure | `native-opentui-build/` |
| `original-crc.c`, `modified-crc.c`, `crc.patch`, `crc.o`, `crc.d`, `compile.log`, `link.log`, `source/`, `build/` | Original/transformed bytes, recorded diff, replacement object/dependencies, logs and isolated configured trees for the single-object relink diagnostic | `modified-crc-relink/` |
| `andcode_crc_relink_calls` | Diagnostic-only exported counter accessor added to the modified CRC translation unit; not a product ABI | Experimental `modified-crc-relink/libopentui.so` |
| `failed-fff-build-logs` | Diagnostic sort/compile logs retained on experimental fff build failure, no distribution approval | CI artifacts |
| `build-ubuntu-mmdebstrap.sh` | Build-only native arm64 mmdebstrap experiment; signed Ubuntu snapshot `20261110T000000Z`, independent output, no device installer | `scripts/` |
| `build-ubuntu-mmdebstrap.test.py` | Native Linux rejection tests for recipe arguments, architecture and existing outputs; skipped on Windows | `scripts/` |
| `collect-ubuntu-sources.py`, `collect-ubuntu-sources.test.py` | Build-only exact installed source-version acquisition through authenticated apt; no source extraction, compilation or license approval | `scripts/` |
| `andcode-ubuntu-source-inputs/`, `andcode-ubuntu-source-inputs.json` | Experimental per-source downloaded .dsc/archive files and command logs, with a hash inventory; staged in a new guest `/tmp/andcode-ubuntu-source-inputs` directory and copied outside the image | Optional mmdebstrap CI artifact |
| `andcode-ubuntu-source-acquisition.log` | Build-only source download progress/failure diagnostic; no source-delivery approval | Optional mmdebstrap CI artifact |
| `andcode-ubuntu-rootfs.tar.gz` | Validated canonical rootfs archive from the mmdebstrap experiment; input for future PRoot packaging, not an APK importer | Experimental CI artifact |
| `andcode-ubuntu-proot.tar.gz`, `andcode-ubuntu-proot.tar.gz.sha256` | Build-time trusted canonical rootfs conversion and digest; hardlinks materialized and absolute symlinks made guest-relative, no ELF patching or device installation | Experimental mmdebstrap artifact |
| `andcode-ubuntu-rootfs.tar.gz.sha256`, `mmdebstrap.log`, `mmdebstrap-copyright`, `ubuntu-indexes/`, `ubuntu-sources.list` | Archive digest, bootstrap log, installed tool notice, retained signed indexes and exact source configuration | Experimental rootfs output |
| `andcode-ubuntu-mmdebstrap-prototype` | Independently gated rootfs experiment artifact; never replaces the Docker artifact automatically | CI artifacts |
| `andcode-ubuntu-mmdebstrap-diagnostics` | Failed bootstrap logs and metadata only; no image/archive release payload | CI artifacts |
| `probe-opencode-native.py` | Linux CI experimental API admission: ordinary/persistent PTY and shell, password memory-only, never printed | `scripts/` |
| `probe-opencode-native-tui.py` | Linux CI independent PTY launches source-experiment TUI, requiring actual prestaged OpenTUI mapping/rendering; terminate only own process group | `scripts/` |
| `opencode-native-prototype.yml` | Manual prestaged-native-extension source-build experiment; failed/unaudited artifacts cannot enter APK | `.github/workflows/` |
| `bun-source-build-experiment.yml` | Manual pinned-commit Bun candidate source-build experiment: pinned toolchain identity, dependency acquisition, configure-only ninja generation; diagnostic only, no official-ELF correspondence/license approval | `.github/workflows/` |
| `bun-source-build-experiment`, `bun-source-build-failure` | Experiment diagnostics: source/toolchain/dependency identities, configure logs/failure state; excluded from APK/bundle | CI artifacts |
| `libandcode-oc2-native-<first-16-sha256-chars>.so` | Experimental Bun-plugin content-named prestaged native extension, full-digest deduplication/collision checks | Experimental native/ output |
| `oc2-native.tsv` | Origin/full-digest/length records for those copies; not production bundle manifest | Experimental output |
| `libandcode-usr-lib-opencode-pty-opencode-pty.so` | Prestaged process-daemon v0.4.0 ELF; static libandcode-opencode-pty.so entry explicitly invokes loader | nativeLibraryDir |
| `oc2` | Pinned V2.2.6 ELF logical name for serve, separate from legacy opencode; physical name libandcode-oc2.so | bundle bin/oc2.bin |
| `etc/third-party/opencode-v2-license`, `etc/third-party/opencode-pty-license` | Pinned-version MIT copyright/license texts delivered as data | bundle/APK assets |
| `andcode-runtime-<sha256>`, `andcode-runtime-stage-<random-value>` | filesDir link/data directories and atomic staging keyed by manifest/nativeLibraryDir identity; never copy ELF or delete old versions | APK filesDir |
| `libandcode-git-core-<command>.so` | Unified git-core wrapper/own-launcher prefix, avoiding git/receive-pack/upload-pack collisions with usr/bin/*.bin | Tier P nativeLibraryDir |

**Exemption**: fixed Magisk filenames (`customize.sh`, `service.sh`, `uninstall.sh`,
`module.prop`) follow official Magisk conventions, exempt from §2.1's "no .sh" rule.
**Reserved area**: own APK NDK libraries (jackpal fork, etc.) **must not** use `libandcode-`,
avoiding packaging-toolchain confusion; retain original library names (`libterminal-jni.so`, etc.).

## 4. Logical-name specification (user perspective)

### 4.1 `bin/` — Interactive commands (in PATH)

| Logical name | Type | Description |
|---|---|---|
| `opencode` | Wrapper script | Set env → exec `opencode.bin` (canonical)/ `libandcode-opencode.so` (Tier P) |
| `opencode-pty` | Upstream passthrough (runtime-downloaded terminal-plugin helper) | Upstream writes `~/.cache/opencode/bin/opencode-pty/<version>/` and checks "regular file+uid+sha256" (rejects symlinks); app-domain exec prohibition → **prestage + redirect**: serve/terminal env sets `OPENCODE_PTY_BIN` to copy, `OPENCODE_PTY_SOCKET_DIR` to app filesDir (§5); Tier P physical `libandcode-opencode-pty.so`; development interp short path must be executable regular loader file, never assume symlink reachability |
| `git`, `ssh` | Upstream passthrough (farm links to physical names) | For internal opencode spawn and users |
| `bash` | Upstream interactive shell, Ubuntu 24.04 independent-program aggregation; terminal prefers prestaged copy | `root/bin/bash.bin` → `libandcode-bash.so`; wrapper `libandcode-cmd-bash.so` |
| `andcode-doctor` | Project-owned | Environment diagnostics: loader/shim/DNS/JIT/phantom-killer status and report |
| `andcode-ubuntu-proot` | Development-terminal shell function, explicitly enters installed independent PRoot instance, returns to original Bash | Interprets `term-ubuntu-proot`; not a completed self-contained installation product entry |
| `andcode-sshd` | Project-owned | Bundled dropbear lifecycle through `start|stop|status` subcommands |
| `opencode-tui` | Upstream passthrough | Prestage under this logical name if opencode is confirmed to invoke TUI by name (DESIGN §4.1) |

### 4.2 `sbin/` — Service/maintenance entries (outside default PATH)

| Logical name | Description |
|---|---|
| `andcode-entry` | Unified entry (renamed entry.sh): initialize env, generate `etc/resolv.conf`, dispatch arguments |
| `andcode-mkresolv` | Generate resolv.conf from Android `net.dns*` (independently reusable by service.sh) |
| `andcode-ubuntu` | Root management prototype: `status|shell|exec|admin`; separate mount namespace per session, exit cleanup; default non-root, explicit admin request, not yet exposed to APK/model |
| `andcode-ubuntu-install` | Root installation prototype; only trusted gzip image at fixed staging path and out-of-band SHA-256, reject existing-instance overwrite; ≥5 GiB free |

## 5. Environment-variable specification

| Variable | Meaning | Example value |
|---|---|---|
| `NODE_EXTRA_CA_CERTS` | Upstream Bun/Node additional CA file; Tier P sets only after explicit enablement for new OpenCode Web backends/inheriting children, retaining built-in roots | App-private `custom-ca/<sha256>.pem` |
| `ANDCODE_ROOT` | Logical root (wrapper path resolution) | `/data/adb/andcode`, `$HOME/andcode` |
| `ANDCODE_EXE_DIR` | Physical executable directory | Tier P = `nativeLibraryDir`; others = `$ANDCODE_ROOT` |
| `ANDCODE_LOADER` | Absolute glibc dynamic-linker path (launcher) | `$ROOT/lib/ld-linux-aarch64.so.1` |
| `ANDCODE_LIBPATH` | `--library-path` value (launcher) | `$ROOT/lib` (canonical)/`$ANDCODE_EXE_DIR` (Tier P) |
| `ANDCODE_SHIM` | Absolute shim path (launcher) | `$ROOT/shim/libandcode-shim.so` |
| `ANDCODE_NATIVE_STAGE` | Independent build-only output for experimental Bun prestaged-extension plugin; not APK runtime installer | CI work/native-prototype |
| `ANDCODE_TIER` | Single lowercase-character form identifier, matching DESIGN sections | `m` / `a` / `p` |
| `ANDCODE_UBUNTU_PROJECT_NAME` | Private-project name snapshotted at new-terminal creation; empty means no mapping; entry validates directory/canonical path, rejects symlinks/escapes/arbitrary host paths | `andcode-demo` → guest `/workspace/andcode-demo` |
| `ANDCODE_BUNDLE_VERSION` | Bundle semantic version | `1.2.0` |
| `ANDCODE_LOG` | Log level | `debug\|info\|error` |
| `OPENCODE_PTY_BIN` | Upstream v2 prestaged PTY executable override, bypassing cache install/validation | Tier P = `nativeLibraryDir/libandcode-opencode-pty.so`; development `/data/local/tmp/andcode/lib/opencode-pty` |
| `OPENCODE_PTY_SOCKET_DIR` | Upstream process-daemon v0.4.0 socket base override; appends `opencode-pty-<uid>/<32 hex>.sock` and checks directory/uid/0700 | Direct APK backend: `Context.getFilesDir()`; managed Ubuntu PRoot backend: guest `/tmp`. Complete socket path must be <104 UTF-8 bytes. |

- Passthrough: users may pass upstream variables such as `OPENCODE_*`; wrappers set only registered
  `ANDCODE_*` and required runtime variables (`HOME`, `TMPDIR`, `PATH`, `LD_PRELOAD`,
  `LD_LIBRARY_PATH`, `GIT_EXEC_PATH`), **never overriding** explicitly set user `OPENCODE_*`.
- Unregistered environment names are prohibited; register additions through §8 first.

## 6. Physical-name specification

Tier P optional-CA data registry: `CustomCa.java` / `CustomCaTest.java` are app-side validation/
platform-JDK test classes; `files/custom-ca/<sha256>.pem` is a user SAF-imported single-certificate copy;
`custom-ca-enabled` / `custom-ca-sha256` are app-private preference keys. Default off, no prestaged
site CA, online downloads, native-manifest entries or Android global trust-store changes.
`scripts/custom-ca-tls.test.py` tests pinned Bun loopback TLS additional trust/wrong-hostname rejection,
generating only temporary test CAs, never downloading or persistently trusting external certificates.

### 6.1 Canonical layout (inside bundle, binding Tier M/A)

```
root/bin/opencode            # Wrapper script (logical name = filename)
root/bin/opencode.bin        # Upstream ELF (.bin suffix only in this context)
root/usr/bin/git ...         # Upstream passthrough, original name
root/sbin/andcode-entry      # Project-owned, no extension
root/lib/ld-linux-aarch64.so.1   # glibc loader, original name (explicit invocation, not DT resolution)
root/lib/libc.so.6 ...           # glibc dependencies, original names (soname contract)
shim/libandcode-shim.so      # Project LD_PRELOAD library (§6.3)
```

### 6.2 Slug derivation algorithm (Tier P repackaging by `bundle/pack-apk-libs.sh`)

For each canonical-layout file, apply this table by **file kind** (fixed in manifest by
`pack-bundle.sh`; criteria in parentheses):

| Logical path (canonical layout) | kind | Tier P physical name (jniLibs) |
|---|---|---|
| `root/bin/opencode.bin` (upstream ELF, `.bin` suffix) | elf-exec | `libandcode-opencode.so` (slug **strips `.bin`**) |
| `root/bin/opencode` (upstream-command wrapper, identified by sibling `<name>.bin`) | wrapper-sh | `libandcode-cmd-opencode.so` (add **`cmd-`** segment under `bin/`, `usr/bin/`) |
| `root/usr/bin/git` | elf-exec/wrapper-sh | Same rule (`git.bin` exists → wrapper) |
| `root/usr/libexec/git-core/git-remote-https` (git-helper wrapper) | wrapper-sh | `libandcode-git-core-git-remote-https.so` (uniform **git-core-** prefix under libexec) |
| `root/usr/libexec/git-core/git-remote-https` (same path, **launcher form**: static ELF replaces shell script to bypass git-spawn shell chain; P0 device check) | launcher | `libandcode-git-core-git-remote-https.so` (same wrapper rule) |
| `root/usr/libexec/git-core/git` (own launcher) | launcher | `libandcode-git-core-git.so` (avoids collision with `usr/bin/git.bin` ELF physical name) |
| `root/usr/lib/proot/proot` (proot-me v5.5 unusable, x86-64; use **Termux proot 5.1.107 bionic build** + loader + libtalloc + libandroid-shmem, independent GPL-2.0 aggregation) | elf-exec(bionic) | `libandcode-usr-lib-proot-proot.so` (full-path slug; **bionic binary, no glibc loader, list separately for Tier P**) |
| `root/usr/libexec/git-core/git-remote-https.bin` (helper ELF) | elf-exec | `libandcode-usr-libexec-git-core-git-remote-https.so` (full-path slug; distinct from wrapper, no collision) |
| `root/sbin/andcode-entry` (own script, no same-name `.bin`) | script | `libandcode-andcode-entry.so` (`andcode-` in slug allowed) |
| `root/lib/ld-linux-aarch64.so.1` (loader exception: explicit-path invocation) | glibc-lib | `libandcode-ld-linux.so` |
| `root/lib/libc.so.6` (DT_NEEDED dependency) | glibc-lib | `libandcode-libc.so` (slug **strips `.so.N` version suffix**) |
| `root/lib/libstdc++.so.6` | glibc-lib | `libandcode-libstdc---.so` (slug sanitization below) |
| `shim/libandcode-shim.so` (own LD_PRELOAD library) | preload-lib | `libandcode-shim.so` (original name already compliant) |
| Data files such as `root/etc/ssl/certs/ca-certificates.crt` | data | **`-`** (no data in jniLibs: read-only data goes unchanged through APK assets → filesDir; also avoids >64-character paths) |
| `opencode-pty/<version>/opencode-pty` (upstream runtime-downloaded plugin, outside bundle layout; prestaged copy enters jniLibs) | elf-exec(MIT, upstream sst/opencode process-daemon) | `libandcode-opencode-pty.so` (same-name sanitized slug; packaging rewrites interp, see §4.1 redirection policy) |

**Slug character sanitization** (after `/`→`-`): retain only `[a-z0-9-]`, replacing every other character with `-`
(`+`, `_`, `.`, etc. individually; do not collapse consecutive results). Full physical name (including `libandcode-`/`.so`) ≤64.

### 6.3 Two key rulings

1. **DT_NEEDED libraries (glibc/libstdc++, etc.)**: soname must match `NEEDED` byte for byte;
   simple renaming is insufficient. P0 decides between two routes:
   - **Route A (default)**: rewrite the entire sysroot closure with `patchelf` during packaging
      (`libc.so.6 → libandcode-libc.so`, updating SONAME and all NEEDED together),
      place alongside executables in `nativeLibraryDir` — simplest single executable directory;
      **glibc exception**: libc retains `libc.so.6` SONAME (loader uses it for
      `__libc_early_init`); only callers' NEEDED uses physical name. Rename loader physically to
      `libandcode-ld-linux.so`, retaining its own SONAME and libc's original NEEDED for loader.
   - **Route B (if P0 proves data-directory mmap-exec works)**: retain original dependency names, extract via assets
     into `filesDir/lib`, point `--library-path` there.
   Either way, **physical namespace always remains `libandcode-*`**, with logical names in manifest.
2. **Tier P wrapper representation**: targetSdk 37.2 prohibits exec of data-directory files,
   so wrappers enter jniLibs as **shebang script bodies** (`libandcode-cmd-*.so`, first line
   `#!/system/bin/sh`), reached by logical-name farm links. Direct-reading `sh <script>` is permitted
   only inside project-owned code, not as a user-facing contract.

### 6.4 Link farm (generated on first launch)

```
$ANDCODE_ROOT/bin/opencode   -> $ANDCODE_EXE_DIR/libandcode-cmd-opencode.so
$ANDCODE_ROOT/bin/git        -> $ANDCODE_EXE_DIR/libandcode-git.so
$ANDCODE_ROOT/usr/libexec/git-core/git-remote-https
                              -> $ANDCODE_EXE_DIR/libandcode-git-core-git-remote-https.so
```

- PATH contains only `$ANDCODE_ROOT/bin` and `$ANDCODE_ROOT/usr/bin`;
- git `GIT_EXEC_PATH` points to farm `usr/libexec/git-core`;
- With static launcher, `bin/git` is the only command entry; discard packager's duplicate
  `usr/bin/git` wrapper (retain `usr/bin/git.bin`); all non-data physical names must be unique, no overwrite.
- **Prohibition**: no farm entries sharing Android `/system/bin` (toybox) names
  (`ls`, `cp`, `sh`, etc.); invoke busybox applets explicitly as `busybox <applet>`,
  never placing applet symlinks in PATH.

## 7. Release artifacts and manifest

### 7.1 Release artifact naming

| Artifact | Name |
|---|---|
| Bundle | `andcode-bundle-arm64-v<semver>.tar.zst` |
| APK | `andcode-v<semver>-arm64.apk` (applicationId: §3) |
| Magisk module | `andcode-magisk-v<semver>.zip` |
| Checksum file | Same name + `.sha256` |
| Standard Linux artifact | `andcode-linux-arm64-v<semver>.tar.gz` (DESIGN §3 compatibility target) |
| Ubuntu development image (prototype) | `andcode-ubuntu-arm64.img.gz` + `.sha256`, 4 GiB ext4; trusted CI artifact only, not production release |

### 7.2 Manifest syntax (`bundle/manifest`, TSV, `#` comments)

```
# logical-path \t physical-tier-p \t kind \t license \t version \t upstream
root/bin/opencode.bin	libandcode-opencode.so	elf-exec	MIT	1.1.2	sst/opencode
root/bin/opencode	libandcode-cmd-opencode.so	wrapper-sh	AGPL-3.0-only	1.0.0	andcode
root/lib/libc.so.6	libandcode-libc.so	glibc-lib(rewritten)	LGPL-2.1	2.39	glibc
shim/libandcode-shim.so	libandcode-shim.so	preload-lib	AGPL-3.0-only	1.0.0	andcode
```

Rules: `physical-tier-p` must satisfy §6.2 algorithm; `kind` is
`elf-exec|wrapper-sh|launcher|glibc-lib|preload-lib|script|data|alias` (launcher =
static musl launcher from `bundle/launcher/launcher.c`, AGPL); CI generates
`THIRD-PARTY-NOTICES.md` from this (REUSE.md §4).

## 8. Registry change process and CI gates

1. New commands/variables/aliases/physical names → update §3/§4/§5 first, then code;
2. CI gate `scripts/naming-lint.sh` (established in P1) enforces:
   - Manifest physical-tier-p matches `^libandcode-[a-z0-9-]+\.so$` and ≤64 characters;
   - Bundle `bin|sbin` filenames match `[a-z0-9-]+` (except `.bin` dual-name rule);
   - Farm denylist = build-time-fixed `adb shell ls /system/bin` snapshot;
   - Own APK NDK library names must not begin `libandcode-`;
   - Repository shell scripts only `scripts/**.sh`;
3. Violations fail build; exceptions (§3 exemption) must appear as explicit allowlist in that script.
