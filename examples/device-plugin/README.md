# 最小 Kubernetes Device Plugin

这个教学示例报告两块**虚拟设备**：`demo-0`、`demo-1`，资源名为 `example.com/learning-device`。它不访问真实硬件。`Allocate` 只把选中的设备 ID 写入容器环境变量 `DEMO_DEVICE_IDS`，便于观察调用结果。

## 先看关键流程

1. 插件在 `/var/lib/kubelet/device-plugins/learning-device.sock` 启动自己的 gRPC 服务。
2. 插件连接 kubelet 的 `/var/lib/kubelet/device-plugins/kubelet.sock`，调用 `Register`。
3. kubelet 反过来连接插件的 socket，调用 `GetDevicePluginOptions`、`ListAndWatch`。
4. Pod 请求 `example.com/learning-device: 1` 后，kubelet 调用 `Allocate`；插件返回容器环境变量。

可对照 [官方 Device Plugin 文档](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/) 阅读 `main.go`。

## 在 kind 集群运行

需要 Docker、kind、kubectl，以及一个已经启动的 kind 集群。以下命令在本目录执行：

```bash
docker build -t learning-device-plugin:local .
kind load docker-image learning-device-plugin:local
kubectl apply -f daemonset.yaml
kubectl -n kube-system rollout status daemonset/learning-device-plugin
kubectl describe nodes
```

在 `kubectl describe nodes` 的 Capacity 和 Allocatable 中找到 `example.com/learning-device: 2`。随后运行：

```bash
kubectl apply -f demo-pod.yaml
kubectl wait --for=jsonpath='{.status.phase}'=Succeeded pod/learning-device-consumer --timeout=120s
kubectl logs learning-device-consumer
```

日志应为 `allocated=demo-0` 或 `allocated=demo-1`；具体 ID 由 kubelet 选择。看插件日志：

```bash
kubectl -n kube-system logs daemonset/learning-device-plugin
```

清理：`kubectl delete -f demo-pod.yaml -f daemonset.yaml`。

## 从示例走向真实设备

把 `deviceIDs` 替换为真实设备发现；在 `ListAndWatch` 中监测热插拔与健康状态；在 `Allocate` 中返回实际的设备节点、挂载或 CDI 设备。这个示例没有实现硬件访问、健康变化、NUMA 拓扑及生产级故障处理。
