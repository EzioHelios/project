# 操作手册与演示文档

沃衡操作手册已迁至 `refine-lca/apps/docs/docs/energy-carbon/woheng/`，通过 `docs.nexlca.com/energy-carbon/woheng` 发布。此目录保留页面步骤元数据和本地截图验证脚本的输入；后续面向用户的文字以文档站为准。

## 目录约定

- `woheng-showcase/pages/*.md`：原站点的页面源文件，供本地步骤核对；不作为文档站发布源。
- `woheng-showcase/manual-manifest.json`：手册结构、路由、步骤、截图 ID 和截图文件名。
- `src/js/web/public/help/woheng-showcase/`：旧地址的跳转兼容页，不再发布或生成手册正文。
- `src/js/web/public/help/woheng-showcase/manual-audit.json`：正式页面和旧地址的跳转映射审计结果。

## 生成方式

```bash
cd src/js/web
bun run docs:manual:woheng
```

现有 `build-manual-site.mjs` 统一生成跳转页：30 个正式页面映射到 canonical docs；旧功能索引、演示脚本、截图索引明确跳转到总览。未知旧页面或无效映射会使生成失败，避免旧正文遗漏。可通过 `--canonicalRoot /绝对路径/refine-lca/apps/docs/docs/energy-carbon/woheng` 核对文档仓库中的实际页面集合。

正文、截图和下载样例仅在文档站维护。截图补拍后替换文档站 `static/img/energy-carbon/woheng/` 中对应文件，并更新 `manual-manifests/woheng-evidence-audit.json`。生成跳转页不读取或复制截图，现有 `public/help` 历史图片暂保留，不继续更新。截图验证记录保留在模块验证报告与文档站证据清单中，不写入手册正文。

以下旧地址及其 `pages/*.html` 子页会自动跳转，并提供可点击的备用链接：

```text
/help/woheng-showcase/index.html
```

## 能源录后查询只读复拍

`src/js/web/scripts/manual/verify-energy-data-maintenance.mjs` 默认仍执行 CRUD。传入 `--phase=query`（或设置 `E2E_ENERGY_PHASE=query`）后，只检查 `/energy/consumption` 的混合能源 KPI、月度天然气数量与单位，并通过 GET 回查原始能源事实；不会新增、修改、导入或删除业务记录。

先在运行环境中设置 `E2E_ADMIN_PASSWORD`，再从项目根目录执行以下命令。默认账号为 `codex.e2e@local.test`，可通过 `E2E_ADMIN_EMAIL` 覆盖；密码没有默认值，未提供时脚本直接退出。脚本默认访问本地前端 18101，复用两基地案例配置，期间默认为 2026-10：泰州天然气 18,600 m3、59,520 元；湖州天然气 22,400 m3、71,680 元。

```bash
cd src/js/web
E2E_TENANT_SLUG=woheng-taizhou-production-base node scripts/manual/verify-energy-data-maintenance.mjs --phase=query
E2E_TENANT_SLUG=woheng-huzhou-production-base node scripts/manual/verify-energy-data-maintenance.mjs --phase=query
```

查询阶段默认将两租户产物分别写入项目根目录的 `.storage/enterprise-entry-20261115/energy` 和 `energy-huzhou`。截图编号为 EV-WH-403、EV-WH-404，报告为各目录下的 `manual-verification/energy-data-maintenance-query.json`，不覆盖 CRUD 报告及其他截图。可用 `E2E_BASE_URL`、`E2E_ENERGY_MONTH`、`MANUAL_VERIFY_OUTPUT_DIR` 覆盖地址、月份和输出目录；更换月份时，目标库须有与案例配置相符的数据。截图使用 `zh-CN`、`Asia/Shanghai`，并检查沃衡品牌与页面自然发出的租户头。

登录前会话探测返回的预期 401 单独记录在 `expectedAuthProbes`，随后成功登录属于正常验证流程；对应控制台记录标为 `expected-session-probe-401-before-login`。登录请求和登录后的接口若返回 401、403 或 5xx，仍会进入 `apiFailures` 并使验证失败。因此，`apiFailures` 为空表示没有未预期的接口失败，不表示整个运行期间从未出现 401。
