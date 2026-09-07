# Kubernetes 已经能跑 Pod，为什么还需要 KubeRay？

## 1. 认识 KubeRay，以及它和 Ray 的关系

KubeRay 是用于在 Kubernetes 上部署和管理 Ray 应用的开源项目，核心组件是 KubeRay Operator。它负责集群的创建、作业的提交、服务的升级，以及按配置回收资源。[项目说明](https://github.com/ray-project/kuberay/blob/v1.6.2/README.md)

Ray 是运行分布式程序的计算框架。开发者把计算写成 Task（任务）或 Actor（有状态的计算进程），Ray 将它们调度到有资源的节点上执行。Ray 可以在本机、虚拟机或 Kubernetes 上运行，并不依赖 KubeRay。[Ray 介绍](https://github.com/ray-project/ray/blob/ray-2.57.0/README.rst)

例如批量处理图片，可以把不同批次交给多个 Task 并行执行；反复使用已加载模型的对象，可以写成 Actor。程序怎样拆分仍要开发者设计，部署 Ray 或 KubeRay 不会自动改写业务代码。

Kubernetes 负责把 Pod 放到机器上、重启失败的容器。Ray 负责分布式程序的调度和执行，KubeRay 负责 Ray 集群、作业和服务在 Kubernetes 上的生命周期。三者各管一层。

### Ray 集群长什么样

Ray 集群包含一个 Head，可按需增加 Worker。在 KubeRay 中，它们通常分别运行在 Pod 里。Head 上的 GCS（全局控制服务）维护集群状态，Worker 启动后向它注册，承担计算任务。

Kubernetes Node 是承载 Pod 的物理机或虚拟机；Ray Node 是运行 raylet 并注册到 Ray 集群的逻辑节点，通常对应一个 Ray Pod。两种 Node 不要混淆。

### 为什么还需要 Operator

普通 Deployment、StatefulSet 也能拉起 Ray 容器，但建集群、等就绪、提交作业和回收资源之间的顺序与状态，需要自己维护。

使用 KubeRay 时，你提交一份 RayCluster 自定义资源（CR），在 `spec` 中声明 Head、Worker、镜像和资源。Operator 通过 Kubernetes API 创建或更新 Pod、Service 等资源，再把实际状态写回 `status`；RayJob 流程还会创建用于提交程序的 Kubernetes Job。

![Operator 读取配置、创建资源、观察变化并回写状态](./images/kuberay/wechat/02-control.png)

Operator 会持续检查配置和现状。假如受控 Worker Pod 被删除，而期望数量没变，它会补建 Worker。Task、Actor、Placement Group 的调度和对象存储仍由 Ray runtime 负责，Operator 不逐个调度 Ray Task。

## 2. 搭建 KubeRay

这里从已有 Kubernetes 集群开始，安装 KubeRay Operator 和 CRD（自定义资源定义）。这一步还不会创建 Ray 集群，后面提交 RayJob 时才会创建。

### 准备环境

本文固定使用 KubeRay v1.6.2、Ray 2.57.0 和 `ray.io/v1`。准备好 Helm 3+、能访问目标集群的 kubectl，以及创建 CRD 和集群级 RBAC 的权限。先确认没有连错集群。

```bash
kubectl config current-context
kubectl get nodes
helm version
```

CPU 示例的 Head 和 Worker 各申请 1 CPU、2 GiB 内存，还要给 Operator、提交器和系统组件留出余量。GPU 示例另需两台各有一张空闲 GPU 的节点，并准备好 NVIDIA 驱动和 Device Plugin。

### 安装并验收 Operator

以下是首次安装命令，依据 [v1.6.2 官方 Helm Chart](https://github.com/ray-project/kuberay/blob/v1.6.2/helm-chart/kuberay-operator/README.md)。如果集群已经装过 Operator，不要重复安装，升级注意事项见运维部分。

```bash
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update
helm install kuberay-operator kuberay/kuberay-operator \
  --version 1.6.2 \
  --namespace kuberay-system --create-namespace

kubectl rollout status deployment/kuberay-operator \
  -n kuberay-system --timeout=180s
kubectl get crd rayclusters.ray.io rayjobs.ray.io rayservices.ray.io
```

确认 Deployment 就绪、三类主要 CRD 可查询后，创建实验命名空间。

```bash
kubectl create namespace kuberay-lab --dry-run=client -o yaml | kubectl apply -f -
```

本次验证环境访问 Docker Hub 不稳定，示例使用 DaoCloud 镜像代理。换到自己的环境时，要确认 Operator 镜像和 Ray 镜像都能拉取。

## 3. 使用 KubeRay

### 按工作类型选择对象

| 你要做什么 | 使用的对象 |
| --- | --- |
| 保留一个集群，反复开发、调试或共享计算 | `RayCluster` |
| 跑完一次训练、评估、批推理或 ETL | `RayJob` |
| 持续提供 Ray Serve 在线服务 | `RayService` |

RayCluster 的生命周期独立于某一次程序。RayJob 则把建集群、提交作业、跟踪结果和按配置回收串起来。定时作业还可以考虑 `RayCronJob`，但本文版本中它仍是 Alpha，需要显式开启 feature gate。

### 先跑一个 CPU 作业

从 GitHub 打开 [CPU RayJob 清单](https://github.com/lijiawang/ai-idc-network-learning/blob/main/examples/kuberay/rayjob-cpu-smoke.yaml)，下载到当前目录，保存为 `rayjob-cpu-smoke.yaml`。它包含一份 Python 程序和一份 RayJob 配置，创建一个 Head、一个 Worker，执行返回值为 42 的 Task。

```bash
kubectl apply --dry-run=server -f rayjob-cpu-smoke.yaml
kubectl apply -f rayjob-cpu-smoke.yaml
kubectl get rayjob,raycluster,pod,job -n kuberay-lab
```

`--dry-run=server` 只做服务端校验，不证明程序能跑通。提交后，等待流程完成，再查看提交器日志。

```bash
kubectl wait -n kuberay-lab \
  --for=jsonpath='{.status.jobDeploymentStatus}'=Complete \
  rayjob/ray-cpu-smoke --timeout=20m
kubectl logs -n kuberay-lab job/ray-cpu-smoke --all-containers=true
```

仓库中的这份 CPU 清单已在两节点 Kubernetes 环境执行成功，结果为 `SUCCEEDED / Complete`，日志中出现 `KUBERAY_CPU_SMOKE_OK`。它开启了终态回收，实测十分钟后专属 RayCluster、Head Pod 和 Worker Pod 已删除。

同一个 RayJob 再次 `apply` 不会自动开始新一轮执行。要重复实验，先保存日志，确认旧作业已结束且可以删除，再删除 `ray-cpu-smoke` 对象并重新提交。

### 提交后发生了什么

以默认 `K8sJobMode`、由 `rayClusterSpec` 创建专属集群的方式为例，Operator 先建 RayCluster，等它 Ready 后创建 submitter Job（提交器）。这个 Kubernetes Job 调用 Ray Jobs API，启动执行入口程序的 Driver；Driver 再提交 Task 或 Actor。Ray Jobs API 中的一次应用运行称为 Ray job，不要和 Kubernetes 中的 RayJob CR、submitter Job 混淆。

![RayJob 从创建集群到提交程序，再由 Ray 执行任务](./images/kuberay/wechat/03-job.png)

### 再尝试 GPU 作业

Worker Pod 用 `nvidia.com/gpu` 申请设备，Ray Task 用 `num_gpus` 声明计算需求。这两层配置要对得上。

```yaml
# Worker Pod 申请物理 GPU
resources:
  requests:
    nvidia.com/gpu: "1"
  limits:
    nvidia.com/gpu: "1"
```

```python
# Task 预留逻辑 GPU
@ray.remote(num_gpus=1)
def infer_one_shard(shard):
    ...
```

Kubernetes 给 Pod 分配设备，KubeRay 默认根据主 Ray 容器的 GPU limit 推导逻辑容量，Ray 再按任务需求分配逻辑 GPU，并设置 `CUDA_VISIBLE_DEVICES`。

只给 Pod 配 GPU，却不给任务写 `num_gpus`，Ray 就无法按 GPU 需求约束这些任务的并发。反过来，Ray 没有可用逻辑 GPU，声明需要 GPU 的任务就会等待。

不要把 Pod 的 GPU limit 设为 1，却手工声明 `num-gpus: "2"`。这只会让 Ray 看到虚高的逻辑容量，物理设备和显存不会增加。

还有一个常见误区。两个 Worker 各有一张 GPU，不代表单个 Task 能请求两张。一个 Task 必须放进同一个 Ray Node，不能把不同 Pod 的卡拼起来使用。

从 GitHub 打开 [双 GPU RayJob 清单](https://github.com/lijiawang/ai-idc-network-learning/blob/main/examples/kuberay/rayjob-two-gpu.yaml)，下载到当前目录，保存为 `rayjob-two-gpu.yaml`。它固定两个各占一张 GPU 的 Worker，用 Pod 反亲和强制放到不同 Kubernetes Node，再并发运行两个单 GPU Task，没有启用自动扩缩容。

运行前确认 GPU 有余量，驱动、Device Plugin、CUDA 与镜像兼容，GPU 节点的 taint 有对应 toleration，并确认镜像代理已同步 GPU tag。

```bash
kubectl apply --dry-run=server -f rayjob-two-gpu.yaml
kubectl apply -f rayjob-two-gpu.yaml
```

这份 GPU 清单尚未实机执行。预期成功时，两个任务打印不同的 `kubernetes_node`，最后输出 `SUCCESS: two Ray GPU tasks ran on two different Kubernetes nodes`。

它只检查 GPU 调度和跨节点放置，不验证 CUDA 算子或 NCCL 性能。检查 CUDA 可用性时，应换成目标框架镜像，并在 Task 中运行真实 GPU 算子。

## 4. 运维 KubeRay

### 失败重试、状态恢复与资源回收

失败后的动作要显式配置。顶层 `backoffLimit` 控制整次 RayJob 的重试，默认是 0。提交器失败、Ray 作业失败等都可能触发顶层重试，重试会新建专属集群。`submitterConfig.backoffLimit` 只管提交器自己的重试。

`activeDeadlineSeconds` 覆盖建集群、提交和运行阶段；超时形成的 `DeadlineExceeded` 不会重试。

作业完成也不等于自动删集群。`shutdownAfterJobFinishes` 默认是 `false`。本文清单将它设为 `true`，配合 `ttlSecondsAfterFinished`，在终态后等待指定时间再回收专属 RayCluster。自定义删除策略可以改变行为；RayJob 和 submitter Job 是否保留，还要看删除策略与 Operator 配置。

![失败时按条件重试，终态后按显式配置回收集群](./images/kuberay/wechat/04-retry-cleanup.png)

资源补回来了，程序状态不一定能恢复。Task、Actor 的失败由 Ray 的 `max_retries`、`max_restarts` 等配置处理；Checkpoint、外部写入的去重和幂等仍要应用负责，尤其要考虑整个入口程序重复执行的情况。

例如程序已经向数据库写入一半结果，再次执行时就需要识别已完成记录。否则新集群虽然正常，业务数据仍可能重复。Head 故障后不要依赖原地补建 Pod 恢复当前作业，也不能靠它找回 Driver 的内存状态。

Operator Pod 失败时，由 Deployment 补建，恢复后继续调谐。Worker Pod 或所在 Node 失败时，Kubernetes 和 KubeRay 视容量补建资源；任务重试、状态恢复和业务补偿仍需要 Ray 配置与应用配合。

基于 Redis 的 GCS 容错可保留 GCS 状态。官方建议在 RayService 上启用；其他工作负载不推荐，且不保证兼容性。它不能替应用保存 Driver 的内存或处理重复写入。

### 扩缩容与资源队列

RayJob 通过 `spec.rayClusterSpec.enableInTreeAutoscaling: true` 启用 Ray Autoscaler（自动扩缩容组件）。它根据 Task、Actor 或 Serve replica 产生的逻辑资源需求，在 Worker Group 的 `minReplicas` 和 `maxReplicas` 之间调整 Worker 数量，由 KubeRay 创建对应的 Pod。

机器容量不够时，还需要节点 Autoscaler 或人工补充机器。增加 Worker 数量不会凭空增加物理 GPU。

NVIDIA GPU Operator 负责驱动和 Device Plugin；需要配额与队列时用 Kueue，需要 Gang（成组调度）和 Pod 级批调度时用 Volcano。没有这些需求就不必引入。

### RayService 升级与版本管理

RayService 还负责 Serve 应用的健康检查和升级。修改 `spec.rayClusterConfig` 通常触发默认 `NewCluster` 升级，先创建新集群，等集群和应用健康后，再切换稳定 Service 的流量。仅更新 `serveConfigV2` 中的应用配置，通常可以在原集群内完成。

Autoscaler 管理的 `replicas`、`minReplicas`、`maxReplicas` 和 `scaleStrategy.workersToDelete` 有例外。单独修改这些字段既不触发升级，也不会从 RayService 同步到已有 RayCluster。

换集群期间需要容纳新旧两套资源。GPU 池没有余量，新集群就可能一直等卡，升级也会卡住。

升级 Operator 前要按[官方升级指南](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/upgrade-guide.html)先更新 CRD，Helm 不会自动更新已经安装的 `crds/`。示例镜像完成实测后应固定 digest，避免同名 tag 的内容变化。

### 看状态与排障

![Pod Running 之后，还要检查 Ray 注册、资源和业务任务](./images/kuberay/wechat/01-ready.png)

`Running` 是 Pod 的粗粒度阶段，只表示 Pod 已绑定 Node、容器已创建，至少一个容器在运行、启动或重启。Pod `Ready=True` 还要求所有容器 Ready，且 readiness gate 满足；它仍不能说明 Ray 已看到预期的 Worker、GPU，或者应用结果正确。

KubeRay v1.6.2 的 `RayCluster.status.state=Ready` 主要检查期望数量的 Ray Pod 是否 Running、Ready，不是持续运行的健康检查。Worker 注册数和逻辑资源要用 `ray status` 看，再用小任务确认执行链路。Driver 成功或 Serve replica 健康之后，资源是否回收还要看配置。

- CR / Operator。先看 `kubectl describe rayjob NAME -n NS`，再看 `kubectl logs -n kuberay-system deployment/kuberay-operator --tail=200`。
- Pod 调度。看 `kubectl describe pod POD -n NS` 和 `kubectl get events -n NS --sort-by=.lastTimestamp`，确认资源、亲和规则、污点和镜像拉取是否阻塞。
- Ray 注册。看 Head、Worker 容器日志，在 Head 中运行 `kubectl exec -n NS HEAD_POD -c ray-head -- ray status`。
- Task Pending。看 `ray status` 的 Demands、单 Pod GPU 容量、Placement Group 和 `maxReplicas`。若使用 Kueue，还要检查其准入状态。
- RayJob 失败。对照 submitter Job 日志、RayJob `status` 和 Ray Jobs API 日志，先判断失败发生在提交阶段还是程序运行阶段。

`NAME`、`POD`、`HEAD_POD`、`NS` 需要替换为实际对象和命名空间。先判断问题属于哪一层，再看对应对象。

### 访问控制与安全下线

不要把 Ray Dashboard 直接暴露到公网，Jobs API 也需要访问控制。KubeRay v1.6+ 配合 Ray 2.52+，可通过 `authOptions` 启用 token authentication。token 不加密流量，仍应配合 TLS、受限 Ingress、NetworkPolicy 或可信网络。

卸载 Operator 前，先检查各命名空间中是否还有 RayCluster、RayJob、RayService 或 RayCronJob。不要直接删除 `ray.io` CRD 或整个实验命名空间来清理单次作业，这可能连带影响其他资源。

## 参考资料

- [KubeRay 概览](https://docs.ray.io/en/latest/cluster/kubernetes/index.html)
- [KubeRay v1.6.2 Release 与版本说明](https://github.com/ray-project/kuberay/releases/tag/v1.6.2)
- [KubeRay v1.6.0 Release 和 RayJob 行为变更](https://github.com/ray-project/kuberay/releases/tag/v1.6.0)
- [RayJob 配置与执行](https://docs.ray.io/en/latest/cluster/kubernetes/getting-started/rayjob-quick-start.html)
- [RayService 升级与例外字段（Ray 2.57.0）](https://github.com/ray-project/ray/blob/ray-2.57.0/doc/source/cluster/kubernetes/user-guides/rayservice.md)
- [Kubernetes Pod 与容器的生命周期](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [KubeRay GPU 配置](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/gpu.html)
- [KubeRay 安装与升级](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/upgrade-guide.html)
- [KubeRay token authentication](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/kuberay-auth.html)
- [GCS fault tolerance](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/kuberay-gcs-ft.html)
