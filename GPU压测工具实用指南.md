# GPU 压测工具实用指南

GPU 验收需要分别验证硬件健康、持续负载稳定性、数据搬运和集群通信。GPU 利用率达到 100%，并不代表这些项目全部合格。

本文以 Ubuntu 22.04/24.04、x86_64、裸机 NVIDIA GPU 服务器为例。命令按官方资料整理，其中 gpu-burn 源码编译步骤已由作者在 A800 上验证，其余步骤未在本文环境进行 GPU 实机测试；版本变化时以工具的 `--help` / `-h` 为准。正式压测请在 GPU 空闲时执行。

## 1. 工具怎么选

| 工具 | 主要用途 | 重点观察 |
|---|---|---|
| DCGM diag | 综合诊断：环境、显存、计算、PCIe/P2P、功耗 | 各项结果、错误详情、实际执行项目 |
| gpu-burn | 持续矩阵计算，验证负载下的稳定性 | errors、GFLOP/s；配合监控温度、功耗、降频 |
| nvbandwidth | 主机↔GPU、GPU↔GPU 等数据搬运测试 | GB/s、GPU 对之间的带宽矩阵、方向及并发差异 |
| nccl-tests | 单机多卡、多机集合通信性能与正确性 | time、algbw、busbw、#wrong |
| bandwidthTest | 旧版 CUDA 基础拷贝样例 | H2D、D2H、同卡 D2D 带宽 |
| Field Diagnostics | 厂商支持流程中的深入硬件诊断 | 报告与错误码；具体流程由 NVIDIA/OEM 指导 |

建议顺序：**DCGM → gpu-burn → nvbandwidth → 单机 nccl-tests → 多机 nccl-tests**。需要深入排查时追加 DCGM Level 4，必要时进入厂商 Field Diagnostics 流程。

## 2. 安装前的准备

```bash
nvidia-smi                 # 确认驱动和 GPU 可见
nvcc --version             # 确认 CUDA Toolkit 编译器
cmake --version            # nvbandwidth 要求至少 3.20

sudo apt update
sudo apt install -y git build-essential cmake wget
mkdir -p "$HOME/gpu-tools"
```

`nvidia-smi` 显示的 CUDA Version 是驱动支持的 CUDA 版本，不代表已安装对应 Toolkit。编译工具还需要 `nvcc`；以下源码示例假定 CUDA 位于 `/usr/local/cuda`，否则替换路径。

DCGM 和 NCCL 使用 NVIDIA 软件源。若尚未配置，可在上述 Ubuntu x86_64 系统执行：

```bash
. /etc/os-release
CUDA_REPO_DIST="ubuntu${VERSION_ID//./}"
wget "https://developer.download.nvidia.com/compute/cuda/repos/${CUDA_REPO_DIST}/x86_64/cuda-keyring_1.1-1_all.deb"
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
```

驱动或 Toolkit 缺失时，先按 [CUDA Linux 安装指南](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/)选择匹配版本。NVSwitch 服务器还需按机型配置相应 Fabric Manager 等组件。

## 3. DCGM：综合健康诊断

### 干什么

`dcgmi` 是 DCGM 的命令行接口。它既能发现设备、监控指标，也能通过 `diag` 主动诊断。

| 级别 | 主要检查范围 | 典型用途 |
|---|---|---|
| Level 1 | 软件库、设备访问等基础环境 | 快速确认环境就绪 |
| Level 2 | 增加显存、PCIe/P2P 检查 | 初步故障定位 |
| Level 3 | 增加计算诊断、显存带宽、目标计算负载和目标功耗 | 交付验收、深入排查 |
| Level 4 | 增加 Memtest 显存模式测试、Pulse Test 脉冲负载 | 排查显存隐患和负载骤变问题 |

高级别包含前一级。具体项目取决于版本、GPU 和插件，三级诊断不能代替数小时的持续烤机。非数据中心 GPU 对高级别诊断的支持有限。

### 怎么安装

以下为首次安装 DCGM 4、CUDA 12 对应包的例子：

```bash
sudo apt install -y --install-recommends datacenter-gpu-manager-4-cuda12
sudo systemctl enable --now nvidia-dcgm
dcgmi discovery -l
```

`cuda12` / `cuda13` 后缀按驱动支持情况和 GPU 架构选择，而非只看 `nvcc`。例如部分较老架构即使使用支持 CUDA 13 的驱动，仍应采用 cuda12 包。已有旧 DCGM 时，按官方升级说明处理包冲突。

