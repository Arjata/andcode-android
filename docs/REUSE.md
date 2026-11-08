# 可复用开源项目调研(docs/REUSE.md)

> 调研日期: 2026-11-06 · 许可证信息均于当日经 GitHub API / 源码 LICENSE 文件逐仓库核实
> 本项目许可证: **AGPL-3.0-only**(仓库根 `LICENSE` 已放置全文)
> v0.3 同步: 设计已去除 Termux 等第三方宿主依赖,清单角色相应调整。

---

## 1. 结论摘要

| 结论 | 说明 |
|---|---|
| ✅ 直接复用(并入/随包分发) | opencode(MIT)、bun(MIT)、dropbear(MIT,实测 LICENSE 原文)、jackpal 终端库(Apache-2.0)、termux-exec(Apache-2.0)——构成交付包核心,保留声明即可 |
| ⚠️ 独立程序聚合(不并源码) | busybox(GPL-2.0,静态单文件)、proot(GPL-2.0,兜底方案)——作为独立可执行文件随包分发,提供源码获取方式即合规;**禁止把其源码复制进本仓库** |
| 🔧 仅构建期使用(不随包分发) | patchelf(GPL-3.0,CI 内做 soname 重写)、termux-elf-cleaner(GPL-3.0,按需)——工具本身不进产物,无分发义务 |
| ⚠️ 参考实现 | termux-pacman/glibc-packages(MIT)——shim 与 sysroot 的对照基线;**Happ1ness-dev/bun-termux(MIT,★85,活跃)——Bun 无 proot 的最佳先行者**;termux-exec(Apache-2.0)——LD_PRELOAD 拦截参照 |
| ⬇️ 降级为可选 | Termux 系(GPLv3)——不再是宿主,仅作附录替代路径;作为"用户已装的第三方 App 被调用"时无义务 |
| ❌ 不可复用代码 | tribixbite/bun-on-termux、termux/termux-boot(未发现 LICENSE)、**CypherpunkArmory/UserLAnd(★4.3k,无 LICENSE = 保留所有权利)**——只观察行为/UX,不拷贝代码 |

---

## 2. 候选清单

### 2.1 交付包核心组件(宽松许可,随包分发)

| 项目 | 仓库 | 许可证 | 角色(对应 DESIGN §4) | 复用方式 |
|---|---|---|---|---|
| opencode | `sst/opencode` (★224.8k, 活跃) | MIT | 移植目标本体;官方发布含 linux-arm64 (glibc) 产物 | 直接运行其产物;需要时打补丁(补丁归本项目 AGPL) |
| opencode-pty | `anomalyco/opencode`, `packages/process-daemon`, tag `process-daemon-v0.4.0` (`5e6ee370634842e0efa99ad103c4d767581b47f0`) | MIT(2026-11-08 核对该版本 Cargo.toml/license 与 npm 包 LICENSE) | V2 Web 终端 daemon,协议 7;独立预置副本而非应用数据目录运行期释放 | 开发部署使用官方 aarch64-unknown-linux-gnu 资产,改写 PT_INTERP;`OPENCODE_PTY_BIN`/`OPENCODE_PTY_SOCKET_DIR` 为该版本上游已有配置,无需改源码;正式打包须登记生成 manifest 与 notices(尚待 CI 集成) |
| bun | `oven-sh/bun` (★96.6k, 活跃) | MIT(静态链接 LGPL-2 JavaScriptCore,按 LGPL 附声明与源码指引) | opencode 运行时;自建产物时的编译基座 | 仅从基线内使用/构建 |
| dropbear | `mkj/dropbear` (★2.5k, 活跃) | **MIT**(已核实 LICENSE 原文: Matt Johnston, MIT 风格授权) | 三种形态共用的内置 sshd(§4.7 交互入口) | 在基线内构建静态/动态版,随 bundle 分发 |
| termux-exec | `termux/termux-exec` (★268, 活跃) | **Apache-2.0**(LICENSE 实测:Apache-2.0 + MIT 组件) | **LD_PRELOAD 拦截参照实现**:Android 上多年的 LD_PRELOAD 工程实践,直接指导 §4.5 shim 的拦截面选择与坑位 | 参考实现;如取码按 Apache-2.0 附声明 |
| jackpal/Android-Terminal-Emulator | `jackpal/Android-Terminal-Emulator` (★3.2k) | **Apache-2.0** | Tier P APK 的终端模拟器核心(emulator/view 库可并入 AGPL 项目) | 最小 fork(上游 2022 年停更;现存 fork 全部停滞于 2014–2021,已核实),保留版权声明 |
| **Termux terminal-emulator / terminal-view(P3 终选,已并入)** | `termux/termux-app` 模块(★64.2k, 活跃) | **GPLv3** | P3 APK 的终端核心(jackpal 停更故改选) | GPLv3→AGPLv3 单向兼容,已并入 app/terminal-*(保留版权头,app/NOTICE-TERMINAL.md);合并作品整体 AGPL-3.0-only;本仓库公开即满足源码义务 |
| proot(Termux bionic 构建) | packages.termux.dev pool/main/p/proot | **GPL-2.0** | **Tier A/M 的 /etc 重定向正解**(真机 P0:LD_PRELOAD 无法拦截 glibc 内部 fopen("/etc/resolv.conf"),proot bind 实测打通 git https 全链路) | 独立程序聚合;proot + loader + libtalloc(LGPL-3.0)+ libandroid-shmem(**BSD-2-Clause**,termux/libandroid-shmem LICENSE 已核)随 bundle 分发,manifest 记录 |
| ConnectBot | `connectbot/connectbot` (★3.6k, 活跃) | Apache-2.0 | Tier A/M 的推荐 SSH 客户端(**可选工具,非依赖**) | 仅文档推荐 |

