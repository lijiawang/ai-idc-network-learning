# GPU Operator 进阶，一个容器怎么把 NVIDIA 驱动装进宿主机

![GPU Operator Driver Pod 在宿主机内核中安装 NVIDIA 驱动](assets/kubernetes-gpu/gpu-operator-driver-container-cover.png)

[上一篇](NVIDIA%20Device%20Plugin%20与%20GPU%20Operator：Kubernetes%20如何管理%20GPU.md)把两台 RTX 3080 Ti 接进 Kubernetes 时，宿主机已经装好了 NVIDIA Driver 和 NVIDIA Container Toolkit。Helm 命令里有两行参数，当时直接关掉了 Operator 的驱动和 Toolkit 管理能力。

```bash
--set driver.enabled=false
--set toolkit.enabled=false
```

所以那次安装里，Operator 只接管 Device Plugin、GFD、DCGM Exporter 和 Validator，节点底层没有动。

把 `driver.enabled` 改回 `true` 后，GPU Operator 会创建 Driver Pod，由它在宿主机上安装驱动。

这篇沿着 GPU Operator v26.3.3 的控制器源码、Driver DaemonSet 清单和启动流程往下追，重点看 Driver Pod 如何加载宿主机内核模块、用户态文件放在哪里，以及 Pod 重建后怎样处理已有模块。Helm 入门和整卡调度见上一篇。

> **这次实验的边界**
>
> 两台 RTX 3080 Ti 节点正在使用宿主机预装的 Driver 570.153.02 和 Container Toolkit 1.19.1。本文没有在这两台机器上切换容器化驱动，避免碰坏已经跑通的环境。
>
> 截至 2026 年 8 月，NVIDIA 将 v26.3.x 标为 `Supported`，v25.10.x 标为 `Deprecated`，v25.3.x 及以下已经 `End of Support`。文中的源码和命令固定在 v26.3.3，上一篇的现有集群并没有随之升级。
>
> 后面的安装命令留给干净、可回滚的 GPU 节点。Driver 版本仍要按 Platform Support、Component Matrix、GPU、操作系统和内核来选。

## 1. 驱动容器的职责

CUDA 程序不会隔着 Driver Pod 调用 GPU。Driver Pod 做的是节点初始化，流程大致如下。

1. Operator 找到带 NVIDIA PCI 设备的节点；
2. Operator 为这些节点创建 `nvidia-driver-daemonset`；
3. Driver Pod 以特权模式运行，针对宿主机正在运行的内核准备并加载 NVIDIA 内核模块；
4. Driver Container 把自己的驱动用户态文件系统暴露到宿主机 `/run/nvidia/driver`；
5. Container Toolkit 根据这个路径配置 CDI 与容器注入链路；
6. Device Plugin 向 kubelet 注册 `nvidia.com/gpu`。

容器隔离了文件系统和进程视图，但仍共用宿主机的 Linux 内核。Driver Pod 里执行 `modprobe`，模块就加载进宿主机内核。用户态库和工具留在 Driver Container，通过 `/run/nvidia/driver` 共享出去，具体过程见第 5.4 节。

删除 Driver Pod 不会自动卸载已经加载的模块。相同配置下的模块复用和真正的驱动升级，放到第 4.5 节再展开。

## 2. Helm、ClusterPolicy、Controller 和 Operand 是四层关系

GPU Operator 走的是标准 Operator 控制循环。Helm 负责把入口资源装进集群，后面的节点组件由 Controller 持续维护。

| 层级 | 负责什么 |
| --- | --- |
| Helm Chart | 安装 CRD、Operator Deployment、RBAC，并根据 values 创建 `ClusterPolicy` |
| `ClusterPolicy` | 保存整个集群希望使用的 Driver、Toolkit、Device Plugin、监控和校验配置 |
| GPU Operator Controller | 持续比较期望状态和实际状态，创建或更新各组件的 DaemonSet、Service、ConfigMap 等对象 |
| Operand | 真正运行在节点上的 Driver、Toolkit、Device Plugin、GFD、DCGM Exporter、Validator 等 Pod |

安装后可以从三个位置看状态。

```bash
helm get values gpu-operator -n gpu-operator

kubectl get clusterpolicy cluster-policy -o yaml

kubectl get daemonset -n gpu-operator
```

v26.3.3 的 `ClusterPolicy` 控制器按下面的顺序协调。沙箱、vGPU、VFIO、Kata 和机密计算等可选状态先省略。

```text
pre-requisites
  -> state-operator-metrics
  -> state-driver
  -> state-container-toolkit
  -> state-operator-validation
  -> state-device-plugin
  -> state-mps-control-daemon
  -> state-dcgm
  -> state-dcgm-exporter
  -> gpu-feature-discovery
  -> state-mig-manager
  -> state-node-status-exporter
  -> ...
```

每走一步，控制器都会创建或更新对应的 Kubernetes 对象，再检查 DaemonSet 等资源是否就绪。中间任何一步没完成，`ClusterPolicy` 都会留在 `notReady`，等下一轮继续处理。

`nvidia-driver-daemonset` 是 Controller 根据 `ClusterPolicy` 生成的结果，手工改了也可能在下一轮被改回去。长期配置应该留在 Helm values、GitOps 清单或 `ClusterPolicy` 里。

查看控制器正在处理哪个状态。

```bash
kubectl logs -n gpu-operator deployment/gpu-operator \
  | grep -E 'ClusterPolicy step completed|state-driver|state-container-toolkit'
```

## 3. Driver Pod 的节点发现

Driver Pod 启动时，Device Plugin 还不能调用 NVML，也没有向 kubelet 注册 `nvidia.com/gpu`。Operator 依据 NFD 生成的 PCI 标签选择节点，不等扩展资源出现。

