# KubeRay 公众号配图生成记录

本组图片由 GPT 图片生成工具制作，适配公众号手机阅读。正文使用 4 张图片；控制循环图经过一次定向修正，最终状态回写箭头从 Operator 指向自定义资源。

## 1. 01-ready.png

参考图：`images/kuberay/07-kuberay-hero-v4.png`。

完整提示词：

```text
Use case: infographic-diagram. Asset type: WeChat public article mobile-ready explanatory image.
Style for every image: professional Chinese technical article infographic designed to be read on a 360-pixel-wide phone screen. Redraw the supplied image substantially. Change canvas to PORTRAIT or square as specified; do not retain the old landscape composition. White background, navy text, blue and violet outlines, restrained green for checks and red for failures. Very large clean Chinese sans-serif type, short lines, thick simple arrows, abundant margins. All explanatory wording in Chinese, technical names verbatim. Main labels at least 48 px equivalent on a 1024px-wide canvas, supporting labels at least 38 px. No tiny footnotes, no paragraph text, no overlapping/crossing wires, no cropped letters, no watermarks or decorative filler. Preserve technical meaning, not old positions.
Canvas square 1:1. Title in two short lines exactly "Pod Running" and "不等于 Ray 业务可用".
Layout: two large cards stacked vertically, no arrow connecting them.
Upper violet card title "① 检查 Pod 状态". A simple compact row of three cube icons labelled "Head", "Worker", "Worker". Beneath the row the large badge "phase=Running". Then exactly "至少一个容器在运行、启动或重启" in readable type on up to two lines. Do not claim Ray processes started.
Lower blue card title "② 验收 Ray 业务". Three green checks in large vertically stacked text "GCS 可访问", "Worker 已注册", "逻辑资源正确". Bottom green outlined action box "ray status + 小任务验证".
No Operator box, no arrows pointing from Operator to checks, no VERIFIED badge, no extra explanatory copy. The two cards are observations at different levels, not a guaranteed causal transition.
```

## 2. 02-control.png

参考图：`images/kuberay/08-kuberay-control-loop-v3.png`。

完整提示词：

```text
Use case: infographic-diagram. Asset type: WeChat public article mobile-ready Chinese control loop diagram.
Style for every image: professional Chinese technical article infographic designed to be read on a 360-pixel-wide phone screen. Redraw the supplied image substantially. Change canvas to PORTRAIT or square as specified; do not retain the old landscape composition. White background, navy text, blue and violet outlines, restrained green for checks and red for failures. Very large clean Chinese sans-serif type, short lines, thick simple arrows, abundant margins. All explanatory wording in Chinese, technical names verbatim. Main labels at least 48 px equivalent on a 1024px-wide canvas, supporting labels at least 38 px. No tiny footnotes, no paragraph text, no overlapping/crossing wires, no cropped letters, no watermarks or decorative filler. Preserve technical meaning, not old positions.
Portrait canvas 3:4. Title "KubeRay 怎样维护集群".
Central vertical chain of four spacious boxes:
1. "自定义资源" with subline "RayCluster / RayJob / RayService" and subline "spec 声明期望".
2. "KubeRay Operator" with subline "读取配置，持续调谐".
3. "Kubernetes API".
4. "Pod / Service / Job".
Draw downward arrow from box1 to2 labelled "监听配置"; from box2 to3 labelled "创建 / 更新"; from box3 to4 simple downward arrow.
One dashed blue loop travels to the LEFT of this chain from box4 UP to box2, arrowhead clearly INTO box2, label "观察实际状态" horizontal near the outer edge. One separate violet return arrow travels RIGHT of chain from box2 UP to box1, arrowhead INTO box1, label "回写 status". Leave enough side margin for these labels, do not cross any boxes or arrows.
Bottom separate pale violet strip with exactly two lines "Pod 内的 Ray runtime" and "调度 Task / Actor". This strip is a responsibility note, not another stage in the control loop. Do not draw arrows from Operator to Task. No worker registration details or other nested diagrams. Minimize text for mobile reading.
```

## 3. 03-job.png

参考图：`images/kuberay/09-rayjob-lifecycle-v4.png`。

完整提示词：

