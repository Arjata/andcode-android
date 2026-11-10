# 可复用开源项目调研(docs/REUSE.md)

> 调研日期: 2026-11-06 · 许可证信息均于当日经 GitHub API / 源码 LICENSE 文件逐仓库核实
> 本项目许可证: **AGPL-3.0-only**(仓库根 `LICENSE` 已放置全文)
> v0.3 同步: 设计已去除 Termux 等第三方宿主依赖,清单角色相应调整。

---

## 1. 结论摘要

| 结论 | 说明 |
|---|---|
| ✅ Permissive components, subject to their actual dependency closure | opencode (MIT), dropbear (MIT), jackpal terminal library (Apache-2.0), termux-exec (Apache-2.0). Preserve applicable notices and audit bundled dependencies separately; a permissive root license does not approve the complete artifact. |
| ⚠️ Bun runtime: redistribution review blocked | Bun's root license is MIT, but its statically linked JavaScriptCore/WebKit and other dependencies require separate source, notices and modified-library relinking review. Do not treat the root MIT notice as sufficient approval. |
| ⚠️ 独立程序聚合(不并源码) | busybox(GPL-2.0,静态单文件)、proot(GPL-2.0,兜底方案)——作为独立可执行文件随包分发,仍须落实适用 GPL 对应源码交付义务;上游 URL 不是合规批准;**禁止把其源码复制进本仓库** |
| 🔧 仅构建期使用(不随包分发) | patchelf(GPL-3.0,CI 内做 soname 重写)、termux-elf-cleaner(GPL-3.0,按需)——工具本身不进产物,无分发义务 |
| ⚠️ 参考实现 | termux-pacman/glibc-packages(MIT)——shim 与 sysroot 的对照基线;**Happ1ness-dev/bun-termux(MIT,★85,活跃)——Bun 无 proot 的最佳先行者**;termux-exec(Apache-2.0)——LD_PRELOAD 拦截参照 |
| ⬇️ 降级为可选 | Termux 系(GPLv3)——不再是宿主,仅作附录替代路径;作为"用户已装的第三方 App 被调用"时无义务 |
| ❌ 不可复用代码 | tribixbite/bun-on-termux、termux/termux-boot(未发现 LICENSE)、**CypherpunkArmory/UserLAnd(★4.3k,无 LICENSE = 保留所有权利)**——只观察行为/UX,不拷贝代码 |

---

## 2. 候选清单

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

### 2.1 交付包核心组件(宽松许可,随包分发)