### 2.2 独立程序聚合(GPL-2.0,只随包放二进制 + 源码指引)

| 项目 | 仓库 | 许可证 | 角色 | 义务与边界 |
|---|---|---|---|---|
| busybox | `mirror/busybox` / busybox.net | GPL-2.0 | 交付包内静态粘合工具(sh/tar/readlink 等,§4.1.2) | **静态单文件独立程序**聚合;官方 `busybox.net/downloads/binaries/` 提供 arm64 静态预编译(实测可访问,采购来源之一,亦可在基线内自建锁版本);`manifest` 记录版本与源码地址;绝不并入源码 |
| GNU Bash | `https://ftp.gnu.org/gnu/bash/`, Ubuntu 源包 `https://ports.ubuntu.com/pool/main/b/bash/` | GPL-3.0-or-later(2026-11-08 核对 Ubuntu `bash_5.2.21-2ubuntu4_arm64.deb` 内 `usr/share/doc/bash/copyright`:Files * / GPL-3+) | Tier P 默认交互 shell,Ubuntu 24.04 基线 5.2.21;动态依赖 libtinfo(Ncurses,MIT/X11 及部分 BSD-3-Clause,同日核对 `libtinfo6_6.4+20240113-1ubuntu2_arm64.deb` copyright) | 独立 ELF 聚合,不取 Bash 源码;CI 收录 ELF/依赖、版权及完整 GPLv3 文本,manifest 标注真实包版本和源码池地址;发布仍须落实 GPL 对应源码提供义务,不以 URL 替代合规交付;不调用第三方宿主 Bash |
| proot | `proot-me/proot` (★2.7k) | SPDX 标注 GPL-2.0(only/or-later 待核实,行动项) | **兜底**:shim 覆盖不全时做最小 bind(§4.5) | 同 busybox 口径;若确认为 GPL-2.0-only,仍然可以"独立二进制聚合 + 源码提供"方式分发 |
| Ubuntu 24.04 arm64 开发 rootfs | Docker Official Image `ubuntu:24.04`,Ubuntu `noble`/`noble-updates`/`noble-security` | 多许可证独立程序聚合,不得整体标成 AGPL;2026-11-09 按镜像内 dpkg 数据库与 `/usr/share/doc/*/copyright` 逐包追踪,发布合规尚待审查 | root chroot 原型包含 apt、Bash、ca-certificates、curl、git、build-essential、python3、util-linux | 新配方仅从官方源 apt 安装,保留 copyright/common-licenses,生成包版本/源包清单及镜像 digest;CI 工件仅用于验证,正式分发前必须提供各 GPL/LGPL 包对应源码及变更,不能以包清单或源码 URL 代替履约;PRoot 不复用 chroot 可写实例 |
| Ubuntu Base 24.04.4 arm64(开发实机引导) | `https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.4-base-arm64.tar.gz` | 同上,保留包内 copyright/common-licenses;2026-11-09 核对官方 HTTPS SHA256SUMS 与下载归档 | 无本地 Linux/Docker 时的设备开发验证入口,不是 CI 镜像来源替换 | 固定 SHA-256 `04207713ece899c3740823d33690441ad3a7f0ded1101aca744e2b0f37ac7ff2`;只在隔离新 ext4 镜像提取,保留源信息/包清单,正式发布仍须逐包合规 |

