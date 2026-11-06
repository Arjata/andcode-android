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

**豁免**:Magisk 平台固定文件名(`customize.sh`、`service.sh`、`uninstall.sh`、
`module.prop`)遵循 Magisk 官方约定,不受第 2.1 条"无 .sh"约束。
**保留区**:APK 自有 NDK 库(jackpal fork 等)**禁止**使用 `libandcode-` 前缀,
避免与打包工具链混淆;其命名沿用原库名(`libterminal-jni.so` 等)。

## 4. 逻辑名规范(用户视角)

### 4.1 `bin/` — 交互命令(PATH 内)

| 逻辑名 | 类型 | 说明 |
|---|---|---|
| `opencode` | 包装器脚本 | 设 env → exec `opencode.bin`(规范布局)/ `libandcode-opencode.so`(Tier P) |
| `git`、`ssh` | 上游直通(经链接农场指向物理名) | 供 opencode 内部 spawn 与用户使用 |
| `andcode-doctor` | 自研 | 环境自检:loader、shim、DNS、JIT、phantom-killer 状态,输出诊断报告 |
| `andcode-sshd` | 自研 | 内置 dropbear 生命周期:`start|stop|status` 子命令式 |
| `opencode-tui` | 上游直通 | 若核实 opencode 需按名调用 TUI 二进制,预置为该逻辑名(DESIGN §4.1) |

### 4.2 `sbin/` — 服务与维护入口(不在默认 PATH)

| 逻辑名 | 说明 |
|---|---|
| `andcode-entry` | 统一入口(原 entry.sh 更名):初始化 env、生成 `etc/resolv.conf`、按参数派发 |
| `andcode-mkresolv` | 从 Android `net.dns*` 生成 resolv.conf(供 service.sh 单独复用) |

## 5. 环境变量规范

| 变量 | 含义 | 取值示例 |
|---|---|---|
| `ANDCODE_ROOT` | 逻辑根目录(包装器据此寻址) | `/data/adb/andcode`、`$HOME/andcode` |
| `ANDCODE_EXE_DIR` | 可执行物理目录 | Tier P = `nativeLibraryDir`;其余 = `$ANDCODE_ROOT` |
| `ANDCODE_LOADER` | glibc 动态链接器绝对路径(launcher 用) | `$ROOT/lib/ld-linux-aarch64.so.1` |
| `ANDCODE_LIBPATH` | `--library-path` 值(launcher 用) | `$ROOT/lib`(规范)/`$ANDCODE_EXE_DIR`(Tier P) |
| `ANDCODE_SHIM` | shim 绝对路径(launcher 用) | `$ROOT/shim/libandcode-shim.so` |
| `ANDCODE_TIER` | 形态标识,单字符小写,与 DESIGN 章节一致 | `m` / `a` / `p` |
| `ANDCODE_BUNDLE_VERSION` | bundle 语义化版本 | `1.2.0` |
| `ANDCODE_LOG` | 日志级别 | `debug\|info\|error` |

- 透传规则:`OPENCODE_*` 等上游变量允许用户透传,但包装器只设置自己登记的
  `ANDCODE_*` 与必需的运行时变量(`HOME`、`TMPDIR`、`PATH`、`LD_PRELOAD`、
  `LD_LIBRARY_PATH`、`GIT_EXEC_PATH`),**不覆盖**用户显式设置的 `OPENCODE_*`。
- 禁止使用未登记的环境变量名;新增变量须先进 §8 注册表。

## 6. 物理名规范

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
| `root/usr/libexec/git-core/git-remote-https`(git 助手包装器) | wrapper-sh | `libandcode-git-remote-https.so`(libexec 下**不加** `cmd-`) |
| `root/usr/libexec/git-core/git-remote-https`(同路径,**launcher 形态**:静态启动器 ELF 取代 shell 脚本,规避 git spawn 的 shell 链路;真机 P0 验证项) | launcher | `libandcode-git-remote-https.so`(同 wrapper 规则) |
| `root/usr/lib/proot/proot`(proot-me v5.5 不可用,x86-64;采用 **Termux proot 5.1.107 bionic 构建** + loader + libtalloc + libandroid-shmem,GPL-2.0 独立聚合) | elf-exec(bionic) | `libandcode-usr-lib-proot-proot.so`(全路径 slug;**bionic 二进制,不经 glibc loader,Tier P 需单列**) |
| `root/usr/libexec/git-core/git-remote-https.bin`(助手 ELF 本体) | elf-exec | `libandcode-usr-libexec-git-core-git-remote-https.so`(全路径 slug;与包装器不同名,无冲突) |
| `root/sbin/andcode-entry`(本项目自有脚本,无同名 `.bin`) | script | `libandcode-andcode-entry.so`(slug 含 `andcode-` 前缀,允许) |
| `root/lib/ld-linux-aarch64.so.1`(loader 特例:显式路径调用) | glibc-lib | `libandcode-ld-linux.so` |
| `root/lib/libc.so.6`(DT_NEEDED 依赖库) | glibc-lib | `libandcode-libc.so`(slug **剥掉 `.so.N` 版本尾**) |
| `root/lib/libstdc++.so.6` | glibc-lib | `libandcode-libstdc---.so`(slug 字符净化见下) |
| `shim/libandcode-shim.so`(本项目 LD_PRELOAD 库) | preload-lib | `libandcode-shim.so`(原名即合规) |
| `root/etc/ssl/certs/ca-certificates.crt` 等数据文件 | data | **`-`**(data 不进 jniLibs:只读数据经 APK assets → filesDir 原样落位;亦避免长路径超 64 字符) |

**slug 字符净化**(在 `/`→`-` 之后):仅保留 `[a-z0-9-]`,其余逐字符替换为 `-`
(`+`、`_`、`.` 等均逐字符替换,连续结果不合并)。物理名全长(含 `libandcode-`/`.so`)≤ 64。

### 6.3 两个关键裁定

1. **DT_NEEDED 依赖库(glibc/libstdc++ 等)**:soname 必须与 `NEEDED` 逐字一致,
   无法简单改名。两条路线,P0 定夺:
   - **路线甲(默认)**:打包时用 `patchelf` 对 sysroot 闭包做全量重写
     (`libc.so.6 → libandcode-libc.so`,同步改 SONAME 与全部 NEEDED),
     连同可执行体一起放入 `nativeLibraryDir`——单一可执行目录,最简;
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
                             -> $ANDCODE_EXE_DIR/libandcode-git-remote-https.so
```

- PATH 只含 `$ANDCODE_ROOT/bin` 与 `$ANDCODE_ROOT/usr/bin`;
- git 的 `GIT_EXEC_PATH` 指向农场内 `usr/libexec/git-core`;
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
