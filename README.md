[![CI](https://github.com/Arjata/andcode-android/actions/workflows/andcode-ci.yml/badge.svg)](https://github.com/Arjata/andcode-android/actions/workflows/andcode-ci.yml)

# andcode

将 [opencode](https://github.com/sst/opencode)(终端 AI 编码代理)移植到 Android arm64,
提供一套**兼容性 Linux arm64 构建环境**(基线:Ubuntu 24.04 arm64 / glibc 2.39;
该环境下构建的原生程序可在 glibc ≥ 2.39 的标准 Linux arm64 设备上直接运行)。

覆盖目标设备:

- Bootloader locked(无 root)→ adb 直推包(Tier A)或自研 APK(Tier P),内含 loader/glibc sysroot
- Bootloader unlocked + root → 真 chroot / Magisk 模块

平台基线:**Android 12+ (minSdk 31)**,APK `compileSdk/targetSdk 37.2`。
设计文档见 **[docs/DESIGN.md](docs/DESIGN.md)**(含架构、构建基线规格、三种自包含
交付形态、阶段计划与风险表);可复用开源项目调研见 **[docs/REUSE.md](docs/REUSE.md)**;
可执行工具入口命名规范见 **[docs/NAMING.md](docs/NAMING.md)**。

**设计原则:自包含**——除 Android 系统外不依赖任何第三方宿主 App(不用 Termux),
交付形态为 Magisk 模块(root)/ adb 直推包(locked)/ 自研最小 APK(locked)。

Tier P 当前提供交互 Bash 终端(手动输入 `opencode`,同进程内保留会话)与 Web 图形界面。
终端首次进入即显示提示符,下方提供两行附加键(ESC/TAB/CTRL/ALT/方向与翻页等);
CTRL/ALT 点击锁定、再次点击解除,IME 键切换软键盘。未部署 Bash 时明确提示回退系统 sh。
Web PTY 创建及命令回显已在旧设备应用域验证;预置可执行副本和 socket 指路见
[DESIGN v0.4.25 §4.4](docs/DESIGN.md#44-tier-p--自研最小-apklocked-设备的面向用户形态)。
Web 终端已适配 Android LatinIME 的逐字输入、退格与回车;其它输入法仍待验证。
Web/终端抽屉“主页”显式返回应用仪表盘;Web 退出时取消页面延迟任务并释放视图。
抽屉新增 **项目 · 导入 / 导出** 与 **设置**:
- Material 3 分组卡片布局;项目卡更多菜单提供复制/导出,设置支持字号即时预览。
- 项目/设置导航配齐图标;独立终端支持双指展开/捏合调整字号(10–28 sp),
  自动保存并同步设置页,不会重建终端会话。
- 使用系统文件选择器导入 ZIP/文件夹副本到应用私有工作区,或导出项目 ZIP;
  单次限 512 MiB、20000 项、64 层,不覆盖同名项目、不跟随导出符号链接。
- 复制项目路径可在 Web 中打开;选中项目作为新终端起始目录,已有会话不自动 cd。
- 设置终端字号、终端/Web 亮屏和导出 .git(默认关闭)。其它隐藏文件仍会导出,
  请检查 .env 等敏感信息;导入不会与源文件夹自动同步,卸载应用会删除私有项目。
旧设备已验证 ZIP 导入/导出内容往返、文件夹导入和项目终端目录;其它提供器及大项目
仍待 P3 实机验证。ZIP 数据组件测试由 CI 的 `app-data-tests` 独立运行。
当前仍是开发部署,完整自包含 jniLibs/CI 集成和 locked 设备验证尚未完成。

Ubuntu 开发环境正在实施双后端：新增 Ubuntu 24.04 arm64 开发镜像配方、
root chroot 普通用户会话原型与独立 CI。旧设备真实应用域的 PRoot 已通过显式代理
HTTPS/apt、新安装/编译 ELF、PTY/子进程及 glibc 更新；终端提供
`andcode-ubuntu-proot [loopback-proxy]` 开发入口，退出返回轻量 Bash。
设置页可为新会话选择 Ubuntu 开发终端，默认仍是轻量 Bash，代理开关默认关闭。
选中私有项目可映射至 `/workspace/<项目名>`；旧设备 TCP DNS 下不使用显式代理的
HTTPS/apt/Git 已通过（仍保留设备现有 VPN）。
**尚未接入 OpenCode/Web PTY，仍非 locked 自包含交付**；chroot 网络身份、
认证 root 服务和 chroot 项目映射仍待 P0/P3 实机验证。只读诊断已确认设备受限
网络规则阻断 UID 60000；未修改设备策略或借用 APK UID 绕过。
状态、可信镜像安装和验收清单见 [docs/UBUNTU.md](docs/UBUNTU.md)。

许可证:**AGPL-3.0-only**(见 `LICENSE`)。

目录(随阶段填充,见设计文档 §5/§6):

```
baseline/       兼容性 arm64 构建基线(Dockerfile / rootfs / 兼容性审计)
bundle/         自包含交付包(glibc 闭包 + loader 包装器 + LD_PRELOAD shim)
magisk-module/  Tier M:root 设备的 Magisk 模块(开机自启,零 App)
scripts/        adb 直推(Tier A)与冒烟测试
app/            Tier P:自研最小 APK(minSdk 31 / targetSdk 37.2,内嵌终端与交付包)
.github/workflows/ CI(andcode-ci.yml)
```
