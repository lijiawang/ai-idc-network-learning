# WaaS MetaX C500 部署 Qwen3.5-4B：vLLM-MetaX 安装、模型服务与性能测试

这篇文章记录一次真实可复现的部署：在 WaaS 的单张 MetaX C500 容器中，使用 Python venv 和官方预编译 wheel 安装 vLLM-MetaX 0.21，部署 Qwen3.5-4B 的 OpenAI 兼容接口，并完成并发性能测试。

本文面向第一次接触 Linux、vLLM 和 MetaX 的读者。命令默认都在 C500 容器内执行。

> 本文的关键原则：不编译 vLLM，不把系统盘写满，不在服务启动时加载另一套完整 vLLM 做压测，模型、环境、缓存和日志统一放在数据盘 `/home/waas`。

## 一、本次部署结果

### 1.1 硬件和软件

| 项目 | 实测值 |
|---|---|
| GPU | 1 × MetaX C500 |
| 显存 | 64 GiB |
| 系统 | Ubuntu 24.04.1 LTS |
| Python | 3.12.3 |
| MACA | 3.7.2.0 |
| 驱动 | 3.8.23 |
| `mx-smi` | 2.3.1 |
| MetaX Torch | 2.8.0+metax3.7.2.0 |
| vLLM | 0.21.0 |
| vLLM-MetaX | 0.21.0+gfbfedf.d20260626.maca3.7.1.5.torch2.8 |
| 模型 | Qwen3.5-4B，BF16，约 8.68 GiB |
| API | `http://127.0.0.1:8000/v1` |
| 最大上下文 | 8192 token |

### 1.2 实际验证结果

- MetaX 插件成功激活，平台类为 `vllm_metax.platform.MxsmlMacaPlatform`。
- mcoplib 检查通过：构建 MACA 3.7.1.5 与运行时 MACA 3.7 主次版本匹配。
- Qwen3.5 架构成功识别为 `Qwen3_5ForConditionalGeneration`。
- `/v1/models` 与 `/v1/chat/completions` 均返回 HTTP 200。
- 官方 `vllm bench serve` 的随机集测试中，40 个请求、最大并发 4，成功 40、失败 0。
- 官方 Sonnet 测试中，10 个请求同时发出，成功 10、失败 0。

### 1.3 性能测试结果

服务使用 eager 模式。2026 年 7 月 26 日冷启动后，使用 vLLM 0.21 官方 `vllm bench serve` 重新验证。

| 数据集 | 请求数 | 峰值并发 | 成功率 | 总耗时 | 请求吞吐 | 输出吞吐 | 平均 TTFT | 平均 TPOT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Random，输入 128、输出 64 | 40 | 4 | 100% | 21.22 s | 1.89 req/s | 120.66 token/s | 96.97 ms | 32.12 ms/token |
| Sonnet，输入 256、输出 64、前缀 100 | 10 | 10 | 100% | 2.40 s | 4.16 req/s | 266.30 token/s | 195.57 ms | 34.90 ms/token |

这些数字是本机、本版本和本文参数下的实测结果，不应直接当成所有 C500 环境的理论峰值。输入长度、输出长度、并发、采样参数和图优化都会影响结果。

## 二、为什么这次不需要编译 vLLM

MetaX 官方文档同时介绍了 wheel 安装和源码构建，它们是两条不同路线。已经有匹配 Python、MACA 和 Torch 的官方预编译包时，应优先使用 wheel；源码构建不是必经步骤。

本次使用的是：

1. MetaX 官方 PyPI 仓库中的 MACA 适配 wheel：`https://repos.metax-tech.com/r/maca-pypi/simple`。
2. MetaX 软件中心列出的 `maca-vllm-metax-0.21.0-py312-3.7.1.106-linux-x86_64.tar.xz` 对应版本信息。
3. vLLM 0.21.0 的预编译 `cp38-abi3-manylinux_2_24_x86_64.whl`，没有从源码执行 `setup.py`、`pip wheel .` 或 CMake 构建。

MetaX 软件中心下载接口需要登录令牌，因此不能在匿名 shell 中直接下载软件中心压缩包。这个限制不代表必须编译：MetaX 依赖仍可以直接从官方 PyPI 安装，vLLM 核心也使用预编译 wheel。

