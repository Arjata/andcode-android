# andcode

[![CI](https://github.com/Arjata/andcode-android/actions/workflows/andcode-ci.yml/badge.svg)](https://github.com/Arjata/andcode-android/actions/workflows/andcode-ci.yml)

**Run OpenCode and a Linux arm64 development environment on Android.**

andcode packages [OpenCode](https://github.com/anomalyco/opencode), an embedded
terminal, and an Ubuntu 24.04 arm64 toolchain for Android devices. The APK
provides both the OpenCode Web interface and a terminal TUI, with a bundled
Ubuntu root filesystem for shell commands, package installation, and native
compilation. It requires no Termux App, proot-distro, or other host application.

The project also maintains a Linux arm64 compatibility baseline and two
alternative delivery forms: an adb-deployed bundle and Magisk integration.

> **Development status — 2026-11-14:** the single-APK installation flow,
> Web/TUI, and opt-in Ubuntu managed backend have passed scoped tests on device
> `8c8da214`. Other devices and locked delivery remain **pending P0/P3 device
> verification**. CI success and device test results do not establish formal
> redistribution approval; dependency licensing and source-delivery review
> remain open. See [current acceptance status](docs/DESIGN.md#6-historical-plan-and-current-acceptance-status).

## What you can do

- Use OpenCode through its Web UI or run `opencode` in the embedded terminal.
- Work in Ubuntu 24.04 arm64 with Bash, Git, Python 3, GCC/G++, Make, and apt.
  The rootfs is included in the APK and extracted when first needed.
- Optionally run the managed OpenCode service inside Ubuntu PRoot so model
  tools and Web terminals use the guest development environment.
- Import a project ZIP or folder through Android's file picker, select its
  directory for new terminal sessions, and export a project ZIP.
- Use terminal extra keys, adjustable font size, pinch resizing, and
  keep-screen-on settings.
- Configure an explicit proxy and an optional custom CA when your provider
  or network requires them. Both require explicit opt-in; TLS verification
  remains enabled.

The current APK uses pinned OpenCode **2.2.6** and a pre-staged PTY daemon.
The older OpenCode payload retained for bundle diagnostics is excluded from
the APK.

## Requirements and delivery forms

The Android baseline is **Android 12 or later (API 31), arm64-v8a**.
The current Gradle configuration sets `minSdk = 31` and
`compileSdk = targetSdk = 37`; the design documentation describes the platform
baseline as 37.2. ELF compatibility gates require at least 16 KiB segment
alignment; broader device acceptance is still pending.

| Form | Entry point | Root required | Current scope |
|---|---|---|---|
| **Tier P — APK** | Embedded terminal and Web UI | No | Primary user-facing form; single-APK and managed PRoot paths tested on the stated device |
| **Tier A — adb bundle** | adb shell; bundle under `/data/local/tmp/andcode` | No; debugging access required | Developer deployment path; locked-device acceptance pending |
| **Tier M — Magisk** | Root/module integration under `/data/adb/andcode` | Yes | Module implementation and manual root model/tool tests; full boot/lifecycle acceptance pending |

Root is not part of Tier P's runtime design. Testing on a root-capable device
does not establish acceptance on bootloader-locked devices. Detailed boundaries
are recorded in [DESIGN](docs/DESIGN.md).

## Try the Android app

Use a reviewed APK from a trusted
[CI run](https://github.com/Arjata/andcode-android/actions/workflows/andcode-ci.yml).
GitHub Releases are the intended sideload distribution channel; Play and
F-Droid delivery are not currently enabled. CI artifacts remain development
outputs, including artifacts whose names contain `release`.

1. Install the APK on an arm64 Android 12+ device. Keep several gigabytes free:
   the validated build was about 640 MB to download and used roughly 2.2 GB
   after installation and rootfs extraction. Sizes vary by build.
2. Open the app, choose the Ubuntu terminal environment in Settings if needed,
   and open **Terminal**. Wait for the first rootfs extraction to finish and
   the shell prompt to appear. The Ubuntu archive is embedded; a separate
   rootfs download is not required.
3. Start the managed OpenCode service from the dashboard and open the Web UI,
   or open the terminal and enter `opencode` to connect to the running service.
4. Configure your own provider and model using
   [OpenCode's configuration guide](https://opencode.ai/v2/docs/config).
   Global configuration belongs in `~/.config/opencode/opencode.json(c)`.
   Provider access, credentials, and network connectivity are supplied by you.
5. Use **Projects · Import / Export** to copy a project into the app workspace.
   Select it before creating a new terminal; copy its path to open it in Web.

When the canonical rootfs is ready, new terminals default to Ubuntu; lightweight
Bash remains the fallback. Terminal environment selection affects new sessions.
When the managed service is running, the `opencode` terminal command connects
to it. Starting the service first is the validated TUI workflow.

**Ubuntu terminal selection and the managed service backend are separate
settings.** To run model tools and Web PTY inside Ubuntu, enable **Run the
OpenCode service in Ubuntu PRoot (experimental)**, then manually stop and
restart the service. This option defaults to **off**. If the rootfs is missing,
service startup extracts the embedded archive before launching the backend;
opening a terminal first is optional. Other missing runtime prerequisites
cause an explicit failure. The guest shares the app home as `/root`, and
selected terminal projects appear under `/workspace/<project-name>`.

PRoot runs under the app UID and is not a security sandbox. Guest access to
shared storage at `/mnt/sdcard` follows Android's storage permissions.

### Network and certificate settings

Proxy use and custom CA trust are independent opt-ins. Enter the proxy URL
required by your network and enable the relevant setting; the app does not
provide the proxy service. For a private CA, import a single PEM certificate,
verify its SHA-256 through an independent trusted channel, and explicitly
enable it. Manually stop and restart the managed service to apply changes.

Additional CA trust applies to newly launched managed backends and inheriting
children. It preserves built-in roots and does not alter Android's global
trust store or WebView trust. Detailed acceptance conditions are in
[DESIGN §4.4](docs/DESIGN.md#44-tier-p--custom-minimal-apk-user-facing-form-for-locked-devices).

### Project data and sessions

Imports are private copies, not synchronized links to the original folder.
Import/export operations are limited to **512 MiB, 20,000 entries, and 64
directory levels**. Existing same-named projects are not overwritten, and
export does not follow symbolic links. `.git` export defaults to off; other
hidden files, including `.env`, can still be included.

Export important projects before uninstalling: Android removes the app's
private data. Terminal sessions survive navigation within the same app
process; recovery after force-stop or system process termination is not
established.

## Build and validate

[`.github/workflows/andcode-ci.yml`](.github/workflows/andcode-ci.yml) is the
reference build and validation pipeline. Native Linux work runs on
`ubuntu-24.04-arm`; the Android packaging job consumes its artifacts.

The pipeline assembles and audits the glibc bundle, prepares an Android-specific
copy, maps executable payloads into `jniLibs`, builds the canonical Ubuntu
rootfs, and passes the complete native/assets directory to Gradle. It runs
component regressions, APK Lint, and byte checks on packaged payloads.

| CI artifact | Contents and purpose |
|---|---|
| `andcode-dist` | Standard and Android-specific bundle archives, checksums, and third-party notices |
| `andcode-tier-p-native` | `arm64-v8a/` payloads and `assets/`, including the Ubuntu archive; input to APK builds |
| `andcode-apk-intermediate` | Debug APK and Lint reports; development/testing output |
| `andcode-apk-release` | Release-signed APK, generated only when all four signing secrets are available |

To rebuild the APK using the extracted `andcode-tier-p-native` artifact,
use JDK 17, Gradle 8.14, and the Android SDK/NDK versions listed in the workflow:

```sh
gradle -p app -PandcodeNativeDir="<absolute-artifact-directory>" assembleDebug lintDebug --no-daemon
```

Without `andcodeNativeDir`, Gradle produces a payload-free development build.
Release signing uses the four `ANDCODE_RELEASE_*` secrets registered in
[NAMING](docs/NAMING.md#3-namespace-registry-authoritative-allocation).
Use a stable signing identity for updates: different debug keys cannot
overwrite one another, and uninstalling to change signatures deletes app data.
A signed APK still requires the documented device and distribution reviews.

For delivery-pipeline changes, validate in this order on Linux CI:

1. Run `bash -n` on modified shell scripts.
2. Run `scripts/naming-lint.sh --bundle-dir <unpacked-directory>`.
3. Run `baseline/check-compat.sh --page-align <bin-or-lib-directory>`.
4. Pass the main CI workflow and perform the relevant real-device gates.

Linux CI is the trusted environment for shell and compatibility validation.
Device tests must run in the real application domain: `run-as` does not
reproduce zygote seccomp restrictions.

## Linux compatibility and runtime design

The compatibility baseline is **Ubuntu 24.04 arm64 / glibc 2.39**. Linux
payloads use a bundled glibc loader and dependency closure, with no glibc
symbol requirements newer than 2.39. Standard Linux arm64 targets need a
compatible glibc installation, normally 2.39 or later. Android-native platform
components use the NDK/Bionic separately.

For Tier P, executable payloads are packaged as `libandcode-*.so` and installed
by Android into `nativeLibraryDir`. App-private data holds configuration,
projects, runtime links, and the guest rootfs. Ubuntu ELF execution through
PRoot is a scoped, device-tested path; it does not grant general execution
permission to app-writable directories. The custom preload shim handles
selected external glibc calls involving `/etc`; glibc-internal access requires
the guest/bind path.

[DESIGN](docs/DESIGN.md) explains the architecture and platform constraints.
[UBUNTU](docs/UBUNTU.md) covers the PRoot backend, separate root chroot
prototype, image construction, and acceptance procedures. The optional
`mmdebstrap` rootfs and native-source build workflows remain isolated
experiments.

## Verified scope and open work

- On device `8c8da214`, the APK passed fresh-install rootfs extraction,
  Web/API access, TUI interaction, guest shell commands, Web PTY, and manual
  stop/restart. A full model/tool round trip and native C compilation chain
  passed through the managed Ubuntu backend with `arjata/glm-5.2`.
- The tested gateway's `arjata/gpt-oss-120b` route returns HTTP 400/503 after
  tool results, despite working plain-text replies. Cross-model isolation
  identified a provider-side tool-path defect; use a model with a working
  tool path until that route is fixed.
- Networking results depend on the tested VPN/proxy/CA configuration. Passing
  explicit-proxy tests does not prove default DNS or VPN-independent access.
- Pinyin IME composition can intercept injected text and cover terminal extra
  keys. The recorded TUI input probes used AOSP Latin IME; other input methods
  need further verification.
- Other devices, locked delivery, abnormal-stop recovery, and remaining root
  chroot integration are **pending P0/P3 device verification**.
- Source-built OpenTUI, watcher, fff, and bun-pty experiments have Linux CI
  evidence but are not integrated into the production APK. Native dependency
  notices, corresponding source, relinking materials, Bun/JSC obligations,
  and Android admission remain subject to review. See [REUSE](docs/REUSE.md).

## Repository and documentation

| Path | Purpose |
|---|---|
| [`app/`](app/) | Android app, embedded terminal modules, assets, and app-data tests |
| [`baseline/`](baseline/) | Linux arm64 build baseline and ELF compatibility audit |
| [`bundle/`](bundle/) | Bundle/APK packers, launchers, overlay scripts, and preload shim |
| [`runtime/ubuntu/`](runtime/ubuntu/) | Root chroot installation and management prototypes |
| [`magisk-module/`](magisk-module/) | Tier M module integration |
| [`scripts/`](scripts/) | Deployment, rootfs construction, audits, regressions, and device gates |
| [`.github/workflows/`](.github/workflows/) | Main CI and isolated build experiments |

Read [AGENTS.md](AGENTS.md) before contributing. The documentation entry points
are [architecture and acceptance](docs/DESIGN.md),
[Ubuntu development](docs/UBUNTU.md), [command and filename naming](docs/NAMING.md),
[third-party reuse and licensing](docs/REUSE.md), and
[repository binary/LFS rules](docs/LFS.md). Build artifacts and signing keys
must stay out of Git; CI generates payload manifests and notices.

## License

Project-authored material is licensed under **AGPL-3.0-only**; see
[LICENSE](LICENSE). Third-party components retain their original licenses,
including the embedded terminal modules described in
[app/NOTICE-TERMINAL.md](app/NOTICE-TERMINAL.md).
The project license does not replace component-specific source, notice, or
relinking obligations. [REUSE](docs/REUSE.md) tracks the outstanding review.
