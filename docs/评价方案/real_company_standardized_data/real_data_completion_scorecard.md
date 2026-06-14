# 真实数据完整录入评分表

生成时间：2026-06-13T23:52:16.355Z

## 判定口径

- 以 `overall_page_test_matrix.csv` 的 48 个企业/页面组合为输入，按企业租户独立统计，不跨企业借用数据。
- `can_count_real_complete=yes` 只表示该企业该页面具备真实来源数据，且已有页面/API 写入、导入可见或平台生成分析结果的验证证据。
- `partial_source_not_complete`、`source_missing_not_complete`、`simulation_only_not_real`、`blocked_*` 均不得计入真实数据完整录入完成。
- 能源强度、能源分析、能流图、能量平衡按平台生成/分析页面处理：真实来源已导入并驱动页面结果时，可以计入 `complete_real_generated_analysis`，但仍需在页面保留来源状态。

## 总体统计

| 桶 | 页面数 |
| --- | ---: |
| `complete_real_user_operable` | 19 |
| `complete_real_generated_analysis` | 15 |
| `partial_source_not_complete` | 9 |
| `simulation_only_not_real` | 4 |
| `complete_real_import_visible` | 1 |
| **可计入真实完整录入** | **35** |
| **总企业/页面组合** | **48** |

## 租户统计

| 企业 | 租户 | 可计入真实完整录入 | 部分来源 | 来源缺失 | 模拟 | 阻塞 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 本田金属技术(佛山)有限公司 | `fs-honda-metal-2025` | 11 | 0 | 0 | 1 | 0 |
| 宁波迈柏科技股份有限公司 | `nb-maibo-2025` | 9 | 2 | 0 | 1 | 0 |
| 鸿通科技（厦门）有限公司 | `xm-hongtong-2025` | 9 | 2 | 0 | 1 | 0 |
| 上海马陆日用友捷汽车电气有限公司 | `sh-malu-youjie-2025` | 6 | 5 | 0 | 1 | 0 |

## 页面统计

| 页面 | 可计入真实完整录入 | 部分来源 | 来源缺失 | 模拟 | 阻塞 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 能源消费 | 1 | 3 | 0 | 0 | 0 |
| 能源强度 | 3 | 1 | 0 | 0 | 0 |
| 能源分析 | 4 | 0 | 0 | 0 | 0 |
| 能效对标 | 3 | 1 | 0 | 0 | 0 |
| 能流图 | 4 | 0 | 0 | 0 | 0 |
| 能量平衡 | 4 | 0 | 0 | 0 | 0 |
| 能源预算 | 3 | 1 | 0 | 0 | 0 |
| 碳核算 | 1 | 3 | 0 | 0 | 0 |
| 产品碳足迹 | 4 | 0 | 0 | 0 | 0 |
| 供应链碳管理 | 4 | 0 | 0 | 0 | 0 |
| 辅助核查 | 4 | 0 | 0 | 0 | 0 |
| 碳资产 | 0 | 0 | 0 | 4 | 0 |

## 明细

