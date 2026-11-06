# 祥泰报告正文同步与客户导出验证

日期：2026-10-14。环境：warehouse.nexlca.com，Huawei `/root/warehouse`。

## 问题与处理

上轮发布更新了程序和报告模板，但未将本地维护的报告正文写入生产数据库。生产草稿的 `content_snapshot.narrative` 为空。

本轮仅同步已核实正文并追加客户导出权限，不发布新镜像、不重算、不修改能源事实、活动数据或因子。

| 项目 | 本地已确认记录 | 线上目标记录 |
| --- | --- | --- |
| 报告 | RPT-1069-2082 v1 | RPT-7-11 v1 |
| 主体 | 祥泰仓库 / XIANGTAI-METERED | 同左 |
| 盘查任务 | XIANGTAI-METER-2025 | 同左 |
| 报告期间 | 2025-07-01 至 2025-12-31 | 同左 |
| 状态 | 草稿 | 保持草稿 |
| 活动数量 | 60条、10个设备 | 同左 |
| 用电量 | 31,380.66 kWh | 同左 |
| 排放量 | 18,285.510582 kgCO2e | 同左 |

逐字同步8项正文：编制目的、预期使用者、边界确定、监测方法、缺失数据处理、质量管理、不确定性评价、结果分析。编制负责人、基准年政策、减排措施未填写；正文中的资料缺口保留【待补充】。未复制本地企业档案，未向2026年报告套用2025年文字。

使用既有 `UpdateInventoryReport` 用例，权限追加与正文更新在同一事务中提交。祥泰156条活动数据、156条核算结果及另一份报告的前后指纹一致。

## 权限

`taizhou` 仍为非超级管理员，仅加入安方中心库、祥泰仓库，均为普通成员。既有角色 `warehouse_customer_viewer` 经核对仅分配给该账号，在原 `carbon.inventory.view` 基础上仅增加 `carbon.inventory.export`。未赋予报告编辑、审核或发布权限，未更改密码。

## 验证

- 内置浏览器重新登录 taizhou，切换祥泰，查看正文并点击“导出 Word”，页面显示“Word报告已导出”。
- 实际浏览器下载文件：`.storage/xiangtai-narrative-sync-20261014/xiangtai-2025-customer-download.docx`。
- 文件SHA256：`f59c8c9e86fa3708149c5ef01d0f2ade66d544abe56ee5095a342c6c4b8f62be`。
- 8项正文与本地确认稿完全一致；主体、期间、草稿状态、31,380.66 kWh、18.2855 tCO2e和0.5827因子通过内容断言。
- 设备月度汇总为10个设备、6个月；未出现内部报告/活动/核算编码及参数与活动记录对应表。
- 原生 soffice 将实际下载文件渲染为10页A4，检查正文、图表、附表和分页；保留缺失资料标记。
- 客户账号HTTP验证：安方、祥泰Word导出均200；两个租户报告编辑均403；在祥泰上下文导出安方报告返回404；账号可见租户仍仅两个。
- 已知现状：客户报告列表仍显示编辑/提交等按钮，但后端编辑权限校验拒绝，本轮未修改前端按钮显隐。

## 备份与证据

生产变更前备份、来源提取和执行日志保存在 `/root/warehouse/backups/xiangtai-narrative-sync-20261014/`，目录权限700。回退仅应恢复目标报告原正文快照并移除本次新增角色权限，不回滚其他业务数据。

本地验证目录：`.storage/xiangtai-narrative-sync-20261014/`。

- `production-before.log` / `production-after.log`：目标报告及账号权限前后快照。
- `apply.log`：变更范围与数据指纹对比。
- `http-verification.json`：客户账号权限与下载结果。
- `download-qa.json`：实际下载文件内容及分页检查。
- `xiangtai-2025-customer-download.pdf`、`page-*.png`、`render-overview.png`：soffice渲染结果。
- `customer-export-success.png`、`narrative-online.png`：线上浏览器证据。
