# andcode — 将 opencode 移植到 Android arm64 的设计方案

> 版本: v0.4 (设计稿) · 日期: 2026-11-06
> v0.4 变更: **平台基线钉死 Android 12+ (minSdk 31)、APK targetSdk/compileSdk 37.2**;
> 移除 targetSdk 28 取巧,Tier P 改用 jniLibs 提取(nativeLibraryDir 可执行)方案,
> 新增 W^X/JIT、16K 页对齐、前台服务类型等适配项。
> v0.3 变更: **去除对 Termux 等独立宿主 App 的依赖**,三种交付形态全部自包含
> (Magisk 模块 / adb 包 / 自研最小 APK)。Termux 降级为附录中的可选替代。
> v0.2 变更: 构建基线切换为 Ubuntu 24.04 arm64 (glibc 2.39)。
>
> 目标: 在 Android arm64 设备上运行 opencode(终端 AI 编码代理),并提供一套
> **兼容性 Linux arm64 构建环境**(基线: Ubuntu 24.04 arm64)——该环境下构建出的原生程序可在 glibc ≥ 2.39 的标准 Linux arm64
> 设备(Ubuntu 24.04+/Debian 13+/云服务器等)上直接运行。

---

## 1. 目标与硬约束

### 1.1 设计原则、平台基线与设备矩阵

**核心原则(自包含)**:除 Android 系统本身外,不要求用户安装任何第三方独立程式
(不用 Termux、不依赖 proot-distro 发行版脚本)。所有宿主能力(终端、SSH、
自启动、进程守护)要么由系统入口提供,要么内嵌在我们的交付物里。

**平台基线(钉死)**:

| 项 | 取值 | 含义 |
|---|---|---|
| 最低系统 | **Android 12 (API 31)** | Phantom Process Killer(12 引入)全程伴随,必须在所有形态内置对策 |
| APK compileSdk | **37.2** | 按最新 SDK 构建,可用最新 API/行为 |
| APK targetSdk | **37.2** | 全量接受新平台行为:数据目录 exec 禁令、W^X、FGS 类型强制、edge-to-edge 等;**不使用 targetSdk 28 取巧** |
| 交付物运行环境 | arm64-only | 含 4K 与 16K 页设备(见 §1.2.8) |

| 设备类别 | Root | 可用入口 | 适用交付形态 |
|---|---|---|---|
| A. Bootloader locked | ✗ | ① adb shell(含 Android 11+ 无线调试,免数据线);② 侧载/商店安装我们的 APK | Tier A(adb 包)/ Tier P(自研 APK) |
| B. Bootloader unlocked + root | ✓ | 上述全部 + su/Magisk/开机脚本 | **Tier M(Magisk 模块,首选)**,兼容 A/P |

### 1.2 Android 平台硬约束(设计必须遵守)

1. **libc 不同**:Android 用户态是 Bionic,不是 glibc。glibc 链接的二进制必须
   携带自己的动态链接器与库(本设计的 **glibc sysroot + loader 包装器**,见 §4.1),
   或运行在 chroot 内。
2. **/sdcard 系挂载为 noexec**:所有可执行文件必须放在应用私有目录、
   `/data/local/tmp` 或 `/data/adb/` 下。**任何方案都不允许把 ELF 放在共享存储。**
3. **数据目录 exec 禁令与 W^X(targetSdk ≥ 29 全量生效)**:
   - targetSdk ≥ 29 的应用被 SELinux 域禁止 exec 应用可写数据目录内的 ELF;
     同时强制 W^X(不得匿名 RWX 映射)。
   - **Tier P 的标准解法:JNI 库提取**——所有随包 ELF(opencode、glibc loader、
     git、busybox、dropbear 及其 .so)以 `lib*.so` 形式打入 APK 的
     `jniLibs/arm64-v8a/`,安装时由系统解压到 `nativeLibraryDir`
     (`/data/app/.../lib/arm64/`),该目录**允许 exec**。
   - JIT(JSC):若 Bun 的 JIT 在 W^X 下被拒,回退 `BUN_JSC_useJIT=0`
     (Bun 支持 `BUN_JSC_*` 环境变量),P0 实测定级。
   - 收益:targetSdk 37.2 使 APK **可上架 Google Play**(需满足 §1.2.8 的 16K
     页要求);发布渠道双轨:Play + GitHub Releases/F-Droid。
