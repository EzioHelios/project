# 真实企业能碳资料包导入验证记录

更新时间：2026-06-14

## 验证目标

验证 `enterprises/<enterprise_code>/` 下的真实企业资料包是否能作为独立租户数据包进入平台核心能碳表，为后续 12 项页面功能的真实用户视角验收提供数据库数据基础。

本记录证明导入器 dry-run 通过，四个企业资料包已经正式导入为独立租户，并完成数据可见性验证、浏览器首屏/API smoke 验证、四租户 12 页面非破坏性深测、四租户 12 页面写入型/导入覆盖验收、四租户核查材料包导出验证，以及四租户辅助核查页面级导出下载验证。

注意：以上验证证明页面和数据链路具备较高可用性，但不等于 48 个企业/页面组合均已完成真实企业数据完整录入。完整录入口径和整改优先级见 `06_四租户12页面录入完整性整改清单.md`。

## 新增导入入口

页面入口（企业用户）：

- `/energy/consumption` -> `数据导入`
- 支持数据集：`energy_interval_facts`、`scope1_stationary_combustion`、`scope2_electricity_bills`、`production_output_facts`
- API：`POST /api/energy/imports/datasets`
- 导入方式：选择数据集、填写来源名称、上传或粘贴标准 CSV；页面返回接收行数、入库行数、跳过行数和逐行错误。

接口装配验证：

```bash
PYTHONPATH=src/py ./.venv/bin/python - <<'PY'
from app.server.asgi import create_app
app = create_app()
print([getattr(route, "path", "") for route in app.routes if "energy/imports" in getattr(route, "path", "")])
PY
```

结果：

```text
['/api/energy/imports/datasets']
```

代码级检查：

```bash
./.venv/bin/python -m py_compile src/py/app/domain/energy/usecases/imports.py src/py/app/domain/energy/controllers/imports.py
./.venv/bin/ruff check src/py/app/domain/energy/usecases/imports.py src/py/app/domain/energy/controllers/imports.py
cd src/js/web && bunx biome check src/components/carbon/energy-guide-pages.tsx
```

结果：以上新增后端文件和能源消费页面单文件检查通过。全量 `bunx tsc --noEmit --pretty false` 仍被既有类型错误阻塞，未作为本次新增入口的完成证据。

页面级能源 CSV 导入回归：

```bash
node tools/validate_energy_csv_import_with_playwright.mjs --runId 20260614P0ENERGYFINAL
```

结果文件：

- `runtime_validation/energy_csv_import_validation.csv`
- `runtime_validation/energy_csv_import_validation.md`
- `runtime_validation/<tenant_slug>_energy_csv_import_validation.csv`
- `runtime_validation/<tenant_slug>_energy_csv_import_validation.md`

回归摘要：

| 租户 | Scope2 电力账单 | Scope1 固定燃烧 | 能源计量事实 | 产量分母事实 |
| --- | --- | --- | --- | --- |
| `fs-honda-metal-2025` | `page_csv_import_passed` | `page_csv_import_passed` | `page_csv_import_passed` | `page_csv_import_passed` |
| `xm-hongtong-2025` | `page_csv_import_passed` | `source_missing` | `page_csv_import_passed` | `source_missing` |
| `sh-malu-youjie-2025` | `page_csv_import_passed` | `source_missing` | `source_missing` | `source_missing` |
| `nb-maibo-2025` | `source_missing` | `source_missing` | `source_missing` | `source_missing` |

统计：16 个企业/数据集组合中，7 个真实来源存在的组合完成页面 CSV 导入和下游 API 可见性验证，9 个组合因企业子包缺少对应数据源记录为 `source_missing`。

回归中修复的问题：

- Scope1/Scope2/能源计量导入发生数据库字段错误时，后端从 500 改为逐行错误返回，避免企业用户导入一行坏数据导致页面崩溃。
- 能源计量 `data_quality` 从企业资料包长文本归一为 `measured`、`estimated`、`manual`。
- Scope2 `billing_month` 支持 `2025-annual` 等年度来源格式，归一为合法 `YYYY-MM` 后再入库，避免能源消费视图 `to_date` 500。

