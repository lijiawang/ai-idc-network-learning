# RDMA 是什么：让数据跨主机直达内存的高速通道

![传统 Socket 经过内核网络栈与 RDMA 绕过内核网络栈的对比](assets/rdma-intro/09-kernel-bypass-rdma-cn.png)

> 阅读提示：第一次接触 RDMA，只要先看懂三件事：数据为什么能少绕路、MR/QP/CQ 分别做什么、Send/Write/Read 有什么区别。

大模型训练需要跨服务器同步数据，分布式存储也需要频繁读写其他机器上的数据。网络带宽越来越高后，瓶颈不一定在线缆上，还可能出现在服务器内部：

**只是想把数据交给网卡发送，为什么还要经过内核、CPU 和多块缓冲区？**

先看最常见的传统 Socket 通信：

![传统 Socket 发送数据时经过用户态、内核态和网卡的处理步骤](assets/rdma-intro/08-traditional-socket-send-path.png)

以发送为例，应用通过 `send()` 进入内核，数据通常要从应用 Buffer 复制到内核 Socket Buffer，再经过 TCP/IP 协议栈和网卡驱动处理，最后由 NIC 通过 DMA 读取并发送。系统调用、内存复制和协议处理都会产生开销。现代操作系统可以通过协议卸载、批处理和零拷贝 API 减少部分开销，因此不能简单认为传统 TCP 一定很慢。

RDMA 把主体数据传输交给 RNIC。两端 RNIC 分别通过 DMA 访问各自主机的已注册内存，并通过网络完成传输。

---

## 一、RDMA 到底是什么？

RDMA 的全称是 Remote Direct Memory Access，中文常译为“远程直接内存访问”。

先理解 DMA，再理解 RDMA：

- DMA：本机的设备（例如网卡或 SSD）可以直接读写本机内存，CPU 负责下达任务，不逐字节搬运数据。
- RDMA：支持 RDMA 的网卡通过网络，在两台主机的已注册内存之间传输数据。

RNIC（RDMA Network Interface Card）就是支持 RDMA 的网卡。在 InfiniBand 文档中，它也常被称为 HCA。**所有 RNIC 都是 NIC，但不是所有 NIC 都支持 RDMA。**

| 对比项 | 普通 NIC | RNIC |
|---|---|---|
| 主要任务 | 收发普通网络报文 | 收发 RDMA 数据，并通过 DMA 读写已注册内存 |
| 数据传输方式 | 普通 TCP/UDP 通信通常由内核协议栈和 CPU 配合完成 | 队列处理、DMA、权限校验等可由网卡硬件完成 |

“直接”不代表可以随意访问另一台机器。远端应用必须先把一段内存注册为 MR（Memory Region）并设置权限，RNIC 只能访问已授权的范围。

---

## 二、RDMA 为什么快？

![传统 Socket 的应用与内核复制和 RDMA Zero-copy 路径对比](assets/rdma-intro/10-zero-copy-vs-traditional-cn.png)

图中右侧以 RDMA Write 为例。RDMA Read 的数据方向相反，但同样由两端 RNIC 通过 DMA 访问已注册内存。

结合上图，可以把 RDMA 的优势概括为三个关键词：

| 关键词 | 用大白话解释 |
|---|---|
| Zero-copy | 典型 RDMA 传输中，RNIC 可通过 DMA 直接访问已注册内存，无需在应用缓冲区与内核缓冲区之间复制数据 |
| Kernel bypass | 实际传输的数据通常不必每次都经过内核协议栈 |
| Transport offload | 队列处理、权限检查、报文分段与重组，以及部分可靠传输工作由 RNIC 完成 |

RDMA 也不是“零 CPU”：CPU 仍要准备资源、提交任务和处理异常；为了追求极低延迟，有些程序还会持续轮询 CQ。

RDMA 能快多少取决于网卡、报文大小、NUMA 拓扑和网络状况，无法用固定倍数概括。它的核心优势是减少软件处理和数据复制，从而降低延迟和 CPU 开销，并让吞吐更接近链路线速。

---

## 三、先看懂 MR、QP 和 CQ

使用 RDMA 时，先记住三个核心对象：

| 对象 | 简单理解 | 主要作用 |
|---|---|---|
| MR | 已经登记并授权的内存 | 告诉 RNIC 哪块内存可以访问 |
| QP | 提交通信任务的队列 | 把 Send、Write、Read 等任务交给 RNIC |
| CQ | 保存完成结果的队列 | 告诉应用任务成功还是失败 |

