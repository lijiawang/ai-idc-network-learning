# NCCL 中的 ReduceScatter 与 AllGather

本文从零解释 NCCL 中的 `ReduceScatter`、`AllGather` 与 Ring AllReduce。重点是区分两件事：

1. **NCCL 对程序保证什么结果**：这是写代码时可以依赖的语义；
2. **Ring 在内部怎样传输**：这是理解性能的模型，但不是应用可依赖的显存布局。

Ring 的走向、内部 chunk 的起始偏移、slice 大小和具体 buffer 复用方式，都属于 NCCL 内部实现；不要据此推断未声明的显存内容。

## 先记住这四句话

| 概念 | 一句话理解 |
|---|---|
| `M` | 一次 collective 中，每张 GPU 提供的元素数；所有 GPU 必须相同。 |
| ReduceScatter | 先对相同位置的元素求和，再让 rank `r` 只保留第 `r` 段结果。 |
| AllGather | 每张 GPU 提供自己拥有的一个段，再让所有 GPU 收齐全部段。 |
| Ring AllReduce | `ReduceScatter` + `AllGather`。 |

阅读顺序建议：先读第 1、2、5、6 节建立“程序视角”；再读第 3、4 节理解 Ring 和显存缓冲区。

![Ring ReduceScatter：错位并发地累加，再分片输出](diagrams/reduce-scatter-beginner-concept.png)

这张图要重点看两点：

1. **同一轮里，4 条 Ring 边同时传输**，不是 GPU0 先发完、GPU1 再发；
2. **不同 chunk 是错位推进的**，不是先把 `S0` 算完，再去算 `S1`。

## 1. 示例与符号

有 4 张 GPU。每张 GPU 都有一个长度为 `M` 的输入张量，均分为 4 个 chunk，每个 chunk 大小为 `M/4`：

```text
GPU0 sendbuf = [A0, A1, A2, A3]
GPU1 sendbuf = [B0, B1, B2, B3]
GPU2 sendbuf = [C0, C1, C2, C3]
GPU3 sendbuf = [D0, D1, D2, D3]
```

- 字母表示数据来自哪张 GPU。
- 数字表示该数据位于输入张量的第几个 chunk。
- 归约操作以 `sum` 为例。

定义全局归约结果：

```text
S0 = A0 + B0 + C0 + D0
S1 = A1 + B1 + C1 + D1
S2 = A2 + B2 + C2 + D2
S3 = A3 + B3 + C3 + D3
```

### 1.1 `M` 到底是不是每张 GPU 都一样大？

**对同一次 NCCL collective 调用来说，是的。**

若这一次调用有 `N` 张 GPU 参与，则每张 GPU 必须向 NCCL 提供：

```text
相同元素个数（同一个 M）
相同数据类型（例如都为 FP16、BF16 或 FP32）
相同归约操作（例如都为 sum）
```

这里“相同”指的是本次通信所传入的连续一段数据，而不是要求模型的每一个参数张量天生一样大。

例如，4 张 GPU 对一个包含 1,024 个 FP32 元素的 bucket 执行 ReduceScatter：

```text
GPU0: sendbuf 有 1,024 个元素
GPU1: sendbuf 有 1,024 个元素
GPU2: sendbuf 有 1,024 个元素
GPU3: sendbuf 有 1,024 个元素
```

则：

```text
M = 1,024 个元素
N = 4
每张 GPU 的 recvbuf = M/N = 256 个元素
```

注意 `M` 应优先理解为**元素数量**，不是字节数。若数据类型是 FP32（每个元素 4 字节），则：

```text
sendbuf 大小 = 1,024 × 4 B = 4 KiB
recvbuf 大小 = 256 × 4 B = 1 KiB
```

### 1.2 为什么模型里不同层的梯度大小明明不一样？

这是“模型张量”和“一次通信调用”的边界不同。

一个模型的参数/梯度可以是不同形状、不同大小：

```text
Embedding 梯度：很大
Attention QKV 权重梯度：中等
LayerNorm 权重梯度：很小
```

训练框架不会要求这些单独的梯度大小相等。通常会把多个梯度按顺序放进一个连续的 **gradient bucket**，然后对这个 bucket 发起一次 NCCL collective：

