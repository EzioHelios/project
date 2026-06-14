# 企业资料包导入入口验证

生成时间: 2026-06-14T00:04:41.829955+00:00

## 校验范围

- 后端整包导入 API 是否注册。
- 四个固定标准化企业子包是否可读取摘要。
- `/energy/consumption` 数据导入 Tab 是否包含整包导入选择、试运行、正式导入和结果区。

## 明细

| 范围 | 项 | 状态 | 说明 |
| --- | --- | --- | --- |
| backend_route | /api/carbon/real-company-packages | `ok` | registered |
| backend_route | /api/carbon/real-company-packages/{enterprise_code:str}/import | `ok` | registered |
| package_summary | package_count | `ok` | actual=honda,hongtong,maibo,malu; expected=honda,hongtong,maibo,malu |
| package_summary | honda | `ok` | tenant=fs-honda-metal-2025; ready=11; partial=0; simulation=1; missing=- |
| package_summary | hongtong | `ok` | tenant=xm-hongtong-2025; ready=9; partial=2; simulation=1; missing=scope1_stationary_combustion |
| package_summary | maibo | `ok` | tenant=nb-maibo-2025; ready=9; partial=2; simulation=1; missing=scope1_stationary_combustion |
| package_summary | malu | `ok` | tenant=sh-malu-youjie-2025; ready=6; partial=5; simulation=1; missing=production_output_facts;scope1_stationary_combustion |
| frontend_entrypoint | real-company-package-dry-run | `ok` | src/js/web/src/components/carbon/energy-guide-pages.tsx |
| frontend_entrypoint | real-company-package-import | `ok` | src/js/web/src/components/carbon/energy-guide-pages.tsx |
| frontend_entrypoint | real-company-package-import-result | `ok` | src/js/web/src/components/carbon/energy-guide-pages.tsx |
| frontend_entrypoint | real-company-package-select | `ok` | src/js/web/src/components/carbon/energy-guide-pages.tsx |