| 项目 | 仓库 | 许可证 | 角色(对应 DESIGN §4) | 复用方式 |
|---|---|---|---|---|
| opencode | `sst/opencode` (★224.8k, 活跃) | MIT | 移植目标本体;官方发布含 linux-arm64 (glibc) 产物 | 直接运行其产物;需要时打补丁(补丁归本项目 AGPL) |
| opencode V2.2.6 | `anomalyco/opencode`, tag `v2.2.6` | MIT(2026-11-09 核对该 tag LICENSE) | 与旧版分开的 Web/serve 固定载荷 | 官方 linux-arm64 归档固定 SHA-256 `f2d27600c367e45057d6a16f6a5c2aa8d77b41a9b10d4bc3d849c2f88870e944`;CI 预置为 oc2.bin,不在设备下载 |
| opencode-pty | `anomalyco/opencode`, `packages/process-daemon`, tag `process-daemon-v0.4.0` (`5e6ee370634842e0efa99ad103c4d767581b47f0`) | MIT(2026-11-08 核对该版本 Cargo.toml/license 与 npm 包 LICENSE) | V2 Web 终端 daemon,协议 7;独立预置副本而非应用数据目录运行期释放 | 开发部署使用官方 aarch64-unknown-linux-gnu 资产,改写 PT_INTERP;`OPENCODE_PTY_BIN`/`OPENCODE_PTY_SOCKET_DIR` 为该版本上游已有配置,无需改源码;正式打包须登记生成 manifest 与 notices(尚待 CI 集成) |
| bun | `oven-sh/bun` | MIT root; pinned JSC `COPYING.LIB` is GNU Library GPL v2; tinycc is LGPL-2.1. Per-file and actual static-input conditions require separate review. | OpenCode runtime and build tool | Source declarations and URLs alone do not satisfy or approve corresponding-source/relinking obligations; runtime redistribution remains blocked pending closure. |
| V2 源码预置扩展实验 | `anomalyco/opencode` v2.2.6 提交 `dc2ffcf8bf26f9e669b6aa22b95f50e12be15e06` | MIT;2026-11-09 核对该 tag LICENSE | 手动 CI 从固定源码及 frozen lockfile 构建,不替代当前官方载荷 | Bun 1.4.4 arm64 归档固定 SHA-256 `baa6bb36f51d6e58561e02bbea825038a9df454f673d6d776e8bbf86f8c7850e`;保留上游 LICENSE/lockfile,未完成传递原生库合规/兼容审计前仅作实验 |
| V2 内嵌原生扩展(实验拆分) | OpenTUI 0.8.1、Parcel watcher 2.5.1、bun-pty 0.4.11、fff-bun 0.10.5 | **OpenTUI 原生包为 MIT AND LGPL-2.1-or-later,不是仅 MIT**;其余 npm metadata 为 MIT。2026-11-09 对固定版本 tarball 校验 registry SHA-512 后检查包内许可证:watcher/bun-pty 附 MIT;fff 平台包未附 LICENSE,不能仅凭 metadata 批准分发 | 将文件导入改为 nativeLibraryDir 显式加载,不伪装临时文件、不让 Bun 运行期释放 ELF | 不取第三方代码入库;OpenTUI 还附 LICENSE-FFMPEG/GHOSTTY/LCMS2/LIBWEBP/STB/WUFFS/ZLIB,需分别追踪源码/构建与重链接义务;传递 Rust/C/C++ notices 和对应源码尚未审查,不得称正式可分发闭包 |
| dropbear | `mkj/dropbear` (★2.5k, 活跃) | **MIT**(已核实 LICENSE 原文: Matt Johnston, MIT 风格授权) | 三种形态共用的内置 sshd(§4.7 交互入口) | 在基线内构建静态/动态版,随 bundle 分发 |
| termux-exec | `termux/termux-exec` (★268, 活跃) | **Apache-2.0**(LICENSE 实测:Apache-2.0 + MIT 组件) | **LD_PRELOAD 拦截参照实现**:Android 上多年的 LD_PRELOAD 工程实践,直接指导 §4.5 shim 的拦截面选择与坑位 | 参考实现;如取码按 Apache-2.0 附声明 |
| jackpal/Android-Terminal-Emulator | `jackpal/Android-Terminal-Emulator` (★3.2k) | **Apache-2.0** | Tier P APK 的终端模拟器核心(emulator/view 库可并入 AGPL 项目) | 最小 fork(上游 2022 年停更;现存 fork 全部停滞于 2014–2021,已核实),保留版权声明 |
| **Termux terminal-emulator / terminal-view(P3 终选,已并入)** | `termux/termux-app` 模块(★64.2k, 活跃) | **GPLv3** | P3 APK 的终端核心(jackpal 停更故改选) | GPLv3→AGPLv3 单向兼容,已并入 app/terminal-*(保留版权头,app/NOTICE-TERMINAL.md);合并作品整体 AGPL-3.0-only;本仓库公开即满足源码义务 |
| proot(Termux bionic 构建) | packages.termux.dev pool/main/p/proot | **GPL-2.0** | **Tier A/M 的 /etc 重定向正解**(真机 P0:LD_PRELOAD 无法拦截 glibc 内部 fopen("/etc/resolv.conf"),proot bind 实测打通 git https 全链路) | 独立程序聚合;proot + loader + libtalloc(LGPL-3.0)+ libandroid-shmem(**BSD-2-Clause**,termux/libandroid-shmem LICENSE 已核)随 bundle 分发,manifest 记录 |
| ConnectBot | `connectbot/connectbot` (★3.6k, 活跃) | Apache-2.0 | Tier A/M 的推荐 SSH 客户端(**可选工具,非依赖**) | 仅文档推荐 |

