# Ubuntu 开发环境：原型状态与验收

对应 [DESIGN §4.8](DESIGN.md#48-ubuntu-开发环境双后端实施中非已交付能力)。

## 当前状态

### Rootfs tool experiment

The optional `mmdebstrap` job in `ubuntu-development.yml` evaluates a mature
bootstrap tool rather than reimplementing distribution package installation.
Select `evaluate_mmdebstrap` when manually dispatching the workflow. The normal
Docker image job is unchanged. The experiment installs the tool only on CI,
uses the Ubuntu archive keyring and signed noble/updates/security indexes, and
retains tool/package/source versions, index bytes, configuration and logs.

`andcode-ubuntu-rootfs.tar.gz` and `andcode-ubuntu-arm64.img.gz` derive from the
same configured tree. The former is a future PRoot packaging input, **not** an
APK installer payload: Android link/metadata adaptation, trusted installation
and application-domain acceptance remain pending. The image must pass the
existing private-mount-namespace apt/non-root smoke and glibc/16K audit before
upload. Failures retain diagnostics, not installable release output. No device
instance is touched. Earlier signed live repository runs did not pin package
versions. The next candidate uses official HTTPS snapshot `20261110T000000Z`
for all guest suites via explicit signed-by sources, records snapshot/mirror
identity and retains apt authentication/expiry checks. It never falls back to
live repositories when the snapshot is unavailable. Build-host tool versions
remain recorded, not snapshot-pinned; byte reproducibility and corresponding-
source delivery are not established. Source-index availability and complete
source-package collection are separate from freezing binary package selection.

CI `42674527942` (commit `5017bbe`, mmdebstrap job `129352236231`) passed the
native arm64 bootstrap, archive validation, apt/non-root/PTY namespace smoke and
glibc/16K audit. Artifact `13699288258`: 373386339-byte ZIP, SHA-256
`552cb2eef2d8baf76df88199f7ac566e27aae06f2d04ad3513807706b1709634`.
Independent host review matched API and payload digests, all nine retained
index files (three InRelease suites), 180 package records, 15165 tar entries
(465454141 expanded file bytes), guest identity/source configuration, and ext4
header/label/4294967296-byte size. The host checked PGP framing, **not** signatures;
signature/expiry enforcement belongs to CI apt. Host review does not establish
image-tree equivalence or execute the image. Docker remains the default; no
device instance changed and no Android or distribution approval is granted.

Further host review matched the SHA-256/size of all six retained `Packages`
indexes against their InRelease records, then matched all 180 installed binary
versions and source-package/version pairs to index stanzas. Review JSON SHA-256:
`69465f98c3abe862c662e4aa8b0c4b0d466dc241f8335dc9b0dad99cec9a3f10`.
This does not independently verify PGP signatures, download the referenced
binary/source packages or establish corresponding-source closure.

The isolated candidate additionally emits `andcode-ubuntu-proot.tar.gz` through the
existing `prepare-proot-gate.py` transformer. Only the trusted CI build passes
the canonical archive's computed digest explicitly; the legacy two-argument
invocation still requires the fixed official Ubuntu Base digest. Conversion
normalizes root-relative symlinks, materializes regular hardlinks, strips
setuid/setgid and validates bounded output without changing file contents or
ELF bytes. This is build-time packaging, not a user-supplied archive installer.
Application-domain extraction, execution, update/recovery and device acceptance
remain pending; no current instance is replaced.

Host conversion of the independently verified `42674527942` canonical archive
passed the archive validator (15165 entries, 469579808 materialized file bytes).
A separate read-only archive comparison verified every regular file digest,
all five materialized hardlinks and each rewritten/unchanged symlink. Converted
archive SHA-256: `1c98cd485db4ea94a5959fbc0925cbf05973309664de07128e757bf4bc5478cd`.
This is host transformation evidence only; gzip metadata is not reproducibly
fixed, and the converted archive has not been executed on Android.

CI `42680411398` (commit `e197165`, mmdebstrap job `129373108570`) passed the
canonical-to-PRoot conversion and the existing Linux gates. Artifact `13703550062`
is a 532612659-byte ZIP, SHA-256
`b601712c3c48e63a8fd52110dd0346feb47d9ec762b3ae13de828333c9f04107`.
Independent review checked payload/API digests, all 15165 canonical/converted
paths, unchanged regular-file bytes, all five materialized hardlinks, symlink
rewrites and retained mode/ownership metadata (469579808 materialized bytes).
It also repeated the six-index / 180 binary-source-version review; its JSON
SHA-256 is `dbaa16b5716462328e3bc4cf281daaa384507c87bf613900b7e2be18a0ba5f52`.
The ext4 header/size check remains distinct from tree equivalence or execution.
No device installation or Android approval follows from these checks.

The next gate uses `compare-ubuntu-rootfs.py` to compare the original ext4
image (read-only mount) with the canonical archive. The smoke-test copy modified
by apt/compilers is never used for this comparison. All paths, types, modes,
UID/GID, regular-file digests and symbolic/hard links must match; only an empty
root-owned mode-0700 ext4 `lost+found` may be omitted from the archive. Results
are retained as `andcode-ubuntu-tree-review.json`. Timestamps, ACLs, xattrs and
sparse allocation are outside this gate. Synthetic POSIX tests and actual
image-tree acceptance must run in Linux CI; Windows does not validate them.

The tree gate passed native arm64 CI `42684788108` (commit `db1c693`, job
`129388559581`): 15166 entries including the root, 12456 regular-file/hardlink
entries, 1266 symlinks, five hardlinks and 469579808 materialized bytes. The job
log SHA-256 is `6f8cde3313c9d9344267e008a5002de0952e3bbd2fd5b2728f13f6aeab6ad91e`.
Thirteen non-root synthetic cases passed; the root-only nonempty recovery-
directory case was skipped. The next optional job runs these tests as root to
exercise that case too. Artifact bytes still require independent review.

Independent HTTPS source-index review of snapshot `20261110T000000Z` verified
all six main/universe source indexes against InRelease SHA-256/size records.
All 100 unique source-package/version pairs from the earlier 180-package live
run were present (this is not proof of a new snapshot bootstrap's selections).
Review JSON SHA-256:
`5d7a019b2b0dfdc14c024b56af9af60caf2e63bf665e64e31d23bf7bd736034a`.
Some identical source versions occur in different pool component directories;
the review retains each location and requires identical file hashes. Source
archives were not downloaded, PGP signatures were not independently verified,
and complete corresponding-source delivery remains unproven.

The next isolated recipe adds authenticated `deb-src` entries for the same three
snapshot suites and downloads each exact installed source-package/version using
guest apt (`--download-only --only-source`). It neither extracts source archives
nor executes source build rules. `andcode-ubuntu-source-inputs/` retains per-
source `.dsc`/archive files, actual apt commands/logs and a SHA-256 inventory
(`andcode-ubuntu-source-inputs.json`); these are copied out of a new temporary
guest directory before the immutable rootfs is exported. The collector rejects
malformed cleartext-signature framing rather than silently stripping it; this
is not an independent PGP signature verifier. A timed-out apt download retains
and reports its partial output, without emitting a successful source inventory.
The build recipe copies partial source evidence outside the disposable guest
before failing; the failure-only diagnostic artifact includes per-package apt
logs, not an approved source payload or rootfs. A failed source pipeline cannot
continue to image construction or successful candidate upload.
These additional guards passed 12 synthetic Python tests on Windows; Linux
recipe execution and real source downloads remain separate CI requirements.
The first source-acquisition experiment, CI `42688539116` (`ec0cd45`, job
`129401821961`), was cancelled at the former 45-minute job limit after logging
75/100 verified source downloads. It produced no successful source/rootfs
candidate. Its 14 root tree-comparison regression tests passed without skips.
Retained job log SHA-256:
`c69ad68aabf654b52ad79c02bc65fa92dd91f2fb530693e92f355b1f001aaab8`.
The optional job now has a bounded 80-minute build step within a 100-minute job,
leaving time for failure diagnostics; the snapshot, authentication and required
complete installed source-version set are unchanged. A successful rerun and
independent source-archive review are still required.
The subsequent optional run `42750180844` (`e82060a`, job `129611694402`)
succeeded, including all 100 exact source-version downloads, canonical-to-PRoot
conversion, original ext4 tree comparison and compatibility checks. Its Linux
regressions passed without skips: 14 archive-validator, 14 tree-comparison,
7 fail-closed recipe, 12 source-collector and 20 PRoot-converter tests.
Job log SHA-256:
`1897505b225face38bbb8cd735c72dfefc159fc14b11fdde241e13f0ccd1954b`.
Regular CI `42750151736` and Docker Ubuntu push CI `42750151274` also succeeded.
Artifact `13733088271` contains 1409398539 bytes; its API ZIP SHA-256 is
`f0d42ad0e7ed199d92f663c86429535e34dda71917142b45078557a14487659d`.
The complete download matches that API digest. Independent review matched all
180 installed binary/source-version tuples against six binary Packages indexes
and their InRelease hash records; review JSON SHA-256:
`197e6ae1ca87ba48981fbc74a8845be5a7d422bc67abcf7cad6036e90bca92a2`.
Separate source-input review bound all 100 exact source versions, 310 `.dsc` and
archive files (740746325 bytes), complete archive sets and retained per-package
commands/logs to six Sources indexes and their InRelease hash records. Source
review JSON SHA-256:
`03bdf935852a956e41f38f583a4e1de95ebc6cfcf54ddb5151842e32b158d6bf`.
The host review did not independently verify PGP signatures or execute source
build rules. Independent canonical/PRoot review also passed: 15167 entries,
5 materialized hardlinks and 567215830 materialized file bytes, with all payload
and 15 retained index-file hashes checked. The 4 GiB original ext4 header/size
and the CI tree report agree with these counts; the host did not independently
walk ext4. The CI tree has one additional allowed empty `lost+found` directory.
Canonical/PRoot review JSON SHA-256:
`fc552d5a19f4814dd9b3d812498572344d6a307d9615571b778bc45b08fb5613`.
An additional, separate host review subsequently verified all three retained
InRelease signatures using Git for Windows `gpgv` 2.4.9, an explicit isolated
home and the keyring downloaded with default TLS verification from
`https://archive.ubuntu.com/ubuntu/project/ubuntu-archive-keyring.gpg`.
Keyring SHA-256:
`80a36b0a6de2f69f49d2df75ef473ccde121e9e190b9ea01d20a4f63778d5c31`.
All three signatures returned `VALIDSIG` for the pinned Ubuntu Archive 2018
fingerprint `F6ECB3762474EDA9D21B7022871920D1991BC93C`, without a bad, revoked or
expired-signature status. Altering the signed `Suite` field was rejected with
`BADSIG`. Separate signature review JSON SHA-256:
`781c6e28d25470c9ffb43607a29e6c75994f141be5bc420432e48e51e97be608`.
These InRelease files do not declare `Valid-Until`; this review does not claim
validation of that absent field, `.dsc` developer signatures or complete source
licensing. Earlier digest-only reports retain their original limited scope.
These results are
not complete corresponding-source, redistribution approval or device installation
acceptance. Existing device instances are unchanged.
Missing exact versions,
apt failures, existing output or unexpected download paths fail the candidate.
This new acquisition path awaits Linux CI and independent archive verification.
It does not automatically close source completeness, patches/build-inputs,
notices or redistribution obligations. Docker and all device instances remain
unchanged. Larger source artifacts are evidence, not APK contents.

The first fixed-snapshot run `42685341275` (commit `dc87389`, job `129390525686`)
passed Linux smoke, conversion and original-image tree gates. Artifact
`13704952467` is 532612248 bytes, ZIP SHA-256
`e66ff0c7aaa92ce41e4096a611cd0d96e62f556d9a99184e93da8a2e57273759`.
Independent ZIP/rootfs/PRoot review passed; it confirmed the recorded snapshot
configuration and tree report, not an independent execution of ext4. All six
retained binary indexes matched InRelease hash records and all 180 installed
binary/source-version tuples matched those indexes (review JSON SHA-256
`415ba7654ce2a23e03d001091fea205ff3578181ae100fc0828118f7fd8b5e49`).
Materialized PRoot bytes are 469579853; path/link counts are unchanged. This
artifact predates source acquisition and cannot be credited with that new gate.

这是 **root chroot + PRoot 开发原型**，不是已完成自包含交付的 Ubuntu 功能。
轻量 Bash 与 Web 界面保持原样；PRoot 已通过旧设备真实应用域的代理模式开发准入。
不依赖 Termux App，不降低 targetSdk，不关闭 SELinux。

- 原生 arm64 CI 首跑 [42508958877](https://github.com/Arjata/andcode-android/actions/runs/42508958877)
  已通过镜像构建、私有 mount namespace 测试、glibc/16K 审计；该工件已按摘要
  安装到独立 `/data/adb/andcode-ubuntu-ci`，拒绝重复安装已实测。可信镜像已通过
  root 代理 HTTPS/严格 apt/hello，以及普通用户编译、权限清空、PTY 与生命周期；
  最后普通用户连接回环代理超时，完整 smoke 退出 1，网络阻塞未解决。
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

   设备已有开发实例时，可以显式选择**固定独立验收实例**，不要移动或覆盖旧实例：

   ```sh
   su -c 'sh /data/local/tmp/andcode-ubuntu-install ci-validation <可信的SHA256>'
   su -c 'sh /data/adb/andcode-ubuntu-ci/andcode-ubuntu ci-validation status'
   su -c 'sh /data/local/tmp/andcode-ubuntu-device-test.sh ci-validation loopback-proxy'
   ```

   `ci-validation` 必须同时传给安装器与该实例的 manager；它只选择
   `/data/adb/andcode-ubuntu-ci`，不是任意路径参数。测试脚本来自
   `scripts/ubuntu-device-test.sh`。两实例使用独立镜像/锁/命名空间，不共享可写系统。

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

2026-11-09 原生 arm64 run `42511151241` 的 build-bundle 已通过物理化、349 ELF
兼容审计及改名 Bash 执行（保留 libc.so.6 SONAME 后）。APK job 当时因 Action
请求已移除的 Android SDK `tools` 包失败，已改显式安装 platform-tools，待重跑。
真实原生工件本机 assembleDebug/lintDebug 与 APK 逐字节核验通过；首启动只写
data 并创建 nativeLibraryDir 链接，21 项回归及真实 manifest 往返通过。
旧设备真实应用域已运行 APK 内 Bash，无 root relabel；git 首测因 launcher
仍搜索旧 PRoot 库目录失败，修正待验证。不代表 V2/Web PTY 或 locked 整包通过。

原生 arm64 run `42515404336` 已全部成功：修复 Bun ET_EXEC 的 DT_VERDEF
遗留地址及 clone3 补丁的新内核回退后，Bash/V2.2.6/PTY 0.4.0 实际执行通过，
下游 SDK、APK 编译/Lint、真实 manifest 初始化与 APK 载荷逐字节核验通过。
`scripts/native-payload-device-test.sh` 只从 APK 轻量终端执行；原生目录路径、
真实应用域/seccomp、Bash/V2/PTY/Git/PRoot 子进程均为独立实机门禁，尚待新版安装。
PRoot 开发完整 gate 也可显式使用当前 APK 的 farm/native 库，不再混用旧开发库。
以上仍不是正式签名、Bun 原生扩展预置闭包或 locked 整包交付结论。

后续原生 run `42516603502`（`4869307`）全成功；成功工件 ZIP 已核对 API
SHA-256 `84287a218c6c885b1e4696bb6976a4db575ee1276bb5811d7b27252aafbe5e2e`，
本机 APK 再次编译/Lint 与原生/assets 逐字节核验通过并保留原签名覆盖安装。
旧设备真实 `untrusted_app`/UID10348/Seccomp=2 下 Bash 5.2.21、V2.2.6、
PTY 0.4.0/protocol7、Git 2.43.0、原生 PRoot 子进程全部通过，
`ANDCODE_NATIVE_PAYLOAD_OK`；adb 单独确认 SELinux Enforcing（应用域无法读状态）。
APK 原生 PRoot 的完整开发 gate 同样在真实应用域输出
`ANDCODE_PROOT_DEVELOPMENT_OK`、`development-exit=0 network-mode=direct`：
apt、C/C++、Make、Git HTTPS、PTY 均成功；仅未设置显式代理，设备 VPN 保留。

`opencode-native-prototype.yml` 是手动固定源码构建实验：在 Bun 编译期将
原生 .so 文件导入改为 `ANDCODE_EXE_DIR` 绝对目录下的内容寻址预置路径，
.node 改为向同目录显式 `process.dlopen`，保留 CommonJS addon 导出语义。
当前插件合成测试只证明改写/导出/字节保真与错误架构拒绝；CI serve 临时目录
扫描仅覆盖启动路径，不替代工具、Web PTY、TUI 或全部传递原生库审计。
实验不接 APK，不修改已验证官方载荷；许可证 notices/源码义务和兼容性待审查。

首个源码实验 run `42518155724` 成功且工件 API 摘要核对通过，但后续更严格静态
审计发现 Bun graph 仍嵌入 extensionless PTY ELF，且导入表包含不会选用的 musl
PTY 库，因此不能集成。新版实验插件显式要求 `OPENCODE_PTY_BIN`、不嵌入 daemon，
排除固定摘要的 musl 输入并在误选时失败；`.so` 的 require 返回路径字符串而不是
ESM namespace。新增门禁待新 CI 通过，许可证/Android 闭包仍待验证。

当前正式原生载荷 Web 首页能在 APK WebView 渲染，默认模型查询为
`arjata/gpt-oss-120b`；shell API 的 Bash/printf/Git 实际执行可达，但 Android
系统 `id` 受到 glibc shim preload 泄漏而失败，普通 Web PTY 创建返回 500
（bun-pty library 未加载，后续访问 symbols 失败）。这是待修边界，不是完整 Web
或工具闭包验收成功；没有降低 targetSdk/SELinux 或引入 TLS bypass。

源码实验 run `42519500865`（`c2277e8`）全部成功：Bun graph 无内嵌 ELF、
四个 glibc 扩展的摘要/依赖/16K/版本审计、shell、普通 PTY 的 tty/resize/子进程、
持久 PTY 快照回显及独立 BUN_TMPDIR 无 ELF 通过。仅为 Linux CI 证据，
不是 Android 原生扩展加载/传递依赖许可证/正式交付批准。

应用域诊断确认 Bash wrapper 的子环境中仍存在 LD_PRELOAD，临时仅对
`/system/bin/id` 清空该变量后即成功（同 UID/domain，未修改网络策略）。
wrapper 已改 direct loader `--preload` 单进程注入而不导出 LD_PRELOAD；
新增真实 glibc Bash/子 sh 的 Linux 门禁和 native device gate 中 Bionic id 断言，
修复待新 CI/APK 实测。模型默认配置正确，但本次实际请求因 EAI_AGAIN
无法解析 provider 域名而重试，已中止；不能算模型端到端成功。

新版官方载荷 run `42519762828`（`2716a49`）全部 CI 成功；native 工件 ZIP/API
SHA-256 `60dbbaed741181f37c1c8194643fc79bcaf7227709689504de7899862a32ecaf`。
本机 assembleDebug/lintDebug、APK 403 个 native 与 253 个 data 逐字节核对及
原签名覆盖安装通过；ZIP 文件名按原 UTF-8 字节解释（Android 构建工具未置 UTF-8
flag，Python 默认 CP437 显示并非真实文件名）。真实应用域新增
`ANDCODE_NATIVE_BIONIC_CHILD_OK` 和原有 native/PRoot 子进程门禁全部通过，
SELinux 由 adb 独立确认为 Enforcing。

官方 V2 的持久 PTY 使用预置 daemon 已通过系统 sh 的 tty、WebSocket 输入、
91×31 resize、重连重放和快照 `ANDCODE_NATIVE_PERSISTENT_WS_OK`。默认 Bash
wrapper 直接由 daemon exec 时立即退出，无输出；通过系统 sh 显式执行 wrapper
可成功。为修正该边界，Tier P 的 `bin/bash` 保留原物理名，改为静态 ELF 入口
直接调用同 nativeLibraryDir 的 loader/Bash/shim，CI/新版 APK 尚待验收。
这不代表 Web UI 操作/默认 Bash 或 Ubuntu Web 后端已经通过。

固定 npm tarball 完整性核查纠正 OpenTUI 原生包许可为 MIT AND LGPL-2.1-or-later，
附 FFmpeg/Ghostty/LCMS2/WebP/STB/Wuffs/Zlib 声明；fff 平台包未附 LICENSE。
详见 REUSE §2.1，仍不得把源码实验直接接入正式 APK。隔离设备 root 诊断可运行
源码版 serve/普通 PTY，但不是应用域或自包含证据；测试进程已停止。
默认 provider 域名在设备系统 ping 与宿主 DNS 均解析失败；PRoot 映射与 TCP DNS
对照也未恢复模型请求，已中断自有重试并清理自有诊断进程，未改网络策略或凭据。

实验 CI 继续增加真实 TUI 准入：独立 controlling PTY 内启动 `--standalone`，
同时要求 `/proc/<pid>/maps` 实际映射预置 OpenTUI 与终端渲染，结束仅终止该
测试进程组；运行期 ELF 扫描扩大到隔离 HOME 与 BUN_TMPDIR。该新门禁尚待 CI，
不提前声称 TUI 或完整运行期加载闭包通过。

源码实验 run `42522076401`（`c24813c`）现已通过上述 TUI 门禁，日志包含
`ANDCODE_SOURCE_TUI_NATIVE_OK`，shell/普通和持久 PTY、隔离 HOME/BUN_TMPDIR
无 ELF 扫描亦通过。前一轮 `42521939719` 的许可证据工件已核对 API SHA-256
`60a9b72e71e2ebcc6dd66dce280fc698532e545b007d2d80502ca7831444c7c8`；
四个固定包的 review 全部 blocked，与预期一致，不能作为发布合规通过证据。

显式 `loopback-proxy` 的应用域独立 serve 诊断可越过 provider DNS 阻塞，但
请求在 TLS 阶段因 `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` 失败。未设置
NODE_TLS_REJECT_UNAUTHORIZED=0、未添加未知 CA、未修改用户配置或默认代理；
已中断自有重试并停止隔离服务。恢复端到端验收需要可验证的 provider 证书链或
正常可解析的直连网络，不把代理可连接误称为模型可用。

静态 Bash 入口 run `42521752952` 全部 CI/本地 APK build/lint 与原签名覆盖安装
通过；真实应用域 native gate 仍通过，持久 PTY 的 Bash `-c` 与系统 id 成功。
但默认交互 Bash 仍退出。仅对自有应用域子进程附加 trace，确认 seccomp 在
libtinfo 读取 terminfo 时禁止 `setfsuid/setfsgid`，未修改过滤器或身份。
v0.4.34 的 ncurses shim 实验被 run `42523439252` 实际初始化门禁拒绝：
libtinfo 内部绑定绕过 interposition；该实现与对应测试已移除，未部署设备。
改为固定 Ubuntu ncurses 6.4+20240113-1ubuntu2.2 源码+安全补丁，关闭
HAVE_SETFSUID、保留上游 safe-open 分支及内核权限检查的 Android 专用 libtinfo，
新增真实 Bash/terminfo 无身份调用门禁；标准 Linux bundle 不变。
本轮创建的 14 个持久 PTY 诊断已通过 API 删除，不影响用户会话或终端偏好。

修复验收：run `42524341097` (`a411328`) 全部成功，包括实际 terminfo、精确
staged libtinfo 映射、真实交互 Bash 与 fs-ID 函数陷阱；可信 native 工件
`13635111177` ZIP SHA-256
`045451ed8f7d16926b2f82079536107ef198619ea9ab3b0567de855a861a39ea`。
本地 APK assembleDebug/lintDebug 通过，403 个 native / 255 个 data 与工件
逐字节一致，原签名覆盖安装成功，APK SHA-256
`4bc04edc0a0e991e92c1ecb09f91a66facc8eeb7d190e8cd642e9b6a0d80d493`。
旧设备真实 `untrusted_app` / `Seccomp=2`、SELinux Enforcing：默认无 args 持久
PTY 启动预置 Bash 后保持 running，stdin/out/err 均为 `/dev/pts/1`，maps 确认
来自 nativeLibraryDir 的 libandcode-libtinfo.so；WebSocket 输入、91×31 resize、
重连回放和 snapshot 通过 `ANDCODE_NATIVE_PERSISTENT_WS_OK`。
完整 native gate 新增强制交互初始化，得到 `ANDCODE_NATIVE_INTERACTIVE_BASH_OK`，
其余 Bionic/PRoot 子进程及版本门禁均通过；独立终端首屏 Bash 提示符截图确认。
完整 PRoot 无显式代理 apt/HTTPS/C/C++/Make/Git HTTPS/PTY 与 libc 8.9 回归通过，
`development-exit=0 network-mode=direct`。新专属验收 PTY 已删除，未删用户会话。
此结果不代表官方普通 Web PTY 或源码原生扩展加载已解决；前者仍需独立修复，
后者仍在许可/源码/闭包准入阶段。

后续网络复核(同日)：宿主 DNS 当前解析到 `198.18.0.66`，使用系统默认校验的
Python HTTPS 已成功；证书 subject 为 `one.ai.api.service.arjata`，issuer 为
私有 `Arjata Authority` 的 `Arjata Fundamental Public Endpoint Issuer`。
这仅证明宿主当前信任链可用，不代表 Android/Bun 信任。真实 APK 默认模型仍
`getaddrinfo EAI_AGAIN`，隔离显式回环代理仍 `UNABLE_TO_GET_ISSUER_CERT_LOCALLY`。
两次自有请求已 interrupt，4296 专属服务已通过其 shell API 停止；未改 4096
默认服务的代理/CA/校验。后续需带外核对的 CA 证书与显式信任配置，或 provider
提供 APK 默认信任的完整链；不能自动从网络/宿主导入未知 CA 或关闭 TLS 校验。

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
  PRoot terminal project mapping is separate from the managed backend described below.

## Managed OpenCode serve in Ubuntu PRoot

The network-trust settings offer **OpenCode 服务进入 Ubuntu PRoot（实验）**
(`serve-proot-backend`, default off). Install the PRoot instance and the complete
APK native payload first, enable the setting, then manually stop and restart the
managed service. Missing guest/payload/farm fails explicitly without direct fallback.
The terminal-backend preference remains independent; selected terminal projects
are not automatically bound into this managed guest.

The backend runs through PRoot and the guest loader, with APK payloads bound at
`/mnt/andcode-exe`, the farm at `/mnt/andcode-farm`, and `files/home` at `/root`.
Configuration, sessions and guest `/root` writes therefore persist in app home.
The imported CA directory is bound at `/mnt/andcode-ca` only after explicit CA
enablement and validation. Loopback proxy use is a separate default-off opt-in;
TLS verification stays enabled. Guest temporary files and PTY sockets use `/tmp`.
Web/TUI retain `127.0.0.1:4096`. PRoot's apparent root remains the Android app UID;
binds are writable and this is not a sandbox or a root chroot integration.

On 2026-11-11 device `8c8da214`, the app-spawned untrusted_app process chain
proot -> guest loader -> oc2 serve passed Web HTTP 200, authenticated API and
`arjata/gpt-oss-120b` plain-text response `ANDCODE_PROOT_SERVE_OK`. Agent shell
commands returned `ANDCODE_PROOT_TOOL_OK`, exit 0, Ubuntu 24.04.4 and
`/usr/bin/bash`. A Web PTY executed `id`, OS and marker commands and exited 0;
guest `/root` writes were readable in host `files/home`. The diagnostic PTY was
deleted. Manual stop left no serve PRoot/loader tree, listener or env fragment;
restart restored the service. Device PRoot/proxy/CA opt-ins remain enabled.

Tool execution passed, but provider continuation after the tool result still
returned HTTP 400 `openai_error` or HTTP 503. Full model/tool round trips remain
unresolved; no protocol workaround, history deletion or default direct-network
success is claimed. Root Ubuntu instances, `ubuntu.img` and the active runtime
farm are preserved. Other devices and abnormal-stop recovery remain pending
P0/P3 on-device verification.

Same-day reinstall retest of the reviewed build (overwrite install, data
preserved): the three opt-ins survived, the PRoot chain and binds matched the
reviewed argv, the Web UI answered 200, new serve-log lines contained no
password record, and the payload stayed opencode 2.2.6. A fresh-session API
probe reproduced the boundary set exactly — plain-text reply succeeded
(`ANDCODE_REVIEW_OK`), the shell tool executed to a completed state, and the
provider rejected the tool-result continuation with HTTP 400 `openai_error`;
three more fresh sessions failed the same way (400, 503, 400). The provider
error is reproducible with the reviewed build, not introduced by the review
changes, and remains unresolved.

Cross-model isolation (same day, same PRoot backend and build) attributes the
defect to the provider's gpt-oss-120b tool path: a two-turn plain conversation
resending turn-1 history with `reasoning_content` succeeds, and a complete
agentic tool round trip passes on `arjata/glm-5.2` — the shell tool executed,
the tool result was resent, and the model replied `ANDCODE_MODEL_TOOL_OK` with
outcome succeeded. This is the first verified full model/tool round trip on the
managed PRoot backend. gpt-oss-120b failed the same tool continuation in 5/5
fresh sessions (HTTP 400/503) while plain replies stayed fine. Use a model with
a working tool path (glm-5.2) for agentic sessions until the provider fixes the
gpt-oss-120b route. See DESIGN v0.4.54 section 4.4 for evidence
scope.

## 必须通过的实机门禁

| 验证 | chroot | PRoot（真实应用域） |
|---|---|---|
| rootfs Bash、PTY 与终端尺寸/信号 | Bash/PTY 创建通过；交互尺寸/信号待 P0/P3 | Bash/PTY/子进程、stty 初始尺寸、Ctrl+C、exit 返回、IME 往返两次 SIGWINCH/尺寸同步通过；其它设备待 P0/P3 |
| DNS、HTTPS 证书校验、`apt update/install` | root 代理模式通过；UID 60000 网络超时、直连 DNS 未通过 | 显式代理完整通过；TCP DNS 无显式代理 HTTPS/apt update/Git 通过，VPN 未关闭 |
| 新安装 `hello` ELF 能运行 | root/普通用户均通过 | 应用域通过 |
| 普通用户 gcc 编译并运行，写 `/etc` 被拒 | UID 60000 通过，LOAD 0x4000 | 待 P0/P3 |
| libc 更新后继续运行（不可盲用旧偏移补丁） | 2.39-0ubuntu8.7 → 8.9 通过 | 同版本更新后执行通过,未修改 ELF |
| 项目访问范围、停止/异常退出无遗留挂载 | 待 P0/P3 | 单项目 bind/写回/错误路径拒绝通过；不是沙箱，异常停止待 P0/P3 |
| OpenCode tools and Web PTY use the selected backend without host root | Pending integration | Device 8c8da214: opt-in managed PRoot serve, guest shell/PTY and app-UID execution passed; full tool round trip verified on `arjata/glm-5.2` (plain two-turn with history `reasoning_content` also passed); `arjata/gpt-oss-120b` tool-result continuation fails provider-side (HTTP 400/503, 5/5 fresh sessions) while its plain replies pass; other devices pending P0/P3 |

PRoot 失败时必须保留为“受限/不可用”，不能借助 root relabel 后声称 locked 支持。
