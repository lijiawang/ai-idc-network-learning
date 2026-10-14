# Pod 卡在 ContainerCreating，先确认节点，再读完整 Event

Pod 创建了十几分钟，状态始终是 `ContainerCreating`。有人怀疑镜像仓库，有人要查 CNI，还有人准备重启 kubelet。

先别猜。`ContainerCreating` 是 `kubectl` 展示的容器等待原因，不是 Pod 的生命周期阶段；Pod 的 `phase` 此时通常仍是 `Pending`。它只说明容器还没有完成创建，无法单凭这几个字判断故障在哪。[Kubernetes Pod 生命周期文档](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)

排查先回答两个问题：**Pod 绑定到了哪台节点？Events 的完整错误信息是什么？**

## 一、如何确认 Pod 所在节点

以下以 `production` 命名空间中的 `payment-api-7c9d` 为例。执行时把示例名称换成实际值：

```bash
kubectl -n production get pod payment-api-7c9d -o wide
```

重点看输出中的 `NODE` 列：

```text
NAME               READY   STATUS              NODE
payment-api-7c9d   0/1     ContainerCreating   worker-03
```

这里的 `worker-03` 就是后续查节点日志、网络插件和存储插件时要锁定的节点。也可以直接读取 Pod 的节点字段：

```bash
kubectl -n production get pod payment-api-7c9d \
  -o jsonpath='{.spec.nodeName}{"\n"}'
```

如果输出为空，Pod 尚未绑定节点。此时先看是否有 `FailedScheduling`，核对资源请求、污点、节点选择规则及相关 PVC。若已有节点名，再检查该节点：

```bash
kubectl get node worker-03
kubectl describe node worker-03
```

节点显示 `Ready` 只能说明节点通过了相应的健康检查，不能证明卷、CNI 和容器运行时都正常。

## 二、如何查看 Events 的完整报错

先查看 Pod 描述，滚动到末尾的 `Events`：

```bash
kubectl -n production describe pod payment-api-7c9d
```

不要只看 `Reason` 一列。`Reason` 是错误类别；`Message` 往往包含真正需要追查的组件、调用和底层错误。例如：

```text
Warning  FailedCreatePodSandBox  kubelet
Failed to create pod sandbox:
failed to setup network for sandbox:
plugin type="calico" failed ...
```

只读到 `FailedCreatePodSandBox`，还无法区分运行时和网络问题。继续读到 `failed to setup network`、`calico`，才能把排查方向缩到该节点上的 CNI 插件。

如果表格太窄，想看事件对象里的完整字段，可以使用：

```bash
kubectl -n production events --for pod/payment-api-7c9d -o yaml
```

重点找每条事件的 `reason`，以及 `message` 或 `note` 字段；同时看发生时间和重复次数。想持续观察新事件：

```bash
kubectl -n production events --for pod/payment-api-7c9d --watch
```

如果当前 `kubectl` 不支持 `events --for`，可用：

```bash
kubectl -n production get events \
  --field-selector involvedObject.kind=Pod,involvedObject.name=payment-api-7c9d \
  -o yaml
```

以上事件查询方式可参考 [kubectl events 官方文档](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_events/)。

## 三、按完整错误信息继续查

| 事件或状态线索 | 下一步 |
| --- | --- |
| `NODE` 为空，出现 `FailedScheduling` | 查调度约束、资源请求、污点和 PVC |
| `FailedMount`、`FailedAttachVolume` | 查卷、PVC、目标节点上的 CSI 插件及存储后端；Secret/ConfigMap 卷还要核对对象是否存在 |
| `FailedCreatePodSandBox`，详情包含 `cni`、`network` 或插件名称 | 查 **Pod 所在节点** 的 CNI 插件及其日志 |
| `FailedCreatePodSandBox`，详情指向 sandbox 镜像、容器运行时或节点资源 | 查该节点的 kubelet、容器运行时及节点资源 |
| `Failed to pull image` | 查镜像名和标签、仓库凭据、节点到仓库的网络及证书 |
| `Init:*` | 找到具体的 init 容器，查看它的状态和日志 |

需要查节点日志时，在 Pod 所在节点上根据实际运行时查看。例如，使用 systemd 和 containerd 的 Linux 节点可以执行：

```bash
sudo journalctl -u kubelet --since '30 minutes ago'
sudo journalctl -u containerd --since '30 minutes ago'
sudo crictl pods --name payment-api-7c9d
```

运行时若不是 containerd，应改查实际使用的服务。`crictl` 可用于检查 CRI 运行时中的 Pod sandbox 和容器，参见 [Kubernetes crictl 排障文档](https://kubernetes.io/docs/tasks/debug/debug-cluster/crictl/)。

如果 `Events` 为空，也不要直接断定 kubelet 没工作。确认 namespace、Pod 名称与节点后，继续查节点状态、kubelet 和运行时日志。先保存 `describe pod`、事件和相关日志，再修改配置或重启组件，便于找到真正原因。

**记住这条顺序：确认节点 → 读完整 Event → 找对应组件 → 一次只处理一个问题。**

参考：[《Pod 卡在 ContainerCreating，该找谁》](https://mp.weixin.qq.com/s/sI_Xbh8Po5ck3ylvlW_Z0g)。
