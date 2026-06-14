# fs-honda-metal-2025 写入型页面流程验收

测试时间：2026-06-13T18:17:15.780Z

租户：本田金属技术(佛山)有限公司（fs-honda-metal-2025）

测试标记：`real-company-write-validation-honda-20260613180426`

摘要：写入通过 8，完整导入覆盖 4，部分导入覆盖 0，源数据缺失 0，源数据阻塞 0，失败 0。

| 页面 | 路由 | 写入口径 | 状态 | API结果 | 页面可见性 | 创建记录 | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 能源消费 | `/energy/consumption` | `source_package_import` | `source_import_visible_not_page_write` | not_applicable | covered_by_visibility_and_deep_checks | - | 页面没有直接手工录入/上传入口；主数据录入依赖标准化资料包导入器或底层数据台账。 |
| 能源强度 | `/energy/intensity` | `source_package_import` | `source_import_visible_not_page_write` | not_applicable | covered_by_visibility_and_deep_checks | - | 页面没有直接手工录入/上传入口；主数据录入依赖标准化资料包导入器或底层数据台账。 |
| 能源分析 | `/energy/analysis` | `source_package_import` | `source_import_visible_not_page_write` | not_applicable | covered_by_visibility_and_deep_checks | - | 页面没有直接手工录入/上传入口；主数据录入依赖标准化资料包导入器或底层数据台账。 |
| 能流图 | `/energy/flow` | `source_package_import` | `source_import_visible_not_page_write` | not_applicable | covered_by_visibility_and_deep_checks | - | 页面没有直接手工录入/上传入口；主数据录入依赖标准化资料包导入器或底层数据台账。 |
| 碳排放核算 | `/carbon/accounting` | `page_api_write` | `write_flow_passed` | boundary_prepared_and_batch_rebuilt_locked:created_included_facility+published_boundary | visible | facility_id=10;boundary_id=20;batch_id=29;record_count=76;included_record_count=76 | - |
| 能效对标 | `/energy/benchmark` | `page_api_write` | `write_flow_passed` | profile_and_item_created | visible | profile_id=10;item_id=43 | - |
| 能量平衡 | `/energy/balance` | `page_api_write` | `write_flow_passed` | simulation_and_record_created | visible | optimization_record_id=8 | - |
| 能源预算 | `/energy/budget` | `page_api_write` | `write_flow_passed` | plan_allocations_adjustment_created | visible | plan_id=9;allocation_id=97;adjustment_id=10 | - |
| 产品碳足迹 | `/carbon/product-footprint` | `page_api_write` | `write_flow_passed` | study_boundary_stage_inventory_result_report_created | visible | study_id=36;stage_id=178;inventory_id=965;result_id=35;report_bytes=6841 | - |
| 供应链碳管理 | `/carbon/supply-chain` | `page_api_write` | `write_flow_passed` | supplier_site_task_data_evidence_review_release_created | visible | supplier_id=36;site_id=36;task_id=36;data_id=35;evidence_id=1260;release_id=7 | - |
| 辅助核查 | `/carbon/verification` | `page_api_write` | `write_flow_passed` | project_attachment_export_job_created | visible | project_id=32;attachment_id=1262;general_export_job_id=18;export_status=completed | - |
| 碳资产 | `/carbon/assets` | `page_api_write` | `write_flow_passed` | period_accounts_allowance_credit_transaction_surrender_forecast_created | visible | period_id=32;quota_account_id=37;credit_account_id=38;allowance_id=8;credit_id=8;transaction_id=8;surrender_id=8;scenario_id=31 | - |

## 操作记录

### 能源消费

- 操作：使用企业资料包标准化数据导入租户 -> 访问 /energy/consumption -> 验证页面可见性与非破坏性操作
- 证据：energy_interval_facts/scope1/scope2 已由企业资料包导入；页面当前无手工录入入口

### 能源强度

- 操作：使用企业资料包标准化数据导入租户 -> 访问 /energy/intensity -> 验证页面可见性与非破坏性操作
- 证据：production_output_facts/production_products 已由企业资料包导入；页面当前无手工录入入口

### 能源分析

- 操作：使用企业资料包标准化数据导入租户 -> 访问 /energy/analysis -> 验证页面可见性与非破坏性操作
- 证据：由 energy_interval_facts 派生分析；页面当前无手工录入入口

### 能流图

- 操作：使用企业资料包标准化数据导入租户 -> 访问 /energy/flow -> 验证页面可见性与非破坏性操作
- 证据：由 energy_interval_facts 派生能流；页面当前无手工录入入口

### 碳排放核算

- 操作：进入碳排放核算 -> 补齐边界发布前置条件 -> 发布组织边界 -> 创建核算批次 -> 重建组织排放清单 -> 锁定批次 -> 核算结果 Tab 检查批次可见
- 证据：边界前置处理: created_included_facility, published_boundary; 页面可见: RV-ACC-20260613180426

### 能效对标

- 操作：进入能效对标 -> 新增标杆方案 -> 新增标杆项 -> 回到页面确认方案/对象可见
- 证据：页面可见: 写入验证标杆方案 20260613180426

### 能量平衡

- 操作：进入能量平衡 -> 执行优化测算 -> 保存优化记录 -> 切换优化记录 Tab 检查可见
- 证据：页面可见: 空压站参数优化

### 能源预算

- 操作：进入能源预算 -> 新增年度目标 -> 生成月度预算 -> 新增调整记录 -> 页面检查预算方案
- 证据：页面可见: 写入验证预算方案 20260613180426

### 产品碳足迹

- 操作：进入产品碳足迹 -> 新建研究 -> 保存边界 -> 新增阶段 -> 新增活动数据 -> 核算 -> 导出公共模板报告
- 证据：页面可见: 写入验证产品碳足迹 20260613180426

### 供应链碳管理

- 操作：进入供应链碳管理 -> 新建供应商/场站/填报任务 -> 新增数据和证据 -> 提交并审核 -> 生成披露
- 证据：页面可见: 写入验证供应商 20260613180426

### 辅助核查

- 操作：进入辅助核查 -> 新建核查项目 -> 登记证据附件 -> 生成材料包导出任务 -> 页面检查项目/附件
- 证据：页面可见: 写入验证核查项目 20260613180426

### 碳资产

- 操作：进入碳资产 -> 新建履约周期/账户/配额/信用持仓 -> 交易模拟 -> 清缴 -> 新建预测情景 -> 页面检查资产数据
- 证据：页面可见: 写入验证履约周期 20260613180426;写入验证配额账户 20260613180426