4. **Android 12+ Phantom Process Killer**:后台 app 的子进程超过阈值(默认
   32 个 / 10 分钟空闲)会被静默杀掉。opencode 会派生 LSP、git、shell 等子进程,
   属于高危场景,需要规避(见 §4.6)。
5. **SELinux**:locked 设备上 shell 域可执行 `/data/local/tmp` 内的 ELF;APK 域
   可执行 `nativeLibraryDir` 内的 ELF(经 jniLibs 提取,见 §1.2.3);都不能碰
   `/lib/ld-linux-aarch64.so.1` 这类绝对 interpreter 路径(一律显式 loader 调用)。
6. **只读的 /etc**:glibc 运行期要读 `/etc/resolv.conf`、`/etc/passwd` 等,
   Android 的 `/etc` 不可写。用我们自研的 **LD_PRELOAD 重定向 shim** 解决(§4.5),
   不为此引入 proot。
7. **真 root(chroot)无上述大部分问题**,Tier M 优先用真 chroot。
8. **16K 页大小设备(Android 15+ 部分机型,Play 对含 NDK 代码应用强制)**:
   - Debian/Ubuntu arm64 工具链默认 `-z max-page-size=65536`,基线 glibc/sysroot
     的 ELF 天然 ≥16K 对齐,**无需重编**;
   - APK 内自有 NDK 代码(jackpal fork 的本地库)必须以 16K 对齐编译
     (`-Wl,-z,max-page-size=16384`),CI 加对齐检查;
   - jniLibs 提取的 glibc ELF 同样受益于上述基线对齐,直接可跑。

### 1.3 opencode 侧的事实假设(Phase 0 逐条验证)

- opencode 由 TypeScript 核心(以 Bun `--compile` 打包为单一可执行文件)+
  Go 编写的 Bubble Tea TUI 组成,官方发布 **linux-arm64 (glibc)** 产物。
- 运行期依赖:`git`(必需)、`rg` 等(增强);认证默认走浏览器 OAuth,
  但支持 API key / 环境变量注入(可完全绕开浏览器)。
- 先行者 `claude-code-termux`(MIT)宣称 Bun 编译产物可在无 proot 的
  glibc 环境下跑通——支持"loader 包装器 + shim"这条最轻路径的可行性。
- **待 P0 核实的关键项**(§4.1 "运行期不落盘"约束是否可满足):
  opencode 是否存在运行期释放/调用 ELF 的行为(如释放 Go TUI 二进制),
  以及是否有预置路径/环境变量机制可指向我们预装的副本。
- 若上述任一假设不成立,风险与备选见 §7。

---

## 2. 总体架构

一句话:**一套构建基线,一个自包含交付包,三种安装形态。**

```
                    ┌────────────────────────────────────────┐
                    │  兼容性构建基线 (baseline/)              │
                    │  Ubuntu 24.04 arm64 · glibc 2.39 · GCC13 │
                    └───────────────┬────────────────────────┘
                                    │
                     ┌──────────────▼───────────────┐
                     │  自包含交付包 andcode-bundle   │
                     │  (§4.1: 同一份内容,三种宿主)  │
                     └──┬──────────────┬──────────┬─┘
                        ▼              ▼          ▼
          ┌──────────────────┐ ┌────────────────┐ ┌──────────────────┐
          │ Tier M (root)    │ │ Tier A (locked)│ │ Tier P (locked)  │
          │ Magisk 模块      │ │ adb 直推包      │ │ 自研最小 APK      │
          │ /data/adb/andcode│ │ /data/local/tmp│ │ 内嵌交付包+终端   │
          │ 真 chroot        │ │ loader 包装器   │ │ targetSdk 28     │
          │ 开机自启 sshd    │ │ sshd (dropbear)│ │ 侧载 GitHub/F-Droid│
          │ 零 App 依赖      │ │ 零 App 依赖     │ │ 唯一交付物=1 个 APK│
          └──────────────────┘ └────────────────┘ └──────────────────┘
```