NFD 读取 PCI 设备就够了，不依赖 CUDA 和 NVIDIA 用户态驱动。NVIDIA 的厂商 ID 是 `10de`，节点上会出现这类标签。

```text
feature.node.kubernetes.io/pci-10de.present=true
feature.node.kubernetes.io/pci-0300_10de.present=true
```

GPU Operator 根据这些标签，再补上自己的状态标签。

```text
nvidia.com/gpu.present=true
nvidia.com/gpu.deploy.driver=true
nvidia.com/gpu.deploy.container-toolkit=true
nvidia.com/gpu.deploy.device-plugin=true
```

Driver DaemonSet 匹配 `nvidia.com/gpu.deploy.driver=true`，并不等 `nvidia.com/gpu` 扩展资源。它自身也不申请 GPU，用默认的低层 OCI runtime（通常是 `runc`）就能启动。此时 NVIDIA runtime 和 Device Plugin 都可以还没装。

查看节点发现链路。

```bash
kubectl get nodes \
  -o custom-columns=NAME:.metadata.name,PCI-NVIDIA:.metadata.labels.feature\.node\.kubernetes\.io/pci-10de\.present,GPU-PRESENT:.metadata.labels.nvidia\.com/gpu\.present,DEPLOY-DRIVER:.metadata.labels.nvidia\.com/gpu\.deploy\.driver
```

这几个字段看着像，其实各管一层。

- `pci-10de.present`，节点上能否看到 NVIDIA PCI 设备；
- `gpu.present`，Operator 是否把它识别为 GPU 节点；
- `gpu.deploy.driver`，该节点是否应该运行 Driver Operand；
- `nvidia.com/gpu`，整条链路完成后，kubelet 上报的可调度资源。

![GPU Operator 从 PCI 发现到创建 Driver Pod 的控制链路](assets/kubernetes-gpu/gpu-operator-control-loop-bootstrap.png)

*图 1。Helm 提交期望状态，NFD 提供 PCI 发现结果，GPU Operator 为匹配节点创建 Driver Pod。*

## 4. Driver DaemonSet 的宿主机权限

`hostPID`、`privileged`、`hostPath` 和挂载传播，共同给了 Driver DaemonSet 管理宿主机驱动所需的权限。

### 4.1 每个 GPU 节点运行一个 Driver Pod

DaemonSet 的 `nodeSelector` 如下。

```yaml
nvidia.com/gpu.deploy.driver: "true"
```

它还使用 `system-node-critical` 优先级，使 Driver Pod 作为节点关键组件获得更高的调度优先级。

### 4.2 Driver Pod 共享宿主机 PID 命名空间

清单里还能看到 `hostPID`。

```yaml
hostPID: true
```

这让驱动生命周期组件能看到宿主机进程。升级或卸载模块之前，Driver Manager 需要判断哪些进程仍在使用 `/dev/nvidia*`，否则模块很可能因为仍有客户端而无法卸载。

### 4.3 initContainer 和主容器都是 privileged

Driver Pod 里有两个核心部分。

| 容器 | 作用 |
| --- | --- |
| `k8s-driver-manager` initContainer | 在 Driver Pod 重建或升级前协调旧驱动客户端、旧模块和节点状态 |
| `nvidia-driver-ctr` | 准备驱动文件，编译或选择内核模块，加载模块并执行 `nvidia-smi` 就绪检查 |

两者都需要 `privileged: true`。光有容器内的 root 还不够，加载内核模块、访问宿主机 sysfs、处理设备和挂载传播都要越过普通容器的隔离边界。

Driver Pod 的权限接近节点管理员。`gpu-operator` 命名空间、Operator ServiceAccount、镜像来源和镜像签名，都得按节点级基础设施组件保护。

### 4.4 hostPath 和挂载传播把两边接起来

v26.3.3 的 Driver Pod 会用到下面这些宿主机路径。

| 宿主机路径 | 在驱动链路中的作用 |
| --- | --- |
| `/run/nvidia` | 保存驱动根目录、校验标记等运行时状态，并使用双向挂载传播 |
| `/` | 以只读 `/host` 提供给 Driver Manager，用于观察宿主机文件系统 |
| `/sys` 及部分 sysfs 路径 | 访问内核、固件和设备相关状态 |
| `/var/log`、`/dev/log` | 写入或转发驱动与 Fabric Manager 日志 |
| `/run/mellanox/drivers` | 启用 GPUDirect RDMA 等场景时与网络驱动栈衔接 |

只写挂载 `/lib/modules` 再执行 `apt install`，会漏掉不少关键动作。v26.3.3 还配置了 `hostPID`、`privileged`、多组 hostPath 和挂载传播；启动脚本随后按宿主机环境构建或选择模块，再加载进内核。

![Driver Pod 通过 privileged、hostPID 和 hostPath 触达宿主机内核](assets/kubernetes-gpu/gpu-operator-driver-pod-host-boundary.png)

*图 2。Driver Pod 没有自己的内核。`hostPID` 用来观察宿主机进程，`hostPath` 连接宿主机路径，`privileged` 让模块加载作用到宿主机内核。用户态驱动通过 `/run/nvidia/driver` 暴露。*

集群实际生成的 PodSpec 可以直接查。