OpenTUI 诊断构建工具单独固定 Zig **0.17.0** 官方 arm64 Linux 归档
`https://ziglang.org/download/0.17.0/zig-aarch64-linux-0.17.0.tar.xz`，SHA-256
`9e8d11661d4ae3bd57702a3832781e23ad151dde5798e16a5ccd503f65234ff8`，52877280 字节。
2026-11-09 下载复核根 LICENSE 为 MIT(Expat)，Copyright Zig contributors，
LICENSE SHA-256 `5c537d6853e005298a285d508cff9ac7192cea23576c840d485b2b586a7ff177`。
仅作构建工具，不随 APK 分发；工具链内 LLVM/libc/libc++ 及静态输出输入仍须独立
逐项审查，根 MIT 不覆盖整个输出。与 fff 的 Zig 0.16.0 分开路径使用，不升级后者。
首轮 OpenTUI CI `42621241263`(提交 `b0f1aba`)完成 glibc FFmpeg 构建，但上游
在配置未执行的 musl 测试/benchmark 目标时触发 `require-video` 缺失而失败，
未替换 npm 输入、未产生通过的诊断包。后续仅对显式 library-target 增加
`andcode-library-only` 配置早退，保留所选库 `require-video=true` 及 16K 门禁；
不构建/收录 musl FFmpeg，不降低准入条件。该提交常规 CI `42621206258` 的
app-data-tests/build-bundle 已成功，APK 作业在 NDK 下载 ZIP 损坏处失败，未执行
Gradle 构建，不据此声称 APK 通过。
构建后额外校验生成的 FFmpeg `config.h`:许可字符串须为 LGPL version 2.1 or
later，GPL/version3/nonfree/network 必须关闭、zlib 必须启用；缺宏、冲突宏或配置
漂移均拒绝替换实验输入。只允许固定 FFmpeg 9.0.2 configure 在 GPLV3/general
external library 两表重复列出的 `CONFIG_LIBSMBCLIENT 0` 同值重复，其它重复仍
拒绝。CI `42623976037`(提交 `5c80984`)即因原检查器拒绝这个上游重复而失败，
不是启用了 Samba/GPL 或源码编译失败；横向空白匹配避免无值头文件保护宏吞掉
下一行。该配置检查只防配方漂移，不替代 C/汇编逐文件许可、
专利/地区使用限制或 LGPL 对应源码/重链接材料审查。

源码实验 CI 的 `collect-opencode-native-licenses.py` 对四个固定原生导入逐一核对
安装源字节/包名/版本/声明许可，将包内顶层 LICENSE*/COPYING*/NOTICE* 与 package.json
保存在诊断工件 `native-license-evidence/`，并生成 `native-license-review.json`。
缺声明记为 `blocked-missing-package-notice`，有声明仍为 `blocked-transitive-review`；
`redistributionApproved` 始终 false。它不是传递源码审查，也不覆盖 Bun/JS/Web 整体依赖，
不能把 CI 成功或收集到 LICENSE 理解为合规交付完成。

OpenTUI 首次完整 Linux 实验 CI `42623009744` 与常规 CI `42622973489` 均成功，
head 为 `1a43a9e9baea98e934ca4ca16c21d275ff408d32`。诊断 artifact
`13678007813`，442621775 字节，ZIP SHA-256
`018e7de71f9c0775e2d4d5eccd0b90b83cbb23df52eb7d56147cbb6bb5794fb6` 与 API
一致；初次下载截断，保留断点续传后才核验。18946 项原清单摘要全部匹配，另有
10399 项上传器沿 FFmpeg build/src 目录链接解引用收录的文件未列入原清单；这些
额外文件已逐字节摘要对照清单内 `sources/ffmpeg-9.0.2` 同相对路径源码，全部相同。
**原工件文件集合仍不闭合**，不把额外源码有一致字节等同原清单完整；后续用
`manifest-opencode-native.py` 按上传器解引用视图生成清单，拒绝越界/循环链接及
特殊文件。是否闭合须下载下一轮工件重新核对。

