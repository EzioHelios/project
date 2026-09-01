# 操作手册与演示文档

本目录用于维护客户演示和用户操作说明。

## 目录约定

- `woheng-showcase/pages/*.md`：面向演示和客户沟通的多页面正式正文。
- `woheng-showcase/manual-manifest.json`：手册结构、路由、步骤、截图 ID 和截图文件名。
- `src/js/web/public/help/woheng-showcase/`：由脚本生成的前端静态手册站点。
- `src/js/web/public/help/woheng-showcase/manual-audit.json`：截图匹配审计结果。

## 生成方式

```bash
cd src/js/web
bun run docs:manual:woheng
```

如需先补截图：

```bash
cd src/js/web
bun run qa:evidence:woheng-showcase:isolated
bun run docs:manual:woheng
```

手册正文不写截图验证备注；缺图、补拍和验证状态记录在 `manual-manifest.json` 与 `manual-audit.json` 中。

前端服务启动后，访问：

```text
/help/woheng-showcase/index.html
```