- **交付包是同一个 tarball**:glibc sysroot 闭包 + opencode + git + busybox +
  dropbear + shim,由三种宿主(模块安装脚本 / adb 推送脚本 / APK 资产)释放。
- 交互统一走两条路:**本机终端**(仅 Tier P 自带)与 **SSH**(三种形态都内置
  dropbear,任何 SSH 客户端可连,ConnectBot 等为可选客户端而非依赖)。
- 对 rooted 设备,Tier M 是零依赖、零 App、开机即用的最优解。

---

## 3. 兼容性 Linux arm64 构建基线(核心交付物)

### 3.1 基线规格

| 项 | 取值 | 理由 |
|---|---|---|
| 基线发行版 | **Ubuntu 24.04 LTS (Noble) arm64** | LTS 支持到 2029;LLVM/GCC/Go/Bun 生态新;GitHub Actions 原生 `ubuntu-24.04-arm` runner 与基线同构,CI 产物与本地逐字节可比 |
| libc | glibc 2.39(符号版本审计强制) | Ubuntu 24.04 自带版本 |
| libstdc++ | GCC 13 随包,或随产物捆绑 | bun 等需要 |
| 三元组 | `aarch64-unknown-linux-gnu` | 标准gnu |
| 禁止项 | 不得链接 Android NDK/Bionic;不得引入 ≥ 2.40 的 glibc 符号 | 兼容性红线 |

> **兼容性下限提示(选 Ubuntu 24.04 的代价)**:产物要求目标机 glibc ≥ 2.39,
> 即标准 Linux arm64 设备需为 Ubuntu ≥ 24.04 / Debian ≥ 13 (trixie) / 同代发行版。
> 对 Android 侧**无影响**——三种交付形态都随包携带基线 glibc,自包含。
> 若日后需要支持更老的标准设备(如 glibc 2.36 的 Raspberry Pi OS Bookworm),
> 追加第二条基线分层发布,不在本期范围。

### 3.2 三个等价构建入口(同一 sysroot,产物一致)

1. **设备端原生构建**:真 chroot(Tier M)或 qemu 内 `apt install build-essential`
   后直接构建——这也是"在 Android 上为 Linux arm64 开发"能力本身的一部分。
2. **PC 端 QEMU 构建**:`debootstrap --arch=arm64 noble` + `qemu-user-static`
   (binfmt),在 x86 PC 上跑出与设备端逐字节可比的产物。
3. **CI 构建**:GitHub Actions 原生 `ubuntu-24.04-arm` runner(与基线发行版同构,
   无需 QEMU;本地/设备端构建走 QEMU 或真机回退),跑 `baseline/Dockerfile`。

### 3.3 兼容性审计(强制门禁)

`baseline/check-compat.sh` 对每个交付 ELF:
- `file` 确认 `aarch64`;
- `objdump -T <elf> | grep -oE 'GLIBC_[0-9.]+' | sort -uV | last ≤ 2.39`;
- `readelf -d` 列出 NEEDED,逐个确认"来自基线 rootfs 或已捆绑到 `lib/`";
- interpreter 校验:交付包内的 glibc 二进制一律以**相对 loader 包装脚本**启动
  (见 §4.1),不依赖 `/lib/ld-linux-aarch64.so.1`。

---

## 4. 自包含交付包与三种安装形态

### 4.1 共同底座:自包含交付包 `andcode-bundle-arm64.tar.zst`

