# 企业端录入可操作性与复杂度评估

生成时间：2026-06-13T23:52:16.424Z

## 判定口径

- 输入来自 `overall_page_test_matrix.csv`，按企业/租户/页面组合统计。
- `can_enterprise_complete_now=yes` 表示当前页面或统一导入入口已经能让企业用户完成主要真实数据闭环。
- `partial` 表示页面可操作或来源可见，但企业资料包缺数据或口径不完整，不能计入真实完整录入。
- `no` 表示源缺失、缺计算结果、纯模拟或平台正确阻断。
- 平台生成的分析页允许通过统一能源导入入口完成底层数据录入，但业务页面必须显示真实来源状态。

## 总体统计

| 操作模式 | 企业/页面组合 |
| --- | ---: |
| `page_direct_business_flow` | 23 |
| `central_import_then_page_analysis` | 11 |
| `partial_source_page_flow` | 5 |
| `simulation_only` | 4 |
| `partial_source_import_visible` | 2 |
| `partial_source_page_csv_import` | 2 |
| `page_direct_csv_import` | 1 |

| 企业操作复杂度 | 企业/页面组合 |
| --- | ---: |
| `medium` | 44 |
| `high` | 4 |
| **当前可由企业完成** | **35** |
| **部分可操作但不可计入完整** | **9** |
| **当前不可完成** | **4** |

## 租户视角

| 企业 | 租户 | 可完成 | 部分 | 不可完成 | 高复杂度 | 阻塞 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 本田金属技术(佛山)有限公司 | `fs-honda-metal-2025` | 11 | 0 | 1 | 1 | 0 |
| 宁波迈柏科技股份有限公司 | `nb-maibo-2025` | 9 | 2 | 1 | 1 | 0 |
| 鸿通科技（厦门）有限公司 | `xm-hongtong-2025` | 9 | 2 | 1 | 1 | 0 |
| 上海马陆日用友捷汽车电气有限公司 | `sh-malu-youjie-2025` | 6 | 5 | 1 | 1 | 0 |

## 页面视角

| 页面 | 路由 | 入口方式 | 复杂度 | 可完成 | 部分 | 不可完成 | 主要简化动作 |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| 能源消费 | `/energy/consumption` | 页面直接导入 | `L3` | 1 | 3 | 0 | 把能源导入模板、错误行下载和导入批次追溯继续沉淀成统一向导。 |
| 能源强度 | `/energy/intensity` | 统一能源导入后分析 | `L2` | 3 | 1 | 0 | 来源状态面板显示缺失数据集，并可跳转到统一能源导入模板下载。 |
| 能源分析 | `/energy/analysis` | 统一能源导入后分析 | `L2` | 4 | 0 | 0 | 缺能源事实时通过来源状态面板跳转到统一能源导入模板下载。 |
| 能效对标 | `/energy/benchmark` | 页面写入 | `L3` | 3 | 1 | 0 | 对无能源/产量来源的租户，新增前提示只能做流程验证，不能形成真实对标结论。 |
| 能流图 | `/energy/flow` | 统一能源导入后分析 | `L2` | 4 | 0 | 0 | 缺计量层级时显示降级路径，并引导补区域/设备层级数据。 |
| 能量平衡 | `/energy/balance` | 页面写入 + 分析 | `L3` | 4 | 0 | 0 | 把模拟记录和真实能源事实驱动结果在表格中继续显式区分。 |
| 能源预算 | `/energy/budget` | 页面写入 | `L3` | 3 | 1 | 0 | 缺历史能源或产量时，预算生成前提示缺失基线，不让用户误认为是真实预测。 |
| 碳核算 | `/carbon/accounting` | 页面业务闭环 | `L3` | 1 | 3 | 0 | 对缺 Scope 来源或缺 CO2e 结果的租户，提供待补数据下载、补录模板和补录导入校验。 |
| 产品碳足迹 | `/carbon/product-footprint` | 页面业务闭环 | `L3` | 4 | 0 | 0 | 保留企业来源和验证写入分列统计，避免测试写入污染企业来源判断。 |
| 供应链碳管理 | `/carbon/supply-chain` | 页面业务闭环 | `L3` | 4 | 0 | 0 | 披露/发布动作增加明确确认，避免供应商 PCF 被误混入组织 Scope3。 |
| 辅助核查 | `/carbon/verification` | 页面导出闭环 | `L3` | 4 | 0 | 0 | 大材料包下载增加大小、进度、重试和过期策略提示。 |
| 碳资产 | `/carbon/assets` | 页面导入 + 模拟写入 | `L3` | 0 | 0 | 4 | 已提供真实资产台账模板下载和页面导入入口；补真实配额、CCER、交易、清缴台账后再进入真实决策验收。 |

