# 四家企业核查资料包标准化数据包

本目录是四家真实企业核查/碳足迹资料包的标准化 staging 数据。它面向平台导入和端到端验收，不代表数据已经写入数据库。

## 验证包入口

- `enterprises/<enterprise_code>/`：每个企业一个独立租户验证包，后续页面验证应优先使用这里的数据，不跨企业混用。
- `enterprises/<enterprise_code>/page_upload_validation_checklist.csv`：该企业逐页面上传/录入验证清单。
- `overall_page_test_matrix.csv`：跨企业、跨页面的功能测试完整度和流畅度总矩阵。
- `_aggregate/`：全企业合并 staging 数据，只用于开发导入器、做全量统计或排查字段，不作为页面上传/录入源。

## 目录治理硬口径

1. 企业资料包是隔离单元。后续任何页面上传、录入、导入、下载、导出验证，都必须先选定一个企业子包和对应租户，不得从另一个企业补数据。
2. 页面数据按企业子包内的功能目录取数：`01_carbon_accounting` 对应 `/carbon/accounting`，`02_carbon_product_footprint` 对应 `/carbon/product-footprint`，`03_carbon_supply_chain` 对应 `/carbon/supply-chain`，`04_carbon_verification` 对应 `/carbon/verification`，`05_energy_management` 对应 `/energy/*`，`06_carbon_assets` 对应 `/carbon/assets`。
3. `_aggregate/` 合并 CSV 不是页面上传源，只能用于生成导入器、排查字段和汇总统计。

## 标准化产物

| 文件 | 行数 | 用途 |
| --- | ---: | --- |
| `_aggregate/enterprise_profiles.csv` | 4 | 企业租户创建输入 |
| `_aggregate/source_files.csv` | 233 | 原始附件索引、哈希、材料分组 |
| `_aggregate/reporting_organizations.csv` | 4 | 报告主体 |
| `_aggregate/reporting_periods.csv` | 4 | 报告期 |
| `_aggregate/organization_boundaries.csv` | 4 | 组织/产品T1边界 |
| `_aggregate/production_products.csv` | 4 | 产品主数据 |
| `_aggregate/production_output_facts.csv` | 26 | 产量分母事实 |
| `_aggregate/product_footprint_studies.csv` | 4 | 产品碳足迹研究 |
| `_aggregate/product_system_boundaries.csv` | 4 | 产品系统边界 |
| `_aggregate/product_lifecycle_stages.csv` | 24 | 生命周期阶段 |
| `_aggregate/product_footprint_inventory_items.csv` | 175 | PCF活动清单 |
| `_aggregate/product_footprint_results.csv` | 4 | PCF结果版本 |
| `_aggregate/emission_factors.csv` | 3 |  |
| `_aggregate/supply_chain_suppliers.csv` | 4 | 供应商档案 |
| `_aggregate/supplier_sites.csv` | 4 | 供应商场站 |
| `_aggregate/supplier_disclosure_tasks.csv` | 4 | 供应商填报任务 |
| `_aggregate/supplier_carbon_data.csv` | 4 | 供应商碳数据/PCF披露 |
| `_aggregate/energy_interval_facts.csv` | 313 | 月度/设备级能源消费事实 |
| `_aggregate/scope1_stationary_combustion.csv` | 60 | 固定燃烧 Scope1 数据 |
| `_aggregate/scope2_electricity_bills.csv` | 39 | Scope2 电力账单/汇总 |
| `_aggregate/scope3_waste_disposal.csv` | 3 | Scope3 废弃物处理 |
| `_aggregate/carbon_verification_projects.csv` | 4 | 核查项目 |
| `_aggregate/carbon_accounting_batches.csv` | 4 | 核算批次 staging |
| `_aggregate/carbon_emission_inventory_items.csv` | 24 | 清单条目 staging |
| `_aggregate/carbon_assets_assumptions.csv` | 4 | 碳资产模拟假设 |
| `standardization_coverage.csv` | 100 | 覆盖度与缺口 |
| `platform_table_mapping.csv` | 25 | 标准数据集到平台表映射 |

