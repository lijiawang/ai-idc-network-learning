# NVIDIA GPU Xid 常见错误码全解析、故障定位与标准化处理方案

> 本文面向 Linux 裸机、虚拟机和 Kubernetes GPU 集群运维，依据 NVIDIA 当前 Xid Catalog、GPU Debug Guidelines、`nvidia-smi`、DCGM 和 GPU Memory Error Management 文档整理。
>
> **最重要的结论：Xid 是驱动写入内核日志的故障线索，不是单凭一个编号就能得到的根因或 RMA 判决。** 同一个 Xid 可能来自应用、驱动、GPU、显存、PCIe、NVLink 或远端设备；恢复动作与根因调查必须分开。

## 1. 先看结论：值班时应该怎么做

收到 Xid 告警后，按以下顺序处理：

1. **先按完整 Xid 和 Recovery Action 分级。**`Reset`、`Reboot`、`Drain P2P`、`Drain and Reset`、新驱动上的 `Recover IMEX Domain`、Xid 79、设备不可达或未知高危事件，应立即停止向对应 GPU、节点或 IMEX 域派新任务；`RESTART_APP`、`IGNORE` 或 `None` 不应自动 cordon 整个节点。
2. **按时间线留证。**保存第一条 Xid 前后的完整日志、GPU UUID、PCI BDF、进程/Pod、伴随 Xid、PCIe AER、NVSwitch SXid 和 Fabric Manager 日志。
3. **在恢复前运行 `nvidia-bug-report.sh`。**掉电、重启和复位都可能丢失关键现场。
4. **查看 Xid 154 或 GPU Recovery Action。**它决定此刻应执行 `None`、`Reset`、`Reboot`、`Drain P2P`、`Drain and Reset`，还是在新驱动上恢复整个 IMEX 域。
5. **再按原始 Xid 查根因。**例如 13/31 先查应用，48/63/64/94/95 查显存，74 查 NVLink，79 查 PCIe/供电/硬件，119/120 查 GSP/驱动/固件。
6. **排空后做 DCGM 主动诊断；需要 RMA 时运行 Field Diagnostic。**DCGM Pass 不能代替 Field Diagnostic，也不能单独决定换卡。
7. **通过恢复验收后才重新调度。**GPU 能被 `nvidia-smi` 看见，不代表已经健康。

一个适合值班台的简化决策如下：

```text
发现 Xid
   │
   ├─ 先采集日志与 nvidia-bug-report
   │   高危/未知事件停止对应 GPU 或节点的新调度
   │   应用级/信息级事件不自动 cordon 整个节点
   │
   ├─ 有 Xid 154 / GPU Recovery Action？
   │      ├─ Reboot ───────────── 排空节点 → OS 重启 → 验收
   │      ├─ Reset ────────────── 排空目标 GPU → GPU reset → 验收
   │      ├─ Drain P2P ────────── 排空 P2P/UVM → 重新查询 → 按新动作处理
   │      ├─ Drain and Reset ───── 禁止新任务 → 等现有任务结束 → reset → 验收
   │      ├─ Recover IMEX Domain ─ 隔离关联域/作业 → 按平台域恢复流程 → 验收
   │      └─ None ─────────────── 不复位，按原始 Xid 调查
   │
   └─ 无 Recovery Action ──────── 查最新版 Xid Catalog 的 Immediate Action
                                  再执行对应错误码的调查流程
```

## 2. Xid 到底是什么

Xid 是 NVIDIA 驱动向操作系统内核日志或事件日志写入的错误报告。Linux 上通常能在 journal、`/var/log/messages` 或 `/var/log/syslog` 中找到。一个典型日志如下：

```text
NVRM: GPU at PCI:0000:3b:00: GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
NVRM: Xid (PCI:0000:3b:00): 79, GPU has fallen off the bus.
```

这里至少包含三类定位信息：

| 字段 | 示例 | 用途 |
| --- | --- | --- |
| GPU UUID | `GPU-aaaa...` | 跨重启、跨 GPU index 关联同一块 GPU |
| PCI BDF | `0000:3b:00.0` | 关联插槽、PCIe Root Port、AER 和拓扑 |
| Xid 与 payload | `79, ...` | 确定错误类型；部分错误还需解码后续字段 |

GPU index（GPU 0、GPU 1）可能随启动或设备变化而改变，工单和监控应以 **UUID + PCI BDF + 机箱/槽位** 为主键。

Xid 与以下概念不能混为一谈：

- **CUDA 错误码**是应用 API 的返回值；Xid 来自内核驱动。
- **SXid**是 NVSwitch 错误。HGX/DGX NVSwitch 系统排障时要同时查 Xid、SXid 和 Fabric Manager 日志。
- **Xid 154**不是根因码，而是伴随其他 Xid 出现的恢复动作摘要。
- **DCGM 指标**可用于监控和诊断，但指标中的 Xid 值仍需回到完整内核日志读取上下文。

## 3. 先分清“恢复动作”和“根因调查”

最新版 NVIDIA Xid Catalog 对每个错误给出两列动作：

- **Immediate Action**：让系统恢复服务的动作，可作为自动化的决策输入；排空、复位和重启仍要验证平台能力、目标范围、客户端释放、幂等性，并在失败后保持隔离。
- **Investigatory Action**：错误复发或不符合预期时，用来追查应用、软件、互联或硬件根因。

这解释了为什么“reset 后恢复”不等于“问题已经解决”。例如 Xid 119 可以通过 GPU reset 暂时恢复，但仍要调查 GSP、驱动和固件；Xid 79 重启后 GPU 重新出现，也不能排除 PCIe 链路、供电或卡本体问题。

### 3.1 Xid 154 与 GPU Recovery Action

较新的驱动可能在根因 Xid 后报告 Xid 154，例如：

```text
Xid 154, GPU recovery action changed from 0x0 (None)
to 0x2 (Node Reboot Required)
```

`nvidia-smi -q` 中的 **GPU Recovery Action**也表达同一类恢复需求。它只说明“怎样清除已经发生的故障状态”，不说明“什么故障触发了这个动作”。`--query-gpu=gpu_recovery_action` 是 R570 系列加入的查询字段；更旧驱动可能不支持或显示 `N/A`，此时以 `nvidia-smi -q`、原始 Xid 和对应版本 Catalog 为准。