## 明细

| 企业 | 页面 | 来源 | 操作模式 | 可完成 | 复杂度 | 缺口/阻塞 |
| --- | --- | --- | --- | --- | --- | --- |
| 宁波迈柏科技股份有限公司 | 能源消费 | `partial_source` | `partial_source_import_visible` | partial | `medium` | 缺少数据集: scope1_stationary_combustion |
| 宁波迈柏科技股份有限公司 | 能源强度 | `real_source_ready` | `central_import_then_page_analysis` | yes | `medium` | 需要先经统一能源导入入口写入底层数据。 |
| 宁波迈柏科技股份有限公司 | 能源分析 | `real_source_ready` | `central_import_then_page_analysis` | yes | `medium` | 需要先经统一能源导入入口写入底层数据。 |
| 宁波迈柏科技股份有限公司 | 能效对标 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 宁波迈柏科技股份有限公司 | 能流图 | `real_source_ready` | `central_import_then_page_analysis` | yes | `medium` | 需要先经统一能源导入入口写入底层数据。 |
| 宁波迈柏科技股份有限公司 | 能量平衡 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 宁波迈柏科技股份有限公司 | 能源预算 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 宁波迈柏科技股份有限公司 | 碳核算 | `partial_source` | `partial_source_page_flow` | partial | `medium` | 缺少数据集: scope1_stationary_combustion |
| 宁波迈柏科技股份有限公司 | 产品碳足迹 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 宁波迈柏科技股份有限公司 | 供应链碳管理 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 宁波迈柏科技股份有限公司 | 辅助核查 | `real_source_ready` | `page_direct_business_flow` | yes | `high` | - |
| 宁波迈柏科技股份有限公司 | 碳资产 | `simulation_only` | `simulation_only` | no | `medium` | 当前资料包没有真实碳资产台账，只能验证模拟流程；页面已提供真实台账模板下载和 CSV 导入入口。 |
| 鸿通科技（厦门）有限公司 | 能源消费 | `partial_source` | `partial_source_page_csv_import` | partial | `medium` | 缺少数据集: scope1_stationary_combustion |
| 鸿通科技（厦门）有限公司 | 能源强度 | `real_source_ready` | `central_import_then_page_analysis` | yes | `medium` | 需要先经统一能源导入入口写入底层数据。 |
| 鸿通科技（厦门）有限公司 | 能源分析 | `real_source_ready` | `central_import_then_page_analysis` | yes | `medium` | 需要先经统一能源导入入口写入底层数据。 |
| 鸿通科技（厦门）有限公司 | 能效对标 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 鸿通科技（厦门）有限公司 | 能流图 | `real_source_ready` | `central_import_then_page_analysis` | yes | `medium` | 需要先经统一能源导入入口写入底层数据。 |
| 鸿通科技（厦门）有限公司 | 能量平衡 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 鸿通科技（厦门）有限公司 | 能源预算 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 鸿通科技（厦门）有限公司 | 碳核算 | `partial_source` | `partial_source_page_flow` | partial | `medium` | 缺少数据集: scope1_stationary_combustion |
| 鸿通科技（厦门）有限公司 | 产品碳足迹 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 鸿通科技（厦门）有限公司 | 供应链碳管理 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 鸿通科技（厦门）有限公司 | 辅助核查 | `real_source_ready` | `page_direct_business_flow` | yes | `high` | - |
| 鸿通科技（厦门）有限公司 | 碳资产 | `simulation_only` | `simulation_only` | no | `medium` | 当前资料包没有真实碳资产台账，只能验证模拟流程；页面已提供真实台账模板下载和 CSV 导入入口。 |
| 上海马陆日用友捷汽车电气有限公司 | 能源消费 | `partial_source` | `partial_source_page_csv_import` | partial | `medium` | 缺少数据集: scope1_stationary_combustion |
| 上海马陆日用友捷汽车电气有限公司 | 能源强度 | `partial_source` | `partial_source_import_visible` | partial | `medium` | 缺少数据集: production_output_facts |
| 上海马陆日用友捷汽车电气有限公司 | 能源分析 | `real_source_ready` | `central_import_then_page_analysis` | yes | `medium` | 需要先经统一能源导入入口写入底层数据。 |
| 上海马陆日用友捷汽车电气有限公司 | 能效对标 | `partial_source` | `partial_source_page_flow` | partial | `medium` | 缺少数据集: production_output_facts |
| 上海马陆日用友捷汽车电气有限公司 | 能流图 | `real_source_ready` | `central_import_then_page_analysis` | yes | `medium` | 需要先经统一能源导入入口写入底层数据。 |
| 上海马陆日用友捷汽车电气有限公司 | 能量平衡 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 上海马陆日用友捷汽车电气有限公司 | 能源预算 | `partial_source` | `partial_source_page_flow` | partial | `medium` | 缺少数据集: production_output_facts |
| 上海马陆日用友捷汽车电气有限公司 | 碳核算 | `partial_source` | `partial_source_page_flow` | partial | `medium` | 缺少数据集: scope1_stationary_combustion |
| 上海马陆日用友捷汽车电气有限公司 | 产品碳足迹 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 上海马陆日用友捷汽车电气有限公司 | 供应链碳管理 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 上海马陆日用友捷汽车电气有限公司 | 辅助核查 | `real_source_ready` | `page_direct_business_flow` | yes | `high` | - |
| 上海马陆日用友捷汽车电气有限公司 | 碳资产 | `simulation_only` | `simulation_only` | no | `medium` | 当前资料包没有真实碳资产台账，只能验证模拟流程；页面已提供真实台账模板下载和 CSV 导入入口。 |
| 本田金属技术(佛山)有限公司 | 能源消费 | `real_source_ready` | `page_direct_csv_import` | yes | `medium` | 能源 CSV 页面导入已验证，成功行可在下游 API 可见。 |
| 本田金属技术(佛山)有限公司 | 能源强度 | `real_source_ready` | `central_import_then_page_analysis` | yes | `medium` | 需要先经统一能源导入入口写入底层数据。 |
| 本田金属技术(佛山)有限公司 | 能源分析 | `real_source_ready` | `central_import_then_page_analysis` | yes | `medium` | 需要先经统一能源导入入口写入底层数据。 |
| 本田金属技术(佛山)有限公司 | 能效对标 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 本田金属技术(佛山)有限公司 | 能流图 | `real_source_ready` | `central_import_then_page_analysis` | yes | `medium` | 需要先经统一能源导入入口写入底层数据。 |
| 本田金属技术(佛山)有限公司 | 能量平衡 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 本田金属技术(佛山)有限公司 | 能源预算 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 本田金属技术(佛山)有限公司 | 碳核算 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 本田金属技术(佛山)有限公司 | 产品碳足迹 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 本田金属技术(佛山)有限公司 | 供应链碳管理 | `real_source_ready` | `page_direct_business_flow` | yes | `medium` | - |
| 本田金属技术(佛山)有限公司 | 辅助核查 | `real_source_ready` | `page_direct_business_flow` | yes | `high` | - |
| 本田金属技术(佛山)有限公司 | 碳资产 | `simulation_only` | `simulation_only` | no | `medium` | 当前资料包没有真实碳资产台账，只能验证模拟流程；页面已提供真实台账模板下载和 CSV 导入入口。 |

