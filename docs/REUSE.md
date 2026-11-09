# 可复用开源项目调研(docs/REUSE.md)

> 调研日期: 2026-11-06 · 许可证信息均于当日经 GitHub API / 源码 LICENSE 文件逐仓库核实
> 本项目许可证: **AGPL-3.0-only**(仓库根 `LICENSE` 已放置全文)
> v0.3 同步: 设计已去除 Termux 等第三方宿主依赖,清单角色相应调整。

---

## 1. 结论摘要

| 结论 | 说明 |
|---|---|
| ✅ 直接复用(并入/随包分发) | opencode(MIT)、bun(MIT)、dropbear(MIT,实测 LICENSE 原文)、jackpal 终端库(Apache-2.0)、termux-exec(Apache-2.0)——构成交付包核心,保留声明即可 |
| ⚠️ 独立程序聚合(不并源码) | busybox(GPL-2.0,静态单文件)、proot(GPL-2.0,兜底方案)——作为独立可执行文件随包分发,仍须落实适用 GPL 对应源码交付义务;上游 URL 不是合规批准;**禁止把其源码复制进本仓库** |
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
| opencode V2.2.6 | `anomalyco/opencode`, tag `v2.2.6` | MIT(2026-11-09 核对该 tag LICENSE) | 与旧版分开的 Web/serve 固定载荷 | 官方 linux-arm64 归档固定 SHA-256 `f2d27600c367e45057d6a16f6a5c2aa8d77b41a9b10d4bc3d849c2f88870e944`;CI 预置为 oc2.bin,不在设备下载 |
| opencode-pty | `anomalyco/opencode`, `packages/process-daemon`, tag `process-daemon-v0.4.0` (`5e6ee370634842e0efa99ad103c4d767581b47f0`) | MIT(2026-11-08 核对该版本 Cargo.toml/license 与 npm 包 LICENSE) | V2 Web 终端 daemon,协议 7;独立预置副本而非应用数据目录运行期释放 | 开发部署使用官方 aarch64-unknown-linux-gnu 资产,改写 PT_INTERP;`OPENCODE_PTY_BIN`/`OPENCODE_PTY_SOCKET_DIR` 为该版本上游已有配置,无需改源码;正式打包须登记生成 manifest 与 notices(尚待 CI 集成) |
| bun | `oven-sh/bun` (★96.6k, 活跃) | MIT(静态链接 LGPL-2 JavaScriptCore,按 LGPL 附声明与源码指引) | opencode 运行时;自建产物时的编译基座 | 仅从基线内使用/构建 |
| V2 源码预置扩展实验 | `anomalyco/opencode` v2.2.6 提交 `dc2ffcf8bf26f9e669b6aa22b95f50e12be15e06` | MIT;2026-11-09 核对该 tag LICENSE | 手动 CI 从固定源码及 frozen lockfile 构建,不替代当前官方载荷 | Bun 1.4.4 arm64 归档固定 SHA-256 `baa6bb36f51d6e58561e02bbea825038a9df454f673d6d776e8bbf86f8c7850e`;保留上游 LICENSE/lockfile,未完成传递原生库合规/兼容审计前仅作实验 |
| V2 内嵌原生扩展(实验拆分) | OpenTUI 0.8.1、Parcel watcher 2.5.1、bun-pty 0.4.11、fff-bun 0.10.5 | **OpenTUI 原生包为 MIT AND LGPL-2.1-or-later,不是仅 MIT**;其余 npm metadata 为 MIT。2026-11-09 对固定版本 tarball 校验 registry SHA-512 后检查包内许可证:watcher/bun-pty 附 MIT;fff 平台包未附 LICENSE,不能仅凭 metadata 批准分发 | 将文件导入改为 nativeLibraryDir 显式加载,不伪装临时文件、不让 Bun 运行期释放 ELF | 不取第三方代码入库;OpenTUI 还附 LICENSE-FFMPEG/GHOSTTY/LCMS2/LIBWEBP/STB/WUFFS/ZLIB,需分别追踪源码/构建与重链接义务;传递 Rust/C/C++ notices 和对应源码尚未审查,不得称正式可分发闭包 |
| dropbear | `mkj/dropbear` (★2.5k, 活跃) | **MIT**(已核实 LICENSE 原文: Matt Johnston, MIT 风格授权) | 三种形态共用的内置 sshd(§4.7 交互入口) | 在基线内构建静态/动态版,随 bundle 分发 |
| termux-exec | `termux/termux-exec` (★268, 活跃) | **Apache-2.0**(LICENSE 实测:Apache-2.0 + MIT 组件) | **LD_PRELOAD 拦截参照实现**:Android 上多年的 LD_PRELOAD 工程实践,直接指导 §4.5 shim 的拦截面选择与坑位 | 参考实现;如取码按 Apache-2.0 附声明 |
| jackpal/Android-Terminal-Emulator | `jackpal/Android-Terminal-Emulator` (★3.2k) | **Apache-2.0** | Tier P APK 的终端模拟器核心(emulator/view 库可并入 AGPL 项目) | 最小 fork(上游 2022 年停更;现存 fork 全部停滞于 2014–2021,已核实),保留版权声明 |
| **Termux terminal-emulator / terminal-view(P3 终选,已并入)** | `termux/termux-app` 模块(★64.2k, 活跃) | **GPLv3** | P3 APK 的终端核心(jackpal 停更故改选) | GPLv3→AGPLv3 单向兼容,已并入 app/terminal-*(保留版权头,app/NOTICE-TERMINAL.md);合并作品整体 AGPL-3.0-only;本仓库公开即满足源码义务 |
| proot(Termux bionic 构建) | packages.termux.dev pool/main/p/proot | **GPL-2.0** | **Tier A/M 的 /etc 重定向正解**(真机 P0:LD_PRELOAD 无法拦截 glibc 内部 fopen("/etc/resolv.conf"),proot bind 实测打通 git https 全链路) | 独立程序聚合;proot + loader + libtalloc(LGPL-3.0)+ libandroid-shmem(**BSD-2-Clause**,termux/libandroid-shmem LICENSE 已核)随 bundle 分发,manifest 记录 |
| ConnectBot | `connectbot/connectbot` (★3.6k, 活跃) | Apache-2.0 | Tier A/M 的推荐 SSH 客户端(**可选工具,非依赖**) | 仅文档推荐 |