后台资料包导入入口（开发/验收）：

```bash
./.venv/bin/app carbon import-real-company-package docs/评价方案/real_company_standardized_data/enterprises/honda --dry-run
./.venv/bin/app carbon import-real-company-package docs/评价方案/real_company_standardized_data/enterprises --dry-run
```

正式导入单个租户包：

```bash
./.venv/bin/app carbon import-real-company-package docs/评价方案/real_company_standardized_data/enterprises
```

正式导入全部企业包：

```bash
./.venv/bin/app carbon import-real-company-package docs/评价方案/real_company_standardized_data/enterprises
```

## 导入器覆盖范围

导入器位置：

- `src/py/app/domain/carbon/real_company_package_importer.py`
- CLI 命令：`app carbon import-real-company-package`

当前覆盖：

| 数据域 | 目标表/能力 | 处理方式 |
| --- | --- | --- |
| 租户 | `team` | 按 `tenant_slug` 创建或更新独立租户 |
| 报告主体/期间/边界 | `carbon_reporting_organization`、`carbon_reporting_period`、`carbon_organization_boundary` | 按业务键 upsert |
| 能源管理 | `dataapp_energyintervalfact`、Scope1 固定燃烧、Scope2 电力、Scope3 废弃物 | 真实来源存在则导入；缺失页面保留在清单 |
| 生产分母 | `dataapp_productionproduct`、`dataapp_productionoutputfact` | 支撑 `/energy/intensity`、`/energy/budget` |
| 产品碳足迹 | PCF study、boundary、stage、inventory、result | 按 `study_code` 解析外键 |
| 供应链碳 | supplier、site、task、carbon data、evidence | PCF 不自动发布到 Scope3 |
| 碳核算 | accounting batch、inventory item | 标记为产品/T1 PCF 来源，不等同完整组织盘查 |
| 辅助核查 | verification project、template、attachment | 附件以索引、哈希、原始文件路径入库；本地原件可进入材料包 ZIP |
| 碳资产 | compliance period、asset account、forecast scenario | 仅模拟；无真实配额/CCER/交易/清缴来源 |

## Dry-run 验证结果

命令：

```bash
./.venv/bin/app carbon import-real-company-package docs/评价方案/real_company_standardized_data/enterprises --dry-run
```

结果：4 个企业包全部 dry-run 通过。

| 企业 | 租户 | 能源事实 | Scope1 | Scope2 | 产量 | PCF清单 | 附件索引 | 数据源缺失页面 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 本田金属技术(佛山)有限公司 | `fs-honda-metal-2025` | 276 | 60 | 13 | 24 | 10 | 22 | 无 |
| 鸿通科技（厦门）有限公司 | `xm-hongtong-2025` | 24 | 0 | 13 | 0 | 27 | 31 | 无完全缺失页，能源强度/预算/碳核算为部分数据 |
| 宁波迈柏科技股份有限公司 | `nb-maibo-2025` | 0 | 0 | 0 | 0 | 120 | 166 | 能源消费、能源分析、能效对标、能流图、能量平衡、能源预算 |
| 上海马陆日用友捷汽车电气有限公司 | `sh-malu-youjie-2025` | 0 | 0 | 2 | 0 | 18 | 14 | 能源分析、能效对标、能流图、能量平衡、能源预算 |

## 正式入库验证结果

命令：

```bash
./.venv/bin/app carbon import-real-company-package docs/评价方案/real_company_standardized_data/enterprises/honda
```

结果：四个企业包正式入库成功，分别写入独立租户。

