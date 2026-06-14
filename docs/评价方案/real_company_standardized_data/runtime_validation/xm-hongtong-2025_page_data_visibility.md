# xm-hongtong-2025 页面数据可见性验证

本文件由 `tools/validate_real_company_tenant_visibility.py` 生成。它验证页面所需的数据库基础数据是否已经以真实资料包来源进入租户, 不替代浏览器交互验收。

| 页面 | 路由 | 来源口径 | 数据状态 | 数据集计数 | 缺失数据集 | 用户侧检查 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 能源消费 | /energy/consumption | real_source | partial_data_visible | energy_interval_facts=24; scope1_stationary_combustion=0; scope2_electricity_bills=13 | scope1_stationary_combustion | 查看能源消费事实、Scope1/Scope2来源和导出。 |  |
| 能源强度 | /energy/intensity | generated_from_real_source | data_visible_ready | energy_interval_facts=24; production_output_facts=1; production_products=1 |  | 查看产品强度、面积/产量分母和趋势。 |  |
| 能源分析 | /energy/analysis | generated_from_real_source | data_visible_ready | energy_interval_facts=24 |  | 查看趋势、结构、异常排行和规则建议。 |  |
| 能效对标 | /energy/benchmark | generated_from_real_source | data_visible_ready | energy_interval_facts=24; production_output_facts=1 |  | 用真实历史数据生成或对比基线。 |  |
| 能流图 | /energy/flow | generated_from_real_source | data_visible_ready | energy_interval_facts=24 |  | 查看能流节点、流量和损耗。 |  |
| 能量平衡 | /energy/balance | generated_from_real_source | data_visible_ready | energy_interval_facts=24 |  | 查看平衡表、数据质量和优化测算。 |  |
| 能源预算 | /energy/budget | generated_from_real_source | data_visible_ready | energy_interval_facts=24; production_output_facts=1 |  | 用历史能源和产量建立预算基线。 |  |
| 碳核算 | /carbon/accounting | real_and_derived_source | partial_data_visible | reporting_organizations=1; reporting_periods=1; organization_boundaries=1; carbon_accounting_batches=1; carbon_emission_inventory_items=6; scope1_stationary_combustion=0; scope2_electricity_bills=13 | scope1_stationary_combustion | 查看主体、期间、边界、Scope记录和PCF来源清单批次。 | 当前核算批次来自产品/T1 PCF, 不能等同完整组织GHG盘查。 |
| 产品碳足迹 | /carbon/product-footprint | real_source | data_visible_ready | pcf_studies=1; pcf_inventory_items=27; pcf_results=1 |  | 查看PCF研究、阶段、活动清单和结果。 |  |
| 供应链碳管理 | /carbon/supply-chain | real_source | data_visible_ready | suppliers=1; supplier_carbon_data=1; supplier_evidence=31 |  | 查看供应商、披露任务、PCF数据和证据。 |  |
| 辅助核查 | /carbon/verification | real_source | data_visible_ready | verification_projects=1; verification_attachments=31; carbon_accounting_batches=1 |  | 查看核查项目、附件索引和导出任务入口。 |  |
| 碳资产 | /carbon/assets | simulated_assumption | simulation_visible | asset_periods=1; asset_scenarios=1 |  | 查看模拟履约期、账户和预测场景。 | 资料包无真实配额、CCER、交易和清缴来源。 |