### 怎么用、看哪些参数

```bash
dcgmi diag -r 1
dcgmi diag -r 3
dcgmi diag -r 4
dcgmi diag -r memory             # 单独检查显存
dcgmi diag -r pcie               # 单独检查 PCIe/P2P
dcgmi diag -r 3 -j > dcgm.json   # 保存 JSON 结果
```

| 参数 | 意义 |
|---|---|
| `-r` | 选择 1–4 级或命名测试，例如 `memory`、`pcie` |
| `-p` | 覆盖某项测试参数，如 `targeted_power.test_duration=300` |
| `-j` | JSON 输出，便于留档和自动化 |
| `-v` | 详细输出 |
| `--entity-id gpu:0` | 新版指定 GPU 0；旧版常用 `-i 0`，按本机帮助确认 |

结果重点看 **Pass / Fail / Warning / Skip** 及其原因。Skip 表示未执行，可能与硬件支持、依赖、配置或前置失败有关，不能直接推断 GPU 损坏。Fail 后继续定位具体 GPU、测试项目和错误，而非只看总状态。

参考：[DCGM 安装](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/getting-started.html)、[诊断命令](https://docs.nvidia.com/datacenter/dcgm/latest/reference/command-line-reference/dcgmi/dcgmi-diag.html)。

## 4. gpu-burn：持续烤机

### 干什么

持续运行矩阵计算并校验结果，用于发现长时间负载下的计算错误。多卡一起运行也能给整机供电与散热施加压力，但不验证卡间通信，也不是覆盖所有显存故障模式的专用测试。

### 怎么安装、怎么用

以下源码编译步骤已在 A800 上验证。前提是已安装 CUDA Toolkit，`nvcc` 可用；以下安装依赖的命令以 root 用户执行，普通用户需加 `sudo`。

```bash
apt update
apt install -y git gcc g++ make

cd "$HOME/gpu-tools"
git clone https://github.com/wilicc/gpu-burn.git
cd gpu-burn

# 编译，指定 A800 架构 compute_80
make COMPUTE=80

# 查看帮助，验证编译产物可运行
./gpu_burn -h
```

编译完成后，在 gpu-burn 目录运行：

```bash
./gpu_burn -l
./gpu_burn 60             # 先运行 60 秒验证
./gpu_burn 3600           # 持续 1 小时
./gpu_burn -tc 3600       # 尝试使用 Tensor Core
./gpu_burn -i 0 -m 80% 600 # GPU 0，使用可用显存的 80%，运行 600 秒
```

`COMPUTE=80` 对应这里的 A800 编译示例；其他 GPU 应按实际架构及 Toolkit 支持情况调整。CUDA 不在默认路径时，可追加 `CUDAPATH=/实际/CUDA/路径`。

| 参数 | 意义 |
|---|---|
| 最后一个数字 | 运行秒数 |
| `-i N` | 仅测试 GPU N |
| `-m N%` / `-m X` | 使用可用显存的百分比 / 指定 MB |
| `-tc` | 尝试使用 Tensor Core |
| `-d` | 使用双精度计算 |
| `-l` | 列出 GPU |
| `-h` | 显示帮助 |

重点看 **errors 是否为 0、各卡 GFLOP/s 是否异常偏低、是否中途失败**。同时观察温度、功耗和时钟；吞吐只能在相同精度、参数和硬件条件下比较。达到 100% 利用率不等于达到整机最大功耗。

参考：[gpu-burn](https://github.com/wilicc/gpu-burn)。

## 5. nvbandwidth：数据搬运和互联带宽

### 干什么

测量多种内存拷贝模式。H2D 是主机到 GPU，D2H 是 GPU 到主机；GPU 对之间的测试可反映 PCIe、NVLink/NVSwitch 路径表现。**不能把所有 D2D 都理解成同一 GPU 内部的显存拷贝**，要看具体用例和矩阵标签。

CE 使用复制引擎，SM 使用计算内核搬运。两者的性能可能不同；CE 不保证一定达到链路上限，SM 也不能直接等同于真实业务性能。

### 怎么安装、怎么用

```bash
cd "$HOME/gpu-tools"
git clone https://github.com/NVIDIA/nvbandwidth.git
cd nvbandwidth
cmake -S . -B build -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc
cmake --build build -j"$(nproc)"

./build/nvbandwidth -h
./build/nvbandwidth -l

# H2D、D2H 分别测试，并非同时双向传输
./build/nvbandwidth -t host_to_device_memcpy_ce device_to_host_memcpy_ce

# GPU 间通过 CE 写入拷贝，输出带宽矩阵
./build/nvbandwidth -t device_to_device_memcpy_write_ce -b 512 -i 10
```

| 参数 | 意义 |
|---|---|
| `-l` | 列出本版本可用用例 |
| `-t` | 指定用例名称或编号；当前版本支持空格分隔多个用例 |
| `-b` | 拷贝缓冲区大小，单位 MiB |
| `-i` | 采样次数；当前版本默认用中位数汇总 |
| `-v` | 详细输出 |
| `--format json` | 当前版本 JSON 输出；旧版本参数可能不同 |
| `-s` | 跳过数据校验；验收时通常不要开启 |

重点看 **GB/s、同类拓扑下各 GPU 对是否明显偏慢、方向是否异常不对称、校验是否失败**。单向与双向汇总值不能直接比较，双向也不保证恰好是单向两倍。测试之间保持相同的缓冲区、拷贝方式和 CPU/NUMA 条件。

参考：[nvbandwidth](https://github.com/NVIDIA/nvbandwidth)。

## 6. nccl-tests：单机、多机通信

### 干什么

测试 AllReduce、AllGather、ReduceScatter 等通信操作的性能与正确性。它更接近分布式训练的通信环节，但不是完整训练性能测试。

### 怎么安装

先查询 NCCL 包版本，选择与 CUDA Toolkit 匹配的条目，且 `libnccl2`、`libnccl-dev` 使用相同版本：

```bash
apt-cache madison libnccl2 libnccl-dev

# 仅在默认候选版本匹配本机 CUDA 时直接安装
sudo apt install -y libnccl2 libnccl-dev
# 需锁定版本时使用：sudo apt install libnccl2='<版本>' libnccl-dev='<相同版本>'

cd "$HOME/gpu-tools"
git clone https://github.com/NVIDIA/nccl-tests.git
cd nccl-tests
make -j"$(nproc)" CUDA_HOME=/usr/local/cuda
```

NCCL 安装在非系统路径时，增加 `NCCL_HOME=/实际路径`。源码版本也应与所装 NCCL 兼容，正式验收需记录 commit 和库版本。

### 怎么用、看哪些参数

```bash
cd "$HOME/gpu-tools/nccl-tests"
# 单机 8 卡；按实际卡数修改 -g
./build/all_reduce_perf -b 8 -e 128M -f 2 -g 8 -w 5 -n 20 -c 1
./build/all_gather_perf -b 8 -e 128M -f 2 -g 8
./build/reduce_scatter_perf -b 8 -e 128M -f 2 -g 8
```

| 参数 | 意义 |
|---|---|
| `-b` / `-e` | 最小 / 最大消息大小，`M` 表示 MiB |
| `-f 2` | 每轮消息大小翻倍 |
| `-g` | 每线程使用 GPU 数量，不是 GPU 编号 |
| `-t` | 每进程线程数，通常保持 1 |
| `-w` / `-n` | 预热次数 / 正式计时次数 |
| `-c 1` | 进行结果正确性检查 |
| `-d` / `-o` | 数据类型 / 归约操作，例如 float / sum |

| 输出 | 怎么看 |
|---|---|
| `time` | 操作耗时，通常为微秒；小消息尤其关注延迟 |
| `algbw` | 算法带宽；结合消息大小和操作语义比较 |
| `busbw` | 按操作通信量折算的带宽，不是某根链路或网口的直接测速值 |
| `#wrong` | 正确性检查错误数，应为 0 |
| in-place / out-of-place | 输入输出是否复用缓冲区，两种结果分别比较 |

### 多机测试

需要先编译 MPI 版本。以下路径适用于 Ubuntu x86_64 的 Open MPI 包：

```bash
sudo apt install -y openmpi-bin libopenmpi-dev
cd "$HOME/gpu-tools/nccl-tests"
make clean
make -j"$(nproc)" MPI=1 MPI_HOME=/usr/lib/x86_64-linux-gnu/openmpi \
  CUDA_HOME=/usr/local/cuda

# 示例：两台服务器，各 8 卡，一进程一卡
mpirun -np 16 --host node1:8,node2:8 --map-by ppr:8:node \
  -x NCCL_DEBUG=INFO \
  "$HOME/gpu-tools/nccl-tests/build/all_reduce_perf" \
  -b 8 -e 128M -f 2 -g 1 -w 5 -n 20 -c 1
```

将 node1/node2 替换为真实主机名。两端需有可启动的 MPI 环境、同路径二进制及兼容的 CUDA/NCCL 库；IB/RoCE 测试还需就绪的 RDMA 驱动与网络。检查 NCCL 日志中的实际传输后端，不能因程序跑通就认定使用了 RDMA。多机性能下降时，结合拓扑、网卡选择和网络状态定位。

参考：[NCCL 安装](https://docs.nvidia.com/deeplearning/nccl/install-guide/index.html)、[nccl-tests](https://github.com/NVIDIA/nccl-tests)、[输出指标](https://github.com/NVIDIA/nccl-tests/blob/master/doc/PERFORMANCE.md)。

## 7. bandwidthTest：旧环境参考

CUDA Samples 12.9 已移除此样例，新环境使用 nvbandwidth。需要复现旧测试时，可获取 v12.8 源码，并在兼容 Toolkit 上单独编译：

```bash
cd "$HOME/gpu-tools"
git clone --depth 1 --branch v12.8 https://github.com/NVIDIA/cuda-samples.git cuda-samples-v12.8
cd cuda-samples-v12.8
/usr/local/cuda/bin/nvcc -O2 -I Common \
  Samples/1_Utilities/bandwidthTest/bandwidthTest.cu -o bandwidthTest

./bandwidthTest --device=0 --memory=pinned --mode=quick
./bandwidthTest --device=0 --memory=pinned --htod
./bandwidthTest --device=0 --memory=pinned --dtoh
./bandwidthTest --device=0 --dtod
```

| 参数 | 意义 |
|---|---|
| `--device=0` | 选择 GPU 0 |
| `--memory=pinned/pageable` | 锁页 / 普通可分页主机内存 |
| `--htod` / `--dtoh` | 主机→GPU / GPU→主机 |
| `--dtod` | 同一 GPU 内部显存拷贝，不是跨卡 NVLink |
| `--mode=quick/range/shmoo` | 快速测试 / 指定范围 / 多尺寸扫描 |
| `--start` / `--end` / `--increment` | range 模式的起点、终点、步长，单位字节 |

关注传输方向、内存类型和带宽。样例输出 PASS 只表示程序测试成功，不表示带宽达到交付标准；官方已指出旧样例不适合准确性能测量。

参考：[旧版源码](https://github.com/NVIDIA/cuda-samples/blob/v12.8/Samples/1_Utilities/bandwidthTest/bandwidthTest.cu)、[移除说明](https://github.com/NVIDIA/cuda-samples/blob/master/CHANGELOG.md)。

## 8. NVIDIA Field Diagnostics：底层硬件诊断

### 干什么

Field Diagnostics（常称 fieldiag）用于深入检查 GPU 硬件和相关互联，是厂商故障分析与 RMA（返厂维修）流程中的重要诊断材料。是否符合 RMA 条件，由 NVIDIA/OEM 根据对应产品流程判断，不能只凭一个错误码定论。

不同 GPU 形态、代际和 HGX 平台可能使用不同工具包。它的 Level I/II **不是 DCGM 的 Level 1/2**，不能混用两套分级。

### 测哪些模块

以下模块名称来自参考截图所示工具包，用来说明检查范围；其他版本可能采用不同名称、组合或实现。

| 模块示例 | 检查方向 |
|---|---|
| `skucheck` | GPU 型号、基本配置和信息是否符合预期 |
| `connectivity` | 平台连接关系及互联状态 |
| `gpumem` | 显存相关功能和数据完整性 |
| `cudacores` | GPU 计算核心功能 |
| `pcie` | PCIe 链路与传输表现；是否包含眼图测试取决于工具包 |
| `nvlink` / `nvswitch` | NVLink/NVSwitch 互联；具体子测试按平台确定 |
| `gpustress` | GPU 持续负载稳定性 |
| `power` | 供电相关压力测试 |
| `thermal` | 热负载、温度及散热表现 |

参考截图给出的时间量级为：SIT 约半小时、Level I 约 2 小时、Level II 约 4–5.5 小时。截图中 Level II 自身也有不同时间描述，因此这些数字仅供预留维护窗口，不能作为统一耗时标准；实际以随包说明和执行进度为准。

### 怎么获取和准备

1. 向 NVIDIA 或服务器 OEM 获取适配机型、GPU 和固件的软件包或启动镜像，核对版本及随包文档。
2. 停止业务，按文档进入指定维护环境。部分工具包使用独立启动系统，部分有特定驱动或内核模块要求。
3. 如果提供 ISO，按厂商说明制作启动 U 盘或使用 BMC 虚拟介质。写 U 盘会覆盖目标盘内容；GPT、DD 模式等选项按镜像要求选择，不是所有包都采用相同设置。
4. 进入工具目录并先查看帮助。截图中的 `/var/diags` 是一个环境示例，不是统一安装路径。
5. 测试结束后，导出完整日志、报告及相关 BMC 事件，再按文档恢复系统。

### 怎么用、看哪些参数

下面保留参考截图中的 `fieldiag.sh` 用法。**仅适用于随包帮助确认支持这些参数的版本**，不应直接套用到其他 fieldiag 程序：

```bash
# 先进入实际工具目录
./fieldiag.sh --help

# 以下为分别选择的测试入口，不必顺序全部执行
./fieldiag.sh --sit           # 系统简易检查
./fieldiag.sh --level1        # Level I 综合测试
./fieldiag.sh --level2        # Level II 综合测试
./fieldiag.sh --test gpumem   # 指定模块；名称以帮助为准
```

| 参数 | 重点确认 |
|---|---|
| `--help` | 当前包支持哪些平台、选项和模块 |
| `--sit` | 快速检查覆盖哪些部件，有无前置条件 |
| `--level1` / `--level2` | 各级覆盖范围、预计耗时、是否包含热测试 |
| `--test` | 指定模块的准确名称及是否支持单独运行 |

### 结果和报错怎么看

优先检查最终状态、失败模块、GPU 序列号/PCI 地址、错误全文和日志路径。部分版本存在 `RETEST`，表示需要按提示处理前置环境后重测；状态和退出码以该工具包文档为准。保留原始日志，不能只提交终端截图。

下列报错文字来自参考截图，**编号含义尚未通过对应工具包文档核实，也不要直接当作 NVIDIA Xid 编号**：

| 截图中的报错 | 排查方向，不是直接故障判定 |
|---|---|
| `540 NVRM Fatal error: unrecoverable HW state` | 查看前后日志、温度、风扇及 BMC 事件；不能仅凭此文字认定过热或 GPU 损坏 |
| `140 NvLink bus error` | 检查 NVLink/NVSwitch 拓扑、关联链路和端点，按厂商流程隔离问题 |
| `143 PCI Express bus error` | 检查 PCIe 错误记录、链路状态、连接器和转接板等路径 |
| `PEX ERROR` | 核对具体平台的 PCIe Switch/PEX 相关日志，不能仅凭名称认定交换板损坏 |

如需换槽、交叉测试或重新插接，应按厂商维护规范断电操作；不要把截图里的“重插单压”等简写作为操作步骤。重点判断异常是否随 GPU、槽位或互联路径迁移，并保留每次测试条件。

参考：[NVIDIA Field Diagnostics 公开文档](https://docs.nvidia.com/deploy/hw-field-diag/index.html)。该公开页面描述较老平台，能说明工具定位和日志处理，但不能用于证明现代 HGX 工具包的脚本参数、模块耗时或上述错误码。现代平台以随包文档和 OEM 指引为准。

## 9. 压测时统一记录什么

另开终端采集状态：

```bash
nvidia-smi --query-gpu=timestamp,index,name,utilization.gpu,temperature.gpu,power.draw,clocks.sm,clocks.mem \
  --format=csv -l 1 > gpu-monitor.csv

# 测试前后分别保存，比较错误计数变化
nvidia-smi -q > gpu-state.txt
nvidia-smi topo -m > gpu-topology.txt
```

交付记录至少包含：**GPU 型号和拓扑、驱动/CUDA/NCCL/工具版本、完整命令、原始输出、温度功耗、ECC/Xid 异常及测试前后变化**。监控进程用 Ctrl+C 结束。

判断带宽是否正常，要对比相同型号、拓扑、方向和参数的基线；不要直接拿显存理论带宽、NVLink 双向总带宽或网卡标称速率对照所有测试结果。任何单项通过，都不能代替整套验收。