| 租户 | team_id | 结果 |
| --- | --- | --- |
| `fs-honda-metal-2025` | `564728a0-8ecd-4a8b-a5de-1e2bf6c8073e` | 已写入当前开发数据库 |
| `xm-hongtong-2025` | `813d946c-8fa0-4b49-884d-cdf2efeeb205` | 已写入当前开发数据库 |
| `nb-maibo-2025` | `f3d9cac2-ecc4-4bb4-b819-478c666b7914` | 已写入当前开发数据库 |
| `sh-malu-youjie-2025` | `4b9eab67-044d-4671-830d-570fcbc427d9` | 已写入当前开发数据库 |

`honda` 样板库内复核结果：

| 数据集 | 行数 |
| --- | ---: |
| `team` | 1 |
| `reporting_organizations` | 1 |
| `reporting_periods` | 1 |
| `organization_boundaries` | 1 |
| `energy_interval_facts` | 276 |
| `scope1_stationary_combustion` | 60 |
| `scope2_electricity_bills` | 13 |
| `scope3_waste_disposal` | 3 |
| `production_products` | 1 |
| `production_output_facts` | 24 |
| `pcf_studies` | 1 |
| `pcf_inventory_items` | 10 |
| `pcf_results` | 1 |
| `suppliers` | 1 |
| `supplier_carbon_data` | 1 |
| `supplier_evidence` | 22 |
| `verification_projects` | 1 |
| `verification_attachments` | 22 |
| `asset_periods` | 1 |
| `asset_scenarios` | 1 |

## 12 页面数据可见性验证

命令：

```bash
./.venv/bin/python tools/validate_real_company_tenant_visibility.py --tenant-slug fs-honda-metal-2025 --enterprise-code honda
```

输出：

- `runtime_validation/fs-honda-metal-2025_page_data_visibility.csv`
- `runtime_validation/fs-honda-metal-2025_page_data_visibility.md`

结果摘要：

| 页面 | 数据状态 | 说明 |
| --- | --- | --- |
| 能源消费 | `data_visible_ready` | 有能源事实、Scope1 固定燃烧、Scope2 电力 |
| 能源强度 | `data_visible_ready` | 有能源事实、产量、产品 |
| 能源分析 | `data_visible_ready` | 可由能源事实生成 |
| 能效对标 | `data_visible_ready` | 有能源事实和产量基线 |
| 能流图 | `data_visible_ready` | 可由能源事实生成 |
| 能量平衡 | `data_visible_ready` | 可由能源事实生成 |
| 能源预算 | `data_visible_ready` | 有能源事实和产量基线 |
| 碳核算 | `data_visible_ready` | 有主体、期间、边界、Scope1/2 和 PCF 来源清单；仍需注意不是完整组织 GHG 盘查 |
| 产品碳足迹 | `data_visible_ready` | 有 PCF 研究、清单、结果 |
| 供应链碳管理 | `data_visible_ready` | 有供应商、PCF 数据和证据 |
| 辅助核查 | `data_visible_ready` | 有核查项目、附件索引和核算批次 |
| 碳资产 | `simulation_visible` | 只有模拟履约期和预测场景，无真实交易/配额来源 |

四个租户均已生成页面数据可见性文件：

| 租户 | 输出文件 |
| --- | --- |
| `fs-honda-metal-2025` | `runtime_validation/fs-honda-metal-2025_page_data_visibility.csv` |
| `xm-hongtong-2025` | `runtime_validation/xm-hongtong-2025_page_data_visibility.csv` |
| `nb-maibo-2025` | `runtime_validation/nb-maibo-2025_page_data_visibility.csv` |
| `sh-malu-youjie-2025` | `runtime_validation/sh-malu-youjie-2025_page_data_visibility.csv` |

跨企业完整度统计：

| 完整度状态 | 页面数 | 说明 |
| --- | ---: | --- |
| `ready_for_platform_validation` | 29 | 具备真实来源数据或真实来源派生数据 |
| `partial_source_ready` | 9 | 资料包只覆盖部分输入 |
| `source_missing_or_assumption_only` | 6 | 资料包未提供核心数据 |
| `simulation_only` | 4 | 碳资产模拟页面 |

真实数据完整录入评分：

