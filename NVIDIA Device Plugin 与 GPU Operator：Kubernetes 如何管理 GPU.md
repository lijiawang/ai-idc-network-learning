# NVIDIA GPU Operator 实战：用 Kubernetes 管理两台 RTX 3080 Ti

GPU Operator 最新稳定版本是 v26.3.3，但它不支持我使用的 RTX 3080 Ti，CUDA Validator 无法通过校验，所以本文改用 v25.3.4。

上一篇把两台 RTX 3080 Ti 加进 Kubernetes，并用独立的 NVIDIA Device Plugin 跑通了 CUDA Pod。那套方案已经能用，但驱动、Container Toolkit、Device Plugin、节点标签和监控分散在不同地方：一部分装在宿主机，一部分靠 YAML 部署，出了问题也要逐层排查。

这次我想继续往前走一步，把 GPU Operator 装起来，看看它究竟接管了什么。两台机器已经有 570.153.02 驱动和 Container Toolkit 1.19.1，所以这次不重装驱动，也不改运行时，Device Plugin 改由 Operator 管理。

使用 Device Plugin 时，Pod 通过下面这段配置申请 GPU：

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

改用 GPU Operator 后，Pod 申请 GPU 的写法不变；Device Plugin、硬件发现、监控和健康检查则由 GPU Operator 部署并持续维护。

先把结果放在前面：

| 项目 | 实测结果 |
| --- | --- |
| GPU Operator | v25.3.4，Helm 状态 `deployed` |
| ClusterPolicy | `ready` |
| NVIDIA 驱动 | 保留宿主机 570.153.02，Operator 不重复安装 |
| NVIDIA Container Toolkit | 保留宿主机 1.19.1，Operator 不重复安装 |
| Device Plugin | 由 GPU Operator 管理，DaemonSet `2/2 Ready` |
| GPU Feature Discovery | 两个节点均为 `Running` |
| DCGM Exporter | 两个节点均为 `Running` |
| GPU 资源 | 两个节点各上报 `nvidia.com/gpu=1` |
| CUDA Validator | 两个节点均返回 `cuda workload validation is successful` |

## 1. 先弄清 GPU Operator 接管了什么

GPU Operator 不是驱动，也不是新的 GPU 调度器。它是一个 Kubernetes 控制器，读取 `ClusterPolicy`，再去部署和检查驱动、Container Toolkit、Device Plugin、GFD、DCGM Exporter 等组件。

![Kubernetes GPU 软件栈](assets/kubernetes-gpu/gpu-software-stack.png)

*图 1：GPU Operator 位于 Kubernetes 与节点 GPU 软件栈之间。*

其中 Device Plugin 仍然负责向 kubelet 注册 `nvidia.com/gpu`。Scheduler 的行为也没有改变，它只根据可分配的 GPU 数量选节点，不会因为装了 Operator 就突然懂得显存、温度或实时利用率。

## 2. 为什么不只安装 Device Plugin

上一篇直接部署 Device Plugin 后，两台节点都能上报 GPU，学习整卡调度已经够用。它没有解决的是后续维护：谁来发现节点特征，谁来装 DCGM Exporter，谁来验证 CUDA 链路，组件版本又怎么保持一致。

GPU Operator 把这些工作收拢到一个 `ClusterPolicy` 下面。代价是组件明显变多，安装也不再只是 `kubectl apply` 一个 DaemonSet。Operator 会部署自己的 Device Plugin，所以原来单独安装的那套最终必须删掉。

## 3. NVIDIA GPU Operator 做了什么

安装 GPU Operator 后，集群里会多出一组相互配合的组件：

| 组件 | 作用 |
| --- | --- |
| NVIDIA Driver | 在 GPU 节点上提供内核驱动 |
| NVIDIA Container Toolkit | 配置容器运行时访问 GPU |
| NVIDIA Device Plugin | 将 GPU 暴露为 Kubernetes 资源 |
| Node Feature Discovery | 发现节点硬件特征 |
| GPU Feature Discovery | 添加 GPU 型号、显存和能力等标签 |
| DCGM / DCGM Exporter | 健康诊断与 Prometheus 指标 |
| MIG Manager | 管理支持 MIG 的 GPU 分区 |
| Operator Validator | 验证驱动、Toolkit、Device Plugin 和 CUDA 是否工作 |

