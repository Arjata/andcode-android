# Reusable Open-Source Project Research (docs/REUSE.md)

> Research date: 2026-11-06 · License information was verified repository by repository that day through the GitHub API / source LICENSE files.
> Project license: **AGPL-3.0-only** (full text in the repository-root `LICENSE`).
> v0.3 synchronization: the design removed third-party host dependencies such as Termux; inventory roles were adjusted accordingly.

---

## 1. Summary of Findings

| Finding | Explanation |
|---|---|
| ✅ Permissive components, subject to their actual dependency closure | opencode (MIT), dropbear (MIT), jackpal terminal library (Apache-2.0), termux-exec (Apache-2.0). Preserve applicable notices and audit bundled dependencies separately; a permissive root license does not approve the complete artifact. |
| ⚠️ Bun runtime: redistribution review blocked | Bun's root license is MIT, but its statically linked JavaScriptCore/WebKit and other dependencies require separate source, notices and modified-library relinking review. Do not treat the root MIT notice as sufficient approval. |
| ⚠️ Aggregation of independent programs (no source incorporation) | busybox (GPL-2.0, static single file), proot (GPL-2.0, fallback): distributed as independent executables, still subject to applicable GPL corresponding-source delivery obligations; upstream URLs are not compliance approval; **their source must not be copied into this repository** |
| 🔧 Build-time only (not distributed in the bundle) | patchelf (GPL-3.0, soname rewriting in CI), termux-elf-cleaner (GPL-3.0, as needed): the tools themselves are not in artifacts, so there are no distribution obligations for them |
| ⚠️ Reference implementations | termux-pacman/glibc-packages (MIT): comparison baseline for shim and sysroot; **Happ1ness-dev/bun-termux (MIT, ★85, active): the best proot-free Bun predecessor**; termux-exec (Apache-2.0): LD_PRELOAD interception reference |
| ⬇️ Downgraded to optional | Termux family (GPLv3): no longer the host, only an alternative appendix path; no obligations when merely invoking a third-party app already installed by the user |
| ❌ Code not reusable | tribixbite/bun-on-termux, termux/termux-boot (no LICENSE found), **CypherpunkArmory/UserLAnd (★4.3k, no LICENSE = all rights reserved)**: observe behavior/UX only, do not copy code |

---

## 2. Candidate Inventory

### Build-only rootfs bootstrap candidate (2026-11-10)

`mmdebstrap` is evaluated only on the native Ubuntu 24.04 arm64 CI runner;
it is not bundled into the APK or required on Android. The upstream main
script at `https://gitlab.mister-muffin.de/josch/mmdebstrap` was inspected on
2026-11-10: its header grants the MIT/Expat license, copyright Johannes
Schauer Marin Rodrigues. This verifies that script, not every helper or
dependency in the distribution package. CI retains the installed package's
copyright file and package/tool versions for the exact invocation. No upstream
code is copied into this repository. The experiment uses signed Ubuntu noble,
noble-updates and noble-security package indexes without disabling signature,
expiry or TLS checks. Package/source versions and signed indexes are evidence,
not a corresponding-source bundle or byte-reproducibility claim. Existing
Docker builds and device instances remain unchanged until independent CI review.

The next experimental recipe also retains exact installed source versions via
authenticated `deb-src` indexes at the same official snapshot. It uses the
guest's existing apt client in download-only/only-source mode: no new dependency
or source code is copied into this repository. The resulting external CI source
archives, `.dsc` files, logs and hash inventory are acquisition evidence only.
Package patches, build recipes, generated inputs, notices and redistribution
conditions must still be reviewed; no complete-source or license approval is implied.

### 2.1 Core Delivery Components (Permissive Licenses, Bundled)

