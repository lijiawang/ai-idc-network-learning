# AI 集群 IDC 网络架构学习

这个仓库整理 AI 训练集群、GPU 通信和 IDC 网络架构相关的学习笔记、公众号文章草稿、拓扑图和配套生成脚本。

## 内容概览

- GPU 基础与大模型并行：DP、TP、PP、EP 等概念理解。
- NCCL collective 通信：Ring AllReduce、Tree AllReduce、ReduceScatter、AllGather 和路由选择。
- GPUDirect：单机多 GPU P2P、跨节点 GPUDirect RDMA。
- AI 集群网络：Rail-Optimized Spine-Leaf、训练网络、管理网络和存储网络分层。
- 可视化素材：文章配图、封面图、SVG 源文件和部分 Python 生成脚本。

## 目录说明

- `assets/`：按主题组织的文章配图、SVG 和生成脚本。
- `diagrams/`：网络与通信相关的图表素材。
- `precision-diagrams/`：精度格式相关文章的图表素材。
- `output/blog/`：生成或整理后的博客文章与图片素材。
- `*.md`：主题文章和学习笔记。

## 使用方式

直接阅读 Markdown 文件即可。部分图表由 Python 脚本生成，脚本位于对应主题目录中，可根据需要重新运行或调整。