![RDMA 对象模型：MR、QP、CQ](assets/rdma-intro/02-rdma-object-model.png)

### MR：允许 RNIC 访问的内存

应用不能直接把任意内存地址交给 RNIC，而要先把一段 Buffer 注册为 MR。注册时需要说明内存范围和访问权限。

注册完成后会得到 `lkey` 和 `rkey`：`lkey` 供本地 RNIC 使用，`rkey` 供对端执行 RDMA Write、Read 等远程访问时使用。

可以把 MR 理解成一块已经登记并授权的货架：地址、范围、权限和访问凭证都正确，RNIC 才允许访问。

### QP：提交任务的地方

QP 是 Queue Pair，由两个队列组成：

- SQ（Send Queue）：提交 Send、Write、Read 等主动任务。
- RQ（Receive Queue）：提前准备 Receive Buffer，主要供 Send/Recv 使用。

可以把 SQ 理解成待办队列，把 RQ 理解成提前准备好的收件箱。

### CQ：查看任务是否完成

应用把任务放进 QP 后，RNIC 在后台处理；任务完成后，应用从 CQ 中获取结果。**任务已经提交，不等于任务已经完成。**

---

## 四、先分清 Send、Write 和 Read

初学 RDMA 最容易混淆的，是这三种操作看起来都像“传数据”，但它们决定了数据放在哪里、接收方要不要提前准备，以及谁会收到通知。

| 操作 | 可以怎么理解 | 接收方需要提前准备吗？ | 远端是否通常收到 CQ 通知？ |
|---|---|---:|---:|
| Send/Recv | 把数据放进对方提前准备的收件箱 | 是，需要 Post Receive | 是 |
| RDMA Write | 把数据推到对方授权的指定内存 | 不需要 | 否 |
| RDMA Read | 从对方授权的指定内存把数据拉回来 | 不需要 | 否 |
| Write with Immediate | Write 数据，同时附带一条通知 | 是，需要预投 Receive WQE 接收通知 | 是 |

![Send、RDMA Write 与 RDMA Read 的数据方向、接收准备和完成通知对比](assets/rdma-intro/06-send-write-read.png)

### Send/Recv：双方都参与

接收方先准备 Receive Buffer 并 Post Receive，发送方再提交 Send。它和普通消息通信最接近，关键点是：**接收方要先准备好收件箱。**

### RDMA Write：把数据推过去

发起方知道对方的远程地址和 `rkey` 后，可以把本地数据直接写进对方指定的 MR。普通 Write 不需要远端提前 Post Receive，也不会自动通知远端业务线程，因此上层还要约定通知方式。

> Write with Immediate 可以在写入数据的同时通知远端。远端需要预投 Receive WQE 来接收通知，但主体数据仍直接写入指定的 MR。

### RDMA Read：把数据拉回来

Read 的方向正好相反：发起方使用远程地址和 `rkey`，把远端 MR 中的数据读到本地 Buffer。完成结果出现在发起方的 CQ 中，远端应用通常不会收到通知。

### 完成不等于业务已经处理

本地 CQ 显示成功，只表示 RDMA 传输已经完成，不等于远端业务已经处理数据或数据已经持久化。

---

## 五、常见连接类型与网络承载方式

### RC、UC、UD：QP 的传输类型

第一次接触 RDMA，重点理解 RC 就够了：

| 类型 | 入门理解 |
|---|---|
| RC（Reliable Connection） | 一对一，连接正常时可靠且有序；常用于 AI、HPC 和存储 |
| UC（Unreliable Connection） | 一对一，但不保证可靠交付；较少作为通用入门选择 |
| UD（Unreliable Datagram） | 类似不可靠数据报；适合小消息或控制面场景 |

RC 支持 Send/Recv、Read、Write 等常见操作，也是本文默认讨论的类型。这里的“可靠”不等于永不失败：路径异常或重试耗尽时，任务仍可能报错，需要上层恢复连接。

### InfiniBand、RoCE 和 iWARP：RDMA 的承载方式

RDMA 是一种通信能力，不等于某一种线缆或网络。

| 技术 | 底层网络 | 入门理解 |
|---|---|---|
| InfiniBand | 专用 InfiniBand Fabric | 原生为高性能 RDMA 设计的网络 |
| RoCE | 以太网 | 在以太网上承载 RDMA，数据中心里较常见 |
| iWARP | TCP/IP 以太网 | 在 TCP/IP 体系上实现 RDMA，生态相对少见 |