源码实验 CI 的 `collect-opencode-native-licenses.py` 对四个固定原生导入逐一核对
安装源字节/包名/版本/声明许可，将包内顶层 LICENSE*/COPYING*/NOTICE* 与 package.json
保存在诊断工件 `native-license-evidence/`，并生成 `native-license-review.json`。
缺声明记为 `blocked-missing-package-notice`，有声明仍为 `blocked-transitive-review`；
`redistributionApproved` 始终 false。它不是传递源码审查，也不覆盖 Bun/JS/Web 整体依赖，
不能把 CI 成功或收集到 LICENSE 理解为合规交付完成。

2026-11-09 固定原生包进一步源码定位(仅证据，**不批准分发**)：以下 commit
来自对应精确版本的 npm registry `gitHead`，并读取该 commit 的文件；metadata
关联不等于证明已下载 ELF 确由这些源码/配置构建，也不代替对应源码交付。

| npm 包 | 固定源码候选 | 已检查的构建输入及剩余边界 |
|---|---|---|
| `@opentui/core-linux-arm64@0.8.1` | `anomalyco/opentui@9a09079c0c7ad0fb2d55404f66a5c453204328dd` | `packages/native/build.zig`、`build.zig.zon`、`scripts/build-ffmpeg.ts` 与 `src/vendor/ffmpeg/README.md`；FFmpeg 为静态对象，不是独立动态依赖；还有 Yoga、Ghostty、uucode、miniaudio 等，不能只按平台包八份声明推断闭包完整 |
| `@ff-labs/fff-bin-linux-arm64-gnu@0.10.5` | `dmtrKovalenko/fff@459ebcdbdba094843fe5339a1a7f7dae4ced2d82` | 根 `LICENSE` 为 MIT、Copyright 2025 Dmitriy Kovalenko，可作为平台包缺失声明的补充来源候选；`crates/fff-c/Cargo.toml` 和 workspace 声明 vendored-libgit2、Rust 依赖等，仍须按实际启用 feature/目标逐项追踪，根 MIT 不覆盖所有静态依赖 |
| `bun-pty@0.4.11` | `sursaone/bun-pty@a582ae17cc6c41cb890b142c48669936541339c7` | `rust-pty/Cargo.toml` 使用 portable-pty 0.8.1、crossbeam、serde 等；须由该目录 Cargo.lock 加实际 feature/目标确定闭包，而非只读顶层 MIT |
| `@parcel/watcher-linux-arm64-glibc@2.5.1` | `parcel-bundler/watcher@119f1ff04bb41c2369929e37274900c61b0a9f49` | `binding.gyp` 的 Linux 分支编入 watchman/BSER、BruteForce、Inotify、legacy C++ 文件，另有 node-addon-api 头文件及 C++ 运行库；须保留各源文件声明并核对实际构建版本 |