| Recovery Action | 标准处理 | 调度策略 |
| --- | --- | --- |
| `None` | 不需要 reset；按原始 Xid 调查，必要时只重启受影响应用 | 无其他风险时可继续使用 |
| `Reset` | 终止目标 GPU 的全部客户端，执行 GPU reset，随后验收 | 立即停止向该 GPU 派新任务 |
| `Reboot` | 排空节点后执行操作系统重启；官方说明 warm reboot 通常足够 | 节点 cordon，禁止新任务 |
| `Drain P2P` | 停止所有 P2P 流量并关闭 UVM persistence，重新查询动作；仍为该状态则 reset | 禁止新任务，排空关联 GPU |
| `Drain and Reset` | GPU 可能已降容；现有未受影响任务可完成或 checkpoint，排空后 reset | 不得派新任务 |
| `Recover IMEX Domain` | 新版 NVML 定义的 IMEX 域恢复动作；不得简化为单节点 reset/reboot，应按多节点 NVLink/IMEX 平台 runbook 恢复并重新查询状态 | 隔离关联作业和 IMEX 域，禁止域内新任务 |

`Recover IMEX Domain` 是新版 NVML/驱动新增状态，只会出现在使用 IMEX 的相关平台；旧版 `nvidia-smi` 文档和驱动可能仍只显示前五项。如果驱动不支持 Recovery Action 字段，就使用对应版本 Xid Catalog 的 Immediate Action，再结合本文错误码分支处理。

旧的 `GPU Reset Status` / `Drain and Reset Status` 已被 NVIDIA 废弃，新自动化不应继续以它们作为决策源。

## 4. 常见 Xid 错误码速查表

下表中的“立即动作”以当前 NVIDIA Xid Catalog 为基线。`Reset` 是否能单卡执行，还取决于 NVLink、NVSwitch、Fabric Manager、MIG 和虚拟化环境，详见第 8 节。

| Xid | 官方含义 | 常见方向 | 立即动作 | 深入调查重点 | 仅凭该码 RMA？ |
| --- | --- | --- | --- | --- | --- |
| 8 | GPU stopped processing | 应用、驱动、硬件 | 重启应用 | 复发时联系支持 | 否 |
| 11/25 | push buffer 非法或损坏 | 应用/CUDA/驱动 | 重启应用 | 失败进程、应用输入、CUDA | 否 |
| **13** | Graphics Engine Exception | 多数为应用越界/非法指令，少数驱动或硬件 | 重启应用 | Compute Sanitizer、cuda-gdb、复现模式 | 否 |
| **31** | GPU memory page fault / MMU fault | 多数为非法地址访问，也可能驱动或硬件 | 重启应用 | fault 是否固定在同一 GPU、应用复现 | 否 |
| **32** | PBDMA error | 触发说明主要指向 PCIe quality；也需排软件路径 | 重启应用 | 按 Catalog 查应用/CUDA，同时关联 AER、链路、插槽、riser/retimer | 否 |
| 37/38 | driver firmware error | 驱动/固件 | 无额外动作 | 版本、bug-report、前序 Xid；38 复发报支持 | 否 |
| 39/40/41 | Copy Engine Exception | 应用、驱动、硬件 | 重启应用 | 复现负载、DCGM/FieldDiag | 否 |
| **43** | GPU stopped processing，应用通道被终止 | 通常为应用软件故障的结果 | 无额外动作 | 向前找 13/31 等首发错误 | 否 |
| **45** | preemptive cleanup / channel teardown | Ctrl-C、SIGKILL、reset 或前序故障后的清理 | 有其他 Xid 时跟随主因；独立出现且平台适用时重启 FM | 时间线、操作记录、FM | 否 |
| 46 | GPU timeout | GPU/驱动卡死 | Reset GPU | 复发时联系支持 | 否 |
| **48** | Double-bit / uncorrectable ECC error | DRAM/HBM 或 SRAM UCE | 单独出现 reset；伴 63/64 时 drain 后 reset | 63/64、94/95、171/172、阈值、FieldDiag | 条件式 |
| 54 | GPU 辅助供电未连接 | 供电/连接 | 检查机械连接 | 电源线、背板、插接 | 否 |
| 60 | video processor exception | 软件/驱动 | 重启应用 | 驱动、应用、前序错误 | 否 |
| 62 | internal micro-controller halt | GPU 微控制器/驱动 | Reset GPU | bug-report、复发模式 | 否 |
| **63** | memory remapping/page retirement event | 重映射或页退役记录成功 | 单独出现无需动作 | pending、bucket、伴随 48/94 | 否 |
| **64** | memory remapping/page retirement failure | 重映射/页退役记录失败 | 优先服从同次 Recovery Action；无摘要时当前 Catalog 要求 Reset，A100 指南要求节点 reboot | failure flag、InfoROM、FieldDiag | 强候选，仍需验证 |
| 66/67 | driver illegal access | 驱动/软件 | 无额外动作 | 66 调查软件；67 联系支持 | 否 |
| **68** | NVDEC0 Exception | 视频解码应用、驱动或硬件 | 重启应用 | codec/输入、驱动、复发性 | 否 |
| **69** | Graphics Engine class error | 应用/CUDA、驱动 | 重启应用 | 应用与 CUDA，复发再升级 | 否 |
| **74** | NVLink Error | 本地链路、对端 GPU/NVSwitch、连接/SI | 严格解码 7 字段并执行 NVLink workflow | 完整 payload、link、SXid、FM；结果可能是忽略、reset 或报支持 | 条件式 |
| 78 | vGPU Start Error | host/guest 驱动或 vGPU 类型不兼容 | 更新兼容的软件/固件 | vGPU 支持矩阵 | 否 |
| **79** | GPU has fallen off the bus | PCIe 链路、GPU、供电、插槽、主板、驱动 | 重启裸机 | AER、供电、热、故障随卡/随槽 | 条件式 |
| 80 | push buffer CRC mismatch | 发送给 GPU 的数据损坏 | 重启应用 | 应用/CUDA、PCIe、复现 | 否 |
| **92** | high single-bit ECC error rate | 显存健康度下降 | 无额外动作 | 联系支持；检查 ECC 趋势、remap/retire、FieldDiag | 条件式 |
| **94** | contained memory error | 错误局限于一个应用 | 重启受影响应用；方便时 reset | row-remap、63、受影响 PID/GI | 条件式 |
| **95** | uncontained memory error | 影响多个应用 | 优先服从同次 Recovery Action；无摘要时当前 Catalog 要求 Reset，A100 非 MIG 指南要求节点 reboot | 48/63/64、remap failure、FieldDiag | 条件式 |
| 109 | context switch timeout | GPU/驱动 | Reset GPU | 复发时联系支持 | 否 |
| 110 | security fault | 软件，也可能硬件 | 优先服从 Recovery Action；无摘要时 reset，并撤销最近硬件改动、冷复位整机 | 失败即联系硬件厂商 | 条件式 |
| **119** | GSP RPC Timeout | GSP/驱动/固件，硬件仍需排除 | Reset GPU | 版本、完整 payload、前序 Xid | 否 |
| **120** | GSP Error | GSP/驱动/固件，硬件仍需排除 | Reset GPU | 同 119 | 否 |
| 121 | corrected C2C link error | GB200 GPU 与 Grace CPU 的 C2C NVLink 已纠正错误 | 无额外动作 | 重复时联系支持；维护窗可 reset 以重训链路 | 否 |
| 137 | NVLink remote MMU privilege fault | 常见为非法 P2P 访问 | 通常无需 reset | Compute Sanitizer、cuda-gdb | 否 |
| 140 | unrecovered ECC error | 错误未能完成 offlining/remap | Reset GPU | 持续则联系硬件厂商 | 条件式 |
| 143 | GPU initialization error | 初始化/驱动/硬件 | Reset GPU | 启动日志、版本、硬件 | 条件式 |
| **144–150** | NVLink 5 子系统错误 | Blackwell NVLink、对端、链路/SI/软件 | 必须按 Catalog 解码 | subcode、severity、IntrInfo、ErrorStatus | 条件式 |
| **154** | GPU Recovery Action Changed | 其他 Xid 的恢复动作摘要 | 按消息中的动作处理 | 回看原始 Xid | 否 |
| 156/157 | resource retirement event/failure | Hopper+ 资源退役 | 156 reset；157 无额外动作 | 157 联系支持；检查资源状态、复发、FieldDiag | 条件式 |
| **171/172** | DRAM/SRAM UCE 补充说明 | 细分 Xid 48 的内存位置 | 跟随 48 | DRAM row-remap 或 SRAM 阈值 | 条件式 |

