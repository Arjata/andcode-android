# 可执行工具入口命名规范(docs/NAMING.md)

> 版本: v1.0 · 2026-11-06 · 适用: bundle 交付包、Tier M/A/P 全部形态、本仓库脚本
> 本规范是**承重规范**:targetSdk 37.2 的 `jniLibs` 只打包 `lib*.so`、数据目录禁止
> exec、动态链接按 soname 精确解析——命名规则与这三条平台硬约束绑定(DESIGN §1.2)。
> 冲突时以本规范为准;修改本规范必须同步 `bundle/manifest` 与 CI 门禁(§7)。

---

## 1. 术语

| 术语 | 定义 |
|---|---|
| **逻辑名** | 用户或程序调用的名字(PATH 中的命令、git 的 exec-path 助手名等) |
| **物理名** | 文件在某一形态下的实际文件名(bundle 规范布局内,或 Tier P 的 jniLibs 内) |
| **规范布局(canonical)** | bundle tarball 内的统一目录结构,三种形态共用的"源格式" |
| **包装器(wrapper)** | 先设置环境(loader/LD_PRELOAD/PATH)再 exec 上游 ELF 的入口脚本 |
| **链接农场(link farm)** | Tier P 首启动在 `filesDir` 内生成的"逻辑名 → 物理名"符号链接树 |
| **slug** | 由逻辑路径派生、满足 `lib*.so` 约束的物理名主体 |

## 2. 通用规则

1. 命令名、脚本名、目录名、slug:**小写字母/数字/连字符**(`[a-z0-9-]`),禁空格、
   禁下划线、禁大写;最长相邻段 32 字符,整名(含 `libandcode-`/`.so`)≤ 64 字符。
2. 环境变量例外:`ANDCODE_` + SCREAMING_SNAKE(§5)。
3. 上游原始名**原样保留**为逻辑名(`opencode`、`git`、`ssh`、`dropbear`),
   不加前缀、不改大小写——用户与 opencode 内部调用(如 spawn `git`)零感知。
4. 本项目自有命令一律带 `andcode-` 前缀,**禁止占用上游命名空间**
   (不得造 `andcode` 无连字符命令冒充上游,也不得给上游命令加我们的小名)。
5. 别名仅允许 POSIX 标准名:唯一已注册别名 `ssh → dbclient`。
6. 一切新名字必须先登记到 §8 注册表再使用;CI 门禁(§7)按注册表校验。

## 3. 命名空间注册表(权威分配)