```bash
kubectl get daemonset nvidia-driver-daemonset \
  -n gpu-operator \
  -o jsonpath='{.spec.template.spec.hostPID}{"\n"}'

kubectl get daemonset nvidia-driver-daemonset \
  -n gpu-operator \
  -o jsonpath='{range .spec.template.spec.initContainers[*]}init {.name}{" privileged="}{.securityContext.privileged}{"\n"}{end}{range .spec.template.spec.containers[*]}container {.name}{" privileged="}{.securityContext.privileged}{"\n"}{end}'

kubectl get daemonset nvidia-driver-daemonset \
  -n gpu-operator \
  -o jsonpath='{range .spec.template.spec.volumes[*]}{.name}{"\t"}{.hostPath.path}{"\n"}{end}'
```

### 4.5 v26.3.3 仍使用 `OnDelete` 更新 Driver Pod

Driver DaemonSet 的更新策略是 `OnDelete`。

```yaml
updateStrategy:
  type: OnDelete
```

驱动更新没法套用普通 DaemonSet 的自动滚动。旧模块还在宿主机内核里，GPU 客户端也可能没停，Driver Upgrade Controller 或 Driver Manager 得先处理客户端、节点和模块，再删除、重建 Driver Pod。相同配置下只删 Pod，v26.3 可以复用模块；新 Pod 随后会重新暴露 `/run/nvidia/driver` 并恢复校验状态。换 Driver 版本仍要卸载旧模块。

## 5. Driver Container 启动流程

### 5.1 识别宿主机环境

Driver Container 会读取宿主机操作系统信息，并以宿主机正在运行的内核版本为目标。驱动能否加载，取决于下面五项是否兼容。

```text
GPU 型号
+ Driver 分支/版本
+ Linux 发行版
+ uname -r
+ 内核模块类型（auto/open/proprietary）
```

只看 CUDA 版本判断不了这组兼容性。CUDA 应用镜像、Driver 用户态组件和宿主机内核模块分属不同层，CUDA 镜像标签替代不了 Driver 检查。

### 5.2 准备与当前内核匹配的构建条件

传统 Driver Container 会在节点启动阶段准备与 `uname -r` 对应的 kernel headers、GCC 和发行版软件包，再构建或链接 NVIDIA 内核模块。

它依赖软件源中仍然存在当前内核对应的包。如果节点运行的是已经从普通仓库下架的旧内核，常见报错如下。

```text
Could not resolve Linux kernel version
```

这类问题靠重启 Driver Pod 不会自动消失。要么升级到受支持的内核，要么给 Driver Container 配置包含旧内核包的归档仓库，要么改用有精确匹配镜像的预编译驱动。

### 5.3 选择并加载 NVIDIA 内核模块

现代 GPU Operator 通过 `driver.kernelModuleType` 选择模块类型。

```text
auto         由支持该能力的 Driver Container 根据 GPU 和驱动分支选择
open         NVIDIA Open GPU Kernel Modules
proprietary  NVIDIA 专有内核模块
```

旧驱动分支并非都支持 `auto`。实际取值要同时核对 GPU Operator 版本与 Driver Container 的支持范围。

安装阶段要把 `nvidia`、`nvidia_uvm`、`nvidia_modeset` 等模块加载进宿主机正在运行的内核。显示栈、GPUDirect RDMA、GDS 等能力还会用到 `nvidia_drm`、`nvidia_peermem`、`nvidia_fs`，按实际启用的功能加载。

Ubuntu Driver Container 使用自身的安装和内核模块构建流程，其中可能包含类似内核更新钩子的机制。宿主机软件包系统不会在这个流程中完成一次标准 DKMS 安装。

### 5.4 把驱动用户态文件暴露到 `/run/nvidia/driver`

CUDA 容器除了内核模块，还需要 `libcuda.so`、NVML 等用户态库和工具。Driver Container 安装完成后，会把自己的根文件系统递归绑定到 `/run/nvidia/driver`。Driver DaemonSet 对 `/run/nvidia` 使用双向挂载传播，宿主机和后续 Operand 因而能看到这些文件。

模块加载在宿主机内核中，用户态文件留在 Driver Container，再通过 `/run/nvidia/driver` 共享给 Toolkit、Validator 和 GPU 工作负载。这些文件不会永久复制进宿主机 `/usr`。

所以，只看宿主机有没有 `/usr/bin/nvidia-smi` 不够。先在 Driver Container 里运行 `nvidia-smi`，再到宿主机检查模块和 `/proc` 状态，证据才完整。

### 5.5 通过 startupProbe 建立驱动就绪标记

v26.3.3 的 Driver DaemonSet 挂载专用 `startup-probe.sh`。探针验证 `nvidia-smi`，成功后写入下面这个标记。

```text
/run/nvidia/validations/.driver-ctr-ready
```

Driver Validator 会先检查宿主机预装驱动。宿主机没有驱动时，它再等待上面的容器化驱动标记。验证通过后会生成 `driver-ready`。

```text
/run/nvidia/validations/driver-ready
```

这个文件里还有 `IS_HOST_DRIVER`、`NVIDIA_DRIVER_ROOT`、`DRIVER_ROOT_CTR_PATH` 等环境信息。Toolkit 启动前会读取它，从而兼容宿主机驱动根目录 `/` 和容器化驱动根目录 `/run/nvidia/driver`。

v26.3.3 继续部署 `nvidia-operator-validator` DaemonSet。Validator 可执行程序随 `gpu-operator` 镜像发布，Pod 名称和校验链路保持不变。

后续组件的 initContainer 会等待对应依赖通过。这样 Toolkit、Device Plugin 和 DCGM Exporter 不会在驱动不可用时被误判为就绪。

![Driver Container 从识别内核到向 Toolkit 交付就绪状态的流程](assets/kubernetes-gpu/gpu-operator-driver-install-flow.png)

