# 从零设计 Rail-Optimized 计算网络（三）：按 Pod 扩到万卡，Core 怎么算、怎么留

前两篇算出了一个 1024 卡的两层网络，也讨论了怎样分期增加服务器。

但当我们要求每次增加一个 Pod，多个 Pod 之间也保持 1∶1，端口就得重新安排。

这一篇固定一个建设单位，一个 Pod 包含四个 SU，也就是 128 台服务器、1024 张 GPU。每台服务器八个 400G 计算端口，交换机仍然提供 64 个 400G 逻辑端口。

这里的 Pod 是项目定义的模块，不是 Kubernetes Pod，也没有全行业统一的服务器数量。

## 01 为了接 Core，Spine 要留出上联

上一篇的独立 1024 卡网络，配置 32 台 Leaf、16 台 Spine。每台 Spine 到 32 台 Leaf 各接两条，已经用掉 64 个端口。

没有空口再接上层。

如果需要多个 Pod 互通，可以从一期就规划 Leaf、Spine、Core 三层。Core 是连接不同 Pod 的公共上层交换机。

每台 Spine 改为 32 口接本 Pod 的 Leaf，另外 32 口接 Core。

32 台 Leaf 一共有 32 × 32＝1024 条上联。现在每台 Spine 只能接其中 32 条，所以需要 1024 ÷ 32＝32 台 Spine。

**一个能向外提供完整带宽的 Pod，配置为 128 台服务器、32 台 Leaf、32 台 Spine。**

每台 Leaf 连接本 Pod 全部 32 台 Spine，每对一条 400G。每台 Spine 的另外 32 条上联，接公共 Core。

从服务器端口总和，到 Leaf 上联，再到 Spine 上联，一个 Pod 的单向总带宽都是 409.6Tb/s。

这是与两层紧凑方案不同的建设选择。若从一开始就知道要跨 Pod 扩展，应按三层方案规划，避免等到 Spine 接满了才腾端口。

## 02 Core 数量，先从 Spine 上联总量算

假设最终建设四个 Pod，合计 512 台服务器、4096 张 GPU。

全网有 4 × 32＝128 台 Spine，每台 32 条上联，一共 4096 条 400G 链路。

每台 Core 有 64 个端口，所以

**Core 数量＝128 × 32 ÷ 64＝64 台。**

同速率端口可以用这个公式计算容量下限。

**Core 容量下限＝Spine 总数 × 单台 Spine 上联口数 ÷ 单台 Core 可用口数。**

有小数时先向上取整。但容量够用只是第一步，还需要安排具体接线，检查不同 Pod 之间的路径容量与路由。

