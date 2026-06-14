# 四家企业核查资料包标准化数据与平台表映射

本目录由 `tools/standardize_verification_packages.py` 生成。CSV 文件是标准化 staging 数据，不直接声明已经入库。

页面上传/录入验证必须使用 `enterprises/<enterprise_code>/<功能目录>/` 下的数据集文件；`_aggregate/` 下同名 CSV 仅为全企业汇总副本，用于字段排查和统计。

## 数据集清单

| 标准数据集 | 行数 | 平台目标表 | 导入状态 | 说明 |
| --- | ---: | --- | --- | --- |
| `enterprise_profiles.csv` | 4 | `team` | requires tenant creation API/CLI | One team per enterprise package. |
| `source_files.csv` | 233 | `carbon_verification_attachment; carbon_supplier_evidence` | csv ready, file copy/upload still needed | Keeps original evidence metadata and source path. |
| `reporting_organizations.csv` | 4 | `carbon_reporting_organization` | csv ready | Organization-level reporting entity. |
| `reporting_periods.csv` | 4 | `carbon_reporting_period` | csv ready | Annual 2025 reporting period. |
| `organization_boundaries.csv` | 4 | `carbon_organization_boundary` | csv ready | Operational-control boundary inferred from T1 package. |
| `production_products.csv` | 4 | `dataapp_productionproduct` | csv ready | Product dictionary for PCF and intensity denominator. |
| `production_output_facts.csv` | 26 | `dataapp_productionoutputfact` | csv ready where source exists | Honda has monthly production source; Maibo and Hongtong have annual output sources; others need production quantities from package/forms. |
| `product_footprint_studies.csv` | 4 | `carbon_product_footprint_study` | csv ready | One PCF study per enterprise/product package. |
| `product_system_boundaries.csv` | 4 | `carbon_product_system_boundary` | csv ready | T1/cradle-to-gate style boundary from workbooks. |
| `product_lifecycle_stages.csv` | 24 | `carbon_product_lifecycle_stage` | csv ready | Lifecycle stage summary. |
| `product_footprint_inventory_items.csv` | 175 | `carbon_product_footprint_inventory_item` | csv ready | Activity rows normalized from quality assessment/calculation sheets. |
| `product_footprint_results.csv` | 4 | `carbon_product_footprint_result` | csv ready | Final PCF values cross-checkable with PDF reports. |
| `emission_factors.csv` | 3 | `dataapp_emissionfactor` | csv ready where source exists | Traceable waste calculation factors extracted from enterprise carbon checklists. |
| `supply_chain_suppliers.csv` | 4 | `carbon_supply_chain_supplier` | csv ready | Each enterprise is modeled as one supplier package. |
| `supplier_sites.csv` | 4 | `carbon_supplier_site` | csv ready with limited address detail | Site details are sparse unless address appears in forms. |
| `supplier_disclosure_tasks.csv` | 4 | `carbon_supplier_disclosure_task` | csv ready | One product disclosure task per package. |
| `supplier_carbon_data.csv` | 4 | `carbon_supplier_carbon_data` | csv ready | Approved PCF summary data for downstream use. |
| `energy_interval_facts.csv` | 313 | `dataapp_energyintervalfact` | csv ready where source exists | Honda, Hongtong, Malu, and Maibo include usable energy records. |
| `scope1_stationary_combustion.csv` | 60 | `dataapp_scope1stationarycombustion` | csv ready where source exists | Natural gas/LNG rows from Honda energy workbook. |
| `scope2_electricity_bills.csv` | 39 | `dataapp_scope2electricitybill` | csv ready where source exists | Electricity rows from Honda/Hongtong/Malu/Maibo source files. |
| `scope3_waste_disposal.csv` | 3 | `dataapp_scope3wastedisposal` | csv ready where source exists | Honda solid waste production data. |
| `carbon_verification_projects.csv` | 4 | `carbon_verification_project` | csv ready | One verification/readiness project per enterprise package. |
| `carbon_accounting_batches.csv` | 4 | `carbon_accounting_batch` | derived csv ready | Derived from PCF source, not full organization GHG inventory. |
| `carbon_emission_inventory_items.csv` | 24 | `carbon_emission_inventory_item` | derived csv ready | Derived from PCF stage rows; must be flagged as product/T1 source. |
| `carbon_assets_assumptions.csv` | 4 | `carbon_compliance_period and asset tables` | assumption only | No real quota/trade source in packages; only simulation seed candidates. |
| `platform_table_mapping.csv` | 25 | `` |  |  |

## 关键口径

- `maibo` 的源清册以 tCO2e 为计算单位，标准化时在 `product_footprint_inventory_items.csv` 中转换为 kgCO2e，并在 `remark` 保留来源说明。
- `carbon_accounting_batches.csv` 和 `carbon_emission_inventory_items.csv` 当前来自产品/T1 PCF 资料，不应宣称为完整组织 14064 盘查清单。
- `carbon_assets_assumptions.csv` 只是碳资产页面的模拟种子；四个资料包没有真实配额、CCER、交易、清缴数据。
- 企业子包内 `source_files.csv` 已计算原始附件 SHA256，但平台导入仍需要实现文件复制/对象存储上传与 DB id 关联。

## 建议导入顺序

1. `enterprise_profiles.csv` -> 创建或选择 `team` 租户。
2. `reporting_organizations.csv`, `reporting_periods.csv`, `organization_boundaries.csv`。
3. `production_products.csv`, `production_output_facts.csv`。
4. `product_footprint_studies.csv`, `product_system_boundaries.csv`, `product_lifecycle_stages.csv`, `product_footprint_inventory_items.csv`, `product_footprint_results.csv`。
5. `supply_chain_suppliers.csv`, `supplier_sites.csv`, `supplier_disclosure_tasks.csv`, `supplier_carbon_data.csv`。
6. `energy_interval_facts.csv`, `scope1_stationary_combustion.csv`, `scope2_electricity_bills.csv`, `scope3_waste_disposal.csv`。
7. `carbon_accounting_batches.csv`, `carbon_emission_inventory_items.csv`, `carbon_verification_projects.csv`, `source_files.csv`。
8. `carbon_assets_assumptions.csv` 仅用于模拟履约场景，不作为真实资产台账导入。
