# 宁波迈柏科技股份有限公司 验证数据包

- 企业代码：`maibo`
- 租户 slug：`nb-maibo-2025`
- 原始资料目录：`/Users/eziohelios/Downloads/V2打包上传`
- 产品碳足迹结果：`6.73` kgCO2e/声明单位

## 子目录

| 子目录 | 用途 | 数据集 |
| --- | --- | --- |
| `00_tenant/` | 租户与核算主体 | `enterprise_profiles.csv`, `reporting_organizations.csv`, `reporting_periods.csv`, `organization_boundaries.csv`, `production_products.csv` |
| `01_carbon_accounting/` | 组织/产品来源碳核算 | `reporting_organizations.csv`, `reporting_periods.csv`, `organization_boundaries.csv`, `carbon_accounting_batches.csv`, `carbon_emission_inventory_items.csv`, `emission_factors.csv`, `scope1_stationary_combustion.csv`, `scope2_electricity_bills.csv`, `scope3_waste_disposal.csv` |
| `02_carbon_product_footprint/` | 产品碳足迹 | `production_products.csv`, `production_output_facts.csv`, `product_footprint_studies.csv`, `product_system_boundaries.csv`, `product_lifecycle_stages.csv`, `product_footprint_inventory_items.csv`, `product_footprint_results.csv`, `scope3_waste_disposal.csv` |
| `03_carbon_supply_chain/` | 供应链碳数据 | `supply_chain_suppliers.csv`, `supplier_sites.csv`, `supplier_disclosure_tasks.csv`, `supplier_carbon_data.csv`, `source_files.csv` |
| `04_carbon_verification/` | 辅助核查与附件 | `carbon_verification_projects.csv`, `carbon_accounting_batches.csv`, `carbon_emission_inventory_items.csv`, `product_footprint_inventory_items.csv`, `product_footprint_results.csv`, `source_files.csv` |
| `05_energy_management/` | 能源管理 | `energy_interval_facts.csv`, `scope1_stationary_combustion.csv`, `scope2_electricity_bills.csv`, `production_output_facts.csv`, `production_products.csv` |
| `06_carbon_assets/` | 碳资产模拟 | `carbon_assets_assumptions.csv`, `carbon_accounting_batches.csv`, `carbon_emission_inventory_items.csv` |

## 页面验证清单

| 页面 | 路由 | 数据行 | 完整度 | 流畅度 | Gap |
| --- | --- | ---: | --- | --- | --- |
| 能源消费 | `/energy/consumption` | 24 | partial_source_ready | not_run | 缺少数据集: scope1_stationary_combustion |
| 能源强度 | `/energy/intensity` | 14 | ready_for_platform_validation | not_run |  |
| 能源分析 | `/energy/analysis` | 12 | ready_for_platform_validation | not_run |  |
| 能效对标 | `/energy/benchmark` | 13 | ready_for_platform_validation | not_run |  |
| 能流图 | `/energy/flow` | 12 | ready_for_platform_validation | not_run |  |
| 能量平衡 | `/energy/balance` | 12 | ready_for_platform_validation | not_run |  |
| 能源预算 | `/energy/budget` | 13 | ready_for_platform_validation | not_run |  |
| 碳核算 | `/carbon/accounting` | 22 | partial_source_ready | not_run | 缺少数据集: scope1_stationary_combustion 碳核算批次来自产品/T1 PCF资料，不能等同完整组织GHG盘查。 |
| 产品碳足迹 | `/carbon/product-footprint` | 129 | ready_for_platform_validation | not_run |  |
| 供应链碳管理 | `/carbon/supply-chain` | 170 | ready_for_platform_validation | not_run |  |
| 辅助核查 | `/carbon/verification` | 294 | ready_for_platform_validation | not_run |  |
| 碳资产 | `/carbon/assets` | 2 | simulation_only | not_run | 资料包没有真实配额、CCER、交易、清缴数据，只能验证模拟场景。 |

## 使用方式

1. 先用 `00_tenant/enterprise_profiles.csv` 建立或选择独立租户。
2. 按页面进入对应目录上传/录入 CSV，不跨企业混用数据。
3. 每个页面验证后回填 `page_upload_validation_checklist.csv` 的 `smoothness_status` 和 `gap_note`。
4. 跨企业统计看根目录 `overall_page_test_matrix.csv`。