- 评分表：`real_data_completion_scorecard.md` / `real_data_completion_scorecard.csv`
- 48 个企业/页面组合中，29 项可计入真实完整录入，19 项不得计入。
- 不得计入的 19 项包括：部分来源 8、来源缺失 6、纯模拟 4、源缺失阻塞 1。

## 浏览器首屏/API smoke 验证

命令：

```bash
node tools/validate_real_company_pages_with_playwright.mjs --enterpriseCode honda --tenantSlug fs-honda-metal-2025 --teamId 564728a0-8ecd-4a8b-a5de-1e2bf6c8073e --teamName '本田金属技术(佛山)有限公司'
```

四个租户均已执行浏览器首屏验证。脚本会登录、设置 `currentTeam`、重新加载应用，并逐个访问 12 个页面。

| 指标 | 结果 |
| --- | ---: |
| 租户数 | 4 |
| 页面数 | 48 |
| `loaded_no_obvious_error` | 48 |
| API 4xx/5xx | 0 |
| 控制台/页面错误 | 0 |
| 总矩阵 `smoothness_status=partial` | 48 |

输出文件：

| 租户 | 输出文件 |
| --- | --- |
| `fs-honda-metal-2025` | `runtime_validation/fs-honda-metal-2025_browser_page_validation.csv` |
| `xm-hongtong-2025` | `runtime_validation/xm-hongtong-2025_browser_page_validation.csv` |
| `nb-maibo-2025` | `runtime_validation/nb-maibo-2025_browser_page_validation.csv` |
| `sh-malu-youjie-2025` | `runtime_validation/sh-malu-youjie-2025_browser_page_validation.csv` |

说明：该验证证明页面首屏和主要 API 没有明显崩溃，不代表上传/录入、筛选、导出、报告下载和证据文件回放已经完成。

## 四租户 12 页面非破坏性深测

命令：

```bash
node tools/deep_validate_real_company_pages_with_playwright.mjs --enterpriseCode honda --tenantSlug fs-honda-metal-2025 --teamId 564728a0-8ecd-4a8b-a5de-1e2bf6c8073e --teamName '本田金属技术(佛山)有限公司'
node tools/deep_validate_real_company_pages_with_playwright.mjs --enterpriseCode hongtong --tenantSlug xm-hongtong-2025 --teamId 813d946c-8fa0-4b49-884d-cdf2efeeb205 --teamName '鸿通科技（厦门）有限公司'
node tools/deep_validate_real_company_pages_with_playwright.mjs --enterpriseCode malu --tenantSlug sh-malu-youjie-2025 --teamId 4b9eab67-044d-4671-830d-570fcbc427d9 --teamName '上海马陆日用友捷汽车电气有限公司'
node tools/deep_validate_real_company_pages_with_playwright.mjs --enterpriseCode maibo --tenantSlug nb-maibo-2025 --teamId f3d9cac2-ecc4-4bb4-b819-478c666b7914 --teamName '宁波迈柏科技股份有限公司'
```

本轮深测只执行非破坏性操作：切换 Tab、查询/重置/刷新、打开但不提交新增入口、检查页面数据提示。

输出文件：

- `runtime_validation/fs-honda-metal-2025_deep_page_validation.csv`
- `runtime_validation/fs-honda-metal-2025_deep_page_validation.md`
- `runtime_validation/xm-hongtong-2025_deep_page_validation.csv`
- `runtime_validation/xm-hongtong-2025_deep_page_validation.md`
- `runtime_validation/sh-malu-youjie-2025_deep_page_validation.csv`
- `runtime_validation/sh-malu-youjie-2025_deep_page_validation.md`
- `runtime_validation/nb-maibo-2025_deep_page_validation.csv`
- `runtime_validation/nb-maibo-2025_deep_page_validation.md`

结果：