## 企业结果摘要

| 企业 | 租户 slug | 产品 | PCF结果(kgCO2e/声明单位) | PCF清单行 | 能源事实行 | 附件索引行 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 宁波迈柏科技股份有限公司 | `nb-maibo-2025` | PCF-MAIBO-2025 | 6.73 | 120 | 12 | 166 |
| 鸿通科技（厦门）有限公司 | `xm-hongtong-2025` | PCF-HONGTONG-2025 | 8.91863792197842 | 27 | 24 | 31 |
| 上海马陆日用友捷汽车电气有限公司 | `sh-malu-youjie-2025` | PCF-MALU-2025 | 3.57687642287556 | 18 | 1 | 14 |
| 本田金属技术(佛山)有限公司 | `fs-honda-metal-2025` | PCF-HONDA-2025 | 6.06682310583861 | 10 | 276 | 22 |

## 当前导入与验收状态

- 已有真实企业资料包导入命令：`app carbon import-real-company-package docs/评价方案/real_company_standardized_data/enterprises/<enterprise_code>`；同时新增实施/验收 API `GET /api/carbon/real-company-packages` 和 `POST /api/carbon/real-company-packages/{enterprise_code}/import`，并在 `/energy/consumption` 的“数据导入”Tab 提供企业资料包导入入口。导入时按企业子包创建/选择独立租户，不跨企业补数据；四个企业子包已通过浏览器页面 dry-run 验证。
- 已有能源页面导入入口：`POST /api/energy/imports/datasets` 和 `/energy/consumption` 的“数据导入”Tab，可导入 `energy_interval_facts`、`scope1_stationary_combustion`、`scope2_electricity_bills`、`production_output_facts`。
- 迈柏已从嵌套证据 ZIP 抽取 `2025年迈柏电费.xls` 的 12 个月电力事实、12 条 Scope2 电力账单，以及 `理想分配阀产出统计表单-20260527.xlsx` 的产量分母。能源 7 个页面来源状态均可见并可驱动分析，但能源消费和组织碳核算仍因缺 Scope1 固定燃烧标记为部分来源。
- 四租户 `/carbon/accounting` 均已完成组织边界发布和清单重建验证；迈柏补入 Scope2 后生成 12 条纳入清单并可锁定，但仍不能认定为完整组织 GHG 盘查。
- 四租户 `/carbon/product-footprint` 均已完成真实 PCF 研究的公共报告导出验证，ZIP 包含 `product-footprint-report.docx`、`report-context.json`、清单 CSV、阶段汇总、质量摘要和 manifest。
- 四租户 `/carbon/assets` 只有模拟假设和页面写入验证。文件名/索引层资产台账缺口扫描未发现真实配额、CCER、交易、清缴或履约台账候选，因此仍为 `simulation_only`。
- 当前 48 个企业/页面组合中，页面操作可用 48/48，写入或导入流程可用 48/48，真实数据完整录入可计入 35/48；详见 `real_data_completion_scorecard.md` 和 `enterprise_user_operability_report.md`。

## 企业子包目录结构

| 子目录 | 验证用途 |
| --- | --- |
| `enterprises/<enterprise_code>/00_tenant/` | 租户与核算主体 |
| `enterprises/<enterprise_code>/01_carbon_accounting/` | 组织/产品来源碳核算 |
| `enterprises/<enterprise_code>/02_carbon_product_footprint/` | 产品碳足迹 |
| `enterprises/<enterprise_code>/03_carbon_supply_chain/` | 供应链碳数据 |
| `enterprises/<enterprise_code>/04_carbon_verification/` | 辅助核查与附件 |
| `enterprises/<enterprise_code>/05_energy_management/` | 能源管理 |
| `enterprises/<enterprise_code>/06_carbon_assets/` | 碳资产模拟 |

## 仍需完善的平台能力