*图 3。Operator 在 Pod 启动前选好传统或预编译 Driver 镜像。Driver Container 加载模块后，`nvidia-smi` 建立 `.driver-ctr-ready`，Validator 再生成下游读取的 `driver-ready`。*

## 6. 传统 Driver Container 和预编译 Driver Container

GPU Operator 管理驱动时有两条主要路径。

| 对比项 | 传统 Driver Container | 预编译 Driver Container |
| --- | --- | --- |
| `driver.usePrecompiled` | `false` | `true` |
| `driver.version` | 完整驱动版本，如 `580.x.y` | 驱动分支，如 `580` |
| 节点启动时构建 | 需要针对当前内核准备并构建模块 | 模块已经针对指定内核构建好 |
| 对外部仓库依赖 | 通常需要获取 headers、GCC 和 OS 包 | 不需要现场下载这些构建依赖 |
| 镜像匹配粒度 | Driver 版本 + OS | Driver 分支 + 完整内核版本/变体 + OS |
| 优点 | 对支持范围内的内核更灵活 | 启动更快、行为更可预测，适合受限网络 |
| 代价 | 软件源、旧内核和现场编译更容易失败 | 必须有精确匹配的镜像，支持范围有限 |

预编译镜像标签格式为 `<driver-branch>-<linux-kernel-version>-<os-tag>`，官方示例是 `525-5.15.0-69-generic-ubuntu22.04`。

预编译驱动省掉了节点现场编译，却没有省掉内核匹配。节点升级内核后，仓库里也要有新内核对应的镜像标签，否则 Driver Pod 还是起不来。

v26.3 文档将官方预编译驱动限制在 x86_64、列出的操作系统和内核变体，并只支持最近发布的 LTSB Driver 分支；它仍不支持 vGPU 和 GPUDirect Storage。生产使用前必须先查支持表和 NGC 镜像标签。

## 7. Toolkit 在驱动就绪后的职责

Driver、NVIDIA Container Toolkit 和 Device Plugin 的分工如下。

| 层 | 解决的问题 |
| --- | --- |
| NVIDIA Driver | Linux 内核如何控制 GPU，用户态程序如何通过 Driver API 访问它 |
| NVIDIA Container Toolkit | containerd、CRI-O 或 Docker 启动容器时，如何注入指定 GPU、设备节点和驱动用户态库 |
| Device Plugin | Kubernetes 如何发现可分配 GPU，并把设备选择结果交给容器启动链路 |

Toolkit DaemonSet 会先等待 Driver Validator 通过，再以特权模式和 hostPath 配置节点上的 GPU 容器注入链路。容器化驱动的根目录指向 `/run/nvidia/driver`。

在 v26.3.3 清单里，宿主机驱动根目录在 Toolkit Container 内的挂载点仍是 `/driver-root`。Toolkit 还会把自己的二进制安装到宿主机默认的 `/usr/local/nvidia`，并生成 CDI 规范文件。

v26.3.3 默认启用 CDI、关闭 NRI。

```yaml
cdi:
  enabled: true
  nriPluginEnabled: false
```

标准业务 Pod 通过 Device Plugin 申请 GPU 时，containerd 或 CRI-O 使用原生 CDI 支持注入设备。绕过 Kubernetes 资源分配、直接使用 `NVIDIA_VISIBLE_DEVICES` 的 GPU 管理容器，在这个默认模式下仍需要 `runtimeClassName: nvidia`。

启用 NRI 后，每个 GPU 节点都会运行 NRI Plugin，Toolkit 会跳过 `nvidia` RuntimeClass 和 containerd `config.toml` 的修改。NRI 仍受上游实现和容器运行时版本限制，本文实验保持默认的 `CDI=true、NRI=false`。

NVIDIA Container Toolkit 负责容器启动时注入 GPU 设备和驱动用户态库。CUDA Toolkit 属于工作负载环境，内核模块由 Driver Container 准备并加载。

启动顺序可以记成下面这条链。

```text
NFD 发现 PCI 设备
  -> Driver 安装并加载模块
  -> Driver Validator
  -> Toolkit 配置 CDI 与容器注入链路
  -> Toolkit Validator
  -> Device Plugin 注册 nvidia.com/gpu
  -> CUDA Validator
  -> 业务 Pod
```

如果大量 Operand 都卡在 `Init`，不要逐个重启。它们很可能都在等同一个上游就绪文件，应先从 Driver 和 Toolkit 往下查。

## 8. 在独立的干净实验集群里安装驱动

下面的命令只留给独立的干净实验集群。这个集群里没有现成的 GPU Operator Release，GPU 节点也准备交给 Operator 管理 Driver 和 Toolkit。

上一篇那套 `gpu-operator` Release 不能直接套用本节命令。`driver.enabled=true` 是集群级配置，会影响所有匹配的 GPU 节点；一次没带完整 values 的 `helm upgrade`，还可能把 DaoCloud 镜像、CDI 等定制项冲回 Chart 默认值。

同一个集群里若有预装驱动节点，可以先把这些节点排除掉。

```bash
NODE='预装驱动的节点名'

kubectl label node "$NODE" \
  nvidia.com/gpu.deploy.driver=false \
  --overwrite
```

这条标签只关闭该节点的 Driver Operand，其他 Operand 还能继续部署。若所有 GPU 节点都预装了驱动，用全局的 `driver.enabled=false` 更省事。

`NVIDIADriver` CRD 适合新集群里的多 Driver 版本、多类型或多种 GPU 节点 OS。它与 `ClusterPolicy` 驱动管理互斥，已有 `ClusterPolicy` 安装也不能原地切换。Chart 启用 CRD 后默认会创建一个匹配所有 GPU 节点的 `default` CR；准备自行划分节点池时，需要从安装开始设置 `driver.nvidiaDriverCRD.deployDefaultCR=false`。