> **代际边界**
>
> 本表主要面向 Ampere 及以后数据中心 GPU；Volta 及更早产品应查 NVIDIA 旧版 Catalog。最新 Catalog 将 Xid 74 标为 A100/H100 适用、B100/GB200 不适用；Blackwell NVLink 主要看 Xid 144–150 等新码。63/64 在 Ampere 及以后表示 row remapping，在较旧的支持产品上表示 dynamic page retirement。另有部分码只适用于特定代际，例如 Xid 54 不适用于 GB200，Xid 80 仅标为 A100/H100，Xid 110/143 不适用于 A100。处理前必须确认 GPU 代际、驱动版本和 Catalog 的 `Applies to` 列。

> 本表是“常见错误码”速查，不是 Catalog 的穷举副本。遇到未列出的 Xid，必须按完整编号查询当前 Catalog；不得根据编号相邻或名称相似套用动作。

## 5. 高频错误码详细解析

### 5.1 Xid 13 与 31：先查应用，但不要绝对化

Xid 13 常见于数组越界、非法指令或非法寄存器；Xid 31 是 MMU 报告非法地址访问。两者多数是应用级问题，立即动作都是重启应用，而不是 reset GPU。

```bash
# 在可复现的测试环境运行；Compute Sanitizer 会显著降低程序速度
compute-sanitizer --tool memcheck \
  --error-exitcode 1 \
  --log-file 'compute-sanitizer.%p.log' \
  <application> <args>

# 建议测试构建加入 -lineinfo；也可以在调试环境用 cuda-gdb
cuda-gdb --args <application> <args>
```

进一步分流不能只看一次日志：

- 只跟特定应用、模型、输入或版本复现：优先修应用/CUDA。
- Xid 13 重复落在相同 TPC/GPC，或 Xid 31 重复落在同一 GPU BDF：按最新 Catalog 运行 DCGM EUD/Field Diagnostic，排除硬件。
- 相同应用在多块不同 GPU 上报 Xid 31：更像应用或软件路径。
- 已知良好应用仍稳定复现：保存最小复现和 bug-report，升级 NVIDIA/整机厂商支持。

不要因为 13/31 中带有“memory”就直接判定显存损坏，也不要因为它们通常是应用错误就忽略跨应用、固定物理单元的重复模式。

### 5.2 Xid 43 与 45：经常是结果码，不是首发根因

Xid 43 表示应用遇到软件诱发故障并终止，此时 GPU 通常仍健康。Xid 45 表示驱动正在清理被中止的应用通道；Ctrl-C、SIGKILL、GPU reset、DBE 或其他前序错误都可能触发它。

正确做法是向前查看同一秒及前后数分钟的日志：

```bash
sudo journalctl -k -b -o short-iso | grep -E 'NVRM: (GPU|Xid)'
```

- `13 → 43 → 45`：13 更可能是起点，43/45 是终止与清理。
- `48/94 → 45`：处理 ECC/contained error，不要围绕 45 换卡。
- A100 上若 45 单独出现，先采集 FM/SXid/bug-report；确认确为 FM 异常后，在平台维护流程内重启 Fabric Manager。不要在活动 fabric 上盲目重启 FM。

### 5.3 Xid 48、63、64、92、94、95：显存故障要看组合

显存错误最容易被错误地简化为“报 ECC 就换卡”。实际需要区分错误是否可纠正、是否被 containment、修复记录是否成功、是否有待生效的 remap，以及是否达到 RMA 阈值。

```bash
nvidia-smi -i <GPU-UUID> -q -d ECC,PAGE_RETIREMENT,ROW_REMAPPER
nvidia-smi -i <GPU-UUID> --query-retired-pages=\
gpu_uuid,retired_pages.address,retired_pages.cause --format=csv
```

不同组合的意义：

| 组合/状态 | 解释 | 处理 |
| --- | --- | --- |
| 单独 Xid 48 | 发生 UCE/DBE，但未看到成功退役/重映射记录 | Reset GPU，并运行 Field Diagnostic |
| 48 + 63 | UCE 后成功记录页退役或 row-remap | 停止新任务，排空后 reset，使修复生效 |
| 48 + 64 | UCE 后修复记录失败 | 立即隔离；先按 Recovery Action，再按平台 reset/reboot，持续则 FieldDiag/厂商 |
| 单独 63 | 记录成功的修复事件 | 通常无需立即动作；看 pending 和维护窗 |
| 64 | 修复记录失败 | 不能当作普通计数；先按 Recovery Action，再按平台 reset/reboot 并升级 |
| 92 | SBE 速率过高 | 采集趋势并运行 FieldDiag，不是立即换卡 |
| 94 | contained，局限于一个应用 | 只重启受影响应用；其他任务可继续，维护窗 reset |
| 95 | uncontained，影响多个应用 | 停止新任务并按 Recovery Action 恢复；无摘要时 Catalog 要求 reset，A100 非 MIG 指南要求 reboot |

Ampere 及以后 GPU 的 Row Remapper 字段需要重点看：

- `Pending: Yes`：记录已存在，但必须 reset GPU 才在硬件中生效。
- `Remapping Failure Occurred: Yes`：表示过去曾发生 remap 失败，属于历史粘性状态；进入隔离和 Field Diagnostic/RMA 评估，不能因 reset 成功而放行。
- `Bank Remap Availability`：看 Max/High/Partial/Low/None 等 bucketized bank count 分布，不能只看总 remap 数；该字段不提供每个 bank 的身份和精确余量。