清单修复提交 `1d3d37ee1ed5a410400dc80e117d77df6c385024` 的源码实验
`42628073140` 与常规 CI `42628022675` 均成功；artifact `13680841250` 的
443040684 字节 ZIP SHA-256
`a2f448c01a7a268b0827310a1bd00bbe2c6db637830cb64c20cf08222152a1bd` 已与 API
及本机完整下载匹配。29345 项文件与摘要清单集合完全相同，逐项 SHA-256 全通过，
清单缺口为 0。四个原生 ELF 的导入清单/来源报告/重建摘要、9 个 Ubuntu 动态库
及 14 项递归闭包报告一致；bun-pty 37 个、fff 116 个 registry crate 归档与 lock
checksum 匹配。347 个 FFmpeg/zlib 对象及上述安全配置重验通过。
这一轮 OpenTUI ELF SHA-256 为
`daa2f6fc84cbedd079db842b3afb53a562420695a0ef9c1d4ae8195881b5ad97`，大小仍
32974432；不同构建输出摘要不同，未声称位级可重现。Linux API/PTY/TUI 与隔离
目录无运行期 ELF 门禁已核对真实日志；所有许可与 Android 批准继续为 false。

本轮重建 OpenTUI ELF 32974432 字节，SHA-256
`312aa75db50cd70dc92fedc458ad20db5e9a5e7b68a4a2f1b021d1f090be6b0d`，构建输出与
Bun 预置副本一致；NEEDED 为 libc/libm/libpthread/libdl，ELF glibc≤2.39/16K 门禁
通过。347 个 FFmpeg/zlib 对象与报告路径/长度/摘要全部复核；对工件内实际生成
config.h 运行修正后的检查器通过 LGPL2.1、GPL/version3/nonfree/network=0、zlib=1
门禁。四库来源均为 fixed-source-ci-rebuild，ABI、真实文件事件、索引/搜索/glob、
普通/持久 PTY、TUI 渲染/预置库 maps 及隔离 HOME/BUN_TMPDIR 无运行期 ELF 日志
均通过；这只代表 Linux 实验，不代表 Android 应用域、原 npm ELF 可重现或许可批准。
后续提交 `5c80984` 常规 CI `42623847446` 成功；其源码实验失败边界见上文。

2026-11-09 固定 OpenTUI 源码声明预审另核对了嵌套 Yoga/Ghostty/uucode 的 MIT
原文、lcms2 MIT、libwebp COPYING 与 PATENTS、stb 双许可、Wuffs Apache-2.0，
以及 miniaudio.h 尾部 Unlicense / MIT-0 双选原文(Copyright 2025 David Reid)。
其中 miniaudio 许可内嵌于头文件，不会出现在仅按 LICENSE 文件名扫描的结果中；
该事实不证明其它内嵌 dr_* 实现或生成数据已逐文件闭环。Zig build.zig 明确设置
Yoga `link_libcpp=true`，工具链 C++ 运行库对应源码/通知也不能漏算；这些均未
新增依赖或取码入库，仍需按实际编译/链接输入做完整通知与义务审查。

上述成功工件的 Zig verbose-link 日志仅有一条最终 `ld.lld` 命令，显式引用
448 个输入，含 libc++abi/libc++/libunwind/libc_nonshared/libcompiler_rt 五份
静态库以及 Zig 生成的 glibc 链接桩。后续构建器按参数顺序保留这条命令的输入
副本与原路径/构建来源/长度/SHA-256，要求仅位于固定 OpenTUI 构建树或两个
专用 Zig cache；拒绝缺失文件、响应文件、相对路径、未知选项、越界链接及
链接输出与安装结果不一致，失败不替换实验 npm 输入。链接桩副本只说明构建期
输入，不是 Ubuntu 运行库。保留静态库也不等同选中成员/逐节归属/完整对应源码，
更不等同 LGPL 可替换重链接已验收；这些限制继续保留。
本机仅完成命令形状重放与合成回归，新增链接输入保留须由下一轮真实 CI 验证。

后续源码 CI `42632448278` / 常规 CI `42632416589`(head `e0ca1b7`)均成功。
artifact `13681818902`，459080002 字节，ZIP SHA-256
`f1f0ebec0ec8d78fe777ce72b81ddc8e686aca6f0e4be300b39b09966320a456` 与 API
一致，29793 项清单集合闭合且全部摘要匹配。448 个实际链接输入副本逐项核对
参数顺序/路径/长度/摘要，347 项 FFmpeg/zlib 对象与原对象报告一致。

