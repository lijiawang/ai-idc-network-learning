# KubeRay 公众号版预览

输入为仓库根目录的《Kubernetes 已经能跑 Pod，为什么还需要 KubeRay？（公众号版）.md》，配图位于 `images/kuberay/wechat/`。生成的 `preview.html` 将图片嵌入文件，离线打开也能阅读。

准备 Node.js 和 `marked` 17.x，在仓库根目录运行：

```bash
node publishing/kuberay-wechat/build.mjs
```

如果 `marked` 在独立的依赖目录中，通过 `NODE_PATH` 指定该目录：

```bash
NODE_PATH=/path/to/node_modules node publishing/kuberay-wechat/build.mjs
```

脚本也支持 `node publishing/kuberay-wechat/build.mjs 输入.md 输出.html`。请等正文和四张配图齐备后再生成。

发布前先打开 `preview.html`，用 360px 左右的手机宽度检查正文、表格与配图字号。然后将正文导入公众号编辑器，把四张原图上传到正文，并在微信内发送预览再次检查。HTML 或 Markdown 直接粘贴不能保证排版完全还原；外链的显示和可点击性也需在编辑器中确认。

这里提供的是排版预览，尚未发布到公众号。
