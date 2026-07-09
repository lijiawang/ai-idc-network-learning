# 一文搞懂 NCCL：ReduceScatter 与 AllGather 到底在干什么

写分布式训练的代码时，你大概率绕不开这两个通信原语——`ReduceScatter` 和 `AllGather`。

文档看了不少，公式也抄过，但每次遇到 Bug 还是会犯嘀咕：

> "GPU0 到底该拿到哪一块？"
> "Ring 是顺时针还是逆时针？"
> "为什么是 N-1 轮而不是 N 轮？"

这篇文章只做一件事：**把这两个原语的语义讲透**。读完之后，你写代码时可以放心依赖什么、不应该依赖什么，会非常清晰。

---

## 一、先记住这四句话

| 概念 | 一句话理解 |
|---|---|
| `M` | 一次 collective 中，每张 GPU 提供的元素数；所有 GPU 必须相同 |
| **ReduceScatter** | 先对相同位置的元素求和，再让 rank `r` 只保留第 `r` 段结果 |
| **AllGather** | 每张 GPU 提供自己拥有的一个段，再让所有 GPU 收齐全部段 |
| **Ring AllReduce** | ReduceScatter + AllGather |

如果时间紧，看这一张表就够了。剩下的内容是为了让你**真正理解这张表**。

---

## 二、4 张 GPU 的例子：先把直觉建起来

我们准备 4 张 GPU，每张都有一个长度为 `M` 的输入张量，均分为 4 个 chunk：

```text
GPU0:  [A0, A1, A2, A3]
GPU1:  [B0, B1, B2, B3]
GPU2:  [C0, C1, C2, C3]
GPU3:  [D0, D1, D2, D3]
```

两个约定：

- **字母**代表数据来自哪张 GPU（A 来自 GPU0，B 来自 GPU1……）
- **数字**代表这是输入张量的第几个 chunk

归约操作我们以 `sum`（求和）为例。定义全局归约结果：

```text
S0 = A0 + B0 + C0 + D0
S1 = A1 + B1 + C1 + D1
S2 = A2 + B2 + C2 + D2
S3 = A3 + B3 + C3 + D3
```

接下来要讲的两个原语，**本质上就是在不同的"分发方式"之间做选择**。

![Ring ReduceScatter：错位并发地累加，再分片输出](diagrams/reduce-scatter-beginner-concept.png)

看这张图，重点关注两件事：

1. **同一轮里，4 条 Ring 边同时传输**——不是 GPU0 先发完、GPU1 再发；
2. **不同 chunk 是错位推进的**——不是先把 `S0` 算完，再去算 `S1`。

---

## 三、ReduceScatter：NCCL 到底保证什么

### 3.1 接口语义

概念上的调用是这样：

```cpp
ncclReduceScatter(sendbuf, recvbuf, M/4, datatype, ncclSum, comm, stream);
```

- `sendbuf` 有 `M` 个元素（完整输入）
- 每张 GPU 的 `recvbuf` 只有 `M/4` 个元素（分片输出）

**对 rank 为 `r` 的 GPU，NCCL 保证：`recvbuf` 得到全局张量的第 `r` 个 chunk。**

完成后，4 张 GPU 的状态是：

```text
GPU0 recvbuf = S0 = A0+B0+C0+D0
GPU1 recvbuf = S1 = A1+B1+C1+D1
GPU2 recvbuf = S2 = A2+B2+C2+D2
GPU3 recvbuf = S3 = A3+B3+C3+D3
```

**这是应用代码唯一应当依赖的结果。**

### 3.2 一个关键提醒

不要把某一种 Ring 的中间传输顺序，理解为最终输出 chunk 的归属。

NCCL 内部可以选择不同的 ring、channel、chunk 偏移和流水策略，但 API 的 **rank-to-output 映射永远不变**：GPU0 拿 S0，GPU1 拿 S1，依此类推。

> 写代码时依赖 API 语义，调性能时再去关心 Ring 走向。

---

## 四、Ring 内部：为什么是 N-1 轮

### 4.1 Ring 的结构

若采用单环，逻辑 ring 长这样：

