#!/usr/bin/env bash
# gen-notices.sh — 从 bundle/manifest 生成 THIRD-PARTY-NOTICES.md(NAMING §7.2 / REUSE §4)
# 用法: gen-notices.sh <manifest> [> output.md]
set -euo pipefail
MF="${1:?usage: gen-notices.sh <manifest>}"

cat <<'HEAD'
# THIRD-PARTY NOTICES

本交付包(andcode)包含的第三方组件及其许可信息。本项目本体以 AGPL-3.0-only 许可
(见仓库 LICENSE)。各组件的完整许可文本以所列上游仓库为准;GPL-2.0 组件(busybox、
proot)以**独立程序聚合**方式随包分发,源码获取地址见下表。

## 组件清单

| 逻辑路径 | 物理名(Tier P) | 类型 | 许可证 | 版本 | 上游 |
|---|---|---|---|---|---|
HEAD

# 跳过注释行;按 license、upstream 排序输出
grep -v '^#' "$MF" | grep -v '^$' | sort -t$'\t' -k4,4 -k6,6 | \
  awk -F'\t' '{ gsub(/\|/, "\\|", $1); gsub(/\|/, "\\|", $2);
    printf "| %s | %s | %s | %s | %s | %s |\n", $1, $2, $3, $4, $5, $6 }'

cat <<'FOOT'

## 许可证要点

- **MIT / Apache-2.0 / BSD-2-Clause 组件**(opencode、dropbear、jackpal、
  libandroid-shmem 等):随包分发,保留版权与许可声明。
- **LGPL 组件**(glibc、libtalloc):随包分发;对应源码可自上游获取
  (glibc 2.39: sourceware.org;libtalloc: samba.org)。
- **GPL-2.0 组件**(busybox、proot):以独立程序聚合方式随包分发,未修改;
  源码:busybox.net(1.36.1,Alpine busybox-static 构建与
  github.com/proot-me/proot)、github.com/proot-me/proot。
- 本项目原创物(shim、launcher、包装器、入口脚本、APK)以 AGPL-3.0-only 提供,
  完整文本见随附 LICENSE。

生成方式:`scripts/gen-notices.sh`(CI 自动,禁止手工编辑本文件)。
FOOT
