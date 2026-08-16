# KubeRay v1.6.2 实验集群交接

本文档记录 2026-08-16 在两节点 CompShare Kubernetes 集群上的实际部署结果。

## 当前部署

| 项目 | 状态 |
| --- | --- |
| Kubernetes | v1.36.2，两个节点均 Ready |
| Helm release | `kuberay-operator` / `kuberay-system`，revision 1，deployed |
| Operator | `quay.io/kuberay/operator:v1.6.2`，1/1 Ready |
| CRD | `RayCluster`、`RayJob`、`RayService`、`RayCronJob` 均已注册 |
| 调度器 | 使用默认 kube-scheduler；未启用 KubeRay 的 Volcano 集成 |
| RayCronJob | CRD 已安装，feature gate 仍为 false |
| CPU 烟测 | `SUCCEEDED / Complete` |

现有 Volcano v1.15.1 保持原状。KubeRay 本次没有设置 `batchScheduler.name=volcano`，避免把 Operator 验收与 Gang 调度兼容性混在一起。

## 访问控制面

CompShare 控制面实例 ID：

```text
uhost-1t4u7p147hun
```

从本机进入控制面：

```bash
/Users/lijiawang/Library/Python/3.11/bin/compshare \
  instance ssh uhost-1t4u7p147hun
```

进入实例后检查 KubeRay：

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf \
  get deployment,pod,service -n kuberay-system -o wide

sudo helm status kuberay-operator -n kuberay-system

sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf \
  get rayjob,raycluster,pod,job,service -n kuberay-lab -o wide
```

不要覆盖本机当前的 `nci-dev` kubeconfig。若要让本机 `kubectl` 管理 CompShare 集群，应另建独立 kubeconfig 并通过 SSH 隧道访问内网 API Server。

## 已完成的 CPU RayJob 烟测

可重复清单：[`rayjob-cpu-smoke.yaml`](./rayjob-cpu-smoke.yaml)

控制面也保留了一份：

```text
/home/ubuntu/rayjob-cpu-smoke.yaml
```

实际验收结果：

```text
RayJob: ray-cpu-smoke
Job ID: ray-cpu-smoke-ktv7w
Job status: SUCCEEDED
Deployment status: Complete
Application marker: KUBERAY_CPU_SMOKE_OK
Ray nodes: 1 headgroup + 1 cpu-worker
Ray image digest: sha256:e094f5745034514531df4caeaa5c7bf119eb2508609faba5ad603a6ea9c02e8b
```

两台节点直连 Docker Hub 会超时，因此烟测清单使用现有 DaoCloud 代理：

```text
m.daocloud.io/docker.io/rayproject/ray:2.57.0
```

重新运行前需要删除旧 RayJob；直接再次 `apply` 不会创建新的一次执行：

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf \
  delete rayjob ray-cpu-smoke -n kuberay-lab \
  --ignore-not-found --wait=true --timeout=3m

sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf \
  apply --dry-run=server -f /home/ubuntu/rayjob-cpu-smoke.yaml

sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf \
  apply -f /home/ubuntu/rayjob-cpu-smoke.yaml

sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf \
  wait -n kuberay-lab \
  --for=jsonpath='{.status.jobDeploymentStatus}'=Complete \
  rayjob/ray-cpu-smoke --timeout=20m
```

查看状态和日志：

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf \
  get rayjob ray-cpu-smoke -n kuberay-lab -o yaml

sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf \
  logs -n kuberay-lab job/ray-cpu-smoke --all-containers=true
```

清单设置了 `ttlSecondsAfterFinished: 600`。实测确认终态十分钟后专属 RayCluster、Head Pod 和 Worker Pod 已自动删除；RayJob CR、submitter Job/Pod、RayJob 持有的 Head Service 和 ConfigMap 仍然保留。

## GPU 烟测为什么没有执行

两个节点各有一张 RTX 3080 Ti，容量与可分配量均为 1。实时盘点发现 `volcano-model-demo` 中已有两个 Running Pod，各占一张 GPU；另有多个等待 GPU 的 Pending Pod。

本次部署没有缩容或删除这些既有工作负载。因此 KubeRay Operator 和 CPU RayJob 已完成验证，但双 GPU RayJob 尚未执行。运行双 GPU 实验前，应先由资源所有者决定如何处理现有 Volcano 模型工作负载。

## 安全边界

- 不要删除 `ray.io` CRD；删除 CRD 会级联影响全集群相应自定义资源。
- 卸载 Operator 前，先检查所有 namespace 中是否还有 RayCluster、RayJob、RayService 或 RayCronJob。
- 不要直接删除 `kuberay-lab` namespace，除非确认其中没有其他用户资源。
- 现有 Volcano 与 GPU Operator 是独立组件，本次部署没有修改它们的 Helm values。