### 8.1 先找一台能回滚的节点

实验节点最好满足这些条件。

- 使用 NVIDIA Platform Support 明确列出的 GPU、操作系统和 Kubernetes 组合；
- GPU 节点使用相同操作系统版本，已经配置 Kubernetes 与 containerd，但还没安装 NVIDIA Driver 和 Container Toolkit；
- 节点或云盘可以快照回滚，GPU 工作负载也已经迁走；
- 软件源能够提供与 `uname -r` 精确匹配的 headers，或已经确认存在预编译 Driver Container；
- 镜像仓库、软件包仓库、代理和证书链已经验证。

动手前先留一份基线。

```bash
cat /etc/os-release
uname -r
lspci -nn | grep -i nvidia
lsmod | grep -E '^(nvidia|nouveau)'
command -v nvidia-smi
```

理想的干净节点应能从 PCI 看到 NVIDIA 设备，但没有已经加载的 `nvidia*` 模块，也没有正在工作的宿主机 Driver。若 `nouveau` 已占用 GPU，应按目标操作系统和 NVIDIA 官方指南处理后再继续。

### 8.2 版本先定下来

需要核对四件事。

1. GPU Operator Platform Support；
2. GPU Operator Component Matrix；
3. 目标 GPU 支持的 Driver 分支；
4. 目标内核是否有 headers 或预编译镜像。

v26.3.3 的 Component Matrix 把 580.126.20 列为默认 Driver，把 580.173.02 列为推荐 Driver。这不代表任意 GPU、OS 和内核都能直接装 580.173.02，具体组合仍要回到支持矩阵核对。

本文后面的安装命令把 `GPU_OPERATOR_VERSION` 固定为 `v26.3.3`。完整的 `values-driver-managed.yaml` 在下一节配置好以后再安装，Driver 版本和镜像源也写在这个文件里。

### 8.3 驱动版本、镜像源和包源要分开写

提到「驱动从哪里下载」，实际牵涉三层配置。

| 配置 | 控制什么 | 不控制什么 |
| --- | --- | --- |
| Helm 仓库与 Chart `--version` | 从哪里取得 GPU Operator Chart，以及安装哪个 Operator 版本 | NVIDIA Driver 版本 |
| `driver.repository`、`driver.image`、`driver.version` | kubelet 拉取哪个 Driver Container 镜像 | Driver Container 内部的 apt、dnf、yum 或 zypper 软件源 |
| `driver.repoConfig.configMapName` | 向 Driver Container 的包管理器追加哪些 OS 软件源定义 | Driver Container 镜像地址和 NVIDIA Driver 版本 |

标准 Data Center Driver 的安装载荷放在 Driver Container 镜像里。`driver.version` 用来选择镜像标签，不会让 Pod 去某个 URL 现场下载 `.run` 文件。传统 Driver Container 启动后还要下载与宿主机内核匹配的 OS 软件包，所以镜像拉取成功了，驱动构建仍然可能卡在软件源。

#### 8.3.1 指定传统 Driver Container 的版本和镜像仓库

能直接访问 NVIDIA NGC 时，v26.3.3 默认从 `nvcr.io/nvidia/driver` 拉镜像。下面换成企业私有仓库，并用 580.173.02 演示配置格式。把实际地址和版本填好后，将这段保存为 `values-driver-managed.yaml`。

```yaml
driver:
  enabled: true
  usePrecompiled: false
  kernelModuleType: auto

  repository: registry.example.com/mirror/nvidia
  image: driver
  version: "580.173.02"
  imagePullPolicy: IfNotPresent
  imagePullSecrets:
    - registry-cred
```

这几个字段会拼成 Driver 镜像地址。

```text
<repository>/<image>:<driver-version>-<os-tag>
```

Ubuntu 22.04 节点最终会拿到类似下面的地址。

```text
registry.example.com/mirror/nvidia/driver:580.173.02-ubuntu22.04
```

`repository` 只写仓库和子路径，不带 `https://`、镜像名或标签。`image` 通常保持 `driver`，`version` 写完整 Driver 版本。OS 后缀由 Operator 根据节点自动补上。

私有仓库里要提前同步好对应 OS 标签的镜像，拉取凭据 Secret 放在 `gpu-operator` 命名空间。v26.3.3 的 `driver.imagePullSecrets` 是字符串数组，正确写法是 `- registry-cred`。

`driver.certConfig` 管不到 containerd 对私有 Registry 的信任。Registry 的 CA 和代理要配在每个节点的操作系统与 containerd 上，`imagePullSecrets` 只解决认证。完全离线时，Operator、Driver Manager、Toolkit、Device Plugin、NFD、DCGM 等已启用组件也要一并同步。

预编译 Driver Container 的 `version` 写 Driver 分支，比如 `580`。

```yaml
driver:
  enabled: true
  repository: registry.example.com/mirror/nvidia
  image: driver
  version: "580"
  usePrecompiled: true
  imagePullSecrets:
    - registry-cred
```

最终标签还会带上完整内核版本和 OS。

```text
580-<uname-r>-ubuntu22.04
```

同一集群有多个内核版本，就要按实际的内核与 OS 组合逐个同步镜像。少一个标签，对应节点就会 `ImagePullBackOff`。

#### 8.3.2 指定 kernel headers 和 GCC 的软件包源

传统 Driver Container 仍要通过 apt、dnf、yum 或 zypper 获取构建依赖。先准备与节点发行版匹配的软件源文件，再把它放进 `gpu-operator` 命名空间的 ConfigMap。

