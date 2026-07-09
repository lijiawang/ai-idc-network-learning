# 大模型训练和推理中的 DP、TP、PP、EP，到底有什么区别？

刚开始学习大模型时，经常会遇到几个缩写：

```shell
DP / TP / PP / EP
```

它们都叫“并行”，但并行的对象完全不同。

先记一句话：

```shell
DP：Data Parallel，数据并行，主要切数据或请求
TP：Tensor Parallel，张量并行，主要切层内矩阵
PP：Pipeline Parallel，流水线并行，主要切模型层
EP：Expert Parallel，专家并行，主要切 MoE 专家
```

再进一步：

```shell
训练阶段：目标是把模型参数训练出来
推理阶段：目标是用训练好的模型回答用户问题
```

所以同样是 DP、TP、PP、EP，在训练和推理里的运行方式、通信内容、性能瓶颈都不一样。

说明一下：本文主要以常见的 decoder-only 自回归大语言模型为例，也就是现在大多数通用 LLM 的形态。其他模型形态也会用并行，但训练目标和推理流程可能会有差异。

---

## 一、先理解大模型是怎么训练出来的

大模型不是靠人工写一堆规则写出来的，而是靠大量数据反复训练出来的。

最核心的训练目标可以简单理解为：

```shell
根据前面的 token，预测下一个 token
```

比如训练数据里有一句话：

```shell
Kubernetes 的最小调度单位是 Pod
```

模型会被训练成：

```shell
看到：Kubernetes 的最小调度单位是
预测：Pod
```

如果模型预测错了，就根据错误程度调整参数。这个过程会重复非常多次。

一个训练 step 通常是这样：

```shell
读取数据
  ↓
forward 前向计算
  ↓
loss 计算误差
  ↓
backward 反向传播（得到各参数梯度）
  ↓
梯度同步（普通 DP/DDP 常用 All-Reduce 聚合多副本梯度）
  ↓
optimizer 更新参数
  ↓
进入下一个 step
```

注意：单卡训练没有"梯度同步"这一步；但对普通 DP/DDP 来说，backward 之后、optimizer 之前需要让各副本拿到等价的全局梯度，否则各副本参数会越训越不一致。ZeRO、FSDP、分布式优化器这类方案会把参数、梯度或优化器状态切片，通信形式可能变成 Reduce-Scatter / All-Gather 等，但目标仍然是让各副本的参数更新保持一致。

这几个词很重要，先解释一下。

### 1. forward：前向计算

forward 就是模型根据输入算出预测结果。

例如：

```shell
输入：Kubernetes 的最小调度单位是
正确答案：Pod
```

模型可能会输出：

```shell
Pod：10%
Service：40%
Node：30%
Container：20%
```

这个“从输入到预测结果”的过程，就是 forward。

换句话说：

```shell
forward = 模型做题
```

### 2. loss：损失值

loss 用来衡量模型预测得有多差。

正确答案是 `Pod`，但模型只给了 `Pod` 10% 的概率，说明它没答好，loss 就会比较高。

如果模型输出变成：

```shell
Pod：90%
Service：5%
Node：3%
Container：2%
```

loss 就会比较低。

所以：

```shell
loss = 模型答题后的扣分
```

### 3. backward：反向传播

backward 是根据 loss 反过来计算：

```shell
哪些参数导致了这次错误？
每个参数应该往哪个方向调整？
应该调整多少？
```

这个“参数应该怎么调整”的信号叫做梯度，也就是 gradient。

所以：

```shell
backward = 根据扣分结果，计算每个参数应该怎么改
```

### 4. gradient：梯度

梯度可以理解为模型参数的修改建议。

比如：

```shell
参数 A：应该 +0.001
参数 B：应该 -0.003
参数 C：应该 +0.0007
```

大模型有几十亿、几百亿甚至更多参数，backward 要为这些参数计算梯度。

### 5. optimizer：优化器

optimizer 是真正根据梯度更新参数的模块。

训练过程可以理解成：

```shell
forward：模型预测
loss：计算预测错了多少
backward：计算参数该怎么改
optimizer：真正更新参数
```

更新很多很多次后，模型就逐渐学会了语言、知识、代码、推理模式。

---

## 二、再理解推理是怎么回事

推理就是用训练好的模型回答问题。

训练时模型参数会不断变化；推理时模型参数通常是固定的。

