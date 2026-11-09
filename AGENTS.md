# AGENTS.md — 本仓库的编码代理工作规则

面向在本仓库工作的 AI 编码代理(OpenCode 等)。规则分三档:
**硬约束(违反即返工)/ 工作流程 / 环境事实**。背景知识在 docs/,本文件只放"必须遵守"。

## 0. 项目一句话

把 opencode(AI 编码代理)移植到 Android arm64,并提供 Ubuntu 24.04 arm64(glibc 2.39)
兼容性构建基线——产物同时可跑在标准 Linux arm64 上。三种自包含交付形态:
Tier M(Magisk 模块,root)/ Tier A(adb 直推包,locked)/ Tier P(自研 APK,locked)。

## 1. 必读文档(按任务类型)

| 任务 | 先读 |
|---|---|
| 任何涉及**可执行入口、命令名、环境变量、物理文件名**的改动 | `docs/NAMING.md`(§3 注册表 → §6 slug 算法 → §8 门禁) |
| 引入/替换**第三方代码或二进制** | `docs/REUSE.md`(§2 清单 → §3 AGPL 合规口径) |
| 需要**把二进制文件放入库**(含 LFS) | `docs/LFS.md`(§2 白名单 → §3 禁止清单 → §5 变更流程) |
| 改动**架构、运行时行为、平台约束**相关代码 | `docs/DESIGN.md` 对应章节(§1.2 平台硬约束、§4 形态) |
| 打包/CI/审计脚本 | `bundle/pack-*.sh`、`baseline/check-compat.sh`、`scripts/naming-lint.sh` 现有实现风格 |

文档与代码不一致时:以 NAMING.md 为命名仲裁,DESIGN.md 记录版本化变更(改架构必须
在文件头 changelog 追加一行),不要让文档静默过时。

## 2. 硬约束(违反即返工)

1. **许可证 = AGPL-3.0-only**(根 `LICENSE`)。取材规则(REUSE.md §3)要点:
   - MIT/Apache/BSD 可并入,须保留版权声明并登记 `bundle/manifest`;
   - **GPL-2.0 代码(busybox、proot)禁止复制进仓库**——只允许"独立二进制聚合 +
     manifest 记录版本与源码地址";
   - **无 LICENSE 仓库(如 UserLAnd、bun-on-termux)禁止取码**,只观察行为;
   - 新增第三方依赖必须先写入 REUSE.md §2 并注明许可证核实方式与日期。
2. **命名规范承重**:新增任何命令/脚本/环境变量/物理名,必须先在 NAMING.md
   §3–§5 注册,再写代码;`bundle/manifest` 的 `physical-tier-p` 必须匹配
   `^libandcode-[a-z0-9-]+\.so$`(≤64 字符)。CI `naming-lint.sh` 不通过 = 构建失败。
3. **兼容性红线**(DESIGN §1.2/§3.1):
   - glibc 符号版本 ≤ **2.39**;禁止链接 Android NDK/Bionic;
   - PT_LOAD 段对齐 ≥ 16K(自有 NDK 代码编译参数 `-Wl,-z,max-page-size=16384`);
   - **targetSdk 37.2 平台约束**:数据目录禁止 exec → 运行期不得产生"会被 exec 的
     ELF";禁止依赖运行期解包 ELF 的行为(opencode 如有,必须预置副本 + 指路);
   - 自研 LD_PRELOAD shim(`bundle/shim/`)是 /etc 只读问题的正解,不要引入 proot,
     除非 shim 被证明覆盖不了(先在 P0 清单留证)。
4. **自包含原则**:不引入对 Termux / proot-distro / 任何第三方宿主 App 的依赖;
   运行时只允许依赖交付包内组件 + Android 系统自带(/system/bin/sh、getprop 等)。
5. **二进制不入库**:.gitignore 已覆盖;任何产物经 CI 工件与 `bundle/manifest` 追踪,
   发现仓库里出现 `.so`/`*.tar.*`/密钥文件,先删再查 .gitignore 是否有漏。
   **Git LFS 也不例外**:LFS 仅限 docs/LFS.md §2 白名单(测试样张/文档图像),
   不得用它绕过本条;违规由 `scripts/lfs-check.sh` 在 CI 拦截。

## 3. 工作流程

- 改动交付物链路(rootfs → bundle → jniLibs)后,验证顺序:
  1. `bash -n` 全部改动的 shell 脚本;
  2. `scripts/naming-lint.sh --bundle-dir <解包目录>`;
  3. `baseline/check-compat.sh --page-align <bin|lib 目录>`;
  4. 让 CI(`ci/github-actions.yml`)跑通——它是唯一可信执行环境(见 §4)。
- 设备相关验证(Tier A/M/P 实机冒烟)本机无法执行:**未实测的设备行为必须在
  交付说明中标注"待 P0/P3 实机验证",禁止声称已验证**。
- 修改 `docs/DESIGN.md` 架构章节时,在文件头 changelog 追加版本行(v0.x 递增),
  并同步 README 与受影响文档的交叉引用。
- 提交(commit)规则见下节;命名/许可证等术语与 NAMING.md、REUSE.md 注册表保持一致。

