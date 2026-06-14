# 上海马陆日用友捷汽车电气有限公司 能源 CSV 页面导入验证

运行时间：2026-06-13T20:12:30.506Z

| 企业 | 租户 | 数据集 | 状态 | UI | API | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| malu | sh-malu-youjie-2025 | Scope2 电力账单 | page_csv_import_passed | imported_visible:导入结果 接收 1 行 入库 1 行 跳过 0 行 | energy_consumption_fact_visible | energy consumption query returned 3 rows for imp-s2-13201216 |
| malu | sh-malu-youjie-2025 | Scope1 固定燃烧 | source_missing | not_applicable_source_missing | not_applicable_source_missing | 企业子包未提供 scope1_stationary_combustion.csv 或无可导入行 |
| malu | sh-malu-youjie-2025 | 能源计量事实 | source_missing | not_applicable_source_missing | not_applicable_source_missing | 企业子包未提供 energy_interval_facts.csv 或无可导入行 |
| malu | sh-malu-youjie-2025 | 产量分母事实 | source_missing | not_applicable_source_missing | not_applicable_source_missing | 企业子包未提供 production_output_facts.csv 或无可导入行 |