```text
Use case: infographic-diagram. Asset type: WeChat public article mobile-ready normal RayJob execution flow.
Style for every image: professional Chinese technical article infographic designed to be read on a 360-pixel-wide phone screen. Redraw the supplied image substantially. Change canvas to PORTRAIT or square as specified; do not retain the old landscape composition. White background, navy text, blue and violet outlines, restrained green for checks and red for failures. Very large clean Chinese sans-serif type, short lines, thick simple arrows, abundant margins. All explanatory wording in Chinese, technical names verbatim. Main labels at least 48 px equivalent on a 1024px-wide canvas, supporting labels at least 38 px. No tiny footnotes, no paragraph text, no overlapping/crossing wires, no cropped letters, no watermarks or decorative filler. Preserve technical meaning, not old positions.
Portrait canvas 3:4. Title "RayJob 怎样开始执行". Small but clearly readable subtitle "K8sJobMode + rayClusterSpec".
Exactly FIVE boxes stacked vertically with straight downward arrows. Each box has a large step number in a blue circle.
1 heading "声明 RayJob" subline "集群配置 + 入口命令".
2 heading "创建 RayCluster" subline "Head Pod + Worker Pod".
3 heading "等待集群 Ready" subline on two lines "期望 Ray Pod" / "已 Running / Ready".
4 heading "启动提交器" subline "Submitter Job 调用 Jobs API".
5 heading "执行 Driver" subline "提交 Task / Actor".
At bottom one modest note "失败重试与回收，另看下一张图".
Do not include a fake success guarantee; Ready is specifically expected Pod Running/Ready. No branches, no loops, no cleanup steps in this image. Never place five boxes horizontally. Text should be comfortably readable on a phone without zoom.
```

## 4. 04-retry-cleanup.png

参考图：`images/kuberay/09-rayjob-lifecycle-v4.png`。

完整提示词：

```text
Use case: infographic-diagram. Asset type: WeChat public article mobile-ready RayJob retry and cleanup explanation.
Style for every image: professional Chinese technical article infographic designed to be read on a 360-pixel-wide phone screen. Redraw the supplied image substantially. Change canvas to PORTRAIT or square as specified; do not retain the old landscape composition. White background, navy text, blue and violet outlines, restrained green for checks and red for failures. Very large clean Chinese sans-serif type, short lines, thick simple arrows, abundant margins. All explanatory wording in Chinese, technical names verbatim. Main labels at least 48 px equivalent on a 1024px-wide canvas, supporting labels at least 38 px. No tiny footnotes, no paragraph text, no overlapping/crossing wires, no cropped letters, no watermarks or decorative filler. Preserve technical meaning, not old positions.
Portrait canvas 3:4. Title "失败怎么重试，资源何时回收". Exactly three clearly separated vertically stacked panels, with no connectors between panels. Big readable text, no tiny footnotes.
PANEL 1 violet title "① 失败后，先判断能否重试".
At top two lines "提交器失败 / Ray 作业失败等" and "允许重试，且还有次数？".
Then two simple independent labelled horizontal rows:
"是" -> "新建集群，重新执行"
"否" -> "最终失败"
Below these rows large note "顶层 backoffLimit，默认 0".
Do not draw an arrow that links success and failure rows to each other. The condition applies to both cases.
PANEL 2 red title "② 整个流程超时，不重试".
Two large lines "activeDeadlineSeconds 超时" and "DeadlineExceeded → 最终失败".
The heading defines full workflow, including cluster creation, submission and running.
PANEL 3 green title "③ 终态后，按配置回收".
Text at top "shutdownAfterJobFinishes=true" broken into two lines only if needed at the = sign, keep exact spelling. Then single left-to-right flow with three large labels "终态" -> "等待 TTL" -> "删除 RayCluster". Below two readable lines "开关默认 false" and "CR / 提交器保留情况另看删除策略".
Do not imply cleanup is enabled by default. Do not add arrows between panels. No crossing arrows, no decorative symbols, no technical text smaller than the agreed minimum.
```

## 控制循环图修正

编辑目标为第 2 张的初次生成结果；最终图片保存为 `02-control.png`。

```text
Use case: precise-object-edit. Input image is the edit target.
Correct ONE connector in this Chinese KubeRay diagram. Preserve everything else exactly: canvas, title, every word, colors, font sizes, central boxes, downward arrows, left dashed observation loop and bottom note.
The violet RIGHT-SIDE return arrow labelled "回写 status" has the wrong source. It currently starts at the "Pod / Service / Job" box.
ERASE the entire lower portion of that violet connector from the Pod / Service / Job box up to the height of KubeRay Operator. Erase its old label at the lower height.
REDRAW that return arrow starting on the RIGHT EDGE of the "KubeRay Operator" box (middle y around 625), going horizontally to the existing right lane, then UP, then LEFT into the RIGHT EDGE of the top "自定义资源" box (y around 275).
The arrowhead must remain at 自定义资源. Put the violet label "回写" / "status" in the right margin between the top box and Operator box, next to this now SHORTER loop.
There must be NO violet line on the right side below the Operator box. In particular, nothing connects Pod / Service / Job to 自定义资源.
Semantics: Operator writes status to the custom resource. Resources do not themselves write status into that CR.
Change no other element. Do not add labels or connectors.
```
