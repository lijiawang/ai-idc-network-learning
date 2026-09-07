import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, extname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const require = createRequire(import.meta.url);
const { marked, Renderer } = await import(pathToFileURL(require.resolve('marked')).href);
const outputDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryDirectory = resolve(outputDirectory, '../..');
const inputPath = process.argv[2]
  ? resolve(process.argv[2])
  : resolve(repositoryDirectory, 'Kubernetes 已经能跑 Pod，为什么还需要 KubeRay？（公众号版）.md');
const outputPath = process.argv[3]
  ? resolve(process.argv[3])
  : resolve(outputDirectory, 'preview.html');

const escapeHtml = (text) => text.replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[character]);

const markdown = await readFile(inputPath, 'utf8');
const title = markdown.match(/^#\s+(.+)$/m)?.[1] ?? '文章预览';
const imageTypes = {
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.webp': 'image/webp', '.gif': 'image/gif', '.svg': 'image/svg+xml',
};
let imageCount = 0;
const renderer = new Renderer();
// Markdown 原样 HTML 显示为文本，预览不执行文章中夹带的代码。
renderer.html = ({ text }) => escapeHtml(text);

let article = await marked.parse(markdown, {
  async: true,
  gfm: true,
  renderer,
  walkTokens: async (token) => {
    if (token.type !== 'image') return;
    if (token.href.startsWith('data:image/')) {
      imageCount += 1;
      return;
    }
    if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(token.href)) {
      throw new Error(`离线预览需要本地图片，请先替换图片地址：${token.href}`);
    }
    const imagePath = resolve(dirname(inputPath), decodeURIComponent(token.href));
    const contentType = imageTypes[extname(imagePath).toLowerCase()];
    if (!contentType) throw new Error(`不支持的图片格式：${imagePath}`);
    const contents = await readFile(imagePath);
    token.href = `data:${contentType};base64,${contents.toString('base64')}`;
    imageCount += 1;
  },
});

const styles = {
  h1: 'margin:0 0 28px;color:#132c48;font-size:28px;line-height:1.4;font-weight:700;',
  h2: 'margin:38px 0 18px;color:#17476b;font-size:22px;line-height:1.5;font-weight:650;',
  h3: 'margin:28px 0 14px;color:#17476b;font-size:18px;line-height:1.6;font-weight:650;',
  p: 'margin:0 0 20px;',
  a: 'color:#1a6394;text-decoration:underline;text-underline-offset:3px;overflow-wrap:anywhere;',
  strong: 'font-weight:650;color:#243b50;',
  em: 'font-style:italic;',
  blockquote: 'margin:24px 0;padding:4px 0 4px 16px;border-left:3px solid #9bb6cc;color:#506174;',
  ul: 'margin:0 0 22px;padding-left:24px;',
  ol: 'margin:0 0 22px;padding-left:24px;',
  li: 'margin:0 0 10px;padding-left:2px;',
  hr: 'margin:32px 0;border:0;border-top:1px solid #dce4eb;',
  img: 'display:block;max-width:100%;width:100%;height:auto;margin:26px auto 8px;',
  table: 'width:100%;table-layout:fixed;border-collapse:collapse;margin:24px 0;font-size:15px;line-height:1.7;',
  th: 'padding:12px 10px;border:1px solid #dce4eb;background:#edf3f7;color:#243b50;text-align:left;font-weight:650;overflow-wrap:anywhere;',
  td: 'padding:12px 10px;border:1px solid #dce4eb;text-align:left;vertical-align:top;overflow-wrap:anywhere;',
  pre: 'margin:22px 0;padding:16px;background:#f3f6f8;border-radius:6px;font-size:14px;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;',
  code: 'font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:0.9em;background:#f0f4f7;padding:1px 4px;border-radius:3px;white-space:inherit;overflow-wrap:anywhere;',
};

article = article.replace(/<(h[1-3]|p|a|strong|em|blockquote|ul|ol|li|hr|img|table|th|td|pre|code)\b([^>]*)>/g,
  (_, tag, attributes) => `<${tag}${attributes} style="${styles[tag]}">`);
article = article.replace(/(<pre\b[^>]*>\s*<code\b[^>]*?) style="[^"]*"/g,
  '$1 style="font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:inherit;background:transparent;padding:0;white-space:inherit;overflow-wrap:anywhere;"');

const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
</head>
<body style="margin:0;background:#fff;color:#273340;">
  <article style="box-sizing:border-box;width:100%;max-width:680px;margin:0 auto;padding:32px 16px 52px;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;font-size:16px;line-height:1.8;overflow-wrap:anywhere;">
${article}
  </article>
</body>
</html>
`;

await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, html, 'utf8');
console.log(`已生成 ${outputPath}（嵌入 ${imageCount} 张图片）`);
