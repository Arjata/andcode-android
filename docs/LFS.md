# Git LFS 规则(docs/LFS.md)

> v1.0 · 2026-11-06 · 上位规则:AGENTS.md §2.5(二进制不入库)、REUSE.md §3(许可证)
> **定位**:LFS 不是"二进制入库"的后门,而是对 `.gitignore` + CI 工件 + `bundle/manifest`
> 这条主通道的**有限补充**——仅覆盖"必须随源码版本化、但体积大"的少量合法文件。

---

## 1. 为什么需要 LFS(以及为什么只用一点点)

本项目的二进制产物(bundle、APK、rootfs、重写后的 glibc 库)一律走:
**CI 工件(artifact)+ `bundle/manifest` 追踪**,版本库中只存在源码与配方。
这条原则保证:产物可复现(从基线构建)、许可证义务链清晰、仓库轻量。

但有两类文件**必须**与源码同步版本化,又不适合直接进 git:

| 类别 | 例 | 为什么要版本化 |
|---|---|---|
| 测试样张(test fixtures) | `tests/fixtures/*.elf`——check-compat/lint 的已知-good/已知-bad 样本 | 没有它们,门禁脚本在 CI 无法自测;样张改动必须与脚本改动同 commit 评审 |
| 文档图像 | `docs/img/*.{png,jpg}`——真机截图、架构图导出 | 文档是交付物(DESIGN/REUSE/NAMING),图像丢失即文档失效 |

除此之外的一切二进制:**禁止入库,禁止进 LFS**。

## 2. 白名单(仅此两类,新增须走 §5 流程)

```gitattributes
tests/fixtures/**/*.elf   → LFS
tests/fixtures/**/*.img   → LFS
docs/img/*.png / *.jpg    → LFS
```

## 3. 禁止清单(LFS 不许做的事)

| 禁止项 | 理由 | 正确通道 |
|---|---|---|
| 构建产物:`*.tar.*`、`*.apk`、`*.so`、`*.o`、`dist/`、`work/` | 违反 §2.5;产物必须可从基线复现 | CI 工件 + `bundle/manifest` |
| 密钥:`*.keystore`、`*.jks`、host key、`*.pub` | 安全红线,与 gitignore 一致 | 签名走 CI secrets |
| GPL-2.0 组件(busybox、proot)二进制 | 许可证义务链必须经 manifest 记录来源与版本,入库即失控 | CI 内从官方来源获取,manifest 登记 |
| 任何"图省事"临时塞进 LFS 的 ELF | 破坏可复现性 | 走基线构建 |

## 4. 尺寸阈值与执行

| 规则 | 阈值 |
|---|---|
| 允许直接进 git 的二进制(小 fixture) | ≤ **256 KB** |
| 超过 1 MB 的二进制文件 | 必须命中 LFS 白名单,或被 .gitignore 忽略;否则 CI 门禁 FAIL |
| 256 KB – 1 MB 且不在白名单 | 建议改小或归入白名单类,CI 给 warning |
| 白名单类内文件 | 不设上限,但单文件 > 50 MB 时须在 §5 流程中说明理由 |

执行者:`scripts/lfs-check.sh`(CI 卫生检查步骤),规则:
1. 非白名单、超阈值的二进制 → FAIL;
2. LFS 跟踪的文件必须与 .gitattributes 声明一致(`git lfs ls-files` 比对);
3. LFS 指针对象若损坏(`pointer` 文件出现在非 LFS 路径)→ FAIL;
4. 仓库未 `git init` 时降级为 1+3(静态扫描)。

## 5. 变更流程(新增/调整白名单类)

1. 修改本文件 §2 与理由;
2. 修改 `.gitattributes`(LFS 段);
3. 若与第三方相关,同步 REUSE.md §2 登记;
4. `scripts/lfs-check.sh` 通过后随 CI 评审;
5. **历史重写(`git lfs migrate`)属于改变仓库历史**:仅主代理在用户明确批准后执行。

## 6. CI/克隆注意事项

- `actions/checkout@v4` 默认**不拉取 LFS**;需要样张的 job 加 `with: lfs: true`;
- 当前 `ci/github-actions.yml` 卫生检查步骤以 `lfs: false` 运行即可(只做一致性
  与阈值检查,不消费对象);
- 贡献者首次克隆:`git lfs install` 后正常 clone;未安装 LFS 时
  `tests/fixtures/**` 呈指针文件,门禁脚本会明确报错提示,不静默失败。
