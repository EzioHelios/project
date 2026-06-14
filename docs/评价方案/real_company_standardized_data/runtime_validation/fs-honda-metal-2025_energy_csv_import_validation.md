# 本田金属技术(佛山)有限公司 能源 CSV 页面导入验证

运行时间：2026-06-13T20:12:22.105Z

| 企业 | 租户 | 数据集 | 状态 | UI | API | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| honda | fs-honda-metal-2025 | Scope2 电力账单 | page_csv_import_passed | imported_visible:导入结果 接收 1 行 入库 1 行 跳过 0 行 | energy_consumption_fact_visible | energy consumption query returned 1 rows for imp-s2-13201216 |
| honda | fs-honda-metal-2025 | Scope1 固定燃烧 | page_csv_import_passed | imported_visible:导入结果 接收 1 行 入库 1 行 跳过 0 行 | energy_consumption_fact_visible | energy consumption query returned 1 rows for imp-s1-13201216 |
| honda | fs-honda-metal-2025 | 能源计量事实 | page_csv_import_passed | imported_visible:导入结果 接收 1 行 入库 1 行 跳过 0 行 | energy_analysis_summary_updated | energy analysis total_energy=22053.48 for 2025-01-01~2025-01-31 |
| honda | fs-honda-metal-2025 | 产量分母事实 | page_csv_import_passed | imported_visible:导入结果 接收 1 行 入库 1 行 跳过 0 行 | production_output_fact_visible | production output query returned 1 rows for ui-import:20260613201216:honda:production_output_facts |