OpenTUI 上述固定构建脚本声明 FFmpeg **9.0.2**，源归档
`https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz`，SHA-256
`8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e`；
zlib **1.3.2**，`https://zlib.net/fossils/zlib-1.3.2.tar.gz`，SHA-256
`bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16`。
这些固定值已于 2026-11-09 通过对应官方 HTTPS 归档下载并复核 SHA-256，
尚未在本项目重建或证明与平台包 ELF 对应。
脚本对 FFmpeg 关闭 GPL/version3/nonfree，启用静态解码库并把对象逐项链接进
libopentui；因此不能用“libopentui 动态加载”免除其内部 LGPL 静态组合义务。
应提供该库准确对应源码、补丁、依赖、构建工具/配置及可操作的修改后重链接路径
(或符合适用条款的对象材料)，并核实最终 APK 对替换修改版库的限制；Bun/JSC
亦须独立处理。仅保留下载 URL 或附一份 LGPL 文本不构成此项完成。

`collect-opencode-native-sources.py` 将以上四份候选源码归档按固定 SHA-256 收入
诊断工件，并收录 FFmpeg/zlib 固定源码归档；同时记录按文件名发现的声明、构建输入、全量 Cargo.lock 包索引以及
OpenTUI 内嵌 zig-deps 归档中的声明。四份源码归档于 2026-11-09 通过 HTTPS
下载并计算摘要后固定；它不证明 npm ELF 的可重现对应关系，不把 lockfile 全表
误当成目标 feature 闭包，也不把声明文件名扫描当成逐文件完整版权审查。
报告 `native-source-review.json` 的 `redistributionApproved` 始终 false。

2026-11-09 候选 Rust 目标证据：固定源码的 bun-pty `publish.yml` 使用
`aarch64-unknown-linux-gnu.2.17`、默认 feature；fff `release.yaml` 的 C FFI
使用 `aarch64-unknown-linux-gnu.2.31 -p fff-c --no-default-features --features zlob`，
不是默认 ripgrep。新增 Cargo normal/build 目标树收集器，以 glibc Rust target
解析候选依赖(不编译、不执行 build.rs)，按 Cargo.lock SHA-256 保存 crate
归档及声明/构建输入索引。fff 候选图含 `option-ext` MPL-2.0、vendored-libgit2、
LMDB、zlob；crate 顶层 MIT/Apache 声明不能覆盖内嵌 C/Zig 代码，也不能据此
断言它们已进入 npm ELF。宿主 build/proc-macro 图受 Cargo 运行主机影响，可信
Linux CI 才是 arm64 Linux 候选基线；仍需准确二进制对应、逐文件及构建/重链接审查。
本机同 target 的预审树选中 bun-pty 38 项(37 registry)、fff 121 项(117 registry)，
所有 registry 归档通过 lock 摘要检查；按文件名未发现 serial、glidesort、heed、
heed-traits、heed-types、zlob 的独立声明文件。此项只表示声明文件名扫描缺口，
不等于代码没有许可证；须逐文件/准确上游补充来源审查，不能按 Cargo metadata 放行。
同日读取固定 crate 原文：`libgit2-sys 0.18.7+1.9.6/libgit2/COPYING` 明确为
**GPL-2.0 + unlimited linking exception**(不是 crate 顶层 MIT/Apache)；
`lmdb-master-sys 0.2.5/lmdb/libraries/liblmdb/LICENSE` 为 **OpenLDAP Public
License 2.8**，另有 COPYRIGHT。归档仅在外部临时审查目录/CI 诊断工件，不复制
GPL-2.0 源码入本仓库；fff 中的静态组合、例外适用范围、对应源码与声明义务
仍须单独确认，不能把 linking exception 当作无需许可审查或自动正式分发的许可。
对 `.cargo_vcs_info.json` 固定提交进一步核对，heed/heed-traits/heed-types 和 zlob
仓库根 LICENSE 均为 MIT，可作归档缺失声明的补充候选(逐提交 SHA-256 由收集器
固定并保留原文)；glidesort 对应提交根目录未找到声明文件，serial 无随包 VCS
定位信息(后续按全 crate 文件匹配补证，见下文)。补充来源不证明二进制对应，也不覆盖所有内嵌代码。
后续核对 serial-rs `v0.4.0` annotated tag 指向
`7ed6540c2789b7c7365cd7a89fcb7bac7c567de8`，固定源码归档 SHA-256
`c8ff1c33d84c0b8a6ee461bcf00d60ec14639856dcd21a14ce29ec5d215b1797`；
serial 0.4.0 crate 全部 6 个普通文件与该提交 `serial/` 子目录同名文件逐字节相同。
该提交根 MIT LICENSE SHA-256
`871afd9d691846de71e0b83812ba9c7ff00bc7b3ad102dedcaa109f2246d52ad` 可据此作为
精确 crate 的补充声明，收集器重新验证全部文件与摘要；不代表 PTY ELF 整体批准。
crate 证据索引同时记录 `build.rs` 和 `.cargo_vcs_info.json` 摘要，便于复核
实际原生构建分支及补充声明提交；收集器从不执行这些构建脚本。
CI `42544621101` 的 arm64 Linux 候选树为 bun-pty 38/37 registry、fff 120/116
registry(与 Windows host 预审相差 1 项)；registry 源码摘要全部复核，报告仍为
blocked。该轮 upload-artifact 默认漏传展开候选源码的 dotfiles，导致全文件
manifest 不闭合，不能作为完整诊断包；已显式保留隔离 stage 内固定源码的 dotfiles。
修复后 CI `42545320876`(提交 `16a3d19`)全成功，工件 ZIP SHA-256
`eaf7f920ad9cbcf9af64fe832b612f7e181821a25a720c8240a6fd59b7ae6e65` 与 API
一致；600 项全文件摘要、两组 registry 归档摘要和 4 份补充声明均核验通过，
源码/许可/运行库报告仍不批准分发，未部署到设备或作为正式 APK 输入。

