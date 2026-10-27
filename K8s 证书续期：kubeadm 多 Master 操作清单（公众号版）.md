# K8s 证书续完还是连不上？kubeadm 多 Master 续期操作清单

![三台控制面节点与待更新的数字证书](images/k8s-cert-renewal/01-cover.png)

值班时看到 `kubectl` 报 `x509: certificate has expired or is not yet valid`，第一反应通常是：赶紧把证书续了。

但证书文件更新，只完成了一半工作。控制面组件可能还在使用启动时加载的旧证书；管理员电脑上的 kubeconfig 也可能仍是旧副本。结果就是 `kubeadm certs renew all` 显示成功，集群却没有真正恢复。

下面按一套**三台 Master、kubeadm 部署、使用本地 etcd**的集群，梳理完整操作。外部 CA、外部 etcd 或定制安装的集群，先确认自身配置，再调整相应步骤。

## 续期前先看清楚：哪些证书要管

| 对象 | 通常由谁管理 | 续期时要注意什么 |
| --- | --- | --- |
| API Server、etcd 等控制面证书 | kubeadm | 每台 Master 分别检查和续期 |
| `admin.conf`、组件 kubeconfig 中的证书 | kubeadm | 文件更新后，留意其他位置是否还有旧副本 |
| CA 证书 | 按集群的 CA 方案管理 | 到期处理不同于普通证书续期 |
| kubelet 客户端证书 | 通常由 kubelet 自动轮换 | 轮换异常时单独排查 |
| kube-proxy 凭据 | 取决于实际部署 | 先确认是 ServiceAccount 还是独立客户端证书 |

kubeadm 默认签发的客户端证书有效期通常为一年，CA 默认更长，但实际有效期以集群配置和检查结果为准。尤其不要看到 `kube-proxy` 就断定它也需要手工续证书：标准部署与遗留、定制部署可能不同。

## 第一步：续期前检查

先确认集群当前状态，留下一份操作前的记录：

```bash
kubectl get nodes -o wide
kubectl -n kube-system get pods -o wide
kubectl get --raw='/readyz'
```

随后登录**每一台 Master**执行：

```bash
sudo kubeadm certs check-expiration
```

检查输出中的到期时间、CA 剩余时间和 `EXTERNALLY MANAGED` 标记。如果证书由外部 CA 管理，就应按外部签发流程处理，不要直接执行后文的 `renew all`。

再看 kube-proxy 的实际认证配置：

```bash
kubectl -n kube-system get cm kube-proxy \
  -o jsonpath='{.data.kubeconfig\.conf}' \
  | grep -E 'tokenFile:|client-certificate(-data)?:'
```

这条命令用于寻找线索；**没有输出不代表无需处理**，还应检查 kube-proxy DaemonSet 挂载的配置文件。如果使用独立的客户端证书，把它列入单独的更新计划。

开始前还要确认两件事：API Server 前的负载均衡器能避开故障节点；本地 etcd 的健康成员足以在一台 Master 短暂退出时维持仲裁。有节点已经异常，就先排查现状，不要按计划继续减少可用节点。

## 第二步：备份

每台 Master 都要备份自己的证书、kubeconfig 和静态 Pod 配置。不要只备份第一台：

```bash
BACKUP_DIR="/root/k8s-cert-backup-$(date +%F-%H%M%S)"

sudo install -d -m 0700 "$BACKUP_DIR"
sudo cp -a /etc/kubernetes/pki "$BACKUP_DIR/"
sudo cp -a /etc/kubernetes/*.conf "$BACKUP_DIR/"
sudo cp -a /etc/kubernetes/manifests "$BACKUP_DIR/"
```

如果 API Server 仍可访问，也可保存 kubeadm 配置，便于之后核对：

```bash
kubectl -n kube-system get cm kubeadm-config -o yaml \
  | sudo tee "$BACKUP_DIR/kubeadm-config.yaml" >/dev/null
```

本地 etcd 还应按当前环境的工具和 TLS 配置制作快照，并验证快照可读取。以下命令仅适用于本机有兼容的 `etcdctl`，且证书路径与示例一致的环境：

```bash
sudo env ETCDCTL_API=3 etcdctl snapshot save "$BACKUP_DIR/etcd.db" \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt \
  --key=/etc/kubernetes/pki/etcd/healthcheck-client.key

sudo etcdutl snapshot status "$BACKUP_DIR/etcd.db" -w table
```

如果 `etcdctl`、`etcdutl` 不在宿主机，应按现有运维方式从相应环境执行。外部 etcd 则使用外部集群自己的备份流程。

备份目录包含私钥和高权限 kubeconfig，必须限制访问。另一个容易忽略的事实是：**已经过期的旧证书即使备份完整，也不能靠复制回去解决过期问题。**

## 第三步：HA 多 Master 滚动续期