下面是 Ubuntu 22.04 x86_64 的结构示例。内部镜像路径按企业仓库填写；ARM64 节点把架构改成 `arm64`，也可以按仓库策略移除架构限制。

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: driver-os-repos
  namespace: gpu-operator
data:
  custom-repo.list: |
    deb [arch=amd64] https://packages.example.com/ubuntu jammy main universe
    deb [arch=amd64] https://packages.example.com/ubuntu jammy-updates main universe
    deb [arch=amd64] https://packages.example.com/ubuntu jammy-security main universe
```

保存为 `driver-os-repos.yaml` 并应用到实验集群，再在 `values-driver-managed.yaml` 的同一个 `driver` 块里加入引用。

```bash
kubectl create namespace gpu-operator \
  --dry-run=client \
  -o yaml \
  | kubectl apply -f -

kubectl apply -f driver-os-repos.yaml
```

```yaml
driver:
  repoConfig:
    configMapName: driver-os-repos
```

Operator 会根据节点 OS 把 ConfigMap 中的文件挂到相应的软件源目录。Ubuntu 使用 `.list` 或 `.sources` 文件；RHEL、CentOS、Rocky 和 RHCOS 使用 `.repo` 文件。其他发行版必须先按当前 Platform Support 或对应合作伙伴文档确认支持路径。内部仓库至少要包含与 `uname -r` 精确匹配的内核 headers、image/modules 或 kernel-devel/kernel-core，以及与内核构建相匹配的 GCC 等依赖。

`repoConfig` 只会追加仓库定义，Driver Container 原有的软件源还在。严格离线或要求来源可审计时，需要调整仓库优先级、禁用默认源，或者用网络策略限制出口。

内部 HTTPS 软件仓库使用企业 CA 时，再创建一个包含 `.crt` 或目标发行版所需证书格式的 ConfigMap，并加入下面的配置。

```bash
kubectl create configmap driver-repo-ca \
  --namespace gpu-operator \
  --from-file=corp-ca.crt
```

```yaml
driver:
  certConfig:
    name: driver-repo-ca
```

这个 CA 只供 Driver Container 访问 OS 软件包仓库使用，和私有镜像仓库证书、Secure Boot 模块签名都没关系。软件源需要走代理时，通过 `driver.env` 同时传入大写和小写的 `HTTP_PROXY`、`HTTPS_PROXY` 与 `NO_PROXY`。节点拉容器镜像的代理仍要单独配在 containerd。

预编译 Driver Container 不在节点上现场下载这些构建包，通常不需要 `repoConfig`，但仍要确保精确匹配的预编译镜像已经进入可访问的 Registry。

#### 8.3.3 安装并验证最终使用的版本和地址

使用私有仓库时，先确认 `gpu-operator` 命名空间里已经有 `registry-cred`。启用 `repoConfig` 或 `certConfig` 时，它们引用的 ConfigMap 也要先创建。确认无误后再安装。

```bash
GPU_OPERATOR_VERSION='v26.3.3'

helm install gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --create-namespace \
  --version "$GPU_OPERATOR_VERSION" \
  -f values-driver-managed.yaml
```

先看 `ClusterPolicy` 保存的期望值。

```bash
kubectl get clusterpolicy cluster-policy \
  -o jsonpath='{.spec.driver.repository}{"/"}{.spec.driver.image}{":"}{.spec.driver.version}{"\n"}'
```

再看 Operator 生成的 Driver DaemonSet，这里能看到包含 OS 标签的最终镜像。

```bash
kubectl get daemonset nvidia-driver-daemonset \
  -n gpu-operator \
  -o jsonpath='{range .spec.template.spec.containers[?(@.name=="nvidia-driver-ctr")]}{.image}{"\n"}{end}'
```

使用 `NVIDIADriver` CRD 时，字段位于 `spec.repository`、`spec.image`、`spec.version` 和 `spec.imagePullSecrets`，OS 软件源引用写作 `spec.repoConfig.name`。

修改已有集群的 `driver.version` 会触发驱动升级，`repository` 或 `repoConfig` 引用的变化也会改动 Driver Pod 模板。这些变更应进入完整的 values 或 GitOps 配置，并安排维护窗口。

同名 ConfigMap 只改内容时，`subPath` 挂载不会在现有 Pod 中刷新，`OnDelete` Driver DaemonSet 也不会主动重建 Pod。需要在维护窗口手工安排重建。带 `nvidia.com/gpu.deploy.driver=false` 标签的节点继续使用宿主机预装驱动，以上字段不会接管它。全局设置 `driver.enabled=false` 时，所有 GPU 节点都由宿主机侧管理驱动。

### 8.4 盯住 Driver Pod 的日志

```bash
kubectl get clusterpolicy cluster-policy -w

kubectl get pods -n gpu-operator -o wide -w
```

另开终端查看 Driver 日志。

```bash
kubectl get pods -n gpu-operator \
  -l app=nvidia-driver-daemonset

DRIVER_POD=$(kubectl get pods -n gpu-operator \
  -l app=nvidia-driver-daemonset \
  -o jsonpath='{.items[0].metadata.name}')

kubectl logs -n gpu-operator \
  "$DRIVER_POD" \
  -c nvidia-driver-ctr \
  --follow
```

Pod 卡在 initContainer 时，查看 Driver Manager。

```bash
kubectl logs -n gpu-operator \
  "$DRIVER_POD" \
  -c k8s-driver-manager
```

日志里要看清几件事，识别到了什么 OS 和内核，选择了什么 Driver 与模块类型，headers 有没有找到，模块是否加载成功，`nvidia-smi` 卡在哪一步。

## 9. 驱动安装后怎样做分层验收

`ClusterPolicy=ready` 只说明控制循环收敛了。验收还得从内核一路查到 Kubernetes，这样出错时才知道断在哪一层。

### 9.1 Driver Pod 层

```bash
kubectl get daemonset nvidia-driver-daemonset \
  -n gpu-operator

