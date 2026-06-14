# 产品碳足迹与供应链来源状态运行验证

运行时间：2026-06-13T20:37:28.225Z

| 企业 | 租户 | 页面 | 状态 | API | UI | 企业来源 | 验证写入 | 业务记录 | 主记录 | 证据 |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| honda | fs-honda-metal-2025 | 产品碳足迹 | source_readiness_passed | real_source_with_validation_writes | source_status_visible | 13 | 20 | 52 | 16 | panel=true; statusLabel=真实来源; primary=inventory_item_count:16; writes=20 |
| honda | fs-honda-metal-2025 | 供应链碳管理 | source_readiness_passed | real_source_with_validation_writes | source_status_visible | 25 | 32 | 65 | 7 | panel=true; statusLabel=真实来源; primary=data_count:7; writes=32 |
| hongtong | xm-hongtong-2025 | 产品碳足迹 | source_readiness_passed | real_source_with_validation_writes | source_status_visible | 30 | 3 | 41 | 28 | panel=true; statusLabel=真实来源; primary=inventory_item_count:28; writes=3 |
| hongtong | xm-hongtong-2025 | 供应链碳管理 | source_readiness_passed | real_source_with_validation_writes | source_status_visible | 34 | 5 | 41 | 2 | panel=true; statusLabel=真实来源; primary=data_count:2; writes=5 |
| malu | sh-malu-youjie-2025 | 产品碳足迹 | source_readiness_passed | real_source_with_validation_writes | source_status_visible | 21 | 3 | 32 | 19 | panel=true; statusLabel=真实来源; primary=inventory_item_count:19; writes=3 |
| malu | sh-malu-youjie-2025 | 供应链碳管理 | source_readiness_passed | real_source_with_validation_writes | source_status_visible | 17 | 5 | 24 | 2 | panel=true; statusLabel=真实来源; primary=data_count:2; writes=5 |
| maibo | nb-maibo-2025 | 产品碳足迹 | source_readiness_passed | real_source_with_validation_writes | source_status_visible | 43 | 6 | 59 | 42 | panel=true; statusLabel=真实来源; primary=inventory_item_count:42; writes=6 |
| maibo | nb-maibo-2025 | 供应链碳管理 | source_readiness_passed | real_source_with_validation_writes | source_status_visible | 169 | 10 | 182 | 3 | panel=true; statusLabel=真实来源; primary=data_count:3; writes=10 |

操作方式：登录平台，切换对应租户，分别访问 `/carbon/product-footprint` 和 `/carbon/supply-chain`，检查“来源状态”“企业来源记录”“验证写入记录”和核心业务记录数。