1. 附件文件本体入库：企业子包内 `source_files.csv` 已有 SHA256、路径、材料分组；仍需把原始文件复制到对象存储或本地 media，并回填到核查附件、供应链证据或资产台账证据。
2. 企业端整包导入治理：当前已有固定标准化包的实施/验收页面入口；后续仍需支持企业用户上传 ZIP/目录包、批次留痕、附件对象存储、失败重试和权限边界。
3. 组织 GHG 来源补齐：鸿通、马陆、迈柏仍缺组织层 Scope1/Scope3 或完整组织边界活动数据；产品/T1 PCF 不得默认等同完整组织 GHG 盘查。
4. 碳资产真实台账：四个资料包没有真实配额、CCER、交易、清缴数据，`carbon_assets_assumptions.csv` 只能用于模拟页面验证；后续需企业补真实资产台账后再做决策有效性验收。
5. 大附件体验：迈柏辅助核查材料包体积较大，下载已验证通过，但仍应补充大小提示、进度、失败重试和归档过期策略。

## 覆盖度入口

- 逐企业/逐数据集覆盖度见 `standardization_coverage.csv`。
- 平台表清单和导入顺序见 `platform_table_mapping.md`。
- 原始附件索引以企业子包内 `03_carbon_supply_chain/source_files.csv` 和 `04_carbon_verification/source_files.csv` 为页面验证输入；全量汇总见 `_aggregate/source_files.csv`。
- 页面运行证据见 `runtime_validation/`，其中能源来源状态、组织边界发布、碳核算清单重建、碳资产来源缺口扫描和 48 页面总矩阵是当前验收主证据。
- 企业资料包导入入口的路由、包摘要和页面入口验证见 `runtime_validation/real_company_package_import_entrypoint_validation.md`；浏览器页面 dry-run 证据见 `runtime_validation/real_company_package_import_playwright_validation.md`。
- 产品碳足迹公共报告导出证据见 `runtime_validation/product_footprint_report_export_validation.md`。
- 目标完成度、剩余 13 个未计入完整录入组合和下一步优先级见 `07_目标完成度审计与下一步.md`。

## 主要缺口

| 企业 | 数据集 | 目标表 | 状态 | 说明 |
| --- | --- | --- | --- | --- |
| 宁波迈柏科技股份有限公司 | `emission_factors` | `dataapp_emissionfactor` | not_generated | Dataset not generated. |
| 宁波迈柏科技股份有限公司 | `scope1_stationary_combustion` | `dataapp_scope1stationarycombustion` | source_missing_or_not_applicable | No reliable source rows found in this package for this dataset. |
| 宁波迈柏科技股份有限公司 | `scope3_waste_disposal` | `dataapp_scope3wastedisposal` | source_missing_or_not_applicable | No reliable source rows found in this package for this dataset. |
| 鸿通科技（厦门）有限公司 | `emission_factors` | `dataapp_emissionfactor` | not_generated | Dataset not generated. |
| 鸿通科技（厦门）有限公司 | `scope1_stationary_combustion` | `dataapp_scope1stationarycombustion` | source_missing_or_not_applicable | No reliable source rows found in this package for this dataset. |
| 鸿通科技（厦门）有限公司 | `scope3_waste_disposal` | `dataapp_scope3wastedisposal` | source_missing_or_not_applicable | No reliable source rows found in this package for this dataset. |
| 上海马陆日用友捷汽车电气有限公司 | `production_output_facts` | `dataapp_productionoutputfact` | source_missing_or_not_applicable | No reliable source rows found in this package for this dataset. |
| 上海马陆日用友捷汽车电气有限公司 | `emission_factors` | `dataapp_emissionfactor` | not_generated | Dataset not generated. |
| 上海马陆日用友捷汽车电气有限公司 | `scope1_stationary_combustion` | `dataapp_scope1stationarycombustion` | source_missing_or_not_applicable | No reliable source rows found in this package for this dataset. |
| 上海马陆日用友捷汽车电气有限公司 | `scope3_waste_disposal` | `dataapp_scope3wastedisposal` | source_missing_or_not_applicable | No reliable source rows found in this package for this dataset. |
