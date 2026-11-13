# AGENTS.md — Coding agent rules for this repository

For AI coding agents (OpenCode and others) working in this repository. Rules fall into three categories:
**Hard constraints (violations require rework) / Workflow / Environment facts**. Background material lives in docs/; this file contains mandatory rules only.

## 0. Project in one sentence

Port opencode (an AI coding agent) to Android arm64 and provide an Ubuntu 24.04 arm64 (glibc 2.39)
compatibility build baseline whose artifacts also run on standard Linux arm64. Three self-contained delivery forms:
Tier M (Magisk module, root) / Tier A (adb-pushed bundle, locked) / Tier P (custom APK, locked).

## 1. Required reading by task type

| Task | Read first |
|---|---|
| Any change involving **executable entry points, command names, environment variables, or physical filenames** | `docs/NAMING.md` (§3 registry → §6 slug algorithm → §8 gates) |
| Introducing/replacing **third-party code or binaries** | `docs/REUSE.md` (§2 inventory → §3 AGPL compliance policy) |
| **Adding binary files to the repository** (including LFS) | `docs/LFS.md` (§2 allowlist → §3 prohibited items → §5 change process) |
| Changing code related to **architecture, runtime behavior, or platform constraints** | Relevant sections of `docs/DESIGN.md` (§1.2 hard platform constraints, §4 delivery forms) |
| Packaging/CI/audit scripts | Existing implementation style in `bundle/pack-*.sh`, `baseline/check-compat.sh`, and `scripts/naming-lint.sh` |

When documentation and code disagree, NAMING.md is the naming authority. Record versioned changes in DESIGN.md
(architecture changes require an additional entry in the changelog at the top). Do not let documentation silently become stale.

## 2. Hard constraints (violations require rework)

1. **License = AGPL-3.0-only** (root `LICENSE`). Key reuse rules (REUSE.md §3):
   - MIT/Apache/BSD code may be incorporated; retain copyright notices and register it in `bundle/manifest`;
   - **GPL-2.0 code (busybox, proot) must not be copied into the repository**. Only aggregation of independent binaries is allowed,
     with versions and source URLs recorded in the manifest;
   - **Do not take code from repositories without a LICENSE (such as UserLAnd or bun-on-termux)**; observe behavior only;
   - Register new third-party dependencies in REUSE.md §2 first, including the license verification method and date.
2. **Naming conventions are foundational**: register every new command/script/environment variable/physical name in NAMING.md
   §3–§5 before writing code. `physical-tier-p` in `bundle/manifest` must match
   `^libandcode-[a-z0-9-]+\.so$` (≤64 characters). Failure of CI `naming-lint.sh` means build failure.
3. **Compatibility boundaries** (DESIGN §1.2/§3.1):
   - glibc symbol versions ≤ **2.39**; linking against Android NDK/Bionic is prohibited;
   - PT_LOAD segment alignment ≥ 16K (build flag for our own NDK code: `-Wl,-z,max-page-size=16384`);
   - **targetSdk 37.2 platform constraint**: execution from data directories is prohibited → do not generate ELF files
     at runtime that will be executed. Do not rely on runtime ELF extraction (if opencode does this, preinstall copies and redirect it to them);
   - The custom LD_PRELOAD shim (`bundle/shim/`) is the intended solution for read-only /etc. Do not introduce proot
     unless the shim is proven insufficient (record evidence in the P0 checklist first).
4. **Self-contained principle**: introduce no dependency on Termux / proot-distro / any third-party host app;
   runtime dependencies are limited to bundled components and Android system tools (/system/bin/sh, getprop, etc.).
5. **No binaries in the repository**: .gitignore already covers them; track all artifacts through CI artifacts and `bundle/manifest`.
   If `.so`/`*.tar.*`/key files appear in the repository, remove them first, then check .gitignore for gaps.
   **Git LFS is no exception**: LFS is limited to the docs/LFS.md §2 allowlist (test fixtures/documentation images).
   Do not use it to bypass this rule; `scripts/lfs-check.sh` blocks violations in CI.

## 3. Workflow

- After changing the delivery pipeline (rootfs → bundle → jniLibs), validate in this order:
  1. Run `bash -n` on all modified shell scripts;
  2. `scripts/naming-lint.sh --bundle-dir <unpacked-directory>`;
  3. `baseline/check-compat.sh --page-align <bin|lib-directory>`;
  4. Get CI (`ci/github-actions.yml`) passing; it is the only trusted execution environment (see §4).
- Device validation (Tier A/M/P physical-device smoke tests) cannot run locally: **device behavior that has not been tested
  must be marked "pending P0/P3 device verification" in delivery notes. Do not claim it is verified**.
- When changing architecture sections in `docs/DESIGN.md`, append a version entry to the top changelog (increment v0.x)
  and synchronize cross-references in README and affected documents.
- See the commit rules below; keep naming/license terminology consistent with the NAMING.md and REUSE.md registries.

### Commit rules

**Commit authorization**:
- The main agent may create commits at **coherent integration checkpoints that have been reviewed and appropriately validated**;
- First- and second-level subagents are **prohibited by default** from running `git commit`, amending, or performing any operation that changes repository history,
  unless the user or main agent provides explicit task-level authorization. By default, leave changes in the shared working tree
  and report changed paths and focused validation results to the parent;
