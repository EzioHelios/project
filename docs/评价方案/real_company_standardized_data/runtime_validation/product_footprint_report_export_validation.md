# 产品碳足迹公共报告导出验证

运行时间：2026-06-14T00:16:16.246Z

摘要：导出成功 4，失败 0。

| 企业 | 租户 | 状态 | 研究 | 下载 | ZIP文件数 | 必需文件 | Manifest | 上下文 | 清单CSV | 文件 |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| honda | fs-honda-metal-2025 | product_footprint_report_exported | PCF-HONDA-2025 | downloaded_zip | 7 | required_entries_present | manifest_valid | report_context_matches_study | inventory_csv_contains_rows | docs/评价方案/real_company_standardized_data/runtime_validation/product_footprint_report_exports/fs-honda-metal-2025/pcf-report-PCF-HONDA-2025-20260614001604.zip |
| hongtong | xm-hongtong-2025 | product_footprint_report_exported | PCF-HONGTONG-2025 | downloaded_zip | 7 | required_entries_present | manifest_valid | report_context_matches_study | inventory_csv_contains_rows | docs/评价方案/real_company_standardized_data/runtime_validation/product_footprint_report_exports/xm-hongtong-2025/pcf-report-PCF-HONGTONG-2025-20260614001609.zip |
| malu | sh-malu-youjie-2025 | product_footprint_report_exported | PCF-MALU-2025 | downloaded_zip | 7 | required_entries_present | manifest_valid | report_context_matches_study | inventory_csv_contains_rows | docs/评价方案/real_company_standardized_data/runtime_validation/product_footprint_report_exports/sh-malu-youjie-2025/pcf-report-PCF-MALU-2025-20260614001612.zip |
| maibo | nb-maibo-2025 | product_footprint_report_exported | PCF-MAIBO-2025 | downloaded_zip | 7 | required_entries_present | manifest_valid | report_context_matches_study | inventory_csv_contains_rows | docs/评价方案/real_company_standardized_data/runtime_validation/product_footprint_report_exports/nb-maibo-2025/pcf-report-PCF-MAIBO-2025-20260614001616.zip |

## 验证口径

- 从 `/carbon/product-footprint` 页面进入“报告生成”Tab 并点击“导出报告”。
- 下载 ZIP 后检查 `report/product-footprint-report.docx`、`report/report-context.json`、`data/inventory-items.csv`、`data/stage-summary.csv`、`quality/quality-summary.json` 和 `manifest.json`。
- `manifest.json` 必须声明 `product_footprint_internal_report` 模板，且 report-context 中的研究编号必须与当前租户研究一致。