```text
多个不同大小的梯度
    ↓ 拼接/打包
一个连续 bucket（本次 M 个元素）
    ↓ 每张 GPU 都构造同样大小、同样顺序的 bucket
一次 ReduceScatter 或 AllReduce
```

因此，必须相等的是：

```text
同一次 collective 中，所有 GPU 的 bucket 大小和 bucket 内元素顺序。
```

不是“模型的所有参数张量必须一样大”。

### 1.3 `M` 不能被 `N` 整除怎么办？

以最容易理解的等分 ReduceScatter 为例，`M` 最好能被 `N` 整除。

```text
M = 1,025，N = 4
1,025 / 4 不能得到整数个元素
```

工程实现通常会采用以下之一：

1. 在 bucket 末尾补齐（padding）到可整除的长度；
2. 将不规则部分拆到单独的通信操作；
3. 使用框架/库提供的更高层分片逻辑处理尾部。

补齐的元素只是为了通信分块对齐；在计算结果中会被忽略，不代表真实梯度。

### 1.4 一个容易踩的坑：所有 rank 必须以相同顺序调用 collective

4 张 GPU 都要参与同一个 collective，而且调用顺序必须一致：

```text
所有 GPU：先对 bucket 0 调 ReduceScatter
所有 GPU：再对 bucket 1 调 ReduceScatter
所有 GPU：最后对 bucket 2 调 ReduceScatter
```

如果 GPU0 在等待 `bucket 0`，但 GPU1 已经跳去执行 `bucket 1`，各 rank 会互相等待，通常导致卡死或通信错误。

这也是分布式训练框架会严格维护参数注册顺序、bucket 顺序和 collective 调度顺序的原因。

## 2. ReduceScatter：接口保证的结果

概念上的调用为：

```cpp
ncclReduceScatter(sendbuf, recvbuf, M/4, datatype, ncclSum, comm, stream);
```

`sendbuf` 有 `M` 个元素；每张 GPU 的 `recvbuf` 只有 `M/4` 个元素。

对 rank 为 `r` 的 GPU，NCCL 保证：`recvbuf` 得到全局张量的第 `r` 个 chunk。

因此，完成后：

```text
GPU0 recvbuf = S0 = A0+B0+C0+D0
GPU1 recvbuf = S1 = A1+B1+C1+D1
GPU2 recvbuf = S2 = A2+B2+C2+D2
GPU3 recvbuf = S3 = A3+B3+C3+D3
```

这是应用代码唯一应当依赖的结果。

> 重要：不要把某一种 Ring 的中间传输顺序理解为最终输出 chunk 的归属。NCCL 可以选择不同的 ring、channel、chunk 偏移和流水策略，但 API 的 rank-to-output 映射不变。

## 3. Ring ReduceScatter 内部在做什么

若采用单环，逻辑 ring 可写为：

```text
GPU0 → GPU1 → GPU2 → GPU3 → GPU0
```

总共执行 `N-1` 轮；4 张 GPU 即 3 轮。每一轮中，每张 GPU 同时：

1. 向 ring 的下一个 GPU 发送一个逻辑 chunk 或其部分归约结果；
2. 从上一个 GPU 接收一个逻辑 chunk 或其部分归约结果；
3. 将接收数据与自己相同 chunk 编号的本地数据做 `sum`；
4. 在下一轮将这个新得到的部分和继续向下游发送。

所以 chunk 是**错位并发**的。对 4 张 GPU 来说，同一轮里的 4 条边同时发生：