DRIVER_POD=$(kubectl get pods -n gpu-operator \
  -l app=nvidia-driver-daemonset \
  -o jsonpath='{.items[0].metadata.name}')

kubectl exec -n gpu-operator \
  "$DRIVER_POD" \
  -c nvidia-driver-ctr \
  -- nvidia-smi
```

### 9.2 宿主机内核层

下面几条在对应节点执行。

```bash
uname -r
lsmod | grep '^nvidia'
cat /proc/driver/nvidia/version
ls -l /dev/nvidia*
```

这一步确认 NVIDIA 模块已经加载进宿主机内核。Driver Container 里有 `nvidia-smi` 二进制文件，并不能证明模块已经可用。

### 9.3 容器化驱动根目录

```bash
find /run/nvidia/driver -maxdepth 2 \
  -type d \
  | head -n 30
```

这个路径存在且内容完整，是 Toolkit 获得用户态驱动文件的必要条件之一。

### 9.4 Toolkit 与容器运行时层

先从 Kubernetes 控制面检查 DaemonSet、日志和当前注入模式。

```bash
kubectl get daemonset nvidia-container-toolkit-daemonset \
  -n gpu-operator

kubectl logs -n gpu-operator \
  daemonset/nvidia-container-toolkit-daemonset \
  -c nvidia-container-toolkit-ctr

kubectl get clusterpolicy cluster-policy \
  -o jsonpath='{.spec.cdi.enabled}{"\t"}{.spec.cdi.nriPluginEnabled}{"\n"}'
```

再到对应 GPU 节点检查 CDI 规范文件和 containerd 实际配置。

```bash
find /var/run/cdi -maxdepth 1 -type f -print

containerd config dump | grep -A 12 -B 3 nvidia
```

本文采用默认的 `CDI=true、NRI=false`，CDI 规范文件和 NVIDIA runtime 配置都要检查。启用 NRI 后，Toolkit 会跳过 containerd 配置修改，此时应改查 NRI Plugin 和 CDI 状态。

### 9.5 Kubernetes 资源层

```bash
kubectl get nodes \
  -o custom-columns=NAME:.metadata.name,GPU-CAPACITY:.status.capacity.nvidia\.com/gpu,GPU-ALLOCATABLE:.status.allocatable.nvidia\.com/gpu

kubectl get pods -n gpu-operator \
  -l app=nvidia-cuda-validator \
  -o wide