### 2.3 参考实现(谨慎取材)

| 项目 | 仓库 | 许可证 | 价值 | 备注 |
|---|---|---|---|---|
| claude-code-termux | `naiyQAQ/claude-code-termux` (★22) | MIT | **最接近的先行者**:Bun 编译的 AI 编码 CLI 在 Termux 上宣称原生跑通(不经 proot)——P0 精读其环境处理与 shim 思路 | MIT,可复用代码但须保留声明 |
| **bun-termux** | `Happ1ness-dev/bun-termux` (★85, 活跃至 2026-11) | **MIT** | **最佳先行者**:Bun 在 Termux 上无 proot 运行的工具与指南,社区关注度最高——P0 首选精读对象 | MIT,可复用代码但须保留声明 |
| termux-pacman/glibc-packages | `termux-pacman/glibc-packages` (★300) | MIT | Termux 下成熟 glibc 打包;我们 §4.5 shim 的**对照测试基线**与库路径实践参考 | sysroot 改由基线 rootfs 抽取,以保 glibc 2.39 一致;此仓库作对照 |
| bun-on-termux | `tribixbite/bun-on-termux` (★29) | **无许可证** | Bun on Termux 思路参考 | 默认版权保护,只能看不能拷 |
| glibc-runner 生态 | `dbgid/glibc-runner-termux`(GPL-3.0)等 | GPL-3.0 / MIT | loader/库路径包装(`grun`)的成熟实践,印证 §4.1.2 包装器与 §6.3 路线甲 | 思路参考为主 |
| glibc-wine / androBox 等 | `airidosas252/glibc-wine`、`Pipetto-crypto/androBox` | MIT / GPL-3.0 | glibc-on-Android 生态的 loader/库路径实践 | 印证 §4.1.2 包装器设计 |
| UserLAnd | `CypherpunkArmory/UserLAnd` (★4.3k, 活跃) | **无 LICENSE(保留所有权利)** | **架构观察对象**:在普通 APK(无 root)里跑完整 Linux 发行版的商业级先例——其 jniLibs/提取/进程管理行为可逆向观察,不可取码 | 仅观察 UX 与公开文档;列为行动项:P3 前实测其 targetSdk 与执行策略作对照 |

### 2.4 降级为可选 / 评估后放弃

| 项目 | 状态 | 原因 |
|---|---|---|
| Termux (`termux/termux-app`, GPLv3-only) | **降级**:附录可选路径 | v0.3 设计原则:不依赖第三方宿主 App。若用户自装 Termux 跑 bundle,属第三方聚合,我们无义务 |
| proot-distro (`termux/proot-distro`, GPL-3.0) | 降级 | 同上;rootfs 改由我们自己的 `make-rootfs.sh` 生成,可控且与基线同源 |
| Magisk (`topjohnwu/Magisk`, GPL-3.0) | 仍为 Tier M 依赖平台 | 只按官方模块格式写脚本模块(脚本归本项目 AGPL),不修改 Magisk 本体 → 无源码义务 |
| Termux:Boot (`termux/termux-boot`, 无 LICENSE) | **弃用** | 自启动改由 Magisk service.sh(Tier M)/ 前台服务(Tier P)承担,消除该风险 |
| `meefik/linuxdeploy` (GPL-3.0) | 放弃 | 2022 年后停更;功能被我们的 make-rootfs.sh + Magisk 模块覆盖 |
| termux-elf-cleaner (`termux/termux-elf-cleaner`, GPL-3.0) | **按需**:仅构建期备用 | 我们交付的 ELF 由 glibc loader 解析而非 Android linker,通常无需清洗;若 Tier P 出现 Android 侧解析警告再引入(CI 内使用,不分发) |
| actions/runner-images (`actions/runner-images`, MIT) | 采用 | CI 的 `ubuntu-24.04-arm` runner 镜像来源,无需额外动作 |
| Andronix / AnLinux | 放弃 | 许可证混乱、与自建脚本重复 |
| box64/box86 | 放弃 | 面向 x86→ARM 转译,我们是原生 arm64 |