启动日志中可能出现 `mcoplib during compilation`、Triton helper 或 Torch extension 的字样。这是预编译软件第一次运行时生成很小的运行时辅助模块，不是重新编译 vLLM。

## 三、规划目录，避免写满系统盘

本机系统盘为 100 GB，而 `/home/waas` 是容量充足的数据盘。因此把所有大文件放到数据盘：

```bash
mkdir -p /home/waas/{venvs,models,packages,logs,compat}
mkdir -p /home/waas/.cache/{pip,huggingface,torch_extensions}

export PIP_CACHE_DIR=/home/waas/.cache/pip
export HF_HOME=/home/waas/.cache/huggingface
export TORCH_EXTENSIONS_DIR=/home/waas/.cache/torch_extensions
```

随时检查空间：

```bash
df -h / /home/waas
du -sh /home/waas/models /home/waas/.cache 2>/dev/null
free -h
```

本次完成安装后，系统盘只使用约 1.4 GB；模型、虚拟环境和缓存都位于 `/home/waas`。

## 四、检查原始环境

### 4.1 查看 GPU

```bash
mx-smi
mx-smi --show-memory
```

应能看到 `MXC500`、一张卡和约 64 GiB 显存。

### 4.2 查看 Python 和 MACA

```bash
command -v python3
python3 --version
ls -ld /opt/maca
```

本机输出为 `/usr/bin/python3` 和 `Python 3.12.3`，MACA 安装在 `/opt/maca`。

## 五、先创建 venv，再安装官方 wheel

### 5.1 创建并激活环境

```bash
python3 -m venv /home/waas/venvs/vllm-metax
source /home/waas/venvs/vllm-metax/bin/activate

python -m pip install -U pip setuptools wheel
```

如果 `venv` 命令报缺少组件，再执行：

```bash
apt-get update
apt-get install -y python3.12-venv python3.12-dev
```

`python3.12-dev` 只提供 Python 头文件，供 Triton 第一次运行时生成辅助模块；它不用于编译 vLLM。

### 5.2 配置 MACA 环境

```bash
export MACA_PATH=/opt/maca
export CUCC_PATH=$MACA_PATH/tools/cu-bridge
export CUDA_PATH=$CUCC_PATH/CUDA_DIR
export CUCC_CMAKE_ENTRY=2

export PATH=/home/waas/venvs/vllm-metax/bin:$MACA_PATH/mxgpu_llvm/bin:$MACA_PATH/bin:$CUCC_PATH/tools:$CUCC_PATH/bin:$PATH
export LD_LIBRARY_PATH=$MACA_PATH/lib:$MACA_PATH/ompi/lib:$MACA_PATH/mxgpu_llvm/lib:${LD_LIBRARY_PATH:-}
export VLLM_PLUGINS=metax
```

### 5.3 使用 MetaX 官方 PyPI

官方索引地址：

```text
https://repos.metax-tech.com/r/maca-pypi/simple
```

实际安装的关键包版本如下：

```text
torch==2.8.0+metax3.7.2.0
vllm-metax==0.21.0+gfbfedf.d20260626.maca3.7.1.5.torch2.8
mcoplib==0.4.6+maca3.7.1.5.torch2.8
flash-attn==2.6.3+metax3.7.2.0torch2.8
flashinfer==0.2.6+metax3.7.2.0torch2.8
triton==3.0.0+metax3.7.2.0
```

安装时让 pip 直接访问官方仓库：

```bash
export PIP_CACHE_DIR=/home/waas/.cache/pip
METAX_INDEX=https://repos.metax-tech.com/r/maca-pypi/simple

python -m pip install --extra-index-url "$METAX_INDEX" \
  'torch==2.8.0+metax3.7.2.0' \
  'vllm-metax==0.21.0+gfbfedf.d20260626.maca3.7.1.5.torch2.8'
```

如果从 MetaX 软件中心下载了官方 0.21 安装包，应优先按压缩包中的版本清单和安装脚本操作。不要把不同 MACA、Torch、vLLM-MetaX 版本随意混装。

本机 vLLM 核心预编译包保存在：

```text
/home/waas/packages/vllm-0.21.0-1-cp38-abi3-manylinux_2_24_x86_64.whl
```

安装命令：

```bash
python -m pip install /home/waas/packages/vllm-0.21.0-1-cp38-abi3-manylinux_2_24_x86_64.whl
```

