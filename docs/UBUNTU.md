# Ubuntu Development Environment: Prototype Status and Acceptance

See [DESIGN §4.8](DESIGN.md#48-dual-ubuntu-development-backends-implemented-acceptance-scope-stated-below).

## Current Status

### Rootfs tool experiment

The optional `mmdebstrap` job in `ubuntu-development.yml` evaluates a mature
bootstrap tool rather than reimplementing distribution package installation.
Select `evaluate_mmdebstrap` when manually dispatching the workflow. The normal
Docker image job is unchanged. The experiment installs the tool only on CI,
uses the Ubuntu archive keyring and signed noble/updates/security indexes, and
retains tool/package/source versions, index bytes, configuration and logs.

`andcode-ubuntu-rootfs.tar.gz` and `andcode-ubuntu-arm64.img.gz` derive from the
same configured tree. The former is a future PRoot packaging input, **not** an
APK installer payload: Android link/metadata adaptation, trusted installation
and application-domain acceptance remain pending. The image must pass the
existing private-mount-namespace apt/non-root smoke and glibc/16K audit before
upload. Failures retain diagnostics, not installable release output. No device
instance is touched. Earlier signed live repository runs did not pin package
versions. The next candidate uses official HTTPS snapshot `20261110T000000Z`
for all guest suites via explicit signed-by sources, records snapshot/mirror
identity and retains apt authentication/expiry checks. It never falls back to
live repositories when the snapshot is unavailable. Build-host tool versions
remain recorded, not snapshot-pinned; byte reproducibility and corresponding-
source delivery are not established. Source-index availability and complete
source-package collection are separate from freezing binary package selection.

CI `42674527942` (commit `5017bbe`, mmdebstrap job `129352236231`) passed the
native arm64 bootstrap, archive validation, apt/non-root/PTY namespace smoke and
glibc/16K audit. Artifact `13699288258`: 373386339-byte ZIP, SHA-256
`552cb2eef2d8baf76df88199f7ac566e27aae06f2d04ad3513807706b1709634`.
Independent host review matched API and payload digests, all nine retained
index files (three InRelease suites), 180 package records, 15165 tar entries
(465454141 expanded file bytes), guest identity/source configuration, and ext4
header/label/4294967296-byte size. The host checked PGP framing, **not** signatures;
signature/expiry enforcement belongs to CI apt. Host review does not establish
image-tree equivalence or execute the image. Docker remains the default; no
device instance changed and no Android or distribution approval is granted.

Further host review matched the SHA-256/size of all six retained `Packages`
indexes against their InRelease records, then matched all 180 installed binary
versions and source-package/version pairs to index stanzas. Review JSON SHA-256:
`69465f98c3abe862c662e4aa8b0c4b0d466dc241f8335dc9b0dad99cec9a3f10`.
This does not independently verify PGP signatures, download the referenced
binary/source packages or establish corresponding-source closure.

The isolated candidate additionally emits `andcode-ubuntu-proot.tar.gz` through the
existing `prepare-proot-gate.py` transformer. Only the trusted CI build passes
the canonical archive's computed digest explicitly; the legacy two-argument
invocation still requires the fixed official Ubuntu Base digest. Conversion
normalizes root-relative symlinks, materializes regular hardlinks, strips
setuid/setgid and validates bounded output without changing file contents or
ELF bytes. This is build-time packaging, not a user-supplied archive installer.
Application-domain extraction, execution, update/recovery and device acceptance
remain pending; no current instance is replaced.

Host conversion of the independently verified `42674527942` canonical archive
passed the archive validator (15165 entries, 469579808 materialized file bytes).
A separate read-only archive comparison verified every regular file digest,
all five materialized hardlinks and each rewritten/unchanged symlink. Converted
archive SHA-256: `1c98cd485db4ea94a5959fbc0925cbf05973309664de07128e757bf4bc5478cd`.
This is host transformation evidence only; gzip metadata is not reproducibly
fixed, and the converted archive has not been executed on Android.

CI `42680411398` (commit `e197165`, mmdebstrap job `129373108570`) passed the
canonical-to-PRoot conversion and the existing Linux gates. Artifact `13703550062`
is a 532612659-byte ZIP, SHA-256
`b601712c3c48e63a8fd52110dd0346feb47d9ec762b3ae13de828333c9f04107`.
Independent review checked payload/API digests, all 15165 canonical/converted
paths, unchanged regular-file bytes, all five materialized hardlinks, symlink
rewrites and retained mode/ownership metadata (469579808 materialized bytes).
It also repeated the six-index / 180 binary-source-version review; its JSON
SHA-256 is `dbaa16b5716462328e3bc4cf281daaa384507c87bf613900b7e2be18a0ba5f52`.
The ext4 header/size check remains distinct from tree equivalence or execution.
No device installation or Android approval follows from these checks.

The next gate uses `compare-ubuntu-rootfs.py` to compare the original ext4
image (read-only mount) with the canonical archive. The smoke-test copy modified
by apt/compilers is never used for this comparison. All paths, types, modes,
UID/GID, regular-file digests and symbolic/hard links must match; only an empty
root-owned mode-0700 ext4 `lost+found` may be omitted from the archive. Results
are retained as `andcode-ubuntu-tree-review.json`. Timestamps, ACLs, xattrs and
sparse allocation are outside this gate. Synthetic POSIX tests and actual
image-tree acceptance must run in Linux CI; Windows does not validate them.

The tree gate passed native arm64 CI `42684788108` (commit `db1c693`, job
`129388559581`): 15166 entries including the root, 12456 regular-file/hardlink
entries, 1266 symlinks, five hardlinks and 469579808 materialized bytes. The job
log SHA-256 is `6f8cde3313c9d9344267e008a5002de0952e3bbd2fd5b2728f13f6aeab6ad91e`.
Thirteen non-root synthetic cases passed; the root-only nonempty recovery-
directory case was skipped. The next optional job runs these tests as root to
exercise that case too. Artifact bytes still require independent review.

Independent HTTPS source-index review of snapshot `20261110T000000Z` verified
all six main/universe source indexes against InRelease SHA-256/size records.
All 100 unique source-package/version pairs from the earlier 180-package live
run were present (this is not proof of a new snapshot bootstrap's selections).
Review JSON SHA-256:
`5d7a019b2b0dfdc14c024b56af9af60caf2e63bf665e64e31d23bf7bd736034a`.
Some identical source versions occur in different pool component directories;
the review retains each location and requires identical file hashes. Source
archives were not downloaded, PGP signatures were not independently verified,
and complete corresponding-source delivery remains unproven.

The next isolated recipe adds authenticated `deb-src` entries for the same three
snapshot suites and downloads each exact installed source-package/version using
guest apt (`--download-only --only-source`). It neither extracts source archives
nor executes source build rules. `andcode-ubuntu-source-inputs/` retains per-
source `.dsc`/archive files, actual apt commands/logs and a SHA-256 inventory
(`andcode-ubuntu-source-inputs.json`); these are copied out of a new temporary
guest directory before the immutable rootfs is exported. The collector rejects
malformed cleartext-signature framing rather than silently stripping it; this
is not an independent PGP signature verifier. A timed-out apt download retains
and reports its partial output, without emitting a successful source inventory.
The build recipe copies partial source evidence outside the disposable guest
before failing; the failure-only diagnostic artifact includes per-package apt
logs, not an approved source payload or rootfs. A failed source pipeline cannot
continue to image construction or successful candidate upload.
These additional guards passed 12 synthetic Python tests on Windows; Linux
recipe execution and real source downloads remain separate CI requirements.
The first source-acquisition experiment, CI `42688539116` (`ec0cd45`, job
`129401821961`), was cancelled at the former 45-minute job limit after logging
75/100 verified source downloads. It produced no successful source/rootfs
candidate. Its 14 root tree-comparison regression tests passed without skips.
Retained job log SHA-256:
`c69ad68aabf654b52ad79c02bc65fa92dd91f2fb530693e92f355b1f001aaab8`.
The optional job now has a bounded 80-minute build step within a 100-minute job,
leaving time for failure diagnostics; the snapshot, authentication and required
complete installed source-version set are unchanged. A successful rerun and
independent source-archive review are still required.
The subsequent optional run `42750180844` (`e82060a`, job `129611694402`)
succeeded, including all 100 exact source-version downloads, canonical-to-PRoot
conversion, original ext4 tree comparison and compatibility checks. Its Linux
regressions passed without skips: 14 archive-validator, 14 tree-comparison,
7 fail-closed recipe, 12 source-collector and 20 PRoot-converter tests.
Job log SHA-256:
`1897505b225face38bbb8cd735c72dfefc159fc14b11fdde241e13f0ccd1954b`.
Regular CI `42750151736` and Docker Ubuntu push CI `42750151274` also succeeded.
Artifact `13733088271` contains 1409398539 bytes; its API ZIP SHA-256 is
`f0d42ad0e7ed199d92f663c86429535e34dda71917142b45078557a14487659d`.
The complete download matches that API digest. Independent review matched all
180 installed binary/source-version tuples against six binary Packages indexes
and their InRelease hash records; review JSON SHA-256:
`197e6ae1ca87ba48981fbc74a8845be5a7d422bc67abcf7cad6036e90bca92a2`.
Separate source-input review bound all 100 exact source versions, 310 `.dsc` and
archive files (740746325 bytes), complete archive sets and retained per-package
commands/logs to six Sources indexes and their InRelease hash records. Source
review JSON SHA-256:
`03bdf935852a956e41f38f583a4e1de95ebc6cfcf54ddb5151842e32b158d6bf`.
The host review did not independently verify PGP signatures or execute source
build rules. Independent canonical/PRoot review also passed: 15167 entries,
5 materialized hardlinks and 567215830 materialized file bytes, with all payload
and 15 retained index-file hashes checked. The 4 GiB original ext4 header/size
and the CI tree report agree with these counts; the host did not independently
walk ext4. The CI tree has one additional allowed empty `lost+found` directory.
Canonical/PRoot review JSON SHA-256:
`fc552d5a19f4814dd9b3d812498572344d6a307d9615571b778bc45b08fb5613`.
An additional, separate host review subsequently verified all three retained
InRelease signatures using Git for Windows `gpgv` 2.4.9, an explicit isolated
home and the keyring downloaded with default TLS verification from
`https://archive.ubuntu.com/ubuntu/project/ubuntu-archive-keyring.gpg`.
Keyring SHA-256:
`80a36b0a6de2f69f49d2df75ef473ccde121e9e190b9ea01d20a4f63778d5c31`.
All three signatures returned `VALIDSIG` for the pinned Ubuntu Archive 2018
fingerprint `F6ECB3762474EDA9D21B7022871920D1991BC93C`, without a bad, revoked or
expired-signature status. Altering the signed `Suite` field was rejected with
`BADSIG`. Separate signature review JSON SHA-256:
`781c6e28d25470c9ffb43607a29e6c75994f141be5bc420432e48e51e97be608`.
These InRelease files do not declare `Valid-Until`; this review does not claim
validation of that absent field, `.dsc` developer signatures or complete source
licensing. Earlier digest-only reports retain their original limited scope.
These results are
not complete corresponding-source, redistribution approval or device installation
acceptance. Existing device instances are unchanged.
Missing exact versions,
apt failures, existing output or unexpected download paths fail the candidate.
This new acquisition path awaits Linux CI and independent archive verification.
It does not automatically close source completeness, patches/build-inputs,
notices or redistribution obligations. Docker and all device instances remain
unchanged. Larger source artifacts are evidence, not APK contents.

The first fixed-snapshot run `42685341275` (commit `dc87389`, job `129390525686`)
passed Linux smoke, conversion and original-image tree gates. Artifact
`13704952467` is 532612248 bytes, ZIP SHA-256
`e66ff0c7aaa92ce41e4096a611cd0d96e62f556d9a99184e93da8a2e57273759`.
Independent ZIP/rootfs/PRoot review passed; it confirmed the recorded snapshot
configuration and tree report, not an independent execution of ext4. All six
retained binary indexes matched InRelease hash records and all 180 installed
binary/source-version tuples matched those indexes (review JSON SHA-256
`415ba7654ce2a23e03d001091fea205ff3578181ae100fc0828118f7fd8b5e49`).
Materialized PRoot bytes are 469579853; path/link counts are unchanged. This
artifact predates source acquisition and cannot be credited with that new gate.

This document covers both a root chroot prototype and the managed PRoot development path.
The root chroot remains a prototype rather than a fully delivered self-contained Ubuntu form;
the managed PRoot serve path has passed its scoped acceptance checks in the real application domain on the older device.
It does not depend on the Termux App, lower targetSdk, or disable SELinux.

- The first native arm64 CI run [42508958877](https://github.com/Arjata/andcode-android/actions/runs/42508958877)
  passed image construction, private mount namespace tests and the glibc/16K audit. The artifact was installed by digest
  into the separate `/data/adb/andcode-ubuntu-ci`; rejection of duplicate installation was tested. The trusted image passed
  root proxy HTTPS/strict apt/hello, and ordinary-user compilation, privilege clearing, PTY and lifecycle checks.
  The final ordinary-user connection to the loopback proxy timed out; the complete smoke exited 1 and the network blocker remained unresolved.
- This round passed: 14 synthetic build-archive validator tests; entry-point syntax under device system sh and build-script
  syntax under the staged Bash; Toybox recursive-private setup in a private mount namespace. The insufficient-space gate
  was tested and rejected installation without creating an instance. A device development instance was created after cleanup (not a CI artifact installation).
- The chroot root maintenance entry passed proxy HTTPS certificate verification, apt update/install hello and the
  glibc 2.39-0ubuntu8.7 → 8.9 update. UID/GID 60000 passed gcc compilation/execution, 16K
  LOAD, zeroed capabilities, prctl no-new-privs queries, PTY/child processes and foreground cleanup.
  **The ordinary-user proxy connection timed out, default DNS did not pass, and the complete smoke script still failed.**
  A controlled diagnostic changed only the UID under the same privilege-drop/capability-clearing conditions: 60000 timed out, while the actual APK UID
  10348 could connect. Neither the official development identity nor the device firewall was changed. Read-only BPF diagnostics further confirmed
  that restricted networking mode was enabled: global rule `0x220` included `RESTRICTED_MATCH`, the APK UID's
  `0xa5` included the corresponding allow bit, and UID 60000 had no record. The authenticated service needs to address network-identity adaptation.
- Under real `untrusted_app`, Seccomp=2, PRoot passed explicit-proxy apt update/install,
  HTTPS certificate verification, newly installed hello, execution of gcc output, PTY/child processes and execution after the glibc 8.7 → 8.9
  update, emitting `ANDCODE_PROOT_DEVELOPMENT_OK` and `development-exit=0`.
  Guest ELF files were unchanged; su/run-as was not used as a substitute. Subsequent HTTPS without an explicit proxy over TCP DNS,
  strict apt update and Git HTTPS passed; other devices and VPN-disabled scenarios remain unverified.
- After user cleanup, older device `8c8da214` had about 54 GiB free; the space blocker was resolved and SELinux remained Enforcing.
- The 4 GiB image requires staging the compressed file first and then retaining at least **5 GiB** free. Real development projects
  may need a larger image; the current prototype offers neither automatic expansion nor overwrite reinstallation.
- Neither chroot nor PRoot is a security sandbox; do not run untrusted projects or automated model operations inside the prototype.
- Corresponding-source/license fulfillment still requires review before formal distribution; CI artifacts do not indicate release approval.

### Device Development Bootstrap Path (Not a Substitute for CI)

When Docker is unavailable locally and the CI recipe has not yet been published, `scripts/bootstrap-ubuntu-device.sh`
can create a separate 4 GiB ext4 development instance from the digest-pinned official Ubuntu Base 24.04.4 arm64 archive.
The input at `/data/local/tmp/ubuntu-base-24.04.4-base-arm64.tar.gz` must be root:root 0600;
the reviewed `/data/local/tmp/andcode-ubuntu` and the existing bundle's standalone BusyBox are also required.
The recipe accepts only fixed paths/digests, refuses to overwrite instances, and retains failure remnants for inspection.
This is native-device development validation and must not be called CI artifact installation validation. The rootfs origin and package inventory are recorded
in the instance's `andcode-ubuntu-build.txt` and the guest's `/etc/andcode-ubuntu-packages.tsv`, respectively.

The older device's mke2fs does not recognize the `orphan_file` feature name; Toybox tar rejects Ubuntu's absolute links,
and Toybox mount incorrectly applies loop logic to a `/dev/null` bind. Bootstrap and sessions reuse the existing standalone BusyBox
payload, keeping a root-private copy inside the instance. No BusyBox source was copied into the repository.
chroot uses separate devpts `newinstance,ptmxmode=0666,mode=0620,gid=60000`, without changing
host `/dev/pts`; host `ptmxmode=000` prevents ordinary users from creating PTYs. The older kernel lacks
the NoNewPrivs field in proc status, so verification uses `prctl(PR_GET_NO_NEW_PRIVS)`; the check must not be skipped.
`scripts/ubuntu-device-test.sh` verifies HTTPS, apt installation, newly installed ELF files, ordinary-user capability
clearing, compilation/execution, host-path invisibility and no mount leaks on foreground exit; it does not test the PRoot application domain.

## Build and Installation (Trusted CI Artifacts Only, Manual Root Operations)

1. Trigger `.github/workflows/ubuntu-development.yml`. It generates the image, compressed-file digest,
   package-version/source-package inventory and base-image digest. It tests apt/compilation on another decompressed image,
   leaving the uploaded original unchanged. Only after that run passes may it be described as "validated by Linux CI."
2. Place `andcode-ubuntu-arm64.img.gz` from the trusted run on the device at
   `/data/local/tmp/andcode-ubuntu-arm64.img.gz`. Confirm its SHA-256 out of band from trusted CI output;
   do not treat a digest supplied by an arbitrary file in the same directory as proof of authenticity.
3. Place the reviewed repository files `runtime/ubuntu/andcode-ubuntu` and
   `runtime/ubuntu/andcode-ubuntu-install` at their same-named paths under `/data/local/tmp/`.
4. Run as root (replace the placeholder with the actual 64-character lowercase hexadecimal digest):

   ```sh
   su -c 'chown 0:0 /data/local/tmp/andcode-ubuntu-arm64.img.gz /data/local/tmp/andcode-ubuntu'
   su -c 'chmod 0600 /data/local/tmp/andcode-ubuntu-arm64.img.gz'
   su -c 'chmod 0700 /data/local/tmp/andcode-ubuntu'
    su -c 'sh /data/local/tmp/andcode-ubuntu-install <trusted-SHA256>'
   su -c 'sh /data/adb/andcode-ubuntu/andcode-ubuntu status'
   su -c 'sh /data/adb/andcode-ubuntu/andcode-ubuntu shell'
   ```

   Installation rejects existing instances; directories are `root:root 0700` and the image is `root:root 0600`. Failed installation retains
   private remnants rather than automatically deleting them and retrying. **Do not install a rootfs directly through the project ZIP import feature.**
   Staged files must be root-owned and not writable by other users; this prototype assumes no malicious root process on the device.
   The current installation prototype also requires `/data/local/tmp/andcode/bin/busybox`, copied into the root-private instance.
   This is a development-bundle dependency and must not be misrepresented as completed self-contained APK installation.

   If the device already has a development instance, explicitly select the **fixed separate acceptance instance**; do not move or overwrite the older instance:

   ```sh
    su -c 'sh /data/local/tmp/andcode-ubuntu-install ci-validation <trusted-SHA256>'
   su -c 'sh /data/adb/andcode-ubuntu-ci/andcode-ubuntu ci-validation status'
   su -c 'sh /data/local/tmp/andcode-ubuntu-device-test.sh ci-validation loopback-proxy'
   ```

   `ci-validation` must be passed to both the installer and that instance's manager; it selects only
   `/data/adb/andcode-ubuntu-ci`, not an arbitrary path. The test script comes from
   `scripts/ubuntu-device-test.sh`. The instances use separate images/locks/namespaces and do not share a writable system.

5. `shell`/`exec` run as an ordinary user (60000), starting in `/workspace`; explicit maintenance command examples:

   ```sh
   su -c 'sh /data/adb/andcode-ubuntu/andcode-ubuntu admin apt-get update'
   su -c 'sh /data/adb/andcode-ubuntu/andcode-ubuntu admin apt-get install -y hello'
   su -c 'sh /data/adb/andcode-ubuntu/andcode-ubuntu exec hello'
   ```

   `admin` has host root privileges; do not expose it to the model or put it in the APK terminal PATH. The image contains no sudo.
   It runs no systemd, starts no network-listening services, and inherits no host proxy or TLS-verification-disabling environment.
   Default DNS uses TCP at 1.1.1.1 / 8.8.8.8; managed networks may require manual changes. Android
   dynamic DNS synchronization is not yet available. `_apt` has primary group inet 3003 (the apt sandbox clears supplementary groups), and the development user
   joins supplementary group 3003; older Android network-permission behavior still requires device confirmation.

Device development bootstrap/tests allow explicit `loopback-proxy` mode, setting
`http_proxy`/`https_proxy=http://127.0.0.1:7890` for that invocation only. They do not automatically inherit the host environment or disable TLS.
The proxy is supplied by the device's existing network configuration. **Passing proxy tests does not mean default direct DNS passed**; it is not
a required dependency of the product's self-contained capability. PRoot default mode was tested separately: public UDP DNS timed out,
while TCP queries in the same application domain worked. With `options use-vc timeout:3 attempts:2`,
`getent`, certificate-verified HTTPS, strict apt update and Git HTTPS succeeded. Here "no proxy" means only
that HTTP/HTTPS/ALL_PROXY were unset; the existing FlClash VPN remained running, not that device networking was unnecessary.
The chroot ordinary-user UID network issue still failed and must not be conflated with PRoot results.

For manual root diagnostics, run `sh /data/local/tmp/andcode-ubuntu-network-diagnose.sh`
(deployed from `scripts/ubuntu-network-diagnose.sh`). It reads device settings and three Android 13
BPF maps without modifying them and validates map layouts; on older 4.9 kernels without the object-information syscall, it reads fdinfo.
`ANDROID13_RESTRICTED_RULE_BLOCKS_UID=60000` means that rule is sufficient to block this UID,
not that every other networking issue has been ruled out. A missing INTERNET permission-map entry alone does not imply denial.
Diagnostics do not change settings/BPF/firewalls, borrow the APK UID, or restore guest privileges. Do not disable restricted networking mode
to make tests pass. Under the existing mode chroot networking remains recorded as failed; PRoot results are not substituted for it.

### PRoot Application-Domain Development Acceptance

`scripts/prepare-proot-gate.py <official-Base-archive> <new-output-archive>` first checks the fixed official SHA-256,
converts absolute symlinks to equivalent guest-relative links, materializes hardlinks as files with identical contents, and removes privilege bits,
without changing any ELF. This is necessary because BusyBox extraction in the older device's application domain triggers SIGSYS, while Toybox returns
Permission denied for some hardlinks. The input remains trusted official Base; this is not an untrusted-archive installer.
Place the output at `/data/local/tmp/ubuntu-base-app-gate.tar.gz` (app-readable), then manually run
`sh /data/local/tmp/proot-rootfs-gate.sh <generated-output-SHA256>` **from the APK terminal**.
The script refuses to overwrite `files/proot-rootfs` and retains failure state; the development copy shares no writable layer with chroot.

`scripts/proot-development-gate.sh [loopback-proxy]` checks apt, hello,
compilation and PTY in that separate instance, using the existing PRoot `-l` (hardlink→symlink) and `--kill-on-exit`.
Logs are in APK `files/proot-development-gate.txt`. PRoot fake root is neither host root
nor a security sandbox. It still depends on `/data/local/tmp` development payloads and **does not prove locked self-contained delivery**.
The noninteractive gate reads stdin from `/dev/null` to avoid terminal SIGTTIN from timeout's new process group.
The initial attempt stopped by job control after libc triggers was terminated; after rerunning
`dpkg --configure -a` in the same instance, the full gate succeeded. The interrupted attempt is not counted as passing.

The standalone APK terminal can run `andcode-ubuntu-proot [loopback-proxy] [command...]`; without a command it enters
interactive Bash, and `exit` returns to the original lightweight Bash. Missing instances/payloads fail explicitly, without automatic installation/elevation.
Generated `files/term-ubuntu-proot` is read by system sh, not executed as a data-directory ELF.
The development entry was verified in the real application domain for hello, PTY, stdin and exit-code 42 propagation;
it does not change OpenCode tools or the Web PTY backend. Archive preprocessing has another 14 synthetic tests integrated into CI.
Interactive terminal testing confirmed `stty size` returned 44×54, Ctrl+C interrupted foreground sleep and returned to the Ubuntu
prompt, and `exit` returned to the original project's lightweight Bash. A foreground guest Python signal test in the real application domain verified
two SIGWINCH events as the soft keyboard hid/showed, with sizes 28×54 → 47×54 → 28×54 and output
`ANDCODE_PROOT_RESIZE_OK`. This covers only this round on the older device; more devices remain pending P0/P3 on-device verification.
In this earlier device round, the settings page's "Terminal environment" affected only new sessions, defaulted to lightweight Bash, and offered an installed Ubuntu PRoot;
the proxy has a separate explicit default-off switch. On the older device, UI selection and persistence of the Ubuntu backend passed; after exiting the old
shell, a new terminal immediately showed the Ubuntu prompt. Existing sessions do not switch. chroot is not offered,
because its authenticated root service is unfinished. APK `assembleDebug` and `lintDebug` passed; Lint warnings were not hidden.
The extended gate also passed C++ compilation, GNU Make and Git HTTPS `ls-remote` in explicit-proxy mode.
The same full gate was rerun using TCP DNS without an explicit proxy, passing apt, C/C++, Make, Git HTTPS,
PTY/child processes and existing-libc execution, with `development-exit=0 network-mode=direct`.
All apt packages in this run were already at the latest installed versions; the rerun is not described as another installation or libc upgrade.
CI added seven-site seccomp verification, idempotent digest checks and subsequent Tier P physicalization for the Android-specific
bundle, leaving the standard Linux bundle unchanged. The first run executed this chain; the subsequent manifest-classification fix and
Tier P native intermediate artifact still require a rerun. This does not establish completed jniLibs self-containment.

On 2026-11-09, native arm64 run `42511151241` build-bundle passed physicalization, compatibility auditing of 349 ELF files
and renamed Bash execution (after retaining libc.so.6 SONAME). The APK job failed because the Action
requested the removed Android SDK `tools` package; it was changed to explicitly install platform-tools, pending a rerun.
Local assembleDebug/lintDebug with the real native artifact and byte-for-byte APK verification passed. First startup only writes
data and creates nativeLibraryDir links; 21 regressions and a real manifest round trip passed.
APK Bash ran in the older device's real application domain without root relabeling. The first git test failed because the launcher
still searched the old PRoot library directory; the fix awaited verification. This does not mean V2/Web PTY or the complete locked package passed.

Native arm64 run `42515404336` fully succeeded: after fixing the stale DT_VERDEF
address in Bun ET_EXEC and the clone3 patch's newer-kernel fallback, actual Bash/V2.2.6/PTY 0.4.0 execution passed,
as did downstream SDK, APK compilation/Lint, real manifest initialization and byte-for-byte APK payload verification.
`scripts/native-payload-device-test.sh` runs only from the APK lightweight terminal. Native-directory paths,
real application domain/seccomp and Bash/V2/PTY/Git/PRoot child processes are separate device gates, awaiting installation of the new version.
The full PRoot development gate can also explicitly use the current APK's farm/native libraries rather than mixing in older development libraries.
These results still do not establish formal signing, a pre-staged Bun native-extension closure, or complete locked-package delivery.

Subsequent native run `42516603502` (`4869307`) fully succeeded; the successful artifact ZIP was checked against API
SHA-256 `84287a218c6c885b1e4696bb6976a4db575ee1276bb5811d7b27252aafbe5e2e`，
Local APK recompilation/Lint and byte-for-byte native/assets verification passed again, followed by overwrite installation retaining the original signature.
On the older device under real `untrusted_app`/UID10348/Seccomp=2, Bash 5.2.21, V2.2.6,
PTY 0.4.0/protocol7, Git 2.43.0 and native PRoot child processes all passed,
with `ANDCODE_NATIVE_PAYLOAD_OK`; adb independently confirmed SELinux Enforcing (the application domain cannot read its status).
The APK native PRoot full development gate likewise emitted in the real application domain
`ANDCODE_PROOT_DEVELOPMENT_OK`、`development-exit=0 network-mode=direct`：
apt, C/C++, Make, Git HTTPS and PTY all succeeded; only the explicit proxy was unset, while the device VPN remained active.

`opencode-native-prototype.yml` is a manually triggered fixed-source build experiment: during Bun compilation,
native .so file imports are rewritten to content-addressed pre-staged paths under the absolute `ANDCODE_EXE_DIR` directory;
.node imports use explicit `process.dlopen` in that directory, retaining CommonJS addon export semantics.
Current synthetic plugin tests establish only rewriting/exports/byte fidelity and wrong-architecture rejection. CI serve temporary-directory
scans cover only startup, not tools, Web PTY, TUI or all transitive native-library audits.
The experiment does not feed the APK or alter verified official payloads; license notices/source obligations and compatibility await review.

The first source experiment run `42518155724` succeeded and its artifact API digest matched, but subsequent stricter static
auditing found an extensionless PTY ELF still embedded in the Bun graph and unused musl
PTY libraries in the import table, preventing integration. The updated experimental plugin explicitly requires `OPENCODE_PTY_BIN`, does not embed the daemon,
excludes digest-pinned musl inputs and fails on accidental selection; `.so` require returns a path string rather than
an ESM namespace. New gates await a new successful CI run; license/Android closure remains unverified.

The current official native payload's Web home page renders in APK WebView and reports the default model as
`arjata/gpt-oss-120b`. Bash/printf/Git execution through the shell API works, but Android
system `id` fails due to leaked glibc shim preload, and ordinary Web PTY creation returns 500
(bun-pty library not loaded, followed by failed symbols access). These are unresolved boundaries, not acceptance of a complete Web
or tool closure; targetSdk/SELinux were not lowered and no TLS bypass was introduced.

Source experiment run `42519500865` (`c2277e8`) fully succeeded: no embedded ELF in the Bun graph,
digest/dependency/16K/version auditing of four glibc extensions, shell, ordinary PTY tty/resize/child processes,
persistent PTY snapshot echo and no ELF in separate BUN_TMPDIR all passed. This is Linux CI evidence only,
not approval of Android native-extension loading, transitive-dependency licensing or formal delivery.

Application-domain diagnostics confirmed LD_PRELOAD remained in the Bash wrapper's child environment; temporarily clearing it only for
`/system/bin/id` succeeded (same UID/domain, no network-policy changes).
The wrapper now uses direct loader `--preload` for single-process injection without exporting LD_PRELOAD.
New Linux gates exercise real glibc Bash/child sh, and the native device gate asserts Bionic id;
the fix awaits new CI/APK device tests. Default model configuration is correct, but the actual request retried after EAI_AGAIN
prevented provider-domain resolution and was aborted; this cannot count as model end-to-end success.

Updated official payload run `42519762828` (`2716a49`) passed all CI; native artifact ZIP/API
SHA-256 `60dbbaed741181f37c1c8194643fc79bcaf7227709689504de7899862a32ecaf`。
Local assembleDebug/lintDebug, byte-for-byte comparison of 403 native and 253 data APK entries and
overwrite installation with the original signature passed. ZIP names were interpreted from original UTF-8 bytes (Android build tools did not set the UTF-8
flag; Python's default CP437 display is not the actual filename). In the real application domain, the new
`ANDCODE_NATIVE_BIONIC_CHILD_OK` and existing native/PRoot child-process gates all passed;
adb independently confirmed SELinux Enforcing.

Official V2 persistent PTY using the pre-staged daemon passed system-sh tty, WebSocket input,
91×31 resize, reconnect replay and snapshot checks with `ANDCODE_NATIVE_PERSISTENT_WS_OK`. The default Bash
wrapper exits immediately without output when directly exec'd by the daemon; explicitly executing the wrapper through system sh
succeeds. To address this boundary, Tier P `bin/bash` retains its physical name but becomes a static ELF entry
calling loader/Bash/shim in the same nativeLibraryDir; this historical boundary awaited CI and APK device tests at the time.
This does not mean Web UI operation/default Bash or the Ubuntu Web backend passed.

Integrity checks of pinned npm tarballs corrected the OpenTUI native-package license to MIT AND LGPL-2.1-or-later,
with FFmpeg/Ghostty/LCMS2/WebP/STB/Wuffs/Zlib notices; the fff platform package includes no LICENSE.
See REUSE §2.1; source experiments still must not directly feed the official APK. Isolated device root diagnostics can run
source-built serve/ordinary PTY, but are not application-domain or self-containment evidence; test processes were stopped.
The default provider domain failed resolution in both device system ping and host DNS. PRoot mapping and TCP DNS
comparisons did not restore model requests; our retries were interrupted and our diagnostic processes cleaned up, without changing network policy or credentials.

Experimental CI adds real TUI acceptance: launch `--standalone` in a separate controlling PTY,
requiring both actual pre-staged OpenTUI mappings in `/proc/<pid>/maps` and terminal rendering, then terminate only that
test process group. Runtime ELF scanning expands to isolated HOME and BUN_TMPDIR. This new gate awaits CI;
neither TUI nor complete runtime-loading closure is claimed to have passed in advance.

Source experiment run `42522076401` (`c24813c`) has now passed that TUI gate, logging
`ANDCODE_SOURCE_TUI_NATIVE_OK`; shell/ordinary and persistent PTY and isolated HOME/BUN_TMPDIR
no-ELF scans also passed. The previous run `42521939719` license-evidence artifact was checked against API SHA-256
`60a9b72e71e2ebcc6dd66dce280fc698532e545b007d2d80502ca7831444c7c8`；
All four pinned-package reviews remain blocked as expected; this is not evidence of release-compliance acceptance.

Separate application-domain serve diagnostics with explicit `loopback-proxy` bypass the provider DNS blocker, but
requests fail during TLS with `UNABLE_TO_GET_ISSUER_CERT_LOCALLY`. We did not set
NODE_TLS_REJECT_UNAUTHORIZED=0, add unknown CAs, or change user configuration/default proxy;
our retries were interrupted and the isolated service stopped. Resuming end-to-end acceptance requires a verifiable provider certificate chain or
working direct-network resolution; proxy connectivity must not be misrepresented as model availability.

Static Bash entry run `42521752952` passed all CI/local APK build/lint and overwrite installation
with the original signature. The real application-domain native gate still passed; persistent PTY Bash `-c` and system id succeeded.
Default interactive Bash still exited. Tracing attached only to our own application-domain child processes confirmed seccomp
forbids `setfsuid/setfsgid` while libtinfo reads terminfo; neither filters nor identity were changed.
The v0.4.34 ncurses shim experiment was rejected by run `42523439252`'s real initialization gate:
libtinfo internal binding bypassed interposition. That implementation and its tests were removed without device deployment.
The replacement uses pinned Ubuntu ncurses 6.4+20240113-1ubuntu2.2 source plus security patches, disabling
HAVE_SETFSUID in Android-specific libtinfo while retaining upstream safe-open branches and kernel permission checks,
with a new real Bash/terminfo no-identity-call gate. The standard Linux bundle is unchanged.
The 14 diagnostic persistent PTYs created in this round were deleted through the API, without affecting user sessions or terminal preferences.

Fix acceptance: run `42524341097` (`a411328`) fully succeeded, including real terminfo, exact
staged libtinfo mappings, real interactive Bash and fs-ID function traps. Trusted native artifact
`13635111177` ZIP SHA-256
`045451ed8f7d16926b2f82079536107ef198619ea9ab3b0567de855a861a39ea`。
Local APK assembleDebug/lintDebug passed; 403 native / 255 data entries matched the artifact
byte for byte, and overwrite installation with the original signature succeeded. APK SHA-256
`4bc04edc0a0e991e92c1ecb09f91a66facc8eeb7d190e8cd642e9b6a0d80d493`。
On the older device under real `untrusted_app` / `Seccomp=2`, SELinux Enforcing, the default no-args persistent
PTY remained running after launching pre-staged Bash; stdin/out/err were all `/dev/pts/1`, and maps confirmed
libandcode-libtinfo.so from nativeLibraryDir. WebSocket input, 91×31 resize,
reconnect replay and snapshot passed with `ANDCODE_NATIVE_PERSISTENT_WS_OK`.
The full native gate added mandatory interactive initialization, yielding `ANDCODE_NATIVE_INTERACTIVE_BASH_OK`;
other Bionic/PRoot child-process and version gates passed. A screenshot confirmed the standalone terminal's initial Bash prompt.
Full PRoot apt/HTTPS/C/C++/Make/Git HTTPS/PTY and libc 8.9 regression without an explicit proxy passed,
with `development-exit=0 network-mode=direct`. The new dedicated acceptance PTY was deleted, not user sessions.
This does not establish a fix for official ordinary Web PTY or source-built native-extension loading; the former still needs a separate fix,
while the latter remains in license/source/closure acceptance review.

Subsequent network review (same day): host DNS currently resolves to `198.18.0.66`; Python HTTPS with
default system verification succeeded. Certificate subject is `one.ai.api.service.arjata`, issued by
`Arjata Fundamental Public Endpoint Issuer` under the private `Arjata Authority`.
This proves only that the host's current trust chain works, not Android/Bun trust. The real APK default model still reports
`getaddrinfo EAI_AGAIN`, and the isolated explicit loopback proxy still reports `UNABLE_TO_GET_ISSUER_CERT_LOCALLY`.
Our two requests were interrupted and the dedicated 4296 service stopped through its shell API; the default 4096 service's
proxy/CA/verification were unchanged. Further work requires an out-of-band verified CA certificate and explicit trust configuration, or a provider-supplied
complete chain trusted by the APK by default. Unknown CAs must not be automatically imported from the network/host, nor TLS verification disabled.

New terminal creation snapshots the selected single private project name; the launcher accepts only `files/projects/<project-name>`,
binds it at `/workspace/<project-name>` and starts there. With no selected project it starts at `/root`.
It does not bind the entire project collection, `/data`, or arbitrary caller-supplied host paths. Symlinked parents/project roots,
out-of-bounds names, colon separators and missing projects are rejected; valid aliases of Android data directories are not falsely rejected.
Links inside projects are not recursively filtered. PRoot is not a sandbox and cannot prevent same-UID host access.
`scripts/proot-terminal-test.sh` runs from the lightweight terminal and has verified separate temporary-project writeback, argument fidelity,
stdin/exit-code 42, empty-project fallback to `/root`, invalid-path/link rejection and cleanup of its own fixtures.
Logs are in `files/proot-terminal-test.txt`. Inability to read global SELinux status from the application domain is reported explicitly;
Enforcing must also be verified through adb. Permission denied is not treated as a successful status check.

## Session and Recovery Limitations

- Each invocation has a separate mount namespace; only one session is allowed per image.
- Foreground exit unmounts in reverse order; if a background process still holds resources, exit code is 75 and `session-lock` is retained.
- The lock is retained if the outer process receives HUP/INT/TERM or a child namespace is terminated by a signal; namespace cleanup is not assumed.
- A bounded background `sleep` of our own was tested: unmount reported busy, returned 75 and retained the lock. After that process exited,
  each process root/mountinfo was checked for references before releasing the loop confirmed to belong to this instance and removing the empty lock.
  This does not establish automatic abnormal recovery or authorize releasing another instance's loop.
- No forced stop, lazy unmount or automatic killing of unknown processes is offered. Manually inspect processes and mounts before recovery;
  **do not simply delete the lock and mount again**. Recovery from process death, device reboot and other abnormal conditions remains unverified.
- The root chroot does not yet map APK private projects or integrate with OpenCode. Once the authenticated root service is complete,
  selected projects will be mapped to `/workspace/<project-name>`; default model execution must drop privileges.
  PRoot terminal project mapping is separate from the managed backend described below.

## Managed OpenCode serve in Ubuntu PRoot

The network-trust settings offer **Run the OpenCode service in Ubuntu PRoot (experimental)**
(`serve-proot-backend`, default off). Install the PRoot instance and the complete
APK native payload first, enable the setting, then manually stop and restart the
managed service. Missing guest/payload/farm fails explicitly without direct fallback.
The terminal-backend preference remains independent; selected terminal projects
are not automatically bound into this managed guest.

The backend runs through PRoot and the guest loader, with APK payloads bound at
`/mnt/andcode-exe`, the farm at `/mnt/andcode-farm`, and `files/home` at `/root`.
Configuration, sessions and guest `/root` writes therefore persist in app home.
The imported CA directory is bound at `/mnt/andcode-ca` only after explicit CA
enablement and validation. Loopback proxy use is a separate default-off opt-in;
TLS verification stays enabled. Guest temporary files and PTY sockets use `/tmp`.
Web/TUI retain `127.0.0.1:4096`. PRoot's apparent root remains the Android app UID;
binds are writable and this is not a sandbox or a root chroot integration.

On 2026-11-11 device `8c8da214`, the app-spawned untrusted_app process chain
proot -> guest loader -> oc2 serve passed Web HTTP 200, authenticated API and
`arjata/gpt-oss-120b` plain-text response `ANDCODE_PROOT_SERVE_OK`. Agent shell
commands returned `ANDCODE_PROOT_TOOL_OK`, exit 0, Ubuntu 24.04.4 and
`/usr/bin/bash`. A Web PTY executed `id`, OS and marker commands and exited 0;
guest `/root` writes were readable in host `files/home`. The diagnostic PTY was
deleted. Manual stop left no serve PRoot/loader tree, listener or env fragment;
restart restored the service. Device PRoot/proxy/CA opt-ins remain enabled.

Tool execution passed, but provider continuation after the tool result still
returned HTTP 400 `openai_error` or HTTP 503. Full model/tool round trips remain
unresolved; no protocol workaround, history deletion or default direct-network
success is claimed. Root Ubuntu instances, `ubuntu.img` and the active runtime
farm are preserved. Other devices and abnormal-stop recovery remain pending
P0/P3 on-device verification.

Same-day reinstall retest of the reviewed build (overwrite install, data
preserved): the three opt-ins survived, the PRoot chain and binds matched the
reviewed argv, the Web UI answered 200, new serve-log lines contained no
password record, and the payload stayed opencode 2.2.6. A fresh-session API
probe reproduced the boundary set exactly — plain-text reply succeeded
(`ANDCODE_REVIEW_OK`), the shell tool executed to a completed state, and the
provider rejected the tool-result continuation with HTTP 400 `openai_error`;
three more fresh sessions failed the same way (400, 503, 400). The provider
error is reproducible with the reviewed build, not introduced by the review
changes, and remains unresolved.

Cross-model isolation (same day, same PRoot backend and build) attributes the
defect to the provider's gpt-oss-120b tool path: a two-turn plain conversation
resending turn-1 history with `reasoning_content` succeeds, and a complete
agentic tool round trip passes on `arjata/glm-5.2` — the shell tool executed,
the tool result was resent, and the model replied `ANDCODE_MODEL_TOOL_OK` with
outcome succeeded. This is the first verified full model/tool round trip on the
managed PRoot backend. gpt-oss-120b failed the same tool continuation in 5/5
fresh sessions (HTTP 400/503) while plain replies stayed fine. Use a model with
a working tool path (glm-5.2) for agentic sessions until the provider fixes the
gpt-oss-120b route.

Full agentic toolchain dispatch (same day, `arjata/glm-5.2`, same PRoot
backend): the model planned and dispatched a five-step chain in one session —
shell `uname -m` (aarch64), write `/root/hello.c`, `gcc` compile (exit 0),
run the binary (`HELLO_ARM64_OK`), `readelf -h | grep Machine`
(`AArch64`) — with every tool call completed and exit 0 and a successful final
continuation. Guest inventory via the session shell API: Ubuntu 24.04.4, bash
5.2.21 (aarch64-unknown-linux-gnu), git 2.43.0, gcc/cc/python3/make/readelf
present. Availability notes: glm-5.2 returned transient 503 "no available
channel" twice, recovering on retry; every other listed gateway model answers
`provider.no-route` (unavailable), so only gpt-oss-120b and glm-5.2 are routed. See DESIGN v0.4.54 section 4.4 for evidence
scope.

External arm64 executable execution (same day, same backend): three external
binary classes ran inside the guest, all exit 0. First, an externally
downloaded musl-static busybox (Alpine 1.36.1-r21, staged via adb into
`files/home` and seen at guest `/root/busybox`) ran `echo`, `uname -m`
(aarch64) and its banner; multi-call binaries identify applets by `argv[0]`,
so the file must be named `busybox`. Second, the APK payload musl-static
`libandcode-opencode-pty.so --version` reported
`opencode-pty 0.4.0 (protocol 7)`. Third, the glibc `libandcode-oc2.so
--version` ran via the guest loader with farm/native library paths and printed
`opencode v2.2.6`. The model then dispatched both the external busybox and the
APK pty launcher through the shell tool in one agentic session, with exact
outputs and a successful continuation. The farm's Termux proot is
bionic-linked and correctly remains host-only, not guest-executable.

Multi-library dynamic executable (same day, `arjata/glm-5.2`, same backend):
the guest links against `libm`, `libpthread`, `libdl`, `libz` (plus
`libcrypto.so.3` and `libtinfo.so.6` present). The model wrote a C program
using sqrt, pthread create/join, `dlopen`/`dlsym` of `libm.so.6` at runtime
and zlib `compress2`; the first gcc run failed on the missing `zlib.h` dev
header, and the model recovered autonomously by installing the dev package
via apt through the explicit proxy before recompiling (exit 0). The binary
ran with exit 0 (marker, sqrt, pthread ok, `dlsym(sqrt)=1`, zlib 15 -> 23
bytes) and `readelf -d` listed `libz.so.1`, `libc.so.6`,
`ld-linux-aarch64.so.1` as DT_NEEDED: on glibc >= 2.34 the math/pthread/dl
libraries are merged into libc, so they no longer produce separate NEEDED
entries and libm was instead verified through the runtime `dlopen` path.
Dynamic linking resolution for multiple object libraries therefore works in
the guest, including model-driven build failure recovery.

Canonical rootfs unification (DESIGN v0.4.55): the CI-built canonical rootfs
archive becomes the shared build artifact for both the chroot and PRoot
backends. Device instances stay separate per tier and both acceptance gates
remain in effect. The single-APK flow is now validated on device
8c8da214: a fresh install of the CI artifact APK (640.5 MB, no prior data)
auto-extracted the embedded 193 MB archive into a 566 MB proot-rootfs on
the first serve start, published the digest marker, and brought up the
PRoot serve chain (Web 200; guest sanity aarch64, gcc 13.3.0, git 2.43.0,
mawk alternatives symlink all exit 0). Existing device instances were not
touched by this path. The terminal backend now defaults to this Ubuntu
rootfs automatically (a missing instance auto-extracts in the background
with an in-session wait), and device storage is bound at /mnt/sdcard in
both the serve guest and the terminal session — Download verified
read-write from the guest. The proxy address and scheme are configured by
the user (no default is assumed); a socks5 URL set on the device was
verified to flow through the guest environment verbatim.
Extraction diagnostics are surfaced via logcat
(tag andcode) because the failure reason otherwise only flashes in the UI.

## Required On-Device Gates

| Check | chroot | PRoot (real application domain) |
|---|---|---|
| rootfs Bash, PTY and terminal size/signals | Bash/PTY creation passed; interactive size/signals pending P0/P3 | Bash/PTY/child processes, initial stty size, Ctrl+C, exit return and two SIGWINCH/size synchronizations across an IME round trip passed; other devices pending P0/P3 |
| DNS, HTTPS certificate verification, `apt update/install` | Root proxy mode passed; UID 60000 networking timed out, direct DNS did not pass | Explicit proxy fully passed; TCP DNS HTTPS/apt update/Git without explicit proxy passed, VPN not disabled |
| Newly installed `hello` ELF runs | Both root/ordinary user passed | Application domain passed |
| Ordinary-user gcc compilation/execution, writes to `/etc` rejected | UID 60000 passed, LOAD 0x4000 | Pending P0/P3 |
| Continued execution after libc update (do not blindly reuse old offset patches) | 2.39-0ubuntu8.7 → 8.9 passed | Execution after the same-version update passed, ELF unchanged |
| Project access scope, no leftover mounts after stop/abnormal exit | Pending P0/P3 | Single-project bind/writeback/invalid-path rejection passed; not a sandbox, abnormal stop pending P0/P3 |
| OpenCode tools and Web PTY use the selected backend without host root | Scoped integration passed; broader device acceptance pending | Device 8c8da214: opt-in managed PRoot serve, guest shell/PTY and app-UID execution passed; full tool round trip verified on `arjata/glm-5.2` (plain two-turn with history `reasoning_content` also passed); `arjata/gpt-oss-120b` tool-result continuation fails provider-side (HTTP 400/503, 5/5 fresh sessions) while its plain replies pass; other devices pending P0/P3 |

When PRoot fails, its status must remain "restricted/unavailable"; root relabeling must not be used to claim locked support.