推理过程大概是：

```shell
用户输入 prompt
  ↓
tokenizer 把文本切成 token
  ↓
模型 forward
  ↓
生成下一个 token
  ↓
继续生成下一个 token
  ↓
直到生成完整回答
```

更细一点，推理通常可以分成两段：

```shell
prefill：一次性处理用户 prompt，建立 KV Cache，并得到第一个输出 token 的 logits
decode：利用已有 KV Cache，一个 token 一个 token 继续生成
```

推理没有：

```shell
loss
backward
gradient
optimizer 参数更新
```

它的模型计算主要是 forward，另外还有采样、调度、缓存管理这些服务逻辑，不做训练意义上的参数更新。

但是推理并不简单，因为大模型是自回归生成的。

所谓自回归，就是一个 token 一个 token 地生成：

```shell
生成第 1 个 token
生成第 2 个 token
生成第 3 个 token
...
```

每生成一个 token，都要经过很多层 Transformer 计算。

所以推理阶段重点关注：

```shell
能不能放下模型
首 token 快不快
每个 token 生成快不快
并发请求多不多
显存里的 KV Cache 会不会爆
```

---

## 三、几个后面会反复出现的术语

### 1. token

token 是模型处理文本的基本单位。

一句话不会直接按“字”或“词”进入模型，而是先被 tokenizer 切成 token。

例如：

```shell
我是大模型
```

可能会被切成：

```shell
我 / 是 / 大 / 模型
```

也可能是：

```shell
我 / 是 / 大模型
```

具体怎么切，取决于 tokenizer。

### 2. tokenizer

tokenizer 是分词器，负责把文本变成模型能处理的 token ID。

例如：

```shell
文本：我是大模型
token：我 / 是 / 大模型
token ID：101 / 234 / 9876
```

模型实际看到的是数字 ID，不是人类看到的文字。

### 3. batch、mini-batch、micro-batch

batch 是一批数据。

训练时不会一条一条样本训练，而是把多条样本组成一批。

```shell
batch = 一批训练样本
```

mini-batch 通常也是训练中一次处理的一小批样本。

micro-batch 是把一个 batch 再切小，常用于流水线并行 PP。

例如：

```shell
一个 batch 有 1024 条样本
切成 8 个 micro-batch
每个 micro-batch 有 128 条样本
```

PP 需要 micro-batch 来填满流水线，减少 GPU 等待。

### 4. activation

activation 是模型中间层的计算结果。

输入经过第 1 层后，会产生一份中间结果；再进入第 2 层，又产生新的中间结果。

这些中间结果就可以叫 activation。

训练时，activation 很重要，因为 backward 需要用它来计算梯度。

### 5. hidden state

hidden state 也是模型中间状态，通常指某一层输出的隐藏表示。

可以简单理解为：

```shell
hidden state = 模型内部对当前 token 的数字化理解
```

在 TP 或 PP 通信中，经常会传递 hidden state。

### 6. checkpoint

checkpoint 是训练过程中的模型快照。

训练可能跑几天甚至几个月，中间机器故障、任务中断都很正常。为了不从头开始，需要定期保存 checkpoint。

checkpoint 里通常包含：

```shell
模型参数
优化器状态
训练 step
随机数状态
其他恢复训练需要的信息
```

### 7. All-Reduce

All-Reduce 是一种集合通信操作。

它做两件事：

```shell
Reduce：把多张 GPU 上的数据聚合，比如求和
All：把聚合结果发给所有 GPU
```

例如 4 张 GPU 各有一个数：

```shell
GPU0：1
GPU1：2
GPU2：3
GPU3：4
```

All-Reduce 求和后，每张 GPU 都拿到：

```shell
10
```

为了讲清楚，这里用标量举例子。实际训练里 All-Reduce 的是张量（几亿维的梯度向量），求和也是逐元素相加，不是单个数。

训练 DP 里的梯度同步经常用 All-Reduce。

推理 TP 里也可能用 All-Reduce，但同步的不是梯度，而是前向计算里的部分结果。

### 8. All-Gather

All-Gather 是把多张 GPU 上各自持有的一部分数据收集起来，让每张 GPU 都拿到完整数据。

例如：

```shell
GPU0：A
GPU1：B
GPU2：C
GPU3：D
```

All-Gather 后，每张 GPU 都拿到：