| 指标 | 结果 |
| --- | ---: |
| 租户数 | 4 |
| 页面数 | 48 |
| `deep_non_destructive_passed` | 48 |
| API 4xx/5xx | 0 |
| Tab 通过 | 256/256 |
| 安全操作通过 | 48/48 |
| 新增入口打开通过 | 20/20 |
| 控制台 warning/error 计数 | 0 |

说明：四个租户均已证明 12 页面可完成非破坏性业务巡检；写入型流程已在下一节单独记录。能源预算、产品碳足迹、供应链碳管理和碳资产页面的业务弹窗已补齐无障碍描述，复测后控制台 warning/error 计数为 0。

## 四租户 12 页面写入型/导入覆盖验收

命令：

```bash
node tools/write_validate_real_company_pages_with_playwright.mjs --enterpriseCode honda --tenantSlug fs-honda-metal-2025 --teamId 564728a0-8ecd-4a8b-a5de-1e2bf6c8073e --teamName '本田金属技术(佛山)有限公司'
node tools/write_validate_real_company_pages_with_playwright.mjs --enterpriseCode hongtong --tenantSlug xm-hongtong-2025 --teamId 813d946c-8fa0-4b49-884d-cdf2efeeb205 --teamName '鸿通科技（厦门）有限公司'
node tools/write_validate_real_company_pages_with_playwright.mjs --enterpriseCode malu --tenantSlug sh-malu-youjie-2025 --teamId 4b9eab67-044d-4671-830d-570fcbc427d9 --teamName '上海马陆日用友捷汽车电气有限公司'
node tools/write_validate_real_company_pages_with_playwright.mjs --enterpriseCode maibo --tenantSlug nb-maibo-2025 --teamId f3d9cac2-ecc4-4bb4-b819-478c666b7914 --teamName '宁波迈柏科技股份有限公司'
```

输出文件：

- `runtime_validation/fs-honda-metal-2025_write_flow_validation.csv`
- `runtime_validation/xm-hongtong-2025_write_flow_validation.csv`
- `runtime_validation/sh-malu-youjie-2025_write_flow_validation.csv`
- `runtime_validation/nb-maibo-2025_write_flow_validation.csv`

结果：

| 指标 | 结果 |
| --- | ---: |
| 租户数 | 4 |
| 页面数 | 48 |
| `write_flow_passed` | 31 |
| `source_import_visible_not_page_write` | 9 |
| `partial_source_import_not_page_write` | 4 |
| `source_missing_not_validated` | 3 |
| `write_flow_blocked_source_missing` | 1 |
| `write_flow_blocked_missing_result` | 0 |
| `write_flow_failed` | 0 |

租户明细：

| 租户 | 写入通过 | 完整导入覆盖 | 部分导入覆盖 | 源数据缺失 | 源数据阻塞 | 缺结果阻塞 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `fs-honda-metal-2025` | 8 | 4 | 0 | 0 | 0 | 0 |
| `xm-hongtong-2025` | 8 | 2 | 2 | 0 | 0 | 0 |
| `sh-malu-youjie-2025` | 8 | 0 | 2 | 2 | 0 | 0 |
| `nb-maibo-2025` | 7 | 0 | 1 | 3 | 1 | 0 |

关键发现：

- 多数企业资料包的组织边界导入后仍是草稿且缺少纳入设施；碳排放核算写入验收需要先补齐设施并发布边界。
- 本田、鸿通、马陆可形成并锁定组织核算批次；本田 3 条固废 Scope3 记录已从企业碳排放清册“排放因子-废料”sheet 提取可追溯 ecoinvent 因子并进入因子库。
- 迈柏缺少可纳入组织碳核算的已审核 Scope 活动数据；平台已拒绝锁定 `record_count=0`、`included_record_count=0` 的空清单。
- 能源消费已具备页面级 CSV 导入入口和模板下载；能源强度、能源分析、能流图等分析页面通过来源状态面板显示缺失数据集，并跳转到能源消费的数据导入 Tab、对应模板和模板下载；数据源缺失页面仍在总矩阵中单独标记，不因有导入入口而计入真实完成。
- 能效对标、能量平衡、能源预算在部分源数据缺失企业中可写入演示/模拟对象，但不能算真实企业数据完整录入；需要在页面和导出结果中保留来源/假设标识。