---

## 3. AGPL-3.0 合规规则(本项目执行口径)

1. **本项目全部原创物**(设计文档、bundle/pack 脚本、shim、Magisk 模块脚本、APK、
   jackpal fork 的修改)→ AGPL-3.0-only。
2. **MIT/BSD/Apache 代码**(opencode、dropbear、jackpal 等)→ 可并入,保留版权
   与许可声明;并入后整体受 AGPL 约束(对下游)。
3. **LGPL 依赖**(glibc、JavaScriptCore)→ 动态链接/随包分发允许,附许可文本与
   对应源码获取方式。
4. **GPL-2.0 独立程序**(busybox、proot)→ 仅以**独立二进制聚合**方式随包分发,
   `manifest` 提供精确版本号与源码地址(满足 GPL 源码提供义务的"书面offer"路径);
   不修改、不并入源码。若未来必须修改,需独立 GPL-2.0 仓库分离发布。
5. **GPLv3 平台**(Magisk)→ 只写其标准格式的脚本模块(脚本归 AGPL),不碰平台源码。
6. **无许可证仓库** → 一律不取代码,只参考行为思路。
7. 每次发布自动生成 `THIRD-PARTY-NOTICES.md`(CI 从 `bundle/manifest` 收集),并在
   APK"关于"页内置 notices 查看入口。

---

## 4. 行动项

状态(2026-11-06):**P1 完成,CI 全绿**(run 42142198520)。已完成:
- [x] CI 全链路(rootfs→bundle→审计→门禁→冒烟→Tier P patchelf 路线甲→发布工件);opencode 资产名实测核实为 `opencode-linux-arm64.tar.gz`(v1.19.5)
- [x] busybox 静态来源落地:Alpine `busybox-static` 包(`busybox.static`,manifest 记录来源)
- [x] `bundle/manifest` + naming-lint + check-compat 门禁随 CI 强制
- [x] `andcode-doctor` JSON 输出收敛(仅 stdout 单一对象)

待办:
- [ ] P0:精读 `Happ1ness-dev/bun-termux`(MIT,首选)与 `claude-code-termux`(MIT)的 shim/环境处理,验证"无 proot 裸 sysroot 跑 Bun"路线
- [ ] P0:对照 `termux-exec`(Apache-2.0)设计 shim 拦截面(open/openat/stat/execve),列出坑位清单
- [ ] P0:核实 `proot-me/proot` LICENSE 原文(only vs or-later),决定兜底路径的分发措辞
- [ ] P0:实测 busybox 静态 arm64(GPL-2.0,官方 binaries 或基线自建)在 `/data/local/tmp`(Tier A)的执行情况;数据目录 exec 已被平台禁止,不再适用(Tier P 走 jniLibs)
- [ ] P0:实测 jniLibs 提取(`lib*.so` → nativeLibraryDir)在 targetSdk 37.2 下的执行;验证 W^X 下 Bun/JSC JIT 或 `BUN_JSC_useJIT=0` 回退
- [ ] P0:核实 opencode 运行期是否释放 ELF(TUI 等)及其预置路径机制(§4.1 约束)
- [x] P0:**git https 助手链路——已解决(真机 2026-11-06)**:三层修复——①helper 改静态 musl launcher(规避 shell spawn 异常);②proot bind /etc(LD_PRELOAD 无法拦截 glibc 内部 fopen 的架构修正,DESIGN §4.5 已改);③`options use-vc`(测试网络阻断 UDP 53 出站)。`git ls-remote https://github.com/...` 真机返回 HEAD
- [ ] P3:jackpal 终端库最小 fork 建仓(Apache-2.0 保留声明),仅保留 TUI 会话所需路径;实测 UserLAnd 的执行策略作对照(仅观察)
- [ ] 发布前:复查 dropbear/bun LGPL 部分的 notices 完整性;APK 关于页内置查看入口