```text
GPU0 → GPU1 → GPU2 → GPU3 → GPU0
```

总共执行 `N-1` 轮。4 张 GPU，就是 3 轮。每一轮里，每张 GPU 同时做四件事：

1. 向下游 GPU 发送一个 chunk（或部分归约结果）；
2. 从上游 GPU 接收一个 chunk；
3. 把接收数据与本地同编号 chunk 相加；
4. 在下一轮把新的部分和继续往下传。

### 4.2 三轮的全过程

```text
第 1 轮：
  GPU0 → GPU1：发送 A3；GPU1 做 B3 += A3，得到 A3+B3
  GPU1 → GPU2：发送 B0；GPU2 做 C0 += B0，得到 B0+C0
  GPU2 → GPU3：发送 C1；GPU3 做 D1 += C1，得到 C1+D1
  GPU3 → GPU0：发送 D2；GPU0 做 A2 += D2，得到 D2+A2

第 2 轮：
  GPU0 → GPU1：发送 D2+A2；GPU1 得到 D2+A2+B2
  GPU1 → GPU2：发送 A3+B3；GPU2 得到 A3+B3+C3
  GPU2 → GPU3：发送 B0+C0；GPU3 得到 B0+C0+D0
  GPU3 → GPU0：发送 C1+D1；GPU0 得到 C1+D1+A1

第 3 轮：
  GPU0 → GPU1：发送 C1+D1+A1；GPU1 得到 S1
  GPU1 → GPU2：发送 D2+A2+B2；GPU2 得到 S2
  GPU2 → GPU3：发送 A3+B3+C3；GPU3 得到 S3
  GPU3 → GPU0：发送 B0+C0+D0；GPU0 得到 S0
```

注意，**这不是"先算完 S0 再算 S1"**。每个 chunk 的最后一步落在不同的边上：

```text
S0 的最后一步：GPU3 → GPU0
S1 的最后一步：GPU0 → GPU1
S2 的最后一步：GPU1 → GPU2
S3 的最后一步：GPU2 → GPU3
```

这就是"错位并发"——**每个 chunk 都在路上，每一轮都继续向下游推进一跳**。

### 4.3 为什么是 N-1 轮？

每个 chunk 在起点已经包含 1 张 GPU 的本地数据。它只需要再经过其余 `N-1` 张 GPU，就完成了全局归约：

```text
本地值（1 份）
  → 融合第 2 张 GPU
  → 融合第 3 张 GPU
  → ...
  → 融合第 N 张 GPU   ← 这里停止，共 N-1 跳
```

AllGather 同理：每张 GPU 一开始已有自己的 1 个 chunk，只需从其余 `N-1` 张 GPU 收齐其余 chunk。

### 4.4 "发送"不等于"清空"

接收端 GPU1 收到 `A3` 时：

```text
发送端 GPU0：读取 A3 并发送
接收端 GPU1：B3 += A3
结果：A3+B3
```

**发送是"读取并传输"，不是"剪切"**。GPU0 上的 `A3` 不会因此变成 0。

---

## 五、AllGather：把碎片拼回去