下一阶段 bun-pty 实验重建仅使用上述固定归档与 Cargo.lock：在 Ubuntu 24.04
arm64 runner 执行 Cargo fetch --locked 后离线 build --locked，强制 GNU 链接器
PT_LOAD≥16K；记录源码/lock/工具/命令/输出摘要，将重建 ELF 替换实验安装树内
唯一固定 glibc 输入，再由 Bun 插件重新计算物理名。它不是原 npm ELF 可重现证明；
Cargo offline 不隔离第三方 build.rs 的网络/主机访问，Rust sysroot/工具链及所有
适用声明义务仍须审查(serial 补充来源见上文)。仅诊断构建，不接入正式 bundle/APK，
不因此批准分发。
CI `42574333144`(提交 `13c271b`)固定源码重建、16K/glibc/导出、运行库闭包、
普通/持久 PTY 与 TUI/无 ELF 释放均通过。下载 ZIP SHA-256
`4f0af54875ac816333562592dcbc4276fe2ab1eb90c473b06d1802c162ab733a` 与 API
一致，640 项摘要完整核验；重建 bun-pty ELF SHA-256
`2f4cbc71ce4b4edb6762dccc584f974ad363076e0c2ad8691732b08c47d2b903`，529104
字节，仅 NEEDED libc/libgcc_s。固定源码、构建 ELF、Bun 预置副本摘要一致且
普通 PTY 已检查实际 maps；其它三库仍为 npm ELF，Android **待 P0/P3 实机验证**。
报告现区分 npm 固定输入与源码重建来源；候选主源码 commit 不再被补充声明
commit 覆盖，相关回归同时验证两个不同 commit 均保留。