总矩阵已回填：

- `overall_page_test_matrix.csv`
- `overall_page_test_matrix.md`
- `06_四租户12页面录入完整性整改清单.md`

## 报告与核查材料包导出验证

命令：

```bash
node tools/validate_verification_evidence_packages_with_playwright.mjs
```

验证方式：逐租户登录、设置 `x-team-id`，在 `/carbon/verification` 下创建 `material_package` 导出任务，通过下载接口流式取回 ZIP，并检查 `manifest.json`、`evidence/evidence-manifest.csv`、报告文件和原始证据纳入状态。

输出文件：

- `runtime_validation/verification_evidence_package_validation.csv`
- `runtime_validation/verification_evidence_package_validation.md`
- `runtime_validation/verification_evidence_exports/<tenant_slug>/*.zip`

结果：

| 租户 | 证据项 | 已纳入 | 缺失/不可用 | 结果 |
| --- | ---: | ---: | ---: | --- |
| `fs-honda-metal-2025` | 105 | 105 | 0 | `evidence_package_exported` |
| `xm-hongtong-2025` | 45 | 45 | 0 | `evidence_package_exported` |
| `sh-malu-youjie-2025` | 17 | 17 | 0 | `evidence_package_exported` |
| `nb-maibo-2025` | 168 | 168 | 0 | `evidence_package_exported` |

说明：

- 导出包包含报告文件、清单 CSV、证据 manifest、审计 CSV 和原始证据文件。
- 企业原始附件已归档到 `evidence_archive/<enterprise_code>/`；嵌套压缩包成员会在导入时解包归档，避免 Docker 后端无法读取 `/Users/.../Downloads` 本机路径。
- Scope1/Scope2/Scope3 台账的 `attachment` 字段也会指向仓库内归档文件，避免材料包导出时台账附件缺失。
- 验证脚本使用下载接口流式写 ZIP，避免大证据包通过浏览器 JS 内存拷贝导致 OOM。

页面级操作验证：

```bash
node tools/validate_verification_ui_export_with_playwright.mjs
```

该脚本按四个租户实际访问 `/carbon/verification`，切换“报告导出”，点击“生成核查材料包”，再在“导出记录”中点击“下载”，并检查下载 ZIP 中的 `manifest.json` 和 `evidence/evidence-manifest.csv`。结果为 4/4 通过，输出：

- `runtime_validation/verification_ui_export_validation.csv`
- `runtime_validation/verification_ui_export_validation.md`
- `runtime_validation/verification_ui_exports/<tenant_slug>/*.zip`

## 已发现并修正的数据适配问题