Zig 0.17.0 固定官方归档内另核对 libc++/libc++abi/libunwind 的 LICENSE.TXT、
`lib/libc/glibc/LICENSES` 与根 MIT LICENSE(2026-11-09)。后续构建仅把同一摘要
归档的 `lib/` 全部常规资源及根 LICENSE/README.md 保留为独立候选源码归档，
记录每个资源字节摘要，拒绝链接/越界/重复/ELF 条目，不保留 Zig 工具可执行文件。
这些资源包含 LLVM 库、Zig compiler-rt/标准库及 glibc 支撑源码，但仍非完整
Zig/LLVM 工具链源码、逐文件许可审查、Bun/JSC 对应源码或重链接交付批准。
本机针对固定归档实际运行收集器得到 19503 项、187671709 字节原始资源，所有
所需声明存在且未发现资源 ELF；65 项原生 Python 回归通过。归档及逐项摘要将
随诊断报告保留，CI 工件复核仍待下一轮执行。

源码 CI `42633493308` / 常规 CI `42633461482`(head
`605787da5f2dd4201568eceac243e378433734b3`)均成功。artifact `13683491047`，
489519009 字节，ZIP SHA-256
`ffd1260792bdc202a0208bed2363501c67a2638eb3602f28e18bfcc49f71770d` 与 API
一致；29794 项文件清单闭合且全部摘要匹配，448 个链接输入及 347 项媒体对象
一致。19503 项 Zig 资源归档清单闭合，逐项摘要与固定官方工具归档的同路径原字节
全部一致，未带入 Zig ELF。两轮 Linux ABI/API/PTY/TUI/隔离目录无运行期 ELF
日志已核对；仍非 Android/许可批准。磁盘不足中断的下载已在用户授权后迁移至
F 盘，迁移前后摘要一致后才删除原临时 ZIP 副本，续传最终 API 摘要通过。

**2026-11-09 新发现的许可阻塞(覆盖上述配置门禁的宽泛解读)**：对实际
FFmpeg `.d` 编译依赖预审，336 项对象可映射 736 项依赖文件，另 11 项 zlib
对象缺 `.d` 明确保留缺口；`libavutil/aarch64/crc.S` 原文声明
GPL-2.0-or-later，且 `objects/libavutil/aarch64/crc.o`(2232 字节、SHA-256
`918940cacb3c696d99b95173abf7793eb60b8566455080f65889838649d0b910`)确实在最终
链接命令中。即使 `CONFIG_GPL=0`/`FFMPEG_LICENSE=LGPL`，也不能推断未链接
GPL 声明代码；既有成功工件保持 blocked，不更改第三方原文、不追认分发批准。
后续固定配方增加 `--disable-armv8` 排除上游 ARMV8-OBJS 组(保留独立 NEON
配置)，要求 HAVE_ARMV8/HAVE_ARMV8_EXTERNAL=0，直接拒绝该 CRC 对象；收集
实际 make 依赖的源码路径/摘要，前 100 行去注释折行后命中 GPL-only 声明即
拒绝替换实验输入。它是保守门禁，不是完整逐文件许可判定；系统头、zlib 头、
宏条件选择、归档成员/最终存活节与其它源码义务仍需人工及实际构建验证。

首轮排除提交 `190b518` 的常规 CI `42641908404` 成功，源码 CI `42642081860`
在最终链接失败；已核对 job `129245514248` 完整日志和失败工件
`13687470347`(ZIP SHA-256
`701c5d8cd0509acf7dd58e024ef9b36de425712f37650a91fb14630269852186`)。
上游 `aarch64/crc.h` 以 HAVE_ARM_CRC 和 HAVE_PMULL/HAVE_EOR3 独立选择
`ff_crc32_aarch64`、`ff_crc_neon_pmull`、`ff_crc_le_neon_pmull`，不会随
ARMV8-OBJS 自动关闭，故仅排除汇编对象会留下三个未定义引用。后续配方同步
增加 `--disable-arm-crc`/`--disable-pmull`，并要求生成的 HAVE_ARM_CRC 和
HAVE_PMULL 均为 0，使 CRC 回退通用 C 路径，不修改第三方许可或补写同名实现；
独立 NEON 配置不关闭。新配方尚待真实 arm64 CI 与工件复核，不能以合成回归
声称链接、媒体或 Android 已通过。