```

验收收尾时运行一个 CUDA 工作负载，确认 Driver、Toolkit、Device Plugin、资源上报和实际计算都正常。

## 10. 常见故障应该从哪一层排查

| 现象 | 更可能的层 | 先检查什么 |
| --- | --- | --- |
| Driver Pod `ImagePullBackOff` | 镜像分发 | 仓库地址、镜像标签、代理、证书和拉取凭据 |
| `Could not resolve Linux kernel version` | 内核构建依赖 | `uname -r`、headers/kernel-devel 是否仍在软件源中 |
| `k8s-driver-manager` init 失败 | 旧驱动或客户端 | 是否还有 GPU Pod/宿主进程占用设备，旧模块能否卸载 |
| Driver Container 的 `nvidia-smi` 失败 | 驱动/内核/GPU | Driver 日志、`lsmod`、`/proc/driver/nvidia/version`、`dmesg` |
| `modprobe` 报签名或权限问题 | 启动安全策略 | Secure Boot、内核 lockdown 与所用 Operator 版本的平台限制 |
| Driver Ready，但 Toolkit 卡住 | 容器运行时 | Toolkit 日志、containerd socket、配置路径、CDI/runtime 模式 |
| Toolkit Ready，但没有 `nvidia.com/gpu` | Device Plugin | Device Plugin 日志、NVML、kubelet plugin socket |
| 多个 Operand 同时卡在 `Init` | 上游校验 | Driver、Toolkit 和 `/run/nvidia/validations`，不要逐个重启下游 |

官方排障文档建议先看 `nvidia-driver-ctr` 或 `k8s-driver-manager` 日志，再查内核 `dmesg`。可以先过滤下面两类信息。

```bash
sudo dmesg | grep -i NVRM
sudo dmesg | grep -i Xid
```

`dmesg` 能补上 Driver Pod 日志里看不到的模块加载、固件、PCI 和 GPU 初始化错误。

针对本文使用的 v26.3.3，官方排障文档仍要求关闭 EFI Secure Boot。`driver.certConfig` 只给 Driver Container 配置私有软件仓库证书，和内核模块签名无关。

## 11. 驱动升级远比换镜像麻烦

DaemonSet 换了镜像，宿主机里已经加载的旧模块并不会自动替换。官方的升级顺序如下。

1. 停止所有 Driver 客户端；
2. 卸载旧 NVIDIA 内核模块；
3. 启动新版 Driver Pod；
4. 安装并加载新版模块；
5. 重新启用 Toolkit、Device Plugin 和业务工作负载。

GPU Operator 的 Upgrade Controller 用节点标签跟踪这个过程，并可按策略执行封锁节点（cordon）、等待任务结束、驱逐 GPU Pod、清空节点（drain）、重建 Driver Pod、校验和解除封锁（uncordon）。

启用自动升级前，需要把这些策略定清楚。

- `maxParallelUpgrades` 与 `maxUnavailable` 允许多少节点同时不可用。并行数设为 1 只控制一次处理一个节点，不代表业务无中断；
- `waitForCompletion` 要等待哪些任务，以及超时后如何处理；
- `gpuPodDeletion` 是否允许强制删除，以及能否接受 `emptyDir` 数据丢失；
- 是否启用 `drain`。它可能驱逐节点上的非 GPU 工作负载，只应在 GPU Pod 删除不足以完成升级时使用；
- PodDisruptionBudget、任务检查点、容量冗余和失败回退是否已准备好。

用节点标签观察升级进度。

```bash
kubectl get node -l nvidia.com/gpu.present \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels.nvidia\.com/gpu-driver-upgrade-state}{"\n"}{end}'
```

两种驱动模式的管理边界不同。

- `driver.enabled=true`，Operator 管理容器化驱动的生命周期，可以使用 Driver Upgrade Controller；
- `driver.enabled=false`，驱动预装在宿主机，Operator 不负责升级、降级或恢复它。

所以在上一篇的两台 RTX 3080 Ti 环境里，即使执行 `helm upgrade` 或 `helm rollback`，宿主机上的 570.153.02 驱动也不会跟着变化。

驱动回退同样需要客户端停止、模块卸载和重新校验，不能把 Helm rollback 当成无损的内核驱动回滚按钮。

## 12. 生产环境到底选哪种驱动方式

| 方式 | 更适合的场景 | 主要代价 |
| --- | --- | --- |
| 宿主机预装 Driver | 现有镜像体系成熟、GPU 节点 OS 不同、驱动由节点运维平台统一管理 | Operator 看得到驱动，但不管理其生命周期 |
| 传统 Driver Container | GPU 节点 OS 统一，希望在 GPU 节点扩缩容时自动部署和维护驱动 | 依赖 headers、GCC、软件源和现场构建，启动时间更长 |
| 预编译 Driver Container | 内核版本固定、网络受限、希望减少现场编译和节点初始化耗时的波动 | 镜像必须精确匹配，支持组合与功能有限 |
| `NVIDIADriver` CRD | 新集群需要按节点选择多个 Driver 版本、类型或 OS | API 仍为 `v1alpha1`，与 `ClusterPolicy` 驱动管理互斥，不能原地切换 |

大规模、同构、自动扩缩的 GPU 节点池很适合容器化驱动；内核和 OS 变化频繁、节点镜像已有严格发布流程的环境，宿主机预装可能更可控；内核固定且离线要求高的集群，预编译 Driver Container 更容易实现可重复部署。

同一节点的驱动生命周期只能有一个负责人。节点镜像系统和 GPU Operator 同时管理驱动，版本源、维护窗口和回滚责任很快就会乱掉。

## 13. 回到开头那个问题

GPU Operator 能从 Pod 里安装驱动，靠的是一组明明白白的节点级权限。Driver Pod 共享宿主机内核和 PID 视图，再通过 privileged、hostPath 与挂载传播处理模块和驱动文件。

NFD 先靠 PCI 标签找到 GPU，Operator 创建 Driver DaemonSet，Driver Container 加载模块并暴露 `/run/nvidia/driver`，Toolkit 接好 CDI 和容器注入链路，Device Plugin 完成 `nvidia.com/gpu` 注册。这条顺序一旦弄清，前面那串 Pod 为什么会卡在 `Init`，也就不神秘了。

传统 Driver Container 适合灵活适配，预编译 Driver Container 更容易做出可重复的离线部署。无论选哪条路，都要匹配 GPU、Driver、OS 和内核，升级时也得给业务留出维护窗口。

真要动手，先找一台能快照回滚的干净节点，按第 9 节把每一层的证据留好。看到 `ready` 只是开始，能说清模块加载在哪、用户态库从哪来、下一层在等谁，这次实验才算跑明白。

## 14. 官方资料与源码

### 官方文档

- [安装与当前补丁版本](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/getting-started.html)
- [Release Notes](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/release-notes.html)
- [Platform Support 与生命周期](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/platform-support.html)
- [预编译驱动](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/precompiled-drivers.html)
- [Driver 升级](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/gpu-driver-upgrades.html)
- [`NVIDIADriver` CRD](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/gpu-driver-configuration.html)
- [CDI 与 NRI](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/cdi.html)
- [离线环境与本地仓库](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/install-gpu-operator-air-gapped.html)
- [旧内核软件源](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/install-gpu-operator-outdated-kernels.html)
- [HTTP/HTTPS 代理](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/install-gpu-operator-proxy.html)
- [GPU Operator 排障](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.3/troubleshooting.html)
- [Container Toolkit v1.19.1 架构](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/1.19.1/arch-overview.html)

### 源码定位

- [v26.3.3 默认 values](https://github.com/NVIDIA/gpu-operator/blob/v26.3.3/deployments/gpu-operator/values.yaml)
- [`ClusterPolicy` 状态机](https://github.com/NVIDIA/gpu-operator/blob/v26.3.3/controllers/state_manager.go)
- [Driver DaemonSet](https://github.com/NVIDIA/gpu-operator/blob/v26.3.3/assets/state-driver/0500_daemonset.yaml)
- [Validator](https://github.com/NVIDIA/gpu-operator/blob/v26.3.3/cmd/nvidia-validator/main.go)
- [Toolkit 等待脚本](https://github.com/NVIDIA/gpu-operator/blob/v26.3.3/assets/state-container-toolkit/0400_configmap.yaml)
- [Ubuntu Driver Container 构建流程，固定历史提交](https://github.com/NVIDIA/gpu-driver-container/blob/94078eae807f9709cca4756b3a8a736b002a99a6/ubuntu22.04/nvidia-driver)
- [部署前核对最新版文档](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/)