```text
第 1 轮：
  GPU0 → GPU1：发送 A3；GPU1 做 B3 += A3，得到 A3+B3
  GPU1 → GPU2：发送 B0；GPU2 做 C0 += B0，得到 B0+C0
  GPU2 → GPU3：发送 C1；GPU3 做 D1 += C1，得到 C1+D1
  GPU3 → GPU0：发送 D2；GPU0 做 A2 += D2，得到 D2+A2

第 2 轮：
  GPU0 → GPU1：发送 D2+A2；GPU1 做 B2 += D2+A2，得到 D2+A2+B2
  GPU1 → GPU2：发送 A3+B3；GPU2 做 C3 += A3+B3，得到 A3+B3+C3
  GPU2 → GPU3：发送 B0+C0；GPU3 做 D0 += B0+C0，得到 B0+C0+D0
  GPU3 → GPU0：发送 C1+D1；GPU0 做 A1 += C1+D1，得到 C1+D1+A1

第 3 轮：
  GPU0 → GPU1：发送 C1+D1+A1；GPU1 做 B1 += ...，得到 S1
  GPU1 → GPU2：发送 D2+A2+B2；GPU2 做 C2 += ...，得到 S2
  GPU2 → GPU3：发送 A3+B3+C3；GPU3 做 D3 += ...，得到 S3
  GPU3 → GPU0：发送 B0+C0+D0；GPU0 做 A0 += ...，得到 S0
```

注意这里的顺序不是“先算完 `S0` 再算 `S1`”。更准确地说：

```text
S0 的最后一步发生在 GPU3 → GPU0
S1 的最后一步发生在 GPU0 → GPU1
S2 的最后一步发生在 GPU1 → GPU2
S3 的最后一步发生在 GPU2 → GPU3
```

这就是“错位”的含义：每个 chunk 都在路上，每一轮都继续向下游推进一跳。

真实 NCCL 还会把逻辑 chunk 切成更小的 slice 做流水。于是物理链路上通常有连续的数据流，而不是一轮只传一次大包。

### 为什么是 `N-1` 轮，而不是 `N` 轮？

每个 chunk 在开始时已经包含一个 GPU 的本地数据。它只需要再经过其余 `N-1` 张 GPU，便完成全局归约：

```text
本地值（已包含 1 份）
  → 融合第 2 张 GPU 的值
  → 融合第 3 张 GPU 的值
  → ...
  → 融合第 N 张 GPU 的值
```

AllGather 同样是 `N-1` 轮：每张 GPU 一开始已有自己的 1 个 chunk，只需从其余 `N-1` 张 GPU 收齐其余 chunk。

### 一个接收归约动作

例如接收端 GPU1 收到某个 `A3`：

```text
发送端 GPU0：读取 A3 并发送
接收端 GPU1：B3 += A3
结果：A3+B3
```

“发送”是读取发送缓冲区并传输，**不是剪切**数据；GPU0 上的 `A3` 不会因此自动变成 0。

## 4. Out-of-place 与 in-place

### Out-of-place（最容易理解）

`sendbuf` 和 `recvbuf` 是不同内存。

```text
GPU0 sendbuf: [A0, A1, A2, A3]
GPU0 recvbuf: [S0]
```

ReduceScatter 的输出只有 `[S0]`。其余输入内容不属于输出。

### In-place（复用完整 M 缓冲区）

可以在完整输入缓冲区里为本 rank 的输出预留对应槽位。概念上：

```text
GPU0: recvbuf = sendbuf + 0 × (M/4)
GPU1: recvbuf = sendbuf + 1 × (M/4)
GPU2: recvbuf = sendbuf + 2 × (M/4)
GPU3: recvbuf = sendbuf + 3 × (M/4)
```

操作结束后，可能将这块完整缓冲区画成：

```text
GPU0: [S0, A1, A2, A3]  # 只有 S0 有效
GPU1: [B0, S1, B2, B3]  # 只有 S1 有效
GPU2: [C0, C1, S2, C3]  # 只有 S2 有效
GPU3: [D0, D1, D2, S3]  # 只有 S3 有效
```

但这只是帮助理解“输出写回哪个槽位”的示意。除本 rank 的 `S_r` 外，其他位置：

- 可能仍保留旧输入；
- 可能被 NCCL 用作临时/流水数据而覆盖；
- 不属于 ReduceScatter 输出，程序不得读取或依赖。

因此，下面的理解是错误的：

```text
GPU0: [A0, S1, A2, A3]
```

在标准 NCCL ReduceScatter 语义中，GPU0 的有效结果应为 `S0`，不是 `S1`。

## 5. AllGather：只使用每张卡的有效输出 chunk