> 不要执行 `git clone vllm`、`pip install .` 或 `python setup.py bdist_wheel`。本环境没有源码编译 vLLM。

### 5.4 验证 Torch、GPU 和插件

```bash
python - <<'PY'
import torch
print("torch:", torch.__version__)
print("GPU 可用:", torch.cuda.is_available())
print("GPU 数量:", torch.cuda.device_count())
print("GPU 名称:", torch.cuda.get_device_name(0))

x = torch.randn(1024, 1024, device="cuda", dtype=torch.float16)
y = x @ x
print("矩阵乘成功:", y.shape, y.device)
PY
```

检查 vLLM 插件：

```bash
VLLM_PLUGINS=metax python - <<'PY'
from vllm.platforms import current_platform
print(current_platform)
PY
```

0.21 版 mcoplib 不再提供旧文档中的 `mcoplib_init` 命令。导入插件并看到 MACA 主次版本匹配成功，就是当前版本的检查方式。

## 六、MetaX Torch 2.8 最小兼容层

本次组合中，vLLM 0.21 会调用新版 `torch.accelerator` API，而 MetaX Torch 2.8 的具体实现仍在 `torch.cuda` 命名空间。不要修改 vLLM 源码，在独立目录增加最小别名即可。

创建 `/home/waas/compat/sitecustomize.py`：

```python
import torch

if hasattr(torch, "accelerator"):
    aliases = {
        "current_device_index": torch.cuda.current_device,
        "device_count": torch.cuda.device_count,
        "device_index": torch.cuda.device,
        "empty_cache": torch.cuda.empty_cache,
        "max_memory_allocated": torch.cuda.max_memory_allocated,
        "memory_reserved": torch.cuda.memory_reserved,
        "memory_stats": torch.cuda.memory_stats,
        "reset_peak_memory_stats": torch.cuda.reset_peak_memory_stats,
        "set_device_index": torch.cuda.set_device,
        "synchronize": torch.cuda.synchronize,
    }
    for name, function in aliases.items():
        if not hasattr(torch.accelerator, name):
            setattr(torch.accelerator, name, function)
```

启用方式：

```bash
export PYTHONPATH=/home/waas/compat
```

这是运行时 API 别名，不会编译或修改任何 wheel。以后升级到原生提供完整 `torch.accelerator` 的 MetaX Torch 后，可以先测试移除此兼容层。

## 七、准备 Qwen3.5-4B 模型

### 7.1 为什么使用 4B

用户要求使用小一些的模型。Qwen3.5-4B 的 BF16 权重约 8.68 GiB，单张 64 GiB C500 有足够空间留给 KV Cache，比 9B 更适合作为首次部署和接口验证模型。

模型目录：

```text
/home/waas/models/Qwen3.5-4B
```

检查文件：

```bash
du -sh /home/waas/models/Qwen3.5-4B
find /home/waas/models/Qwen3.5-4B -maxdepth 1 -type f -printf '%f\n' | sort
```

如果需要重新下载，可使用 ModelScope，并将缓存和目标目录放到数据盘：

```bash
source /home/waas/venvs/vllm-metax/bin/activate
python -m pip install modelscope

setsid nohup modelscope download \
  --model Qwen/Qwen3.5-4B \
  --local_dir /home/waas/models/Qwen3.5-4B \
  > /home/waas/logs/download-qwen35-4b.log 2>&1 &
```

下载时可以临时启用 WaaS 网络代理：

```bash
source /etc/waas-script/proxy.sh
```

下载结束后如不再需要代理：

```bash
source /etc/waas-script/unset_proxy.sh
```

## 八、启动和管理模型服务

### 8.1 后台启动

先进入虚拟环境并设置运行环境：

```bash
source /home/waas/venvs/vllm-metax/bin/activate

export MACA_PATH=/opt/maca
export CUCC_PATH=$MACA_PATH/tools/cu-bridge
export CUDA_PATH=$CUCC_PATH/CUDA_DIR
export CUCC_CMAKE_ENTRY=2
export PATH=/home/waas/venvs/vllm-metax/bin:$MACA_PATH/mxgpu_llvm/bin:$MACA_PATH/bin:$CUCC_PATH/tools:$CUCC_PATH/bin:$PATH
export LD_LIBRARY_PATH=$MACA_PATH/lib:$MACA_PATH/ompi/lib:$MACA_PATH/mxgpu_llvm/lib:${LD_LIBRARY_PATH:-}
export VLLM_PLUGINS=metax
export PYTHONPATH=/home/waas/compat
export TORCH_EXTENSIONS_DIR=/home/waas/.cache/torch_extensions
export HF_HOME=/home/waas/.cache/huggingface
```

