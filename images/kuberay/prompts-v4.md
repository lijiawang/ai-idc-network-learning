# KubeRay v4 配图生成记录

生成日期：2026-09-06。工具：内置 GPT 图片生成工具，基于 v3 图片重绘。

- [Pod 状态与业务验收](./07-kuberay-hero-v4.png)：移除 Operator 指向验收结果的箭头，改用中文区分 Pod 状态与业务验收。
- [RayJob 执行、重试与回收](./09-rayjob-lifecycle-v4.png)：分区表达正常执行、失败重试、全流程超时与有条件回收。

以下为实际使用的完整提示词。图片已逐项核对文字、箭头、版本和正文引用。

## 07-kuberay-hero-v4.png

输入图片：`07-kuberay-hero-v3.png`。

```text
Use case: infographic-diagram
Asset type: Chinese technical article explanatory image, final production raster.
Input image: existing KubeRay hero is an edit target; redesign its layout and text to correct misleading semantics. Preserve clean white background, navy/blue/purple palette, simple Pod cube icons.
Primary request: make a precise, immediately understandable Chinese infographic. All explanatory text must be Chinese, API names remain English. 16:9 landscape, large text, generous space.
Title exact: "Pod Running ≠ Ray 业务可用".
Two clearly separated panels with NO arrow between them.
LEFT panel heading "① 看 Pod 状态". Stack three clean boxes "Head Pod", "Worker Pod", "Worker Pod", each with a purple "Running" badge. Beneath boxes text "只说明 Pod phase=Running" and smaller "至少一个容器正在运行、启动或重启".
RIGHT panel heading "② 验收 Ray 业务". Diagram: one "Head / GCS" box above two "Worker" boxes. Each Worker has one blue arrow aimed at Head / GCS labelled "注册". Beneath diagram three green checklist items exactly "GCS 可访问", "Worker 已注册", "逻辑资源正确". Beneath checklist a pale green box "ray status + 小任务验证". These are checks the reader must perform, not guarantees from Operator.
Bottom full-width small independent note: "KubeRay 管理资源生命周期；业务可用性需要单独验收。"
Constraints: REMOVE the old central Operator box and all create/reconcile arrows; don't show any Operator arrow ending at verification checks; no "Processes started", no VERIFIED badge, no crossing arrows, no extra copy. Chinese crisp sans serif; clear hierarchy. Every required label visible and spelled exactly. Flat vector-like publication diagram rendered as raster, not a photograph.
```

## 09-rayjob-lifecycle-v4.png

输入图片：`09-rayjob-lifecycle-v3.png`。

```text
Use case: infographic-diagram
Asset type: Chinese technical article lifecycle diagram, final production raster.
Input image: existing RayJob lifecycle is the edit target. Redesign its wiring completely to remove crossings; retain blue/purple/green/red palette on white.
Primary request: make a compact accurate Chinese infographic readable without prose. Wide 16:10 landscape. Large labels. Three separated horizontal sections, each with independent arrows, no arrows crossing section boundaries, no long looping arrows.
Title "RayJob：执行、重试与回收".
Subtitle "K8sJobMode + rayClusterSpec | KubeRay v1.6.2".
SECTION 1 heading "① 正常执行". Single left-to-right blue sequence, 5 boxes:
"RayJob CR" (subline "集群配置 + 入口命令") ->
"创建 RayCluster" (subline "Head + Workers") ->
"等待集群 Ready" (subline "期望 Ray Pod 已 Running / Ready") ->
"Submitter Job" (subline "ray job submit") ->
"Driver" (subline "提交 Task / Actor").
Do not add success/failure branches under Driver in section 1. The other sections explain outcomes independently.
SECTION 2 heading "② 失败与重试". At the left a red rectangular box with two lines "提交器失败" / "Ray 作业失败等", arrow right to a diamond "允许重试且次数未耗尽？". Upper right branch labelled "是" leads to purple box "新建集群，重跑本次作业", smaller subline "重新从「创建 RayCluster」开始". Lower right branch labelled "否" leads to red box "最终失败". Don't draw a return arrow across normal flow.
Below this branching graph place a separate slim red horizontal strip with only a straight one-way arrow: "全生命周期超时" (subline "activeDeadlineSeconds") -> "DeadlineExceeded" -> "最终失败（不重试）".
Small purple note inside section 2: "顶层 backoffLimit 控制整次重试，默认 0".
SECTION 3 heading "③ 终态后回收". Compact left-to-right sequence: "成功 / 最终失败" -> "等待 TTL" -> "删除专属 RayCluster". Put the condition in a prominent note immediately above these arrows: "本文清单：shutdownAfterJobFinishes=true". Under this sequence two short footnotes: "该开关默认 false；开启后按 TTL 回收。" and "RayJob CR / Submitter Job 的保留取决于删除策略和 Operator 配置。"
Important facts: submitter failure can enter top-level retry before Driver exists; activeDeadlineSeconds covers the full RayJob lifetime, not just Driver runtime. Cleanup requires true, not automatic by default.
Constraints: reproduce Chinese text legibly and exactly, prefer short deliberate line breaks, no extra text, no fictional stages, no crossing wires, no unlabeled branches, no wrong arrow direction. No extra arrow out of retry diamond beyond exactly labelled 是/否. Clean flat publication diagram, not 3D.
```

