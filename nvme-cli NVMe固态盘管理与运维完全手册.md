# nvme-cli NVMe 固态盘管理与运维完全手册

> 面向 Linux 服务器、AI 集群本地盘与 NVMe-oF 运维。本文以“先确认设备身份、再读健康与日志、最后变更”为主线，命令示例以 nvme-cli 3.x 为准；2.x 的对应写法见下文。执行变更前，以本机 `nvme version`、`nvme <子命令> --help`、设备手册和平台变更流程为准。
>
> 本文是独立编写的运维手册。选题受到 [xyangclass 的同名文章](https://mp.weixin.qq.com/s/Y19cI2DYAmruuJGo4p4Xvw)启发，未转载原文内容。

## 1. 值班时先记住这四件事

1. **`/dev/nvme0n1` 不是永久身份。**设备编号会随重启、热插拔、控制器枚举顺序变化。工单至少记录序列号、型号、固件版本、PCI BDF、命名空间 ID（NSID）和机箱槽位。
2. **SMART 是趋势，不是单点“健康分”。**`critical_warning`、`available_spare`、`percentage_used`、`media_errors`、`num_err_log_entries` 和温度要结合历史基线、业务 I/O 错误、内核日志一起看。
3. **`format`、`sanitize`、命名空间删除和固件激活可能影响数据与整个控制器。**先备份、排空业务、核对作用域与设备能力，再制定回退或换盘方案。
4. **保留故障现场。**掉盘、只读、I/O 超时后，先保存 `nvme` 输出与内核日志；反复 reset 或重启会抹掉部分线索。

一个可直接用于初查的只读命令组：

```bash
nvme version
sudo nvme list
sudo nvme list-subsys
lsblk -o NAME,PATH,SERIAL,MODEL,SIZE,TRAN,TYPE,FSTYPE,MOUNTPOINTS
sudo nvme id ctrl /dev/nvme0
sudo nvme id ns /dev/nvme0n1
sudo nvme log smart /dev/nvme0
sudo nvme log error /dev/nvme0
journalctl -k -b --no-pager | grep -Ei 'nvme|pcie|aer|i/o error'
```

以上 `/dev/nvme0` 与 `/dev/nvme0n1` **只是示例**，必须先根据当前主机的设备映射替换。没有相应设备时，命令会失败。

## 2. 对象模型：先分清控制器和命名空间

| 对象 | 常见路径 | 用来做什么 |
| --- | --- | --- |
| NVMe 控制器 | `/dev/nvme0`，字符设备 | Identify Controller、SMART、错误日志、固件、Sanitize 等控制器级操作 |
| 命名空间 | `/dev/nvme0n1`，块设备 | 文件系统承载对象；Identify Namespace、容量与 LBA 格式 |
| 分区 | `/dev/nvme0n1p1` | GPT/文件系统层对象，通常交给 `lsblk`、`blkid`、`parted` 管理 |
| NVMe 子系统 | 可含多个控制器与路径 | NVMe-oF、双端口盘与多路径场景需要识别路径关系 |

一个控制器可以暴露多个命名空间；一个命名空间在多路径场景中也可能经不同控制器可达。因此“盘、控制器、命名空间、路径”不能直接画等号。`nvme list-subsys`、`nvme list -v` 和 sysfs 可补齐拓扑。

识别物理盘时，先对照以下信息：

```bash
sudo nvme list -v
sudo nvme id ctrl /dev/nvme0 | grep -E '^(sn|mn|fr|subnqn|cntlid|nn)'
sudo nvme id ns /dev/nvme0n1 | grep -E '^(nsze|ncap|nuse|flbas|lbaf)'
readlink -f /sys/class/nvme/nvme0/device
udevadm info --query=property --name=/dev/nvme0n1 | grep -E 'ID_SERIAL|ID_MODEL|ID_PATH'
```

`sn` 是序列号，`mn` 是型号，`fr` 是固件版本；`nsze` 是命名空间逻辑块数量，`ncap` 是可用容量，`nuse` 是已分配逻辑块估计，`flbas` 指向当前 LBA 格式。`nuse` 不是文件系统 `df` 的已用量。

## 3. 安装、版本与命令写法

发行版优先使用其软件包，避免自行组合不匹配的 `nvme-cli` 与 `libnvme`：

```bash
# Debian / Ubuntu
sudo apt install nvme-cli

# RHEL / Rocky / AlmaLinux
sudo dnf install nvme-cli

nvme version
nvme help
```

nvme-cli 3.0 将多类命令归入插件组。2.x 的常见旧写法在默认构建中仍可作为弃用别名，但新脚本宜采用 3.x 写法；旧发行版则按本机 `--help` 改写。

| nvme-cli 3.x | nvme-cli 2.x 常见写法 | 用途 |
| --- | --- | --- |
| `nvme id ctrl` | `nvme id-ctrl` | 控制器信息 |
| `nvme id ns` | `nvme id-ns` | 命名空间信息 |
| `nvme log smart` | `nvme smart-log` | SMART/Health |
| `nvme log error` | `nvme error-log` | 错误信息日志 |
| `nvme log fw` | `nvme fw-log` | 固件槽位日志 |
| `nvme log self-test` | `nvme self-test-log` | 自检结果 |
| `nvme log sanitize` | `nvme sanitize-log` | Sanitize 状态 |
| `nvme ns list` | `nvme list-ns` | 命名空间列表 |
| `nvme fw download` | `nvme fw-download` | 固件镜像传输 |
| `nvme fw commit` | `nvme fw-commit` | 固件提交与激活 |

不要解析供人阅读的列对齐文本做长期自动化。支持 JSON 的命令可用 `-o json`，并在升级 nvme-cli 时验证字段、错误码和实际输出。nvme-cli 3.2 的开发版又调整了文本排版，JSON 更适合作为机器接口。

## 4. 设备发现与上线核查

新盘插入服务器后，按下面顺序走一遍。所有配置类动作留在盘身份与健康核查之后。

1. **确认发现。**`lspci -nn | grep -i 'non-volatile memory'`、`nvme list`、`lsblk`，并对照 BMC/机箱槽位。
2. **确认是目标盘。**记录 `sn`、`mn`、`fr`、BDF、NSID 和容量。不能只凭 `/dev/nvmeX` 编号。
3. **查看已有数据。**`lsblk -f`、`blkid`、`findmnt`、`pvs`、`mdadm --detail --scan`；在不知道盘用途时不创建分区或格式化。
4. **查看健康与错误。**读取 SMART、错误日志和内核日志，保存首次接入时间。
5. **确认能力。**Identify Controller 的 `oacs`、`fna`、`sanicap`、`frmw`、`nn` 等字段决定管理命令是否可用、作用域如何；名称相近的盘也可能有不同固件配置。
6. **按平台方案交付。**文件系统、RAID、LVM、Ceph OSD 或 Kubernetes local PV 只能选定一个明确的所有者。写盘前确认它不属于现有阵列、卷组或其他节点。

记录模板：

| 字段 | 值 |
| --- | --- |
| 主机 / 机箱 / 槽位 | 待填 |
| 序列号 / 型号 / 固件 | 待填 |
| PCI BDF / 控制器 / NSID | 待填 |
| 容量 / LBA 格式 / 业务用途 | 待填 |
| SMART 基线 / 首次发现时间 | 待填 |

## 5. SMART：如何读出真正有用的信号

```bash
sudo nvme log smart /dev/nvme0
sudo nvme log smart /dev/nvme0 -o json
sudo nvme log error /dev/nvme0
sudo nvme log fw /dev/nvme0
```

| 字段 | 解释 | 处置思路 |
| --- | --- | --- |
| `critical_warning` | 位图，不是普通计数器；非 0 需要解码 | 结合厂商手册与其他字段立即定位，不能简单归零后放行 |
| `temperature` | 综合温度，工具通常显示摄氏度 | 结合温度阈值、风道、持续时间和节流现象判断 |
| `available_spare` / `available_spare_threshold` | 剩余备用容量及厂商阈值 | 低于阈值或持续下降时规划替换 |
| `percentage_used` | 厂商估算的寿命消耗百分比 | 可超过 100；不等于“剩余寿命”，应看增长斜率和保修指标 |
| `media_errors` | 控制器检测到的不可恢复介质错误累计 | 新增值需要关联 I/O 错误、LBA、业务与厂商诊断 |
| `num_err_log_entries` | 错误日志条目累计数 | 增长不一定都是坏块；看错误日志具体状态和时间线 |
| `unsafe_shutdowns` | 非正常断电累计 | 增长时查供电、BMC、主机重启和盘背板 |
| `data_units_read` / `data_units_written` | 读写工作量计数 | 一个单位为 1000 × 512 字节；用于趋势与 TBW 估算 |
| `controller_busy_time` | 控制器忙碌分钟数累计 | 不能单独当作实时利用率 |

`critical_warning` 的标准位包括备用空间不足、温度超阈值、可靠性下降、介质进入只读，以及易失性内存备份失效等。具体位与新增位随规范版本和设备能力变化；自动化要保留原始数值并按对应规范解码。SMART 日志还可能提供警告温度与临界温度累计时间；一次正常温度读数不能抵消长期过热记录。

判读时采用“**绝对状态 + 增量 + 业务影响**”：

- `media_errors` 从 0 到 1 且业务出现 `EIO`：先保全数据与现场，排空或切换业务，准备替换/厂商诊断。
- `percentage_used` 较高但数月平稳、无错误：按寿命策略规划，不仅凭一个数字判死盘。
- 温度长期接近厂商阈值并伴随性能下降：先查风扇、风道、进风温度、SSD 节流与业务负载。
- `num_err_log_entries` 增长但 `media_errors` 不变：查看具体 NVMe 状态码、内核重试、链路/AER，而非直接认定 NAND 损坏。

## 6. 错误日志与内核日志：建立时间线

```bash
sudo nvme log error /dev/nvme0
journalctl -k --since '1 hour ago' --no-pager | grep -Ei 'nvme|pcie|aer|timeout|reset|i/o error'
sudo dmesg -T | grep -Ei 'nvme|pcie|aer|timeout|reset|i/o error'
```

NVMe 错误日志通常是有限的环形记录，并非完整历史。`error_count` 可帮助判断顺序，`sqid`、`cmdid`、`status_field`、`lba`、`nsid` 等字段可帮助定位请求；有些设备不提供全部细节。Linux 内核日志往往更能说明“先超时，后 reset，最后掉盘”的先后关系。

遇到 I/O timeout 时，按顺序核查：

1. 是单盘、单控制器、单 PCIe Root Port，还是整机多盘同时异常？
2. 是否有 PCIe AER、链路降速、背板/retimer/BMC 事件、供电波动？
3. SMART 的介质错误与错误日志是否同时增长？
4. 问题是否只在特定负载、温度或省电状态发生？
5. 多路径场景是某一条路径失效，还是命名空间整体不可达？

单盘反复介质错误更偏向盘本体；同一插槽换盘后复发更偏向槽位、背板、PCIe 或供电。这只是排查方向，最终仍需实测和厂商诊断。

## 7. 自检与取证

设备声明支持自检时，可在维护窗口发起短测；扩展自检可能持续较长时间，并对业务延迟产生影响。

```bash
sudo nvme device-self-test /dev/nvme0 --self-test-code=1
sudo nvme log self-test /dev/nvme0
```

`--self-test-code=1` 是短测，`2` 是扩展自检。命令成功通常表示“开始了自检”，并不等于自检通过；结果要从 self-test 日志确认。不要在故障盘尚未保全数据时让长测代替备份。

提交厂商工单前，保存至少以下证据：序列号与固件版本、SMART 原始输出、错误日志、自检日志、内核日志、BMC/PCIe 日志、首次与最近复发时间、业务 I/O 错误、盘与槽位交叉验证结果。日志中的序列号和业务路径可能敏感，外发前按组织要求处理。

## 8. 变更命令的边界

| 操作 | 可能影响 | 操作前必须确认 |
| --- | --- | --- |
| `nvme format` | LBA 格式变更；可选用户数据擦除 | 目标 NSID、`fna` 作用域、文件系统/阵列所有者、备份与停机窗口 |
| `nvme sanitize` | 控制器/子系统范围的数据清除，耗时可能较长 | `sanicap`、擦除方法、所有命名空间、退役证明要求 |
| `nvme ns delete/create/attach/detach` | 容量和路径布局变化，业务设备可能消失 | 命名空间能力、控制器列表、上层卷/阵列映射 |
| `nvme fw download/commit` | 固件切换、控制器 reset、I/O 中断 | 厂商镜像与适配型号、槽位、激活方式、回退计划 |
| `nvme reset` / `subsystem-reset` | 当前控制器或子系统 I/O 中断 | 多路径状态、业务排空和集群故障转移能力 |
| `nvme set-feature` / 原始 passthru | 性能、功耗或协议状态变化 | Feature ID 的规范与厂商语义、持久化行为 |

在生产机上不要通过 `--force` 绕过“设备忙”的保护。控制器支持某个命令，并不表示当前数据布局与业务允许执行。

### 8.1 Format 与 Sanitize 不是同一件事

`format` 改变或重新初始化命名空间格式；其 `--ses=1` 请求用户数据擦除，`--ses=2` 请求加密擦除。是否支持及影响范围必须看 Identify Controller 的 `fna`、Identify Namespace 的 LBA 格式表和设备手册。`sanitize` 是独立的清除操作，可选择 Block Erase、Overwrite 或 Crypto Erase；应通过 Sanitize 状态日志确认完成和结果。文件系统层的 `mkfs`、`rm`、`blkdiscard` 也不等价于设备级安全擦除。

在审批与核对表中填入真实设备和参数后才执行，以下是**参数结构示意，不是可直接运行的工单**：

```text
nvme format <已核对的命名空间或控制器> --namespace-id=<已核对NSID> --lbaf=<受支持格式编号> --ses=<擦除模式>
nvme sanitize <已核对的控制器> --sanact=<设备支持的动作>
nvme log sanitize <控制器>
```

退役验收应记录擦除范围、操作时间、控制器状态、Sanitize 完成结果及组织要求的验证证据。加密擦除的有效性依赖设备确实对所有用户数据使用受控密钥，不能只凭命令返回 0 推断合规完成。

### 8.2 固件升级

先读 `nvme id ctrl` 的 `frmw`、`nvme log fw`，再核对厂商发布说明中支持的型号、当前版本、目标版本、槽位和激活条件。`fw download` 仅把镜像传给设备；`fw commit` 的 action 决定替换、下次 reset 激活或尝试立即激活。**提交成功不代表已经运行新固件**，还要按厂商要求完成 reset/重启并重新读取 `fr` 与固件日志。

升级流程：灰度一台非关键节点 → 验证业务 I/O、SMART、错误日志和重启后枚举 → 分批排空生产节点 → 每批验收后放行。共享 NVMe-oF 存储的固件升级应由存储平台流程管理，不能把远程命名空间当成本地单盘处理。

### 8.3 命名空间管理

`nvme ns list <控制器>` 可查看命名空间列表。创建与删除只适用于控制器明确支持该能力的场景。nvme-cli 3.0 的 `nvme ns create/delete/attach/detach` 成功时默认可能没有确认文本，脚本必须检查退出码，并重新读取列表和 Identify 结果。不要从旧脚本的 stdout 解析新 NSID。

## 9. NVMe-oF 与多路径补充

本地 PCIe 盘与 NVMe over Fabrics 共用许多管理命令，但故障域不同。NVMe/TCP 或 RDMA 还要核查网络连通性、目标 NQN、主机 NQN、认证、发现服务、路径状态和 ANA。`nvme list-subsys` 是第一步：一条块设备路径失败不一定意味着命名空间不可用，所有路径同时异常则应调查网络、目标存储和主机配置。

```bash
sudo nvme list-subsys
sudo nvme list -v
cat /etc/nvme/hostnqn
```

不要直接在共享命名空间上运行 `format`、`sanitize` 或命名空间管理命令。3.0 以后 NVMe-oF 连接配置也有变化；连接与重连自动化应按本机版本及平台编排器检查，避免与已有控制器所有者冲突。

## 10. AI 集群本地盘的三个典型场景

### 10.1 训练数据缓存盘性能下降

先对比训练作业的读放大、并发和数据集热度，再看盘。检查温度与节流、PCIe 链路速率/宽度、队列深度、文件系统空间与碎片、后台压缩/GC、SMART 错误、内核 I/O timeout。不要只因为吞吐下降就做 secure erase 或固件升级。

### 10.2 Kubernetes 节点准备换盘

确定盘承载的是容器运行时、kubelet、local PV、Ceph OSD 还是临时缓存；分别执行驱逐、数据迁移/副本恢复和盘身份核对。对 local PV，不能假设同名 `/dev/nvme0n1` 在更换后仍指向原盘；使用稳定标识并验证调度与挂载结果。

### 10.3 多盘同时掉线

优先怀疑共同故障域：PCIe switch、背板、retimer、供电、主机重启或内核/驱动事件。保存同一时间窗口内所有盘的 BDF、AER、BMC 与内核日志，再决定是否换盘。同时更换多块 SSD 可能掩盖真正根因。

## 11. 可复用的只读取证脚本

脚本只采集当前系统已识别的控制器，不执行 reset、写入或擦除。先在隔离环境确认本机的命令写法。运行结果包含序列号和日志，按内部工单资料管理。

```bash
#!/usr/bin/env bash
set -euo pipefail

out="${1:-./nvme-evidence-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$out"
nvme version > "$out/version.txt"
nvme list > "$out/list.txt"
nvme list-subsys > "$out/list-subsys.txt"
lsblk -o NAME,PATH,SERIAL,MODEL,SIZE,TRAN,TYPE,FSTYPE,MOUNTPOINTS > "$out/lsblk.txt"
journalctl -k -b --no-pager > "$out/kernel-journal.txt"

shopt -s nullglob
for sysctrl in /sys/class/nvme/nvme[0-9]*; do
    ctrl="${sysctrl##*/}"
    [[ "$ctrl" =~ ^nvme[0-9]+$ ]] || continue
    dev="/dev/$ctrl"
    [[ -c "$dev" ]] || continue
    mkdir -p "$out/$ctrl"
    nvme id ctrl "$dev" > "$out/$ctrl/id-ctrl.txt" 2>&1 || true
    nvme log smart "$dev" > "$out/$ctrl/smart.txt" 2>&1 || true
    nvme log error "$dev" > "$out/$ctrl/error.txt" 2>&1 || true
    nvme log fw "$dev" > "$out/$ctrl/fw.txt" 2>&1 || true
done

printf 'Evidence: %s\n' "$out"
```

脚本中的 `|| true` 只用于允许不支持的日志继续采集；**不能**据此判断健康。查看每个输出文件中的错误，并给最终工单附上人工说明。需要长期监控时，应单独做适配版本的采集器，保留原始指标并监控增量。

## 12. 巡检周期与告警分级建议

以下是建立基线时的起点，不是跨厂商通用阈值。具体阈值以 SSD 型号、业务 SLO、保修和平台冗余为准。

| 周期 | 采集内容 | 处理重点 |
| --- | --- | --- |
| 每分钟或平台既有周期 | 设备在线状态、I/O 错误、内核 timeout、路径状态、温度 | 掉盘和业务错误需要即时告警 |
| 每日 | SMART 原始值与增量、错误日志新增项、固件版本 | 关注 `critical_warning`、`media_errors`、备用空间和温度变化 |
| 每周 | 读写量、寿命消耗速度、异常断电次数、同型号盘横向比较 | 识别异常写放大、冷却不足和局部批次问题 |
| 变更前后 | Identify、SMART、错误日志、内核日志和业务读写验收 | 形成可追溯的前后快照 |

可按业务影响分级：**立即隔离或切流**适用于设备只读、持续 I/O 错误、掉盘或多路径全部失败；**当天调查**适用于新出现的介质错误、备用空间预警、反复 reset；**计划处理**适用于寿命消耗加快、温度余量下降或固件维护需求。任何单项指标都要结合变化速度与业务现象。

## 13. 常用命令速查

| 目的 | 命令（3.x） | 属性 |
| --- | --- | --- |
| 列盘与拓扑 | `nvme list`、`nvme list-subsys` | 只读 |
| 控制器/命名空间身份 | `nvme id ctrl <ctrl>`、`nvme id ns <ns>` | 只读 |
| SMART/错误/固件日志 | `nvme log smart <ctrl>`、`nvme log error <ctrl>`、`nvme log fw <ctrl>` | 只读 |
| 自检结果 | `nvme log self-test <ctrl>` | 只读 |
| 发起短测 | `nvme device-self-test <ctrl> -s 1` | 可能影响时延 |
| 查看命名空间 | `nvme ns list <ctrl>` | 只读 |
| 查看 Sanitize 进度 | `nvme log sanitize <ctrl>` | 只读 |
| 格式变更 | `nvme format ...` | 高危变更 |
| 安全清除 | `nvme sanitize ...` | 不可逆变更 |
| 固件升级 | `nvme fw download ...`、`nvme fw commit ...` | 高危变更 |

`<ctrl>` 与 `<ns>` 是占位符。厂商插件和 `admin-passthru` 可以执行规范外或厂商私有操作，应单独查设备文档，不能按这张通用表直接自动化。

## 14. 常见问题速答

**`nvme list` 看不到盘，怎么办？** 先查 `lspci`、`dmesg`、BMC 与物理槽位。如果 PCIe 设备也消失，优先查硬件链路和供电；如果 PCIe 在而块设备不在，查驱动、控制器初始化、命名空间和多路径状态。

**SMART 没有报警，盘就一定健康吗？** 不能这样判断。链路/背板故障、突发掉盘、文件系统错误和部分固件问题未必先反映为 SMART 预警。

**`percentage_used=100` 就立刻不能用了吗？** 它是厂商寿命估算，达到 100 表示估算耐久度已消耗完，不等于此刻所有读取都会失败。应结合服务等级、保修、写入速率与替换窗口处理。

**为什么 `nvme format /dev/nvme0n1` 可能影响别的命名空间？** 设备可能声明 Format 作用于所有命名空间，且控制器字符设备、块设备和显式 NSID 的默认作用域不同。必须先看 `fna` 和本机命令帮助，并以维护窗口验证。

**自检通过还需要看业务日志吗？** 需要。自检覆盖的是设备内部可检测的问题，不能替代 PCIe、网络、多路径、文件系统和应用层验证。

## 15. 来源与进一步阅读

- [nvme-cli 项目与命令文档](https://github.com/linux-nvme/nvme-cli)
- [nvme-cli NEWS：3.0 命令分组与 3.1 变更](https://github.com/linux-nvme/nvme-cli/blob/master/NEWS.md)
- [SMART 日志命令](https://github.com/linux-nvme/nvme-cli/blob/master/Documentation/nvme-smart-log.txt)、[自检命令](https://github.com/linux-nvme/nvme-cli/blob/master/Documentation/nvme-device-self-test.txt)
- [Format 命令](https://github.com/linux-nvme/nvme-cli/blob/master/Documentation/nvme-format.txt)、[Sanitize 命令](https://github.com/linux-nvme/nvme-cli/blob/master/Documentation/nvme-sanitize.txt)、[Firmware Commit 命令](https://github.com/linux-nvme/nvme-cli/blob/master/Documentation/nvme-fw-commit.txt)
- [NVM Express 规范资料](https://nvmexpress.org/specifications/)
- [启发本文选题的微信原文](https://mp.weixin.qq.com/s/Y19cI2DYAmruuJGo4p4Xvw)