| 问题 | 处理 |
| --- | --- |
| Python `dict/list` 不能直接写入 PostgreSQL JSON 字段 | 在通用 upsert helper 中为 JSON 参数绑定 SQLAlchemy `JSON` 类型 |
| `data_quality`、`inventory_status`、`quality_status`、`project_type` 等源值超过平台枚举字段长度 | 增加导入侧短码映射，完整来源说明保留在 `remark`、`source_payload` 或源 CSV |
| Scope2 年度电量行的 `billing_month=2025-annual` 不符合平台 `YYYY-MM` 字段 | 导入时规范化为 `2025-12`，原始来源保留在备注 |
| 供应商 PCF 数据未提供 `published_to_scope3` | 显式写入 `false`，避免供应商 PCF 自动混入 Scope3 |
| 碳资产模型 ORM 默认值没有数据库 server default | 导入器显式写入模拟履约期风险阈值和预测默认值 |
| 附件只写相对路径导致材料包导出 `missing_file=22` | 导入器改为根据企业 `package_root` 写入真实原件绝对路径，重新导出后 `included=22`、`missing_file=0` |
| 碳核算清单接口参数 `scope` 与 Litestar ASGI `scope` 注入名冲突 | 控制器改用 `scope_filter` 并保留 query alias `scope`；租户上下文下清单查询显式按 `team_id` 过滤 |
| 历史 MVP 附件状态 `approved` 不在当前附件枚举内，导致辅助核查附件汇总 500 | MVP 种子数据后续写入 `ready`；附件读取侧兼容历史 `approved` 并映射为材料就绪 |
| Docker 后端无法读取主机 `/Users/.../Downloads` 绝对路径 | 导入器将企业原始证据归档到仓库 `docs/评价方案/real_company_standardized_data/evidence_archive/<enterprise_code>/` 并写入仓库相对路径 |
| Scope 台账附件字段仍保留 Downloads 路径，导致材料包二次缺失 | Scope1/Scope2/Scope3 导入时同步归档 `attachment` 并写入仓库相对路径 |
| 浏览器下载大 ZIP 时把二进制转成 JS 数组导致 Node OOM | 证据包验证脚本改为 Node `fetch` + stream pipeline 流式下载 |
| 组织碳核算页面无法区分 Scope 来源缺失、边界缺失和清单为空 | 新增 `GET /api/carbon/accounting/readiness` 和“核算结果/来源状态”面板；最新四租户验证显示本田、鸿通、马陆为 `ready`，迈柏为 `source_missing` |
| 资料包已有草稿边界但没有边界设施，企业需重复手填同名核算单元才能发布 | 组织边界页面新增“生成设施”动作，后端按资料包边界生成可追溯纳入设施；四租户页面验证 4/4 可生成/复用设施并发布边界 |
| 天然气来源值与因子键不一致导致本田 Scope1 固定燃烧缺计算结果 | 因子解析器增加 `天然气 -> natural_gas` 和 `m3/m³/Nm³` 等价匹配，复用现有 NCSC 2026 天然气因子；本田天然气缺结果已清零 |
| 缺少 CO2e 计算结果的组织碳核算批次仍可能被锁定 | `lock_batch()` 增加缺结果防线；当前四租户重建验证显示本田、鸿通、马陆完整清单可锁定，迈柏空清单拒绝锁定 |
| 缺结果被正确阻断后，企业用户无法在页面直接拿到待补记录或回传补录 | `/carbon/accounting` 核算结果页新增“缺结果记录”面板、CSV 下载、补录模板和补录 CSV 上传校验；本田旧 3 条固废缺结果曾通过页面定位、下载、模板下载、缺必填补录拒收、`validation-only` 完整补录写入和重建恢复验证；当前已改为可追溯因子计算链路 |
| 部分能源页面写入可通过但无法区分真实来源、部分来源和来源缺失 | 能源消费、能源强度、能源分析、能流图、能量平衡、能效对标、能源预算 7 页接入 `GET /api/energy/source-readiness`；四租户 28 个页面组合浏览器验证全部可见来源状态；缺源页面已增加缺失数据集标签和统一数据导入入口，马陆租户导入引导验证通过 |
| 能源 CSV 导入错误只能在页面上查看，企业无法留存错误行 | 能源消费“数据导入”Tab 增加错误行 CSV 下载；本田租户非法 Scope2 样例验证显示可下载 `row_number/message/raw_csv_line` 并保留原始错误行 |
| 产品碳足迹/供应链页面已有真实资料包数据但未明确区分企业来源和验证写入 | `/carbon/product-footprint` 新增 `GET /api/carbon/product-footprint/source-readiness`，`/carbon/supply-chain` 新增 `GET /api/carbon/supply-chain/source-readiness`，两页均显示“来源状态”；四租户 8/8 页面组合验证通过，均显示 `真实来源`，并单独统计 `real-company-write-validation` |
| 辅助核查页面已有真实证据包和导出能力，但未在页面汇总真实来源和平台生成记录 | `/carbon/verification` 新增 `GET /api/carbon/verification/source-readiness` 和“来源状态”面板；四租户 4/4 页面组合验证通过，均显示 `真实来源`，并单独统计就绪附件、材料包文件、缺失凭证和平台生成记录 |
| 碳资产写入流程通过后容易被误判为真实配额/交易台账 | `/carbon/assets` 新增 `GET /api/carbon/assets/source-readiness`、“资产来源”面板和“台账导入”Tab；四租户页面验证 4/4 显示 `模拟来源`，真实资产台账模板下载 4/4 通过，本田台账导入验证 7 行入库、1 行错误拒收并下载错误 CSV；写入验收来源 `real-company-write-validation` / `enterprise_asset_rule` 不计入真实资产来源 |
| 根目录同名业务 CSV 容易被误用为页面上传源 | 全企业合并业务 CSV 已迁入 `_aggregate/`；`tools/standardize_verification_packages.py` 已同步调整输出路径，重新标准化时仍保持“企业子包是页面验证输入、根目录只放报告/治理 CSV”的边界 |

