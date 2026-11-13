[![CI](https://github.com/Arjata/andcode-android/actions/workflows/andcode-ci.yml/badge.svg)](https://github.com/Arjata/andcode-android/actions/workflows/andcode-ci.yml)

# andcode

Port [opencode](https://github.com/sst/opencode) (a terminal AI coding agent) to Android arm64,
with a **compatible Linux arm64 build environment** (baseline: Ubuntu 24.04 arm64 / glibc 2.39;
native programs built in this environment run directly on standard Linux arm64 devices with glibc ≥ 2.39).

Target devices:

- Bootloader locked (no root) → adb-pushed bundle (Tier A) or custom APK (Tier P), including a loader/glibc sysroot
- Bootloader unlocked + root → real chroot / Magisk module

Platform baseline: **Android 12+ (minSdk 31)**, APK `compileSdk/targetSdk 37.2`.
See **[docs/DESIGN.md](docs/DESIGN.md)** for architecture, build baseline specifications, the three self-contained
delivery forms, phased plans, and risk tables; **[docs/REUSE.md](docs/REUSE.md)** for research on reusable open-source projects;
and **[docs/NAMING.md](docs/NAMING.md)** for executable tool entry-point naming conventions.

**Design principle: self-contained** — no dependency on third-party host apps beyond the Android system (no Termux).
Delivery forms are a Magisk module (root) / adb-pushed bundle (locked) / custom minimal APK (locked).

Tier P currently provides an interactive Bash terminal (enter `opencode` manually; sessions remain in the same process) and a Web GUI.
The terminal shows a prompt on first entry, with two extra-key rows below (ESC/TAB/CTRL/ALT/arrows/page navigation, etc.).
Tap CTRL/ALT to latch and tap again to release; the IME key toggles the soft keyboard. If Bash is not deployed, an explicit message announces fallback to system sh.
Web PTY creation and command echo have been verified in the app domain on an older device; for preinstalled executable copies and socket redirection, see
[DESIGN v0.4.54 §4.4](docs/DESIGN.md#44-tier-p--custom-minimal-apk-user-facing-form-for-locked-devices).
The Web terminal supports character-by-character input, backspace, and enter with Android LatinIME; other input methods remain unverified.
Home in the Web/terminal drawer explicitly returns to the app dashboard; leaving Web cancels delayed page tasks and releases the view.
The drawer adds **Projects · Import / Export** and **Settings**:
- Optional custom CA (default off): select a single PEM, verify its file SHA-256 obtained through an independent trusted channel,
  then explicitly enable it. Trust is added only to the next OpenCode Web backend launch and child processes inheriting its environment,
  preserving default root certificates. It does not change the system/WebView/standalone terminal/Ubuntu or automatically download or bundle site CAs.
  Importing/disabling does not interrupt an existing service; manually stop and restart the backend to apply changes. Device scope and remaining issues follow below.
  Regular CI `42609380415` and source-experiment CI `42609429688` for commit `c3a7574` succeeded:
  all 26 CA security checks on arm64 passed, as did the pinned Bun checks for rejection when disabled/success when enabled/wrong-hostname rejection/
  rejection after disabling again. This CI does not replace Android settings import or provider end-to-end verification.
  2026-11-09 device update: same-signature overwrite installation preserved data; SAF import/wrong-digest rejection/disabled state after import/
  backend start-stop environment checks all passed. Under real `untrusted_app`, Seccomp=2, and SELinux Enforcing,
  an explicit loopback proxy + CA enabled the default model with streaming, interruption, and resumption; disabling the CA rejected the certificate.
  The provider returned HTTP 400 after the first tool-result submission. On 2026-11-10, on the same device with explicit proxy+CA, a fresh session
  completed two consecutive full tool round trips; the old acceptance session still returned 400. The history-replay root cause remains unresolved; no sessions were deleted
  or protocol changes made. Default direct networking previously still had DNS `EAI_AGAIN` and was not retested in this round; no fix to default networking is claimed.
  The earlier diagnostic backend was stopped with CA trust off; see the newer
  managed-backend verification below and DESIGN for the exact acceptance scope.
- Managed-backend loopback proxy (default off): explicitly opt into
  `http://127.0.0.1:7890` in network-trust settings, then manually stop and
  restart the service. The device must provide that proxy separately; direct
  networking does not require a third-party host app. TLS verification stays
  enabled and private CA trust is a separate opt-in. On 2026-11-11 device
  `8c8da214`, SAF CA import + both opt-ins + restart produced the expected TUI
  reply from `arjata/gpt-oss-120b`. A subsequent shell command succeeded, but
  its tool-result continuation received provider HTTP 400 (`openai_error`);
  full tool round trips remain unresolved. This device retains both opt-ins
  enabled; other devices/networks remain pending P0/P3 verification.
  PC debugging uses `adb -s 8c8da214 forward tcp:14096 tcp:4096`; the Web GUI
  is served at `/` and authenticated JSON endpoints at `/api/*` use HTTP Basic
  with the managed password. Never publish that password or expose the port
  to the LAN. See [DESIGN §4.4](docs/DESIGN.md#44-tier-p--custom-minimal-apk-user-facing-form-for-locked-devices).
- Material 3 grouped-card layout; the project card overflow menu offers copy/export, and settings provide an immediate font-size preview.
- Managed Ubuntu PRoot backend (experimental, default off): enable
  **Run the OpenCode service in Ubuntu PRoot (experimental)**, then manually stop and restart the
  service. The installed PRoot instance and complete APK runtime payload are
  required; missing prerequisites fail without direct fallback. Web/TUI keep
  `127.0.0.1:4096`, while tools and Web PTY run in Ubuntu under the app UID.
  App home is shared as guest `/root`; terminal-backend/project selection remains
  separate. Proxy and custom CA are independent opt-ins, with TLS verification on.
  On device `8c8da214`, Web/API, a plain-text model response, Ubuntu shell commands,
  Web PTY, home writeback and manual stop/restart passed. Tool commands exited 0,
  but provider continuation still returned HTTP 400/503; full model/tool round trips
  remain unresolved. Overwrite-install retest of the reviewed build preserved the
  opt-ins and reproduced the same boundary set (plain reply OK, tool executed,
  continuation 400/503 in 4/4 fresh sessions), confirming the provider error is
  not introduced by the review changes. Cross-model isolation attributes the
  defect to the gpt-oss-120b tool path: a full agentic tool round trip (shell
  executed, result resent, reply received) passed on `arjata/glm-5.2` through the
  same PRoot backend — use a model with a working tool path for agentic sessions.
  A five-step toolchain chain (write C file, gcc compile, run, readelf-verify
  AArch64) then passed end to end on glm-5.2; the guest also exposes
  python3/make/git 2.43.0, and other gateway models are currently unrouted.
  Externally built arm64 executables (adb-staged musl-static busybox, the APK
  pty launcher, glibc oc2 via the guest loader) all ran exit 0, including
  model-dispatched execution. Single-APK first-launch flow validated on
  device: a fresh install auto-extracts the embedded 193 MB canonical
  rootfs (digest marker published, PRoot serve up, guest gcc/git/mawk
  sanity all green). A model-driven multi-library dynamic build
  (gcc -lm -lpthread -ldl -lz with runtime dlopen and zlib) also passed, with
  the model recovering from a missing dev header via apt on its own.
  Other devices and locked delivery remain pending P0/P3.
  See [Ubuntu acceptance](docs/UBUNTU.md#managed-opencode-serve-in-ubuntu-proot) and
  [DESIGN §4.4](docs/DESIGN.md#44-tier-p--custom-minimal-apk-user-facing-form-for-locked-devices).
- Project/settings navigation includes icons; the standalone terminal supports two-finger spread/pinch font resizing (10–28 sp),
  automatically saved and synchronized with settings without recreating the terminal session.
- Use the system file picker to import ZIP/folder copies into the app-private workspace or export a project ZIP;
  each operation is limited to 512 MiB, 20000 entries, and 64 levels. Same-named projects are not overwritten, and export does not follow symbolic links.
- Copy a project path to open it in Web; selecting a project sets the starting directory for new terminals, without automatically running cd in existing sessions.
- Configure terminal font size, terminal/Web keep-screen-on behavior, and .git export (default off). Other hidden files are still exported;
  check for sensitive data such as .env. Imports do not automatically synchronize with the source folder, and uninstalling the app deletes private projects.
ZIP import/export content round trips, folder import, and project terminal directories have been verified on the older device; other providers and large projects
remain pending P3 device verification. ZIP data-component tests run independently in CI's `app-data-tests`.
This is still a development deployment; complete self-contained jniLibs/CI integration and locked-device verification are not yet complete.

An isolated native-source experiment rebuilt OpenTUI, watcher, fff, and
bun-pty from pinned sources in Linux arm64 CI, passing preinstalled-library mapping, ordinary/persistent PTY, TUI, and no-runtime-ELF-extraction gates; it is **not yet
integrated into the production APK**. FFmpeg directory links caused gaps in the initial artifact's full-file inventory; this was fixed,
and the subsequent CI `42628073140` artifact's 29345-entry file/digest inventories matched completely and passed entry-by-entry verification. Licensing/relinking materials, Bun/JSC
obligations, and Android admission remain unapproved; see the [native-experiment review record](docs/REUSE.md#21-core-delivery-components-permissive-licenses-bundled).
Subsequent per-file preliminary review found that FFmpeg CRC assembly objects carrying GPL notices were still
linked despite GPL being disabled in configuration. Existing experimental artifacts remain prohibited from production distribution. The exclusion recipe and actual source-dependency gate have now passed
source CI `42646838972`; the new artifact's 29789-entry inventory, 446 link inputs, CRC object exclusion, and
2304 generic CRC comparison sets have been reviewed. Other per-file notices, relinking, Bun/JSC, and Android
admission remain unapproved; configuration strings or successful Linux CI cannot substitute for license review.

The Ubuntu development environment is implementing two backends: a new Ubuntu 24.04 arm64 development-image recipe,
a root chroot prototype for ordinary-user sessions, and separate CI. PRoot in the older device's real app domain has passed explicit-proxy
HTTPS/apt, newly installed/compiled ELF, PTY/child-process, and glibc-update checks. The terminal provides
the `andcode-ubuntu-proot [loopback-proxy]` development entry point, returning to lightweight Bash on exit.
Settings can select the Ubuntu development terminal for new sessions; lightweight Bash remains the default, and the proxy toggle defaults to off.
A selected private project can map to `/workspace/<project-name>`; HTTPS/apt/Git without an explicit proxy passed
on the older device with TCP DNS (the device's existing VPN remains enabled).
**Not yet integrated with OpenCode/Web PTY and still not a locked self-contained delivery**; chroot network identity,
the authenticated root service, and chroot project mapping remain pending P0/P3 device verification. Read-only diagnostics confirmed that the device's restricted
network rules block UID 60000; no device policy was changed and no APK UID was borrowed to bypass this.
See [docs/UBUNTU.md](docs/UBUNTU.md) for status, trusted image installation, and the acceptance checklist.

An isolated native-arm64 `mmdebstrap` CI experiment now evaluates tool-built
Ubuntu rootfs archives and ext4 images from signed repositories. Docker remains
the default pending CI review; existing device instances are not replaced.
See [the rootfs tool experiment](docs/UBUNTU.md#rootfs-tool-experiment).
The isolated candidate also converts that canonical tree to a PRoot archive
without changing ELF bytes (trusted CI and independent archive review passed).
A new read-only original-image/tree comparison gate awaits Linux CI;
trusted device installation remains pending.
The next optional bootstrap pins guest packages to an explicit official HTTPS
snapshot without disabling apt authentication; complete source delivery is pending.
An additional experimental gate downloads exact installed source versions via
authenticated apt and retains an external hash inventory; CI review is pending.

License: **AGPL-3.0-only** (see `LICENSE`).

Directories (populated by phase; see design document §5/§6):

```
baseline/       Compatible arm64 build baseline (Dockerfile / rootfs / compatibility audit)
bundle/         Self-contained bundle (glibc dependency closure + loader wrappers + LD_PRELOAD shim)
magisk-module/  Tier M: Magisk module for rooted devices (autostart at boot, no app)
scripts/        adb push deployment (Tier A) and smoke tests
app/            Tier P: custom minimal APK (minSdk 31 / targetSdk 37.2, embedded terminal and bundle)
.github/workflows/ CI(andcode-ci.yml)
```
