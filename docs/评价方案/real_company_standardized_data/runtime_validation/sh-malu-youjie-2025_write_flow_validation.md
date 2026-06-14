# sh-malu-youjie-2025 写入型页面流程验收

测试时间：2026-06-13T18:17:15.782Z

租户：上海马陆日用友捷汽车电气有限公司（sh-malu-youjie-2025）

测试标记：`real-company-write-validation-malu-20260613181024`

摘要：写入通过 8，完整导入覆盖 0，部分导入覆盖 2，源数据缺失 2，源数据阻塞 0，失败 0。

| 页面 | 路由 | 写入口径 | 状态 | API结果 | 页面可见性 | 创建记录 | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 能源消费 | `/energy/consumption` | `source_package_import` | `partial_source_import_not_page_write` | not_applicable | covered_by_visibility_and_deep_checks | - | 页面没有直接手工录入/上传入口；主数据录入依赖标准化资料包导入器或底层数据台账。 |
| 能源强度 | `/energy/intensity` | `source_package_import` | `partial_source_import_not_page_write` | not_applicable | covered_by_visibility_and_deep_checks | - | 页面没有直接手工录入/上传入口；主数据录入依赖标准化资料包导入器或底层数据台账。 |
| 能源分析 | `/energy/analysis` | `source_package_import` | `source_missing_not_validated` | not_applicable | not_applicable_source_missing | - | 资料包缺少该页面核心数据源；不能视为端到端录入通过。 |
| 能流图 | `/energy/flow` | `source_package_import` | `source_missing_not_validated` | not_applicable | not_applicable_source_missing | - | 资料包缺少该页面核心数据源；不能视为端到端录入通过。 |
| 碳排放核算 | `/carbon/accounting` | `page_api_write` | `write_flow_passed` | boundary_prepared_and_batch_rebuilt_locked:created_included_facility+published_boundary | visible | facility_id=12;boundary_id=29;batch_id=31;record_count=2;included_record_count=2 | - |
| 能效对标 | `/energy/benchmark` | `page_api_write` | `write_flow_passed` | profile_and_item_created | visible | profile_id=12;item_id=45 | - |
| 能量平衡 | `/energy/balance` | `page_api_write` | `write_flow_passed` | simulation_and_record_created | visible | optimization_record_id=10 | - |
| 能源预算 | `/energy/budget` | `page_api_write` | `write_flow_passed` | plan_allocations_adjustment_created | visible | plan_id=11;allocation_id=121;adjustment_id=12 | - |
| 产品碳足迹 | `/carbon/product-footprint` | `page_api_write` | `write_flow_passed` | study_boundary_stage_inventory_result_report_created | visible | study_id=38;stage_id=180;inventory_id=967;result_id=37;report_bytes=6849 | - |
| 供应链碳管理 | `/carbon/supply-chain` | `page_api_write` | `write_flow_passed` | supplier_site_task_data_evidence_review_release_created | visible | supplier_id=38;site_id=38;task_id=38;data_id=37;evidence_id=1262;release_id=9 | - |
| 辅助核查 | `/carbon/verification` | `page_api_write` | `write_flow_passed` | project_attachment_export_job_created | visible | project_id=34;attachment_id=1264;general_export_job_id=20;export_status=completed | - |
| 碳资产 | `/carbon/assets` | `page_api_write` | `write_flow_passed` | period_accounts_allowance_credit_transaction_surrender_forecast_created | visible | period_id=34;quota_account_id=41;credit_account_id=42;allowance_id=10;credit_id=10;transaction_id=10;surrender_id=10;scenario_id=33 | - |

## 操作记录

### 能源消费

- 操作：使用企业资料包标准化数据导入租户 -> 访问 /energy/consumption -> 验证页面可见性与非破坏性操作
- 证据：energy_interval_facts/scope1/scope2 已由企业资料包导入；页面当前无手工录入入口；但资料包只覆盖部分输入；source_row_count=2; missing=energy_interval_facts,scope1_stationary_combustion

### 能源强度

- 操作：使用企业资料包标准化数据导入租户 -> 访问 /energy/intensity -> 验证页面可见性与非破坏性操作
- 证据：production_output_facts/production_products 已由企业资料包导入；页面当前无手工录入入口；但资料包只覆盖部分输入；source_row_count=1; missing=energy_interval_facts,production_output_facts

### 能源分析

- 操作：使用企业资料包标准化数据导入租户 -> 访问 /energy/analysis -> 验证页面可见性与非破坏性操作
- 证据：资料包未提供该页面核心来源数据；source_row_count=0; missing=energy_interval_facts

### 能流图

- 操作：使用企业资料包标准化数据导入租户 -> 访问 /energy/flow -> 验证页面可见性与非破坏性操作
- 证据：资料包未提供该页面核心来源数据；source_row_count=0; missing=energy_interval_facts

### 碳排放核算

- 操作：进入碳排放核算 -> 补齐边界发布前置条件 -> 发布组织边界 -> 创建核算批次 -> 重建组织排放清单 -> 锁定批次 -> 核算结果 Tab 检查批次可见
- 证据：边界前置处理: created_included_facility, published_boundary; 页面可见: RV-ACC-20260613181024

### 能效对标

- 操作：进入能效对标 -> 新增标杆方案 -> 新增标杆项 -> 回到页面确认方案/对象可见
- 证据：页面可见: 写入验证标杆方案 20260613181024

### 能量平衡

- 操作：进入能量平衡 -> 执行优化测算 -> 保存优化记录 -> 切换优化记录 Tab 检查可见
- 证据：页面可见: 空压站参数优化

### 能源预算

- 操作：进入能源预算 -> 新增年度目标 -> 生成月度预算 -> 新增调整记录 -> 页面检查预算方案
- 证据：页面可见: 写入验证预算方案 20260613181024

### 产品碳足迹

- 操作：进入产品碳足迹 -> 新建研究 -> 保存边界 -> 新增阶段 -> 新增活动数据 -> 核算 -> 导出公共模板报告
- 证据：页面可见: 写入验证产品碳足迹 20260613181024

### 供应链碳管理

- 操作：进入供应链碳管理 -> 新建供应商/场站/填报任务 -> 新增数据和证据 -> 提交并审核 -> 生成披露
- 证据：页面可见: 写入验证供应商 20260613181024

### 辅助核查

- 操作：进入辅助核查 -> 新建核查项目 -> 登记证据附件 -> 生成材料包导出任务 -> 页面检查项目/附件
- 证据：页面可见: 写入验证核查项目 20260613181024

### 碳资产

- 操作：进入碳资产 -> 新建履约周期/账户/配额/信用持仓 -> 交易模拟 -> 清缴 -> 新建预测情景 -> 页面检查资产数据
- 证据：页面可见: 写入验证履约周期 20260613181024;写入验证配额账户 20260613181024