2026-11-09 watcher 源码重建实验新增固定头文件：`node-addon-api 7.1.1`
(与固定上游 bun.lock 一致，registry SHA-512 同锁文件)，归档 SHA-256
`b10455d15a977c0cd17a1cb0eb679e03d939f8ef8d4302eb33e1f78dacc71f82`，同日读取
随包 LICENSE.md 为 MIT、Copyright 2017 Node.js API collaborators；Node 24.6.0
官方 headers 归档 SHA-256 `6b891cced2a8ee08fef06b8cb36a890bd6d1dd8aca575e2a392bb78f0970b819`
与 nodejs.org 官方 SHASUMS256.txt 一致。头文件包含 Node MIT/其它声明，随归档
保留，不能把整份头文件闭包简化为一种许可。以固定 binding.gyp Linux 分支明确
源文件列表和 NAPI_VERSION=4 编译(首轮 CI `42577241899` 证明版本 3 缺
ThreadSafeFunction，未产生替换载荷)，不执行 npm 安装脚本；需验证原生导出及 Bun
真实 subscribe/write/unsubscribe 文件事件后，才替换实验输入。仍仅诊断，不批准
准确原 npm 二进制对应、内嵌源码逐文件许可或 Android 准入。
后续编译以 GCC `-H` 记录实际引用头文件，连同显式源文件记录摘要、固定来源分类和
声明文本线索。watcher 的 `src/wasm/include.h` 内含 Node.js contributors MIT 原文，
不因 Linux 分支为空而丢弃声明；系统 GCC/glibc 头文件仅记录摘要，未因此交付对应
源码。该索引不覆盖编译器内部或链接器输入，不等于逐文件许可审查完成。
真实事件探针另外使用收集的 loader/libc/libstdc++/libgcc_s 运行最终内容寻址预置
副本，并检查 maps 全部对应；不能以 runner 默认运行库下的构建后测试替代该门禁。
CI `42578098328` 已通过重建/真实事件并生成 Bun 导入，随后旧静态白名单拒绝
重建库 NEEDED 的 `ld-linux-aarch64.so.1`；与运行库闭包及局部门禁统一允许该已
收集 loader，保留递归符号版本与实际 maps 验证，不引入新系统库依赖。
前一轮 `42575345307`(提交 `125ec97`)ZIP SHA-256
`19550896df80985dd5850408382209f6a49b0da14511db441e15ae5adce3dff8` 与 API
一致，642 项清单摘要匹配，包含 serial 六文件匹配与 bun-pty 来源报告；其中
诊断 README 在清单生成后写入，仅受 ZIP/API 摘要保护。已将 README 前移，后续
工件应额外核验 ZIP 文件集合与摘要清单集合完全一致(除清单自身)。
网络记录：`42578577616` 完成 watcher staged maps/真实事件与 shell/PTY/TUI/无 ELF
门禁，但下载固定 media 源码超时；`42579064629`、`42579438063` 则在固定 Bun
下载持续 HTTP 504。只增加有界传输重试及同一 GitHub asset ID `665259460`
的 API 下载路径，仍强制原 SHA-256；不跳过源码证据、TLS 或摘要门禁。
CI `42579620831`(提交 `40252c0`)完整成功，artifact `13656956805`，225990521
字节，ZIP SHA-256 `bd5424f935494df0622f3f961bf5f89d4f266e2663be433397065a52db193a8d`
与 API 一致；3461 项文件摘要及 ZIP/清单文件集合完全匹配(除清单自身)。
watcher 重建 ELF SHA-256 `a384a3ab5aa60dda6c61fb87489a99b719910113c00f54c1f3760aeea3662d42`，
623824 字节，构建输出、Bun 导入清单及预置副本相同；普通构建环境及收集运行库
下的真实事件日志均通过。bun-pty 重建 ELF 摘要仍为上述 `2f4cbc71…`，两库来源
报告均标注 fixed-source-ci-rebuild。编译输入索引摘要复核通过：389 项中 watcher
25、node-addon-api 3、Node headers 4、runner 系统输入 357；后者仅摘要记录，
不代表对应源码交付或许可审查。所有批准字段仍为 false，未部署设备。

fff 新增诊断重建配方：同一固定源码/lock，以 `-p fff-c --no-default-features
--features zlob`、固定 Zig 0.16.0 和 GNU bfd 链接器构建，Cargo fetch --locked
后离线编译；保留选中目标/feature 的 crate 归档、Cargo JSON 消息和最终 GNU map。
显式 `LIBZ_SYS_STATIC=1` 使用 lock 内 libz-sys 的内嵌 zlib，
`LIBGIT2_NO_VENDOR=0` 保留选中 vendored-libgit2 分支，避免无记录地依赖 runner libz；
这些 C 源码仍在 CI 外部归档，不复制进仓库，也不因静态链接成功批准许可。
LOAD 输入仅在链接后仍存在时记录摘要，rustc 删除的临时对象明确记为不可用；
这不是逐节/逐文件准确链接归属，也不交付系统工具链对应源码。只有 ELF/导出/
16K/glibc 与 Bun 实际索引/搜索/glob 成功后才替换实验 npm 输入，随后还须使用
收集运行库检查最终内容寻址副本。当前待 CI，不批准原 npm 对应、分发或 Android。
首轮 CI `42601569967`(提交 `a3ac510`)已完成 fff 编译，但依赖门禁发现
`libz.so.1` 并拒绝替换输入，后续 Bun 构建/运行门禁跳过，未产生获准工件。
提交 `4e46ebc` 显式固定上述静态分支，新 CI `42602199884` 尚待结果确认；
回归同时覆盖系统 `libz.so.1` 被拒绝且原输入字节不变，不通过扩展白名单放行。