然后直接用 `setsid` 和 `nohup` 启动：

```bash
setsid nohup vllm serve /home/waas/models/Qwen3.5-4B \
  --served-model-name Qwen3.5-4B \
  --host 0.0.0.0 \
  --port 8000 \
  --trust-remote-code \
  --dtype auto \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.85 \
  --enforce-eager \
  --language-model-only \
  > /home/waas/logs/qwen35-4b-vllm.log 2>&1 &

echo $! > /home/waas/logs/qwen35-4b-vllm.pid
echo "服务进程 PID: $!"
```

两个参数尤其重要：

- `--enforce-eager`：避开当前 MetaX Torch 2.8 缺少的 functorch 编译配置项。会关闭 Torch Compile 和 CUDA Graph，性能可能低于图优化模式，但本次实测稳定。
- `--language-model-only`：Qwen3.5 本身具有多模态能力；本服务只提供文本推理，因此关闭视觉编码器 profiling，显著减少无用的启动内存。

`setsid nohup` 可以让服务在退出终端后继续运行。PID 被记录到数据盘，停止服务时会用到。

### 8.2 查看状态和日志

```bash
ps -fp "$(cat /home/waas/logs/qwen35-4b-vllm.pid)"
ss -ltnp | grep :8000
tail -n 100 /home/waas/logs/qwen35-4b-vllm.log
mx-smi --show-memory
free -h
```

看到 `Application startup complete` 才表示服务真正可用。仅看到 Python 进程不代表 8000 端口已经就绪。

### 8.3 停止

```bash
PID=$(cat /home/waas/logs/qwen35-4b-vllm.pid)
kill -TERM -- "-$PID"
```

这里停止的是整个进程组，包括 API Server 和 EngineCore。确认已经停止：

```bash
ps -fp "$PID"
ss -ltnp | grep :8000
```

重新启动时不需要再次安装软件，重新执行本节的环境变量和启动命令即可。

## 九、调用 OpenAI 兼容 API

### 9.1 查看模型列表

```bash
curl http://127.0.0.1:8000/v1/models
```

应返回模型 ID `Qwen3.5-4B`。

### 9.2 发送聊天请求

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3.5-4B",
    "messages": [
      {"role": "user", "content": "请用一句话介绍 MetaX C500。"}
    ],
    "temperature": 0.1,
    "max_tokens": 64,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

本次实际回复：

```text
MetaX C500 服务器上的 vLLM 服务已成功启动并处于就绪状态，能够正常处理推理请求。
```

该次调用的统计为：输入 31 token，输出 28 token，共 59 token。

API 返回成功只能证明推理链路可用，不能证明回答中的事实正确。复验时，模型曾把 MetaX C500 错误描述为其他厂商的 5G 设备，属于模型幻觉。验证部署时应检查 HTTP 状态码、返回结构和 token 统计；验证专业知识时应另用可靠资料、检索增强或人工评估。

### 9.3 Python SDK

```bash
python -m pip install openai
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="EMPTY")
response = client.chat.completions.create(
    model="Qwen3.5-4B",
    messages=[{"role": "user", "content": "你好，请介绍一下你自己。"}],
    max_tokens=128,
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)
print(response.choices[0].message.content)
```

## 十、性能测试

### 10.1 测试方法

vLLM 0.21 已将旧的 `benchmarks/benchmark_serving.py` 标记为弃用。直接执行该脚本只会提示改用 CLI 并退出，因此本文使用官方等价入口：

```bash
vllm bench serve
```

Benchmark 使用流式请求，能够统计 TTFT（首 token 延迟）、TPOT（除首 token 外的平均单 token 时间）和 ITL（token 间延迟）。运行前后都应检查主存和显存；本次客户端退出后主存恢复正常，模型服务保持健康。

### 10.2 Random 数据集，并发 4

测试条件：固定输入 128 token、输出 64 token，2 个预热请求，40 个正式请求，最大并发 4。