![4 GPU Ring AllGather 步骤图](https://lijiawang.oss-cn-hangzhou.aliyuncs.com/20260625153805256.png)

ReduceScatter 后，各 GPU 的有效输入是：

```text
GPU0 提供 S0
GPU1 提供 S1
GPU2 提供 S2
GPU3 提供 S3
```

概念上的调用为：

```cpp
ncclAllGather(sendbuf, recvbuf, M/4, datatype, comm, stream);
```

这里每张 GPU 的 `sendbuf` 为一个 `M/4` 大小的有效 chunk；`recvbuf` 为容纳完整 `M` 元素结果的缓冲区。

AllGather 将这些 chunk 分发到每一张 GPU。完成后每张 GPU 都有：

```text
[S0, S1, S2, S3]
```

也就是：

```text
[
  A0+B0+C0+D0,
  A1+B1+C1+D1,
  A2+B2+C2+D2,
  A3+B3+C3+D3
]
```

AllGather **不会读取** in-place 缓冲区里残留的 `A1/A2/A3` 等旧值；它只以每个 rank 的有效 `S_r` 为输入。

对 in-place AllGather，可将最终完整输出缓冲区理解为预先已放有本 rank 的那一块：

```text
GPU0: [S0,  _,  _,  _]
GPU1: [ _, S1,  _,  _]
GPU2: [ _,  _, S2,  _]
GPU3: [ _,  _,  _, S3]
```

其余槽位由 AllGather 填满，最终每张卡均为 `[S0, S1, S2, S3]`。

## 6. 与 AllReduce 的关系

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

### 6.1 三个 collective 的输入与输出对比

以 `N` 张 GPU、每张输入 `M` 个元素为例：

| 操作 | 每张 GPU 的输入 | 每张 GPU 的输出 | 典型用途 |
|---|---:|---:|---|
| AllReduce | `M` | `M` | 数据并行梯度同步 |
| ReduceScatter | `M` | `M/N` | ZeRO/FSDP 等分片梯度或分片优化器状态 |
| AllGather | `M/N` | `M` | 将分片参数/梯度临时恢复为完整张量 |

`AllReduce` 可以用“先 ReduceScatter、再 AllGather”理解：前半段完成求和并分片，后半段将分片广播回每一张卡。

### 6.2 通信量的直觉

在理想的单 Ring 模型中，每张 GPU 在 ReduceScatter 中发送和接收的数据量都约为：

```text
(N-1) × (M/N)
```

AllGather 也是相同数量级。因此完整 Ring AllReduce 中，每张 GPU 总发送量约为：

```text
2 × (N-1) × (M/N)
```

当 `N` 很大时，这接近 `2M`。Ring 的好处在于每轮每条相邻链路都可持续工作，不会让所有 GPU 同时争抢单个中心节点。

## 7. 常见误解检查表

| 误解 | 正确理解 |
|---|---|
| “发送后源 GPU 的数据会变成 0。” | 发送是读取并传输；源数据不会因为发送而自动清零。 |
| “先归约完整 S0，再归约 S1。” | 所有 chunk 错位并发地在 Ring 中推进。 |
| “GPU0 最终拿哪个 chunk 由 Ring 方向决定。” | 对 NCCL API，GPU0 的有效输出固定为 `S0`；内部 Ring 可自由选择实现。 |
| “AllGather 会继续用输入缓冲区中残留的旧 A/B/C/D 数据。” | 不会；它只使用每张 GPU 的有效 `S_r`。 |
| “一次 collective 里所有模型参数都要一样大。” | 不需要；要求相同的是每张 GPU 为该次 collective 准备的 bucket。 |

## 8. 实战检查清单

发起一次 collective 前，确认：

1. 所有 rank 都加入同一个 communicator；
2. 所有 rank 调用的是同一种 collective；
3. 所有 rank 按相同顺序调用 collective；
4. 对同一次调用，元素数、数据类型和归约操作匹配；
5. collective 在 CUDA stream 上异步执行；在 GPU 操作完成前，不要读写相关 buffer。

## 9. 一句话记忆

> ReduceScatter：第 `r` 张 GPU 只保留第 `r` 个全局归约 chunk `S_r`；AllGather：把所有 `S_r` 重新拼回每张 GPU。
