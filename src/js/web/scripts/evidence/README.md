# Evidence Capture Scripts

统一截图入口：

```bash
node src/js/web/scripts/run-demo-capture.mjs --package woheng-showcase --namespace woheng --profile full --brand woheng
node src/js/web/scripts/run-demo-capture.mjs --package chery-org-carbon-tender --namespace chery --profile tender --brand chery
```

## 约定

- `run-demo-capture.mjs` 负责启动隔离前端、注入品牌环境变量、设置输出目录，并调用 package registry 中登记的取证实现。
- `evidence/package-registry.mjs` 只登记项目级配置：package key、默认 namespace/profile/brand、取证脚本和输出目录。
- 具体截图脚本只负责业务截图清单、页面动作、数据门禁和 manifest 内容。
- 截图脚本不得依赖长期 `storageState`。运行时必须校验登录态，失败后重新登录。
- 新增项目不要再新建散落的 runner，先在 registry 增加 package，再复用统一入口。

## 常用参数

- `--package`：取证包，例如 `woheng-showcase`、`chery-org-carbon-tender`。
- `--namespace`：演示数据命名空间。
- `--profile`：演示数据 profile。
- `--brand`：品牌 profile。
- `--port`：隔离前端端口。
- `--only`：只重拍指定证据 ID。
- `--plan-only`：只生成截图计划。
- `--no-server`：不启动隔离 Vite 服务，直接使用 `E2E_BASE_URL` 或默认地址。
