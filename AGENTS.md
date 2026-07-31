# 代理协作约定

## 上传到 GitHub

当用户要求「上传到 GitHub」或「推送到 GitHub」时，默认直接使用 Git：

```bash
git add <用户指定或本次任务相关的文件>
git commit -m "<简洁提交说明>"
git push origin main
```

- 不默认使用 `gh`。
- 不默认创建分支、Pull Request 或 Draft PR。
- 工作区存在无关修改或未跟踪文件时，只暂存用户指定或本次任务产生的文件。
- 用户明确指定分支、远程仓库或提交范围时，以用户的要求为准。

## 每次修改后的上传

每次完成对仓库文件的修改后，都要将本次修改涉及的文件提交并推送到 GitHub：

```bash
git add <本次修改的文件>
git commit -m "<简洁提交说明>"
git push origin main
```

仍然不得把无关的已修改文件或未跟踪文件一并提交。
