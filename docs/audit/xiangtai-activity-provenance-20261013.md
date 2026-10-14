# 祥泰67条组织碳活动记录来源核验

后续状态：用户授权后的67条删除及6条派生汇总退役已完成，见[清理记录](xiangtai-demo-cleanup-20261013.md)。本文保留删除前的来源核验结论。

核验日期：2026-10-13。范围：线上读取快照、用户提供的旧系统 SQL、当前仓库 Git 历史及迁移代码。本轮只读核验，未修改线上数据库，未恢复或执行 SQL，未执行历史演示脚本。

## 结论

线上快照中的67条祥泰组织碳活动记录，全部匹配本平台开发期间的两批演示生成代码，不是用户提供的 `db_xtck_20260407.sql` 中的原始仓库活动记录，也不是由其中电表读数计算出来的活动量。

这不代表祥泰没有历史数据。SQL 中存在电表采样、设备、区域、通勤及出入库记录，必须与后来生成的演示碳活动区分。

核验使用 `.storage/warehouse-ghg-20261013/before.json` 中 `xiangtai.GhgActivityRecord` 的67条记录；这是本次线上排查已取得的快照，不代表持续监控线上新增记录。

## 1. 两批生成记录

| 来源 | 对应代码提交 | 活动期间 | 数量 | 组成 |
| --- | --- | --- | ---: | --- |
| `demo_seed` | `d5d1dd303f2aa272c62430db78ff3b665acdb474`，2026-05-16 | 2025年7至12月 | 30 | 移动燃烧、固定燃烧、制冷剂、废弃物、运输各6条 |
| `carbon_mvp_seed` | `020b51be77247f4523fef281ad82e6db1e0e2869`，2026-06-13 | 2026年1至6月 | 37 | 移动燃烧、固定燃烧、购电、蒸汽、废弃物、运输各6条，制冷剂1条 |

提交日期是代码版本日期，不作为生产环境执行日期的证明。

可复核的历史代码：

```sh
git show d5d1dd30:src/py/app/domain/carbon/controllers.py
git show 020b51be:src/py/app/domain/carbon/mvp_data_importer.py
git show 020b51be:src/py/app/lib/tenancy.py
```

第一批位于 `_seed_demo_scope_records`，历史文件第2555行起。第二批位于 `_seed_scope_records`。独立重现公式并与线上快照逐条比较，67/67均匹配，无遗漏、无重复匹配。

比较内容包括来源类别、活动日期及结束日、活动量、单位、名称、代码（原脚本定义时）及燃料、里程、工时、运距、载重、供应方等关键参数。

具体例子：

| 线上记录 | 实际值 | 生成依据 |
| --- | --- | --- |
| `LEGACY-ELECTRICITY-19`，2026年1月购电 | 47,350 kWh | `45500 + 1 × 1850`；脚本指定表号 `MVP-ELEC-001` |
| `LEGACY-ELECTRICITY-24`，2026年6月购电 | 56,600 kWh | `45500 + 6 × 1850` |
| `LEGACY-MOBILE-2`，2025年7月园区叉车 | 118.5 L | `118.5 + 0 × 9`；脚本指定 `FK-01` |
| `LEGACY-TRANSPORT-1`，2025年7月运输 | 4,147 tkm | `(286 + 0 × 12) × (14.5 + 0 / 2)` |
| `LEGACY-TRANSPORT-30`，2026年6月运输 | 2,640 tkm | `(98 + 6 × 2) × (18 + 6)` |

第一批读取能源数据的最新月份用于选择演示月份，但活动量仍由固定公式生成，并非能源事实推导。不能因期间与历史能源数据接近就认定真实。

## 2. 为什么出现在祥泰，并显示为历史迁移

第二批脚本明确使用 `DEFAULT_TENANT_ID` 写入，值为 `00000000-0000-7000-8000-000000000001`，与当前祥泰租户一致。它还开启租户绕过，并将样例设为 `manual`、`monthly_statement`、`approved`。这些状态是程序赋值，不是企业人工填报或实际审核的证据。

随后，[组织碳迁移脚本](../../src/py/app/db/migrations/versions/2026_08_22_add_canonical_ghg_inventory_b1c2d3e4f6a.py) 的 `_migrate_legacy_activities` 将本平台既有 `dataapp_scope*` 表搬入 `ghg_activity_record`：

