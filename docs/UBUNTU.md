# Ubuntu 开发环境：原型状态与验收

对应 [DESIGN §4.8](DESIGN.md#48-ubuntu-开发环境双后端实施中非已交付能力)。

## 当前状态

这是 **root chroot + PRoot 开发原型**，不是已完成自包含交付的 Ubuntu 功能。
轻量 Bash 与 Web 界面保持原样；PRoot 已通过旧设备真实应用域的代理模式开发准入。
不依赖 Termux App，不降低 targetSdk，不关闭 SELinux。

- 原生 arm64 CI 首跑 [42508958877](https://github.com/Arjata/andcode-android/actions/runs/42508958877)
  已通过镜像构建、私有 mount namespace 测试、glibc/16K 审计；尚未用该工件在设备安装。
- 本轮已通过：构建归档校验器 14 项合成测试；设备系统 sh 的入口语法、预置 Bash
  的构建脚本语法；Toybox 私有 mount namespace 递归 private 设置。空间不足门禁
  曾实测拒绝且未创建实例。清理空间后已建立设备开发实例（不是 CI 工件安装）。
- chroot root 维护入口已通过代理 HTTPS 证书校验、apt update/install hello 及
  glibc 2.39-0ubuntu8.7 → 8.9 更新；UID/GID 60000 已通过 gcc 编译运行、16K
  LOAD、capabilities 清零、prctl no-new-privs 查询、PTY/子进程及前台清理。
  **普通用户连接代理超时，默认 DNS 未通过，完整 smoke 脚本仍失败。**
  对照诊断在同样降权/清除 capabilities 条件下只更换 UID：60000 超时，实际 APK UID
   10348 可连接；未因此改变正式开发身份或设备防火墙。只读 BPF 诊断进一步确认
   设备受限网络模式开启，全局规则 `0x220` 包含 `RESTRICTED_MATCH`，APK UID 的
   `0xa5` 包含相应放行位而 UID 60000 无记录。认证服务需解决网络身份适配。
- PRoot 在真实 `untrusted_app`、Seccomp=2 下通过显式代理 apt update/install、
  HTTPS 证书校验、新装 hello、gcc 编译产物执行、PTY/子进程与 glibc 8.7 → 8.9
  更新后运行，输出 `ANDCODE_PROOT_DEVELOPMENT_OK`、`development-exit=0`。
  guest ELF 未修改，没有用 su/run-as 替代；后续 TCP DNS 的无显式代理 HTTPS、
  严格 apt update 与 Git HTTPS 已通过，其它设备及关闭 VPN 场景仍未验证。
- 用户清理后旧设备 `8c8da214` 可用约 54 GiB，空间阻塞已解除，SELinux 保持 Enforcing。
- 4 GiB 镜像需要先暂存压缩文件，再保留至少 **5 GiB** 可用空间。实际开发项目
  可能需要更大的镜像；当前原型不提供自动扩容或覆盖重装。
- chroot/PRoot 都不是安全沙箱；不要在原型内执行不可信项目或模型自动化操作。
- 正式分发前还需对应源码/许可履约审查，CI 工件不代表发布已获批准。

### 设备开发引导路径（不替代 CI）

本机无 Docker 且 CI 配方尚未发布时，可用 `scripts/bootstrap-ubuntu-device.sh`
对固定摘要的官方 Ubuntu Base 24.04.4 arm64 归档建立独立 4 GiB ext4 开发实例。
输入在 `/data/local/tmp/ubuntu-base-24.04.4-base-arm64.tar.gz`，必须 root:root 0600；
同时需要审查后的 `/data/local/tmp/andcode-ubuntu` 与现有 bundle 的独立 BusyBox。
配方只接受固定路径/摘要且拒绝覆盖实例，失败保留残留供检查。
这是原生设备开发验证，不得称为 CI 工件安装验证。rootfs 来源与包清单分别记录在
实例 `andcode-ubuntu-build.txt` 与 guest `/etc/andcode-ubuntu-packages.tsv`。

旧设备 mke2fs 不支持 `orphan_file` 特性名；Toybox tar 拒绝 Ubuntu 的绝对链接，
Toybox mount 对 `/dev/null` bind 错误执行 loop 逻辑。引导与会话复用现有 BusyBox
独立载荷，将 root 私有副本保存在实例内。没有复制 BusyBox 源码进仓库。
chroot 使用独立 devpts `newinstance,ptmxmode=0666,mode=0620,gid=60000`，不更改
宿主 `/dev/pts`；宿主 `ptmxmode=000` 会让普通用户无法创建 PTY。旧内核缺少
proc status 的 NoNewPrivs 字段，使用 `prctl(PR_GET_NO_NEW_PRIVS)` 验证，不能跳过检查。
`scripts/ubuntu-device-test.sh` 验证 HTTPS、apt 安装、新安装 ELF、普通用户 capability
清空、编译运行、宿主路径不可见与前台退出无挂载泄漏；它不测试 PRoot 应用域。

## 构建与安装（仅可信 CI 工件，root 人工操作）

1. 触发 `.github/workflows/ubuntu-development.yml`。它生成镜像、压缩文件摘要、
   包版本/源包清单与基础镜像 digest；使用另一份解压镜像做 apt/编译测试，
   不修改上传的原镜像。只有该 run 通过后才能称“Linux CI 验证通过”。
2. 将可信 run 的 `andcode-ubuntu-arm64.img.gz` 放至设备
   `/data/local/tmp/andcode-ubuntu-arm64.img.gz`。从可信 CI 输出带外确认 SHA-256，
   不把同目录任意文件给出的摘要当作真实性证明。
3. 将本仓库审查后的 `runtime/ubuntu/andcode-ubuntu` 与
   `runtime/ubuntu/andcode-ubuntu-install` 放至 `/data/local/tmp/` 同名路径。
4. root 执行（将占位符替换为真实的 64 位小写十六进制摘要）：

   ```sh
   su -c 'chown 0:0 /data/local/tmp/andcode-ubuntu-arm64.img.gz /data/local/tmp/andcode-ubuntu'
   su -c 'chmod 0600 /data/local/tmp/andcode-ubuntu-arm64.img.gz'
   su -c 'chmod 0700 /data/local/tmp/andcode-ubuntu'
   su -c 'sh /data/local/tmp/andcode-ubuntu-install <可信的SHA256>'
   su -c 'sh /data/adb/andcode-ubuntu/andcode-ubuntu status'
   su -c 'sh /data/adb/andcode-ubuntu/andcode-ubuntu shell'
   ```

   安装拒绝已有实例，目录 `root:root 0700`，镜像 `root:root 0600`。安装失败保留
   私有残留，不会自动删掉后重试。**不要直接使用项目 ZIP 导入功能安装 rootfs。**
   暂存文件要求 root 所有且不可被其他用户写入；本原型假设设备无恶意 root 进程。
   当前安装原型还需要 `/data/local/tmp/andcode/bin/busybox`，复制到 root 私有实例；
   这是开发 bundle 依赖，不应被误称为已完成的自包含 APK 安装。

5. `shell`/`exec` 为普通用户（60000），在 `/workspace` 起步；显式维护命令示例：

   ```sh
   su -c 'sh /data/adb/andcode-ubuntu/andcode-ubuntu admin apt-get update'
   su -c 'sh /data/adb/andcode-ubuntu/andcode-ubuntu admin apt-get install -y hello'
   su -c 'sh /data/adb/andcode-ubuntu/andcode-ubuntu exec hello'
   ```

   `admin` 有宿主 root 权限，不交给模型，不放入 APK 终端 PATH。镜像不含 sudo。
   不运行 systemd，不启动网络监听服务，不继承宿主代理或关闭 TLS 校验的环境。
   默认 DNS 为 TCP 的 1.1.1.1 / 8.8.8.8，受管网络可能需要人工更换；尚无 Android
   动态 DNS 同步。`_apt` 的主组设为 inet 3003（apt 沙箱会清除补充组），开发用户
   加入补充组 3003；旧 Android 的网络权限行为仍需实机确认。

设备开发引导/测试允许显式选择 `loopback-proxy` 模式，只在本次调用设置
`http_proxy`/`https_proxy=http://127.0.0.1:7890`。不自动继承宿主环境、不关闭 TLS。
代理由设备现有网络配置提供，**代理测试通过不等于默认直连 DNS 通过**，不作为
产品自包含能力的必需依赖。PRoot 默认模式已单独测试：UDP 公共 DNS 超时，
同一应用域 TCP 查询正常，使用 `options use-vc timeout:3 attempts:2` 后，
`getent`、证书校验 HTTPS、严格 apt update 与 Git HTTPS 成功。此处“无代理”只指
未设置 HTTP/HTTPS/ALL_PROXY，设备原有 FlClash VPN 保持运行，不代表无需设备网络。
chroot 普通用户的 UID 网络问题仍失败，不能与 PRoot 结果混为一谈。

人工 root 诊断可执行 `sh /data/local/tmp/andcode-ubuntu-network-diagnose.sh`
（从 `scripts/ubuntu-network-diagnose.sh` 部署）。它只读设备设置及三个 Android 13
BPF map，校验 map 布局；旧 4.9 内核不支持对象信息 syscall 时读取 fdinfo。
输出 `ANDROID13_RESTRICTED_RULE_BLOCKS_UID=60000` 表示该规则足以阻断此 UID，
不是已排除所有其它网络问题。INTERNET 权限 map 中缺条目本身不代表拒绝。
诊断不修改设置/BPF/防火墙，不借用 APK UID，不恢复 guest 权限；不要为了通过
测试而关闭受限网络模式。现有模式下 chroot 联网仍记为失败，PRoot 结果不受替代。

### PRoot 应用域开发准入

`scripts/prepare-proot-gate.py <官方Base归档> <新输出归档>` 先核对固定官方 SHA-256，
将绝对符号链接改为等价 guest 相对链接、硬链接展开等内容文件并移除特权位，
不修改任何 ELF。原因是旧设备应用域 BusyBox 提取触发 SIGSYS，Toybox 对部分
硬链接返回 Permission denied。输入仍是可信官方 Base，不是不可信归档安装器。
将输出放到 `/data/local/tmp/ubuntu-base-app-gate.tar.gz`（应用可读），然后**从
APK 终端**人工执行 `sh /data/local/tmp/proot-rootfs-gate.sh <生成输出的SHA256>`。
脚本拒绝覆盖 `files/proot-rootfs`，保留失败现场；开发副本不与 chroot 共享写层。

`scripts/proot-development-gate.sh [loopback-proxy]` 从该独立实例做 apt、hello、
编译和 PTY 验证；使用现有 PRoot `-l`（hardlink→symlink）与 `--kill-on-exit`。
日志在 APK `files/proot-development-gate.txt`。PRoot fake root 不是宿主 root，
也不是安全沙箱。当前仍依赖 `/data/local/tmp` 开发载荷，**不证明 locked 自包含交付**。
非交互 gate 从 `/dev/null` 读取 stdin，避免 timeout 新进程组触发终端 SIGTTIN。
最初在 libc 触发器后被 job-control 停住的尝试已终止；同实例重新执行
`dpkg --configure -a` 后完整 gate 成功，不把被中断的尝试算通过。

APK 独立终端可执行 `andcode-ubuntu-proot [loopback-proxy] [命令...]`；无命令进入
交互 Bash，`exit` 返回原轻量 Bash。缺少实例/载荷时明确报错，不自动安装/提权。
生成的 `files/term-ubuntu-proot` 由系统 sh 读取，不作为数据目录 ELF 执行。
开发入口已在真实应用域验证 hello、PTY、stdin 与退出码 42 传播；
不改变 OpenCode 工具或 Web PTY 后端。归档预处理另有 14 项合成测试接入 CI。
交互终端已实测 `stty size` 返回 44×54、Ctrl+C 中断前台 sleep 后返回 Ubuntu
提示符、`exit` 返回原项目轻量 Bash。真实应用域的 guest Python 前台信号测试已验证
软键盘隐藏/显示时两次 SIGWINCH，尺寸 28×54 → 47×54 → 28×54，输出
`ANDCODE_PROOT_RESIZE_OK`；仅代表旧设备本轮，更多设备仍待 P0/P3 实机验证。
设置页的“终端环境”仅影响新会话，默认轻量 Bash，可选已安装的 Ubuntu PRoot；
代理另有默认关闭的显式开关。旧设备已通过 UI 选择并持久化 Ubuntu 后端、退出旧
shell 后新终端直接显示 Ubuntu 提示符；已有会话不会切换。不提供 chroot 选择，
其认证 root 服务尚未完成。APK `assembleDebug`、`lintDebug` 均通过，Lint 警告未隐藏。
扩展 gate 也已在显式代理模式通过 C++ 编译、GNU Make 和 Git HTTPS `ls-remote`。
相同完整 gate 已使用 TCP DNS 无显式代理重跑，通过 apt、C/C++、Make、Git HTTPS、
PTY/子进程和现有 libc 执行，输出 `development-exit=0 network-mode=direct`。
本次 apt 安装包均为已装最新版，不将重跑描述成再次安装或再次升级 libc。
CI 增加 Android 专用 bundle 的 seccomp 七处校验、幂等摘要检查及后续 Tier P
物理化，标准 Linux bundle 不变；首跑已执行该链，后续 manifest 分类修复及
Tier P 原生中间工件仍需重跑，不代表 jniLibs 自包含已经完成。

新终端创建时快照选中的单个私有项目名；启动器只接受 `files/projects/<项目名>`，
绑定至 `/workspace/<项目名>` 并从该目录起步。无选中项目时从 `/root` 起步。
不绑定整个项目目录集合、`/data` 或任意调用者传入的宿主路径。拒绝链接父目录/
项目根、越界名、冒号分隔符和丢失项目；Android 数据目录的合法别名不会被误拒绝。
项目内部的链接不会被递归过滤，PRoot 不构成沙箱，也不能阻止同 UID 的宿主访问。
`scripts/proot-terminal-test.sh` 从轻量终端执行，已实测独立临时项目写回、参数保真、
stdin/退出码 42、空项目回 `/root`、错误路径/链接拒绝与自有夹具清理。
日志为 `files/proot-terminal-test.txt`；应用域无法读取 SELinux 全局状态时会明确提示，
须同时在 adb 侧核验 Enforcing，不把 Permission denied 当作状态通过。

## 会话与恢复限制

- 每次调用独立挂载命名空间，同一镜像仅允许一个会话。
- 前台退出会反向卸载；如果后台进程仍占用，退出码 75 且保留 `session-lock`。
- 外层接收 HUP/INT/TERM 或子命名空间被信号终止时保留锁，不假设命名空间已清理。
- 已做自有限时后台 `sleep` 实测：卸载报 busy、返回 75 且保锁；待该进程退出后，
  逐个检查进程 root/mountinfo 无引用，再释放确认属于本实例的 loop 并删空锁。
  不代表已实现自动异常恢复，也不授权释放其它实例的 loop。
- 不提供强制停止、懒卸载或自动杀未知进程。恢复前应人工检查进程与挂载；
  **不要只删锁后再次挂载**。进程死亡、设备重启等异常恢复仍待验证。
- chroot 暂不映射 APK 私有项目，也不接入 OpenCode。待认证 root 服务完成后，
  再将选择的项目映射至 `/workspace/<项目名>`，默认模型执行必须降权。
  PRoot 已提供单项目开发映射，但尚未接入 OpenCode/Web PTY。

## 必须通过的实机门禁

| 验证 | chroot | PRoot（真实应用域） |
|---|---|---|
| rootfs Bash、PTY 与终端尺寸/信号 | Bash/PTY 创建通过；交互尺寸/信号待 P0/P3 | Bash/PTY/子进程、stty 初始尺寸、Ctrl+C、exit 返回、IME 往返两次 SIGWINCH/尺寸同步通过；其它设备待 P0/P3 |
| DNS、HTTPS 证书校验、`apt update/install` | root 代理模式通过；UID 60000 网络超时、直连 DNS 未通过 | 显式代理完整通过；TCP DNS 无显式代理 HTTPS/apt update/Git 通过，VPN 未关闭 |
| 新安装 `hello` ELF 能运行 | root/普通用户均通过 | 应用域通过 |
| 普通用户 gcc 编译并运行，写 `/etc` 被拒 | UID 60000 通过，LOAD 0x4000 | 待 P0/P3 |
| libc 更新后继续运行（不可盲用旧偏移补丁） | 2.39-0ubuntu8.7 → 8.9 通过 | 同版本更新后执行通过,未修改 ELF |
| 项目访问范围、停止/异常退出无遗留挂载 | 待 P0/P3 | 单项目 bind/写回/错误路径拒绝通过；不是沙箱，异常停止待 P0/P3 |
| OpenCode 工具与 Web PTY 使用所选后端且非 root | 待集成 | 待集成 |

PRoot 失败时必须保留为“受限/不可用”，不能借助 root relabel 后声称 locked 支持。