操作顺序只有一条原则：**一次处理一台 Master；这台恢复并验收通过，再碰下一台。**

先在 Master 1 执行：

```bash
sudo kubeadm certs renew all
sudo kubeadm certs check-expiration
```

第二条命令确认本机磁盘上的证书已有新到期时间。接下来还要让相关控制面组件加载这些证书。

kubeadm 部署的控制面组件通常是静态 Pod。稳妥的做法是将**一个组件**的 manifest 暂时移出 `/etc/kubernetes/manifests/`，等 kubelet 停止旧 Pod，再移回文件，让 kubelet 创建新 Pod。例如：

```bash
sudo install -d -m 0700 /root/k8s-staticpod-hold

sudo mv \
  /etc/kubernetes/manifests/kube-apiserver.yaml \
  /root/k8s-staticpod-hold/

# 确认旧 Pod 已停止，再执行下一条

sudo mv \
  /root/k8s-staticpod-hold/kube-apiserver.yaml \
  /etc/kubernetes/manifests/
```

等待时以**旧 Pod 退出、新 Pod 启动并健康**为准，不要只等固定的十秒钟。使用本地 etcd 的集群，也要让续期后需要重新加载证书的 etcd 静态 Pod 完成重建；controller-manager、scheduler 同样逐个处理。每处理完一个组件都先验证，再处理下一个。

不要把 `systemctl restart kubelet` 当作“所有控制面 Pod 已加载新证书”的验收结果。组件是否重新创建、是否健康，需要实际检查。

Master 1 恢复后，从负载均衡器入口和节点本机分别确认 API Server、etcd 状态正常。然后用同样方式处理 Master 2、Master 3。

## 第四步：收尾操作

如果平时使用的 `~/.kube/config` 是从 `/etc/kubernetes/admin.conf` 复制出来的，续期后要更新这份副本：

```bash
sudo cp -i /etc/kubernetes/admin.conf "$HOME/.kube/config"
sudo chown "$(id -u):$(id -g)" "$HOME/.kube/config"
```

其他使用独立 kubeconfig 的运维平台、脚本和自动化任务，也应检查它们持有的凭据。`admin.conf` 权限很高，不要为了省事把它分发给所有用户或工具。

最后做一次完整验收：

```bash
kubectl get --raw='/readyz'
kubectl get nodes
kubectl -n kube-system get pods -o wide
```

并在每台 Master 再次运行：

```bash
sudo kubeadm certs check-expiration
```

验收时既要看证书到期时间，也要看控制面 Pod 是否持续运行、API Server 是否能通过正常入口访问，以及日常管理命令是否恢复。

## 回滚方案：先定位故障，再决定恢复什么

如果某台 Master 在续期后没有恢复，**立刻暂停后续节点操作**。先判断问题发生在哪一层：

- 新证书没有生成成功：查看 kubeadm 输出和本机证书状态。
- 证书已更新，但组件没有重建：检查静态 Pod manifest、kubelet 和容器运行状态。
- 组件已启动，API 仍不可用：检查 etcd 健康、API Server 日志和负载均衡器健康检查。
- 只有管理员的 `kubectl` 失败：检查正在使用的 kubeconfig 是否仍含旧证书。

如果故障来自误改的 manifest，可用对应节点的备份恢复配置，再重新检查组件状态。如果考虑恢复旧证书，必须先确认它**尚在有效期内**，并保证证书、私钥及相关 kubeconfig 成套匹配。不要把整个备份目录盲目覆盖到所有 Master，更不要用已过期证书“回滚”。

## 生产执行清单

**操作前**

- [ ] 确认集群确由 kubeadm 管理，识别外部 CA、外部 etcd 等例外情况
- [ ] 记录节点、控制面 Pod、API Server 和 etcd 的当前状态
- [ ] 在每台 Master 检查证书及 CA 到期时间
- [ ] 确认负载均衡器和 etcd 仲裁状态
- [ ] 备份每台 Master 的 PKI、kubeconfig、静态 Pod manifest
- [ ] 制作并验证 etcd 快照
- [ ] 检查 kube-proxy 的实际认证方式

**逐台续期**

- [ ] Master 1：续期、逐个重建相关静态 Pod、验证
- [ ] Master 2：确认 Master 1 健康后，再执行同样步骤
- [ ] Master 3：确认前两台健康后，再执行同样步骤

**完成验收**

- [ ] 每台 Master 的证书到期时间符合预期
- [ ] etcd、API Server、controller-manager、scheduler 健康
- [ ] 通过正常集群入口执行 `kubectl` 成功
- [ ] 更新需要更新的管理员 kubeconfig 副本
- [ ] 检查独立工具凭据及特殊配置的 kube-proxy

证书续期最容易被忽略的，不是命令参数，而是命令之后的验证。**新证书写入磁盘、组件重新加载、集群入口正常使用**，这三步都完成，才能给这次变更打勾。