| 形式 | 归属 | 示例 |
|---|---|---|
| `libandcode-*.so` | **Tier P 物理名总命名空间**:所有打入 jniLibs 的文件(上游 ELF、包装脚本、loader、本项目的 .so) | `libandcode-git.so` |
| `andcode-*`(无扩展名) | 本项目提供给用户的命令/服务入口(bundle `bin/`、`sbin/`) | `andcode-doctor` |
| `*.bin`(仅规范布局内) | 与同名包装器共存的上游 ELF 本体 | `root/bin/opencode.bin` |
| 无前缀原名 | 上游逻辑命令(经包装器或直接暴露) | `opencode`、`git` |
| `ANDCODE_*` | 环境变量 | `ANDCODE_TIER` |
| `andcode` | Magisk 模块 id / 组件标识 | `module.prop` 的 `id=andcode` |
| `dev.andcode.app`(占位,可随发布组织调整) | APK applicationId | `app/build.gradle` |
| `.sh` 后缀 | **仅限仓库内开发脚本**(`scripts/`);bundle 与 PATH 内命令一律无扩展名 | `scripts/deploy-adb.sh` |
| `andcode-terminal-ime.js` | APK assets 内自有 Web 终端输入法适配脚本(非 PATH 命令) | `app/app/src/main/assets/andcode-terminal-ime.js` |
| `andcode-terminal-ime.test.mjs` | 上述脚本的 Node 内置测试(开发期,不进 APK) | `app/tests/andcode-terminal-ime.test.mjs` |
| `projects`、`import-<随机值>` | APK filesDir 项目目录与导入暂存目录;仅数据,不作为可执行入口 | `files/projects/<项目名>`、`files/import-<随机值>` |
| `andcode-settings` | APK 私有 SharedPreferences 名,保存终端/导出偏好与选中项目 | 不保存 API key |
| `terminal-backend`、`ubuntu-loopback-proxy` | 上述偏好键;新终端选择 `bash`/`ubuntu-proot`,代理默认关闭且显式选择,不影响已有会话或 Web | APK SharedPreferences |
| `ProjectsActivity.java`、`SettingsActivity.java`、`AppSettings.java`、`ProjectArchive.java`、`ProjectArchiveTest.java`、`UtilityActivity.java` | APK 项目/设置组件、共享页面及 ZIP 安全测试(Java 类文件遵循类名) | `dev.andcode.app` |
| `ic_more.xml` | APK 项目卡的更多操作矢量图标(Android resource 采用现有 snake_case 风格) | `res/drawable/ic_more.xml` |
| `ic_nav_projects.xml`、`ic_nav_settings.xml` | APK 共享抽屉的项目/设置矢量图标(沿用 Android resource snake_case) | `res/drawable/` |
| `TerminalExtraKeys.java` | APK 自有终端附加键控件,复用 TerminalView 输入协议 | `dev.andcode.app` |
| `term-env.sh`、`term-bashrc` | APK filesDir 生成的系统 sh / Bash 启动配置,仅由 shell 读取,不是可执行文件 | `files/term-env.sh`、`files/term-bashrc` |
| `etc/third-party/bash-copyright`、`etc/third-party/ncurses-copyright` | 随包 Bash / libtinfo 的 Ubuntu 版权及许可文本,数据文件不进入 jniLibs | bundle `etc/third-party/` |
| `etc/third-party/gpl-3` | Bash 版权文本引用的完整 GPLv3 许可证 | bundle 数据文件 |
| `build-ubuntu-rootfs.sh` | CI 原生 arm64 Ubuntu 开发镜像构建配方 | `scripts/` |
| `andcode-ubuntu` | root 专用 chroot 原型管理入口,不放入模型 PATH | `runtime/ubuntu/andcode-ubuntu` |
| `ubuntu-rootfs-test.sh` | Linux CI 镜像/普通用户编译与 apt 冒烟 | `scripts/` |
| `validate-ubuntu-rootfs.py` | 构建期 rootfs 结构/链接校验,不是设备安装器 | `scripts/` |
| `andcode-ubuntu-arm64.img.gz`、`andcode-ubuntu-arm64.img.gz.sha256` | 4 GiB ext4 开发镜像及压缩文件摘要,仅 CI 工件 | `dist/` |
| `andcode-ubuntu-packages.tsv`、`andcode-ubuntu-build.txt` | dpkg 包版本/来源与 Docker 镜像身份,仅 CI 工件 | `dist/` |
| `andcode-ubuntu`(目录) | root 专用实例,与轻量 bundle 和未来 PRoot 实例隔离 | `/data/adb/andcode-ubuntu/` |
| `andcode-ubuntu-ci`、`ci-validation`(首参数) | 可信 CI 镜像的独立验收实例;安装器/manager 只允许此固定替代目录,拒绝覆盖,不接受任意路径 | `/data/adb/andcode-ubuntu-ci/` |
| `ubuntu.img`、`rootfs`、`session-lock` | root 实例镜像/挂载点/并发锁,不接受应用传入替代路径 | `/data/adb/andcode-ubuntu/` |
| `andcode-image` | 镜像内部格式/发行版/架构标记 | guest `/etc/andcode-image` |
| `ubuntu-development.yml` | 手动触发的镜像构建与 Linux 冒烟 workflow | `.github/workflows/` |
| `andcode-ubuntu-install` | root 专用可信 CI 镜像安装器,摘要/空间/权限检查,不接收 ZIP | `runtime/ubuntu/andcode-ubuntu-install` |
| `ubuntu-rootfs-validator.test.py` | rootfs 构建校验器的合成归档回归测试 | `scripts/` |
| `compare-ubuntu-rootfs.py`, `compare-ubuntu-rootfs.test.py` | Build-only read-only canonical archive / original ext4 tree comparison and synthetic regressions; paths, types, modes, UID/GID, file bytes and links; excludes timestamps, ACLs and xattrs | `scripts/` |
| `andcode-ubuntu-tree-review.json` | Canonical archive / original ext4 tree comparison result; no runtime or source approval | Experimental mmdebstrap artifact |
| `UBUNTU.md` | 双后端状态、可信镜像安装流程与实机准入清单 | `docs/` |
| `bootstrap-ubuntu-device.sh` | root 设备开发验证配方,固定 Ubuntu Base 摘要,不替代 CI 正式安装 | `scripts/` |
| `loopback-proxy`(参数值) | 设备开发验证显式选择现有 `http://127.0.0.1:7890` 代理,仅该调用透传 http_proxy/https_proxy;不关闭 TLS 校验 | Ubuntu 引导/设备测试参数 |
| `ubuntu-device-test.sh` | root chroot 真机联网/apt/权限/编译/退出清理验证,不代表 PRoot 通过 | `scripts/` |
| `ubuntu-network-diagnose.sh` | root 人工只读检查 Android 13 BPF 网络规则/当前 APK 与固定 guest UID;不修改设置/权限表,不借用 UID 执行 | `scripts/` |
| `launcher.test.py` | Linux CI 编译自有 launcher,ASan/UBSan 检查直拉及 PRoot argv 组装/参数保真 | `scripts/` |
| `wrapper.test.py` | Linux CI 检查包装器 direct loader 的 --preload 单进程注入与 Bionic 子进程环境隔离 | `scripts/` |
| `bash-launcher.c`、`bash-launcher.test.py` | Tier P 的 bin/bash 静态 ELF 入口及 Linux 回归,替代原 libandcode-cmd-bash.so 脚本,供 PTY daemon 直接 exec;不增加物理命令名 | `bundle/launcher/`、`scripts/` |
| `build-android-tinfo.sh`、`android-tinfo.test.py` | Android 专用 ncurses 构建及真实初始化/内核权限/无身份调用回归;固定 Ubuntu 源码与补丁,不改标准 Linux bundle | `scripts/` |
| `collect-opencode-native-sources.py`、`collect-opencode-native-sources.test.py` | 固定四个原生扩展的候选源码归档摘要/构建输入/声明与嵌套依赖清单;只采集证据,不批准分发 | `scripts/` |
| `native-source-evidence`、`native-source-review.json` | 源码实验的候选对应源码归档与审查索引;仅 CI 诊断工件,不进入 APK | 实验 stage/ |
| `collect-opencode-native-runtime.py`、`collect-opencode-native-runtime.test.py` | 从 CI Ubuntu 24.04 sysroot 收集实验 glibc/GCC 动态库,验证递归依赖及版本化符号,不修改正式 bundle | `scripts/` |
| `runtime`、`native-runtime-review.json` | 源码实验运行库目录与包版本/源码包/摘要/依赖证据;仅诊断工件,非许可批准 | 实验 stage/ |
| `collect-opencode-native-rust.py`、`collect-opencode-native-rust.test.py` | 按候选发布 target/feature 查询 Cargo normal/build 图,收集 lock 摘要校验的 registry 归档;不执行构建脚本或批准分发 | `scripts/` |
| `native-rust-evidence`、`native-rust-review.json` | 候选 Rust 依赖树、固定 crate 源码/声明索引和工具版本;不是 npm ELF 实际链接证明 | 实验 stage/ |
| `serial-rs-<commit>.tar.gz` | serial 0.4.0 缺随包声明时的固定上游来源,必须验证 crate 全部普通文件与 serial/ 子目录对应 | `native-rust-evidence/` |
| `build-opencode-native-pty.py`、`build-opencode-native-pty.test.py` | CI 从固定 bun-pty 源码及 lock 重建 arm64 glibc PTY,校验后仅替换实验 npm 输入 | `scripts/` |
| `native-pty-build`、`native-pty-build-review.json` | 实验 PTY 源码/构建日志/命令/工具版本/前后 ELF 摘要;不批准分发或 Android 准入 | 实验 stage/ |
| `build-opencode-native-watcher.py`、`build-opencode-native-watcher.test.py` | 固定 Parcel watcher Linux 源码及 N-API 头重建,验证真实文件事件后仅替换实验 npm 输入 | `scripts/` |
| `native-watcher-build`、`native-watcher-build-review.json` | watcher 固定源码/头文件归档/编译命令/事件探针与新旧 ELF 摘要;仅 CI 诊断 | 实验 stage/ |
| `native-watcher-build-inputs.json` | 编译器 -H 实际引用的常规头文件与显式源文件摘要/来源分类/声明线索;非逐文件许可批准 | 实验 stage/ |
| `build-opencode-native-fff.py`、`build-opencode-native-fff.test.py` | 固定 fff 源码/lock/zlob feature 的 Linux arm64 诊断重建及失败不替换回归 | `scripts/` |
| `native-fff-build`、`native-fff-build-review.json` | fff 固定源码/选中 crate 归档、Cargo 消息、GNU 链接 map、Bun 搜索/glob 探针与前后摘要;不批准分发 | 实验 stage/ |
| `build-opencode-native-opentui.py`、`build-opencode-native-opentui.test.py` | 固定 OpenTUI/Zig 0.17.0/FFmpeg/zlib 的 Linux arm64 诊断重建,失败不替换 npm 输入 | `scripts/` |
| `native-opentui-build`、`native-opentui-build-review.json` | OpenTUI 固定源码/补丁/构建命令/日志/FFmpeg 配置和对象摘要/前后 ELF 证据;不批准分发 | 实验 stage/ |
| `link-inputs` | OpenTUI 实验实际 ld.lld 命令的对象/静态库/链接期动态桩副本,按参数序号保留并记录原路径与摘要;不是运行库或许可批准 | `native-opentui-build/` |
| `zig-library-resources.tar.gz` | 固定 Zig 0.17.0 归档中的 lib/ 资源与根 LICENSE/README 原字节,排除工具可执行文件;含工具链运行库源码/声明候选,非完整对应源码批准 | `native-opentui-build/` |
| `crc-probe.c`、`crc-probe`、`crc-probe.log` | 自有 CRC 逐位参考/分块对照探针、Linux CI 临时 ELF 与编译/运行日志;只验 FFmpeg 通用 CRC,不进入 APK | `native-opentui-build/` |
| `link-replay/`、`link.map`、`archive-extraction.tsv`、`link.log`、`abi.log` | 同一固定 Zig linker 仅用保留输入重放的隔离目录与 map/归档抽取/运行日志;要求 ELF 字节一致,不等同修改版重链接批准 | `native-opentui-build/link-replay/` |
| `andcode-library-only` | OpenTUI 实验 Zig 构建选项;仅配置明确的 library-target,不配置无关 musl 测试/benchmark 图,不关闭所选库视频门禁 | 构建期 `-D` |
| `manifest-opencode-native.py`、`manifest-opencode-native.test.py` | 实验工件全文件 SHA-256 清单与回归;跟随内部链接,拒绝越界/循环/特殊文件,与上传器实际文件集合一致 | `scripts/` |
| `ANDCODE_SERVE_PID` | Linux 源码实验 API 探针读取自有服务 maps 的 PID;不用于设备进程发现或终止 | 实验 CI |
| `ncurses-build.txt`、`ncurses-upstream-copying` | Android libtinfo 固定源码摘要/构建配置/上游版权声明,随包 manifest 跟踪 | `etc/third-party/` |
| `proot-app-gate.sh` | 应用终端内手动触发的最小 PRoot/ptrace 准入,输出域/uid/seccomp/退出码;不代表 Ubuntu 完整支持 | `scripts/` |
| `proot-rootfs-gate.sh` | 应用域原版 Ubuntu Base Bash 独立实例准入,不修改 SELinux 或 glibc | `scripts/` |
| `proot-development-gate.sh`、`proot-development-gate.txt` | 应用域独立 Ubuntu 的 apt/工具链/新 ELF/PTY 验证脚本与 APK files 诊断输出 | `scripts/`、APK `files/` |
| `proot-terminal-test.sh`、`proot-terminal-test.txt` | 应用域启动器参数/单项目映射/失败拒绝/stdin/退出码回归;只创建和清理自有临时夹具 | `scripts/`、APK `files/` |
| `term-ubuntu-proot`、`term-ubuntu-proot.sh` | APK assets 启动模板及 filesDir 副本,系统 sh 解释;仅映射会话创建时选中的单个私有项目,不提权 | APK `assets/`、`files/` |
| `proot-gate.txt` | APK 私有临时开发诊断输出 | `files/` |
| `proot-rootfs`、`proot-rootfs-gate.txt` | 免 root 后端准入的独立 Ubuntu Base 实例与诊断,不共享 chroot 可写层 | APK `files/` |
| `ubuntu-base-app-gate.tar.gz` | 固定摘要官方 Base 的独立只读开发输入副本,供真实应用域读取 | `/data/local/tmp/` |
| `prepare-proot-gate.py` | Build-time conversion of fixed-digest Ubuntu Base or an explicitly digested trusted CI rootfs; bounded hardlink materialization, guest-relative links, privilege stripping, unchanged ELF bytes; not an APK installer | `scripts/` |
| `prepare-proot-gate.test.py` | Digest, link, content, resource-limit and no-overwrite regression tests for build-time rootfs conversion; no downloads | `scripts/` |
| `busybox`(root 实例副本) | 复用现有独立 BusyBox 载荷处理 Android Toybox 不兼容的 bind mount/归档提取,root:root 0700 | `/data/adb/andcode-ubuntu/busybox` |
| `ubuntu-base-24.04.4-base-arm64.tar.gz` | 官方 Ubuntu Base 24.04.4 arm64 开发引导输入,固定 SHA-256 | 开发暂存 `/data/local/tmp/`,不入库 |
| `andcode-bundle-android-arm64-v<semver>.tar.gz` | Android 应用域专用 seccomp 补丁副本与同名 `.sha256`;不改标准 Linux 原始 bundle | CI 工件,非已验证 locked 交付 |
| `andcode-tier-p-native` | CI 中间工件:arm64-v8a 原生物理名、manifest.farm、assets/andcode-runtime 数据;非完整自包含 APK | Actions artifact |
| `andcode-apk-intermediate` | CI debug APK 与 Lint 报告,仅验证中间原生载荷打包;非正式签名/自包含产品 | Actions artifact |
| `andcodeNativeDir` | Gradle 显式原生工件目录属性,包含 arm64-v8a/manifest.farm/assets;不设置时保留开发空载荷构建 | `-PandcodeNativeDir=<绝对目录>` |
| `andcode-runtime` | APK assets 内 CI 生成的只读 bundle 数据与 manifest.farm,不含运行期解包 ELF | `assets/andcode-runtime/` |
| `RuntimePayload.java`、`RuntimePayloadTest.java` | APK 只读原生载荷链接农场初始化与平台 JDK 安全回归 | `dev.andcode.app`、`app/tests/` |
| `pty-launcher.c` | 自有静态 musl PTY 入口,由 /proc/self/exe 定位同目录 loader/daemon,不依赖固定安装路径 | `bundle/launcher/` |
| `repair-elf-verdef.py`、`repair-elf-verdef.test.py` | 构建期校验/修复 patchelf 搬迁版本定义节后遗留的 DT_VERDEF 地址;只从 ELF 节表取地址,拒绝模糊布局 | `scripts/` |
| `patch-seccomp.test.py` | Linux CI 合成字节夹具验证 seccomp 补丁、幂等、旧补丁升级及错误基线拒绝 | `scripts/` |
| `native-payload-device-test.sh` | 从 APK 终端运行的原生载荷准入;不以 adb/run-as 代替应用域,结果仅写入私有数据日志 | `scripts/` |
| `native-payload-test.txt` | 上述准入日志,不保存口令/模型配置 | APK filesDir |
| `opencode-native-imports.ts`、`opencode-native-imports.test.ts` | Bun 源码构建实验插件与回归,将原生扩展导入改为显式预置路径;不修改官方二进制 | `scripts/` |
| `prepare-opencode-native-build.py` | 固定上游提交的源码构建实验接线,拒绝不匹配锚点 | `scripts/` |
| `audit-opencode-native.py`、`audit-opencode-native.test.py` | 实验工件 ELF/依赖/对齐/摘要审计与回归,拒绝残留 Bun 内嵌 ELF 或 musl 闭包 | `scripts/` |
| `collect-opencode-native-licenses.py`、`collect-opencode-native-licenses.test.py` | 固定安装树原生扩展的包版本/许可/包内声明快照,缺声明明确记录为 blocked,不构成发布许可批准 | `scripts/` |
| `native-license-review.json`、`native-license-evidence/` | 实验工件中四个原生扩展的人工审查待办与包内声明副本,不进入正式 APK | 源码实验工件 |
| `runtime-declarations/` | 固定 Bun/WebKit 提交的声明与构建脚本原字节,逐文件摘要校验;只作来源候选,不是完整对应源码或正式 notices | `native-source-evidence/` |
| `sort-test`、`sort-test.log` | 自有标准库稳定排序适配层的独立 Rust 测试 ELF 与编译/运行日志;仅 Linux 源码实验,不进入 APK | `native-fff-build/` |
| `ffmpeg-notice-candidates.json` | 从实际编译依赖全文中保留声明候选注释的字节范围、原文与摘要;不是正式 notices 或完整许可判定 | `native-opentui-build/` |
| `zig-generated-sources/` | Original bytes and per-file digests of `b/<hash>/builtin.zig` from the pinned Zig global/local caches after building; generated-input snapshots only, not proof of complete compiler inputs | `native-opentui-build/` |
| `modified-crc-relink/` | Isolated modified FFmpeg CRC source, replacement object, retained-input relink, map and runtime probes; Linux diagnostic only, never a staged APK input | `native-opentui-build/` |
| `media-generator-replay/`, `ops_lookup.gen.c`, `ops_neon.gen.S`, `lookup.log`, `neon.log` | Build-only isolated stdout/logs from fixed FFmpeg `ops_asmgen -lookup` / `-ops`; byte comparison with retained generated inputs, not a license or full-source approval | `native-opentui-build/` |
| `media-generator-rebuild/`, `source/`, `system-headers/`, `ops_asmgen`, `ops_asmgen.o`, `ops_asmgen.d`, `ops_asmgen.i`, `compiler.log`, `compile.log`, `link.log`, `preprocess.log`, `lookup.log`, `neon.log`, `ops_lookup.gen.c`, `ops_neon.gen.S` | Isolated host-generator recompilation, complete observed dependency snapshots, preprocessing and two-mode output comparison; build-only diagnostic, never staged in an APK | `native-opentui-build/` |
| `media-preprocess/`, `inputs/`, `<sha256>`, `<index>.i`, `<index>.s`, `<index>.d`, `<index>.log` | Post-build fixed-Zig preprocessing samples and content-addressed observed dependency snapshots for recorded media translation units; not proof of the original compile-time input set | `native-opentui-build/` |
| `media-object-relink/`, `objects/`, `<index>.o`, `<index>.log`, `libopentui.so`, `link.log`, `link.map`, `archive-extraction.tsv`, `abi.log`, `crc-probe`, `crc-probe.log`, `crc-execution.log` | Isolated recompilation of all sampled media units, with the separately instrumented CRC object substituted for execution probes; no staged APK inputs, original-object byte equality or complete modified-source claim | `native-opentui-build/` |
| `probe-opencode-media-tui.py`, `probe-opencode-media-tui.test.py` | Isolated replacement-library PTY/TUI diagnostic and synthetic rejection tests; never modify the staged native baseline | `scripts/` |
| `media-tui/`, `native/`, `home/`, `tmp/`, `tui.log`, `tui-output.bin`, `tui-maps.txt`, `review.json` | Replacement OpenTUI TUI diagnostic, original-name lookup alias with explicitly different digest, copied other native files, isolated extraction directories and mapping/render evidence; not a valid release payload | `media-object-relink/` |
| `source-rules` | Explicit diagnostic selector for fresh source-rule replacement-library TUI; fixed input/output under modified-media-source-relink, never an arbitrary path override | `probe-opencode-media-tui.py` fourth argument |
| `media-tui/`, `native/`, `home/`, `tmp/`, `tui.log`, `tui-output.bin`, `tui-maps.txt`, `review.json` | Fresh source-rule library TUI evidence isolated from the sampled-object TUI and all staged native inputs; not a release manifest or Android admission | `modified-media-source-relink/` |
| `rebuild-zlib-generators.py`, `rebuild-zlib-generators.test.py` | Isolated host reconstruction of zlib MAKECRCH/MAKEFIXED and a same-translation-unit GEN_TREES_H harness, retained preprocessing inputs and byte-comparison rejection tests | `scripts/` |
| `gentrees/`, `trees-generator.c`, `trees.h` | Own same-translation-unit entry point for the fixed upstream static tree initializer and isolated GEN_TREES_H output; not an upstream standalone build command or release input | `zlib-generator-rebuild/` |
| `swscale-generator-rebuild/`, `build.log`, `run.log`, `uops_macros.h` | Configured source-rule build of libswscale/tests/sws_ops and isolated -macros stdout comparison; test executable remains in the copied media build tree, never a release input | `modified-media-source-rebuild/` |
| `rebuild-modified-media.py`, `rebuild-modified-media.test.py` | Isolated fresh configured FFmpeg/zlib source-rule rebuild with the pinned CRC instrumentation; no sampled-preprocessor reuse or baseline replacement | `scripts/` |
| `modified-media-source-rebuild/`, `native/`, `build.log`, `review.json` | Fresh copied build script, pinned media archives/pristine source trees, modified CRC source, configure/make outputs and full selected-media object evidence; not complete corresponding-source or distribution approval | `native-opentui-build/` |
| `failed-modified-media-source-build` | Failed isolated modified media source-rule inputs, logs and partial outputs; diagnostic evidence only | CI artifacts |
| `relink-modified-media.py`, `relink-modified-media.test.py` | Relink retained non-media OpenTUI inputs with all fresh source-rule media objects, then run isolated ABI/CRC probes; no baseline or APK replacement | `scripts/` |
| `modified-media-source-relink/`, `libopentui.so`, `link.map`, `archive-extraction.tsv`, `link.log`, `abi.log`, `crc-probe`, `crc-compile.log`, `crc-run.log`, `review.json` | Fresh source-rule library substitution and Linux ABI/CRC evidence; not full source, decoder, TUI or legal approval | `native-opentui-build/` |
| `zlib-generator-rebuild/`, `source/`, `system-headers/`, `makecrch/`, `makefixed/`, `generator`, `<index>.i`, `<index>.d`, `<index>.o`, `<index>-preprocess.log`, `<index>-compile.log`, `link.log`, `run.log`, `compiler.log`, `crc32.h`, `inffixed.h`, `review.json` | Copied pristine zlib source, host-header snapshots and isolated generated outputs; never replace media build inputs or assert toolchain/source closure | `native-opentui-build/` |
| `original-crc.c`, `modified-crc.c`, `crc.patch`, `crc.o`, `crc.d`, `compile.log`, `link.log`, `source/`, `build/` | Original/transformed bytes, recorded diff, replacement object/dependencies, logs and isolated configured trees for the single-object relink diagnostic | `modified-crc-relink/` |
| `andcode_crc_relink_calls` | Diagnostic-only exported counter accessor added to the modified CRC translation unit; not a product ABI | Experimental `modified-crc-relink/libopentui.so` |
| `failed-fff-build-logs` | fff 实验构建失败时保留排序/编译日志的诊断工件,不含可分发批准 | CI artifacts |
| `build-ubuntu-mmdebstrap.sh` | Build-only native arm64 mmdebstrap experiment; signed Ubuntu snapshot `20261110T000000Z`, independent output, no device installer | `scripts/` |
| `build-ubuntu-mmdebstrap.test.py` | Native Linux rejection tests for recipe arguments, architecture and existing outputs; skipped on Windows | `scripts/` |
| `collect-ubuntu-sources.py`, `collect-ubuntu-sources.test.py` | Build-only exact installed source-version acquisition through authenticated apt; no source extraction, compilation or license approval | `scripts/` |
| `andcode-ubuntu-source-inputs/`, `andcode-ubuntu-source-inputs.json` | Experimental per-source downloaded .dsc/archive files and command logs, with a hash inventory; staged in a new guest `/tmp/andcode-ubuntu-source-inputs` directory and copied outside the image | Optional mmdebstrap CI artifact |
| `andcode-ubuntu-source-acquisition.log` | Build-only source download progress/failure diagnostic; no source-delivery approval | Optional mmdebstrap CI artifact |
| `andcode-ubuntu-rootfs.tar.gz` | Validated canonical rootfs archive from the mmdebstrap experiment; input for future PRoot packaging, not an APK importer | Experimental CI artifact |
| `andcode-ubuntu-proot.tar.gz`, `andcode-ubuntu-proot.tar.gz.sha256` | Build-time trusted canonical rootfs conversion and digest; hardlinks materialized and absolute symlinks made guest-relative, no ELF patching or device installation | Experimental mmdebstrap artifact |
| `andcode-ubuntu-rootfs.tar.gz.sha256`, `mmdebstrap.log`, `mmdebstrap-copyright`, `ubuntu-indexes/`, `ubuntu-sources.list` | Archive digest, bootstrap log, installed tool notice, retained signed indexes and exact source configuration | Experimental rootfs output |
| `andcode-ubuntu-mmdebstrap-prototype` | Independently gated rootfs experiment artifact; never replaces the Docker artifact automatically | CI artifacts |
| `andcode-ubuntu-mmdebstrap-diagnostics` | Failed bootstrap logs and metadata only; no image/archive release payload | CI artifacts |
| `probe-opencode-native.py` | Linux CI 实验 API 准入:普通/持久 PTY、shell,口令只在内存使用不输出 | `scripts/` |
| `probe-opencode-native-tui.py` | Linux CI 独立 PTY 启动源码实验 TUI,要求实际映射预置 OpenTUI 并渲染;仅终止自有进程组 | `scripts/` |
| `opencode-native-prototype.yml` | 手动执行的原生扩展预置源码构建实验;失败/未审计工件不得接入 APK | `.github/workflows/` |
| `libandcode-oc2-native-<sha256前16位>.so` | 实验 Bun 插件按内容命名的原生扩展预置副本,完整摘要校验去重/冲突 | 实验输出 native/ |
| `oc2-native.tsv` | 上述副本的来源/完整摘要/长度记录;不是正式 bundle manifest | 实验输出 |
| `libandcode-usr-lib-opencode-pty-opencode-pty.so` | 预置 process-daemon v0.4.0 ELF 本体;静态 libandcode-opencode-pty.so 入口显式调用 loader | nativeLibraryDir |
| `oc2` | 固定 V2.2.6 ELF 本体逻辑名,用于 serve,与旧 opencode 分开;物理名 libandcode-oc2.so | bundle bin/oc2.bin |
| `etc/third-party/opencode-v2-license`、`etc/third-party/opencode-pty-license` | 固定版本 MIT 版权许可文本,随 data 交付 | bundle/APK assets |
| `andcode-runtime-<sha256>`、`andcode-runtime-stage-<随机值>` | filesDir 内按 manifest/nativeLibraryDir 身份区分的链接/数据目录与原子暂存;从不复制 ELF,不删除旧版本 | APK filesDir |
| `libandcode-git-core-<命令>.so` | git-core 包装器/自有 launcher 统一前缀;避免 git/receive-pack/upload-pack 等与 usr/bin/*.bin 冲突 | Tier P nativeLibraryDir |

**豁免**:Magisk 平台固定文件名(`customize.sh`、`service.sh`、`uninstall.sh`、
`module.prop`)遵循 Magisk 官方约定,不受第 2.1 条"无 .sh"约束。
**保留区**:APK 自有 NDK 库(jackpal fork 等)**禁止**使用 `libandcode-` 前缀,
避免与打包工具链混淆;其命名沿用原库名(`libterminal-jni.so` 等)。

## 4. 逻辑名规范(用户视角)

### 4.1 `bin/` — 交互命令(PATH 内)

| 逻辑名 | 类型 | 说明 |
|---|---|---|
| `opencode` | 包装器脚本 | 设 env → exec `opencode.bin`(规范布局)/ `libandcode-opencode.so`(Tier P) |
| `opencode-pty` | 上游直通(opencode 运行时下载的终端插件帮助进程) | 上游会写入 `~/.cache/opencode/bin/opencode-pty/<版本>/` 且校验"普通文件+uid+sha256"(拒 symlink);应用域禁 exec → **预置副本 + 指路**:serve/终端 env 设 `OPENCODE_PTY_BIN` 指向预置副本;`OPENCODE_PTY_SOCKET_DIR` 指向应用 filesDir(§5);Tier P 物理名 `libandcode-opencode-pty.so`,开发部署 interp 短路径必须是可执行 loader 普通文件,不可假定 symlink 可达 |
| `git`、`ssh` | 上游直通(经链接农场指向物理名) | 供 opencode 内部 spawn 与用户使用 |
| `bash` | 上游交互 shell,Ubuntu 24.04 基线独立程序聚合;终端优先加载预置副本 | `root/bin/bash.bin` → `libandcode-bash.so`;包装器 `libandcode-cmd-bash.so` |
| `andcode-doctor` | 自研 | 环境自检:loader、shim、DNS、JIT、phantom-killer 状态,输出诊断报告 |
| `andcode-ubuntu-proot` | 开发终端 shell 函数;显式进入已安装 PRoot 独立实例,退出返回原 Bash | `term-ubuntu-proot` 解释执行;不是已完成自包含安装的产品入口 |
| `andcode-sshd` | 自研 | 内置 dropbear 生命周期:`start|stop|status` 子命令式 |
| `opencode-tui` | 上游直通 | 若核实 opencode 需按名调用 TUI 二进制,预置为该逻辑名(DESIGN §4.1) |

### 4.2 `sbin/` — 服务与维护入口(不在默认 PATH)

| 逻辑名 | 说明 |
|---|---|
| `andcode-entry` | 统一入口(原 entry.sh 更名):初始化 env、生成 `etc/resolv.conf`、按参数派发 |
| `andcode-mkresolv` | 从 Android `net.dns*` 生成 resolv.conf(供 service.sh 单独复用) |
| `andcode-ubuntu` | root 管理原型:`status|shell|exec|admin`;每次会话独立 mount namespace,退出清理;默认普通用户,admin 必须显式请求,暂不向 APK/模型开放 |
| `andcode-ubuntu-install` | root 安装原型,只接受固定暂存路径的可信 gzip 镜像及带外 SHA-256,拒绝覆盖既有实例;至少 5 GiB 可用空间 |

## 5. 环境变量规范

| 变量 | 含义 | 取值示例 |
|---|---|---|
| `NODE_EXTRA_CA_CERTS` | Bun/Node 上游追加 CA 文件;Tier P 仅显式启用后向新 OpenCode Web 后端及其继承环境的子进程设置,不替换内置根 | 应用私有 `custom-ca/<sha256>.pem` |
| `ANDCODE_ROOT` | 逻辑根目录(包装器据此寻址) | `/data/adb/andcode`、`$HOME/andcode` |
| `ANDCODE_EXE_DIR` | 可执行物理目录 | Tier P = `nativeLibraryDir`;其余 = `$ANDCODE_ROOT` |
| `ANDCODE_LOADER` | glibc 动态链接器绝对路径(launcher 用) | `$ROOT/lib/ld-linux-aarch64.so.1` |
| `ANDCODE_LIBPATH` | `--library-path` 值(launcher 用) | `$ROOT/lib`(规范)/`$ANDCODE_EXE_DIR`(Tier P) |
| `ANDCODE_SHIM` | shim 绝对路径(launcher 用) | `$ROOT/shim/libandcode-shim.so` |
| `ANDCODE_NATIVE_STAGE` | 仅构建期 Bun 预置扩展实验插件的独立输出目录;不是 APK 运行时安装入口 | CI work/native-prototype |
| `ANDCODE_TIER` | 形态标识,单字符小写,与 DESIGN 章节一致 | `m` / `a` / `p` |
| `ANDCODE_UBUNTU_PROJECT_NAME` | 新终端创建时快照的私有项目名;空值不映射;入口验证目录与规范路径,拒绝符号链接/越界,不接受宿主任意路径 | `andcode-demo` → guest `/workspace/andcode-demo` |
| `ANDCODE_BUNDLE_VERSION` | bundle 语义化版本 | `1.2.0` |
| `ANDCODE_LOG` | 日志级别 | `debug\|info\|error` |
| `OPENCODE_PTY_BIN` | 上游 v2 预置 PTY 可执行路径覆盖;跳过缓存安装/校验 | Tier P = `nativeLibraryDir/libandcode-opencode-pty.so`;开发期 `/data/local/tmp/andcode/lib/opencode-pty` |
| `OPENCODE_PTY_SOCKET_DIR` | 上游 process-daemon v0.4.0 socket 基目录覆盖;实际追加 `opencode-pty-<uid>/<32 hex>.sock`,保留普通目录/uid/0700 校验 | APK `Context.getFilesDir()`(不用可被清理的 cacheDir);完整 socket 路径 UTF-8 长度须 <104 字节 |

- 透传规则:`OPENCODE_*` 等上游变量允许用户透传,但包装器只设置自己登记的
  `ANDCODE_*` 与必需的运行时变量(`HOME`、`TMPDIR`、`PATH`、`LD_PRELOAD`、
  `LD_LIBRARY_PATH`、`GIT_EXEC_PATH`),**不覆盖**用户显式设置的 `OPENCODE_*`。
- 禁止使用未登记的环境变量名;新增变量须先进 §8 注册表。

## 6. 物理名规范

Tier P 可选 CA 数据注册：`CustomCa.java` / `CustomCaTest.java` 为应用侧校验与
平台 JDK 测试类；`files/custom-ca/<sha256>.pem` 为用户 SAF 导入的单证书副本，
`custom-ca-enabled` / `custom-ca-sha256` 为应用私有偏好键。默认关闭，不预置任何
站点 CA，不联网下载，不进入 native manifest，不改 Android 全局证书库。
`scripts/custom-ca-tls.test.py` 为固定 Bun 的 loopback TLS 追加信任/错误主机名拒绝测试，
仅生成临时测试 CA，不下载或持久信任外部证书。

### 6.1 规范布局(bundle 内,binding Tier M/A)

```
root/bin/opencode            # 包装器脚本(逻辑名 = 文件名)
root/bin/opencode.bin        # 上游 ELF(.bin 后缀仅此场景使用)
root/usr/bin/git ...         # 上游直通,原名
root/sbin/andcode-entry      # 自研,无扩展名
root/lib/ld-linux-aarch64.so.1   # glibc loader,原名(DT 解析不经它,显式调用)
root/lib/libc.so.6 ...           # glibc 依赖库,原名(soname 契约)
shim/libandcode-shim.so      # 本项目 LD_PRELOAD 库(见 §6.3)
```

### 6.2 slug 派生算法(Tier P 重打包,由 `bundle/pack-apk-libs.sh` 执行)

对规范布局内每个文件,按**文件种类**应用下表(种类由 `pack-bundle.sh` 在 manifest
中固化,判据见括号):

| 逻辑路径(规范布局) | kind | Tier P 物理名(jniLibs) |
|---|---|---|
| `root/bin/opencode.bin`(上游 ELF,`.bin` 后缀) | elf-exec | `libandcode-opencode.so`(slug **剥掉 `.bin`**) |
| `root/bin/opencode`(上游命令包装器,同目录存在 `<name>.bin` 时判定) | wrapper-sh | `libandcode-cmd-opencode.so`(`bin/`、`usr/bin/` 下加 **`cmd-`** 段) |
| `root/usr/bin/git` | elf-exec/wrapper-sh | 同上规则(存在 `git.bin` → wrapper) |
| `root/usr/libexec/git-core/git-remote-https`(git 助手包装器) | wrapper-sh | `libandcode-git-core-git-remote-https.so`(libexec 下统一 **git-core-** 前缀) |
| `root/usr/libexec/git-core/git-remote-https`(同路径,**launcher 形态**:静态启动器 ELF 取代 shell 脚本,规避 git spawn 的 shell 链路;真机 P0 验证项) | launcher | `libandcode-git-core-git-remote-https.so`(同 wrapper 规则) |
| `root/usr/libexec/git-core/git`(自有 launcher) | launcher | `libandcode-git-core-git.so`(避免与 `usr/bin/git.bin` 的 ELF 物理名冲突) |
| `root/usr/lib/proot/proot`(proot-me v5.5 不可用,x86-64;采用 **Termux proot 5.1.107 bionic 构建** + loader + libtalloc + libandroid-shmem,GPL-2.0 独立聚合) | elf-exec(bionic) | `libandcode-usr-lib-proot-proot.so`(全路径 slug;**bionic 二进制,不经 glibc loader,Tier P 需单列**) |
| `root/usr/libexec/git-core/git-remote-https.bin`(助手 ELF 本体) | elf-exec | `libandcode-usr-libexec-git-core-git-remote-https.so`(全路径 slug;与包装器不同名,无冲突) |
| `root/sbin/andcode-entry`(本项目自有脚本,无同名 `.bin`) | script | `libandcode-andcode-entry.so`(slug 含 `andcode-` 前缀,允许) |
| `root/lib/ld-linux-aarch64.so.1`(loader 特例:显式路径调用) | glibc-lib | `libandcode-ld-linux.so` |
| `root/lib/libc.so.6`(DT_NEEDED 依赖库) | glibc-lib | `libandcode-libc.so`(slug **剥掉 `.so.N` 版本尾**) |
| `root/lib/libstdc++.so.6` | glibc-lib | `libandcode-libstdc---.so`(slug 字符净化见下) |
| `shim/libandcode-shim.so`(本项目 LD_PRELOAD 库) | preload-lib | `libandcode-shim.so`(原名即合规) |
| `root/etc/ssl/certs/ca-certificates.crt` 等数据文件 | data | **`-`**(data 不进 jniLibs:只读数据经 APK assets → filesDir 原样落位;亦避免长路径超 64 字符) |
| `opencode-pty/<版本>/opencode-pty`(上游运行时下载插件,非 bundle 布局;预置副本进 jniLibs) | elf-exec(MIT,上游 sst/opencode process-daemon) | `libandcode-opencode-pty.so`(slug 同名净化;interp 由打包链改写,见 §4.1 指路口径) |

**slug 字符净化**(在 `/`→`-` 之后):仅保留 `[a-z0-9-]`,其余逐字符替换为 `-`
(`+`、`_`、`.` 等均逐字符替换,连续结果不合并)。物理名全长(含 `libandcode-`/`.so`)≤ 64。

### 6.3 两个关键裁定

1. **DT_NEEDED 依赖库(glibc/libstdc++ 等)**:soname 必须与 `NEEDED` 逐字一致,
   无法简单改名。两条路线,P0 定夺:
   - **路线甲(默认)**:打包时用 `patchelf` 对 sysroot 闭包做全量重写
      (`libc.so.6 → libandcode-libc.so`,同步改 SONAME 与全部 NEEDED),
      连同可执行体一起放入 `nativeLibraryDir`——单一可执行目录,最简;
      **glibc 特例**:libc 自身保留 `libc.so.6` SONAME(loader 依赖该标记执行
      `__libc_early_init`),仅调用者 NEEDED 改物理名;loader 物理名改为
      `libandcode-ld-linux.so`,其自身 SONAME 及 libc 对 loader 的 NEEDED 保持原名。
   - **路线乙(若 P0 证实数据目录可 mmap-exec)**:依赖库保持原名,经 assets
     解压到 `filesDir/lib`,`--library-path` 指向之。
   无论哪条路线,**物理命名空间永远是 `libandcode-*`**,逻辑名记录在 manifest。
2. **包装器脚本在 Tier P 的存在形式**:targetSdk 37.2 禁止 exec 数据目录文件,
   故包装器以 **shebang 脚本体**进入 jniLibs(`libandcode-cmd-*.so`,首行
   `#!/system/bin/sh`),链接农场让逻辑名指到它。`sh <脚本>` 的裸读方式仅允许
   出现在自研代码内部,不作为对用户的约定。

### 6.4 链接农场(首启动生成)

```
$ANDCODE_ROOT/bin/opencode   -> $ANDCODE_EXE_DIR/libandcode-cmd-opencode.so
$ANDCODE_ROOT/bin/git        -> $ANDCODE_EXE_DIR/libandcode-git.so
$ANDCODE_ROOT/usr/libexec/git-core/git-remote-https
                              -> $ANDCODE_EXE_DIR/libandcode-git-core-git-remote-https.so
```

- PATH 只含 `$ANDCODE_ROOT/bin` 与 `$ANDCODE_ROOT/usr/bin`;
- git 的 `GIT_EXEC_PATH` 指向农场内 `usr/libexec/git-core`;
- 使用静态 launcher 时 `bin/git` 是唯一命令入口,不保留打包器生成的重复
  `usr/bin/git` 包装器(保留 `usr/bin/git.bin`);所有非 data 物理名必须唯一,禁止覆盖。
- **禁令**:农场中不得出现与 Android `/system/bin`(toybox)同名的条目
  (`ls`、`cp`、`sh`…);busybox applet 一律以 `busybox <applet>` 显式调用,
  PATH 内不铺 applet 符号链接。

## 7. 发布物与 manifest

### 7.1 发布物命名

| 产物 | 命名 |
|---|---|
| 交付包 | `andcode-bundle-arm64-v<semver>.tar.zst` |
| APK | `andcode-v<semver>-arm64.apk`(applicationId 见 §3) |
| Magisk 模块 | `andcode-magisk-v<semver>.zip` |
| 校验文件 | 同名 + `.sha256` |
| 标准 Linux 产物 | `andcode-linux-arm64-v<semver>.tar.gz`(与 DESIGN §3 兼容性目标对应) |
| Ubuntu 开发镜像(原型) | `andcode-ubuntu-arm64.img.gz` + `.sha256`,4 GiB ext4;仅可信 CI 工件,尚非正式发行物 |

### 7.2 manifest 语法(`bundle/manifest`,TSV,`#` 注释)

```
# logical-path \t physical-tier-p \t kind \t license \t version \t upstream
root/bin/opencode.bin	libandcode-opencode.so	elf-exec	MIT	1.1.2	sst/opencode
root/bin/opencode	libandcode-cmd-opencode.so	wrapper-sh	AGPL-3.0-only	1.0.0	andcode
root/lib/libc.so.6	libandcode-libc.so	glibc-lib(rewritten)	LGPL-2.1	2.39	glibc
shim/libandcode-shim.so	libandcode-shim.so	preload-lib	AGPL-3.0-only	1.0.0	andcode
```

规则:`physical-tier-p` 必须满足 §6.2 算法;`kind` 取值
`elf-exec|wrapper-sh|launcher|glibc-lib|preload-lib|script|data|alias`(launcher =
静态 musl 启动器,来源 `bundle/launcher/launcher.c`,AGPL);CI 以此生成
`THIRD-PARTY-NOTICES.md`(REUSE.md §4)。

## 8. 注册表变更流程与 CI 门禁

1. 新增命令/变量/别名/物理名 → 先改本文件 §3/§4/§5,再改代码;
2. CI 门禁 `scripts/naming-lint.sh`(随 P1 建立)强制:
   - manifest 中 physical-tier-p 匹配 `^libandcode-[a-z0-9-]+\.so$` 且 ≤64 字符;
   - bundle `bin|sbin` 内文件名匹配 `[a-z0-9-]+`(`.bin` 双名规则除外);
   - 链接农场黑名单 = `adb shell ls /system/bin` 快照(构建期固化);
   - APK 自有 NDK 库名不得以 `libandcode-` 开头;
   - 仓库 shell 脚本仅 `scripts/**.sh`;
3. 违规即构建失败;本文件的例外(§3 豁免)必须在此脚本中以显式白名单存在。