2026-11-09 实验动态库基线：CI 使用 Docker Official `ubuntu:24.04` 安装官方
`libstdc++6`/`libgcc-s1`，记录实际 image ID、dpkg 二进制/源码包版本、库摘要和
包内 copyright。同日读取现有 Ubuntu 24.04 实例 gcc-14 包 copyright，确认
libstdc++/libgcc 的 GNU GPLv3 + GCC Runtime Library Exception 口径；该例外不等于
免除库自身对应源码/声明义务，实际包版权原文随诊断工件保留。glibc 仍按 LGPL
独立审查。新收集器只复制 CI sysroot 的 arm64 库，不使用宿主 runner 库，不进入
正式 APK/bundle；递归 NEEDED 与版本化符号检查、运行成功均不构成分发批准。
CI `42543657122`(提交 `4279a3e`)已通过 9 份运行库、14 个 ELF 的依赖/版本与
16K/glibc≤2.39 门禁、shell/普通及持久 PTY、真实 TUI staged 映射及隔离
HOME/BUN_TMPDIR 无 ELF 释放检查。下载工件 ZIP SHA-256
`8d4c27abc3893881f18d4c243fd71cf53302b914129089c921ab18aca2719b0c` 与 API
一致，44 项文件摘要、9 份库摘要均逐字节复核；glibc `2.39-0ubuntu8.9`、GCC
运行库 `14.2.0-4ubuntu2~24.04.1`。这只是 Linux 实验，不替代 Android 准入。

2026-11-09 Android libtinfo 自编译核验:Ubuntu
`ncurses_6.4+20240113.orig.tar.gz` SHA-256
`37a12a0f8ae2605012c9a164dd286b0cfa02b51b5055836d09eb3d597fc351b1`，
包内 COPYING 为 MIT/X11 风格(含保留姓名条款)；应用 Ubuntu
`6.4+20240113-1ubuntu2.2` 补丁集(含两个安全修复)，debian.tar.xz SHA-256
`c7bbb8483d7ec358fb925a370575d8ebef63d6e455edce140de2ca7b86cf98d1`，
摘要与 ports.ubuntu.com `.dsc` 一致。源码仅 CI 暂存构建，不入本仓库；保留
Ubuntu copyright、上游 COPYING、固定摘要/配置。只对 Android bundle 的
libtinfo 关闭 HAVE_SETFSUID，使用上游无身份变更安全打开分支，不伪造 syscall
结果、不启用 root-access；需实际初始化和应用域复测后才批准产物。

### 2.2 独立程序聚合(GPL-2.0,只随包放二进制 + 源码指引)