RoCEv1 运行在二层以太网上；更常见的 RoCEv2 增加了 IP/UDP 封装，可以跨三层网络。这里的 UDP 只是承载方式，应用仍通过 RDMA 接口提交任务。PFC、ECN、DCQCN 等网络配置属于进阶主题，本文不展开。

---

## 六、一条 RDMA 连接大致怎么跑起来？

不必一开始就记状态机细节，只要把下面的顺序串起来：

    准备并注册内存
        -> 创建 CQ 和 QP
        -> 双方交换连接信息
        -> 把 QP 置为可工作状态
        -> 接收方提前 Post Receive（Send/Recv 或 Write with Immediate 场景）
        -> 向 SQ 提交任务
        -> RNIC 执行
        -> 从 CQ 查看结果

双方通常通过 TCP、RDMA CM 或其他控制通道交换 QP 信息；单边 Read、Write 还要交换远程地址和 `rkey`。在 RC 模式下，RTR（Ready to Receive）表示可以接收，RTS（Ready to Send）表示可以发送。

---

## 七、RDMA 在 AI 集群里处在什么位置？

在多机大模型训练中，开发者通常不会手写 Verbs；训练框架、集合通信库和传输框架会分层封装底层细节。

![RDMA 在 AI 集群中的软件层次、普通主机内存中转路径与 GPUDirect RDMA 直通路径](assets/rdma-intro/07-rdma-in-ai-cluster-v2.png)

图中的线条分别表示：

- **蓝色双向线**：普通主机内存中转路径，数据经过 GPU、主机内存和 RNIC。
- **绿色双向线**：GPUDirect RDMA 直通路径，RNIC 直接读写 GPU 显存，不再使用主机内存中转。
- **灰色箭头或虚线**：软件调用、任务提交和控制关系，不表示主体数据经过 CPU 搬运。
- **紫色虚线**：RDMA CM 与 RDMA Verbs 的可选连接管理关系，不是数据传输的必经路径。

中间的软件栈可以简单理解为：训练框架调用通信组件，通信组件再通过网络后端或传输框架调用 RDMA Verbs，由 RNIC 传输数据；底层网络则是 InfiniBand 或 RoCE。实际软件组合可能有所不同。

> 实际能否使用 GPUDirect RDMA，取决于 GPU、RNIC、驱动、通信库和 PCIe 拓扑等条件。详见[《GPUDirect RDMA：跨节点 GPU 的显存直通车》](https://mp.weixin.qq.com/s/eaPt4jwbF833z8ovJDhkPA)。

---

## 八、怎么确认 RDMA 环境可用？

先确认设备、连通性和点对点性能，再扩大到多机业务。

### 1. 看设备和端口

常用命令：

    rdma link
    ibv_devices
    ibv_devinfo

确认设备存在、端口处于 Active 状态，并检查链路类型和速率。

### 2. 测基本连通性

使用 `rping` 或示例程序验证 RDMA 连接。普通 `ping` 成功只代表 IP 大致可达，不代表 RDMA QP 一定能建立。

### 3. 测点对点性能

`perftest` 常用工具包括：

    ib_write_bw
    ib_read_bw
    ib_send_bw
    ib_write_lat
    ib_read_lat
    ib_send_lat

这些工具分别测试 Write、Read、Send 的带宽与延迟。

---

## 九、总结

1. RDMA 让 RNIC 在两台主机的已注册内存之间传输数据，减少中间复制和 CPU 协议处理。
2. MR 决定“哪块内存能访问”，QP 用来提交任务，CQ 告诉应用“任务是否完成”。
3. Send/Recv 是双方配合的消息模式，Write/Read 是直接访问远端已授权内存的单边操作。

一句话概括：**CPU 负责控制，RNIC 负责搬运。**

---

## 参考资料

- [IBTA：InfiniBand Architecture Specification](https://www.infinibandta.org/ibta-specification/)
- [Linux Kernel：Userspace verbs access](https://docs.kernel.org/infiniband/user_verbs.html)
- [Linux RDMA Core：用户态库与工具](https://github.com/linux-rdma/rdma-core)
- [rdma-core / libibverbs：ibv_reg_mr(3)](https://github.com/linux-rdma/rdma-core/blob/master/libibverbs/man/ibv_reg_mr.3)
- [NVIDIA：RDMA Aware Networks Programming User Manual](https://docs.nvidia.com/rdma-aware-networks-programming-user-manual-1-7.pdf)
- [【RDMA 学习笔记——基础篇】（1）RDMA 概述](https://blog.csdn.net/qq_54050349/article/details/161665483)