```
andcode/
├── root/
│   ├── lib/                  # 基线 glibc 2.39 的 ld-linux-aarch64.so.1 + 全部 NEEDED 库
│   ├── bin/opencode.bin*     # opencode 主体(ELF)
│   ├── bin/opencode          # §4.1.2 的 loader 包装器
│   ├── bin/opencode-tui*     # TUI 二进制**预置**(见下方"运行期不落盘"约束)
│   └── usr/                  # git、rg、dropbear/dbclient、busybox 等配套(同样 glibc 版)
├── shim/libandcode-shim.so   # §4.5 LD_PRELOAD 重定向 shim
├── etc/                      # resolv.conf / passwd / group / nsswitch.conf
├── sbin/andcode-entry        # 统一入口(命名规范见 docs/NAMING.md §4.2)
└── manifest                  # 版本、校验和、组件来源(供 notices 生成)
```

> 命名(逻辑名/物理名/slug/环境变量)一律遵循 **docs/NAMING.md**;
> Tier P 的 jniLibs 物理名与链接农场由该规范定义。

**运行期不落盘(exec)约束**:targetSdk 37.2 下,任何**运行时才写出的 ELF 都
不可执行**(数据目录 exec 禁令,§1.2.3)。因此:
- opencode 如有运行期解包行为(如把 Go TUI 二进制释放到 `~/.opencode/bin`),
  必须绕开:预置全部子二进制到交付包,并通过其支持的路径/PATH 机制指向预置版
  (具体机制在 P0 核实,记入 §1.3 验证清单);
- `TMPDIR`、`HOME` 指向可写目录没有问题——只要不往那里写**会被 exec 的文件**。

#### 4.1.2 loader 包装器(无 proot、无 root 运行 glibc 二进制的核心)

```sh
#!/system/bin/sh
ROOT="$(dirname "$(readlink -f "$0")")/../.."
export LD_PRELOAD="$ROOT/shim/libandcode-shim.so"
export HOME="$HOME" TMPDIR="$HOME/tmp" PATH="$ROOT/usr/bin:$PATH"
exec "$ROOT/lib/ld-linux-aarch64.so.1" \
     --library-path "$ROOT/lib" \
     --inhibit-cache \
     "$ROOT/bin/opencode.bin" "$@"
```

- `--inhibit-cache` + `--library-path` 绕开 `/etc/ld.so.cache` 与绝对 interpreter;
- busybox(静态、GPL-2.0)承担无 glibc 环境下的脚本粘合(sh/readlink/tar 等),
  以**独立程序聚合**方式随包分发(附源码获取地址,见 REUSE.md §3.4)。

### 4.2 Tier M — Magisk 模块(rooted 设备首选,零 App 依赖)

```
magisk-module/
├── module.prop
├── customize.sh              # 释放 bundle 到 /data/adb/andcode,生成 chroot
├── service.sh                # 开机:组装 chroot 挂载 → 起 dropbear → 起 opencode serve(可选)
└── uninstall.sh
```

- 运行方式:**真 chroot**(性能最优,无 proot 翻译开销),bind-mount
  `/dev`、`/proc`、`/sys`,可选 bind `/sdcard/Download` 为工作区(只放源码不放 ELF)。
- 开机自启由 Magisk `service.d` 机制完成,**无需任何 App**。
- 管理入口:`su -c /data/adb/andcode/sbin/andcode-entry`,或 `ssh localhost`(dropbear)。

### 4.3 Tier A — adb 直推包(locked 设备,零 App 依赖)

```bash
# scripts/deploy-adb.sh
adb push andcode-bundle-arm64.tar.zst /data/local/tmp/
adb shell "cd /data/local/tmp && busybox-arm-static tar --zstd -xf ... && ./sbin/andcode-entry sshd"
```

- 目标目录 `/data/local/tmp`:shell uid 可写可执行,locked 设备即可用;
  Android 11+ 可用无线调试,免数据线。
- 交互:PC 端 `adb shell` 直连,或包内 dropbear 起本地 sshd 后用任意 SSH
  客户端连 `127.0.0.1:2222`(adb `tcp` 转发或局域网)。
- 局限:adbd 断开不影响已 nohup 的进程,但设备重启后需重推/重跑(可接受,
  Tier A 定位为"开发者的第二形态")。