| Project | Repository | License | Role (DESIGN §4) | Reuse Method |
|---|---|---|---|---|
| opencode | `sst/opencode` (★224.8k, active) | MIT | Porting target itself; official releases include linux-arm64 (glibc) artifacts | Run its artifacts directly; patch as needed (patches under this project's AGPL) |
| opencode V2.2.6 | `anomalyco/opencode`, tag `v2.2.6` | MIT (tag LICENSE checked on 2026-11-09) | Pinned Web/serve payload separate from the older version | Official linux-arm64 archive pinned to SHA-256 `f2d27600c367e45057d6a16f6a5c2aa8d77b41a9b10d4bc3d849c2f88870e944`; staged as oc2.bin by CI, not downloaded on device |
| opencode-pty | `anomalyco/opencode`, `packages/process-daemon`, tag `process-daemon-v0.4.0` (`5e6ee370634842e0efa99ad103c4d767581b47f0`) | MIT (that version's Cargo.toml/license and npm package LICENSE checked on 2026-11-08) | V2 Web terminal daemon, protocol 7; separate pre-staged copy rather than runtime extraction into app data | Development deployment uses the official aarch64-unknown-linux-gnu asset with rewritten PT_INTERP; `OPENCODE_PTY_BIN`/`OPENCODE_PTY_SOCKET_DIR` already exist upstream in this version, requiring no source changes; formal packaging must register generated manifest and notices (CI integration pending) |
| bun | `oven-sh/bun` | MIT root; pinned JSC `COPYING.LIB` is GNU Library GPL v2; tinycc is LGPL-2.1. Per-file and actual static-input conditions require separate review. | OpenCode runtime and build tool | Source declarations and URLs alone do not satisfy or approve corresponding-source/relinking obligations; runtime redistribution remains blocked pending closure. |
| V2 source-built pre-staged extension experiment | `anomalyco/opencode` v2.2.6 commit `dc2ffcf8bf26f9e669b6aa22b95f50e12be15e06` | MIT; tag LICENSE checked on 2026-11-09 | Manual CI builds pinned source with a frozen lockfile, without replacing the current official payload | Bun 1.4.4 arm64 archive pinned to SHA-256 `baa6bb36f51d6e58561e02bbea825038a9df454f673d6d776e8bbf86f8c7850e`; retain upstream LICENSE/lockfile; experimental only until transitive native-library compliance/compatibility auditing is complete |
| V2 embedded native extensions (experimental separation) | OpenTUI 0.8.1, Parcel watcher 2.5.1, bun-pty 0.4.11, fff-bun 0.10.5 | **OpenTUI native packages are MIT AND LGPL-2.1-or-later, not MIT alone**; other npm metadata says MIT. On 2026-11-09, pinned tarballs were verified against registry SHA-512 and package licenses inspected: watcher/bun-pty include MIT; the fff platform package has no LICENSE, so metadata alone cannot approve distribution | Replace file imports with explicit nativeLibraryDir loading; no disguised temporary files or Bun runtime ELF extraction | No third-party code copied into the repository; OpenTUI also includes LICENSE-FFMPEG/GHOSTTY/LCMS2/LIBWEBP/STB/WUFFS/ZLIB, requiring separate source/build/relinking tracking; transitive Rust/C/C++ notices and corresponding source remain unreviewed, so this must not be called a formally distributable closure |
| dropbear | `mkj/dropbear` (★2.5k, active) | **MIT** (LICENSE text verified: Matt Johnston, MIT-style grant) | Built-in sshd shared by all three forms (§4.7 interaction entry points) | Build static/dynamic versions within the baseline and distribute with the bundle |
| termux-exec | `termux/termux-exec` (★268, active) | **Apache-2.0** (LICENSE inspected: Apache-2.0 + MIT components) | **LD_PRELOAD interception reference implementation**: years of Android LD_PRELOAD engineering directly inform §4.5 shim interception scope and pitfalls | Reference implementation; retain Apache-2.0 notices if taking code |
| jackpal/Android-Terminal-Emulator | `jackpal/Android-Terminal-Emulator` (★3.2k) | **Apache-2.0** | Tier P APK terminal-emulator core (emulator/view libraries may be incorporated into the AGPL project) | Minimal fork (upstream stopped updating in 2022; all existing forks stalled in 2014–2021, verified), retaining copyright notices |
| **Termux terminal-emulator / terminal-view (final P3 choice, incorporated)** | `termux/termux-app` modules (★64.2k, active) | **GPLv3** | P3 APK terminal core (selected because jackpal is inactive) | One-way GPLv3→AGPLv3 compatibility; incorporated into app/terminal-* (copyright headers retained, app/NOTICE-TERMINAL.md); combined work as a whole AGPL-3.0-only; publishing this repository satisfies the source obligation |
| proot (Termux bionic build) | packages.termux.dev pool/main/p/proot | **GPL-2.0** | **The /etc redirection solution for Tier A/M** (on-device P0: LD_PRELOAD cannot intercept glibc internal fopen("/etc/resolv.conf"); proot bind enabled the complete git https chain in device testing) | Independent-program aggregation; proot + loader + libtalloc (LGPL-3.0) + libandroid-shmem (**BSD-2-Clause**, termux/libandroid-shmem LICENSE checked) distributed with the bundle and recorded in manifest |
| ConnectBot | `connectbot/connectbot` (★3.6k, active) | Apache-2.0 | Recommended Tier A/M SSH client (**optional tool, not a dependency**) | Documentation recommendation only |

OpenTUI diagnostic builds separately pin the official Zig **0.17.0** arm64 Linux archive
`https://ziglang.org/download/0.17.0/zig-aarch64-linux-0.17.0.tar.xz`，SHA-256
`9e8d11661d4ae3bd57702a3832781e23ad151dde5798e16a5ccd503f65234ff8`, 52877280 bytes.
Downloaded and rechecked on 2026-11-09: root LICENSE is MIT (Expat), Copyright Zig contributors,
LICENSE SHA-256 `5c537d6853e005298a285d508cff9ac7192cea23576c840d485b2b586a7ff177`。
Used only as a build tool, not distributed with the APK; toolchain LLVM/libc/libc++ and static output inputs still require independent
item-by-item review. Root MIT does not cover the whole output. It uses a separate path from fff's Zig 0.16.0, without upgrading the latter.
The first OpenTUI CI `42621241263` (commit `b0f1aba`) completed the glibc FFmpeg build, but upstream
failed on missing `require-video` while configuring unexecuted musl test/benchmark targets;
no npm input was replaced and no passing diagnostic package produced. The follow-up adds an
`andcode-library-only` configuration early return only for explicit library-target, retaining `require-video=true` for the selected library and the 16K gate.
No musl FFmpeg is built/collected and acceptance conditions are not relaxed. That commit's regular CI `42621206258`
passed app-data-tests/build-bundle; the APK job failed on a corrupt NDK download ZIP before
running Gradle, so APK success is not claimed.
An additional post-build check validates generated FFmpeg `config.h`: the license string must be LGPL version 2.1 or
later; GPL/version3/nonfree/network must be disabled and zlib enabled. Missing/conflicting macros or configuration
drift prevent experimental input replacement. The only permitted duplicate is equal-valued `CONFIG_LIBSMBCLIENT 0`, listed in both the GPLV3/general
external library tables by pinned FFmpeg 9.0.2 configure; other duplicates remain
rejected. CI `42623976037` (commit `5c80984`) failed because the original checker rejected this upstream duplicate,
not because Samba/GPL was enabled or source compilation failed. Horizontal-whitespace matching prevents a valueless header guard from consuming
the next line. This configuration check guards only against recipe drift; it does not replace per-file C/assembly licensing,
patent/regional-use restrictions or LGPL corresponding-source/relinking-material review.

Source-experiment CI's `collect-opencode-native-licenses.py` checks installed source bytes/package names/versions/declared licenses
for each of the four pinned native imports, retaining package top-level LICENSE*/COPYING*/NOTICE* and package.json
in diagnostic artifact `native-license-evidence/` and generating `native-license-review.json`.
Missing notices are recorded as `blocked-missing-package-notice`; even with notices, status remains `blocked-transitive-review`.
`redistributionApproved` is always false. This is not transitive-source review and does not cover all Bun/JS/Web dependencies;
neither successful CI nor collected LICENSE files mean compliant delivery is complete.

The first complete OpenTUI Linux experiment CI `42623009744` and regular CI `42622973489` both succeeded,
at head `1a43a9e9baea98e934ca4ca16c21d275ff408d32`. Diagnostic artifact
`13678007813` is 442621775 bytes; ZIP SHA-256
`018e7de71f9c0775e2d4d5eccd0b90b83cbb23df52eb7d56147cbb6bb5794fb6` matches the API.
The initial download was truncated and was verified only after resuming it. All 18946 original manifest digests matched, but another
10399 files collected by the uploader by dereferencing FFmpeg build/src directory links were absent from the original manifest. These
extra files were checked by byte digests against the same relative paths under manifested `sources/ffmpeg-9.0.2`; all matched.
**The original artifact file set remains unclosed**; matching extra source bytes does not establish original-manifest completeness. Subsequent builds use
`manifest-opencode-native.py` to generate the manifest from the uploader's dereferenced view, rejecting out-of-bounds/cyclic links and
special files. Closure must be rechecked by downloading the next artifact.

Manifest-fix commit `1d3d37ee1ed5a410400dc80e117d77df6c385024` passed source experiment
`42628073140` and regular CI `42628022675`. Artifact `13680841250`'s
443040684-byte ZIP SHA-256
`a2f448c01a7a268b0827310a1bd00bbe2c6db637830cb64c20cf08222152a1bd` matched the API
and complete local download. The 29345-file set exactly matches the digest manifest; every SHA-256 passed,
with 0 manifest gaps. The four native ELF import manifests/origin reports/rebuild digests, 9 Ubuntu dynamic libraries
and 14-entry recursive closure report agree; bun-pty's 37 and fff's 116 registry crate archives match lock
checksums. All 347 FFmpeg/zlib objects and the safety configuration above passed rechecking.
This round's OpenTUI ELF SHA-256 is
`daa2f6fc84cbedd079db842b3afb53a562420695a0ef9c1d4ae8195881b5ad97`, still
32974432 bytes. Different builds produced different digests; bit-level reproducibility is not claimed. Actual logs for Linux API/PTY/TUI and isolated-directory
no-runtime-ELF gates were checked; all license and Android approvals remain false.

This round's rebuilt OpenTUI ELF is 32974432 bytes, SHA-256
`312aa75db50cd70dc92fedc458ad20db5e9a5e7b68a4a2f1b021d1f090be6b0d`; build output matches
the Bun pre-staged copy. NEEDED is libc/libm/libpthread/libdl; ELF glibc≤2.39/16K gates
passed. All 347 FFmpeg/zlib objects were rechecked against reported paths/sizes/digests. The corrected checker on the artifact's actual generated
config.h passed LGPL2.1, GPL/version3/nonfree/network=0 and zlib=1
gates. All four libraries report fixed-source-ci-rebuild origins; ABI, real file events, indexing/search/glob,
ordinary/persistent PTY, TUI rendering/pre-staged library maps and isolated HOME/BUN_TMPDIR no-runtime-ELF logs
passed. This covers only the Linux experiment, not Android application-domain acceptance, original npm ELF reproducibility or license approval.
Subsequent commit `5c80984` passed regular CI `42623847446`; its source-experiment failure boundary is described above.

On 2026-11-09, preliminary notice review of pinned OpenTUI source also checked the nested Yoga/Ghostty/uucode MIT
texts, lcms2 MIT, libwebp COPYING and PATENTS, stb dual licensing, Wuffs Apache-2.0,
and the Unlicense / MIT-0 dual-option text at the end of miniaudio.h (Copyright 2025 David Reid).
The miniaudio license is embedded in the header and does not appear in a LICENSE-filename-only scan;
this does not establish per-file closure for other embedded dr_* implementations or generated data. Zig build.zig explicitly sets
Yoga `link_libcpp=true`; corresponding source/notices for the toolchain C++ runtime must also be counted. None of this
adds dependencies or copies code into the repository; complete notice/obligation review must still follow actual compile/link inputs.

The successful artifact above has exactly one final `ld.lld` command in its Zig verbose-link log, explicitly referencing
448 inputs, including five static libraries libc++abi/libc++/libunwind/libc_nonshared/libcompiler_rt
and Zig-generated glibc link stubs. The subsequent builder retains copies of this command's inputs in argument order,
with original paths/build origins/sizes/SHA-256, requiring them to reside only in the pinned OpenTUI build tree or two
dedicated Zig caches. Missing files, response files, relative paths, unknown options, out-of-bounds links and
link-output/installed-result mismatches are rejected; failure leaves experimental npm inputs unreplaced. Link-stub copies document build-time
inputs, not Ubuntu runtime libraries. Retaining static libraries does not establish selected members/per-section attribution/complete corresponding source,
much less acceptance of LGPL replaceable relinking; these limitations remain.
Only command-shape replay and synthetic regressions were completed locally; new link-input retention requires verification in the next real CI run.

Subsequent source CI `42632448278` / regular CI `42632416589` (head `e0ca1b7`) both succeeded.
Artifact `13681818902`, 459080002 bytes, ZIP SHA-256
`f1f0ebec0ec8d78fe777ce72b81ddc8e686aca6f0e4be300b39b09966320a456` matches the API;
the 29793-entry manifest set is closed and all digests match. All 448 actual link-input copies were checked for
argument order/paths/sizes/digests; 347 FFmpeg/zlib objects agree with the original object report.

The pinned official Zig 0.17.0 archive's libc++/libc++abi/libunwind LICENSE.TXT,
`lib/libc/glibc/LICENSES` and root MIT LICENSE were also checked (2026-11-09). Subsequent builds retain only all regular
`lib/` resources and root LICENSE/README.md from the same-digest archive as a separate candidate-source archive,
recording each resource's byte digest and rejecting links/out-of-bounds/duplicate/ELF entries; the Zig tool executable is not retained.
These resources include LLVM libraries, Zig compiler-rt/standard library and glibc support source, but do not establish complete
Zig/LLVM toolchain source, per-file license review, Bun/JSC corresponding source or relinking delivery approval.
Running the collector locally against the pinned archive produced 19503 entries and 187671709 raw-resource bytes; all
required notices were present and no resource ELF was found. All 65 native Python regressions passed. The archive and individual digests will
be retained with diagnostic reports; CI artifact rechecking still awaits the next run.

Source CI `42633493308` / regular CI `42633461482` (head
`605787da5f2dd4201568eceac243e378433734b3`) both succeeded. Artifact `13683491047`,
489519009 bytes, ZIP SHA-256
`ffd1260792bdc202a0208bed2363501c67a2638eb3602f28e18bfcc49f71770d` matches the API.
The 29794-file manifest is closed and all digests match; 448 link inputs and 347 media objects
agree. The 19503-entry Zig resource archive manifest is closed and every digest matches the original bytes at the same path in the pinned official tool archive,
without including Zig ELF. Logs for two rounds of Linux ABI/API/PTY/TUI/isolated-directory no-runtime-ELF
checks were reviewed; this still is not Android/license approval. The download interrupted by insufficient disk space was moved to
drive F with user authorization. The original temporary ZIP copy was deleted only after matching pre/post-move digests; the resumed download passed the final API digest check.

**New license blocker discovered on 2026-11-09 (overrides broad interpretations of the configuration gate above)**: preliminary review of actual
FFmpeg `.d` compile dependencies mapped 336 objects to 736 dependency files, with an explicit remaining gap for 11 zlib
objects missing `.d` files. `libavutil/aarch64/crc.S` explicitly declares
GPL-2.0-or-later, and `objects/libavutil/aarch64/crc.o` (2232 bytes, SHA-256
`918940cacb3c696d99b95173abf7793eb60b8566455080f65889838649d0b910`) is indeed in the final
link command. Even with `CONFIG_GPL=0`/`FFMPEG_LICENSE=LGPL`, absence of linked
GPL-declared code cannot be inferred. Existing successful artifacts remain blocked; third-party text is unchanged and distribution approval is not granted retroactively.
The subsequent pinned recipe adds `--disable-armv8` to exclude upstream ARMV8-OBJS (retaining independent NEON
configuration), requires HAVE_ARMV8/HAVE_ARMV8_EXTERNAL=0 and directly rejects that CRC object. It collects
source paths/digests from actual make dependencies and rejects experimental input replacement when a GPL-only declaration is found
in the first 100 lines after removing comment wrapping. This is a conservative gate, not a complete per-file license determination; system headers, zlib headers,
conditional macro selection, archive members/final surviving sections and other source obligations still require manual and actual-build verification.

The initial exclusion commit `190b518` passed regular CI `42641908404`, while source CI `42642081860`
failed at final linking. The full job `129245514248` log and failed artifact were checked:
`13687470347`(ZIP SHA-256
`701c5d8cd0509acf7dd58e024ef9b36de425712f37650a91fb14630269852186`)。
Upstream `aarch64/crc.h` independently selects
`ff_crc32_aarch64`, `ff_crc_neon_pmull` and `ff_crc_le_neon_pmull` through HAVE_ARM_CRC and HAVE_PMULL/HAVE_EOR3; they are not automatically disabled with
ARMV8-OBJS, so excluding only the assembly object leaves three undefined references. The follow-up recipe also
adds `--disable-arm-crc`/`--disable-pmull` and requires generated HAVE_ARM_CRC and
HAVE_PMULL both to be 0, falling back to the generic C CRC path without changing third-party licenses or supplying same-named implementations.
Independent NEON configuration stays enabled. The new recipe awaits real arm64 CI and artifact review; synthetic regressions cannot
establish successful linking, media or Android acceptance.

To avoid treating successful TUI rendering as CRC correctness, a project-owned `crc-probe.c` is added, statically linking
libavutil from the same prefix: 8 standard polynomials, three table forms (standard/257-entry/1024-entry), 8
unaligned offsets, 6 lengths and zero/nonzero seeds yield 2304 cases, each compared against an independent bitwise reference algorithm and chunked continuation.
Any compilation/run/marker failure prevents experimental npm input replacement. Probe source, commands, logs
and ELF digests remain only in diagnostic artifacts, not the APK; linking occurs on the runner and cannot establish Android,
complete decoding or the final shared library's exported media interface. The new gate passed synthetic failure regressions and Windows
Clang C syntax checks; actual execution still awaits native arm64 CI, and passing all 2304 calculations is not claimed.

Subsequent actual verification (2026-11-10): commit `37e6536` passed regular CI `42645263750` and source CI
`42645293538`. Artifact `13689266279`, 489539534 bytes, ZIP SHA-256
`260246d7f7043910a8795a49b9aabc3b64cd0b2370c16db3fb934f24d80d91c9` matches the API.
The 29786-entry manifest set is closed; all 446 final link inputs and 345 media objects match their digests.
Direct recomputation from artifact make dependency files maps 334 objects→733 actual source dependencies, all matching sizes/digests;
11 zlib objects still lack `.d`. Actual HAVE_ARMV8,
HAVE_ARMV8_EXTERNAL, HAVE_ARM_CRC and HAVE_PMULL are all 0; the CRC assembly object is absent from
the object table and final link inputs, with independent NEON retained. All 19503 Zig resources match the pinned archive.
Job `129256831289` logs confirm real Linux ABI/PTY/TUI/isolated HOME/BUN_TMPDIR no-runtime-ELF
gates passed; Android acceptance or correspondence to older npm ELF files cannot be inferred.

CRC-probe commit `4bfeb01` also passed regular CI `42646804980` and source CI `42646838972`.
Artifact `13690215064`, 489629927 bytes, ZIP SHA-256
`5010c990855de9bf254821959a0734d372341ea6fd068c73bd5a39122bd9b06a` matches the API.
The 29789-file manifest is closed; all 446 link inputs, 345 media objects, 334→733 source
dependencies and 19503 Zig resources were rechecked. Actual `crc-probe.log` contains the 2304-case success marker;
source and standalone probe ELF digests match the report. Linux ABI/PTY/TUI/no-runtime-ELF logs passed again
(job `129262254406`). Rebuilt OpenTUI is 32969560 bytes, SHA-256
`2fe57e9fbcd1096b0532a04b98744480d6f0c89f8454034e77504b7ce142cfd7`，
NEEDED remains libc/libm/libpthread/libdl; static glibc≤2.39/16K gates passed. Different ELF
digests across the two rounds are not misrepresented as reproducible builds. License, corresponding-source and Android approval fields all remain false.

Further manual preliminary review of the first 100 lines of 733 actual dependencies found, besides LGPL, three IJG-noticed
source files `libavcodec/jfdctfst.c`, `jfdctint_template.c`, `jrevdct.c`, plus embedded
permissive-license/generated-header candidates. Final notices must retain these specific declarations and attributions rather than attach only LGPL.
This round still is not full-file or complete-closure licensing review; no third-party code/binaries were copied into the repository.
Subsequent full-text keyword review of the same artifact's 733 dependencies found additional license paragraphs at `libavutil/libm.h` line 101
and `mathematics.c` line 234, and a separate copyright candidate at `libswscale/filters.c`
line 303. The first-100-lines gate is not complete notices. The subsequent recipe retains, for actual dependencies,
complete C block comments containing licensing keywords, exact byte ranges/start lines/digests, and keyword lines outside block comments.
Original bytes can be checked against source; it does not automatically determine licenses, remove nested declarations, or infer absence of obligations
from absent keywords. The candidate report still has scope limitations including system headers, missing zlib `.d`, non-comment declarations/generators.
The new collector was actually run locally on original artifact `42646838972` bytes, covering 733 dependencies and retaining 732
block comments and 11 outside-block candidate lines, with checkable ranges/digests. This is a locally reconstructed candidate report,
not evidence already bundled by older CI; retaining it in subsequent artifacts still awaits CI.
The existing Windows LLD 23.1.2 also successfully cross-linked all 446 retained inputs locally, retaining map and
archive extraction diagnostics; output differs byte-for-byte from the original ELF (32969640 bytes) and was not run.
This proves only that another linker can consume these inputs; its member selection must not be misrepresented as original Zig final-link
evidence, let alone acceptance of modified FFmpeg replacement/relinking on Linux/Android or distribution approval.

The subsequent diagnostic recipe adds retained-input replay with the same fixed Zig `ld.lld`: all input paths point to
digest-verified copies, changing only the output path and adding map/why-extract reports. Experimental npm input replacement requires the resulting ELF
to match the original build byte-for-byte and pass ELF static checks and Bun ABI/maps probes.
Unsupported linker behavior, input drift, differing bytes or missing reports/probes fail the gate; it neither falls back to another linker
nor relaxes equality requirements. The new gate awaits real CI; even a successful report proves only original-link replay with unchanged
inputs, not replaceable relinking after modifying FFmpeg or LGPL/Android distribution approval.

Real source CI `42652931946` / regular CI `42652895593` for same-linker replay
(head `6dd5352`) subsequently succeeded. Artifact `13692081137`, 499726018 bytes, ZIP
SHA-256 `1f0759d782d19d79188f4b057659587115f8576714f5d6ac479fe3d039edf321`
matches the API. The 29794-file manifest is closed; all 446 inputs/345 media objects/334→733 source
dependencies/19503 Zig resources were rechecked, and 2304 CRC cases passed again. Replay with the same fixed Zig produced
byte-identical output to the original ELF; Bun ABI/maps passed and map/archive extraction report digests
matched, recording 25 extracted archive members: libc++abi 15, libc++ 2, libunwind 4,
libc_nonshared 3, compiler-rt 1. Extraction does not establish survival of every member's sections or complete
source attribution for those members. Original artifact OpenTUI is 32969560 bytes, SHA-256
`a096fceb66780f25e47fe83849d9f9cfe6c93ee385e4ea02d382d10374fadb3c`；job
`129283784357` full logs were retained; Linux PTY/TUI/no-runtime-ELF gates passed, still without
modified-library relinking or Android approval. The local verifier's earlier Zig subcommand argument-offset error was corrected;
recomparison of all arguments and actual ELF bytes passed without relaxing artifact gates.
The 25 members were also read individually from the five retained static archives locally, confirming unique member names and ELF
contents and recording each size/digest. This binds extraction records to actual archive bytes, but still is not
a complete mapping of compiler arguments/preprocessed inputs to source licensing; no third-party ELF was added to the repository.
Subsequent DWARF inspection located compilation-unit paths for 24 members in the
pinned official Zig archive. The compiler-rt compilation unit is named only
`compiler_rt`; its line table lists 90 official source-file candidates and 1
global-cache-generated `builtin.zig` that the older artifact did not retain.
Self-reported DWARF paths do not prove source-to-object rebuildability or section
liveness and cannot establish approved source attribution. The subsequent recipe
retains post-build `b/<hash>/builtin.zig` bytes, source paths and digests from both
explicit caches, rejecting symlinks, unexpected paths, ELF and oversized inputs.
These are generated-input snapshots, not a complete compiler-input closure or a
retroactive addition to older artifacts.

Source experiments `42655395777` (head `5c66a5b`) and `42656714390` (head `412fd1d`),
and their regular CI runs `42655354765` and `42656524852`, all succeeded. Both
artifacts were independently verified: artifact `13692138201` is 501250589 bytes,
with ZIP SHA-256 `77ca20972725eda50f08d66427ec265652a5716e006cb4ad5106ecf046d70e87`
and a closed 29801-file manifest; artifact `13694046156` is 501336313 bytes, with
ZIP SHA-256 `5887e5a57da3788fe6d4106bb362c74709a0335a588f73a8789d2a1c3b03f6b8`
and a closed 29802-file manifest. Both match the API metadata. Reapplying the
four-file sorting patch to the pinned original archive reproduced the build tree
byte for byte. The modified lockfile and 119 selected dependencies exclude
glidesort; 3 arm64 sorting tests and search/glob probes passed. The original
candidate graph still includes that dependency; historical evidence is unchanged.
All six Bun/WebKit declaration files matched their commits, digests and retained
bytes. Both runs passed byte-identical same-linker replay of 446 inputs, ABI,
2304 CRC cases, Linux PTY/TUI and the isolated-directory no-runtime-ELF gate.
Full-text recomputation of declaration candidates for all 733 actual dependencies
matched the latest bundled report. These results do not constitute complete
notices, corresponding source, modified-library relinking or Android approval.

For generated-builtin retention recipe `5d444e0`, source CI `42661927969` and
regular CI `42661893364` both succeeded. Artifact `13696046606` was fully downloaded
and independently verified: 501356265 bytes, ZIP SHA-256
`bdafa515d7e840b625c5efcdf911a1a0f83dd20b05a363ad5dc9d3bd1e375940`, matching the
API metadata, with a closed 29816-file manifest. All 14 generated `builtin.zig`
snapshots, totaling 41148 bytes, matched their retained paths, digests and sizes.
All candidates in this run came from the global cache; the local cache had none.
The same-Zig byte-identical 446-input replay, 25 archive extraction records,
119 modified fff candidates, six declaration files, declaration recomputation for
733 dependencies, 2304 CRC cases and Linux runtime gates continued to pass.
The DWARF line table of the sole member of the retained `libcompiler_rt.a` lists
91 files. Its generated path `b/2a01436ccce52344c33c97b4d9478f83/builtin.zig`
resolves to the retained 2340-byte file with SHA-256
`9840d59c686c7d7fa6904bc02eb9e1029aedc5b39cbfe20ac3b3d3b9ff2c2c06`.
This resolves that generated-path gap for this run, not for historical artifacts:
the compiler-rt member digest differs from run `42652931946`, and matching cache
paths do not prove identical contents across runs. Complete compiler inputs,
source-to-object rebuildability, section liveness and modified-library replacement
and relinking remain unproven. All approval fields remain false.

The next Linux-only diagnostic modifies the pinned FFmpeg `libavutil/crc.c`
(SHA-256 `fbcab458ebddda14d121333622525cb0547c1d428645e9286534690c48366ad5`)
in an isolated copy, retaining its original license header and recording the
transformation. It adds a call counter, rebuilds only that object through the
existing configured FFmpeg make rule, substitutes exactly one retained linker
argument, and links with the same fixed Zig tool. The modified library must differ
from the baseline, retain the expected ABI/dependencies, and execute the CRC
reference cases through its exported functions with the counter checked. All
other retained inputs must remain unchanged. This is a single-object
replacement experiment, not complete FFmpeg relinking, corresponding-source
delivery, Bun/JSC compliance or Android approval. It never replaces the staged
baseline library or the official APK payload.

Independent review of source CI `42669933882` (commit `fd4f1cf`, job
`129343485963`) passed on 2026-11-10. Artifact `13698572857` contains 536622025
bytes; ZIP SHA-256 `2abe7e9d916c4ea17cee0ea184705656594532c2dd78bddc2a6440019a789236`
matches GitHub API metadata. The manifest set is closed at 40273 files, including
the isolated modification tree. All 446 retained link inputs and 25 extracted
archive members were rechecked; original same-Zig replay remained byte-identical.
Exactly one CRC object was substituted, while the staged baseline stayed unchanged.
The modified library passed ABI/dependency checks and 2304 CRC cases with 6912
instrumented calls. Baseline OpenTUI SHA-256 is
`ce992bf35c98b577033d0af0eb448f5e13ea0e63cd1fa9c82aed41671ca8af3e`.
The 14 generated builtin snapshots (41148 bytes), 119 modified fff packages
without glidesort, six Bun/WebKit declaration files and Linux runtime gates
also passed independent rechecking. The media dependency evidence still covers
334 FFmpeg objects and 733 files, with eleven zlib objects explicitly missing
dependency files. This artifact predates the zlib dependency recipe update;
it does not close that gap. Verification log SHA-256 is
`11c022cef4abb9aca820aa432532ac295570c6faede1699ceaa254288979faff`.
All redistribution, full relinking and Android approval fields remain false.

The package notice collector now distinguishes npm-owned notices from the fixed
fff rebuild's retained root `LICENSE` (source commit
`459ebcdbdba094843fe5339a1a7f7dae4ced2d82`, SHA-256
`f8264de82db188834a5711d7e348dc08c33db14f79bb587ccb42616fd694ee81`).
It verifies the regular retained file and records a separate `sourceNotices`
entry for a matching rebuild. This does not silently add a notice to the npm
package, infer original ELF correspondence, or approve its transitive closure;
`blocked-missing-package-notice` remains visible for the original package.
Source CI `42680417924` (commit `e197165`, artifact `13703238123`) and an
independent archive review confirmed the exact 1074-byte source notice binding
without altering that npm status. ZIP SHA-256:
`61f33864a53381b1a909a0ebb11f7be968cfc48806b6e8b007aefb66bfe11205`.
The 40284-file manifest, 345 media object / 755 non-system input mapping,
retained verbose compiler output, original relink, modified CRC probe and Linux
runtime gates also passed. The independent log SHA-256 is
`b3de286dfe787fdf3cb282df63e2ad809a328badc1942da201a80baa1269837b`.
No original npm correspondence, transitive license or Android approval follows.

The subsequent recipe will request compiler-generated `-MMD` dependencies for
all eleven zlib objects with explicit `zlib/<name>.o` targets. New builds must
retain these files and map their cache-local source/header bytes before staging.
This closes only the previously explicit zlib non-system dependency gap if
verified by CI; `-MMD` still omits system headers and does not prove complete
compiler inputs or per-file licensing. Historical artifacts without those files
remain unchanged and retain their recorded limitation.

Independent review of source CI `42674532077` (commit `5017bbe`, artifact
`13701261405`) passed: ZIP 536633750 bytes, SHA-256
`80b453f5c48f7f1b13e90298c1ea6d136d3bb65505fc766042219fdc16f56ad0`,
closed 40284-file manifest. All 345 media objects now map to 755 retained
non-system source/header files, including all eleven zlib objects; no dependency
file is missing. The 446-input byte-identical original replay, 25 extraction
records, modified single-object CRC relink (2304 cases / 6912 calls), 14 builtin
snapshots, modified 119-package fff graph, six runtime declarations and Linux
runtime gates remain intact. OpenTUI SHA-256 is
`ad387ba0ed88dc3420e754b6f41e2cb0c6a70f28fa05f3a9824b9b8d916769fb`.
Independent verification log SHA-256 is
`6885fdc91c7d49e9e335c0a3c87edad96903ae3a9f09ff8739549ca31ac9b7fa`.
This closes that run's recorded non-system zlib dependency gap, not system
headers, complete source attribution, licensing, full relinking or Android.

The media recipe will also enable FFmpeg make's `V=1` output, retaining the
actual compiler invocations in the existing build log rather than deriving
commands from DWARF paths or generic flags. This is command evidence only:
response files, generated inputs, conditional preprocessing and system headers
still require separate coverage before complete corresponding source is claimed.
The pinned helper captures subprocess stdout, so `V=1` alone discards that
evidence. The updated transformation explicitly records command/arguments/cwd
as JSON and forwards captured stdout before checking the child exit status.
New builds reject logs without the actual verbose CRC compiler invocation.
The forwarding fix passed source CI `42676981376` (commit `0776ef6`, job
`129360890884`) and independent artifact review. Artifact `13700954839` is a
536648166-byte ZIP, SHA-256
`07e533d6b47c3c50245b98f5d975d8e9241f79aee6dbb36a1d5e8d605a26d4c5`.
The closed 40284-file manifest, all 345 dependency mappings / 755 files, original
replay, single-object modification probe and Linux runtime gates passed again.
OpenTUI SHA-256 is `4cfc1787f31e3f5c57fa5ab7ae85ae6965132c3d161d3859c0be47999acc46b7`;
independent verification log SHA-256 is
`f0c5509dab276cecbf9dc05228d23b4d42b34f48907f978986f880b55999f4e0`.
A separate host review associated the observed argv/cwd/source paths with all
345 retained objects (334 FFmpeg and eleven zlib) and their recorded non-system
dependencies. Its JSON evidence SHA-256 is
`9a2517c7e0f33c422d44a65d6cbc7d11381df3e8b712f8d63e9210b50886156b`.
Earlier recipes are not credited with retaining the discarded compiler output.

The next recipe adds `ffmpegCompileCommands` to the existing build report and
requires one observed compiler invocation per retained media object. It binds
source/object/wrapper digests to recorded command arguments, working directory
and log line, rejecting absent, duplicate, unexpected-wrapper or source/dependency
mismatches before staging. Source CI `42681418653` (commit `4019179`, job
`129376656791`) and independent full artifact review passed. Artifact
`13702819455` is 536695750 bytes, ZIP SHA-256
`94de3fd438c5be4adfadfc64ca422b274c3e017fc13ed70d95d7b7453a5b353b`.
The independent verifier re-derived all 345 command/object bindings, checked all
755 dependency files and retained the 446-input replay and single-CRC modified
relink checks (2304 cases / 6912 calls). Verification log SHA-256 is
`28a5b8690decfbde422c230b24c0191cee9d2b7b7e98cd4733144571bec8735f`.
The rebuilt fff root notice is independently bound to its fixed source without
overriding the npm package's blocked notice status. Recorded
commands are evidence, never re-executed as input; they do not capture complete
preprocessing, system headers, generated-input provenance, surviving sections or
license obligations. All approval fields remain false.

The external per-file media notice report for run `42676981376` has also passed
independent byte/relationship/quotation binding checks: all 755 file digests,
345 object mappings and 751 quoted comment blocks match the retained source
bytes and line ranges. Raw dependency lists contain 8719 references but 8717
unique file/object pairs; repeated `.d` entries for two headers are deduplicated
only in the report, without changing build evidence. Report JSON SHA-256 is
`94f40064ffe7d9adecebf87f3da1d5d6842b67ac7ec85f9abc15d4edd4527cf0`;
parent binding-review JSON SHA-256 is
`3511cc722234bd43932cd1426ffbe8398689e7a37ab34857210e19ef6c8682f6`.
Manual classifications remain review candidates, not independently approved
license decisions: 711 LGPL-header candidates, 28 permissive candidates and
16 inputs with no explicit in-file grant. The ISC-style grant in `faandct.c`
and its IJG provenance reference do not by themselves establish that derived
material has no IJG obligations. Three other files contain actual IJG terms.
Generated-input provenance, complete notices and distribution approval remain
open; the external reports are not an APK notice payload.

The follow-up external generated-input report for run `42681418653` passed a
separate parent byte/digest/direct-rule binding review. All 16 flagged inputs
match run `42676981376`; four are byte-identical to files shipped in the pinned
upstream source archives (zlib `crc32.h`, `trees.h`, `inffixed.h`, and FFmpeg
`uops_macros.h`). Ten generator/rule source nodes and seven direct host-generator
inputs match the pinned archives. In particular, zlib 1.3.2's `inffixed.h`
maintenance generator is `inftrees.c` under `MAKEFIXED`, not `infback.c`.
Research JSON SHA-256:
`fddc19b7a11b93d8a47f095478d8f81f339fd5cba20e61440b8ee17dc845a1b3`;
parent binding-review JSON SHA-256:
`d38f49c53704b4e173a0aa4e855791a8cd20de195bc15e0f6384a2322650c6f4`.
These checks do not independently approve legal classifications, prove all
provenance, or execute any generator. The research report makes no regeneration
claim. Upstream-shipped pre-generated inputs must not be described as generated
by the observed normal build merely because maintenance generators exist.

The next Linux-only recipe replays the retained FFmpeg `ops_asmgen` host tool
in an isolated `media-generator-replay/` directory, once with `-lookup` and once
with `-ops`, retaining stdout, stderr/command logs and digests. Both outputs must
match the configured `ops_lookup.gen.c` / `ops_neon.gen.S` inputs byte-for-byte;
the generator, source, rule and baseline outputs must remain unchanged. Failure,
timeout, drift or a pre-existing replay directory prevents staging. This is a
two-mode host-tool replay, not a rebuild of the generator, configure replay,
maintenance-table regeneration, complete source closure or license approval.
The baseline and modified CRC experiments and all approval fields stay unchanged.
Windows synthetic tests cover the replay and build failure gate; real Linux
execution remains a separate CI requirement.

The first replay candidate, source CI `42751634740` (`7bfe613`, job
`129616365080`), failed before native compilation: the test's combined mock
contexts exceeded Python 3.12's static block nesting limit. No generator replay
or accepted diagnostic artifact resulted. Retained job log SHA-256:
`219261fbdf894b44e1ea1fd88b77ef68db58955a474f3c88ee3c782f584da129`.
The fixture now uses `contextlib.ExitStack` for dynamic mock registration and
unchanged LIFO cleanup; all 32 OpenTUI synthetic tests pass on local Python 3.12
and 3.13. Regular CI `42751608247` passed, but does not establish Linux generator
acceptance. A new source CI run is required; no runtime or approval gate is relaxed.

The corrected source CI `42752976094` (`2703a91`, job `129620707357`) and regular
CI `42752955897` succeeded. Independent review of artifact `13735246855`
(536715100 bytes) matched API ZIP SHA-256
`db3717bf784f587cba02ab1df63bc49aecd0eb0c9cc6012590aa9b5627570a3f`.
The 40288-file manifest is closed. Both isolated host-tool modes reproduced their
baseline generated bytes: lookup 112125 bytes, SHA-256
`a905ef363cdbf6f64607329b6ef2deca2253d26bb104688e5992e05e41530fb6`;
NEON 292164 bytes, SHA-256
`70c949fa195bdedf3f9b00f463ba3bb985d942e8d8181bb9b932c06c784a1238`.
The retained generator/source/rule and command/log bindings were independently
checked. All 345 media object-command bindings, 755 non-system dependencies,
446 original link inputs, byte-identical original relink, single-CRC replacement
(2304 cases / 6912 calls), 14 generated builtin snapshots, fixed source notices
and Linux runtime gates also passed. Job log SHA-256:
`042eb7008c010891f1af95664fde221c691ec1312b4f31a3f8fb6b5bb2afc3f9`;
independent verification log SHA-256:
`8bbb0a7cb3cb75fd105dd4dde7bff2fbff000e9dffb5ae6402f247ab1f607d41`.
This accepts the bounded two-mode replay only, not a generator rebuild, complete
preprocessing/system-header inputs, full modified FFmpeg replacement, LGPL
compliance or Android acceptance. All approval fields remain false.

The next bounded diagnostic recompiles the standalone `ops_asmgen` host tool
in `media-generator-rebuild/`, without replacing the retained baseline tool,
media objects or staged OpenTUI. Only the fixed main source and its recorded
non-system dependency closure are copied. The command is constructed from the
reviewed GCC flags; compiler-log text is never executed. Host GCC path, version
and executable digest are recorded; inherited include/compiler/library injection
variables are removed. Preprocessing emits both a full `-MD` dependency file
(including system headers) and the actual `.i` translation unit subsequently
compiled. Observed system headers must resolve under `/usr` and are copied with
hashes; the copied non-system dependency set must match the retained set.
The rebuilt tool must produce both byte-identical generated outputs. Baseline
inputs, compiler, observed headers, copies and preprocessed bytes are guarded
against mutation. Failure, timeout, drift or pre-existing output prevents staging.
This is not a toolchain/source closure or a byte-identical generator-ELF claim;
it does not regenerate configure or upstream maintenance tables, approve
distribution/relinking, or add any experimental ELF to the APK. Synthetic Windows
regressions are separate from the required Linux CI build and external review.

Source CI `42756591596` (`d101ece`, job `129632296087`) and regular CI
`42756568100` succeeded. Independent review of artifact `13736437847`
(537051597 bytes) matched API ZIP SHA-256
`f50471ed74a24f169b02d56d135af350280d40e3a8665b0b7d357d5eef5a8452`.
The complete 40389-file manifest is closed. The isolated generator rebuild binds
14 copied source inputs, 75 observed system-header snapshots and 101 retained
diagnostic files. GCC is Ubuntu 13.3.0-6ubuntu2~24.04.1, executable SHA-256
`a20520ee21543f243d40636a9181a142c45ecd989de31ab86b99a8ea5ada870d`.
The actual compiled `.i` has 262236 bytes, SHA-256
`dc0f80343ffa307acecc5bb5e27499a07d409232430c04d40a9ef11b37428a04`.
Both regenerated outputs match the baseline and earlier retained-tool replay
byte-for-byte. Independent checks bind the full observed dependency sets,
constructed preprocessing/compile/link/run argv, logs and AArch64 ELF identity.
Generator rebuild review JSON SHA-256:
`4d226d12e72d16cea730f73f98e5eec16f15b153494919e85c7707edda8f85a1`.
Existing 345 object-command / 755 non-system dependency bindings, 446-input
original relink, single-CRC replacement, source-notice candidates and Linux
PTY/TUI/runtime gates also passed. Job log SHA-256:
`637dafbd8fb1862c2879caa254e8d9e35b5fb0a3480bef7957c4b2c3a8d83b0e`;
complete independent verification log SHA-256:
`9a74d69405034b675b5acbb4dd8aca6daed84a9bedc4b689429499b029c8c6e2`.
This proves only the bounded standalone-generator rebuild and two output byte
matches. It does not prove generator ELF reproducibility, complete toolchain
inputs, preprocessing of all media objects, other generators, complete source,
modified-library replacement or license/Android approval. No experimental ELF
has been added to the APK or installed on a device.

The next diagnostic independently samples preprocessing for all recorded media
translation units after the baseline build. It constructs a direct invocation
of the fixed Zig compiler, verifies the retained wrapper and source/object
hashes, permits only reviewed compiler flags and include paths inside the media
cache, and never executes log text. Original compile/dependency output flags
are removed; `-E -MD` emits isolated C `.i` / assembly `.s` output and a full
observed dependency file. Each observed dependency must resolve inside the
media cache or fixed Zig tool tree and is copied to a content-addressed snapshot.
Commands, logs, output hashes and per-unit dependency mappings are retained;
baseline objects, sources, wrapper and observed inputs must remain unchanged.
Failure, timeout, unapproved options or external paths prevent staging. This
is explicitly post-build sampling, not capture of the original compiler's
complete inputs, reconstruction of the original objects, toolchain closure,
complete corresponding source or license/Android approval. Generator and
single-object relink diagnostics remain separate and all approvals remain false.

Source CI `42759758740` (`31aab46`, job `129642428678`) and regular CI
`42759727310` succeeded. Independent review of artifact `13737997725`
(557139538 bytes) matched API ZIP SHA-256
`18450178b3b6ca97fef0587e5fd90e4eac22bb7d097db5670f58c72d22d805fb`.
The complete 42369-file manifest is closed. All 345 post-build preprocessing
samples bind output bytes, constructed commands, logs and dependency files to
755 media dependency paths and 192 fixed-Zig header paths, represented by 945
distinct content snapshots. Tool-header snapshots match the retained official
Zig library-resource manifest; configured `src/` aliases are bound to identical
retained source bytes. These counts describe paths/content, not separate compiler
executions or unique licenses. Independent preprocessing review JSON SHA-256:
`03274271dca78712af5ff5d894bac14d46a31148cb1a01acf861e24fd9f318d9`.
The standalone generator rebuild and both output matches also passed again;
its review JSON SHA-256:
`0edd598d48b36e37d7d60cdba98e944e6ce2eef034c6c327a71c919b7bcff9a8`.
Existing object-command/notice candidates, original retained-input relink,
single-CRC replacement and Linux runtime/PTY/TUI gates passed. Job log SHA-256:
`fc36371b0f3e571b0c554227caf9063d5873df2ceae63f435a54a9df0ac049c2`;
complete independent verification log SHA-256:
`4ac3360f670f0d046477ac9d8b3deb958c7bc2c20189157386b53a2f701207eb`.
This acceptance remains post-build sampling only: it does not establish original
compile-time input capture, original-object reconstruction, complete modified
media replacement, complete corresponding source or legal/Android approval.

Observed Zig-header notice research v2 (2026-11-10) covers exactly those 192
paths: 27 compiler headers, 34 Linux UAPI headers and 131 glibc headers. Parent
review independently compared every observed header's retained preprocessing
snapshot bytes with its Zig resource archive member in both artifacts
`13737997725` and `13740806776`, checked the reported notice lines/byte ranges,
and verified 210 selected resource members (192 headers plus 18 license files).
All 945 content-snapshot payload paths are present; v1's contrary statement was
a ZIP-prefix error and is withdrawn, with v1 preserved as superseded evidence.
V2 report SHA-256:
`18da5b8b9ed5adfb8d3c6f209312888e740f8f54501eae92f5bcbc6dcdbd3e43`;
parent byte/citation review SHA-256:
`c1d03b59752fe3e2a24544aeafaca8fc53f1bda8e60d2362d0a18ebcdc18bbcc`.

Candidate grants remain file-specific: 26 compiler headers have embedded
Apache-2.0 WITH LLVM-exception SPDX notices; `arm_neon.h` has an unsigned MIT-style
grant, not that SPDX identifier. Among UAPI headers, 25 have GPL-2.0 WITH
Linux-syscall-note identifiers and `linux/sockios.h` has GPL-2.0+; eight lack
embedded grant markers. Among glibc headers, 111 have LGPL-2.1-or-later notices,
one has a Regents BSD-style notice, and 19 lack embedded grant markers. The 28
unresolved paths still need upstream provenance/applicability review; absence of
an embedded marker does not establish absence of a license. `sys/ttydefaults.h`
must retain its own complete copyright/USL paragraph and numbered clauses;
glibc `LICENSES` has different copyright text and an explicit removed-clause
entry and is not a verbatim substitute.

The 28 unresolved header paths now have a completed provenance research pass
(retained outside the repository under the bounded 0.17.0 source archive).
Parent recomputation confirms all 28 retained extract SHA-256 values, and the
`arm_neon.h` exact-identity claim: the 0.17.0 tarball copy (SHA-256
`ed8fc4135aef7c5af5f30ca3715d96ee9ad5a2bc97f558214fadda5704742b26`) is
byte-identical to the Zig sync commit `520af6966041b891442ab34ac13b0f6861a09fc0`
copy. Mapping summary: one clang build-time TableGen product (unsigned
MIT-style notice traced to `NeonEmitter.cpp`'s embedded string; the .td files
are Apache-2.0 WITH LLVM-exception but do not claim to cover generated
output); eight Linux UAPI paths (six one-line `cmd_wrap` redirectors with
rule-text matches, `linux/errno.h` a verbatim upstream copy, `unistd_64.h`
consistent with Linux v7.0 `headers_install` output with the
`_UAPI_ASM_`→`_ASM_` guard rewrite); sixteen glibc copies that are
byte-identical across 2.42/2.43/2.44 (so tags cannot pin the sync version);
two glibc build-time `stubs` outputs with mechanism evidence but no
upstream bytes; and `bits/cloexec.h` identified as a Zig-authored compat shim
added by commit `23aa045ef456`, not an upstream glibc file (no `*cloexec*`
header exists anywhere in the upstream tree). A parent note was corrected:
`features.h` does not pin 2.43 in-file; tree-level binding comes from the 2.44
sync commit. Parent review SHA-256:
`535268032b2f6b68aebd3e10918f00156cbe4691a26b71b3974a5488e9f00f61`.

The 25-pinned-declaration collector commit `77a2a89` now also has its own
independent nine-gate acceptance for run `42802742226`. Artifact `13759215670`
is 689785005 bytes; its API/downloaded ZIP SHA-256 is
`d5e6e05b16a80ccdbe5c2ff0971b69ecc2d76dfe7440d68814c9ea44f8ccf0f7`. The
archive's `native-source-review.json` carries exactly 25 declaration files
(22 Bun + 3 WebKit) matching the current pinned set, and no Bun archive yet
(that capability landed in the next commit). Fresh source-rule relink, swscale
regeneration (`swscaleMacrosOutputMatched`), fresh TUI with replacement
SHA-256 `a188b86ebacdff9ec6371e6dfe46b52f90d0186fe771274010017d1953c04168`
and 15/14/14/23 semantic rejection groups all pass. Nine-gate parent
acceptance index SHA-256:
`78f45ea14dad995edfb8e3836033dcffa55f151a453ce8e95a6a854456c65843`;
job `129784131962` log SHA-256:
`a79df3c30b92e4ba4aa522fdc60985753a96d57dee9046c927cb5b170ac3a8dc`.

Honest boundaries: trimmed comparisons are not byte identity except the
`arm_neon.h` case; `headers_install`, glibc install and clang TableGen
generation were not reproduced on Linux; missing embedded notices still do not
establish license absence, and provenance equality does not establish license
applicability. Per-file license attribution and notice obligations remain open;
all approvals remain false.

Full Apache/LLVM-exception text is physically retained in the WASI/libc++-family
license files; v1's blanket missing-full-text statement is withdrawn. Physical
co-location alone does not bind those files to a particular observed header.
Parent full-byte inventory/heading review SHA-256:
`1e120ef558a960d4eb4f2b902475f11d8958d691a8bfe5703a92522dc779193d`.
The 18-file inventory's lack of GPL/LGPL/syscall-note full-text heading matches
is only a bounded observation, not proof of absence from all archive text.
These are notice candidates and evidence bindings, not formal notices, original
compile-input provenance, complete corresponding source or distribution,
relinking or Android approval; every approval field remains false.

The fixed official Zig 0.17.0 source archive (23049960 bytes, SHA-256
`b6c7f1728f043700d6529bac980800792f824256a9d2f1839b3d62beed0b8abd`)
was separately fetched with TLS verification and matched the official download
index entry. Retained index SHA-256:
`81080b1daf59c569e04ebd90c3a9d2f87bbfd25716be61042c9602d3dbd44a3b`.
All 192 observed tool headers match the corresponding official source members.
Across the entire 19503-file retained resource set, 19415 files match and 88
test-source files differ: their binary-package resource copies are empty while
the official source copies are nonempty. The review records every difference;
source and binary resource trees must not be described as wholly identical.
All 88 differing paths end in `test.zig`; source `build.zig` lines 158-187
declare installation of `lib/` with `blank_extensions` containing `test.zig`
at lines 183-185. This is a matching source-side rule, not evidence that the
official package was produced by an independently executed rebuild. Rule/citation
review SHA-256:
`1520967b0307ff796c967e4b20cc8e47df055274e131f54926895361d96a239b`.
Parent source/resource review JSON SHA-256:
`91f8c953a34bb2ecef6b14ff2aba00a141589d38090af8e0dbc313ea2b8d82cf`.
The source `CMakeLists.txt` lines 136-138 request LLVM/Clang 22, while
`cmake/Findllvm.cmake` lines 36-46 check LLVM 22.x. These declarations neither
identify the official binary's exact compiler nor make this Zig toolchain
interchangeable with Bun's separately declared LLVM 23 toolchain. The source
glibc README documents customized multi-version headers and start files, and
the Linux-header update tool documents installation/architecture regrouping.
Retaining those rules does not prove their execution or exact upstream
glibc/kernel/LLVM revisions. No compiler was rebuilt or executed locally and
source-build, full toolchain, per-file license and corresponding-source closure
remain incomplete.

The separately retained official Zig 0.17.0 bootstrap source archive is
57030388 bytes, SHA-256
`1e9e9b8e3c753b35dfb1d9ea48f097579fadbd3e5c1e724ab3fc5bce05477b71`,
matching the same retained official download index. All 21913 regular files in
its `zig/` subtree match the standalone source archive by path, size and SHA-256.
Archive-only parent review SHA-256:
`a631d8a5260a9076c4a952d1d5c0b0129a21e48e545552928f659c5bc5bb3584`.
The bootstrap also retains Clang/LLVM/LLD sources, build rules, selected license
files and zlib 1.3.1/zstd 1.5.2 declarations; its zlib is separate from the media
experiment's zlib 1.3.2. Bootstrap `README.md` line 11 claims LLVM/LLD/Clang
21.1.0, but `llvm/CMakeLists.txt` line 19 includes
`cmake/Modules/LLVMVersion.cmake`, whose lines 3-10 default to LLVM 22.1.8.
This declaration conflict is preserved, not resolved by trusting the README or
by asserting the official binary's producer. No bootstrap/CMake build was run;
upstream LLVM revisions/patches, generated headers, compiler reproduction and
complete toolchain/license/corresponding-source closure remain unverified.

The next bounded diagnostic compiles every retained post-build `.i` / `.s`
sample with the same fixed Zig target and reviewed code-generation flags into
separate AArch64 relocatable objects. Preprocessor include/definition options
are not re-applied; C language-standard flags are retained. It records object
hashes and baseline byte comparisons without requiring equality. All media
linker positions must match the sampled object set; final linking replaces the
generic sampled CRC object with the separately built instrumented CRC object,
uses newly compiled objects for all other media inputs, and retains non-media
inputs. The recompiled uninstrumented CRC object is retained but is not the
final link input. Commands, maps, archive extraction, ABI and 2304-case / 6912-call
CRC execution logs remain isolated. The baseline library, retained inputs and
sample snapshots are mutation-guarded; failures/timeouts prevent staging.
This is not a complete modified-source rebuild: the instrumented CRC follows
its earlier separate configured-tree build, while the other inputs come from
post-build preprocessing samples. It does not establish original object byte
identity, full live-code coverage, decoder/TUI behavior of the replacement,
complete corresponding source, toolchain closure or legal/Android approval.
The replacement library is never staged in the APK.

The first all-media attempt, CI `42763817879` (`1fe64da`), failed before
compiling its first replacement object: Zig 0.17 rejects `-x cpp-output` with
`language not recognized`. Regular CI `42763796545` succeeded. Failed-log
artifact `13739018684` (1624699 bytes) matches API SHA-256
`3eaf163c72b50958197f1df428e00f4900f5bbab42e9b88953ec022cdfb9a22a`;
job log SHA-256:
`dcaffad92e116029f1d528d9ae9f17d26329ab20cc4691ad94cba0961730c846`.
This is not a successful replacement artifact. The corrected diagnostic uses
explicit C language for retained `.i` text, not unsupported `cpp-output`.
Consequently this performs a second preprocessing pass and must not be described
as direct frontend consumption of preprocessed C. Only numeric line markers
and pragmas are allowed as directives; include/define/other directives fail
closed. No original include paths or macro definitions are supplied. Built-in
macro behavior and this extra pass remain differences from original compilation;
object equality and original-input equivalence are not assumed. Linux execution
and independent artifact review are still required for the corrected attempt.

Corrected source CI `42765618304` (`fa8962a`, job `129661311669`) and regular
CI `42765593273` succeeded. Independent review of artifact `13740806776`
(569629477 bytes) matched API ZIP SHA-256
`743be72f9e9b07eb7efe4846eb6027fc378e37b02dee7b9c3b2426b8c1ea77fc`.
The complete 43067-file manifest is closed. All 345 sampled media objects were
recompiled as AArch64 relocatables; none is byte-identical to its baseline.
All 345 final media linker positions are replaced (344 sampled recompilations
plus the separately instrumented CRC). Independent review binds 698 diagnostic
files, exact compile/link/probe commands, linker reports and ABI/CRC markers.
The replacement library and CRC executable pass AArch64, 16K PT_LOAD and
glibc <=2.39 checks; NEEDED remains libm/libc/libpthread/libdl. The CI logs record
2304 reference cases and 6912 instrumented calls against the replacement.
Media-object relink review JSON SHA-256:
`63d84743bc57176ba9405fb2c922a6d5aa69fbc33c9f1a98bd5928f962d472b7`.
Preprocessing and standalone-generator rebuild were independently rechecked;
review JSON SHA-256s respectively:
`c8defa0a8e66c7303a80e5245d56119ac3b2aaee1c531947be5e9d412569a9e1`,
`ca7f0549ba138e6c66d2fabc6c5245c55800849036c48de0a155235987f4fbd8`.
Job log SHA-256:
`7673306a8a282819ce9fcbacf3a3d9141f072ae60b8560bd5f673e7dffb44623`;
complete independent verification log SHA-256:
`4ad8d43726dee9d179771a43170208118ecf31e06e279801374dddebe39effbe`.
This accepts only the bounded sampled-object replacement and ABI/CRC diagnostic.
The retained baseline TUI gate does not validate this replacement library's TUI
or decoder behavior. Original compilation equivalence, complete modified-source
rebuild, full corresponding source, notices, toolchain and Android/legal approval
remain unproven. No replacement library was staged in the APK or on a device.

The pristine media source-tree check is now exhaustive over retained regular
files for that accepted artifact, rather than the earlier representative-file
sample. The FFmpeg 9.0.2 official archive SHA-256
`8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e`
contains 10399 regular files; zlib 1.3.2 archive SHA-256
`bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16`
contains 254. Both complete path sets, per-file sizes and SHA-256s match the
retained pristine `sources/` trees in artifact `13740806776`, with no extra,
missing or changed regular files. The official archives have only directories
and regular files. Parent review JSON SHA-256:
`80565ad71b62ed6667646abc9bec946d65abc50fda128ebabb26ca6ec6e227d3`.
This check does not compare modes/timestamps, independently verify upstream
archive signatures, rebuild source rules, establish modified/configured-tree
provenance or close toolchain and complete corresponding-source obligations.

The next Linux diagnostic tests the replacement library's own terminal rendering
in a separate `media-tui/` tree. Other native inputs are copied unchanged; only
OpenTUI uses replacement bytes under the original filename required by the
already-built CLI. This is explicitly a lookup alias: the byte-preserved lookup
manifest is not a valid release digest manifest. The report binds original and
replacement digests, process maps, raw terminal output, command and isolated
HOME/BUN_TMPDIR contents. The real PTY probe requires the alias mapping, staged
runtime and rendered OpenCode content. Baseline native inputs, CLI and diagnostic
copies must remain unchanged; no extracted ELF is allowed in isolated data
directories. Failures/timeouts do not create an accepted review. This experiment
does not change the baseline native directory, rebuild the compiled CLI, approve
decoder coverage or provide a content-addressed release payload/Android approval.

The replacement-library TUI diagnostic is now independently accepted for native
CI run `42772789165`, commit
`8f3be3f0514fad1a0dc48974b144ac621820b6f0`, artifact `13743357750`
(584975016 bytes; ZIP SHA-256
`e4b38c4becd00b93075dabc58d6dd18ac941ff43d53bffe0a3a11b31301732e2`).
Five archive-only parent gates independently rechecked the complete 43078-file
manifest, baseline native evidence, all 345 media substitutions, preprocessing,
standalone media generators and the replacement TUI. The TUI evidence binds four
native copies, ten diagnostic files, 365 rendered terminal bytes, the exact
replacement/staged-runtime map paths and an empty runtime-ELF extraction result.
The replacement SHA-256 is
`f004627eeb3bb58e763ccd9f5b22237eff47cfc0db69a6fc7e8b53014fbd27fe`.
Independent TUI review SHA-256:
`b1bc5852d8c87502f2c770d71019c8368cf9c60fb1dfd57ac1216ad13a1a83cd`;
object-relink, preprocessing and generator-rebuild review SHA-256s respectively:
`bd994d9c7fbe390b42b2bf094696a737f11d853875062b405b2ae8ea7db8848c`,
`d3be8c985c04008782a1756115652d11f837a39063b2e7e9baa6ae7ccbec3784`,
`b84658b1b58002c77555ed4639cf5be39ffe1744a3e00ad50f80edbfc7634bf8`.
The retained job `129684258391` log SHA-256 is
`93d58412fc83215af31c26bdee18d0a67d3fe392919a8f82ca807331f314395a`;
regular CI `42772733568` also succeeded at the exact same commit. This closes
only the Linux replacement-library PTY/map/render experiment, not decoder
coverage, original-object equivalence, a complete modified-source rebuild,
corresponding-source/relinking approval, valid release packaging or Android
application-domain admission. Formal APK inputs and device data remain unchanged.

The isolated zlib maintenance-generator diagnostic copies the pristine zlib
tree, then rebuilds `crc32.c` with `MAKECRCH` and `inftrees.c` / `zutil.c` with
`MAKEFIXED`. Host GCC performs full-dependency preprocessing and compiles the
retained actual `.i` files; the diagnostic retains observed `/usr` headers,
source inputs, object/executable bytes and all command/log bindings. Generated
`crc32.h` and `inffixed.h` must match pristine upstream copies byte-for-byte.
Original/copied source files, actual `.i`, observed system inputs and the GCC
executable are mutation-guarded. Failures, dependency escapes, missing main
dependencies, drift and timeouts do not create an accepted review. No result
replaces configured media inputs or APK payloads. This covers only these two
maintenance modes; `trees.h`, swscale maintenance generators, complete compiler
and sysroot sources, original build provenance and legal/Android approval remain
outside this diagnostic and require separate evidence.

The follow-up hardening also checks ELF64 little-endian version 1, AArch64
machine identity, ET_REL for compiled objects and ET_EXEC/ET_DYN for generators
before running them. Objects and generator executables are mutation-guarded
through the remainder of the diagnostic. Synthetic regressions reject wrong
machine/type/version fields and link/run-time mutation; these local mocked tests
do not execute GCC or establish a successful new Linux build.

The exact hardened commit `21c2ad6b7cd972fec2f3f0e226efc2511049f326`
subsequently passed native run `42786104011` and regular CI `42786068255`.
Job `129727581798` retains the actual two-output generator success marker and
replacement-TUI markers; its 1704404-byte log SHA-256 is
`07cc4fe79629f0848cb70babfc3a2579f294b55041461f94039ce44e3607e693`.
The API records artifact `13750637145`, 587094175 bytes, digest
`30233cfe514a68ca0ed4eafd15c6a1c8d9805379a80866941acaca249be80060`.
That specific ZIP has not been downloaded or independently accepted. Its CI
success is not substituted for the earlier artifact's archive-only acceptance;
the later `0489a01` artifact below includes the hardening and has its own review.

Independent acceptance of the actual zlib-generator artifact is complete for
native run `42776837614`, commit
`7ac5ff5169696ec2e9298511527cff9c6cea258b`, artifact `13744779170`
(587100121 bytes; ZIP SHA-256
`5273ed3f4fc94727c1c16251a265c4c48cf763c6812bd077b2f2dc781dfb5902`).
All six archive-only gates passed, including the closed 43410-file manifest,
baseline native evidence, sampled-media relink, preprocessing, media-generator
rebuild, replacement TUI and isolated zlib maintenance rebuild. The zlib review
binds all 254 copied source files, three actual GCC-preprocessed compilation
units, 53 observed system headers and 331 diagnostic files. Both generated
headers match fixed pristine upstream bytes; AArch64 object/generator identities,
exact commands, dependency paths, emitted input/output bytes and log bindings
were independently rechecked without executing downloaded code locally.
Zlib review SHA-256:
`599b27ccac98532d0ee4fbd373e129c34203e2a2c709f99a530c9d670bbb545f`.
Object-relink, preprocessing, media-generator and replacement-TUI review
SHA-256s respectively:
`cd59d1c375203687db6488d5aaefd4924183fb2cb8e52512ccb90ce0cd362fc9`,
`5d69383d77882186b6f62940d508d12c42968ea02f7d9ccd2415c06639b8bdf9`,
`84cb1c67182f99d2ceec3725cc3f53021874162674211f6861a242bcbd0100e4`,
`d725b3d6a8ddf6c066c05d80d29fecdeac3bc40b4a070bdb933fdeaa836f47e3`.
Job `129697214357` log SHA-256:
`e4f8f67c3536fbc292a83cc01a159a36e4ccab7ec569cffd3b605bd91b9ac825`;
regular CI `42776795592` succeeded at the exact same commit. This accepted run
predates the subsequent build-time ELF/mutation hardening; its independent
archive verifier separately enforced AArch64 object/generator checks. Acceptance
covers MAKECRCH/MAKEFIXED only, not `trees.h`, swscale maintenance generators,
original build/toolchain provenance, a complete modified-source rebuild, full
corresponding source or redistribution/relinking/Android approval. Formal APK
inputs, device data and existing Ubuntu instances remain unchanged.

The follow-up tree-header diagnostic adds an explicitly non-upstream standalone
entry point: `trees-generator.c` includes the unchanged `trees.c` in the same
translation unit and calls its internal `tr_static_init()` with `GEN_TREES_H`
defined. Host GCC records actual preprocessing/dependencies before compiling the
retained `.i`, linking and running in a fresh `gentrees/` working directory.
The harness itself, its upstream `trees.c` dependency and executable are bound
and mutation-guarded; generated `trees.h` must match the pristine upstream bytes.
Synthetic tests reject missing tree dependencies, harness mutation and missing
or changed output. This is a proposed maintenance harness, not proof that zlib's
original build used that entry point; successful regeneration awaits native CI.
The prior accepted two-mode artifacts and their recorded counts remain unchanged.
Previously compared generated headers remain mutation-guarded until all modes
finish; a later generator changing an earlier output rejects the entire review.

The tree-header harness now has independent native-artifact acceptance at run
`42792765746`, commit `bd34724498ff7ee705e265f60635971ff19c3e8f` (artifact
identity and other gate boundaries below). All three generated headers match
pristine upstream; `trees.h` is 8472 bytes, SHA-256
`bb0a9d3ca88ee00c81adb7c636e73b97085f6ef1b52d6d58edbe2b6dc3adeb4d`.
The archive-only gate binds four actual preprocessed compilation units, the
explicit same-TU harness and `trees.c` dependency, 254 copied source files,
53 system headers, executable/object identities, commands and 341 diagnostic
files. Zlib review SHA-256:
`99159bb1284cfa12fcaeae55dd357d1bfd730294c0fdbbe942fddcb0a77c9696`.
Fifteen self-consistent archive mutation cases reject altered approvals,
ELF identity, command/dependency/source/output bindings and the harness itself;
retained rejection log SHA-256:
`8b579f70be3587fc65e289c6f706a249ec112147c46ee7d41e60b1ee390806cd`.
This run predates the later end-of-all-modes generated-header mutation guard;
the independent verifier checks every retained generated output. It proves this
diagnostic regeneration, not the invocation used to produce upstream releases
or complete toolchain/corresponding-source/legal approval.

Read-only remaining-generator research identifies swscale `uops_macros.h` as
the output of the configured `libswscale/tests/sws_ops -macros` test program,
not a standalone zlib-style generator. `libswscale/output.c` is handwritten
source with compile-time macro instantiation, not a missing generated C file.
Tablegen source-rule classification depends on the recorded disabled
`CONFIG_HARDCODED_TABLES`; this does not establish regeneration of other configs.
Research JSON SHA-256:
`e6da977ba986fa43727056cb119be4f82cb8c10d98ed04b3e567294b6b5da700`.
Parent review rechecked 21 cited file hashes and 18 fixed-archive source-file
matches, plus the direct tree initializer call and actual swscale option handler;
parent binding SHA-256:
`6e0fe8eafe2aa06d043148aafa55ad3ed71248b8c94b814c59b8151c007b1ac7`.
The research proposes rules only; no swscale macro regeneration, full toolchain,
corresponding-source, relinking or distribution approval follows.

The configured source-rule diagnostic now also builds
`libswscale/tests/sws_ops` in the copied media tree and runs only `-macros`
from a new `swscale-generator-rebuild/` working directory. Explicit test-link
flags request 16K alignment; the existing AArch64/glibc ELF gate applies before
execution, and stdout must equal the pristine `uops_macros.h` byte-for-byte.
Selected media objects, recorded dependencies and pristine sources are guarded
through this test build; the generator itself is guarded through execution.
This adds test-program build/run evidence, not original preprocessing capture or
full toolchain/source closure. Synthetic failure, timeout, output drift, ELF and
mutation cases pass locally; real macro regeneration still awaits native CI.
Additional rejection cases cover generator ELF type/version/machine, a test
build changing a selected installed/build object or recorded configuration
dependency, and TUI subprocess mutation of its copied lookup manifest.

The next independent diagnostic starts from fresh copies of the fixed media
archives, their complete byte-matched pristine source trees and the retained
patched build script. It modifies only the copied pinned CRC translation unit,
then runs that script's configure/make rules for all selected FFmpeg/zlib objects
without copying any baseline build/prefix, generated headers, objects or sampled
preprocessor outputs. Gates require the exact selected object set, recorded
compiler sources/dependencies, the instrumented CRC source hash, changed CRC
object and AArch64 relocatable objects. Original source/script/archive and
baseline objects remain mutation-guarded. Local synthetic tests exercise success,
archive/source drift, malformed objects, dependency gaps, mutation, failure and
timeout handling; only native CI can establish an actual source-rule rebuild.
The result does not itself relink OpenTUI, execute decoders/TUI, capture all
original preprocessing inputs or establish full corresponding-source/toolchain,
relinking, legal or Android approval; no formal APK inputs are replaced.
Evidence enumeration follows internal directory aliases with explicit
escape/cycle rejection, matching the dereferenced upload manifest. In particular,
the FFmpeg build's `src/` alias must not silently omit its source-file evidence.
Synthetic directory-alias/cycle tests cover this enumeration separately from
actual source-rule execution.

2026-11-10 independent source-rule artifact acceptance: native run
`42788737498`, commit `0489a010a7c29b039a37302586a5454e08900ce8`, succeeded.
Artifact `13753120400` contains 663224717 bytes with API-verified ZIP SHA-256
`61c1aec87e8620bb32be3ec2a5f702f9dd358149e01c931c3ff2e687932ecf8a`.
All six prior archive gates pass again: the complete manifest closes over
65729 files, final-link evidence retains 446 inputs, post-build preprocessing
binds 345 units / 945 snapshots / 755 media dependencies / 192 tool headers,
the sampled-object replacement passes ABI/CRC and isolated TUI mapping/render
bindings, and the two-mode zlib generator outputs still match. These prior
sampled-object/TUI results do not describe the fresh source-rule library.
The seventh independent gate separately checks all 10399 FFmpeg and 254 zlib
pristine source files against the fixed official archives, the sole copied CRC
source modification, all 345 fresh build/installed object pairs, source-rule
commands, exact main-source paths, recorded dependencies, compiler wrapper and
unchanged media configuration. Its 22318-file diagnostic review SHA-256 is
`803623be051f120eae57746c79a34a1f45ea8983915ba91151884ffafdefb243`.
The exact job `129736451311` log has SHA-256
`c7068d2ac098293b00416a7bbd0ca7b50e764bf7b4ff38342985ce4b67ca88c7`.
Parent semantic mutation tests reject twelve self-consistent manifest/evidence
changes: approval, omitted inventory entry, changed source/wrapper, object
machine/type/version, command/main-source binding, dependency target/escape and
configuration drift. Python 3.12 and 3.13 both pass, with identical retained log
SHA-256 `4844463f22e4a6e5025583bfea6aca7ac7dd6effb03b34d63ab7f6808b74f592`.
This artifact predates fresh-source final relinking, its TUI gate, `trees.h`
maintenance regeneration and swscale macro regeneration. No such results, all
original preprocessing inputs, full toolchain/corresponding source, legal
relinking/distribution approval or Android admission are inferred. All four
approval flags remain false; formal APK inputs and device instances are unchanged.

The subsequent isolated link diagnostic substitutes every fresh source-rule
media object into the retained OpenTUI final-link command while preserving all
non-media inputs. It requires exact source-review/input hashes, full media-set
coverage, fixed Zig archive identity, map/extraction evidence, unchanged NEEDED,
the OpenTUI ABI marker and the 2304-case/6912-call instrumented CRC probes.
The fresh library and probe pass the existing AArch64/16K/glibc <=2.39 ELF gate;
all source-rule and retained inputs remain mutation-guarded. Synthetic tests
cover link failures/timeouts, object-set/input drift, missing map/ABI/CRC evidence
and changed dependencies. Actual execution still requires native CI; this is
not TUI/decoder coverage, original object equivalence, a full toolchain/source
closure, LGPL relinking approval or Android admission. No baseline is replaced.
The fresh library must differ from the retained baseline. Baseline library,
fresh library and CRC probe bytes are guarded against mutation through probe
completion; synthetic cases reject unchanged replacement bytes and mutation of
each executable/library as well as retained inputs.
Complete object substitution is checked against linker argv, not inferred from
map liveness: garbage collection may discard entire unused media objects. The
map must retain the explicitly exercised instrumented CRC object; no all-object
or all-section liveness claim follows.
A focused synthetic case substitutes two media objects while deliberately
omitting the unused one from the map; CRC/map/ABI execution evidence still must
pass. The first link run `42790552909` at `6b439e4` failed at the superseded
all-object map assertion, not at an accepted ABI/CRC result. Its job
`129742564402` log is retained (SHA-256
`cfd883e646861e495905aeaca7d096f48e7a460039886162f7bb450f3671ced0`);
the corrected gate requires a new native run and independent archive review.

The corrected source-rule final-link diagnostic now passes independent
acceptance for native run `42792765746`, exact commit
`bd34724498ff7ee705e265f60635971ff19c3e8f`. Artifact `13754410711` is
673370304 bytes; its downloaded ZIP matches API SHA-256
`115d29df18642a323d352d38e60d9c6b0ee7ae95a05be900a915978a7bc3bc49`.
All eight archive gates pass, including a closed 65748-file full manifest,
the prior sampled-object diagnostics and three-mode zlib regeneration. The
fresh source-rule gate separately binds 10399 FFmpeg / 254 zlib source files,
345 fresh objects and 22318 diagnostic files (review SHA-256
`cfa05c4daaaa74e77622cc2dc454bfbebf1e25506cb7d1e6938877849d33d9f1`).
The new link gate reconstructs all 446 input positions, replaces every one of
the 345 selected media objects with its fresh source-rule counterpart, preserves
the retained non-media inputs, and validates CRC map retention plus archived
ABI/2304-case/6912-call execution evidence. Replacement library SHA-256 is
`8dd0abe94ee7e47370680d2b06e70a7e79ade56affb92b5c1c74888dc0c15dc0`;
the library/probe pass the AArch64/16K/glibc <=2.39 gate and unchanged NEEDED.
Final-link independent review SHA-256:
`0686db5bb50bb15629ef1f2ad86cc129510679b6f6878d855448fb686de8064a`.
Fourteen self-consistent semantic mutations reject approval/review/inventory,
object/input counts, argv/log/map/extraction, ABI/CRC markers and executable
machine drift; rejection log SHA-256:
`dd1ccb63b9f66fe7ad63d2efc810d448ab00f326da36527418844f6060738590`.
Exact job `129750136113` log SHA-256:
`0010e2d28410bdafdcdf81b26230a9fa63f3fc6593485e79a194f2383498d636`.
This artifact predates fresh-source TUI and swscale macro regeneration. Its
sampled-media TUI is not evidence for the fresh source-rule library. Complete
original preprocessing, decoder behavior, section liveness, full corresponding
source/toolchain, legal relinking/distribution and Android admission remain
unapproved; all four approval flags remain false and APK/device inputs unchanged.

An explicit `source-rules` selector runs the existing isolated PTY/TUI gate on
the fresh source-rule relink library, bound to its own accepted diagnostic input
review. Its native copies, lookup alias, HOME/BUN_TMPDIR, maps and render files
are separate from the prior sampled-object TUI. Baseline manifest and native
files remain unchanged, and the input review is also mutation-guarded. Selector
and approval rejection, review drift and both fixed staging variants are covered
by synthetic tests. Actual map/render/no-extracted-ELF acceptance requires new
native CI and independent archive review; it is not a release payload, decoder
coverage, full corresponding source or Android/legal approval.

Independent acceptance of that separate fresh-source TUI is now complete for
native run `42793824292`, commit
`16767203a8145596ce2f1b7e8dfd6737b4e91f71`. Artifact `13754222024` is
688707219 bytes, with downloaded/API ZIP SHA-256
`a4285bae2f40efc28bd659ac1ae57f5c175d0ec077c219cb2fd643b8f8f981ed`.
Nine archive gates pass over a closed 65759-file manifest, including the fresh
345-object source-rule build, full 446-input final-link reconstruction and
three-mode zlib regeneration. The separately staged TUI retains four native
copies and ten diagnostic files, 365 rendered bytes and actual maps for the
replacement alias and explicit staged Ubuntu loader/libc. Replacement SHA-256:
`46c24b5e9f9f7a51062c071fe73cbc9ccd765a16decc25dd546fb7b269804236`.
Its lookup manifest is only a diagnostic selector, not a release manifest;
baseline native inputs remain unchanged and retained isolated HOME/BUN_TMPDIR
contain no ELF. Fresh TUI independent review SHA-256:
`f58ccebd716ee918d230e77c1f81e30f867ae8fd85b3370defb1187aa5fd3c10`.
Fourteen self-consistent mutations reject approval/selector/review drift,
release-manifest and extraction claims, inventory/copy/map/render/log changes
and an injected runtime ELF; rejection log SHA-256:
`29f7faa8d69f6fd88369c0092ffee365e840d136633e4e1e33f7c4e0c4ec41cb`.
Job `129753736712` log SHA-256:
`1412ddab687b91541bc3af2929d3c13ae4bd5e3056cded1ce55966d1045ecb16`.
This is Linux CI TUI execution plus independent archived evidence, not local
execution, general decoder coverage, every live section, complete original
preprocessing/source/toolchain or legal/Android approval. It predates swscale
regeneration and the later mutation guards; all approval flags remain false.

Swscale regeneration and the generated-header protection also have independent
archive acceptance for run `42795683456`, exact commit
`0ed2c932552d343c798d4d8240aa4b8b951a8ecd`. Artifact `13755083168` is
689541127 bytes; its API/downloaded ZIP SHA-256 is
`0e4da68924db4c502ef07623e4f84d5716180cd296eb46021463cc04d6ec8e3f`.
All nine gates pass with a closed 65765-file manifest. The fresh source-rule
diagnostic has 22324 files and retains the configured build's actual swscale
compile/link commands, `sws_ops.o` and dependency file. `make V=1` builds the
AArch64 executable; a separate `-macros` execution produces 153519 bytes,
identical to pristine `libswscale/uops_macros.h`, SHA-256
`7005eb8091c070e609a8038d5e27860cddf5300e3577875da90796c8ba5164c6`.
Generator SHA-256:
`d25c4bb7d78d80c7dfad9e83ba93658b8419c8192e932802fdeeda1a11972b5c`.
The independent gate checks executable/object ELF identity, exact compile/link
inputs, dependency target and in-cache scope; 23 self-consistent source-evidence
mutations are rejected on Python 3.12 and 3.13 (identical rejection-log SHA-256
`1e3f71a4d5387a27eb3d88c75e5a764975821d44fb349947b27716e9be0cde42`).
The fresh library again replaces all 345 media positions among 446 final-link
inputs, and the distinct fresh TUI review binds replacement SHA-256
`9727f8a823d1352be489ef319fd7f6599a9c70d73d9e8900b72d9aa008172f78`,
365 rendered bytes, actual replacement/Ubuntu-runtime maps and no ELF in the
isolated runtime directories. Fresh TUI review SHA-256:
`ab2d1eef88195b9dcb05990059e58177615e79a7b47c2803d89352d93f67e58d`.
Nine-gate parent acceptance index SHA-256:
`cda88c5fbf3e7ef5f5e0f4bda5beff2cd91a40639692b02d2d6d8de520c766e7`;
job `129760151319` log SHA-256:
`5ee16f0ba5ab3ae814e11a8020276bac56e2f1277db4dd6147d9d2ce3de7009e`.
These are Linux CI execution/archived-evidence results, not original full
preprocessing, compiler/toolchain closure, general decoding, every live section,
complete corresponding source or release/Android approval. The later
`021f0f5` executable-header guards and lookup-manifest checks still require their
own artifact review. APK/device inputs remain unchanged and all approvals false.

The hardened `021f0f5` artifact now has its own independent acceptance for run
`42797400784`. Artifact `13755642301` is 689541422 bytes; its API/downloaded
ZIP SHA-256 is
`f34536f0edda14953e26ea8f03781ca69e02ebfa2b5d9cca031c3641ac55fb8c`.
All nine gates pass over the same closed 65765-file manifest, including swscale
regeneration (`swscaleMacrosOutputMatched`), the hardened executable
type/version/machine checks and the lookup-manifest-protected fresh TUI
(replacement SHA-256
`68cd119f09f8b340b30099e99d22b51b622060fefd8cdf9712c701b5a6f08bec`, 365
rendered bytes, no runtime ELF). The sampled-variant TUI additionally rendered
4428 bytes with replacement SHA-256
`11304c120d3925809e52cc66e0449d72e1e52083796b5a2af76027a5d975cfab`; render
volume varies per build and is only a liveness binding, not decoder coverage.
Fifteen zlib, fourteen relink, fourteen fresh-TUI and 23 source-evidence
self-consistent mutation rejections pass. One parent gate execution was first
run from the wrong working directory and failed on a missing helper script; the
failure log is retained as
`run-42797400784-verify-opentui-artifact-parent.wrong-cwd-failure.log` and the
gate was re-run unchanged from the repository root. Nine-gate hardened parent
acceptance index SHA-256:
`23a3d605afc5936848d9acbb46ec4b0d48be46f5bfdb4e4dfbba788a8409a2ac`;
job `129765972263` log SHA-256:
`74537bd3f4047253be5e76675a2ae7862ce0cdfa7511c773bcbd22bcc86f9bbb`.
These remain Linux CI results with all approval flags false.

Pinned Bun/JSC notice identification, 2026-11-10: GitHub tag `bun-v1.4.4` resolves to
`oven-sh/bun@38afee6c84fcf48c0edb2466aa4b27d287a59c30`; that commit's `LICENSE.md`
SHA-256 `362fe32c954ec829240bd7429c53d705eef08c6bfa45ffc2d02005f857cba4dd`。
Its explanation explicitly identifies JavaScriptCore/WebKit static linking and modified-library relinking obligations, and lists tinycc
LGPL-2.1 and other dependencies; top-level MIT alone cannot classify it. Pinned
`scripts/build/deps/webkit.ts`(SHA-256
`e801ac2b2c0b83767a10e4bf673addda60ff1c4e64d1246c0e442ce22b3c5059`) sets
WEBKIT_VERSION to `d6375c72affe0f70222cdcb45012b10f0bf3a9d5`, distinguishing prebuilt
downloads from local source builds. That WebKit commit's `Source/JavaScriptCore/COPYING.LIB` text
is GNU Library GPL v2, SHA-256
`5094ecb9c9dcd0eadc34f3c11511d9b5535063032bc150164ecd1a5d5a445547`. Individual source files'
LGPL/BSD and other terms still require separate checks; this text cannot establish one uniform license for the entire tree.
The origin collector retains only selected notices, version pins and build files from pinned commits, rejecting digest drift; it neither downloads
all WebKit nor executes builds or claims exact correspondence between official Bun ELF and candidate source. Exact corresponding source, complete notices,
relinking toolchains and APK replacement paths for Bun/JSC/tinycc/other static dependencies remain
blocked, awaiting collection of these files and rechecking in trusted CI.

2026-11-10 independent Library-side artifact review: official WebKit release
`420061461`, tag `autobuild-d6375c72affe0f70222cdcb45012b10f0bf3a9d5`,
contains asset `663826053` (`bun-webkit-linux-arm64-lto.tar.gz`, 258728605
bytes). Downloaded bytes match its GitHub Release API SHA-256
`78d840c6afda98bebf6036f53f3227a7149514206bfdb60f384fb85a2e8dd212`.
A read-only streaming inventory hashed all 2800 members and confirmed regular
ar archives `libJavaScriptCore.a`, `libWTF.a`, `libbmalloc.a`, `libicutu.a`,
`libicui18n.a`, `libicudata.a` and `libicuuc.a`. Inventory JSON SHA-256:
`2970206ecea0b3c36570112ef8e2ac611413cc0c2ac567a36fcfc6f6bd56d818`.
These are Library-side objects, not Bun application-side objects; this is not
a complete relink kit or proof that the shipped Bun ELF used these exact inputs.
Read-only ar inspection additionally found 1023 LLVM-bitcode members and one
ELF64 AArch64 ICU-data object (plus archive metadata), inventory SHA-256
`4ef8fcae3aebaf04f65b4e541119055d360b159f6ee6b8fdf60ab1260fa62753`.
Bitcode magic does not establish its target or producer compatibility. The
archive also contains `compile_commands.json` (727 entries, SHA-256
`532cd68b4955056d5bfcfd2a193bd13d143aeb22e786679813558b983eae9e63`),
declaring Clang 23, `aarch64-unknown-linux-gnu` and `/opt/sysroot-aarch64`.
This is archive-contained metadata, not independently observed compiler output
or a complete source/object mapping; it must not be conflated with the media
build's retained actual-command evidence.
Corresponding Library source, application-side materials, build/toolchain
closure and practical modified-library relinking remain unproven. This artifact
is retained outside the repository and is not an APK input. Upstream Android/
Bionic targets are reference only and excluded by this project's glibc/no-NDK
baseline. A build-configuration tinycc exclusion is not evidence of final ELF
contents. All redistribution, relinking and Android approvals remain false.

A further read-only parent inspection parsed all 727 retained compilation
declarations and found `-march=armv8-a+crc` and `-mtune=ampere1` in each.
One declaration, `/webkit/Source/bmalloc/mimalloc/mimalloc/src/static.c`, then
appends `-march=armv8.1-a`. Do not describe the entire archive as uniformly
compiled for the lower architecture, or infer absence of mimalloc from Bun's
`USE_EXTERNAL_MIMALLOC` build configuration. This metadata is not proof that the
declared compile ran, of the bitcode target/producer, or of which code survived
the final Bun link. The archive-contained sysroot option occurs twice per
entry; counts are option occurrences, not additional compile executions.
Parent flags-review JSON SHA-256:
`8bfa3e6ff2bd7385aa5c30e12ab2af3bb372d84b6a3b92edd43bc83d92b7c1ef`.
Actual allocator providers, symbol/liveness relationships and minimum-CPU
compatibility remain unverified. No archive tool or binary was executed.

A subsequent bounded parent experiment disassembled the smallest bitcode member
(byte count, then member ordinal) in each of the six bitcode-containing static
archives, using the already-installed Windows LLVM 23.1.2 `llvm-dis`. Each of
these six samples declares `target triple = "aarch64-unknown-linux-gnu"` and
contains producer/`llvm.ident` text naming Ubuntu Clang 23.1.2 with package suffix
`++20260910043923+069ef0e7cb36-1~exp1~20260910043934.72`. The original archive and
ar-member SHA-256s were rechecked, and sample bytes, emitted IR, tool binary
hash/version, exact commands and logs were retained outside the repository.
Sample review SHA-256:
`0eef5147ae6ee9fef2405ba7315436316f362b70c6e9fc46bc2a985d18781149`.
This establishes readability and embedded metadata for those six samples only,
not all 1023 bitcode modules or the exact producer executable. Five selected
samples have no retained function target-attribute lines; no CPU minimum can be
deduced from that absence. No downloaded object or archive executable was run,
no target code was generated or linked, and no Bun library replacement or
source/toolchain/license/Android approval follows.

The subsequent all-module pass now disassembles every one of the 1023 retained
bitcode members using that same existing Windows LLVM 23.1.2 tool. All modules
are readable and declare `aarch64-unknown-linux-gnu`; every module's embedded
`llvm.ident` names the same Ubuntu Clang 23.1.2 package string quoted above.
807 modules contain function definitions and function target-attribute lines;
their 6669 retained attribute groups use `target-cpu="generic"` and
`target-features="+crc,+fp-armv8,+neon,+outline-atomics,+v8a,-fmv"`.
All-module review SHA-256:
`748691669e6c5f697d15275a263ed819e39d6803d8e1fd43fa39df982bb6cf04`.
Exact original member hashes, stdin bindings, tool binary hash/version, emitted
IR sizes/hashes, producer text, attributes and stderr are retained; full emitted
IR is hashed rather than persisted for this pass. The original bitcode remains
in the verified archive. These embedded attributes do not prove final machine
instructions, feature dispatch, retained sections, minimum CPU or allocator
provision; the earlier compile-metadata ARMv8.1 mimalloc declaration is not
silently treated as equivalent to these module attributes. No target generation,
execution or Bun final link occurred, and all approval fields remain false.

Bounded Bun application-side relinking research now binds six additional
official texts at Bun commit `38afee6c84fcf48c0edb2466aa4b27d287a59c30`
(`bun.ts`, `compile.ts`, `tools.ts`, `ci-images/spec.ts`, `flags.ts` and
`rust-toolchain.toml`). The parent independently fetched the same fixed raw URLs
with TLS verification and matched all six retained byte counts and SHA-256s,
then checked the material source excerpts. The declared toolchain pins LLVM
23.1.1; the normal accepted major/minor range is `>=23.1.0 <23.1.99`, with an
explicit-directory override. The build checks clang/rustc LLVM major parity;
this is a build-policy declaration, not independently tested bitcode compatibility.
The retained sysroot recipe declares Ubuntu 20.04, glibc 2.31 headers/runtime,
and GCC 13 packages. Its equivalence to WebKit's separately named sysroot is
unverified. The final-link rule uses clang++ with an object response file, lld
selected via `--ld-path=`, and a separate lazy-object response file containing
`--start-lib` / `--end-lib`. Actual Bun C++/Rust objects, generated application
inputs, dependency objects/archives, linker-script/export inputs, toolchain and
sysroot closure remain missing from the accepted relink material.

Research revision 2 corrects the earlier over-strong bitcode, allocator and
extractor claims; revision 1 is preserved as superseded external evidence.
Neither archive symbol intersections nor a link-command-shape experiment
without application inputs can prove actual Bun relinking, archive necessity,
or live-code relationships. Revision 2 JSON SHA-256:
`8b9b6db27b7d43cc5a8896239b895f958a68e1986f194d94b2a7091f110afd55`;
parent binding-review JSON SHA-256:
`63230b52378bfb20f55220d9ab3c7fbc914ba0e112b8bb49580fa196da928f4c`.
No Bun/WebKit tool was executed or toolchain installed in this research;
Android/Bionic assets remain excluded from the glibc candidate. No legal,
relinking or Android approval follows from these source declarations.

A subsequent read-only inventory retains the whole fixed Bun commit archive
outside the repository: 92996071 compressed bytes, SHA-256
`64c0d268a6fa9f5e6e5ac40761dacb6b0825b2092f02cd07d772a9018f39e520`,
26952 members and 277897935 declared expanded bytes. Ten previously pinned
license/build/toolchain texts match this archive byte-for-byte. Inventory
SHA-256: `1a034b942965892026caae5c0eacdee2ea00dd517674087dfc59bb11a1f37820`.
This observed codeload digest is not an upstream published archive checksum,
signature or proof of the official executable's source correspondence.
The parent additionally matches nine fixed raw files against the archive:
`rust.ts`, dependency `index.ts`/`mimalloc.ts`, `verify-binary.ts`,
`binary-expectations.ts`, `src/linker.lds`, Cargo manifest/lock and the mimalloc
OOM patch. Binding review SHA-256:
`d283e486dae7697c657b9b516a171721e8a18405ecec702e8b3be1c366fd1945`.
`rustLtoInLink()` declares `release && !asan`, independently of the C/C++ LTO
switch; that branch adds `-Clinker-plugin-lto` and `-Cembed-bitcode=yes`.
Disabling C/C++ LTO alone therefore does not establish a machine-code-only Rust
relink kit. Non-Windows target rustflags explicitly select lld; the source notes
the current staticlib/rlib path has no rustc target final-link step. The mimalloc
direct build declares `src/static.c` compiled as C++, PIC and a glibc
initial-exec TLS model; this remains a build declaration, not final allocator
provider/liveness evidence. No source script is executed, no toolchain is
installed and no target code is generated or linked. Exact application objects,
generated inputs, dependency/toolchain closure and practical modified-JSC Bun
relinking remain missing; all four approval flags remain false.

The native CI source collector now pins 25 selected Bun/WebKit declaration
files rather than six, including application/Rust/codegen/source-acquisition
rules, toolchain/sysroot declarations, linker script, Cargo manifest/lock and
allocator patch. Every selected file must validate before any selected file is
written; a later digest/size failure leaves no partially accepted file set.
Thirteen collector regressions pass on Python 3.12/3.13, including late failure
and material-rule inventory checks. A separate parent invocation fetches all
25 fixed raw URLs over explicitly verified TLS and validates the same pinned
hashes; review SHA-256:
`a04906ffb8e3436cf446034073eaec47830ffed70ec65b950c0fa4672e9e2786`.
The enlarged collector still needs its own native CI result; it does not execute
the upstream scripts or approve complete corresponding source or relinking.

Read-only static inventory of Bun's fixed dependency index retains all 24
imported dependency modules, 45 literal patch files and 21 GitHub commit pins;
review SHA-256:
`d76598ece34ac91ab872397322f33f5748c1870f89b9513f3f8252aca17d09e6`.
These are source declarations, not evaluated Linux/arm64 feature selection or
complete fetch inputs. In particular, Bun's declared zlib provider is
`zlib-ng/zlib-ng@12731092979c6d07f42da27da673a9f6c7b13586`, not media
zlib 1.3.2 or Zig bootstrap zlib 1.3.1. Dynamic/non-patch inputs still need review.
The fixed root Cargo material inventory separately retains 123 workspace/root
manifests, 305 lock packages (180 registry identities/checksums) and 126 declared
path references. Two referenced manifests are absent from the Bun archive:
`vendor/rust-argon2/Cargo.toml` and `vendor/lolhtml/Cargo.toml`; their acquisition
is declared separately. Inventory SHA-256:
`4df3e7c1a7df9cc1083bfd2274311eac29d61861b985e2606506200e2b0162d4`.
No cargo resolution, actual target/features/build scripts, dependency license
closure, practical relink or distribution/Android approval is established.

A bounded parent review of Bun's pinned acquisition rules documents how
vendored dependencies are declared to be fetched: GitHub tarballs cached by
URL hash only, CRLF-normalized `git apply` patches with overlays, `.ref`
stamps written last, and source identity `sha256(commit + patch contents)`
that ignores disk edits. Notably, the fetch path declares no archive
digest/signature verification, so any reproduction must pin dependency
archive digests independently. No upstream script was executed. Review
SHA-256:
`accda93b66d05eb53870f4a42104447ef5c1e015e58ed7a39f522749c054107d`.

The CI source collector now also retains the whole fixed Bun candidate source
archive (`oven-sh/bun@38afee6c84fcf48c0edb2466aa4b27d287a59c30`, pinned
SHA-256 `64c0d268a6fa9f5e6e5ac40761dacb6b0825b2092f02cd07d772a9018f39e520`)
after a complete bounded member inventory validates: every member is hashed
without extraction, directory/symlink/regular types are recorded, unsafe or
duplicate paths, absolute/out-of-root symlinks and expansion over 512 MiB are
rejected, and all 25 pinned declaration files must byte-match inside the
archive before any evidence file is written. Sixteen collector regressions pass
on Python 3.12 and 3.13, including digest drift, oversize, path-escape,
absolute-symlink and declaration-drift rejection plus refuse-overwrite. This
archive identity still does not establish official-ELF correspondence,
dependency acquisition, compiler execution or any approval; all approval flags
remain false.

The Bun-archive collector commit `a93e93d` has its own independent nine-gate
acceptance for run `42806387561`. Artifact `13760693571` is 781680453 bytes;
its API/downloaded ZIP SHA-256 is
`4442dd44a1cfdff490f8aeda8b41f0d0073be05efae78aa5b5700b8e96cdd2ec`. The
diagnostic now also contains the CI-fetched Bun candidate source archive with
exactly the parent-pinned identity: SHA-256
`64c0d268a6fa9f5e6e5ac40761dacb6b0825b2092f02cd07d772a9018f39e520`, 92996071
bytes, 26952 members (24703 files, 2240 directories, 9 symlinks), 277897935
expanded bytes, alongside the same 25 pinned declaration files. The CI
collector's own inventory SHA-256 is
`875ddc3b22246893fef1362a0198c499b861f1de53e9325f0fd67a872c6b9827`. This is a
bounded member identity/inventory capability, not evidence that the official
Bun executable was built from this source: dependency acquisition, patch
application, compiler execution and complete corresponding source remain
unproven, and all approval flags remain false. Nine-gate parent acceptance
index SHA-256:
`78920fcfe26c43e268a2acf4241aad1a9f0b5767a19905406e3da475bb526ff7`;
job `129796496545` log SHA-256:
`7f64ae868068c52aa97ee8246d6ee0aef6eb09aaad534e38c34987281ed48877`.

2026-11-11 Bun candidate-source build experiment (diagnostic only, manual
workflow `bun-source-build-experiment.yml`). Milestone 1 (run `42874759506`,
commit `06fe195bcfefa21dd2283e6b380d633793016bd1`): the pinned source archive
(digest re-verified in-CI: `64c0d268a6fa9f5e6e5ac40761dacb6b0825b2092f02cd07d772a9018f39e520`)
passes `bun install --frozen-lockfile` and `--configure-only` on
ubuntu-24.04-arm, emitting the full ninja graph (`build/debug/build.ninja`,
`compile_commands.json`, dependency and codegen directories) with a recorded
toolchain identity: Bun 1.4.4, Ubuntu clang 23.1.6, LLD 23.1.6,
rustc 1.100.0-nightly (574ff7d98, pinned `nightly-2026-09-15`), ninja 1.13.2
plus Bun's own pinned `oven-sh/ninja` fetch, cmake 3.31.6, perl 5.38.2.
Configure job log SHA-256:
`51d5dca0b4819791fc5d8592d9a70cae026c5f5086812f8e8ee7f4cf6a83a81f`.
Milestone 2 (run `42876084120`, commit `7e028e107c69ae03999273403a1840f51785242b`):
the full debug-profile build completes on the same runner within the job
budget, producing a runnable application-side binary `build/debug/bun-debug`
(1305197544 bytes, AArch64 ELF, SHA-256
`8f29c518de6eb3f502030a7e52129ffd8a97a664b9d836c413c1526e78deaed2`) from 1241
compiled objects, reporting version `1.4.4-debug` and passing a smoke eval
(`andcode-bun-build-smoke-ok 42`). Build job log SHA-256:
`2ac0eee94ae16584e69d24f7e75597f214ba9c176efad535796eefe9a78b4f2d`; artifacts
`13792637172` (binary evidence, API SHA-256
`950aa266d5e29b74c9321ec7974d307877ddd6608c5d0d3b49e25a3b3d7c5f7e`) and
`13791497391` (configure evidence, API SHA-256
`eb91e5bb64bbccc8888da76b8d12c198c3be00805dc48cad979044b5baa4e962`).
Boundaries: this proves the pinned candidate source builds mechanically on
trusted CI with a pinned toolchain and yields runnable application-side
objects. It does not replicate the official release toolchain exactly (apt
clang 23.1.6 within the declared `>=23.1.0 <23.1.99` range, no ubuntu-20.04
glibc sysroot, debug profile without ThinLTO), does not establish
official-ELF correspondence, does not run `verify-binary.ts` against official
expectations, and does not approve dependency licenses, modified-JSC
relinking, redistribution or Android admission. The release-profile rebuild
with the pinned sysroot and a modified-library relink drill remain future
work; all approval flags remain false.

Further source identification for pinned native packages on 2026-11-09 (evidence only, **no distribution approval**): the commits below
come from npm registry `gitHead` for each exact version, and files at those commits were read. Metadata
association does not prove downloaded ELF files were built from those sources/configurations or replace corresponding-source delivery.

| npm Package | Pinned Source Candidate | Inspected Build Inputs and Remaining Boundaries |
|---|---|---|
| `@opentui/core-linux-arm64@0.8.1` | `anomalyco/opentui@9a09079c0c7ad0fb2d55404f66a5c453204328dd` | `packages/native/build.zig`, `build.zig.zon`, `scripts/build-ffmpeg.ts` and `src/vendor/ffmpeg/README.md`; FFmpeg consists of static objects, not a separate dynamic dependency; Yoga, Ghostty, uucode, miniaudio and others also exist, so eight platform-package notices alone cannot establish closure completeness |
| `@ff-labs/fff-bin-linux-arm64-gnu@0.10.5` | `dmtrKovalenko/fff@459ebcdbdba094843fe5339a1a7f7dae4ced2d82` | Root `LICENSE` is MIT, Copyright 2025 Dmitriy Kovalenko, a candidate supplementary source for the platform package's missing notice; `crates/fff-c/Cargo.toml` and workspace declare vendored-libgit2, Rust dependencies and others, still requiring item-by-item tracing of actual enabled features/targets; root MIT does not cover all static dependencies |
| `bun-pty@0.4.11` | `sursaone/bun-pty@a582ae17cc6c41cb890b142c48669936541339c7` | `rust-pty/Cargo.toml` uses portable-pty 0.8.1, crossbeam, serde and others; determine closure from that directory's Cargo.lock plus actual features/targets, not just top-level MIT |
| `@parcel/watcher-linux-arm64-glibc@2.5.1` | `parcel-bundler/watcher@119f1ff04bb41c2369929e37274900c61b0a9f49` | `binding.gyp`'s Linux branch compiles watchman/BSER, BruteForce, Inotify and legacy C++ files, plus node-addon-api headers and the C++ runtime; retain each source file's notices and verify actual build versions |

The pinned OpenTUI build script above declares FFmpeg **9.0.2**, source archive
`https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz`，SHA-256
`8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e`；
zlib **1.3.2**，`https://zlib.net/fossils/zlib-1.3.2.tar.gz`，SHA-256
`bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16`。
These pins were downloaded from their official HTTPS archives and SHA-256 rechecked on 2026-11-09;
they had not yet been rebuilt in this project or proven to correspond to platform-package ELF files.
The script disables FFmpeg GPL/version3/nonfree, enables static decoder libraries and links their objects individually into
libopentui. Therefore "libopentui is dynamically loaded" does not waive its internal LGPL static-combination obligations.
Provide the library's exact corresponding source, patches, dependencies, build tools/configuration and a workable modified-library relinking path
(or object materials satisfying applicable terms), and verify final-APK restrictions on replacing modified libraries. Bun/JSC
must be handled independently. Retaining download URLs or attaching one LGPL text does not complete this obligation.

`collect-opencode-native-sources.py` includes the four candidate-source archives above in diagnostic artifacts by pinned SHA-256,
along with pinned FFmpeg/zlib source archives. It records notices found by filename, build inputs, the full Cargo.lock package index and
notices inside OpenTUI's embedded zig-deps archives. The four source archives were pinned after HTTPS download
and digest computation on 2026-11-09. This does not prove reproducible correspondence to npm ELF, mistake the full lockfile table
for target-feature closure, or treat notice-filename scanning as complete per-file copyright review.
Report `native-source-review.json` always keeps `redistributionApproved` false.

Candidate Rust target evidence, 2026-11-09: pinned bun-pty `publish.yml` uses
`aarch64-unknown-linux-gnu.2.17` with default features; fff `release.yaml`'s C FFI
uses `aarch64-unknown-linux-gnu.2.31 -p fff-c --no-default-features --features zlob`,
not default ripgrep. A new Cargo normal/build target-tree collector resolves candidate dependencies for the glibc Rust target
(without compiling or executing build.rs), retaining crate archives by Cargo.lock SHA-256
and a notice/build-input index. The fff candidate graph includes `option-ext` MPL-2.0, vendored-libgit2,
LMDB and zlob; crate top-level MIT/Apache declarations cannot cover embedded C/Zig code or establish
that it entered npm ELF. Host build/proc-macro graphs depend on the host running Cargo; trusted
Linux CI is the arm64 Linux candidate baseline. Exact binary correspondence, per-file and build/relinking review remain necessary.
The local preliminary tree for the same target selected bun-pty 38 entries (37 registry), fff 121 entries (117 registry);
all registry archives passed lock digest checks. Filename scans found no standalone notice files for serial, glidesort, heed,
heed-traits, heed-types or zlob. This identifies only a notice-filename scanning gap,
not unlicensed code; per-file/exact upstream supplementary-source review is required, not approval based on Cargo metadata.
Pinned crate texts read the same day: `libgit2-sys 0.18.7+1.9.6/libgit2/COPYING` explicitly states
**GPL-2.0 + unlimited linking exception** (not the crate's top-level MIT/Apache);
`lmdb-master-sys 0.2.5/lmdb/libraries/liblmdb/LICENSE` is **OpenLDAP Public
License 2.8**, with a separate COPYRIGHT. Archives remain only in external temporary review directories/CI diagnostic artifacts; no
GPL-2.0 source is copied into this repository. fff static combination, exception applicability, corresponding source and notice obligations
still require separate confirmation; a linking exception is not permission to skip license review or automatically distribute formally.
Further checks of commits pinned by `.cargo_vcs_info.json` found MIT root LICENSE files for heed/heed-traits/heed-types and zlob,
candidate supplements for missing archive notices (the collector pins per-commit SHA-256
and retains original text). No notice file was found at the glidesort commit root, and serial includes no VCS
location information (later supplemented by full-crate file matching below). Supplementary sources do not prove binary correspondence or cover all embedded code.
Subsequent review found serial-rs annotated tag `v0.4.0` points to
`7ed6540c2789b7c7365cd7a89fcb7bac7c567de8`, pinned source-archive SHA-256
`c8ff1c33d84c0b8a6ee461bcf00d60ec14639856dcd21a14ce29ec5d215b1797`；
All 6 regular files in serial 0.4.0 crate are byte-identical to same-named files under that commit's `serial/` directory.
That commit's root MIT LICENSE SHA-256
`871afd9d691846de71e0b83812ba9c7ff00bc7b3ad102dedcaa109f2246d52ad` can therefore supplement
the exact crate's notice; the collector rechecks all files/digests. This is not approval of the whole PTY ELF.
The crate evidence index also records `build.rs` and `.cargo_vcs_info.json` digests to support review of
actual native-build branches and supplementary-notice commits; the collector never executes these build scripts.
CI `42544621101`'s arm64 Linux candidate tree has bun-pty 38/37 registry and fff 120/116
registry (1 entry different from Windows host preliminary review). All registry source digests were rechecked; reports remain
blocked. That run's default upload-artifact omitted dotfiles in expanded candidate sources, leaving the full-file
manifest unclosed and the diagnostic package incomplete; pinned-source dotfiles in the isolated stage are now explicitly retained.
After the fix, CI `42545320876` (commit `16a3d19`) fully succeeded; artifact ZIP SHA-256
`eaf7f920ad9cbcf9af64fe832b612f7e181821a25a720c8240a6fd59b7ae6e65` matches the API.
All 600 full-file digests, two registry-archive digest groups and 4 supplementary notices passed verification;
source/license/runtime-library reports still do not approve distribution, and nothing was deployed to a device or used as official APK input.

The next bun-pty experimental rebuild uses only those pinned archives and Cargo.lock: on the Ubuntu 24.04
arm64 runner, Cargo fetch --locked precedes offline build --locked, enforcing GNU linker
PT_LOAD≥16K. Source/lock/tool/command/output digests are recorded; the rebuilt ELF replaces the sole pinned glibc input
in the experimental installation tree, then the Bun plugin recalculates its physical name. This is not proof of original npm ELF reproducibility.
Cargo offline does not isolate third-party build.rs network/host access. Rust sysroot/toolchain and all
applicable notice obligations still require review (see supplementary serial source above). Diagnostic builds only, not official bundle/APK inputs;
distribution is not thereby approved.
CI `42574333144` (commit `13c271b`) passed fixed-source rebuild, 16K/glibc/exports, runtime-library closure,
ordinary/persistent PTY and TUI/no-ELF-extraction gates. Downloaded ZIP SHA-256
`4f0af54875ac816333562592dcbc4276fe2ab1eb90c473b06d1802c162ab733a` matches the API,
with all 640 digests verified. Rebuilt bun-pty ELF SHA-256
`2f4cbc71ce4b4edb6762dccc584f974ad363076e0c2ad8691732b08c47d2b903`，529104
bytes, with only libc/libgcc_s NEEDED. Pinned-source build ELF and Bun pre-staged copy digests agree, and
actual ordinary-PTY maps were checked. The other three libraries remain npm ELF; Android is **pending P0/P3 on-device verification**.
Reports now distinguish pinned npm inputs from source-rebuild origins; the main candidate-source commit is no longer overwritten by the supplementary-notice
commit, with regressions verifying retention of both distinct commits.

The watcher source-rebuild experiment added pinned headers on 2026-11-09: `node-addon-api 7.1.1`
(matching pinned upstream bun.lock, registry SHA-512 identical to the lockfile), archive SHA-256
`b10455d15a977c0cd17a1cb0eb679e03d939f8ef8d4302eb33e1f78dacc71f82`. Its bundled LICENSE.md, read the same day,
is MIT, Copyright 2017 Node.js API collaborators. Official Node 24.6.0
headers archive SHA-256 `6b891cced2a8ee08fef06b8cb36a890bd6d1dd8aca575e2a392bb78f0970b819`
matches nodejs.org's official SHASUMS256.txt. Headers contain Node MIT/other notices retained with the archive;
the entire header closure cannot be reduced to one license. Compilation uses the explicit source list from pinned binding.gyp's Linux branch
and NAPI_VERSION=4 (first CI `42577241899` showed version 3 lacks
ThreadSafeFunction and produced no replacement payload), without running npm install scripts. Experimental input replacement requires native-export verification and real Bun
subscribe/write/unsubscribe file events. This remains diagnostic only, not approval of
exact original npm binary correspondence, embedded-source per-file licensing or Android acceptance.
Subsequent compilation uses GCC `-H` to record actually included headers, with explicit sources, digests, pinned-origin categories and
notice-text clues. Watcher's `src/wasm/include.h` embeds the Node.js contributors MIT text;
the notice is not discarded because the Linux branch is empty. System GCC/glibc headers are recorded only by digest, not delivered as corresponding
source. This index covers neither compiler internals nor linker inputs and does not complete per-file license review.
The real-event probe additionally runs the final content-addressed pre-staged copy with collected loader/libc/libstdc++/libgcc_s,
checking all maps match; post-build tests under runner-default libraries cannot substitute for this gate.
CI `42578098328` passed rebuild/real events and generated Bun imports, then the older static allowlist rejected
the rebuilt library's NEEDED `ld-linux-aarch64.so.1`. The already collected loader is now consistently allowed by runtime closure and local gates,
retaining recursive symbol-version and actual-maps checks without adding a new system-library dependency.
Previous run `42575345307` (commit `125ec97`) ZIP SHA-256
`19550896df80985dd5850408382209f6a49b0da14511db441e15ae5adce3dff8` matches the API;
642 manifest digests match, including serial six-file matching and bun-pty origin reports. Its
diagnostic README was written after manifest generation, protected only by ZIP/API digests. README generation has been moved earlier; subsequent
artifacts must additionally verify exact ZIP-file-set/digest-manifest-set equality (except the manifest itself).
Network history: `42578577616` completed watcher staged maps/real events and shell/PTY/TUI/no-ELF
gates but timed out downloading pinned media source; `42579064629` and `42579438063` encountered persistent HTTP 504 on pinned Bun
downloads. Only bounded transfer retries and an API download path for the same GitHub asset ID `665259460`
were added, still enforcing the original SHA-256; source evidence, TLS and digest gates are not skipped.
CI `42579620831` (commit `40252c0`) fully succeeded. Artifact `13656956805`, 225990521
bytes, ZIP SHA-256 `bd5424f935494df0622f3f961bf5f89d4f266e2663be433397065a52db193a8d`
matches the API; all 3461 file digests and ZIP/manifest file sets match exactly (except the manifest itself).
Rebuilt watcher ELF SHA-256 `a384a3ab5aa60dda6c61fb87489a99b719910113c00f54c1f3760aeea3662d42`,
623824 bytes, matches build output, Bun import manifest and pre-staged copy. Real-event logs under both the normal build environment and collected runtime libraries
passed. Rebuilt bun-pty ELF retains digest `2f4cbc71…` above; both libraries' origin
reports say fixed-source-ci-rebuild. Compile-input index digest rechecking passed: 389 entries comprise watcher
25, node-addon-api 3, Node headers 4 and runner system inputs 357. The latter are digest-only records,
not corresponding-source delivery or license review. All approval fields remain false; no device deployment occurred.

fff adds a diagnostic rebuild recipe: the same pinned source/lock, built with `-p fff-c --no-default-features
--features zlob`, pinned Zig 0.16.0 and GNU bfd linker, with offline compilation after Cargo fetch --locked;
selected-target/feature crate archives, Cargo JSON messages and the final GNU map are retained.
Explicit `LIBZ_SYS_STATIC=1` uses the locked libz-sys embedded zlib;
`LIBGIT2_NO_VENDOR=0` retains the selected vendored-libgit2 branch, avoiding an unrecorded runner-libz dependency.
These C sources remain in external CI archives, not copied into the repository; static-link success does not approve licensing.
LOAD inputs receive digests only if still present after linking; temporary objects removed by rustc are explicitly unavailable.
This is not precise per-section/per-file link attribution and does not deliver system-toolchain corresponding source. Experimental npm inputs are replaced only after ELF/exports/
16K/glibc and real Bun indexing/search/glob pass; the final content-addressed copy must then be checked with
collected runtime libraries. Original npm correspondence, distribution and Android are not approved.
First CI `42601569967` (commit `a3ac510`) completed fff compilation, but the dependency gate found
`libz.so.1` and rejected input replacement. Subsequent Bun build/runtime gates were skipped; no approved artifact resulted.
Commit `4e46ebc` explicitly pinned those static branches; CI `42602199884` fully succeeded.
Regressions also cover rejection of system `libz.so.1` with original input bytes unchanged; the allowlist is not expanded to admit it.
That run includes actual fff search/glob, final pre-staged copy/collected runtime maps, and shell/ordinary and
persistent PTY/TUI/no-runtime-ELF-extraction gates; artifact `13666846466`, 248955245 bytes.
ZIP SHA-256 `9ea996e8b7c9d12a5beaed6f16d801bf0e6e491a9785b73ca38bc3fa2f8e8a10`
matches the GitHub API; all 3956 file digests and ZIP/manifest set closure were rechecked byte-for-byte locally.
fff build output, Bun import and final pre-staged copy share digest:
`27dd516b50ae87429ae748c8a9a43485777e36de2be846ace04235f5f0bc03e7`, 10417896 bytes;
NEEDED contains only `libgcc_s.so.1`, `libm.so.6`, `libc.so.6`, `ld-linux-aarch64.so.1`.
Search/glob logs for build/final pre-staged copies, 116 registry-archive digests among 120 selected packages,
and all three libraries' fixed-source-ci-rebuild origin reports agree with the manifest. All approvals remain false.
Of 26 GNU LOAD report entries, 19 remain available after linking with recorded digests, 6 objects/archives are unavailable,
and 1 is GNU-synthesized `linker stubs`, not a missing physical file. That run's older report
misclassified the latter as a temporary path; subsequent parsing lists linker-generated separately without altering existing artifacts/digests.
The 19 digests are CI records only; original link inputs are unavailable locally, so byte-for-byte content rechecking is not claimed.
Per-file licensing, toolchain/static-dependency corresponding source and precise link attribution remain incomplete; nothing was deployed to Android.

Supplementary glidesort verification, 2026-11-09: `glidesort-0.1.2.crate`'s `.cargo_vcs_info.json`
pins `orlp/glidesort@c4df9518ec23a424a867b3d50967f0aaafe3c0fd`. Corresponding codeload
archive SHA-256 `f7b01ecb077689763d80ce6897b700b594a228d018f2734d95fe69098ff6fa1b`;
local review verified all 16 crate source files/README/original manifest byte-identical to that commit, excluding only
Cargo-generated `Cargo.toml`, `Cargo.lock` and `.cargo_vcs_info.json`.
The commit archive has no LICENSE/COPYING file, and the current GitHub repository root likewise provides no standalone text;
API license=null. `Cargo.toml`'s `MIT OR Apache-2.0` declaration and README attribution do not replace
actual copyright/license notices. No MIT author/year was fabricated or license text borrowed from other projects. This remains
blocked pending upstream completion or replacement with a reviewed implementation; source matching alone cannot approve distribution.

The subsequent experimental recipe uses a project-owned thin adapter calling Rust `slice::sort_by` / `sort_by_key`, without copying
glidesort. Only when original digests of four pinned files match does it remove workspace/fff-core
glidesort declarations and the lockfile's sole dependency edge/package record, replacing two internal sort entry points and retaining each
before/after digest plus modified source/lockfile. Builds still use `--locked`, reject graphs still selecting
glidesort, and independently test ascending/descending order, stable equal keys, empty/single-element inputs, non-Copy values and panic safety.
The implementation abandons shared temporary-buffer optimization, so performance equivalence cannot be claimed; the new Rust standard-library origin/license still requires
review. Original candidate-source trees and older artifacts continue to include glidesort and remain blocked; only modified experimental
builds may claim its exclusion. Real CI sorting/search/glob/TUI regressions remain pending; no APK approval.
The patch was actually applied locally to the four pinned files and all modification digests rechecked; the
3 project-owned sorting tests compiled with Windows rustc passed. This does not replace arm64/Linux CI or Android/performance verification.

Experimental dynamic-library baseline, 2026-11-09: CI installs official
`libstdc++6`/`libgcc-s1` using Docker Official `ubuntu:24.04`, recording actual image ID, dpkg binary/source-package versions, library digests and
package copyright. Reading gcc-14 package copyright in an existing Ubuntu 24.04 instance that day confirmed
GNU GPLv3 + GCC Runtime Library Exception for libstdc++/libgcc. The exception does not
waive the libraries' own corresponding-source/notice obligations; actual package copyright text is retained with diagnostic artifacts. glibc remains separately
reviewed under LGPL. The new collector copies only arm64 libraries from the CI sysroot, not host-runner libraries, and does not feed the
official APK/bundle. Recursive NEEDED/versioned-symbol checks and successful execution are not distribution approval.
CI `42543657122` (commit `4279a3e`) passed dependency/version and
16K/glibc≤2.39 gates for 9 runtime libraries and 14 ELF files, shell/ordinary and persistent PTY, real TUI staged mappings and isolated
HOME/BUN_TMPDIR no-ELF-extraction checks. Downloaded artifact ZIP SHA-256
`8d4c27abc3893881f18d4c243fd71cf53302b914129089c921ab18aca2719b0c` matches the API;
44 file digests and 9 library digests were rechecked byte-for-byte. glibc `2.39-0ubuntu8.9`, GCC
runtime `14.2.0-4ubuntu2~24.04.1`. This is only a Linux experiment, not Android acceptance.

Android libtinfo custom-build verification, 2026-11-09: Ubuntu
`ncurses_6.4+20240113.orig.tar.gz` SHA-256
`37a12a0f8ae2605012c9a164dd286b0cfa02b51b5055836d09eb3d597fc351b1`，
Bundled COPYING is MIT/X11-style (including a name-retention clause); apply Ubuntu
`6.4+20240113-1ubuntu2.2` patches (including two security fixes), debian.tar.xz SHA-256
`c7bbb8483d7ec358fb925a370575d8ebef63d6e455edce140de2ca7b86cf98d1`，
Digests match ports.ubuntu.com `.dsc`. Source is staged only for CI builds, not added to this repository; retain
Ubuntu copyright, upstream COPYING and pinned digests/configuration. Disable HAVE_SETFSUID only in Android-bundle
libtinfo, using upstream safe-open branches without identity changes, fabricated syscall
results or root-access. Artifacts require actual initialization and application-domain retesting before approval.

### 2.2 Independent-Program Aggregation (GPL-2.0, Bundled Binaries and Source Guidance Only)

| Project | Repository | License | Role | Obligations and Boundaries |
|---|---|---|---|---|
| busybox | `mirror/busybox` / busybox.net | GPL-2.0 | Static glue tools in the delivery bundle (sh/tar/readlink etc., §4.1.2) | Aggregation of a **static single-file independent program**; official `busybox.net/downloads/binaries/` provides prebuilt static arm64 binaries (access tested, one procurement source; alternatively build a pinned version within the baseline); `manifest` records version/source URL; never incorporate source |
| GNU Bash | `https://ftp.gnu.org/gnu/bash/`, Ubuntu source packages `https://ports.ubuntu.com/pool/main/b/bash/` | GPL-3.0-or-later (2026-11-08 checked `usr/share/doc/bash/copyright` in Ubuntu `bash_5.2.21-2ubuntu4_arm64.deb`: Files * / GPL-3+) | Tier P default interactive shell, Ubuntu 24.04 baseline 5.2.21; dynamic dependency libtinfo (Ncurses, MIT/X11 and some BSD-3-Clause, `libtinfo6_6.4+20240113-1ubuntu2_arm64.deb` copyright checked the same day) | Independent ELF aggregation, no Bash source taken; CI collects ELF/dependencies, copyright and full GPLv3 text; manifest records actual package versions/source-pool URLs; releases still must fulfill GPL corresponding-source obligations, not replace compliant delivery with URLs; no third-party host Bash invocation |
| proot | `proot-me/proot` (★2.7k) | SPDX says GPL-2.0 (only/or-later pending verification, action item) | **Fallback**: minimal binds when shim coverage is incomplete (§4.5) | Same policy as busybox; even if GPL-2.0-only is confirmed, distribution as "independent binary aggregation + source provision" remains possible |
| Ubuntu 24.04 arm64 development rootfs | Docker Official Image `ubuntu:24.04`, Ubuntu `noble`/`noble-updates`/`noble-security` | Multi-license independent-program aggregation; must not be labeled AGPL as a whole. Traced per package on 2026-11-09 through image dpkg database and `/usr/share/doc/*/copyright`; release compliance awaits review | Root chroot prototype contains apt, Bash, ca-certificates, curl, git, build-essential, python3, util-linux | New recipe installs through apt only from official sources, retains copyright/common-licenses and generates package-version/source-package inventory and image digest; CI artifacts are for validation only. Before formal distribution, provide each GPL/LGPL package's corresponding source and changes; inventories/source URLs do not replace fulfillment. PRoot does not reuse writable chroot instances |
| Ubuntu Base 24.04.4 arm64 (device development bootstrap) | `https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.4-base-arm64.tar.gz` | As above, retain package copyright/common-licenses; official HTTPS SHA256SUMS and downloaded archive checked on 2026-11-09 | Device development validation entry when local Linux/Docker is unavailable, not a replacement CI image source | Pinned SHA-256 `04207713ece899c3740823d33690441ad3a7f0ded1101aca744e2b0f37ac7ff2`; extract only into an isolated new ext4 image, retain source information/package inventory; formal release still requires per-package compliance |

### 2.3 Reference Implementations (Reuse with Care)

fff diagnostic builds use the official Zig **0.16.0** arm64 tool archive (CI only, not bundled):
`https://ziglang.org/download/0.16.0/zig-aarch64-linux-0.16.0.tar.xz`，SHA-256
`ea4b09bfb22ec6f6c6ceac57ab63efb6b46e17ab08d21f69f3a48b38e1534f17`，
Downloaded on 2026-11-09 and checked against official index.json digests and archive-root LICENSE: MIT (Expat),
Copyright Zig contributors. Bundled standard libraries/compiler runtimes/LLVM and others must not collectively be assumed MIT;
static toolchain inputs in build artifacts still require separate review. A pinned tool digest is not license approval.

Build-time Actions (not included in APK/bundle): `actions/download-artifact@v4`,
`actions/setup-java@v4`、`android-actions/setup-android@v3`、
`gradle/actions/setup-gradle@v4`, verified MIT through each repository's LICENSE on 2026-11-09
(for Gradle, specifically v4/LICENSE, not main's mixed licensing as a substitute for the used version). Used only to
download current-run artifacts and install JDK/Android SDK/Gradle; no third-party source/tools incorporated into deliverables.
Troubleshooting may install official Ubuntu `gdb` in CI (GPL-3.0-or-later; on 2026-11-09 checked
GNU GDB `gdb/top.c` copyright header and GPLv3+ version output through sourceware's RTEMS read-only mirror);
it collects only our own CI process stacks and is not included in APK/bundle.

| Project | Repository | License | Value | Notes |
|---|---|---|---|---|
| claude-code-termux | `naiyQAQ/claude-code-termux` (★22) | MIT | **Closest predecessor**: claims native execution of a Bun-compiled AI coding CLI on Termux (without proot); closely study environment handling/shim ideas in P0 | MIT, code reusable with notices retained |
| **bun-termux** | `Happ1ness-dev/bun-termux` (★85, active through 2026-11) | **MIT** | **Best predecessor**: tools/guides for proot-free Bun on Termux, highest community interest; first P0 close-reading choice | MIT, code reusable with notices retained |
| termux-pacman/glibc-packages | `termux-pacman/glibc-packages` (★300) | MIT | Mature Termux glibc packaging; **comparison-test baseline** for our §4.5 shim and library-path practices | sysroot now extracted from baseline rootfs for glibc 2.39 consistency; this repository serves as a comparison |
| bun-on-termux | `tribixbite/bun-on-termux` (★29) | **No license** | Conceptual Bun-on-Termux reference | Copyright protection applies by default; observe, do not copy |
| glibc-runner ecosystem | `dbgid/glibc-runner-termux` (GPL-3.0) and others | GPL-3.0 / MIT | Mature loader/library-path wrapping (`grun`), supporting §4.1.2 wrappers and §6.3 Route A | Primarily conceptual reference |
| glibc-wine / androBox and others | `airidosas252/glibc-wine`, `Pipetto-crypto/androBox` | MIT / GPL-3.0 | Loader/library-path practices in the glibc-on-Android ecosystem | Supports §4.1.2 wrapper design |
| UserLAnd | `CypherpunkArmory/UserLAnd` (★4.3k, active) | **No LICENSE (all rights reserved)** | **Architecture observation target**: commercial-grade precedent for running complete Linux distributions in an ordinary APK (without root); jniLibs/extraction/process-management behavior may be reverse-observed, but no code may be taken | Observe UX/public documentation only; action item: test its targetSdk/execution strategy before P3 for comparison |

### 2.4 Downgraded to Optional / Rejected after Evaluation

| Project | Status | Reason |
|---|---|---|
| Termux (`termux/termux-app`, GPLv3-only) | **Downgraded**: optional appendix path | v0.3 principle: no third-party host-app dependency. If users install Termux themselves to run the bundle, that is third-party aggregation with no obligations for us |
| proot-distro (`termux/proot-distro`, GPL-3.0) | Downgraded | As above; rootfs now generated by our own `make-rootfs.sh`, controllable and sharing baseline origins |
| Magisk (`topjohnwu/Magisk`, GPL-3.0) | Still Tier M's required platform | Write only script modules in the official format (scripts under this project's AGPL), without modifying Magisk itself → no source obligation |
| Termux:Boot (`termux/termux-boot`, no LICENSE) | **Dropped** | Autostart moves to Magisk service.sh (Tier M) / foreground service (Tier P), eliminating this risk |
| `meefik/linuxdeploy` (GPL-3.0) | Rejected | Inactive after 2022; covered by our make-rootfs.sh + Magisk module |
| termux-elf-cleaner (`termux/termux-elf-cleaner`, GPL-3.0) | **As needed**: build-time fallback only | Our ELF files are parsed by glibc loader rather than Android linker, usually needing no cleaning; introduce only if Tier P shows Android-side parsing warnings (CI use, not distributed) |
| actions/runner-images (`actions/runner-images`, MIT) | Adopted | Source of CI `ubuntu-24.04-arm` runner images; no additional action |
| Andronix / AnLinux | Rejected | Confusing licensing and duplication of our scripts |
| box64/box86 | Rejected | Intended for x86→ARM translation; we use native arm64 |

---

## 3. AGPL-3.0 Compliance Rules (Project Policy)

1. **All original project work** (design documents, bundle/pack scripts, shim, Magisk module scripts, APK,
   jackpal fork modifications) → AGPL-3.0-only.
2. **MIT/BSD/Apache code** (opencode, dropbear, jackpal, etc.) → may be incorporated with copyright
   and license notices retained; the incorporated whole is subject to AGPL for downstream recipients.
3. **LGPL dependencies** (glibc, JavaScriptCore) → verify versions, static/dynamic linking and changes individually;
   retain notices and fulfill applicable requirements for exact corresponding source, relinking/replacement and necessary installation materials.
   Attaching license text or upstream URLs alone does not establish fulfillment.
4. **GPL-2.0 independent programs** (busybox, proot) → distribute only as **independent binary aggregation**;
   `manifest` supplies exact versions/source URLs as a traceability index, not a valid written offer.
   Releases must provide corresponding source (including downstream build patches/scripts), or a valid source-provision method
   allowed by applicable terms for the actual delivery method. Do not claim formal distributability before completion. Do not incorporate source;
   if modifications become necessary, release them separately in an independent GPL-2.0 repository.
5. **GPLv3 platforms** (Magisk) → write only script modules in their standard format (scripts under AGPL); do not touch platform source.
6. **Unlicensed repositories** → never take code; refer only to behavioral ideas.
7. Automatically generate `THIRD-PARTY-NOTICES.md` for every release (CI collects from `bundle/manifest`), and embed
   a notices viewer entry in the APK "About" page.

---

## 4. Action Items

Status (2026-11-06): **P1 complete, all CI green** (run 42142198520). Completed:
- [x] Full CI pipeline (rootfs→bundle→audit→gates→smoke→Tier P patchelf Route A→release artifacts); opencode asset name verified as `opencode-linux-arm64.tar.gz` (v1.19.5)
- [x] Static busybox source established: Alpine `busybox-static` package (`busybox.static`, origin recorded in manifest)
- [x] `bundle/manifest` + naming-lint + check-compat gates enforced in CI
- [x] `andcode-doctor` JSON output standardized (one object on stdout only)

Pending:
- [ ] P0: Closely study shim/environment handling in `Happ1ness-dev/bun-termux` (MIT, first choice) and `claude-code-termux` (MIT), verifying the "Bun on bare sysroot without proot" approach
- [ ] P0: Design shim interception scope (open/openat/stat/execve) against `termux-exec` (Apache-2.0), listing pitfalls
- [ ] P0: Verify `proot-me/proot` LICENSE text (only vs or-later), determining distribution wording for the fallback
- [ ] P0: Test static arm64 busybox (GPL-2.0, official binaries or baseline self-build) execution in `/data/local/tmp` (Tier A); data-directory exec is now platform-prohibited and no longer applicable (Tier P uses jniLibs)
- [ ] P0: Test jniLibs extraction (`lib*.so` → nativeLibraryDir) execution under targetSdk 37.2; verify Bun/JSC JIT under W^X or `BUN_JSC_useJIT=0` fallback
- [ ] P0: Verify whether opencode extracts ELF at runtime (TUI etc.) and its pre-staged-path mechanism (§4.1 constraints)
- [x] P0: **git https helper chain — resolved (device, 2026-11-06)**: three-layer fix — ①static musl launcher for helper (avoids shell spawn anomaly); ②proot bind /etc (architecture correction because LD_PRELOAD cannot intercept glibc internal fopen, DESIGN §4.5 updated); ③`options use-vc` (test network blocks outbound UDP 53). `git ls-remote https://github.com/...` returned HEAD on device
- [ ] P3: Create minimal jackpal terminal-library fork (retain Apache-2.0 notices), keeping only paths needed for TUI sessions; test UserLAnd execution strategy for comparison (observation only)
- [ ] Before release: recheck notice completeness for dropbear/bun LGPL portions; embed viewer entry in APK About page