为避免把 TUI 渲染成功当作 CRC 计算正确，另增加自有 `crc-probe.c`，静态链接
同一 prefix 的 libavutil：8 种标准多项式、标准/257 项/1024 项三种表、8 种
非对齐偏移、6 种长度、零/非零种子共 2304 组，与独立逐位参考算法及分块续算
逐项对照；编译/运行/标记任一失败均不替换实验 npm 输入。探针源码、命令、日志
及 ELF 摘要仅留诊断工件，不进入 APK；它由 runner 链接，不能证明 Android、
完整解码或最终共享库的媒体导出接口。新增门禁已做合成失败回归及 Windows
Clang C 语法检查，真实执行仍待原生 arm64 CI，不声称已通过 2304 组计算。

后续实际验证(2026-11-10)：提交 `37e6536` 的常规 CI `42645263750` 与源码 CI
`42645293538` 成功。工件 `13689266279`，489539534 字节，ZIP SHA-256
`260246d7f7043910a8795a49b9aabc3b64cd0b2370c16db3fb934f24d80d91c9` 与 API
一致；29786 项清单集合闭合，446 个最终链接输入及 345 个媒体对象逐项摘要一致。
直接从工件 make 依赖文件复算 334 个对象→733 个实际源码依赖，全部长度/摘要
一致，另 11 个 zlib 对象缺 `.d` 未消除。实际配置的 HAVE_ARMV8、
HAVE_ARMV8_EXTERNAL、HAVE_ARM_CRC、HAVE_PMULL 均为 0，CRC 汇编对象不在
对象表和最终链接输入，独立 NEON 保留。19503 项 Zig 资源逐项匹配固定归档。
job `129256831289` 日志确认真实 Linux ABI/PTY/TUI/隔离 HOME/BUN_TMPDIR 无
运行期 ELF 门禁通过，不能据此推断 Android 或旧 npm ELF 对应关系。

新增 CRC 探针提交 `4bfeb01` 的常规 CI `42646804980` 与源码 CI `42646838972`
亦成功。工件 `13690215064`，489629927 字节，ZIP SHA-256
`5010c990855de9bf254821959a0734d372341ea6fd068c73bd5a39122bd9b06a` 与 API
一致，29789 项文件清单闭合，446 个链接输入、345 个媒体对象、334→733 源码
依赖及 19503 项 Zig 资源全部复核。真实 `crc-probe.log` 包含 2304 组成功标记，
源码及独立探针 ELF 摘要与报告一致;Linux ABI/PTY/TUI/无运行期 ELF 日志再次
通过(job `129262254406`)。重建 OpenTUI 32969560 字节，SHA-256
`2fe57e9fbcd1096b0532a04b98744480d6f0c89f8454034e77504b7ce142cfd7`，
NEEDED 仍 libc/libm/libpthread/libdl，glibc≤2.39/16K 静态门禁通过；两轮不同
ELF 摘要不冒称可重现构建。许可、对应源码及 Android 批准字段均继续 false。

对 733 项实际依赖前 100 行进一步人工预审，除 LGPL 外还包含三个 IJG 声明
源文件 `libavcodec/jfdctfst.c`、`jfdctint_template.c`、`jrevdct.c`，以及内嵌
宽松许可/生成头候选。最终 notices 需保留这些专门声明与归属，不能只附 LGPL；
此轮仍非全文件或完整闭包许可审核，没有将第三方代码/二进制复制入仓库。
后续对同工件 733 项依赖全文做关键词预审，发现 `libavutil/libm.h` 第 101 行
和 `mathematics.c` 第 234 行的额外许可段落，以及 `libswscale/filters.c` 第
303 行的独立版权候选；前 100 行门禁不等于完整 notices。后续配方为实际依赖
保留含许可关键词的完整 C 块注释、精确字节范围/起始行与摘要，并记录块注释外的
关键词行；原字节可回查源码，不自动判定许可证、不删去嵌套声明，也不据无关键词
宣称没有义务。此候选报告仍有系统头、zlib 缺 `.d`、非注释声明/生成器等范围限制。
本机对 `42646838972` 工件原字节实际运行新收集器，覆盖 733 份依赖，保留 732
段块注释和 11 条块外候选行，逐段范围/摘要可回查；这是本机重建候选报告，
不是旧 CI 已随包保存的证据，后续构建随工件保留仍待 CI。
本机另用已有 Windows LLD 23.1.2 对 446 份保留输入跨链接成功，保留 map 与
archive extraction 诊断；输出不与原 ELF 逐字节相同(32969640 字节)，未运行。
这仅证明这些输入可被另一个 linker 消费，不能将其成员选择冒称原 Zig 最终链接
证据，更不代表修改后 FFmpeg 的 Linux/Android 替换重链接验收或分发批准。