```shell
[A, B, C, D]   （拼接成完整数据，而不是相加）
```

注意：All-Reduce 是"先聚合（如求和）再广播"，All-Gather 是"只拼接不聚合"，这是两者最本质的区别。

TP 中 column parallel（列切分）在需要还原完整输出时会用到 All-Gather；如果后续层可以直接消费切分后的 hidden state，一些框架会暂时不 gather。

### 9. Reduce-Scatter

Reduce-Scatter 可以理解为：

```shell
先 Reduce 聚合，再 Scatter 分发切片
```

它不会让每张 GPU 都拿完整结果，而是每张 GPU 拿聚合结果的一部分。

在大模型训练里，Reduce-Scatter 常用于 ZeRO、FSDP、张量并行等场景，帮助降低显存和通信压力。

### 10. All-to-All

All-to-All 是每张 GPU 都给其他 GPU 发不同的数据。

MoE 的 EP 经常用 All-to-All。

因为每个 token 会被 router 分配给不同 expert，而 expert 又分布在不同 GPU 上，所以需要把 token 发到对应 expert 所在的 GPU。

例如 4 张 GPU，每张 GPU 上都有一批 token，router 把它们分配到分散在 4 张 GPU 上的不同 expert：

```shell
        发往 GPU0  发往 GPU1  发往 GPU2  发往 GPU3
GPU0 自留  → GPU1   → GPU2   → GPU3
GPU1 → GPU0   自留  → GPU2   → GPU3
GPU2 → GPU0  → GPU1   自留  → GPU3
GPU3 → GPU0  → GPU1  → GPU2   自留
```

也就是说：每张 GPU 都同时给其他所有 GPU 发"去往那边 expert 的 token"，同时也在收其他 GPU 发来的 token。这种"所有 GPU 两两之间都在交换不同数据"的通信模式，就是 All-to-All。

这就是 All-to-All 的典型场景。

### 11. KV Cache

KV Cache 是推理阶段非常重要的显存占用。

Transformer 的 Attention 会用到 K 和 V，也就是 Key 和 Value。

自回归生成时，前面已经算过的 token 的 K/V 不需要每次重新算，可以缓存下来。

这份缓存就是 KV Cache。

KV Cache 的好处是加速生成，坏处是会占用显存。

请求越多、上下文越长、生成越长，KV Cache 越大。

### 12. TTFT 和 TPOT

TTFT 是 Time To First Token，首 token 延迟。

也就是：

```shell
用户发出请求后，多久看到第一个 token
```

TPOT 是 Time Per Output Token，每个输出 token 的耗时。

也就是：

```shell
模型生成后续每个 token 平均要多久
```

推理优化时，经常会同时看 TTFT 和 TPOT。

一般来说，TTFT 更容易受到排队、prefill 和首个 decode 的影响；TPOT 更能反映 decode 阶段持续生成 token 的速度。

### 13. QPS 和吞吐

QPS 是每秒请求数。

吞吐可以有多种口径，例如：

```shell
每秒处理多少请求
每秒生成多少 token
每秒处理多少输入 token + 输出 token
```

大模型服务里，经常用 tokens/s 表示吞吐。

---

## 四、DP：训练同步梯度，推理复制副本

DP 是 Data Parallel，数据并行。

### 1. 训练时的 DP

训练时，DP 会复制多份模型副本，每个副本处理不同的数据。

例如 4 组 GPU：

```shell
DP0：训练 batch A
DP1：训练 batch B
DP2：训练 batch C
DP3：训练 batch D
```

每个 DP 副本都会执行：

```shell
forward -> loss -> backward
```

然后每个副本得到自己的梯度：

```shell
DP0：gradient_A
DP1：gradient_B
DP2：gradient_C
DP3：gradient_D
```

如果它们各自更新参数，模型副本就会越来越不一样。

所以普通训练 DP/DDP 通常需要做梯度 All-Reduce：

```shell
average_gradient =
  (gradient_A + gradient_B + gradient_C + gradient_D) / 4
```

然后所有副本都用同一份平均梯度更新参数。

训练 DP 的核心是：

```shell
不同数据
相同模型副本
同步梯度
保持参数一致
```

### 2. 推理时的 DP

推理时，DP 更像多开几个模型服务副本。

```shell
请求 A -> Replica 0
请求 B -> Replica 1
请求 C -> Replica 2
请求 D -> Replica 3
```