| 项目 | 仓库 | 许可证 | 角色 | 义务与边界 |
|---|---|---|---|---|
| busybox | `mirror/busybox` / busybox.net | GPL-2.0 | 交付包内静态粘合工具(sh/tar/readlink 等,§4.1.2) | **静态单文件独立程序**聚合;官方 `busybox.net/downloads/binaries/` 提供 arm64 静态预编译(实测可访问,采购来源之一,亦可在基线内自建锁版本);`manifest` 记录版本与源码地址;绝不并入源码 |
| GNU Bash | `https://ftp.gnu.org/gnu/bash/`, Ubuntu 源包 `https://ports.ubuntu.com/pool/main/b/bash/` | GPL-3.0-or-later(2026-11-08 核对 Ubuntu `bash_5.2.21-2ubuntu4_arm64.deb` 内 `usr/share/doc/bash/copyright`:Files * / GPL-3+) | Tier P 默认交互 shell,Ubuntu 24.04 基线 5.2.21;动态依赖 libtinfo(Ncurses,MIT/X11 及部分 BSD-3-Clause,同日核对 `libtinfo6_6.4+20240113-1ubuntu2_arm64.deb` copyright) | 独立 ELF 聚合,不取 Bash 源码;CI 收录 ELF/依赖、版权及完整 GPLv3 文本,manifest 标注真实包版本和源码池地址;发布仍须落实 GPL 对应源码提供义务,不以 URL 替代合规交付;不调用第三方宿主 Bash |
| proot | `proot-me/proot` (★2.7k) | SPDX 标注 GPL-2.0(only/or-later 待核实,行动项) | **兜底**:shim 覆盖不全时做最小 bind(§4.5) | 同 busybox 口径;若确认为 GPL-2.0-only,仍然可以"独立二进制聚合 + 源码提供"方式分发 |
| Ubuntu 24.04 arm64 开发 rootfs | Docker Official Image `ubuntu:24.04`,Ubuntu `noble`/`noble-updates`/`noble-security` | 多许可证独立程序聚合,不得整体标成 AGPL;2026-11-09 按镜像内 dpkg 数据库与 `/usr/share/doc/*/copyright` 逐包追踪,发布合规尚待审查 | root chroot 原型包含 apt、Bash、ca-certificates、curl、git、build-essential、python3、util-linux | 新配方仅从官方源 apt 安装,保留 copyright/common-licenses,生成包版本/源包清单及镜像 digest;CI 工件仅用于验证,正式分发前必须提供各 GPL/LGPL 包对应源码及变更,不能以包清单或源码 URL 代替履约;PRoot 不复用 chroot 可写实例 |
| Ubuntu Base 24.04.4 arm64(开发实机引导) | `https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.4-base-arm64.tar.gz` | 同上,保留包内 copyright/common-licenses;2026-11-09 核对官方 HTTPS SHA256SUMS 与下载归档 | 无本地 Linux/Docker 时的设备开发验证入口,不是 CI 镜像来源替换 | 固定 SHA-256 `04207713ece899c3740823d33690441ad3a7f0ded1101aca744e2b0f37ac7ff2`;只在隔离新 ext4 镜像提取,保留源信息/包清单,正式发布仍须逐包合规 |

### 2.3 参考实现(谨慎取材)

fff 诊断构建使用 Zig **0.16.0** arm64 官方工具归档(仅 CI，不随包交付)：
`https://ziglang.org/download/0.16.0/zig-aarch64-linux-0.16.0.tar.xz`，SHA-256
`ea4b09bfb22ec6f6c6ceac57ab63efb6b46e17ab08d21f69f3a48b38e1534f17`，
2026-11-09 下载并核对官方 index.json 摘要及归档根 LICENSE：MIT (Expat)，
Copyright Zig contributors。内附标准库/编译运行时及 LLVM 等不应整体推断为 MIT；
构建产物中静态工具链输入仍需单独审查，固定工具摘要不是其许可批准。

构建期 Actions（不进入 APK/bundle）：`actions/download-artifact@v4`、
`actions/setup-java@v4`、`android-actions/setup-android@v3`、
`gradle/actions/setup-gradle@v4`，2026-11-09 通过各仓库 LICENSE 核实为 MIT
（Gradle 特别核对 v4/LICENSE，不以 main 的混合许可替代所用版本）。仅用于
下载当前 run 工件及安装 JDK/Android SDK/Gradle，不并入第三方源码或工具到交付物。
故障诊断可在 CI 安装 Ubuntu 官方 `gdb`（GPL-3.0-or-later，2026-11-09 核对
GNU GDB `gdb/top.c` 版权头及 GPLv3+ 版本输出，sourceware 的 RTEMS 只读镜像）；
仅收集自有 CI 进程栈，不进入 APK 或 bundle。

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
3. **LGPL 依赖**(glibc、JavaScriptCore)→ 逐项核实版本、静态/动态链接和变更，
   保留声明并落实适用条款要求的准确对应源码、重链接/替换与必要安装材料；
   仅附许可文本或上游 URL 不足以证明履约。
4. **GPL-2.0 独立程序**(busybox、proot)→ 仅以**独立二进制聚合**方式随包分发,
   `manifest` 提供精确版本号与源码地址作为追溯索引，不等同于有效的书面 offer。
   发布须按实际交付方式落实对应源码(含下游构建补丁/脚本)或适用条款允许的有效
   源码提供方式，未完成前不称可正式分发。不并入源码；若未来必须修改，需独立
   GPL-2.0 仓库分离发布。
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