Device Plugin 仍是原来的 Device Plugin，只是改由 Operator 创建和维护。GPU Operator 真正增加的是整套组件的生命周期管理。

![NVIDIA Device Plugin 与 GPU Operator 的职责边界](assets/kubernetes-gpu/device-plugin-vs-gpu-operator.png)

*图 2：Device Plugin 是 GPU Operator 管理的软件栈中的一个组件。*

## 4. 单独安装与 Operator 管理的区别

| 对比项 | 独立 Device Plugin | GPU Operator |
| --- | --- | --- |
| GPU 资源暴露 | 支持 | 通过其管理的 Device Plugin 支持 |
| 驱动安装 | 集群外完成 | 可由 Operator 管理，也可使用预装驱动 |
| Container Toolkit | 集群外完成 | 可由 Operator 管理，也可使用预装 Toolkit |
| 节点标签 | 需另行部署 GFD | 自动管理 NFD/GFD |
| GPU 监控 | 需另行部署 DCGM Exporter | 可统一部署 |
| MIG 管理 | 需手动或另行部署 | 可通过 MIG Manager 管理 |
| 故障验证 | 主要依赖人工检查 | 提供 Validator 工作负载 |
| 资源开销 | 较小 | 组件更多、开销更高 |
| 控制方式 | 主机配置、IaC 加 DaemonSet | Helm、CRD 和 Operator 调谐 |
| 适用环境 | 已准备好的简单或托管环境 | 需要标准化和生命周期管理的生产环境 |

我更愿意把它看成管理边界的选择。只装 Device Plugin，驱动和运行时继续由云镜像、Ansible 或运维脚本负责；使用 GPU Operator，则把更多节点侧状态交给 Kubernetes。已经有成熟裸机镜像流水线的环境，不一定非要让 Operator 安装驱动。

## 5. 在两台 RTX 3080 Ti 集群上如何选择

上一篇的两个节点已经具备：

- NVIDIA 驱动 570.153.02；
- NVIDIA Container Toolkit 1.19.1；
- 已配置的 containerd NVIDIA runtime；
- NVIDIA Device Plugin v0.17.1。

这套环境没必要为了安装 Operator 再折腾一遍驱动。我最终保留主机现状，只让 Operator 接管 Device Plugin、GFD、DCGM Exporter 和 Validator。

> RTX 3080 Ti 属于消费级 GPU，不支持 MIG，也不在 GPU Operator 官方的数据中心 GPU 支持列表中。本次组合还使用了 Kubernetes v1.36.2，因此应把它看成兼容性实验，而不是 NVIDIA 官方支持的生产基线。

## 6. 安装 GPU Operator

安装时最需要注意的是 Device Plugin。直接删掉旧 DaemonSet，会让节点暂时丢失 `nvidia.com/gpu`；不删，又会留下两套插件。我的做法是先关闭 Operator 自带的 Device Plugin，把其他组件装好，最后再切换 Device Plugin。

安装前先记录当前状态：

```bash
kubectl get nodes \
  -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\\.com/gpu

kubectl get pods -A -o wide
kubectl -n kube-system get daemonset nvidia-device-plugin-daemonset -o yaml \
  > ~/nvidia-device-plugin-daemonset-before-gpu-operator.yaml
```

先停止 GPU 工作负载，但暂时不要删除旧 Device Plugin：

```bash
kubectl scale deployment/gpu-test --replicas=0
```

### 6.1 最终安装版本：GPU Operator v25.3.4

添加 NVIDIA Helm 仓库：

```bash
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update
helm search repo nvidia/gpu-operator --versions | head
```

![Helm 仓库中的 GPU Operator 版本](assets/kubernetes-gpu/gpu-operator-helm-versions.png)

*图 3：Helm 仓库中的最新稳定版本是 v26.3.3，本文最终安装的是 v25.3.4。*

本次实验最终运行的是：

```text
GPU Operator Helm Chart：v25.3.4
GPU Operator Controller：v25.3.4
NVIDIA Device Plugin：v0.17.4
```

可以通过下面的命令确认 Helm 实际安装版本：

```bash
helm list -n gpu-operator
helm status gpu-operator -n gpu-operator
helm get values gpu-operator -n gpu-operator
```

本文得到的 Helm 状态为：

```text
NAME: gpu-operator
NAMESPACE: gpu-operator
STATUS: deployed
CHART: gpu-operator-v25.3.4
```