每个副本加载同一份模型权重，但互相之间通常不需要同步。

推理 DP 没有：

```shell
backward
gradient
optimizer
梯度 All-Reduce
```

它的核心是：

```shell
多份模型副本
分摊用户请求
提高并发吞吐
```

### 3. DP 小结

```shell
训练 DP：多个副本训练不同 batch，最后同步梯度
推理 DP：多个副本处理不同请求，副本之间基本独立
```

---

## 五、TP：训练和推理都会有层内通信

TP 是 Tensor Parallel，张量并行。

它解决的问题是：

```shell
单层矩阵太大，一张 GPU 放不下或算不快
```

Transformer 里有大量矩阵乘法：

```shell
Y = XW
```

其中：

```shell
X：输入
W：权重矩阵
Y：输出
```

如果 W 很大，可以把 W 切到多张 GPU 上。

### 1. 训练时的 TP

训练 TP 会把一层内部的计算拆给多张 GPU。

切法主要有两种，和推理 TP 一致：

```shell
row parallel（行切分）：按 W 的行切，各 GPU 算出 partial_Y，需要 All-Reduce 求和
column parallel（列切分）：按 W 的列切，各 GPU 算出输出的不同列；如果后续需要完整 Y，就 All-Gather 拼接
```

例如：

```shell
GPU0：计算 W 的一部分
GPU1：计算 W 的一部分
GPU2：计算 W 的一部分
GPU3：计算 W 的一部分
```

forward 时，各 GPU 需要完成必要的结果合并。row parallel 通常会用 All-Reduce 聚合 partial output；column parallel 是否 All-Gather，取决于后续层是否需要完整 hidden state。Megatron 这类实现里，经常会让 column parallel 的输出继续保持切分状态，直接交给后面的 row parallel 层消费，从而少做一次 gather。

backward 时，各 GPU 还要计算梯度，并完成反向传播需要的通信。

所以训练 TP 的特点是：

```shell
forward 有通信
backward 也有通信
参数会更新
```

### 2. 推理时的 TP

推理 TP 也会切矩阵。

区别是推理没有 backward，也没有梯度同步。

但是要特别注意：

```shell
推理 TP 仍然可能有 All-Reduce
```

只是这个 All-Reduce 同步的不是梯度，而是 forward 中的部分结果。

例如 row parallel 场景：

```shell
GPU0：partial_Y0
GPU1：partial_Y1
GPU2：partial_Y2
GPU3：partial_Y3
```

真正的输出是：

```shell
Y = partial_Y0 + partial_Y1 + partial_Y2 + partial_Y3
```

这时就需要 All-Reduce，把各 GPU 的 partial output 加起来。

如果是 column parallel（列切分），则各 GPU 拿到的是输出的不同列。需要完整输出时，要用 All-Gather 把它们拼回完整输出，而不是求和；如果下一层能直接处理切分后的 hidden state，也可以先不 gather。

也就是说：

```shell
训练 DP 的 All-Reduce：同步梯度
推理 TP 的 All-Reduce：同步前向计算结果
```

这两个都叫 All-Reduce，但目的完全不同。

### 3. TP 为什么影响推理延迟

推理是逐 token 生成。

每生成一个 token，都要跑很多层。

如果每层都有 TP 通信，那么生成每个 token 时都会遇到跨 GPU 通信。

所以 TP 推理会影响：

```shell
TTFT：首 token 延迟
TPOT：每 token 生成耗时
tokens/s：整体吞吐
```

TP 通常更适合放在单机内部高速互联里，比如 NVLink / NVSwitch。

跨机器做 TP 也可以，但每层频繁通信，延迟和带宽压力会明显增加。

### 4. TP 小结

```shell
训练 TP：切层内矩阵，forward/backward 都有通信
推理 TP：切层内矩阵，只做 forward，但仍可能有 All-Reduce
```

---

## 六、PP：训练用 micro-batch 填流水线，推理按层串行经过

PP 是 Pipeline Parallel，流水线并行。

它解决的问题是：

```shell
模型层数太多，一张 GPU 或一组 GPU 放不下完整模型
```

PP 会按层切模型。

例如一个 80 层模型，可以切成 4 个 stage：

```shell
Stage 0：Layer 1-20
Stage 1：Layer 21-40
Stage 2：Layer 41-60
Stage 3：Layer 61-80
```