较旧 GPU 的 Dynamic Page Retirement 则看 `Pending Page Blacklist`。Pending 为 Yes 时，退役页尚未在下一次驱动初始化中被排除，需在维护窗重新初始化 GPU、reset 或 reboot，并确认状态转为 No。

不要运行 `nvidia-smi --reset-ecc-errors=<TYPE>` 来“修复”故障，其中 `<TYPE>` 可取 `VOLATILE` 或 `AGGREGATE`（也可分别写为 `-p 0`、`-p 1`；Ampere 及以后不支持清 aggregate）。该命令只清计数，会破坏趋势证据，不会修好存储单元。

### 5.4 Xid 74 与 144–150：NVLink 错误必须定位到链路和对端

Xid 74 表示 GPU 到另一块 GPU 或 NVSwitch 的 NVLink 连接出现问题。它可能来自本地链路，也可能只是对端 GPU 先失败后产生的次生错误。

```bash
nvidia-smi topo -m
nvidia-smi nvlink -s -i <GPU-UUID>
nvidia-smi nvlink -e -i <GPU-UUID>

systemctl status nvidia-fabricmanager
journalctl -u nvidia-fabricmanager
```

采证前不得运行 `nvidia-smi nvlink -re`；它会清零受支持代际的错误计数，而且 NVLink 5 不支持该清零操作。

排障时必须保存：

- Xid 74 后的完整 **7 个十六进制字段**，不能只抄 `74`；
- 本地 GPU UUID、link ID、对端 BDF/设备、拓扑；
- 同时段的其他 Xid、SXid、Fabric Manager 日志；
- 错误计数在同一观察窗口内的增量，而不只是累计非零值。

同一链路反复出现 ECC/parity、SI 或恢复失败，经过连接检查、重插和复位仍复现时，才进一步区分 GPU、baseboard、NVSwitch 或连接组件并提交厂商。Blackwell 的 Xid 144–150 带 subcode、fatal/non-fatal、link、`IntrInfo`、`ErrorStatus` 等字段，必须使用对应驱动代际的 Xid Catalog 解码，不能套用 Xid 74 的简化流程。

### 5.5 Xid 79：GPU 不可达，不等于 GPU 本体必坏

Xid 79 表示驱动通过 PCIe 访问 GPU 时，设备已经不可达。常见根因包括：

- PCIe Root Port、switch、riser、retimer、连接器或插槽；
- GPU 本体；
- 辅助供电、背板或 PSU；
- 温度、机械接触；
- 驱动或系统问题。

应在重启前优先保存：

```bash
sudo journalctl -k -b -o short-iso | grep -E -i \
'NVRM|Xid|pcie|aer|pcieport|dpc|fatal|surprise|link down'

lspci -Dnn | grep -i nvidia
lspci -Dtv
sudo lspci -Dnnk -s <GPU-BDF>
sudo lspci -Dvv -s <GPU-BDF>
# 同样检查目标 GPU 的上游 bridge/root port
sudo lspci -Dvv -s <UPSTREAM-PORT-BDF>
```

这里的 `grep` 只是现场快速视图，不能替代第 6.2 节保存的未经筛选时间窗。

最新版 Catalog 的立即动作是 **重启裸机**。GPU 已经 off bus 时，反复尝试单卡 reset 通常没有意义。AER 可能记录在 GPU 的链路对端或 Root Port；endpoint 计数为零并不能证明链路健康。固件若未通过 ACPI `_OSC` 把 AER 控制权交给 OS，无内核 AER 日志也不能排除错误。常规采证不要使用 `setpci`、sysfs remove/reset/rescan 等写操作，也不要默认读取 `lspci -xxx/-xxxx` 的完整配置空间。恢复后要检查链路宽度/速率、AER、供电和温度，并通过换槽、换卡或替换 riser/retimer 判断故障是“随卡”还是“随系统路径”。只有证据随卡或诊断明确指向卡本体时，才进入 GPU RMA。

### 5.6 Xid 119/120：GSP 故障先恢复，再调查软件栈

Xid 119 是等待 GSP RPC 超时，Xid 120 是 GSP 错误。两者当前 Immediate Action 都是 reset GPU，Investigatory Action 都是调查软件。

保存以下信息：

- 119/120 完整 payload 和先后顺序；
- GPU driver、GSP firmware、VBIOS、系统固件版本；
- 最近是否升级/回退驱动或固件；
- 前序 Xid、bug-report、DCGM/Field Diagnostic 结果。

若 reset 无效，可执行节点 power cycle；power cycle 后仍复发，再按 GPU Debug Guidelines 提交支持。119/120 本身不是直接 RMA 码。

## 6. 标准化故障处理 SOP

### 6.1 阶段 A：告警、隔离与事件分级

建议按恢复影响分为四个等级；其中 P1 再分 GPU/节点复位与 IMEX 域恢复两条路径：

| 等级 | 典型条件 | 第一动作 |
| --- | --- | --- |
| P0：节点不可用 | Recovery=`Reboot`、Xid 79、GPU 无法枚举，或无 Recovery 摘要时 A100 非 MIG 的 Xid 95 | cordon/停止新调度，立即采证，排空并重启 |
| P1：需排空复位 | Recovery=`Reset`、`Drain P2P`、`Drain and Reset`，或 Catalog 要求 reset | 停止向目标 GPU/节点派新任务，排空后复位 |
| P1：域级恢复 | Recovery=`Recover IMEX Domain` | 停止域内新任务，隔离关联作业，按平台 IMEX 域 runbook 恢复 |
| P2：应用级 | 13/31/43/68/69、Xid 94 contained，Recovery=`None` | 重启受影响应用，保留其他健康任务 |
| P3：信息/伴随 | 单独 45、单独 63、154 | 向前找主因，按主因或动作摘要处理 |

自动化只能做初始隔离，不能仅按 `xid != 0` 一律 reboot。Xid 43 与 79 的影响完全不同，Xid 94 与 95 的边界也不同。

### 6.2 阶段 B：恢复前采集证据

先记录事件元数据：时间和时区、节点/机架/槽位、GPU UUID/BDF/序列号、Job/Pod/用户、应用/框架/CUDA/NCCL 版本、最近变更、复现频率、是否多节点同时发生。