### 4.4 Tier P — 自研最小 APK(locked 设备的面向用户形态)

平台参数:`minSdk 31 · targetSdk/compileSdk 37.2 · arm64-v8a`(见 §1.1)。

- **一个 APK 即全部,内嵌交付包**。因数据目录 exec 禁令(§1.2.3),交付包按
  可执行性一分为二:
  - **只读执行体 → `jniLibs/arm64-v8a/`,以 `lib*.so` 命名**(如
    `libopencode.so`、`libgit.so`、`libbusybox.so`、`libld-linux.so` 及 glibc 的
    `lib*.so` 依赖):安装时系统自动解压到 `nativeLibraryDir`(可 exec);
    首启动把包装脚本、`etc/`、shim 配置写入 `filesDir` 并回指
    `nativeLibraryDir` 内的执行体;
  - **可写数据**(`HOME`、`TMPDIR`、git 仓库、配置、生成的 `resolv.conf`)
    → `filesDir`,绝无 ELF 落盘后 exec。
- 终端 UI 复用 `jackpal/Android-Terminal-Emulator` 的 emulator/view 库
  (Apache-2.0,可并入 AGPL 项目,保留声明);jackpal 上游 2022 年后停更,
  以"最小 fork"方式维护,只保留 TUI 会话所需路径。
- **targetSdk 37.2 平台行为适配清单**:
  - 前台服务必须声明类型:用 `specialUse`(属性说明:承载开发工具长会话),
    并申请 `POST_NOTIFICATIONS` 运行时权限(通知才可见);
  - edge-to-edge 强制(targetSdk 35+):终端页按 WindowInsets 适配;
  - 预测性返回手势(Android 16+):终端页禁用 predictive back 以防误退;
  - scoped storage:工作区默认 `filesDir`,可选 SAF 授权 `/sdcard` 项目目录
    (noexec 限制只影响 ELF,不影响源码)。
- 常驻:前台服务(specialUse)+ wake-lock 承载 `opencode serve`/长会话(§4.6)。
- UI 极简:一个终端页 + 一个"状态/设置"页(启动 sshd、注入 API key、
  phantom-killer adb 引导、工作区选择),本质上是一个"自带 opencode 的终端"。

### 4.5 LD_PRELOAD 重定向 shim(替代 proot 的关键部件)

自研、本项目 AGPL、数页 C 代码。拦截 `open/openat/stat/access` 等少数调用,
把 glibc 的只读系统路径重定向进 `$ROOT/etc`:

| glibc 请求 | 重定向到 | 用途 |
|---|---|---|
| `/etc/resolv.conf` | `$ROOT/etc/resolv.conf`(由 `andcode-mkresolv` 从 Android `net.dns*` 生成) | DNS |
| `/etc/passwd`, `/etc/group` | `$ROOT/etc/…` | getpwuid(HOME/用户名解析) |
| `/etc/hosts`, `/etc/nsswitch.conf` | `$ROOT/etc/…` | 域名与 NSS 配置 |

- 兜底:若 shim 覆盖不全(P0 实测),退路是引入**单个静态 proot 二进制**
  仅做 bind(见 §7 R1);proot 为 GPL-2.0,独立程序聚合 + 提供源码获取方式,合规。
- Termux glibc 生态(`termux-pacman/glibc-packages`,MIT)作为该 shim 设计的
  参考实现与对照测试基线。

### 4.6 Android 12+ Phantom Process Killer 对策(三种形态共用)

```bash
adb shell "cmd device_config set_sync_disabled_for_tests persistent"
adb shell "device_config put activity_manager max_phantom_processes 2147483647"
```

- Tier M(root):安装时用 root 直接固化上述设置(并适配个别 ROM 的私有开关),
  重启后由 service.sh 复查——**唯一能自动持久化的形态**。
- Tier P(APK):设置页一键引导用户执行 adb 命令(展示可复制命令,含无线调试
  引导),叠加前台服务降低被杀概率;Android 12+ 为我们支持的最低版本,该对策
  对所有目标设备必然适用,不存在"老系统不需要"的分支。