```bash
vllm bench serve \
  --backend openai-chat \
  --base-url http://127.0.0.1:8000 \
  --endpoint /v1/chat/completions \
  --model Qwen3.5-4B \
  --tokenizer /home/waas/models/Qwen3.5-4B \
  --dataset-name random \
  --random-input-len 128 \
  --random-output-len 64 \
  --num-prompts 40 \
  --num-warmups 2 \
  --request-rate inf \
  --max-concurrency 4 \
  --ignore-eos \
  --save-result \
  --result-dir /home/waas/logs
```

```text
Successful requests:                  40
Failed requests:                       0
Benchmark duration:                21.22 s
Request throughput:                 1.89 req/s
Output token throughput:          120.66 token/s
Peak output token throughput:     128.00 token/s
Total token throughput:           381.73 token/s
Mean TTFT:                          96.97 ms
P99 TTFT:                          120.50 ms
Mean TPOT:                          32.12 ms/token
P99 TPOT:                           32.62 ms/token
Mean ITL:                           31.62 ms
P99 ITL:                            33.21 ms
```

### 10.3 Sonnet 数据集，10 请求同时发送

从 vLLM 0.21 官方仓库取得同版本测试文本：

```bash
mkdir -p /home/waas/benchmarks /home/waas/benchmark-results
curl -fL \
  https://raw.githubusercontent.com/vllm-project/vllm/v0.21.0/benchmarks/sonnet.txt \
  -o /home/waas/benchmarks/sonnet.txt
```

按照输入 256 token、输出 64 token、公共前缀 100 token、10 个请求和无限请求速率测试：

```bash
vllm bench serve \
  --backend vllm \
  --base-url http://127.0.0.1:8000 \
  --endpoint /v1/completions \
  --dataset-name sonnet \
  --dataset-path /home/waas/benchmarks/sonnet.txt \
  --model Qwen3.5-4B \
  --tokenizer /home/waas/models/Qwen3.5-4B \
  --num-prompts 10 \
  --sonnet-input-len 256 \
  --sonnet-output-len 64 \
  --sonnet-prefix-len 100 \
  --request-rate inf \
  --save-result \
  --result-dir /home/waas/benchmark-results \
  --result-filename qwen35-4b-sonnet-10-20260726.json
```

```text
Successful requests:                  10
Failed requests:                       0
Peak concurrent requests:             10
Benchmark duration:                  2.40 s
Request throughput:                 4.16 req/s
Output token throughput:          266.30 token/s
Peak output token throughput:     320.00 token/s
Total token throughput:          1279.91 token/s
Mean TTFT:                         195.57 ms
P99 TTFT:                          227.28 ms
Mean TPOT:                          34.90 ms/token
P99 TPOT:                           36.40 ms/token
Mean ITL:                           34.90 ms
P99 ITL:                           217.07 ms
```

`--request-rate inf` 表示请求会尽快发出。没有设置 `--max-concurrency` 时，本轮 10 个请求的峰值并发就是 10，因此它不能与并发 4 的结果直接横向比较。

结果文件：

```text
/home/waas/benchmark-results/qwen35-4b-sonnet-10-20260726.json
```

跑更高并发前，先检查：

```bash
free -h
mx-smi --show-memory
df -h / /home/waas
```

不要只看聚合 TPS。并发升高通常会提高整卡吞吐，但也会增加 TTFT、ITL 和尾延迟。建议固定输入、输出和数据集，按并发 1、4、8、16 逐级测试，并同时观察错误率、P99 延迟、主存和显存。

## 十一、这次修正的几个问题

### 11.1 “必须编译纯 Python vLLM 核心”不合理

旧方案把源码构建当成必选步骤。实际已经有匹配的预编译 wheel，本次没有编译 vLLM。只有官方没有提供匹配 Python、MACA、Torch 和架构的包时，才需要评估源码构建。

### 11.2 只安装 `vllm-metax` 而不核对核心版本不够安全

`vllm-metax` 是平台插件，仍需匹配的 vLLM 核心。不能随意安装一个最新版 vLLM。应按 MetaX 发布包的版本矩阵锁定整个组合。

### 11.3 旧版 `mcoplib_init` 不适用于 0.21

旧文档中的初始化命令属于早期发布。0.21 的 mcoplib 安装后会在加载插件时输出构建版本和运行时 MACA 匹配结果，不需要另跑不存在的命令。

### 11.4 `torch.accelerator.*` 缺失

表现：