### 提交(commit)规则

**提交权限**:
- 主代理(main agent)可在**已评审、已适当验证的连贯集成检查点**创建提交;
- 一级/二级子代理**默认禁止** `git commit`、amend 或任何改变仓库历史的操作,
  除非用户或主代理给出明确的任务级授权;默认把改动留在共享工作树,
  向上级报告改动路径与聚焦验证结果;
- 获授权的子代理提交必须限定在其被分配的写入集(write set)内,并向父级
  报告 commit hash、包含路径与验证结果;主代理保留集成评审与后续全仓库提交的责任。

**提交信息格式**——默认单行主题 + 空行 + 扁平变更列表:

```text
feat: add serialization abstraction and JSON codec

- Add format-neutral serialization::Value and serialization::Codec public APIs
- Add json::Codec plus parse/dump helpers while hiding nlohmann/json in src
- Update Logger and table helpers to use serialization::Value instead of nlohmann/json
- Keep third-party include dependencies private to the library build targets
- Add JSON serialization tests and update table coverage
```

规则:
1. 首行 `<type>: <summary>`,type 优先取 `feat`、`fix`、`refactor`、`docs`、
   `test`、`chore`;
2. summary 用简洁英文祈使句描述核心变更,避免含糊标题;
3. 主题后空一行,再用 `- ` 列出关键变更;
4. 每条聚焦一个明确变更;以"改了什么"为主,作用域/影响仅在有用时提及;
5. 相邻条目连续、不空行;仅在有意区分不同散文或变更组时才在正文内空行;
6. 列表扁平,不嵌套;
7. 很小的提交可只用主题行;跨模块/跨层或含测试新增的提交必须带变更列表;
8. 除非用户明确要求,不含无关背景与冗长过程记录;
9. 助手署名提交:正文后空一行,追加
   `Co-authored-by: <assistant name> <assistant email>` 尾注,
   采用当前平台或项目的身份约定。

## 4. 环境事实

- 开发主机是 **Windows(pwsh),无本地 Linux shell/WSL 分发版**——不要在本机执行
  bash 脚本做验证;真实验证在 GitHub Actions 的 `ubuntu-24.04-arm` 原生 runner。
- 仓库尚未 `git init`;CI 首跑会真实校验脚本语法与全链路。
- shell 脚本必须 **LF**(见 `.gitattributes`);shebang 涉及设备侧的脚本要 POSIX sh
  兼容(用 `/system/bin/sh` 可执行的子集,禁止 bashism——`smoke-test.sh`、
  `bundle/overlay/sbin/*` 属于此类)。
- Communicate with the user in Chinese. Write all new or updated documentation and
  code comments in English. Keep commit messages in English and terminology consistent
  with the NAMING.md registry (`andcode-`, `libandcode-*`, `ANDCODE_*`, Tier M/A/P).

## 5. 当前进行时(待办,动手前先认领)

状态(2026-11-08):**P0/P1/P2 完成 + P3 里程碑达成**——**opencode TUI 已在
自研 APK 终端内完整渲染并可用**(Tier P,真机截图验证;模型会话端到端 ✓)。
Tier A 冒烟 7/7、git https、Tier M 安装+doctor 均已真机验证。Release v0.1.1。

关键知识(2026-11-08 真机攻坚,详见 DESIGN v0.4.2):
- **应用域 seccomp 陷阱**(4.9-perf 内核 + GSI):zygote seccomp 对
  set_robust_list(99)/rseq(293)/clone3(435) 直接 SIGSYS,glibc 二进制启动即死;
  bionic 不调用故普通 App 无感。修复 = `scripts/patch-seccomp.sh`(幂等,
  校验后打补丁)+ `GLIBC_TUNABLES=glibc.pthread.rseq=0`。
- **BUN_TMPDIR**(非 TMPDIR)决定 Bun 内嵌原生库(libopentui)提取目录,
  必须应用可写;否则 dlopen 拿到 /$bunfs 虚拟路径 ENOENT。
- **run-as ≠ 应用域**:run-as 子进程无 zygote seccomp,不能替代应用内验证。
- pack-bundle wrapper 渲染曾丢 `#!` 前缀(真 tty 下裸 `/bin/sh` 卡死);
  launcher proot 分支 argv 错位——均已修(见提交 b61e3d8、d226bbb)。
- Tier M "500" 与应用域 "500" 根因相同:`--model openai/...` 指错内置
  provider;应使用 `--model arjata/...` 或省略(走配置默认)。

剩余:
1. **P3 收尾**:bundle 完整 jniLibs 集成(opencode/git/proot/libtalloc 入
   nativeLibraryDir,pack-apk-libs 输出对接 gradle);**seccomp 补丁并入 CI
   打包链**(fresh bundle 部署后自动执行 patch-seccomp.sh);release 签名;
   TUI 内adb 注入按键不可达(Termux extraKeys/IME 接线未移植,人工触屏可用)。
2. **P2 收尾**:Tier M 会话复测(此前 "500" 系模型旗标错,修复后待真机复跑)。
3. 用户侧:撤销已暴露的 GitHub token(`ghp_...`)与 API key(`sk-...`)。