```bash
# 1. 列出 boot，并先保存未经筛选的权威时间窗
sudo journalctl --list-boots
sudo journalctl -k -b --since '<start-time>' --until '<end-time>' \
  -o short-iso --no-pager

# 再生成辅助筛选视图（--grep 需要 systemd 237+）
sudo journalctl -k -b --since '<start-time>' --until '<end-time>' \
  --grep='NVRM|Xid|SXid|PCIe|AER|DPC|link down' \
  --case-sensitive=no -o short-iso --no-pager

# 若事件发生在上一次启动且 journal 使用持久化存储
sudo journalctl -k -b -1 -o short-iso --no-pager

# 2. 资产、恢复状态和进程
nvidia-smi -L
nvidia-smi --query-gpu=index,uuid,pci.bus_id,name,serial,driver_version \
  --format=csv
# R570+ 支持；旧驱动未知字段会使整条查询失败，因此单独执行
nvidia-smi --query-gpu=uuid,gpu_recovery_action --format=csv
nvidia-smi -q
nvidia-smi --query-compute-apps=pid,process_name,gpu_uuid --format=csv

# 3. 拓扑、显存和互联
nvidia-smi topo -m
nvidia-smi -q -d ECC,PAGE_RETIREMENT,ROW_REMAPPER
nvidia-smi nvlink -s
nvidia-smi nvlink -e

# 4. 恢复前采集 NVIDIA 支持包
sudo nvidia-bug-report.sh
```

旧版驱动如果不支持 `gpu_recovery_action`，用 `nvidia-smi -q` 查看；字段仍不存在时，查对应版本的 Xid Catalog。

从权限受控、空间充足的事件目录运行 `nvidia-bug-report.sh`；输出保存在当前目录，可能包含敏感系统、进程和配置数据，必须受控保存和传输。官方建议标准采集必要时最多允许约一小时。若确认挂住，保留已有不完整输出后先尝试 safe mode：

```bash
sudo nvidia-bug-report.sh --safe-mode
```

只有 NVIDIA/OEM 明确要求、处于维护窗口且接受系统挂死风险时，才使用 `sudo nvidia-bug-report.sh --safe-mode --extra-system-data`。

不要执行 `dmesg -C` 或 `dmesg -c`，它们会清除内核环形缓冲区；`dmesg -T` 在 suspend/resume 后的换算时间也可能不准。

HGX/NVSwitch 系统还要保存：

```bash
sudo journalctl -u nvidia-fabricmanager
sudo systemctl status nvidia-fabricmanager
sudo cp /var/log/fabricmanager.log <incident-directory>/
```

### 6.3 阶段 C：无侵入调查

在工作负载仍运行时，只做不会主动压测 GPU 的检查：

- 对齐应用、调度器、容器退出与第一条 Xid 的时间；
- 判断错误是单卡、单槽、单节点、同型号还是全局软件版本相关；
- 查看 PCIe AER、BMC 供电/温度、Fabric Manager/SXid；
- 查看事先已经启用的 DCGM health/时序指标。

不要在业务仍运行时启动 DCGM level 2/3。主动诊断会消耗 GPU、CPU、内存、功率和互联资源。

### 6.4 阶段 D：排空后运行 DCGM 主动诊断

先确认 DCGM 实际看到的 entity ID：

```bash
dcgmi discovery --list
dcgmi discovery --list --all
```

常用诊断：

```bash
# 快速软件部署检查
dcgmi diag --run 1 --entity-id gpu:<dcgm-id> --verbose --json

# 中等检查：memory + PCIe，通常约数分钟，依版本/平台而异
dcgmi diag --run 2 --entity-id gpu:<dcgm-id> --verbose --json

# 长硬件诊断；重复或疑似硬件故障时执行
dcgmi diag --run 3 --entity-id gpu:<dcgm-id> --verbose --json

# 定向复测
dcgmi diag --run pcie --entity-id gpu:<dcgm-id> \
  --iterations 3 --verbose --json
```

诊断注意事项：

- level 1 是快速部署检查，level 2 包含 memory/PCIe，level 3 是更长的硬件和压力测试；支持项依 GPU 类型和 DCGM 版本而异。
- 退出码 0 才表示请求的诊断完成且没有报告错误。`Skip`、插件缺失、无法启动或权限错误都不是 Pass。
- 真正执行测试的是 `nv-hostengine`/诊断服务账户；只给前端 `dcgmi` 加 `sudo` 不一定解决服务端权限。
- DCGM 不能修复硬件，也不能替代 NVIDIA Field Diagnostic。

### 6.5 阶段 E：执行最小必要恢复动作

GPU reset 前必须终止目标设备上的 CUDA、图形和监控客户端，包括可能持有设备句柄的其他 `nvidia-smi`、DCGM、Exporter、X server 等。`--query-compute-apps` 不覆盖所有图形或监控客户端，`lsof` 也可能因 glob、权限或错误重定向漏报；两者只能交叉辅助，不能单独作为放行依据。

```bash
nvidia-smi -i <GPU-UUID-or-PCI-BDF> -q -d PIDS
nvidia-smi --query-compute-apps=pid,process_name,gpu_uuid --format=csv
sudo lsof /dev/nvidia* 2>/dev/null

# 优先用 UUID 或 PCI BDF，避免 index 漂移
sudo nvidia-smi --gpu-reset -i <GPU-UUID-or-PCI-BDF>
```

不要省略 `-i`，除非确实要 reset 全部 GPU。未指定目标时，`nvidia-smi --gpu-reset` 会作用于所有 GPU。

NVIDIA 明确说明 GPU reset 不保证在所有场景成功，也不应成为生产环境的无条件恢复手段；板上部分组件可能没有回到初始状态。命令失败，或 reset 后任一目标 GPU 仍不可见、不健康时，应保持隔离并对节点执行 power cycle；随后再次采证、验收，持续异常则升级厂商。MIG-enabled vGPU guest 不支持该 reset；其他 VM 也必须服从 hypervisor 权限和第 8.3 节的边界。

如果 Recovery Action 是 Reboot：

1. 确认 bug-report 与关键日志已经保存；
2. 排空节点；
3. 执行操作系统 warm reboot；
4. 如果 GPU 仍不可见或 reboot 后健康检查失败，再做整机 power cycle；
5. 持续复发则保持隔离并升级厂商。

### 6.6 阶段 F：恢复后验收

至少完成以下检查：

```bash
nvidia-smi -L
nvidia-smi -q
nvidia-smi topo -m
nvidia-smi nvlink -s
dcgmi discovery --list
dcgmi diag --run 1 --entity-id gpu:<dcgm-id> --verbose
dcgmi diag --run 2 --entity-id gpu:<dcgm-id> \
  --timeout <site-timeout-seconds> --verbose --json
```

验收门槛：

