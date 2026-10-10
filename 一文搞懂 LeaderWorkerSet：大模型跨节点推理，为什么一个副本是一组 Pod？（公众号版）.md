# 一文搞懂 LeaderWorkerSet：大模型跨节点推理，为什么一个副本是一组 Pod？

假设一个模型需要两台 GPU 服务器才能放下。它对外提供一份推理服务时，两台机器上的进程必须一起工作：一台上的进程接收请求，另一台上的进程参与计算。

现在要提供两份服务副本，就需要四个 Pod。但这四个 Pod 不是随便凑在一起的：它们应当分成两组，每组两个。组内一个 Pod 出问题，整组可能都无法完成推理；扩容时，也应该一次增加完整的一组。

这正是 **LeaderWorkerSet（简称 LWS）** 要表达的事情：**把一组协同工作的 Pod 当作一个副本来管理。**它是 Kubernetes 的自定义资源，主要面向多机推理等分布式工作负载。[LWS 官方概念文档](https://lws.sigs.k8s.io/docs/concepts/leaderworkerset/)

## 01 一个副本，为什么不再是一个 Pod

我们平时使用 Deployment，常说“部署 3 个副本”，通常意味着创建 3 个彼此独立的 Pod。每个 Pod 自己就能提供一份服务。

多机模型服务的情况不同。一份模型副本可能需要跨两台甚至更多服务器运行：每台服务器上的进程只持有模型的一部分，它们通过网络协同完成一次请求。这时，单个 Pod 虽然处于 `Running`，却不代表整份模型已经可以服务。

用 LWS 的术语看：

| 字段 | 表示什么 | 示例 |
| --- | --- | --- |
| `spec.replicas` | 有多少组独立的服务副本 | `2` 表示两组 |
| `leaderWorkerTemplate.size` | **每组**一共有多少个 Pod，包含 leader | `3` 表示每组 1 个 leader、2 个 worker |

因此，`replicas: 2`、`size: 3` 会产生 **2 组 × 3 个 Pod = 6 个 Pod**。扩容到 `replicas: 3`，增加的是一整组，而不是单独增加一个 worker。[LWS API 参考](https://lws.sigs.k8s.io/docs/reference/leaderworkerset.v1/)

这里的 **leader 是组内角色**，它的索引是 0。它可以承担请求入口或协调工作，也可以和 worker 运行相同的程序。LWS 不会替应用自动选出一个业务主节点，更不会自动把模型切成几份；进程怎样协作仍由 vLLM、SGLang 等推理程序决定。[双 Pod 模板说明](https://lws.sigs.k8s.io/docs/concepts/leaderworkerset/pod-templates/) · [官方多机推理示例](https://lws.sigs.k8s.io/docs/examples/leaderworkerset/basic/)

## 02 提交一份 LWS 后，集群里会出现什么

以名为 `demo`、`replicas: 2`、`size: 3` 的 LWS 为例，默认的 `Ordinal` 组身份模式下，Pod 名称大致如下：

```text
LeaderWorkerSet demo
├── 第 0 组
│   ├── demo-0      leader
│   ├── demo-0-1    worker
│   └── demo-0-2    worker
└── 第 1 组
    ├── demo-1      leader
    ├── demo-1-1    worker
    └── demo-1-2    worker
```

背后有两层控制：LWS 控制器创建一个管理所有 leader 的 StatefulSet；每个 leader 对应一个管理本组 workers 的 StatefulSet。默认的稳定编号，让程序和运维人员都能知道一个 Pod 属于哪组、在组内是什么位置。LWS 也会创建用于组内寻址的 headless Service。[控制器架构](https://lws.sigs.k8s.io/docs/concepts/leaderworkerset/)

这说明 LWS 并没有绕开 Kubernetes 原有的 StatefulSet。StatefulSet 负责更底层的 Pod 创建和稳定身份；LWS 在其上补上了“整组”这个管理单位，包括组级扩缩容、就绪判断、故障恢复和滚动更新。

## 03 用一份最小清单认识关键字段

下面的 CPU 清单只用 Nginx 观察 LWS 的资源结构，**不是多机推理服务**。leader 和 worker 使用同一个 Pod 模板，因此省略了可选的 `leaderTemplate`。示例结构参考[官方样例](https://github.com/kubernetes-sigs/lws/blob/main/docs/examples/sample/lws.yaml)。

```yaml
apiVersion: leaderworkerset.x-k8s.io/v1
kind: LeaderWorkerSet
metadata:
  name: demo
  namespace: lws-lab
spec:
  replicas: 2
  leaderWorkerTemplate:
    size: 3
    workerTemplate:
      spec:
        containers:
          - name: nginx
            image: nginxinc/nginx-unprivileged:1.27
            ports:
              - containerPort: 8080
```

读这份清单时，先抓住两件事：**`replicas` 数组，`size` 数组内的 Pod**。`workerTemplate` 是必填的 Pod 模板；没有写 `leaderTemplate` 时，leader 也使用它。若实际服务需要 leader 运行 HTTP 接口、worker 只运行计算进程，可以分别设置 `leaderTemplate` 和 `workerTemplate`，给它们不同的镜像、命令与资源请求。[双 Pod 模板说明](https://lws.sigs.k8s.io/docs/concepts/leaderworkerset/pod-templates/)

想自己观察，可以先在测试集群确认 LWS 已安装，再提交清单。官方当前安装文档以 v0.11.1 为例，要求 Kubernetes 版本不低于 1.34；安装控制器需要相应的集群权限。[安装文档](https://lws.sigs.k8s.io/docs/installation/)

```bash
kubectl config current-context
kubectl get crd leaderworkersets.leaderworkerset.x-k8s.io
kubectl create namespace lws-lab --dry-run=client -o yaml | kubectl apply -f -
kubectl apply --dry-run=server -f lws-demo.yaml
kubectl apply -f lws-demo.yaml

kubectl get leaderworkersets,statefulsets,pods -n lws-lab
kubectl get pods -n lws-lab \
  -l leaderworkerset.sigs.k8s.io/name=demo --show-labels
```

把上面的 YAML 保存为 `lws-demo.yaml` 后再执行命令。服务端 dry-run 只能检查资源是否被集群接受，不能证明 Nginx 或真实推理程序已经跑通。观察时应该看到两组、每组三个 Pod；`status.readyReplicas` 统计的是**就绪组数**，不是就绪 Pod 数。[状态字段参考](https://lws.sigs.k8s.io/docs/reference/leaderworkerset.v1/)

## 04 同组 Pod 怎样找到彼此

分布式程序启动时，至少要知道：本组 leader 在哪里、组里有多少个成员、自己是第几个成员。LWS 为 Pod 注入了相应信息，例如：

| 环境变量 | 用途 |
| --- | --- |
| `LWS_LEADER_ADDRESS` | 本组 leader 的地址 |
| `LWS_GROUP_SIZE` | 本组 Pod 总数 |
| `LWS_WORKER_INDEX` | 本 Pod 在组内的索引；leader 为 0 |

这些变量配合 headless Service，提供了组内发现和稳定寻址的基础。官方 vLLM 示例就把组大小、节点编号和 leader 地址接到多机启动参数上。**LWS 提供身份与生命周期，真正的模型加载、张量并行和进程间通信由推理程序完成。**[标签与环境变量](https://lws.sigs.k8s.io/docs/reference/labels-annotations-and-environment-variables/) · [vLLM/SGLang 示例](https://lws.sigs.k8s.io/docs/examples/leaderworkerset/basic/)

headless Service 主要服务于 Pod 之间的寻址。若要把推理 API 稳定地提供给客户端，仍需按实际应用配置面向 leader 的 Service 和请求路由；官方多机推理示例也单独提供了访问入口。[官方基础示例](https://lws.sigs.k8s.io/docs/examples/leaderworkerset/basic/)

## 05 启动、故障、升级：LWS 管的是整组

### 启动时，worker 要等 leader 吗

默认 `startupPolicy: LeaderCreated`：只要 leader Pod 对象已经创建，LWS 就会创建本组的 worker StatefulSet。leader 和 workers 可以并行启动，这有利于缩短等待时间，但不保证 workers 启动时 leader 已经 `Ready`。

如果应用要求 leader 先完成初始化，可以设置 `startupPolicy: LeaderReady`。此时要为 leader 设计合适的 Ready 检查：如果 leader 必须等 workers 连上来才会 Ready，而 workers 又必须等 leader Ready 才创建，就会互相等待。[启动策略](https://lws.sigs.k8s.io/docs/concepts/leaderworkerset/startup-policy/)

### 一个 worker 坏了，为什么可能重建整组

默认的 `leaderWorkerTemplate.restartPolicy` 是 `RecreateGroupOnPodRestart`。当组中某个 Pod 故障或重启，LWS 会删除并重建这整组 Pod。原因很现实：在紧耦合的模型并行服务里，一个进程退出后，其他进程虽然仍在运行，集体通信状态可能已经失效。

如果应用能自行处理单个成员重连，可以选 `None`；若启动阶段很长，希望避免待启动 Pod 引发反复整组重建，可评估 `RecreateGroupAfterStart`。这几种策略改变的是**故障后如何恢复**，不能代替应用自己的健康检查。[故障处理文档](https://lws.sigs.k8s.io/docs/concepts/leaderworkerset/failure-handling/)

### 升级时，`maxSurge: 1` 到底多占多少资源

LWS 的滚动更新按**组**计算。`maxUnavailable: 1` 表示升级期间最多允许一组不可用；`maxSurge: 1` 表示最多临时多创建一整组。假设每组三台八卡服务器，`maxSurge: 1` 需要考虑的是额外 **24 张 GPU** 的容量，而不是一张卡或一个 Pod。[滚动更新文档](https://lws.sigs.k8s.io/docs/concepts/leaderworkerset/rollout-strategy/)

还有一个容易踩的点：把 `size` 从 2 改成 3，属于**模板变更**。LWS 会按滚动更新策略替换各组 Pod，包括 leader；它不会直接把一个 worker 热加入现有模型进程。若只是要增加完整服务容量，通常先增加 `replicas`。[组大小调整](https://lws.sigs.k8s.io/docs/concepts/leaderworkerset/resizing/)

## 06 “作为一组管理”不等于“同时调度成功”

LWS 知道哪些 Pod 属于同一组，也能在故障和更新时按组处理。但默认情况下，Pod 仍按普通 Kubernetes 方式逐个调度。假如一组三个 GPU Pod，集群暂时只放得下两个，就可能出现两个 Pod 占着 GPU、第三个一直 `Pending` 的情况。

需要“资源够整组才一起调度”时，还要配置 gang scheduling。LWS 的原生 gang scheduling 是**可选**能力，官方文档将其标为 alpha，并列出 Kubernetes、控制器 feature gate 等前提；它不是创建 LWS 后自动具备的保证。[Gang scheduling 文档](https://lws.sigs.k8s.io/docs/concepts/leaderworkerset/gang-scheduling/) · [安装前提](https://lws.sigs.k8s.io/docs/installation/)

同样，LWS 能配置组内 Pod 的拓扑放置，但它不会凭空提供低延迟网络。多机模型并行仍要检查 GPU 节点、网络设备与链路的实际带宽，以及调度约束能否把同组 Pod 放到合适的位置。[拓扑放置文档](https://lws.sigs.k8s.io/docs/concepts/leaderworkerset/topology-placement/)

## 07 什么时候该用 LWS

判断方法很简单：**一份可服务的模型副本，是否必须由多个 Pod 一起组成？**

如果单个 Pod 就能加载完整模型并独立响应请求，普通 Deployment 往往已经足够。如果一份模型副本必须跨多机运行，扩缩容、就绪检查、故障恢复和升级都应该以整组为单位，LWS 才体现出价值。

读 LWS 配置时记住三句话：

> `replicas` 决定有多少组；`size` 决定每组有多少 Pod；LWS 负责把组管好，推理程序负责让组内进程真正协作。

**参考资料：**[LWS 官方概念](https://lws.sigs.k8s.io/docs/concepts/leaderworkerset/) · [API 参考](https://lws.sigs.k8s.io/docs/reference/leaderworkerset.v1/) · [基础示例](https://lws.sigs.k8s.io/docs/examples/leaderworkerset/basic/) · [安装说明](https://lws.sigs.k8s.io/docs/installation/)
