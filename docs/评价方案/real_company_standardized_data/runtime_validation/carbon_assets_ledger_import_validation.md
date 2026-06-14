# 碳资产真实台账页面导入验证

运行时间：2026-06-13T22:06:22.249Z

| 企业 | 租户 | 状态 | 入库 | 跳过 | 错误下载 | API | 可追溯台账 | 证据 |
| --- | --- | --- | ---: | ---: | --- | --- | ---: | --- |
| honda | fs-honda-metal-2025 | ledger_import_passed | 7 | 1 | error_download_passed | simulation_only | 0 | 页面台账导入 7 行、错误 1 行；错误行 CSV 可下载；来源为 real-company-write-validation，不计入真实资产台账。 |

操作方式：登录平台，切换本田租户，访问 `/carbon/assets` 的“台账导入”Tab，粘贴标准 CSV，执行导入并下载错误行。