1. 保留原始活动量及含演示标记的备注。
2. 使用 `LEGACY-*` 编码和 `legacy_migration` 来源标签。
3. 未排除演示记录。

这里的“旧表”指本平台早期业务表，不等于原仓储项目 SQL。演示生成、默认租户写入、未区分来源的迁移共同造成当前混淆。

部分运输记录的创建日期由演示脚本直接设为活动发生日期，也不能根据早期 `created_at` 判断为真实历史记录。脚本中的 `/demo/...pdf` 附件路径同样不是原始票据证据。

可以确认生成程序及迁移路径；仅凭现有证据不能确定当时由谁或哪个部署任务执行，也不能凭 Git 作者字段判断是人手写还是 AI 编写。

## 3. SQL 中实际保存的历史记录

文件：`/Users/eziohelios/Dev/xtck/db_xtck_20260407.sql`。

SHA-256：`d120cb53e46a78d5d52fa0ab1362861f5f77508dd9761710c493dcf7ae61b94f`。

通过流式解析 PostgreSQL COPY 数据段计数，未导入数据库，未输出账户、人员姓名或摄像头凭据。

| 资料 | 数据表 | 行数 | COPY起始行 |
| --- | --- | ---: | ---: |
| 电表采样 | `dataapp_ammeterindexvalue` | 1,291,536 | 7125 |
| 设备 | `dataapp_monitorequipment` | 20 | 1302538 |
| 区域 | `dataapp_monitorsector` | 17 | 1302566 |
| 区域图片关联 | `dataapp_monitorsectorphoto` | 20 | 1302591 |
| 员工通勤 | `dataapp_employeecommute` | 44 | 1298744 |
| 入库台账 | `dataapp_inmoney` | 3,716 | 1298814 |
| 出库台账 | `dataapp_outmoney` | 24,418 | 1302619 |
| 泰州本部入库单 | `泰州本部入库单` | 494 | 1373369 |
| 泰州本部出库单 | `泰州本部出库单` | 6,806 | 1373871 |
| 告警 | `dataapp_alarmevent` | 4,623 | 2494 |

电表采样包含20个电表编号，`reading_time` 原始时间范围为 `2023-03-21 16:15:00+00` 至 `2025-12-17 03:00:00+00`。来源码0有1,191,736条，来源码1有99,800条；旧项目 `dataapp/models.py:208` 分别标注为“云集”“红外”。

SQL 没有这67条活动所依赖的 `dataapp_scope1*`、`dataapp_scope2*`、`dataapp_scope3*` 表，也没有 `ghg_activity_record` 表；全文未发现 `[demo_seed]`、`[carbon_mvp_seed]` 或 `MVP-ELEC-001`。

以上证明这些记录存在于用户提供的旧系统备份，不是对每条历史采集值的现场真实性、准确性或计量覆盖率作背书。出入库的不同表可能重叠，且“泰州本部”不能未经映射直接归属祥泰，不能把表行数相加当成独立业务总量。通勤表没有报告期字段，不能未经核定扩算年度活动。

## 4. 对后续核算的影响

- 67条演示活动不能作为祥泰正式排放核算依据；更换正式因子也不能改变其活动量来源。
- 历史电表记录可用于逐表、逐区域能源归集。是否可作为组织购电量，还需确认计量边界，不可直接合计所有表。详见[已完成的计量边界核验](xiangtai-metering-boundary-20261012.md)。
- 通勤、出入库资料应先核定期间、仓库归属及业务字段；出入库金额或数量不能直接代替运输运距、燃油量等活动量。
- 建议下一步先备份并隔离这67条演示记录及关联样例，保留审计记录，再用已核实的历史事实生成正式活动。本轮没有执行隔离、删除或重新核算。

## 5. 可复核产物

- 核验脚本：`.storage/warehouse-ghg-provenance-20261013/audit.py`
- 汇总：`.storage/warehouse-ghg-provenance-20261013/summary.json`
- 全部67条逐条比较：`.storage/warehouse-ghg-provenance-20261013/activity-comparison.csv`
- 线上快照SHA-256：`17513ceabfb65128e7354bd088add9de813349152b49f6d3091b4839ef67faab`

复核命令：`python .storage/warehouse-ghg-provenance-20261013/audit.py`。脚本只读取本地备份、快照并写出本地核验结果，不连接数据库。