- GPU 数量、UUID、BDF 和 PCIe 最大链路宽度/速率符合资产基线；当前链路值在空闲时可能因电源管理降低，应在定义好的负载或诊断条件下比较；
- GPU Recovery Action 回到 `None`；
- `Pending Page Blacklist`、`Row Remapper Pending` 已达到本次维护目标；若 `Remapping Failure Occurred=Yes`，保持隔离并进入 Field Diagnostic/OEM RMA 流程，不能要求历史粘性 flag 在 reset 后清零；累计 ECC、retired page 和 remap 计数也可能持久存在；
- 适用的 NVSwitch/NVLink 平台上，Fabric Manager/NVLSM 正常、fabric healthy、预期链路为 Active；
- DCGM level 1 和排空后的 level 2 真正 Pass；显式实体仅验目标 GPU，只有整节点已完全排空时才可省略 `--entity-id` 做全节点诊断；
- 已知良好的 CUDA/NCCL smoke test 通过；
- 从本次 reset/reboot 时间点起的观察窗口内没有新 Xid、SXid，且没有归因到目标 PCIe 路径的新 fatal/non-fatal AER；correctable AER 速率处于资产基线内。

全部通过后才解除隔离。单纯“`nvidia-smi` 有输出”不构成验收。

## 7. Kubernetes / GPU Operator 场景

Xid 来自宿主机内核驱动。业务 Pod 退出、Device Plugin 重启或 GPU 重新出现在资源列表中，都不表示物理故障已经恢复。

### 7.1 标准处理顺序

```bash
# 仅在 Recovery Action、Xid 或未知风险要求隔离时执行
kubectl cordon <node>

# 保存节点上的 GPU 工作负载与事件
kubectl get pods -A -o wide --field-selector spec.nodeName=<node>
kubectl get events -A --sort-by=.lastTimestamp

# 查看 Device Plugin 日志；实际 Pod 名和容器名以集群为准
kubectl logs -n gpu-operator <device-plugin-pod> \
  -c nvidia-device-plugin

# 证据保存后：全节点 reboot 或无法可靠做 GPU→Pod 映射时，排空并等待成功
kubectl drain <node> \
  --ignore-daemonsets \
  --timeout=<site-timeout>
```

`cordon` 只阻止普通新调度，不会驱逐现有 Pod；需要全节点恢复时，`drain` 成功前不得操作节点。`--ignore-daemonsets` 也只是忽略、不会停止 DaemonSet，因此 Device Plugin、DCGM Exporter 等仍须在受控维护流程中释放 GPU。不要把 `--force`、`--delete-emptydir-data` 或 `--disable-eviction` 写成默认参数：它们可能删除无控制器 Pod、本地数据，或绕过 PDB。

然后：

1. 从宿主机 journal、`nvidia-smi` 和 `nvidia-bug-report.sh` 采集主证据；容器内可能只看见被注入的设备。
2. 另运行 GPU Operator `must-gather` 收集 Operator、operand、manifest 与集群日志。它不能替代宿主机 `nvidia-bug-report.sh`。
3. 按 Recovery Action 决定 checkpoint、Eviction、drain、reset 或 reboot：`Reset` 只有在能可靠建立 GPU UUID 到 Pod 的映射时才局部排空目标 GPU；`Reboot` 必须排空整个节点。无法可靠映射时，不要猜，按整节点排空处理。排空应尊重 PodDisruptionBudget、termination grace period 和业务 checkpoint。
4. 如果 GPU reset 失败并升级为 reboot，要补做全节点排空；如果改为 reset 另一块 GPU，要先排空使用那块 GPU 的所有 Pod。
5. reset 前确认目标范围内的 GPU Pod，以及宿主侧 DCGM Exporter、Device Plugin、监控服务等都已释放设备句柄；必要时通过受控维护流程暂停和恢复相关 operand，不要临时手删 DaemonSet。
6. 不要在业务 Pod 中直接执行 GPU reset。
7. 修复后等待 GPU Operator operand Ready、Device Plugin 重新注册，核对普通 GPU 或 MIG 资源，再运行 smoke test。

GPU Operator 官方 `must-gather` 可能采集整个集群、耗时较长，输出也可能包含敏感配置；只应由获授权人员用于人工诊断。生产环境应把 URL 固定到已验证的 release/tag/commit，从可信变更记录取得预期哈希并审阅脚本，不能跟随 `main` 分支或直接纳入无人值守自动化：

```bash
curl -fL -o must-gather.sh \
  'https://raw.githubusercontent.com/NVIDIA/gpu-operator/<validated-ref>/hack/must-gather.sh'
printf '%s  %s\n' '<expected-sha256>' must-gather.sh | sha256sum -c -
chmod +x must-gather.sh
./must-gather.sh
```

```bash
kubectl get node <node> \
  -o 'custom-columns=NAME:.metadata.name,CAPACITY:.status.capacity.nvidia\.com/gpu,ALLOCATABLE:.status.allocatable.nvidia\.com/gpu'
```

MIG `mixed` 策略还会发布 `nvidia.com/mig-<profile>` 资源，上述物理 GPU 两列不足以完成 MIG 验收；应检查完整的 `.status.capacity`、`.status.allocatable` 或 `kubectl describe node <node>`，与预期资源基线比较。

只有宿主机验收通过、GPU Operator operands Ready、资源重新注册、CUDA/NCCL smoke test 通过且观察窗口内无新错误后，才执行：

```bash
kubectl uncordon <node>
```

这一路径可概括为：`quarantine/cordon → drain → 收集日志 → remediation → 恢复 Operator 服务 → 健康检查 → uncordon`。`drain-failed` 或 `remediation-failed` 必须转人工，不得自动解除隔离。NVIDIA NVSentinel 的 Node Drainer 和 Fault Remediation 实现了同类状态机，可作为大规模集群自动化参考。

Device Plugin 会根据 NVML 事件将某些 GPU 标为 unhealthy，并从可分配资源中移除。重启插件最多刷新其发布状态，不能修复 ECC、PCIe、NVLink 或 GPU 硬件故障。

### 7.2 监控建议

DCGM Exporter 可将 GPU 指标暴露给 Prometheus，Xid 指标通常显示为 `DCGM_FI_DEV_XID_ERRORS`。应至少同时采集：

- Xid 与 GPU Recovery Action；
- ECC SBE/DBE；
- retired pages、row-remap total/pending/failed；
- PCIe replay；
- NVLink CRC/replay/recovery；
- GPU 温度、功率和时钟事件；
- GPU UUID、节点、Pod、MIG GI/CI 等标签。

告警应按 Xid 和 Recovery Action 分流。不要用一个“Xid 非零即 reboot”的规则覆盖所有错误，也不要把 legacy gauge `DCGM_FI_DEV_XID_ERRORS` 当累计次数：它的值是具体 Xid 编号，不能仅以“持续非零”建告警。新版可选的 `DCGM_EXP_XID_ERRORS_COUNT` 统计窗口内 sample 数，不是唯一事故数；`DCGM_EXP_XID_ERRORS_TOTAL` 累计 exporter 启动后观察到的非零记录，exporter 重启会归零。Recovery Action、row-remap 等字段也不保证在默认 collector 启用，必须核对实际 `/metrics`、驱动/DCGM 支持和 collector 配置。

