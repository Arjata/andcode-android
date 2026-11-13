#!/usr/bin/env bash
# lfs-check.sh — Git LFS hygiene checks (docs/LFS.md §4)
# Usage: lfs-check.sh [repo-root] (defaults to current directory; runs in CI or any clone)
# Rules:
#   1. Binary files > 1MB outside the LFS allowlist → FAIL (≤256KB pass; intermediate sizes warn)
#   2. LFS tracked files match .gitattributes declarations (checked when git-lfs is available)
#   3. LFS pointer files outside the allowlist → FAIL
# Before git init, fall back to static scanning with rules 1+3.
set -u

ROOT="${1:-.}"
cd "$ROOT" || exit 2

LIMIT=$((1024 * 1024))          # 1 MB FAIL threshold
SMALL=$((256 * 1024))           # 256 KB passes directly
BIG_WARN=$((50 * 1024 * 1024))  # 50 MB requires justification even on the allowlist (docs/LFS.md §4)

fail=0; warn=0

# Allowlist check: path patterns with filter=lfs in .gitattributes
in_lfs_whitelist() { # $1 = relative path
  grep -E 'filter=lfs' .gitattributes 2>/dev/null | while IFS= read -r line; do
    pat="$(printf '%s' "$line" | awk '{print $1}')"
    case "$1" in
      $pat) return 0 ;;
    esac
  done
  return 1
}

is_lfs_pointer() { # $1 = file; first line resembles version https://git-lfs...
  [ "$(head -c 6 "$1" 2>/dev/null)" = "versio" ] || return 1
  head -n 1 "$1" | grep -q '^version https://git-lfs'
}

# ── Rules 1+3: repository-wide scan ────────────────────────────────────────
while IFS= read -r -d '' f; do
  rel="${f#./}"
  case "$rel" in
    .git/*|*.md|*.sh|*.c|*.h|*.yml|*.yaml|*.tsv|*.tpl|Makefile|LICENSE|*.prop) continue ;;
  esac
  if is_lfs_pointer "$f"; then
    if ! in_lfs_whitelist "$rel"; then
      echo "[FAIL] 非白名单路径出现 LFS pointer: $rel"; fail=$((fail+1))
    fi
    continue
  fi
  size=$(wc -c < "$f")
  if [ "$size" -gt "$LIMIT" ]; then
    if in_lfs_whitelist "$rel"; then
      [ "$size" -gt "$BIG_WARN" ] && { echo "[WARN] LFS 文件 > 50MB,须在 docs/LFS.md §5 说明: $rel($size B)"; warn=$((warn+1)); }
    else
      echo "[FAIL] 非白名单二进制 > 1MB(走 CI 工件/manifest,或加入 LFS 白名单): $rel($size B)"; fail=$((fail+1))
    fi
  elif [ "$size" -gt "$SMALL" ]; then
    in_lfs_whitelist "$rel" || { echo "[WARN] 256KB–1MB 二进制建议减小或入白名单: $rel($size B)"; warn=$((warn+1)); }
  fi
done < <(find . -type f -print0)

# ── Rule 2: git-lfs consistency (requires a Git repository and git-lfs) ─────
if [ -d .git ] && command -v git-lfs >/dev/null 2>&1; then
  tracked="$(git lfs ls-files -n 2>/dev/null | sed 's#^\./##' | sort)"
  declared="$(git check-attr filter -- $(git ls-files) 2>/dev/null \
    | awk -F': filter: ' '$2=="lfs"{print $1}' | sort)"
  if [ "$tracked" != "$declared" ]; then
    echo "[FAIL] LFS 跟踪集与 .gitattributes 不一致"; fail=$((fail+1))
    diff <(printf '%s\n' "$declared") <(printf '%s\n' "$tracked") | head -20 || true
  fi
fi

echo "lfs-check: $([ $fail -eq 0 ] && echo PASS || echo FAIL)$([ $warn -gt 0 ] && echo "($warn warnings)")"
exit $([ $fail -eq 0 ] && echo 0 || echo 1)
