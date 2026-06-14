# 四租户碳资产来源状态运行验证

运行时间：2026-06-13T22:06:55.656Z

| 企业 | 租户 | 状态 | API | UI | 模板 | 可追溯台账 | 模拟种子 | 未追溯记录 | 资产台账 | 证据 |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| honda | fs-honda-metal-2025 | source_readiness_passed | simulation_only | source_status_visible | template_downloaded | 0 | 3 | 24 | 32 | panel=true; statusLabel=模拟来源; traceable=0; seeds=3; unverified=24; template=template_downloaded |
| hongtong | xm-hongtong-2025 | source_readiness_passed | simulation_only | source_status_visible | template_downloaded | 0 | 3 | 3 | 4 | panel=true; statusLabel=模拟来源; traceable=0; seeds=3; unverified=3; template=template_downloaded |
| malu | sh-malu-youjie-2025 | source_readiness_passed | simulation_only | source_status_visible | template_downloaded | 0 | 3 | 3 | 4 | panel=true; statusLabel=模拟来源; traceable=0; seeds=3; unverified=3; template=template_downloaded |
| maibo | nb-maibo-2025 | source_readiness_passed | simulation_only | source_status_visible | template_downloaded | 0 | 3 | 6 | 8 | panel=true; statusLabel=模拟来源; traceable=0; seeds=3; unverified=6; template=template_downloaded |

操作方式：登录平台，切换对应租户，访问 `/carbon/assets`，检查“资产来源”状态、可追溯台账、模拟种子、未追溯记录和资产台账数量，并下载真实资产台账模板校验字段。