在确定最终版本之前，我也测试过 GPU Operator v26.3.3。Operator、NFD、GFD、DCGM Exporter 和 Device Plugin 都能启动，但 v26 自带的 CUDA Validator 在 RTX 3080 Ti 与 570.153.02 驱动上失败：

```text
Failed to allocate device vector A
(error code forward compatibility was attempted on non supported HW)
```

这不是 Scheduler 或 Device Plugin 故障，而是 Validator 使用的 CUDA 与消费级 Ampere GPU、570 驱动组合不兼容。单独混用 v25 Validator 和 v26 Operator 也不可行，旧 Validator 的 `driver-validation` 会以退出码 127 失败。

因此，v26.3.3 仅作为失败的兼容性测试记录，本实验最终统一安装实测通过的 **GPU Operator v25.3.4**。下面的安装命令直接写明版本，不再使用版本占位符。

生产环境不能照抄这个选择。应优先依据 NVIDIA Platform Support 与 Release Notes 选择受支持的 Kubernetes、操作系统、GPU、驱动和 Operator 组合。

### 6.2 先安装基础组件，再切换 Device Plugin

第一次安装先把 `devicePlugin.enabled` 设成 `false`：

这两台云主机拉取官方镜像时出现过超时，安装时实际用了下面三个 DaoCloud 镜像仓库：

```text
Operator、Device Plugin、GFD：
m.daocloud.io/nvcr.io/nvidia

Validator：
m.daocloud.io/nvcr.io/nvidia/cloud-native

Node Feature Discovery：
m.daocloud.io/registry.k8s.io/nfd/node-feature-discovery
```

这里只替换镜像仓库，具体镜像名称和版本仍由 GPU Operator v25.3.4 的 Helm Chart 决定。对应关系可以在下面命令的 `repository` 参数中看到。

首次安装时，通过 Helm 的 `--set` 参数覆盖仓库地址：

```bash
--set operator.repository=m.daocloud.io/nvcr.io/nvidia
--set validator.repository=m.daocloud.io/nvcr.io/nvidia/cloud-native
--set devicePlugin.repository=m.daocloud.io/nvcr.io/nvidia
--set gfd.repository=m.daocloud.io/nvcr.io/nvidia
--set node-feature-discovery.image.repository=m.daocloud.io/registry.k8s.io/nfd/node-feature-discovery
```

如果 GPU Operator 已经安装，可以保留其他配置，只修改镜像仓库：

```bash
helm upgrade gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --version v25.3.4 \
  --reuse-values \
  --set operator.repository=m.daocloud.io/nvcr.io/nvidia \
  --set validator.repository=m.daocloud.io/nvcr.io/nvidia/cloud-native \
  --set devicePlugin.repository=m.daocloud.io/nvcr.io/nvidia \
  --set gfd.repository=m.daocloud.io/nvcr.io/nvidia \
  --set node-feature-discovery.image.repository=m.daocloud.io/registry.k8s.io/nfd/node-feature-discovery
```

修改后查看 Pod 实际使用的镜像：

```bash
kubectl get pods -n gpu-operator \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{range .spec.initContainers[*]}{"  init: "}{.image}{"\n"}{end}{range .spec.containers[*]}{"  container: "}{.image}{"\n"}{end}{end}'
```

输出中的镜像地址应以 `m.daocloud.io/` 开头。接下来是本文首次安装时使用的完整命令：

```bash
helm install gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --create-namespace \
  --version v25.3.4 \
  --set driver.enabled=false \
  --set toolkit.enabled=false \
  --set cdi.enabled=false \
  --set devicePlugin.enabled=false \
  --set operator.repository=m.daocloud.io/nvcr.io/nvidia \
  --set validator.repository=m.daocloud.io/nvcr.io/nvidia/cloud-native \
  --set devicePlugin.repository=m.daocloud.io/nvcr.io/nvidia \
  --set gfd.repository=m.daocloud.io/nvcr.io/nvidia \
  --set node-feature-discovery.image.repository=m.daocloud.io/registry.k8s.io/nfd/node-feature-discovery
```

等 Operator 和 NFD 正常启动：

```bash
kubectl get pods -n gpu-operator -o wide
kubectl get clusterpolicy
```

再删除旧 DaemonSet，马上启用 Operator 管理的版本：