这个示例的总量是 128 Leaf、128 Spine、64 Core，与 NVIDIA 的 512 台服务器规模表一致。下面的详细分组是教学推导，不能仅凭设备数相同就认定是官方唯一接法。[NVIDIA SuperPOD Architecture](https://docs.nvidia.com/dgx-superpod/reference-architecture-scalable-infrastructure-h100/latest/dgx-superpod-architecture.html)

## 03 全网 64 台 Core，为什么一台 Spine 只接两台

先只看四个 Pod 各自的 Spine 1。

把它们都接到 Core 1，每个 Pod 接 16 条，这台 Core 就用了 4 × 16＝64 个端口。

每台 Spine 1 需要 32 条上联，刚才只用掉 16 条。再加一台 Core 2，按同样规则连接，剩下的 16 条也有了去处。

两台 Core 作为一组，接完了四个 Pod 的 Spine 1。

每个 Pod 有 Spine 1～Spine 32，把这种接法重复 32 次，就得到 32 个组、每组两台，共 64 台 Core。

| Core 组 | 对应对象 |
|---|---|
| 第 1 组，两台 Core | 四个 Pod 的 Spine 1 |
| 第 2 组，两台 Core | 四个 Pod 的 Spine 2 |
| …… | …… |
| 第 32 组，两台 Core | 四个 Pod 的 Spine 32 |

每台 Spine 到对应组的两台 Core 各接 16 条，总上联仍然是 32 条 400G。

Leaf 则连接本 Pod 全部 32 台 Spine，可以通过它们到达全部 Core 组。

例如从 Pod 1 发往 Pod 3，可以经过源 Leaf、Pod 1 的 Spine 5、第 5 组的一台 Core、Pod 3 的 Spine 5，最后到目的 Leaf。目的 Pod 的 Spine 5 连接本 Pod 全部 Leaf，能够继续转发到目标服务器。

**全网 Core 数量、单台 Spine 连接的 Core 数量、每对设备的链路数，要分开看。**

## 04 Core 也必须留 32 个口吗

Core 需要为未来 Pod 留口，但没有固定要留一半的规则。

Leaf 的 32＋32，是服务器下联与 Spine 上联。Spine 的 32＋32，是 Leaf 下联与 Core 上联。

在当前三层方案里，Core 已经是最高层，它把端口分给各个 Pod。

按最终四个 Pod 的接法，每台 Core 给一个 Pod 分配 16 个端口。分期建设时就会出现下面的占用情况。

| 已建 Pod | 每台 Core 已用端口 | 为未来预留 |
|---|---|---|
| 1 个 | 16 口 | 48 口 |
| 2 个 | 32 口 | 32 口 |
| 3 个 | 48 口 | 16 口 |
| 4 个 | 64 口 | 0 口 |

建了两个、最终四个的时候，才恰好留 32 口。

这些空口是未来 Pod 的接入位置。若 Core 还要向上再接一层，那就属于另一套拓扑，需要重新分配上下联，不能沿用这里的设备数量。

## 05 十个 Pod 已经是万卡，为何有人算出 256 台 Core

十个 Pod 对应 10240 张 GPU、1280 台服务器、320 台 Leaf 和 320 台 Spine。

按当前端口总数计算，Core 容量下限是

**320 × 32 ÷ 64＝160 台。**

但如果有人给出 256 台 Core，先问清楚他是不是把最终十六个 Pod 的容量也算进去了。

按最终十六个 Pod 规划时，一台 Core 给每个 Pod 分四个端口，十六个 Pod 正好占满 64 口。

每台 Spine 有 32 条上联，到每台 Core 接四条，就要连接八台 Core。

仍按 Spine 编号分 32 组，每组八台，合计 256 台 Core。

接线规则变成所有 Pod 的 Spine 1 连接第 1 组八台 Core，每对四条；Spine 2 连接第 2 组，其余依次对应。

| 最终规划 | 每组 Core | 每对 Spine—Core 链路 | Core 总数 |
|---|---|---|---|
| 4 个 Pod | 2 台 | 16 条 | 64 台 |
| 16 个 Pod | 8 台 | 4 条 | 256 台 |

按十六个 Pod 方案交付十个时，每台 Core 用掉 10 × 4＝40 个端口，留下 24 个，供未来六个 Pod 使用。

**256 台包含了预留成本，不能当成十个 Pod 的必需数量。**

如果只做十个 Pod，就围绕十个设计。160 台是端口总量下限，仍需证明具体接法能满足目标。沿用 32 个固定组，每组只有五台，32 条 Spine 上联不能平均分配，必须研究不同链路分配或增加设备留空口。

我不会仅凭整除后的设备总数，把它写成已经验证的无收敛采购方案。

## 06 预留最终容量，也要固定最终接法

如果最终目标是十六个 Pod，一期就应该按每台 Spine 接八台 Core、每对四条的规则规划。

原先四 Pod 方案的一台 Spine 只接两台 Core、每对 16 条。后面想原样保留这两组链路、继续添加 Core，会发现 Spine 的上联端口已经用完。

所以，设备数量和接线规则必须一起按目标规模制定。

按最终十六个 Pod 的规则部署公共 Core 后，每增加一个 Pod，只向预留端口接入新链路。若为了省初期投资，只部署部分 Core，当前跨 Pod 可用带宽就要重新核算，不能仍按完整 1∶1 宣称。

上层建设模块固定后，服务器也可以分批上架。一个 Pod 的 32 台 Spine 先规划好，只安装一个 SU 的八台 Leaf 时，每台 Spine 先用八个下联口，其余 24 个留给这个 Pod 后续的三个 SU。这样，SU 内接入、Pod 内扩展和跨 Pod 连接各有明确的预留位置。

## 07 最后核对一次，容量够了不代表可以直接签收

上面的算例只计算正常状态下的业务容量。辅助节点、备件和故障后保持带宽所需的额外设备，要另算。

尤其要分开三件事。正常时的 1∶1、未来扩容的空口、故障后的剩余带宽，不是一笔容量。

若某台 Leaf 恰好有 32 条下联、32 条上联，断掉部分上联，可用带宽就会下降。替代路径能绕过故障，不会补回失去的容量，正在运行的训练也未必无中断恢复。

物理采购还要核对逻辑端口。以 IB 的 QM9700／QM9790 为例，64 个 400G NDR 逻辑端口对应 32 个 OSFP 插槽。一个逻辑链路数不能直接换成同样数量的成品线缆，RoCEv2 设备也应按自身规格核对。[NVIDIA QM97XX 线缆说明](https://networking-docs.nvidia.com/qm97x0hw/cable-installation)

RoCEv2 要验证以太网路径、MTU、优先级以及端侧拥塞控制。典型无损方案会联合配置 ECN 和 PFC，具体参数由设备和软件方案决定。[NVIDIA RoCE 配置说明](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-1-and-Switch-Ports/Quality-of-Service/RDMA-over-Converged-Ethernet-RoCE/)

IB 则要检查 Subnet Manager、Fabric 路由、分区及对应拥塞管理。NCCL 选择了哪些网卡、GPU Direct RDMA 是否生效，也要从运行结果确认。[NCCL 多网卡设置](https://docs.nvidia.com/deeplearning/nccl/archives/nccl_2303/user-guide/docs/env.html)

测试从单链路、单 SU、单 Pod 逐级做到跨 Pod，根据业务覆盖 AllReduce、All-to-All，再做断链路和交换机故障演练。上下行总带宽相等，只是验收中的一项。

真正准备交付时，把当前规模、最终规模和跨 Pod 带宽要求写在端口表开头，再给现有与未来链路逐条标出两端设备和端口。

**新增第十一个 Pod 时，线应该插在哪里，要在第一期的设计里就能找到答案。**
