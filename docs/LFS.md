# Git LFS rules (docs/LFS.md)

> v1.0 · 2026-11-06 · Governing rules: AGENTS.md §2.5 (no binaries in the repository), REUSE.md §3 (licensing)
> **Purpose**: LFS is not a backdoor for committing binaries. It is a **limited supplement** to the primary
> `.gitignore` + CI artifacts + `bundle/manifest` workflow, covering only a small number of permitted large files that must be versioned with source code.

---

## 1. Why LFS is needed (and why its use is limited)

All binary artifacts in this project (bundles, APKs, rootfs, rewritten glibc libraries) use
**CI artifacts + `bundle/manifest` tracking**; the repository contains only source code and recipes.
This principle ensures reproducible artifacts (built from the baseline), clear licensing obligations, and a lightweight repository.

However, two types of files **must** be versioned alongside source code but are unsuitable for direct storage in git:

| Category | Example | Why versioning is required |
|---|---|---|
| Test fixtures | `tests/fixtures/*.elf` — known-good/known-bad samples for check-compat/lint | Without them, gate scripts cannot self-test in CI; fixture and script changes must be reviewed in the same commit |
| Documentation images | `docs/img/*.{png,jpg}` — device screenshots, exported architecture diagrams | Documentation is a deliverable (DESIGN/REUSE/NAMING); missing images invalidate it |

All other binaries: **prohibited in both the repository and LFS**.

## 2. Allowlist (only these two categories; additions require the §5 process)

```gitattributes
tests/fixtures/**/*.elf   → LFS
tests/fixtures/**/*.img   → LFS
docs/img/*.png / *.jpg    → LFS
```

## 3. Prohibited items (what LFS must not be used for)

| Prohibited item | Reason | Correct workflow |
|---|---|---|
| Build artifacts: `*.tar.*`, `*.apk`, `*.so`, `*.o`, `dist/`, `work/` | Violates §2.5; artifacts must be reproducible from the baseline | CI artifacts + `bundle/manifest` |
| Keys: `*.keystore`, `*.jks`, host keys, `*.pub` | Security boundary, consistent with gitignore | Use CI secrets for signing |
| GPL-2.0 component binaries (busybox, proot) | The manifest must record sources and versions to track licensing obligations; committing binaries defeats that control | Fetch from official sources in CI and register in the manifest |
| Any ELF temporarily placed in LFS for convenience | Breaks reproducibility | Build from the baseline |

## 4. Size thresholds and enforcement

| Rule | Threshold |
|---|---|
| Binaries allowed directly in git (small fixtures) | ≤ **256 KB** |
| Binary files larger than 1 MB | Must match the LFS allowlist or be ignored by .gitignore; otherwise the CI gate reports FAIL |
| 256 KB – 1 MB and not allowlisted | Reducing the size or placing the file in an allowlisted category is recommended; CI emits a warning |
| Files in allowlisted categories | No upper limit, but individual files > 50 MB require justification through the §5 process |

Enforced by `scripts/lfs-check.sh` (the CI hygiene step), with these rules:
1. Non-allowlisted binaries above the threshold → FAIL;
2. LFS-tracked files must match .gitattributes declarations (compare with `git lfs ls-files`);
3. Broken LFS pointer objects (`pointer` files appearing at non-LFS paths) → FAIL;
4. If `git init` has not been run, fall back to rules 1+3 (static scanning).

## 5. Change process (adding/adjusting allowlisted categories)

1. Update §2 of this file and its rationale;
2. Update `.gitattributes` (the LFS section);
3. For third-party material, synchronize the REUSE.md §2 registration;
4. After `scripts/lfs-check.sh` passes, review together with CI;
5. **History rewriting (`git lfs migrate`) changes repository history**: only the main agent may perform it, after explicit user approval.

## 6. CI/cloning notes

- `actions/checkout@v4` **does not fetch LFS by default**; add `with: lfs: true` to jobs requiring fixtures;
- The current hygiene step in `ci/github-actions.yml` can run with `lfs: false` (it checks only consistency
  and thresholds, without consuming objects);
- First clone for contributors: run `git lfs install`, then clone normally. Without LFS installed,
  `tests/fixtures/**` contains pointer files; the gate script reports an explicit error rather than failing silently.