- Tier A:部署脚本顺带执行;文档注明重启后需重跑。

### 4.7 认证与交互

1. **认证**:a) 从终端复制 OAuth URL 到任意浏览器,回贴回调;b) API key /
   环境变量注入(Tier P 设置页直接粘贴,完全无浏览器);c) Tier P 可用
   Intent 拉起默认浏览器完成回调。
2. **无头/远程**:`opencode serve` + 内置 dropbear → 任何 SSH 客户端或 PC
   浏览器(同 LAN)接入。这使"手机上的 opencode"也可以完全由 PC 驱动,
   触屏 TUI 只是其中一种入口而非必需。

---

## 5. 仓库结构(本仓库交付物)

```
andcode/
├── docs/                     # DESIGN.md · REUSE.md · NAMING.md
├── baseline/                 # 兼容性构建基线(§3)
│   ├── Dockerfile            # ubuntu:24.04 (arm64) + build-essential + git + bun
│   ├── make-rootfs.sh        # debootstrap arm64 rootfs(交付包 sysroot 来源)
│   └── check-compat.sh       # glibc/ELF 兼容性审计门禁
├── bundle/                   # 自包含交付包(§4.1)
│   ├── pack-bundle.sh        # 从基线 rootfs 抽取 glibc 闭包 + 组件 → tarball
│   ├── pack-apk-libs.sh      # 规范布局 → Tier P jniLibs 物理名重打包(NAMING §6.2)
│   ├── wrapper.sh.tpl        # loader 包装器模板
│   └── shim/                 # LD_PRELOAD 重定向 shim(C, AGPL)
├── magisk-module/            # Tier M(§4.2)
├── scripts/
│   ├── deploy-adb.sh         # Tier A(§4.3)
│   ├── naming-lint.sh        # 命名规范 CI 门禁(NAMING §8)
│   └── smoke-test.sh         # 三形态共用验收(§6)
├── app/                      # Tier P 自研 APK(§4.4, Kotlin + jackpal 终端库 fork)
├── third_party/              # 指南与补丁(不 vendoring 源码,只放构建配方)
└── .github/workflows/andcode-ci.yml  # 基线 → 交付包 → 审计 → 冒烟 → 发布
```

---

## 6. 阶段计划与验收标准

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| **P0 可行性(2–3 天)** | adb 包(Tier A)手工路径:静态 busybox + sysroot + loader 包装器跑官方 opencode;同时精读 `claude-code-termux` 验证无 proot 路线;**另测 jniLibs 提取 + W^X/JSC JIT + TUI 释放行为**(Tier P 三大前提) | 在真机(任一 locked 设备)上完成一次真实编码会话;§1.3 假设逐条 ✓/✗;shim 缺口与 JIT 定级结论成形 |
| **P1 基线与交付包(1 周)** | `baseline/` 三件套 + `bundle/pack-bundle.sh` + shim v1 + CI | 产物过 `check-compat.sh`;同一 tarball 在 Tier A、真 chroot、原生 Ubuntu 24.04 arm64 三处均可运行 |
| **P2 Tier M(1 周)** | Magisk 模块 + service.sh 开机自启 + phantom-killer 固化 | B 类设备刷入后:重启自动 sshd,`ssh` 进会话即用;全程零第三方 App |
| **P3 Tier P APK(2–3 周)** | APK(minSdk 31 / targetSdk 37.2)、jniLibs 打包、jackpal 终端库最小 fork、设置页、specialUse 前台服务 | A 类设备侧载一个 APK 即完成安装→认证→会话;被切后台 30 分钟进程存活;16K 页设备(或开发者选项模拟)可运行 |
| **P4 打磨** | DNS/断网重连、OAuth 回调、`serve`+SSH 保底、多会话、发布工程(notices、F-Droid 元数据) | 冒烟矩阵全绿(见 REUSE/CI) |

---

## 7. 风险与备选