### 1. 训练时的 PP

训练时，一个 micro-batch 会依次经过各个 stage：

```shell
forward:
Stage0 -> Stage1 -> Stage2 -> Stage3

backward:
Stage3 -> Stage2 -> Stage1 -> Stage0
```

如果只有一个 micro-batch，很多 stage 会等待。

例如一开始：

```shell
Stage0 在工作
Stage1 等 Stage0 的输出
Stage2 等 Stage1 的输出
Stage3 等 Stage2 的输出
```

这些等待时间叫做 pipeline bubble，也就是流水线气泡。

为了减少气泡，会把 batch 切成多个 micro-batch，让流水线尽量连续工作。

更进一步，主流做法是 **1F1B 调度（one forward one backward）**：不是把所有 micro-batch 的 forward 全做完再做 backward，而是在 warmup 之后进入稳定状态，每个 stage 交替执行一个 forward 和一个 backward。这样做有两个好处：

```shell
1. 减少气泡：forward 和 backward 交错，让前后 stage 更快进入工作状态
2. 省显存：尽早启动 backward，就能尽早释放该 micro-batch 的 activation
```

再进一步还有 **interleaved schedule（虚拟流水线）**：把每个 stage 再切成多个虚拟 chunk，让通信和计算更细粒度地交错，进一步压缩 bubble。代价是通信量增加。Megatron-LM / Megatron-Core 支持 interleaved 1F1B，但通常需要通过 virtual pipeline 相关配置开启；基础 1F1B 不等于默认 interleaved。

### 2. 推理时的 PP

推理时，PP 也按层切模型。

请求会这样走：

```shell
输入 -> Stage0 -> Stage1 -> Stage2 -> Stage3 -> 输出
```

推理没有 backward，所以只传 forward 的 hidden state。

但推理是逐 token 生成，每个 token 都要穿过所有 stage。

因此 PP 推理的一个问题是：

```shell
链路变长，单请求延迟可能变高
```

不过在高并发场景下，可以把不同请求或不同 token 放进流水线里，提高整体吞吐。所以 PP 对显存和吞吐有价值，但不保证降低单请求端到端延迟。

另外，推理时每个 stage 会保存自己负责层的 KV Cache。

例如：

```shell
Stage0 保存 Layer 1-20 的 KV Cache
Stage1 保存 Layer 21-40 的 KV Cache
Stage2 保存 Layer 41-60 的 KV Cache
Stage3 保存 Layer 61-80 的 KV Cache
```

同一个会话后续生成 token 时，最好继续走同一条 PP 链路，否则 KV Cache 管理会变复杂。

### 3. PP 小结

```shell
训练 PP：用 micro-batch 填流水线，减少 bubble
推理 PP：请求逐层经过多个 stage，重点关注延迟和 KV Cache
```

---

## 七、EP：MoE 模型里的专家并行

EP 是 Expert Parallel，专家并行。

它主要用于 MoE 模型。

普通 Dense 模型没有 expert，所以一般不谈 EP。

### 1. 什么是 MoE

MoE 是 Mixture of Experts，混合专家模型。

它的核心结构是：

```shell
Token -> Router -> 选择 Top-K Expert -> Expert 计算 -> 合并结果
```

"合并结果"不是简单拼接，而是按 router 给每个被选中 expert 的权重（gate score）做**加权求和**。例如 token 选了 Expert 2（权重 0.7）和 Expert 7（权重 0.3），最终输出 = 0.7×Expert2输出 + 0.3×Expert7输出。

可以理解为：

```shell
模型里有很多 expert
每个 token 不会激活所有 expert
router 会选择少数几个 expert 来处理这个 token
```

例如：

```shell
Token A -> Expert 2, Expert 7
Token B -> Expert 1, Expert 7
Token C -> Expert 4, Expert 9
```

### 2. 什么是 expert

expert 可以理解为 MoE 层里的一个子网络。

每个 expert 通常是一个小的前馈网络。

MoE 的特点是：

```shell
总参数量很大
但每个 token 只激活其中一小部分参数
```

这让模型可以拥有更大的参数规模，同时控制每次计算的成本。

### 3. 什么是 router

router 是路由器，也叫 gate。

它负责判断每个 token 应该送给哪些 expert。

例如：

```shell
router 看到 Token A
判断 Expert 2 和 Expert 7 最适合处理它
于是把 Token A 发给这两个 expert
```