![4 GPU Ring AllGather 步骤图](https://lijiawang.oss-cn-hangzhou.aliyuncs.com/20260625153805256.png)

ReduceScatter 之后，每张 GPU 各自握着一块"碎片"：

```text
GPU0 提供 S0
GPU1 提供 S1
GPU2 提供 S2
GPU3 提供 S3
```

概念上的调用：

```cpp
ncclAllGather(sendbuf, recvbuf, M/4, datatype, comm, stream);
```

- 每张 GPU 的 `sendbuf` 是一个 `M/4` 大小的有效 chunk
- `recvbuf` 是容纳完整 `M` 元素结果的缓冲区

完成后，**每张 GPU 都拿到完整的 `[S0, S1, S2, S3]`**：

```text
[
  A0+B0+C0+D0,
  A1+B1+C1+D1,
  A2+B2+C2+D2,
  A3+B3+C3+D3
]
```

### 一个容易踩的坑

AllGather **不会读取**缓冲区里残留的旧值（比如 in-place 模式下的 `A1/A2/A3`），**它只以每个 rank 的有效 `S_r` 为输入**。

对 in-place AllGather，可理解为：完整输出缓冲区里，预先已放好本 rank 的那一块：

```text
GPU0:  [S0,  _,  _,  _]
GPU1:  [ _, S1,  _,  _]
GPU2:  [ _,  _, S2,  _]
GPU3:  [ _,  _,  _, S3]
```

其余槽位由 AllGather 填满，最终每张卡都是 `[S0, S1, S2, S3]`。

---

## 六、AllReduce = ReduceScatter + AllGather

Ring AllReduce 可以理解成两段连续操作：

```text
完整输入 M
    │
    ├─ ReduceScatter：每张 GPU 得到一个全局归约 chunk S_r（大小 M/4）
    │
    └─ AllGather：将 S0、S1、S2、S3 分发给所有 GPU
                         ↓
              每张 GPU 得到完整的全局归约张量 M
```

### 三个 collective 的输入输出对比

| 操作 | 每张 GPU 输入 | 每张 GPU 输出 | 典型用途 |
|---|---:|---:|---|
| **AllReduce** | `M` | `M` | 数据并行梯度同步 |
| **ReduceScatter** | `M` | `M/N` | ZeRO/FSDP 分片梯度或分片优化器 |
| **AllGather** | `M/N` | `M` | 把分片参数/梯度恢复为完整张量 |

### 通信量的直觉

理想单 Ring 模型下，每张 GPU 在 ReduceScatter 中收发的数据量约为：

```text
(N-1) × (M/N)
```

AllGather 也是同一数量级。所以完整 Ring AllReduce，每张 GPU 总发送量约为：

```text
2 × (N-1) × (M/N)
```

当 `N` 很大时，这接近 `2M`。**Ring 的好处在于：每轮每条相邻链路都在持续工作，不会让所有 GPU 同时争抢单个中心节点。**

---

## 七、关于 M 的几个常见疑问

### Q1：M 是每张 GPU 都一样大吗？

**对同一次 NCCL collective 调用来说，是的。**

若本次调用有 `N` 张 GPU 参与，每张 GPU 必须向 NCCL 提供：

- 相同元素个数（同一个 M）
- 相同数据类型（FP16 / BF16 / FP32……）
- 相同归约操作（sum / max / min……）

注意，M 优先理解为**元素数量**，不是字节数。

```text
例：4 张 GPU 对 1,024 个 FP32 元素的 bucket 执行 ReduceScatter

M = 1,024 个元素
N = 4
每张 GPU 的 recvbuf = M/N = 256 个元素
```

### Q2：那为什么模型里不同层的梯度大小不一样？

这是"模型张量"和"一次通信调用"的边界不同。

模型参数/梯度天然大小不一：

```text
Embedding 梯度：很大
Attention QKV 梯度：中等
LayerNorm 梯度：很小
```

训练框架不会要求这些梯度单独相等。它的做法是：**把多个梯度按顺序拼接进一个连续的 gradient bucket**，再对整个 bucket 发起一次 collective：

```text
多个不同大小的梯度
    ↓ 拼接 / 打包
一个连续 bucket（本次 M 个元素）
    ↓ 每张 GPU 构造同样大小、同样顺序的 bucket
一次 ReduceScatter 或 AllReduce
```

所以真正必须相等的，是 **同一次 collective 中所有 GPU 的 bucket 大小和 bucket 内元素顺序**，而不是"模型的所有参数张量必须一样大"。

### Q3：M 不能被 N 整除怎么办？

以等分 ReduceScatter 为例，`M` 最好能被 `N` 整除。

```text
M = 1,025，N = 4
1,025 / 4 不能得到整数个元素
```

工程上通常有三种处理方式：

1. 在 bucket 末尾 **padding** 到可整除的长度；
2. 将不规则部分拆到单独的通信操作；
3. 使用框架提供的更高层分片逻辑处理尾部。

补齐的元素只是为了通信分块对齐，**在计算结果中会被忽略**，不代表真实梯度。

### Q4：所有 rank 必须以相同顺序调用 collective？

**必须。** 这是分布式训练里非常容易踩的坑。

```text
所有 GPU：先对 bucket 0 调 ReduceScatter
所有 GPU：再对 bucket 1 调 ReduceScatter
所有 GPU：最后对 bucket 2 调 ReduceScatter
```

如果 GPU0 还在等 `bucket 0`，而 GPU1 已经跳去执行 `bucket 1`——各 rank 会互相等待，**通常导致卡死或通信错误**。

这也是分布式训练框架要严格维护参数注册顺序、bucket 顺序、collective 调度顺序的原因。

---

## 八、In-place vs Out-of-place

### Out-of-place（最直观）

`sendbuf` 和 `recvbuf` 是不同内存：

```text
GPU0 sendbuf:  [A0, A1, A2, A3]
GPU0 recvbuf:  [S0]
```

ReduceScatter 的输出只有 `[S0]`，其余输入内容不属于输出。

### In-place（复用完整 M 缓冲区）

为本 rank 的输出预留对应槽位，概念上：

```text
GPU0:  recvbuf = sendbuf + 0 × (M/4)
GPU1:  recvbuf = sendbuf + 1 × (M/4)
GPU2:  recvbuf = sendbuf + 2 × (M/4)
GPU3:  recvbuf = sendbuf + 3 × (M/4)
```

操作结束后，可能画成：

```text
GPU0:  [S0, A1, A2, A3]   # 只有 S0 有效
GPU1:  [B0, S1, B2, B3]   # 只有 S1 有效
GPU2:  [C0, C1, S2, C3]   # 只有 S2 有效
GPU3:  [D0, D1, D2, S3]   # 只有 S3 有效
```

**但这只是"输出写回哪个槽位"的示意图**。除本 rank 的 `S_r` 外，其他位置：

- 可能仍保留旧输入；
- 可能被 NCCL 用作临时/流水数据而覆盖；
- **不属于 ReduceScatter 输出，程序不得读取或依赖**。

特别提醒——下面的理解是**错的**：

```text
GPU0:  [A0, S1, A2, A3]   # ✗ 错！GPU0 应该拿到 S0，不是 S1
```

---

## 九、避坑清单（建议收藏）

### 5 个最常见的误解

| 误解 | 正确理解 |
|---|---|
| "发送后源 GPU 的数据会变成 0" | 发送是读取并传输，源数据不会自动清零 |
| "先归约完整 S0，再归约 S1" | 所有 chunk 错位并发地在 Ring 中推进 |
| "GPU0 最终拿哪个 chunk 由 Ring 方向决定" | 对 API 而言，GPU0 的输出固定为 `S0`；内部 Ring 可自由选择 |
| "AllGather 会用输入缓冲区里残留的旧数据" | 不会；只使用每张 GPU 的有效 `S_r` |
| "一次 collective 里所有模型参数都要一样大" | 不需要；要求相同的是 bucket，不是参数张量 |

### 发起 collective 前的检查清单

1. 所有 rank 都加入同一个 communicator；
2. 所有 rank 调用的是同一种 collective；
3. 所有 rank 按**相同顺序**调用 collective；
4. 对同一次调用，元素数、数据类型、归约操作匹配；
5. collective 在 CUDA stream 上**异步执行**；GPU 操作完成前，不要读写相关 buffer。

---

## 写在最后

最后送你一句话：

> **ReduceScatter**：第 `r` 张 GPU 只保留第 `r` 个全局归约 chunk `S_r`。
>
> **AllGather**：把所有 `S_r` 重新拼回每张 GPU。

写代码时，请只依赖 API 语义——`GPU_r` 拿 `S_r`、AllGather 后人人都有完整的 `[S0, S1, ..., S_{N-1}]`。

至于 Ring 的走向、内部 chunk 的起始偏移、slice 大小和 buffer 复用方式，都属于 NCCL 的**内部实现**，理解它们是为了调性能，不是为了推断显存里"应该有什么"。

**分清这两件事，你就不会在分布式训练的通信问题上反复踩坑。**

---

*如果这篇文章帮到了你，欢迎转发给你身边正在搞分布式训练的同事——他们大概率也需要。*