后续诊断配方新增同一固定 Zig `ld.lld` 的保留输入重放：所有输入路径改指向
已核对摘要的副本，仅改变输出路径并增加 map/why-extract 报告；要求生成 ELF
与原构建逐字节一致、ELF 静态检查和 Bun ABI/maps 探针通过才替换实验 npm 输入。
若 linker 不支持、输入漂移、字节不同或报告/探针缺失则失败，不回退另一个 linker
或放松一致性要求。新门禁尚待真实 CI；其报告即使成功也只证明未修改输入的原始
链接重放，不是修改 FFmpeg 后的可替换重链接或 LGPL/Android 分发批准。

同一 linker 重放的真实源码 CI `42652931946` / 常规 CI `42652895593`
(head `6dd5352`)随后成功。artifact `13692081137`，499726018 字节，ZIP
SHA-256 `1f0759d782d19d79188f4b057659587115f8576714f5d6ac479fe3d039edf321`
与 API 一致；29794 项文件清单闭合，446 个输入/345 个媒体对象/334→733 源码
依赖/19503 项 Zig 资源逐项复核，CRC 2304 组再次通过。同一固定 Zig 重放输出
与原始 ELF 逐字节一致，Bun ABI/maps 通过，map 与 archive extraction 报告摘要
一致，记录抽取 25 个归档成员：libc++abi 15、libc++ 2、libunwind 4、
libc_nonshared 3、compiler-rt 1。提取不等于每个成员所有节最终存活，也不代表
成员源码归属已完整证明。原工件 OpenTUI 为 32969560 字节、SHA-256
`a096fceb66780f25e47fe83849d9f9cfe6c93ee385e4ea02d382d10374fadb3c`；job
`129283784357` 完整日志已保存，Linux PTY/TUI/无运行期 ELF 门禁通过，仍无
修改版重链接或 Android 批准。此前本机核验器的 Zig 子命令参数偏移错误已修正，
重新对比全部参数和实际 ELF 字节通过，未放宽工件门禁。
本机另从保留的五个静态归档逐一读取上述 25 个成员，确认每个成员名唯一、内容
为 ELF，并记录各自长度/摘要；此举将抽取记录绑定到实际 archive 字节，仍非
编译参数/预处理输入与源码许可的完整映射，也没有把第三方 ELF 放入仓库。
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

