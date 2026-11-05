# andcode

将 [opencode](https://github.com/sst/opencode)(终端 AI 编码代理)移植到 Android arm64,
提供一套**兼容性 Linux arm64 构建环境**(基线:Ubuntu 24.04 arm64 / glibc 2.39;
该环境下构建的原生程序可在 glibc ≥ 2.39 的标准 Linux arm64 设备上直接运行)。

覆盖目标设备:

- Bootloader locked(无 root)→ Termux + proot-distro 或自带 loader 的 glibc sysroot
- Bootloader unlocked + root → 真 chroot / Magisk 模块

平台基线:**Android 12+ (minSdk 31)**,APK `compileSdk/targetSdk 37.2`。
设计文档见 **[docs/DESIGN.md](docs/DESIGN.md)**(含架构、构建基线规格、三种自包含
交付形态、阶段计划与风险表);可复用开源项目调研见 **[docs/REUSE.md](docs/REUSE.md)**;
可执行工具入口命名规范见 **[docs/NAMING.md](docs/NAMING.md)**。

**设计原则:自包含**——除 Android 系统外不依赖任何第三方宿主 App(不用 Termux),
交付形态为 Magisk 模块(root)/ adb 直推包(locked)/ 自研最小 APK(locked)。

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