| 企业 | 页面 | 路由 | 判定 | 计入 | 来源 | 操作 | 依据 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 宁波迈柏科技股份有限公司 | 能源消费 | /energy/consumption | `partial_source_not_complete` | no | partial_source | partial_source_import_not_page_write | 只有部分来源或口径存在缺口，不能计入真实完整录入。 |
| 宁波迈柏科技股份有限公司 | 能源强度 | /energy/intensity | `complete_real_generated_analysis` | yes | real_source_ready | source_import_visible | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 宁波迈柏科技股份有限公司 | 能源分析 | /energy/analysis | `complete_real_generated_analysis` | yes | real_source_ready | source_import_visible | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 宁波迈柏科技股份有限公司 | 能效对标 | /energy/benchmark | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 宁波迈柏科技股份有限公司 | 能流图 | /energy/flow | `complete_real_generated_analysis` | yes | real_source_ready | source_import_visible | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 宁波迈柏科技股份有限公司 | 能量平衡 | /energy/balance | `complete_real_generated_analysis` | yes | real_source_ready | generated_or_scenario_flow_passed | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 宁波迈柏科技股份有限公司 | 能源预算 | /energy/budget | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 宁波迈柏科技股份有限公司 | 碳核算 | /carbon/accounting | `partial_source_not_complete` | no | partial_source | write_flow_passed | 只有部分来源或口径存在缺口，不能计入真实完整录入。 |
| 宁波迈柏科技股份有限公司 | 产品碳足迹 | /carbon/product-footprint | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 宁波迈柏科技股份有限公司 | 供应链碳管理 | /carbon/supply-chain | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 宁波迈柏科技股份有限公司 | 辅助核查 | /carbon/verification | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 宁波迈柏科技股份有限公司 | 碳资产 | /carbon/assets | `simulation_only_not_real` | no | simulation_only | simulation_flow_passed | 资料包没有真实配额、CCER、交易或清缴来源，只能验证模拟能力。 |
| 鸿通科技（厦门）有限公司 | 能源消费 | /energy/consumption | `partial_source_not_complete` | no | partial_source | partial_source_import_not_page_write | 只有部分来源或口径存在缺口，不能计入真实完整录入。 |
| 鸿通科技（厦门）有限公司 | 能源强度 | /energy/intensity | `complete_real_generated_analysis` | yes | real_source_ready | source_import_visible | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 鸿通科技（厦门）有限公司 | 能源分析 | /energy/analysis | `complete_real_generated_analysis` | yes | real_source_ready | source_import_visible | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 鸿通科技（厦门）有限公司 | 能效对标 | /energy/benchmark | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 鸿通科技（厦门）有限公司 | 能流图 | /energy/flow | `complete_real_generated_analysis` | yes | real_source_ready | source_import_visible | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 鸿通科技（厦门）有限公司 | 能量平衡 | /energy/balance | `complete_real_generated_analysis` | yes | real_source_ready | generated_or_scenario_flow_passed | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 鸿通科技（厦门）有限公司 | 能源预算 | /energy/budget | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 鸿通科技（厦门）有限公司 | 碳核算 | /carbon/accounting | `partial_source_not_complete` | no | partial_source | write_flow_passed | 只有部分来源或口径存在缺口，不能计入真实完整录入。 |
| 鸿通科技（厦门）有限公司 | 产品碳足迹 | /carbon/product-footprint | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 鸿通科技（厦门）有限公司 | 供应链碳管理 | /carbon/supply-chain | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 鸿通科技（厦门）有限公司 | 辅助核查 | /carbon/verification | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 鸿通科技（厦门）有限公司 | 碳资产 | /carbon/assets | `simulation_only_not_real` | no | simulation_only | simulation_flow_passed | 资料包没有真实配额、CCER、交易或清缴来源，只能验证模拟能力。 |
| 上海马陆日用友捷汽车电气有限公司 | 能源消费 | /energy/consumption | `partial_source_not_complete` | no | partial_source | partial_source_import_not_page_write | 只有部分来源或口径存在缺口，不能计入真实完整录入。 |
| 上海马陆日用友捷汽车电气有限公司 | 能源强度 | /energy/intensity | `partial_source_not_complete` | no | partial_source | partial_source_import_not_page_write | 只有部分来源或口径存在缺口，不能计入真实完整录入。 |
| 上海马陆日用友捷汽车电气有限公司 | 能源分析 | /energy/analysis | `complete_real_generated_analysis` | yes | real_source_ready | source_import_visible | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 上海马陆日用友捷汽车电气有限公司 | 能效对标 | /energy/benchmark | `partial_source_not_complete` | no | partial_source | write_flow_passed | 只有部分来源或口径存在缺口，不能计入真实完整录入。 |
| 上海马陆日用友捷汽车电气有限公司 | 能流图 | /energy/flow | `complete_real_generated_analysis` | yes | real_source_ready | source_import_visible | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 上海马陆日用友捷汽车电气有限公司 | 能量平衡 | /energy/balance | `complete_real_generated_analysis` | yes | real_source_ready | generated_or_scenario_flow_passed | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 上海马陆日用友捷汽车电气有限公司 | 能源预算 | /energy/budget | `partial_source_not_complete` | no | partial_source | write_flow_passed | 只有部分来源或口径存在缺口，不能计入真实完整录入。 |
| 上海马陆日用友捷汽车电气有限公司 | 碳核算 | /carbon/accounting | `partial_source_not_complete` | no | partial_source | write_flow_passed | 只有部分来源或口径存在缺口，不能计入真实完整录入。 |
| 上海马陆日用友捷汽车电气有限公司 | 产品碳足迹 | /carbon/product-footprint | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 上海马陆日用友捷汽车电气有限公司 | 供应链碳管理 | /carbon/supply-chain | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 上海马陆日用友捷汽车电气有限公司 | 辅助核查 | /carbon/verification | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 上海马陆日用友捷汽车电气有限公司 | 碳资产 | /carbon/assets | `simulation_only_not_real` | no | simulation_only | simulation_flow_passed | 资料包没有真实配额、CCER、交易或清缴来源，只能验证模拟能力。 |
| 本田金属技术(佛山)有限公司 | 能源消费 | /energy/consumption | `complete_real_import_visible` | yes | real_source_ready | source_import_visible | 真实来源数据已通过页面导入或资料包导入覆盖，页面可见；该页暂无独立手工录入动作。 |
| 本田金属技术(佛山)有限公司 | 能源强度 | /energy/intensity | `complete_real_generated_analysis` | yes | real_source_ready | source_import_visible | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 本田金属技术(佛山)有限公司 | 能源分析 | /energy/analysis | `complete_real_generated_analysis` | yes | real_source_ready | source_import_visible | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 本田金属技术(佛山)有限公司 | 能效对标 | /energy/benchmark | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 本田金属技术(佛山)有限公司 | 能流图 | /energy/flow | `complete_real_generated_analysis` | yes | real_source_ready | source_import_visible | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 本田金属技术(佛山)有限公司 | 能量平衡 | /energy/balance | `complete_real_generated_analysis` | yes | real_source_ready | generated_or_scenario_flow_passed | 该页为平台生成/分析页面，真实来源数据已导入并可驱动页面结果。 |
| 本田金属技术(佛山)有限公司 | 能源预算 | /energy/budget | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 本田金属技术(佛山)有限公司 | 碳核算 | /carbon/accounting | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 本田金属技术(佛山)有限公司 | 产品碳足迹 | /carbon/product-footprint | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 本田金属技术(佛山)有限公司 | 供应链碳管理 | /carbon/supply-chain | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 本田金属技术(佛山)有限公司 | 辅助核查 | /carbon/verification | `complete_real_user_operable` | yes | real_source_ready | write_flow_passed | 具备真实来源数据，且页面/API 已验证关键业务写入或导出闭环。 |
| 本田金属技术(佛山)有限公司 | 碳资产 | /carbon/assets | `simulation_only_not_real` | no | simulation_only | simulation_flow_passed | 资料包没有真实配额、CCER、交易或清缴来源，只能验证模拟能力。 |