| # | 风险 | 影响 | 备选方案 |
|---|---|---|---|
| R1 | Bun/opencode 在"无 proot 的裸 glibc sysroot"下依赖未覆盖的系统文件(shim 缺口),或 JSC 在 targetSdk 28 之外的 JIT 受限 | Tier A/P 主路径受阻 | ① P0 即实测并补全 shim;② 引入单个静态 proot 二进制做 bind(GPL-2.0 独立聚合 + 源码提供);③ Tier M 真 chroot 不受影响 |
| R2 | Ubuntu 24.04 基线把标准设备兼容下限抬到 glibc ≥ 2.39 | 标准 Linux 目标面收窄 | ① Android 侧不受影响(bundle 自带 glibc);② 追加 Debian 12 第二基线分层发布;③ 简单工具改静态 musl |
| R3 | targetSdk 37.2 的运行期限制:数据目录 exec 禁令、W^X/JIT、运行期释放 ELF | Tier P 主路径受阻 | ① jniLibs 提取(`lib*.so` → `nativeLibraryDir`),可执行体零落盘(§4.4);② JIT 被拒则 `BUN_JSC_useJIT=0`(性能损失,实测定级);③ opencode 若必须运行期释放 ELF 且无法指向预置副本,为其打补丁改走预置路径(补丁归 AGPL) |
| R4 | ROM 差异(厂商杀后台、device_config 被锁) | 进程存活率 | Tier M root 固化为主推荐;`serve`+SSH 保底;主流 ROM 适配命令文档化 |
| R5 | opencode 上游快速迭代,产物结构变化 | 维护成本 | CI 定期重跑 P0 冒烟;假设以 `scripts/smoke-test.sh` 代码化 |
| R6 | jackpal 终端库停更、新 Android(targetSdk 35+ 行为)兼容性回归 | Tier P 终端体验 | 最小 fork 维持并完成 edge-to-edge/predictive back 适配;终端仅是入口之一,SSH/serve 保底;必要时评估 Termux 终端库(GPLv3,需独立 fork 仓库) |
| R7 | locked 设备 adb 不可用(未开 USB 调试) | Tier A 不可用 | Tier P 不依赖 adb,作为 locked 设备默认形态 |
| R8 | 16K 页设备上个别组件(非基线工具链产物)4K 对齐不兼容 | 部分 Android 15+ 机型失败 | 基线 glibc/Ubuntu 工具链默认 64K 对齐,理论免疫(§1.2.8);CI 加 `readelf -l` 段对齐检查;自有 NDK 代码强制 16K 对齐编译 |
| R9 | Android 14+/15+ 对 `device_config` 写入收紧(部分 ROM 需 root) | Tier A/P 的 phantom-killer 对策退化 | 前台服务 + 会话内子进程数量控制;Tier M root 固化为主推荐形态;文档按 ROM 列差异 |

---

## 8. 明确不做的事(范围边界)

- **不依赖 Termux/proot-distro 等第三方宿主 App**:它们至多出现在附录文档作为
  可选替代;交付物全部自包含(静态 busybox + 自带 sysroot + dropbear + 自研 shim)。
- 不移植到 Android 原生 Bionic(把 opencode 重链到 bionic):成本极高且破坏
  "产物可在标准 Linux arm64 运行"的目标。
- 不做 x86/模拟器路径:目标设备全部是 arm64。
- 不修改 Android 系统分区:所有方案在 `/data` 与应用沙箱内完成。

---

## 附录:可选替代路径(非本设计主路径,仅记录)

- **Termux + proot-distro**:社区最成熟的宿主,适合不想侧载 APK、能装 F-Droid
  Termux 的用户;我们的交付包理论上可直接在 proot Debian/Ubuntu 内运行
  (`bundle/` 设计刻意不假设宿主)。详见 REUSE.md 对 Termux 系许可证义务的分析。
- **ConnectBot 等第三方 SSH 客户端**:Tier A/M 的推荐客户端,但属可选工具,
  不构成依赖。