```bash
kubectl delete daemonset \
  -n kube-system \
  nvidia-device-plugin-daemonset

helm upgrade gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --version v25.3.4 \
  --reuse-values \
  --set devicePlugin.enabled=true
```

这样安装其他组件时 GPU 资源仍由旧插件维持，真正的中断只发生在最后一次切换。如果新插件没有起来，前面保存的 YAML 也能用来恢复。

> 如果只预装了驱动、没有安装 Toolkit，应只设置 `driver.enabled=false`。如果驱动和 Toolkit 都希望由 Operator 管理，则不要关闭它们，但必须先确认操作系统、内核、Secure Boot、GPU 型号和驱动版本均在支持范围内。

## 7. 验证 GPU Operator

先查看命名空间中的 Pod、Service、DaemonSet 和 Deployment：

```bash
kubectl -n gpu-operator get all
```

![GPU Operator 组件运行状态](assets/kubernetes-gpu/gpu-operator-resources-running.png)

*图 4：GPU Operator 安装完成后的资源状态，两个节点上的 Device Plugin、GFD、DCGM Exporter 和 Validator 均已正常运行。*

截图已经能看出各组件的运行情况，接下来只检查三个关键结果。首先确认 `ClusterPolicy`：

```bash
kubectl get clusterpolicy cluster-policy \
  -o jsonpath='{.status.state}{"\n"}'
```

实测输出：

```text
ready
```

然后检查两个节点上报的 GPU：

```bash
kubectl get nodes \
  -o custom-columns=NAME:.metadata.name,GPU-CAPACITY:.status.capacity.nvidia\\.com/gpu,GPU-ALLOCATABLE:.status.allocatable.nvidia\\.com/gpu
```

实测结果：

```text
NAME          GPU-CAPACITY   GPU-ALLOCATABLE
10-60-50-9    1              1
10-60-8-241   1              1
```

最后查看 CUDA Validator：

```bash
kubectl get pods -n gpu-operator -l app=nvidia-cuda-validator -o wide
kubectl logs -n gpu-operator <nvidia-cuda-validator-pod>
```

日志为：

```text
cuda workload validation is successful
```

最后创建一个真正申请 GPU 的 Pod：

```bash
kubectl run gpu-operator-smoke-test \
  --restart=Never \
  --image=nvcr.io/nvidia/k8s/cuda-sample:vectoradd-cuda12.5.0 \
  --overrides='{"apiVersion":"v1","spec":{"containers":[{"name":"gpu-operator-smoke-test","image":"nvcr.io/nvidia/k8s/cuda-sample:vectoradd-cuda12.5.0","resources":{"limits":{"nvidia.com/gpu":1}}}]}}'

kubectl wait \
  --for=jsonpath='{.status.phase}'=Succeeded \
  pod/gpu-operator-smoke-test \
  --timeout=10m

kubectl get pod gpu-operator-smoke-test -o wide
kubectl logs gpu-operator-smoke-test
kubectl delete pod gpu-operator-smoke-test
```

![GPU Operator 调度 CUDA Pod 测试](assets/kubernetes-gpu/gpu-operator-cuda-pod-test.png)

*图 5：测试 Pod 申请一块 GPU 后被调度到 worker `10-60-8-241`，CUDA vector-add 返回 `Test PASSED`，测试结束后 Pod 已删除。*

`ClusterPolicy=ready`、两个节点各有一块可分配 GPU，CUDA Validator 和实际 GPU Pod 都运行成功，说明 GPU Operator 已经正常工作。

## 8. 装完 Operator，调度能力并没有自动升级

GPU Operator 管的是节点软件栈，不是训练作业队列。装完以后，默认调度仍然是整卡计数：`nvidia.com/gpu: 1` 申请一块 GPU，不能写成 `0.5`。这两台机器各有一块卡，所以默认最多同时满足两个单卡 Pod。

Time-Slicing 和 MPS 可以继续配置，但它们属于 Device Plugin 的共享策略。Time-Slicing 不提供显存隔离，也不能把一个物理 GPU 真的变成几块独立 GPU。MIG 的隔离更彻底，但 RTX 3080 Ti 不支持，本文也就没有部署 MIG Manager。

训练排队、配额、Gang Scheduling、多租户公平共享，以及 NVLink、NUMA、网络拓扑感知，都不是 GPU Operator 负责的事情。这些要交给 Kueue、Volcano 或其他调度扩展。