### 4. 训练时的 EP

训练 EP 会把不同 expert 放到不同 GPU 上。

例如：

```shell
GPU0：Expert 0, 1
GPU1：Expert 2, 3
GPU2：Expert 4, 5
GPU3：Expert 6, 7
```

训练时流程大概是：

```shell
router 选择 expert
  ↓
All-to-All 把 token 发到 expert 所在 GPU
  ↓
expert forward
  ↓
All-to-All 把结果发回来
  ↓
backward 计算梯度
  ↓
更新 router 和 expert 参数
```

训练 EP 会涉及：

```shell
token 路由
All-to-All 通信
expert forward
expert backward
router 梯度
expert 参数更新
负载均衡 loss
```

这里有一个常见问题：expert 负载不均。

如果大量 token 都被分到同一个 expert：

```shell
Expert 7：10000 个 token
Expert 2：500 个 token
```

Expert 7 所在 GPU 就会变成瓶颈，整体训练速度被拖慢。

所以 MoE 训练通常会加入负载均衡相关的 loss，让 router 尽量不要把 token 都发给少数 expert。也有一些新模型会用 auxiliary-loss-free 的负载均衡方式，例如给 expert 动态调整 bias，本质目标仍然是避免少数 expert 过热。

另外说清 EP 和 DP 的关系：一种常见布局是 EP 嵌套在 DP 组内运行。一个 DP 副本内部，expert 分散到该副本的多张 GPU（这就是 EP 维度）；而多个 DP 副本各自独立持有一套完整的 expert 集合。所以可以看到 `DP × EP` 这样的配置。

但这不是唯一组织方式。现代训练和推理框架经常用 device mesh 把 DP、TP、PP、EP 组合起来，EP 和 DP 的边界会根据框架、模型结构和部署目标变化。对入门理解来说，先记住：DP 主要复制数据/请求维度，EP 主要切分 MoE expert 维度。

### 5. 推理时的 EP

推理 EP 没有 backward，也不会更新 expert 参数。

流程变成：

```shell
router 选择 expert
  ↓
All-to-All 把 token 发到 expert 所在 GPU
  ↓
expert forward
  ↓
All-to-All 把结果发回来
  ↓
继续生成 token
```

推理 EP 的问题主要是：

```shell
All-to-All 延迟
hot expert 热点
请求负载不均
```

如果很多请求都命中同一个 expert，这个 expert 所在 GPU 会变忙，影响整体延迟。

针对 hot expert 热点，推理侧会用 **expert duplication / redundant experts**：把高频被命中的 expert 复制几份放到不同 GPU，分摊请求；router 或调度器在多个副本间做负载均衡。代价是显存增加（同一份 expert 权重存多份），换来的是吞吐和延迟改善。DeepSeek 的 EPLB 思路、vLLM 的 MoE 推理都有类似机制。

### 6. EP 小结

```shell
训练 EP：训练 router 和 expert，有 forward/backward/参数更新
推理 EP：只做 router 路由和 expert forward，不更新参数
```

---

## 八、四种并行方式放在一起看

| 并行方式 | 切什么 | 训练时主要做什么 | 推理时主要做什么 |
|---|---|---|---|
| DP | 数据 / batch / 请求 | 多副本处理不同 batch，同步梯度 | 多副本处理不同请求，提高并发 |
| TP | 层内矩阵 | 拆矩阵做 forward/backward | 拆矩阵做 forward，可能有 All-Reduce |
| PP | 模型层 | 拆层，用 micro-batch 跑流水线 | 拆层，请求依次经过多个 stage |
| EP | MoE expert | token 路由到 expert，训练 router/expert | token 路由到 expert，只做 forward |

再用一句话记：

```shell
DP：多份模型，吃不同数据或请求
TP：一层太大，把矩阵拆开
PP：模型太深，把层拆开
EP：专家太多，把 expert 拆开
```

---

## 九、训练和推理的核心区别

训练阶段：

```shell
有 forward
有 loss
有 backward
有 gradient
有 optimizer
有参数更新
有 checkpoint
```

推理阶段：

```shell
主要是 forward
没有 loss
没有 backward
没有 gradient
没有 optimizer 更新
有 KV Cache
关注 TTFT / TPOT / tokens/s
```

所以同样一个并行方式，在训练和推理里的含义会变。