- Authorized subagent commits must stay within their assigned write set. Report the commit hash,
  included paths, and validation results to the parent; the main agent retains responsibility for integration review and subsequent repository-wide commits.

**Commit message format** — by default, a one-line subject + blank line + flat change list:

```text
feat: add serialization abstraction and JSON codec

- Add format-neutral serialization::Value and serialization::Codec public APIs
- Add json::Codec plus parse/dump helpers while hiding nlohmann/json in src
- Update Logger and table helpers to use serialization::Value instead of nlohmann/json
- Keep third-party include dependencies private to the library build targets
- Add JSON serialization tests and update table coverage
```

Rules:
1. First line: `<type>: <summary>`, preferably using `feat`, `fix`, `refactor`, `docs`,
   `test`, or `chore` as the type;
2. Describe the core change with a concise English imperative summary; avoid vague titles;
3. Leave a blank line after the subject, then list key changes with `- `;
4. Each item focuses on one concrete change, primarily what changed; mention scope/impact only when useful;
5. Keep adjacent items consecutive without blank lines; use blank lines in the body only to deliberately separate prose or change groups;
6. Keep the list flat, without nesting;
7. Very small commits may contain only a subject; cross-module/cross-layer commits or commits adding tests must include a change list;
8. Omit unrelated background and lengthy process logs unless explicitly requested by the user;
9. For assistant attribution, leave a blank line after the body and append the trailer
   `Co-authored-by: <assistant name> <assistant email>`,
   following the current platform or project identity convention.

## 4. Environment facts

- The development host is **Windows (pwsh), with no local Linux shell/WSL distribution**. Do not execute
  bash scripts locally for validation; actual validation runs on GitHub Actions' native `ubuntu-24.04-arm` runner.
- The repository has not yet had `git init` run; the first CI run will actually validate script syntax and the full pipeline.
- Shell scripts must use **LF** (see `.gitattributes`). Device-side scripts with shebangs must be POSIX sh
  compatible (use the subset supported by `/system/bin/sh`; no bashisms — this includes `smoke-test.sh`
  and `bundle/overlay/sbin/*`).
- Communicate with the user in Chinese. Write all new or updated documentation and
  code comments in English. Keep commit messages in English and terminology consistent
  with the NAMING.md registry (`andcode-`, `libandcode-*`, `ANDCODE_*`, Tier M/A/P).

## 5. Current work (claim a task before starting)

Status (2026-11-11): **P0/P1/P2/P3 are all complete** — Tier P Web/TUI works end to end
(Release v0.1.1); the optional Ubuntu PRoot backend for managed serve is merged
(`d7df3b2`, default off; device acceptance in DESIGN v0.4.54). CI jniLibs integration
(`pack-apk-libs` output passed through artifacts to `-PandcodeNativeDir`), seccomp patching
(within the Tier P physicalization step, including idempotence checks), and conditional release signing (when all four secrets are present,
`assembleRelease` + `apksigner verify`) are in place. Two complete Tier M text+bash tool
round trips passed retesting with an explicit proxy+CA (DESIGN §4.2, root manual-diagnostic scope).

Key findings (2026-11-08 device debugging; details in DESIGN v0.4.2):
- **App-domain seccomp trap** (4.9-perf kernel + GSI): zygote seccomp sends SIGSYS directly for
  set_robust_list(99)/rseq(293)/clone3(435), killing glibc binaries at startup;
  bionic does not call them, so ordinary apps are unaffected. Fix = `scripts/patch-seccomp.sh` (idempotent,
  verifies before patching) + `GLIBC_TUNABLES=glibc.pthread.rseq=0`.
- **BUN_TMPDIR** (not TMPDIR) determines the extraction directory for Bun's embedded native libraries (libopentui).
  It must be app-writable; otherwise dlopen receives a /$bunfs virtual path and returns ENOENT.
- **run-as ≠ app domain**: run-as child processes lack zygote seccomp and cannot substitute for in-app validation.
- pack-bundle wrapper rendering previously lost the `#!` prefix (bare `/bin/sh` hung under a real tty);
  the launcher's proot branch had misaligned argv — both are fixed (commits b61e3d8, d226bbb).
- Tier M "500" and app-domain "500" share the same root cause: `--model openai/...` selects the wrong built-in
  provider; use `--model arjata/...` or omit it to use the configured default.
- **Provider `arjata/gpt-oss-120b` tool-path defect** (2026-11-11): continuations after tool results
  consistently return 400/503 (5/5 fresh sessions), while plain text (including multiple turns resending reasoning_content)
  works. A full agentic tool round trip passed on `glm-5.2` through the same gateway — opencode serialization is not at fault;
  this is a provider-side gpt-oss-120b routing issue. Use a model with a working tool path for agentic sessions for now.

Remaining:
1. Provider-side gpt-oss-120b tool continuations returning 400/503 (track this; do not bypass the protocol in the client).
2. TUI Pinyin IME composition intercepts adb injection and obscures the extra-key row (upstream behavior; injection works after switching to AOSP
   Latin IME, DESIGN v0.4.52).
3. PRoot serve acceptance on other devices and locked delivery forms (P0/P3).
4. User action: revoke exposed GitHub tokens (`ghp_...`) and API keys (`sk-...`).