## 9. 常见故障及排查顺序

### 9.1 Node 没有 `nvidia.com/gpu`

按依赖顺序检查，不要只盯着 Device Plugin：

```bash
nvidia-smi
sudo ctr plugins ls
sudo nvidia-ctk runtime configure --runtime=containerd
kubectl -n gpu-operator get pods
kubectl -n gpu-operator logs daemonset/nvidia-device-plugin-daemonset
```

如果宿主机的 `nvidia-smi` 已经失败，应先修复驱动，Kubernetes 层无法绕过这个问题。

### 9.2 Pod 一直 Pending

查看调度事件：

```bash
kubectl describe pod <pod-name>
```

常见原因包括：

- 所有 GPU 已被其他 Pod 分配；
- Pod 同时使用了 nodeSelector、亲和性或污点容忍条件，导致没有可用节点；
- 请求的 MIG 或共享资源名称与节点实际上报的不一致；
- Device Plugin 尚未注册或正在重启。

### 9.3 Pod 已运行但 CUDA 不可用

检查：

```bash
kubectl exec <pod-name> -- nvidia-smi
kubectl logs <pod-name>
kubectl -n gpu-operator get pods
sudo journalctl -u containerd -u kubelet --since '10 minutes ago'
```

这类问题通常位于 Toolkit、containerd runtime、驱动兼容性或容器镜像，而不一定是 Scheduler。

### 9.4 Operator 长时间不是 ready

查看 ClusterPolicy 和 Validator：

```bash
kubectl describe clusterpolicy cluster-policy
kubectl get pods -n gpu-operator
kubectl logs -n gpu-operator <validator-pod-name> --all-containers
```

驱动容器还可能受内核头文件、Secure Boot、内核版本和操作系统支持范围影响。生产环境升级前应先在独立节点池验证，而不是直接对整个 GPU 集群滚动变更。

这次实际碰到的问题主要有三个：

- NFD 为 `ImagePullBackOff`：`registry.k8s.io` 跳转到 `*.docker.pkg.dev` 后超时，改用 DaoCloud NFD 镜像。
- GFD 或 Device Plugin 为 `ImagePullBackOff`：访问 `nvcr.io` TLS 握手超时，改用 `m.daocloud.io/nvcr.io/nvidia`。
- Validator 报 `forward compatibility was attempted on non supported HW`：Operator 自带 CUDA 校验版本与 RTX 3080 Ti、宿主机驱动不兼容，不能误判为 Device Plugin 没注册。

三种问题最后都可能显示为 `ClusterPolicy=notReady`，但原因完全不同。先看 Pod 是否成功拉到镜像，再看 Device Plugin 是否注册，最后才查 CUDA 与驱动兼容性，会省掉很多无效排查。

## 10. 最后

安装 GPU Operator 不会改变 Pod 申请 GPU 的 YAML。变化都在基础设施层：原来单独安装的 Device Plugin 被 Operator 接管，NFD/GFD 开始维护节点标签，DCGM Exporter 提供监控，Validator 负责检查整条 CUDA 链路。

对这两台已经装好驱动的机器来说，`driver.enabled=false` 和 `toolkit.enabled=false` 是最重要的两个参数。GPU Operator 并不要求一定由它安装驱动，已有的主机软件栈完全可以保留。

真正花时间的反而是版本和镜像。v26.3.3 的组件能运行，但 CUDA Validator 与 RTX 3080 Ti、570 驱动不兼容；切回统一的 v25.3.4 后才全部通过。国内网络下，NFD 和 NVIDIA 镜像也最好提前准备镜像加速。最终两台节点都上报 `nvidia.com/gpu=1`，`ClusterPolicy` 为 `ready`，GPU Operator 安装完成。

## 11. 官方参考资料

- Kubernetes Device Plugins：<https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/>
- Kubernetes GPU 调度：<https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/>
- NVIDIA Kubernetes Device Plugin：<https://github.com/NVIDIA/k8s-device-plugin>
- NVIDIA GPU Operator：<https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/>
- NVIDIA GPU Operator 安装指南：<https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/getting-started.html>
- NVIDIA GPU Operator Platform Support：<https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/platform-support.html>
- NVIDIA Container Toolkit：<https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/>