例如：

```shell
训练 DP 的 All-Reduce：同步梯度
推理 TP 的 All-Reduce：同步前向计算结果
```

两个都叫 All-Reduce，但同步的数据完全不同。

---

## 十、实际会怎么组合

真实的大模型通常不会只用一种并行方式。

### 1. 普通 Dense 大模型训练

Dense 模型没有 MoE expert，一般不会用 EP。

常见组合是：

```shell
DP + TP + PP
```

也就是常说的 3D 并行。

需要注意的是，纯 DP 每个副本都存一份完整模型参数和优化器状态，显存浪费严重。现代训练常用 ZeRO（DeepSpeed）、FSDP（PyTorch）或分布式优化器来切分参数、梯度或优化器状态。它们可以理解为沿着数据并行维度做分片的显存优化方案，可以和 TP/PP 叠加使用。

例如：

```shell
总 GPU = DP x TP x PP
128 = 4 x 8 x 4
```

含义是：

```shell
4 个数据并行副本
每个副本内部有 4 个流水线 stage
每个 stage 内部用 8 张 GPU 做张量并行
```

### 2. MoE 大模型训练

MoE 模型还会引入 EP：

```shell
DP + TP + PP + EP
```

EP 只作用在 MoE expert 相关部分，普通 dense 层仍然可能主要用 TP/PP/DP。

### 3. Dense 大模型推理

推理时，如果模型单卡能放下，想提高并发，可以先用 DP：

```shell
DP = 多个模型副本
```

如果模型单卡放不下，可以用 TP：

```shell
TP = 多张 GPU 合起来跑一个模型副本
```

如果模型层数太多，TP 还不够，可以加 PP：

```shell
TP + PP = 矩阵切分 + 层切分
```

如果还要提高并发，再叠 DP：

```shell
DP x TP x PP
```

### 4. MoE 大模型推理

MoE 推理会用到 EP：

```shell
DP + TP + PP + EP
```

其中：

```shell
DP：复制多个服务副本
TP：切 dense 层或部分专家计算
PP：按层切模型
EP：把 expert 分散到不同 GPU
```

---

## 十一、几个容易混淆的问题

### 1. 推理 DP 和训练 DP 是一回事吗？

不是。

训练 DP：

```shell
不同副本训练不同 batch
通常需要梯度 All-Reduce
需要保持参数一致
```

推理 DP：

```shell
不同副本处理不同请求
不需要梯度同步
参数固定不变
```

### 2. 推理 TP 有没有 All-Reduce？

有可能有。

但它不是梯度 All-Reduce。

推理 TP 的 All-Reduce 通常用于合并 forward 里的 partial output。

```shell
训练 DP All-Reduce：同步 gradient
推理 TP All-Reduce：同步 hidden state / partial output
```

### 3. PP 是不是一定能降低延迟？

不一定。

PP 的主要价值是把模型按层放到多张 GPU 上，让大模型能跑起来。

但请求要经过多个 stage，链路变长后，单请求延迟可能反而上升。

PP 更适合模型太深、单个副本放不下的场景。

### 4. EP 是不是所有模型都有？

不是。

EP 只适用于 MoE 模型。

普通 Dense Transformer 没有 expert，因此没有 EP。

### 5. TP 越大越好吗？

不是。

TP 越大，单卡显存压力越小，单卡计算量也可能下降。

但 TP 越大，跨 GPU 通信越多。

如果通信拖慢计算，整体速度可能变差。

---

## 十二、最后总结

大模型训练和推理都需要并行，但目的不同。

训练是为了把模型参数学出来：

```shell
forward -> loss -> backward -> optimizer -> 更新参数
```

推理是为了用训练好的参数生成答案：

```shell
prompt -> forward -> token -> token -> token
```

DP、TP、PP、EP 可以这样记：

```shell
DP：训练同步梯度，推理复制副本
TP：训练切矩阵做前反向，推理切矩阵做前向且可能 All-Reduce
PP：训练用 micro-batch 填流水线，推理请求逐层穿过 stage
EP：训练 MoE router 和 expert，推理 MoE token 路由到 expert
```

最核心的一句话：

```shell
DP 管数据和请求，TP 管层内矩阵，PP 管模型层，EP 管 MoE 专家。
```

理解这句话，再看各种大模型训练和推理框架里的并行配置，就不会只是在背缩写了。