2026-11-10 Bun/JSC 固定版本声明定位：GitHub tag `bun-v1.4.4` 解析到
`oven-sh/bun@38afee6c84fcf48c0edb2466aa4b27d287a59c30`，该提交 `LICENSE.md`
SHA-256 `362fe32c954ec829240bd7429c53d705eef08c6bfa45ffc2d02005f857cba4dd`。
其说明明确 JavaScriptCore/WebKit 静态链接及修改后重链接义务，另列 tinycc
LGPL-2.1 等依赖，不能只按顶层 MIT 归类。固定
`scripts/build/deps/webkit.ts`(SHA-256
`e801ac2b2c0b83767a10e4bf673addda60ff1c4e64d1246c0e442ce22b3c5059`)中的
WEBKIT_VERSION 为 `d6375c72affe0f70222cdcb45012b10f0bf3a9d5`，并区分预构建
下载与本地源码构建。该 WebKit 提交 `Source/JavaScriptCore/COPYING.LIB` 原文
为 GNU Library GPL v2，SHA-256
`5094ecb9c9dcd0eadc34f3c11511d9b5535063032bc150164ecd1a5d5a445547`；具体源文件
的 LGPL/BSD 等条件仍须逐项核对，不能由这份文本推出整树统一许可证。
来源收集器只保留固定提交的选定声明、版本 pin 与构建文件并拒绝摘要漂移；不下载
整份 WebKit、不执行构建、不声称 Bun 官方 ELF 与候选源码完全对应。Bun/JSC/
tinycc/其它静态依赖的准确对应源码、全部通知、重链接工具链和 APK 替换路径继续
blocked，尚待可信 CI 收集上述文件并复核。

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
收集运行库检查最终内容寻址副本。不批准原 npm 对应、分发或 Android。
首轮 CI `42601569967`(提交 `a3ac510`)已完成 fff 编译，但依赖门禁发现
`libz.so.1` 并拒绝替换输入，后续 Bun 构建/运行门禁跳过，未产生获准工件。
提交 `4e46ebc` 显式固定上述静态分支，CI `42602199884` 已全部成功；
回归同时覆盖系统 `libz.so.1` 被拒绝且原输入字节不变，不通过扩展白名单放行。
该轮包含 fff 实际搜索/glob、最终预置副本与收集运行库 maps，以及 shell/普通及
持久 PTY/TUI/无运行期 ELF 释放门禁；artifact `13666846466`，248955245 字节。
ZIP SHA-256 `9ea996e8b7c9d12a5beaed6f16d801bf0e6e491a9785b73ca38bc3fa2f8e8a10`
与 GitHub API 一致；本机逐字节复核全部 3956 项文件摘要及 ZIP/manifest 集合闭合。
fff 构建输出、Bun 导入及最终预置副本摘要一致：
`27dd516b50ae87429ae748c8a9a43485777e36de2be846ace04235f5f0bc03e7`，10417896 字节；
NEEDED 仅 `libgcc_s.so.1`、`libm.so.6`、`libc.so.6`、`ld-linux-aarch64.so.1`。
构建与最终预置副本的搜索/glob 日志、120 项选中包中的 116 份 registry 归档摘要、
三库 fixed-source-ci-rebuild 来源报告与清单一致；所有批准字段仍为 false。
GNU LOAD 报告 26 项中 19 项链接后可用并记录摘要，6 项对象/归档已不可用，
另 1 项为 GNU 合成的 `linker stubs`，不是缺失的物理文件。该轮旧报告把后者
误归为临时路径；后续解析器已单列 linker-generated，不修改既有工件或其摘要。
19 项摘要仅是 CI 记录，本机未持有这些原始链接输入，不冒称已逐字节重核其内容；
仍缺逐文件许可、工具链/静态依赖对应源码及准确链接归属，未部署 Android。

2026-11-09 glidesort 补充核验：`glidesort-0.1.2.crate` 的 `.cargo_vcs_info.json`
固定 `orlp/glidesort@c4df9518ec23a424a867b3d50967f0aaafe3c0fd`。对应 codeload
归档 SHA-256 `f7b01ecb077689763d80ce6897b700b594a228d018f2734d95fe69098ff6fa1b`，
本机复核 crate 的 16 份源文件/README/原始 manifest 与提交逐字节一致；只排除
Cargo 自动生成的 `Cargo.toml`、`Cargo.lock` 与 `.cargo_vcs_info.json`。
该提交归档没有 LICENSE/COPYING 文件，GitHub 当前仓库根同样未提供独立原文，
API license=null；`Cargo.toml` 的 `MIT OR Apache-2.0` 声明和 README 的署名不替代
实际版权/许可通知。未伪造 MIT 作者年份、未从其他项目借许可文本；此项保持
blocked，待上游补齐或换用经审查的实现，不能仅因源码匹配批准分发。

后续实验配方改用自有薄适配层调用 Rust `slice::sort_by` / `sort_by_key`，不复制
glidesort 实现。仅在四个固定文件原始摘要匹配时，移除 workspace/fff-core 的
glidesort 声明与锁文件中唯一依赖边/包记录，替换两个内部排序入口；保存每项
修改前后摘要及修改后源码/锁文件。继续使用 `--locked` 构建，拒绝依赖图仍选中
glidesort，独立测试升/降序、稳定同键、空/单元素、非 Copy 与 panic 安全。
新实现放弃共享临时缓冲优化，不能声称性能等价；新的 Rust 标准库来源/许可仍须
审查。原始来源候选树和旧工件继续含 glidesort 且 blocked，只有修改后的实验
构建可声明已排除该依赖；真实 CI 排序/搜索/glob/TUI 尚待回归，不批准 APK。
本机已对固定四文件实际应用补丁并复核全部修改摘要，Windows rustc 编译后的
3 项自有排序测试通过；这不替代 arm64/Linux CI 或 Android/性能验证。

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