```text
AttributeError: module 'torch.accelerator' has no attribute 'empty_cache'
AttributeError: module 'torch.accelerator' has no attribute 'memory_stats'
```

原因是 vLLM 0.21 使用新 API，而 MetaX Torch 2.8 仍通过 `torch.cuda` 暴露相同能力。使用第六章的独立兼容层即可，不应修改 site-packages 中的 vLLM 源码。

### 11.5 Functorch 配置项不存在

表现：

```text
torch._functorch.config.autograd_cache_normalize_inputs does not exist
```

当前稳定解决方法是 `--enforce-eager`。不要为了绕过它在 Torch 内部配置中随意伪造大量字段。等 MetaX 发布与 vLLM 0.21 图编译路径完全匹配的 Torch 后，再移除该参数做 A/B 测试。

### 11.6 权重加载后长时间不监听端口

Qwen3.5-4B 会被识别为支持多模态的架构。纯文本服务应加入 `--language-model-only`，否则启动阶段还会为视觉编码器准备缓存并做 profiling，额外消耗时间和主存。

### 11.7 为什么显存显示约 85%

`--gpu-memory-utilization 0.85` 会让 vLLM 为模型权重和 KV Cache 规划约 85% 的显存。这不表示模型权重本身有 50 多 GiB，也不表示内存泄漏。空闲时 KV Cache 使用率可以为 0，但预留的显存仍由服务持有。

## 十二、容器重启后的恢复

容器重启后按顺序执行：

```bash
df -h / /home/waas
mx-smi
if [ ! -f /usr/include/python3.12/Python.h ]; then
  apt-get update
  apt-get install -y python3.12-dev
fi
```

2026 年 7 月 26 日冷启动复验时，容器中的 Python 开发头文件已经消失，首次启动报错：

```text
fatal error: Python.h: No such file or directory
```

补装 `python3.12-dev` 后，Triton 成功生成小型运行时辅助模块，服务正常启动。这进一步说明数据盘中的模型和 venv 可以持久保存，但系统层软件包未必会随容器重建保留。这个过程不是编译 vLLM。

然后重新执行第八章中的环境变量和 `setsid nohup vllm serve` 命令。启动后检查：

```bash
tail -f /home/waas/logs/qwen35-4b-vllm.log
ss -ltnp | grep :8000
curl http://127.0.0.1:8000/v1/models
```

模型、venv、兼容配置和日志都在 `/home/waas`。如果平台的数据盘挂载发生变化，应先确认该目录存在，再启动服务。

## 十三、常用命令速查

```bash
# 服务进程
ps -fp "$(cat /home/waas/logs/qwen35-4b-vllm.pid)"

# 服务日志
tail -f /home/waas/logs/qwen35-4b-vllm.log

# 停止整个服务进程组
PID=$(cat /home/waas/logs/qwen35-4b-vllm.pid)
kill -TERM -- "-$PID"

# API 模型列表
curl http://127.0.0.1:8000/v1/models

# GPU 显存
mx-smi --show-memory

# 主存
free -h

# 磁盘
df -h / /home/waas

# 查看安装版本
/home/waas/venvs/vllm-metax/bin/python -m pip list | \
  grep -E 'torch|vllm|metax|mcoplib|flash|triton'
```

## 参考资料

1. MetaX 官方《vLLM-MetaX 概述》：<https://developer.metax-tech.com/api/client/document/preview/1360/split_files/macart_vllm_metax.html>
2. MetaX 官方文档入口：<https://developer.metax-tech.com/api/client/document/preview/1360/split_files/%E6%A6%82%E8%BF%B0.html>
3. MetaX 官方 PyPI：<https://repos.metax-tech.com/r/maca-pypi/simple>
4. MetaX 开发者社区 vLLM 搜索：<https://developer.metax-tech.com/search?q=vllm>
5. vLLM 官方文档：<https://docs.vllm.ai/>
6. Qwen 官方模型页面：<https://modelscope.cn/organization/qwen>

---

本次部署的核心结论：MetaX C500 上有匹配的官方预编译 vLLM-MetaX 组件时，不需要自行编译 vLLM。先创建 venv，锁定 MACA、Torch、vLLM 和插件版本，把模型及缓存放到数据盘，再用 eager 和纯文本模式解决当前版本组合的兼容性问题，即可稳定提供 OpenAI 兼容服务。
