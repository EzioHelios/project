# xm-hongtong-2025 非破坏性深度页面操作验收

测试时间：2026-06-13T22:37:33.437Z

租户：鸿通科技（厦门）有限公司（xm-hongtong-2025）

| 页面 | 路由 | 状态 | Tab | 安全操作 | 新增入口 | API失败 | 控制台错误 | 控制台样本 | 失败点 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 能源消费 | `/energy/consumption` | `deep_non_destructive_passed` | 4/4 | 2/2 | 0/0 | 0 | 0 | - | - |
| 能源强度 | `/energy/intensity` | `deep_non_destructive_passed` | 6/6 | 2/2 | 0/0 | 0 | 0 | - | - |
| 能源分析 | `/energy/analysis` | `deep_non_destructive_passed` | 5/5 | 2/2 | 0/0 | 0 | 0 | - | - |
| 能效对标 | `/energy/benchmark` | `deep_non_destructive_passed` | 5/5 | 1/1 | 0/0 | 0 | 0 | - | - |
| 能流图 | `/energy/flow` | `deep_non_destructive_passed` | 4/4 | 1/1 | 0/0 | 0 | 0 | - | - |
| 能量平衡 | `/energy/balance` | `deep_non_destructive_passed` | 4/4 | 1/1 | 0/0 | 0 | 0 | - | - |
| 能源预算 | `/energy/budget` | `deep_non_destructive_passed` | 5/5 | 1/1 | 1/1 | 0 | 0 | - | - |
| 碳核算 | `/carbon/accounting` | `deep_non_destructive_passed` | 7/7 | 0/0 | 0/0 | 0 | 0 | - | - |
| 产品碳足迹 | `/carbon/product-footprint` | `deep_non_destructive_passed` | 6/6 | 1/1 | 1/1 | 0 | 0 | - | - |
| 供应链碳管理 | `/carbon/supply-chain` | `deep_non_destructive_passed` | 5/5 | 0/0 | 2/2 | 0 | 0 | - | - |
| 辅助核查 | `/carbon/verification` | `deep_non_destructive_passed` | 7/7 | 0/0 | 0/0 | 0 | 0 | - | - |
| 碳资产 | `/carbon/assets` | `deep_non_destructive_passed` | 6/6 | 1/1 | 1/1 | 0 | 0 | - | - |

本脚本只执行非破坏性操作：切换 Tab、查询/重置/刷新、打开但不提交新增入口。涉及真实新增、导入、锁定、审批、交易模拟等写操作需单独人工确认后执行。