## 8. MIG、NVLink/NVSwitch 与虚拟化的复位边界

### 8.1 MIG

Xid 中的 `GPU-I:<GI>` 可以帮助定位受影响的 GPU Instance，但 reset 通常仍以物理 GPU 为边界。

- Xid 94：只重启命中的应用；其他实例可继续运行，维护窗 reset。
- Xid 95 或 `Drain and Reset`：禁止再分配整张物理 GPU，排空该卡上的所有 GI/CI 后再 reset。
- GI/CI（MIG devices）在 GPU 或系统 reset 后不持久，必须按期望配置重新创建并核对；可由 GPU Operator MIG Manager 或 `mig-parted` 自动恢复。
- DCGM、NVSM、Exporter 等监控句柄也可能阻止 reset。

MIG mode 本身还存在代际差异：Ampere 启用 MIG 通常需要 GPU reset，且 MIG mode 跨 reboot 持久；Hopper 及以后启用 MIG 不再需要 reset，但 MIG mode 只在驱动驻留期间持久，驱动卸载/重载或系统重启后需重新启用。Kubernetes 中还应确认 `nvidia.com/mig.config.state=success`、预期 profile/count 标签与资源数正确，并用 `nvidia-smi -L` 核对 MIG UUID。

### 8.2 NVLink / NVSwitch

| 平台 | 裸机 reset 能力 |
| --- | --- |
| Ampere+，GPU 直连 NVLink | 可单卡 reset |
| pre-Ampere，NVLink 相连 | 所有 peer GPU 需在同一命令中 reset |
| Ampere + NVSwitch，Fabric Manager 运行 | 可单卡 reset，FM 协助重置对应 switch link |
| Ampere + NVSwitch，Fabric Manager 未运行 | 不能单卡 reset；同一命令必须包含所有 NVLink peer-connected GPU，并按 FM 指南重置相关 GPU/NVSwitch |
| Hopper+ + NVSwitch | 裸机可单卡 reset，不再依赖 FM 协助 reset |

Hopper+ 的 reset 不依赖 FM，不代表正常运行无需 fabric 服务。reset 后仍要检查 FM/NVLSM、fabric registration、SXid 和所有相关 GPU/NVSwitch 链路。Shared NVSwitch/vGPU 等模式应按平台要求使用与驱动匹配的 Fabric Manager/FM SDK。

可进一步使用 DCGM 定位实体和链路；计数应比较固定工作负载窗口内的增量，累计非零本身不代表本次仍在故障：

```bash
dcgmi nvlink --link-status --show-entity-ids
dcgmi nvlink --errors --gpuid <dcgm-id> --json
```

### 8.3 虚拟化

GPU reset 能否在 VM 中使用取决于 GPU 代际、直通/vGPU 模式和 hypervisor 权限。Ampere+ direct-NVLink 的设备全部在同一 VM 时不支持 GPU reset，应重启 VM；Ampere + NVSwitch 全直通同一 VM 也应重启 VM。Hopper+ NVSwitch 是否可 reset 取决于 hypervisor 权限，不允许时重启 VM。MIG-enabled vGPU guest 不支持 GPU reset。不要把裸机 SOP 原样套进 VM。

## 9. 什么时候升级软件，什么时候升级支持/RMA

### 9.1 驱动/固件升级不是通用修复

只有以下情况才把升级作为有依据的处理：

- Catalog 明确给出 `UPDATE_SWFW`，例如某些 vGPU 启动不兼容；
- NVIDIA Release Notes 命中已知问题；
- 最小复现、回退/升级对比或支持组织已经确认驱动/固件缺陷；
- 当前组合不在 GPU、驱动、Fabric Manager、DCGM、OS 或 hypervisor 的支持矩阵内。

升级后要同步验证驱动、GSP/VBIOS、Fabric Manager/NVLSM、DCGM 和业务 CUDA/NCCL 基线。不要无证据地用“升到最新版”覆盖硬件隔离流程。

### 9.2 立即升级厂商支持的条件

- Xid 79、设备无法枚举或重启后仍不可见；
- 严重 Xid 在同一已知良好负载、同一 UUID/BDF 上重复；
- reset/reboot/power cycle 后短时间复发；
- DCGM 报硬件、显存、PCIe 或互联失败；
- row-remap failure、InfoROM 问题或修复资源耗尽；
- NVLink 同一链路重复报错，重插/复位无效；
- 无法采集、无法 reset，或恢复动作长期不回到 `None`。

厂商工单至少附：`nvidia-bug-report.log.gz`、完整内核日志、DCGM 日志、HGX 的 Fabric Manager/SXid、版本与拓扑、复现步骤/频率、应用信息、已做操作，以及故障是否随卡/随槽的隔离结果。

### 9.3 RMA 的正确判据

NVIDIA Field Diagnostic 是判断 GPU 健康的权威综合工具，通常是开始 RMA 前的必要条件。应联系整机厂商获取与平台匹配的工具和流程。

显存 RMA 的官方边界：

- **Ampere+ DRAM/HBM row remap**：`Row Remapping Failure` flag 置位，并由 Field Diagnostic 验证。该 flag 可由三类情况触发：某个 bank 已有 8 个 UCE remapped row 后再次需要 UCE remap；UCE 再次命中已经 remap 的 row；累计达到 512 次 UCE remap。对支持该能力的 Blackwell 产品，同一 bank 已完成两次 row remap 后，第三次 UCE remap attempt 会在有 spare channel 时尝试 HBM channel repair；成功则硬件恢复，否则继续 remap 直至 failure flag 置位。
- **SRAM UCE**：达到 SRAM Threshold Exceeded 条件，并由 Field Diagnostic 判定。官方阈值包括同一 address bank 中 parity-protected SRAM 超过 4 个 UCE unique count，或 SECDED-protected SRAM 超过 2 个。
- **旧动态页退役机制**：对适用的 legacy 产品，累计 60 个或更多 retired pages 达到 RMA 评估门槛；累计至少 15 页且仍以每周至少 1 个新页增长，可提前评估；64 页会使 Field Diagnostic 失败。不要把这些旧页退役数字套到 Ampere+ row-remap 产品。

达到阈值只是 RMA eligible/评估门槛，不代表自动批准换卡。应在 ECC enabled 状态下运行厂商指定的 Field Diagnostic，并提交 `nvidia-bug-report.log.gz`、`fieldiag.log`、完整日志、复现频率、辅助供电/插接检查，以及用已知良卡或换系统得到的“故障随卡/随系统”证据。Field Diagnostic Pass 是硬件健康的重要指示；若问题仍稳定随卡，也应提交隔离证据供 NVIDIA/厂商评估测试覆盖。

因此以下判断都是错误的：

