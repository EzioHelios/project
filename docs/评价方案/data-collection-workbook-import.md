# 能碳采集包导入设计说明

## 目标

能碳采集包用于把企业基本信息、报告范围、产量、能源消费、组织碳活动数据、排放因子和产品碳足迹数据放到一个多 sheet Excel 中统一导入。用户可见表头使用中文业务字段，系统字段放在隐藏的第 2 行用于稳定识别。

## 模板规则

- 第 1 行：中文业务字段，必填字段用 `*` 标记。
- 第 2 行：系统识别字段，默认隐藏。
- 第 3 行起：填报数据。
- 枚举字段支持中文值，例如 `外购蒸汽`、`柴油`、`维修补充`、`重型货车`。
- 模板下载接口：`GET /api/carbon/data-collection-workbooks/template`。
- 导入预览接口：`POST /api/carbon/data-collection-workbooks/preview`。
- 正式导入接口：`POST /api/carbon/data-collection-workbooks/import`。

## Sheet 覆盖范围

| Sheet | 数据集 | 主要用途 |
| --- | --- | --- |
| `01_企业基本信息` | `enterprise_profiles` | 企业、租户和资料包基础信息 |
| `02_报告组织` | `reporting_organizations` | 组织碳核算报告主体 |
| `03_报告期间` | `reporting_periods` | 报告年度或期间 |
| `04_组织边界` | `organization_boundaries` | 组织边界和控制方法 |
| `05_产品主数据` | `production_products` | 产品档案 |
| `06_产量分母` | `production_output_facts` | 产品产量、作业量等强度分母 |
| `07_能源计量事实` | `energy_interval_facts` | 能源消费明细 |
| `08_Scope1移动源燃烧` | `scope1_mobile_combustion` | 车辆、叉车等移动燃烧 |
| `09_Scope1固定源燃烧` | `scope1_stationary_combustion` | 锅炉、炉窑等固定燃烧 |
| `10_Scope1制冷剂逸散` | `scope1_refrigerant_leak` | 制冷剂填充、维修补充和泄漏 |
| `11_Scope2电力账单` | `scope2_electricity_bills` | 外购电力账单 |
| `12_Scope2外购热汽冷` | `scope2_purchased_energy` | 外购热力、蒸汽、冷量 |
| `13_Scope3废弃物` | `scope3_waste_disposal` | 废弃物处置活动数据 |
| `14_Scope3外购运输` | `scope3_third_party_transport` | 第三方运输活动数据 |
| `15_排放因子` | `emission_factors` | 组织核算和活动数据计算因子 |
| `16_PCF研究` | `product_footprint_studies` | 产品碳足迹研究主数据 |
| `17_PCF系统边界` | `product_system_boundaries` | 产品系统边界 |
| `18_PCF生命周期阶段` | `product_lifecycle_stages` | 生命周期阶段 |
| `19_PCF清单项` | `product_footprint_inventory_items` | 产品碳足迹清单项 |
| `20_PCF结果` | `product_footprint_results` | 产品碳足迹核算结果 |
| `21_组织碳核算批次` | `carbon_accounting_batches` | 组织碳核算批次 |
| `22_组织碳清册结果` | `carbon_emission_inventory_items` | 组织碳排放清册结果 |

## 测试样本

脱敏样本模板位于：

`docs/评价方案/templates/honda-metal-sanitized-energy-carbon-data-collection.xlsx`

集成测试覆盖：

- 下载模板首行中文表头和隐藏识别行。
- 解析本田金属脱敏包生成的多 sheet Excel。
- Scope 1 移动源燃烧、Scope 1 固定源燃烧、Scope 1 制冷剂逸散。
- Scope 2 电力账单、外购热力/蒸汽/冷量。
- Scope 3 废弃物、外购运输。
- 产量分母、能源计量事实、产品碳足迹清单和结果。
- 预览接口行数、缺失必填项和中文枚举显示。
- 正式导入后的数据库行数。