## 后续页面验收操作建议

1. 每个企业资料包作为一个独立子目录和独立租户处理，不跨企业混用数据。
2. `honda` 可作为 12 个页面的首个完整样板租户。
3. 使用超级管理员进入平台，切换或指定 `fs-honda-metal-2025` 租户。
4. 按 `enterprises/honda/page_upload_validation_checklist.csv` 顺序访问 12 个页面；不同类型数据在对应页面分别上传、录入、筛选、导出和追溯。
5. 每个页面检查至少四件事：数据是否出现、筛选/分页是否可用、计算/导出是否可触发、来源/证据是否能追溯；辅助核查页面还需要检查 ZIP 下载、manifest 和原始证据文件。
6. 将页面结果回填到 `overall_page_test_matrix.csv`：`smoothness_status` 可使用 `passed`、`blocked`、`partial`、`not_run`。
7. 对 `maibo`、`malu` 的能源页面，不补造数据；按真实资料缺失记录页面空态和操作提示是否合理。
8. 对能源页面，先检查 `来源状态`：`source_missing` 不能计为真实企业数据闭环，`partial` 只能计为部分来源通过，`ready` 才能进入后续筛选、计算、导出和报表验收。
9. 对组织碳核算页面，先检查 `来源状态`：`source_missing` 需要补 Scope 活动数据，`boundary_missing` 可在“组织边界”Tab 通过“生成设施 -> 发布”处理，`partial` 需要继续检查排放因子/CO2e 计算结果；缺结果批次不得锁定，但可下载缺结果、下载补录模板并上传补录 CSV 进行行级校验，完整补录只有在企业提供可追溯 CO2e 口径后才可作为真实结果。
10. 对产品碳足迹和供应链页面，先检查 `来源状态`：`真实来源` 才能继续做研究、清单、结果、供应商数据、证据和披露导出验收；`验证写入记录` 只能证明页面/API 可写，不应混作企业原始资料包来源。
11. 对辅助核查页面，先检查 `来源状态`：`真实来源`、就绪附件、材料包文件和缺失凭证应与材料包 ZIP 下载验证一致；平台生成记录只能证明报告/导出流程，不替代企业原始证据来源。
12. 对碳资产页面，先检查 `资产来源`：四个当前企业包均应为 `模拟来源`，可追溯资产台账为 0；可下载真实资产台账模板并通过“台账导入”Tab 准备补数，但只有补充真实配额、CCER、交易或清缴来源并导入后，才能进入真实碳资产辅助决策验收。

## 尚未完成

- 还没有对 48 个企业/页面组合逐一做人工级 UI 深测；当前已有首屏/API smoke、写入型流程、导入覆盖和核查证据包下载验证。
- 原始附件已可通过仓库归档路径进入导出 ZIP；长期归档到 media/object storage、权限控制和页面文件预览仍需后续产品化。
- 报告/材料包导出已通过接口和下载用例验证；仍建议在 `/carbon/verification` 页面补做按钮、任务列表、下载交互和失败重试体验验证。