- “出现一次 Xid 48 就换卡”；
- “Xid 63 代表显存快坏了”；
- “Xid 79 一定是 GPU 本体坏”；
- “DCGM Pass，所以绝不可能是硬件”；
- “reset 后能训练，所以不需要留证和调查”。

## 10. 事件记录与关闭模板

每个 Xid 事件建议至少记录以下字段：

| 类别 | 字段 |
| --- | --- |
| 事件 | 工单号、开始/结束时间、时区、等级、影响任务数 |
| 资产 | 集群、节点、机架、机箱/槽位、GPU 型号/序列号/UUID/BDF |
| 软件 | OS、kernel、driver、CUDA、GSP/VBIOS、FM、DCGM、容器运行时、GPU Operator |
| 业务 | Job/Pod、用户、框架、模型、NCCL、是否可复现 |
| 日志 | 第一条 Xid、完整 payload、伴随 Xid/SXid/AER、Recovery Action |
| 健康 | ECC、retire/remap、PCIe、NVLink、温度、功率、DCGM 结果 |
| 操作 | cordon/drain、应用重启、reset/reboot/power cycle、部件互换 |
| 结论 | 根因层级、是否随卡/随槽、厂商判定、RMA 结果 |
| 验收 | Recovery=None、DCGM、CUDA/NCCL smoke、观察窗口、解除隔离时间 |

关闭事件前必须回答三个不同的问题：

1. **服务是否恢复？**——由 Recovery Action 和恢复验收回答。
2. **故障为什么发生？**——由时间线、复现、软件/链路/硬件隔离回答。
3. **怎样防止复发？**——由代码修复、版本治理、机械/供电整改、监控阈值或 RMA 回答。

## 11. 常见误区汇总

- Xid 编号是排障入口，不是根因标签。
- 第一条错误通常比最后一条更接近根因；43/45/154 经常是结果或摘要。
- 13/31 多数先查应用，但固定落在同一物理单元的重复模式必须排硬件。
- 63 是成功记录 remap/retire，64 才是记录失败。
- 74 可能由远端 GPU/NVSwitch 先故障引起，必须看 link、对端、SXid 和完整 payload。
- 79 是“PCIe 上不可达”，不是“已证明 GPU 卡坏”。
- 94 可以只杀受影响应用；95 需要恢复动作，应优先服从同次 Recovery Action；无摘要时当前 Catalog 要求 reset，A100 非 MIG 指南要求节点 reboot。H100、B100、GB200 等平台不要套用该 A100 特例。
- Xid 154/GPU Recovery Action 决定恢复方式，原始 Xid 决定调查方向。
- GPU reset 前必须释放所有客户端；reset 后必须验健康。
- 清 ECC 计数、重启 Device Plugin 或重装驱动都不能修复物理显存、PCIe 或 NVLink 故障。
- RMA 要看 Field Diagnostic、阈值和隔离证据，不能只看一次 Xid。

## 12. NVIDIA 官方资料

- [Xid Errors：概念与使用边界](https://docs.nvidia.com/deploy/xid-errors/introduction.html)
- [Working with Xid Errors：日志、nvidia-smi、DCGM、bug-report](https://docs.nvidia.com/deploy/xid-errors/working-with-xid-errors.html)
- [最新 Xid Catalog 与 Immediate/Investigatory Action](https://docs.nvidia.com/deploy/xid-errors/analyzing-xid-catalog.html)
- [NVML GPU Recovery Action 枚举（含 Recover IMEX Domain）](https://docs.nvidia.com/deploy/nvml-api/group__nvmlVgpuStructs.html)
- [GPU Debug Guidelines：节点分诊、复位、DCGM、Field Diagnostic](https://docs.nvidia.com/deploy/gpu-debug-guidelines/index.html)
- [`nvidia-smi` 官方文档：GPU Recovery Action 与 reset 限制](https://docs.nvidia.com/deploy/nvidia-smi/index.html)
- [DCGM Diagnostics 命令参考](https://docs.nvidia.com/datacenter/dcgm/latest/reference/command-line-reference/dcgmi/dcgmi-diag.html)
- [DCGM Entities and Groups：显式实体与 inactive GPU](https://docs.nvidia.com/datacenter/dcgm/latest/learn/core-services/entities-and-groups.html)
- [DCGM Field Identifiers](https://docs.nvidia.com/datacenter/dcgm/latest/dcgm-api/dcgm-api-field-ids.html)
- [DCGM Exporter 与 Kubernetes/MIG 指标](https://docs.nvidia.com/datacenter/cloud-native/gpu-telemetry/latest/dcgm-exporter.html)
- [DCGM Exporter 指标语义（含 Xid window/total）](https://docs.nvidia.com/datacenter/dcgm/latest/reference/dcgm-exporter-metrics.html)
- [GPU Memory Error Management：用户可见统计与 Xid 对照](https://docs.nvidia.com/deploy/a100-gpu-mem-error-mgmt/latest/user-visible-statistics.html)
- [GPU Memory Error Management：RMA Policy](https://docs.nvidia.com/deploy/a100-gpu-mem-error-mgmt/latest/rma-policy-thresholds-for-row-remapping.html)
- [Dynamic Page Retirement：旧架构页退役与 RMA 门槛](https://docs.nvidia.com/deploy/dynamic-page-retirement/index.html)
- [NVIDIA RMA Process](https://docs.nvidia.com/deploy/rma-process/index.html)
- [Fabric Manager User Guide：NVSwitch/SXid/平台复位边界](https://docs.nvidia.com/datacenter/tesla/fabric-manager-user-guide/index.html)
- [GPU Operator Troubleshooting](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/troubleshooting.html)
- [MIG User Guide：MIG mode 与 GI/CI 持久性](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/getting-started-with-mig.html)
- [GPU Operator with MIG](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-operator-mig.html)
- [DCGM NVLink 命令参考](https://docs.nvidia.com/datacenter/dcgm/latest/reference/command-line-reference/dcgmi/dcgmi-nvlink.html)
- [NVSentinel Node Drainer](https://docs.nvidia.com/nvsentinel/components/node-drainer/)
- [NVSentinel Fault Remediation](https://docs.nvidia.com/nvsentinel/components/fault-remediation/)
- [NVIDIA IMEX Service：连接、恢复 quorum 与清理](https://docs.nvidia.com/multi-node-nvlink-systems/imex-guide/connections.html)
- [Kubernetes：安全排空节点](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/)
- [Compute Sanitizer 命令与退出码](https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html)
- [Linux PCIe AER 指南](https://docs.kernel.org/next/PCI/pcieaer-howto.html)

> 本文整理日期：2026-08-13。Xid Catalog 会随新 GPU、驱动和恢复机制更新；生产 SOP 应保存本文框架，但在处置时重新核对当前 Catalog、平台支持矩阵和整机厂商流程。
