# 企业录入案例实现记录

## 2026-11-15：运行小时派生与验收范围

### 原行为及问题依据

沃衡包原先调用 `app.domain.carbon.energy_analysis_importer._rebuild_equipment_workload_facts()`：先删除当前租户中来源为 `meter_run_hours` 的记录，再筛选 `meter_hourly` 来源且 `amount > 0` 的能源事实，按设备和日期统计行数，将 `count(*)` 同时写入 `workload_amount` 和 `run_hours`，单位为 h，状态直接写为 `confirmed`。原验收条件另要求 `workload_facts >= 6`。

该实现没有读取启停状态、累计运行时间表或班组运行记录，也没有按每条事实的起止时间累计持续时长。将正电量行数解释为运行小时，至少需要证明每条记录完整代表一小时实际运行、无重复区间、无缺测，并明确待机用电是否计入运行；现有派生过程未验证这些条件。本轮月度用量、领油单、维修工单和通勤运输案例也没有提供上述依据。条数达到 6 只能说明表中存在记录，不能证明设备、期间、计量单位或运行时间覆盖完整。

这属于现有输入不能支持原派生语义的问题。生产产量模型已经接入能源强度，不代表设备运行小时模型已经废弃，也不能用产量替代运行小时。

### 本轮调整及范围

本轮仅移除沃衡包中的运行小时自动派生调用和无条件的 6 条数量门槛。未删除作业量模型、维护服务、对标查询或其他来源的既有记录，未将 `meter_projection` 的正电量记录改当运行小时，未为使验收通过补造作业量。原派生函数仍存在于业务模块，本轮没有修改该模块或改变其他调用方。

保留现有生产产品、价格、产量和资源绑定检查，并保留 `workload_facts` 数量及 `workload_status` 状态。2026-11-15 两轮本地验收中，两租户均为 `workload_facts=0`、`workload_status=not_provided`。记录依据为 `/tmp/woheng-entry-stable-validate-1.log` 和 `/tmp/woheng-entry-stable-validate-2.log`；这些是本地验证日志，不是业务输入。

**运行小时未提供，未宣称完整能效对标。** 本轮通过的是企业输入案例的数量、单位、期间、对象、因子和核算结果检查，以及包中仍列明的安装检查。包级 `completed` 表示这些安装检查执行通过，不表示所有模块数据齐备或所有对标指标可计算。后续发现的组织核算边界可用性缺口也必须单独补验，已有核算结果不能替代页面重新核算条件的检查。

### 对现有功能的影响

| 功能 | 当前代码依据与本轮影响 |
| --- | --- |
| 运行小时、作业量数据维护 | `EquipmentWorkloadFact`、`EquipmentWorkloadFactService` 及其依赖提供器保留。本轮未改维护服务，也未单独完成维护入口的浏览器验收，不能据此声明完整维护流程已验证。 |
| 单位运行小时用电、单位作业量用电对标 | `EnergyBenchmarkQueryService._workload_actuals()` 和 `_workload_baseline()` 仍读取作业量表中的已确认记录。没有正的分母时，实际值为空、数据质量为 `invalid_denominator`；没有基准时还可能显示 `missing_benchmark`。本轮未提供运行小时，因此这些指标不具备完整演示条件。 |
| 用能分析中的运行小时汇总 | `energy/queries/analysis.py` 仍汇总作业量表，空表的汇总数值被 SQL 转为 0。应结合 `record_count=0` 解释为未提供记录，不能将其解释成已经确认设备停机零小时。此显示语义未在本轮修改。 |
| 产品产量、产值能源强度 | `energy/queries/intensity.py` 使用生产分母查询；相应设计文档限定其服务生产经营产出强度。该路径没有替代上述设备运行小时对标。 |
| 对标档案与指标配置 | 既有档案和运行小时指标继续保留；配置存在不代表分母完整，也不代表已经得到可用的对标结果。 |

`workload_status=available` 当前仅表示表中存在记录，不是按设备、期间和单位核对后的完整性结论。恢复完整设备对标验收时，需要提供注明设备、起止时间、实际运行时长、单位、确认状态和来源的业务记录；或另行确认可审计的运行状态推导规则。验收还需核对分子与分母对象及期间一致、缺测与重复处理、分母大于零，并通过真实对标查询验证。不得仅恢复固定条数门槛作为替代。

### 可追溯代码位置

- 原派生过程：`src/py/app/domain/carbon/energy_analysis_importer.py`，`_rebuild_equipment_workload_facts()`。
- 沃衡安装与校验：`src/py/app/demo/ops/woheng.py`，`_specialize_tenant()`、`_validate()`。
- 设备对标：`src/py/app/domain/energy/queries/benchmark.py`，`_workload_actuals()`、`_workload_baseline()`、`_comparison_row()`。
- 分析汇总：`src/py/app/domain/energy/queries/analysis.py`。
- 生产强度：`src/py/app/domain/energy/queries/intensity.py`；`docs/评价方案/能源强度产品产量产值分母设计.md`。

## 2026-11-15：10月组织核算边界与重新核算条件

原企业案例调用核算用例时未传组织边界，因而能够生成结果；页面则要求选择同主体、同报告期的已发布边界，并通过 readiness 检查。原 validate 只核对已有结果，遗漏了重新核算条件。这是验收缺口，旧的包级通过记录不覆盖此项。

新增安装流程通过 `OrganizationBoundaryUseCase.create_boundary()`、`save_selection()`、`publish_boundary()` 创建并发布10月专属边界。边界采用运营控制法这一演示假设，纳入案例的5个区域及5台设备、Scope 1/2/3、ISO类别1/2/3、Scope 3类别4和7，并采用Scope 2地点法。活动生成、活动维护和 `RunInventoryCalculation` 显式使用同一边界ID，不复用2026年度或其他月份边界。

`entry_boundary_readiness()` 除调用页面使用的 `GhgAnalyticsQueryService.readiness()`，还检查报告期确为2026年10月、边界属于相同主体且唯一发布、范围和设施覆盖完整、8条活动均关联该报告期和边界。缺少边界、未发布、错误期间、活动未关联或 readiness 不通过时，企业案例 validate 失败。

对已经生成结果但缺少边界的本地案例，提供独立的 `repair_entry_boundary_links()` 修复入口。执行前按原案例检查事实和活动，拒绝锁定、归档、内容不一致或已关联其他期间/版本的记录；随后创建对应月度边界，通过现有活动维护用例只补空缺的边界关联。该入口不重装能源事实，不替换因子或归集，不更新历史run、结果和参数快照，不执行核算。修复后可从页面发起新的运行；旧运行没有边界的历史事实仍保留，不回填成已使用新边界的运行。

实库修复必须在主线程安排的独占窗口执行；准备代码及隔离测试不代表已经修复实际库。隔离测试覆盖新安装的同边界核算、错误期间和未发布边界拒绝、已有结果但缺关联时校验失败、补关联幂等、修复后重新核算8条结果及历史结果快照不变。

### 实库执行结果

主线程在确认能源截图及临时数据清理完成后授权独占写入窗口。本轮仅执行上述demoops边界修复入口，未重装整包或从脚本发起新的实际库核算。

| 租户 | 10月报告期ID | 已发布边界ID | 活动关联 | 页面同源readiness |
| --- | ---: | ---: | ---: | --- |
| 沃衡泰州 | 2084 | 3087 | 8条 | `readyForCalculation=true`，0个阻断项 |
| 沃衡湖州 | 2085 | 3088 | 8条 | `readyForCalculation=true`，0个阻断项 |

重复执行时两租户的 `activity_links_updated` 均为0；整包validate及企业案例validate均通过。前后逐字段比较确认，历史run、结果、参数分配快照，以及案例事实、活动内容、参数、ID和数量不变。原结果合计仍为泰州327124.80 kgCO2e、湖州256348.76 kgCO2e。此处ready来自页面同源查询，实际浏览器重新生成和GWP重算由主线程安排终验，不能将本次检查表述为已经完成浏览器重算。

证据文件仍为0/8，readiness将其列为不阻断计算的warning；本次不宣称证据文件完整。运行小时仍为`not_provided`，不宣称完整能效对标。

本地执行证据：`/tmp/woheng-entry-boundary-repair-1.json`、`/tmp/woheng-entry-boundary-repair.json`、`/tmp/woheng-entry-boundary-package-validate.log`；历史快照比较文件为`/tmp/woheng-entry-frozen-before.json`、`/tmp/woheng-entry-frozen-after.json`。隔离测试日志为`/tmp/woheng-entry-boundary-isolated.log`，单元测试日志为`/tmp/woheng-entry-boundary-unit.log`。

## 2026-11-15：重新生成后的来源关联验收

实际浏览器按正常流程重新生成购电活动并核算成功后，活动仍为8条，泰州合计327124.80 kgCO2e。原demo校验却把`source_payload.input_record`作为案例身份，导致正常生成器刷新业务字段后误报购电活动及结果缺失。只读检查确认活动5463仍通过`source_record_type=energy_interval_fact`和`source_record_id=4013059`关联原能源事实，`source_fact_ids=[4013059]`也完整。

本轮在demo中统一改用业务来源合同：能源活动按来源类型和能源事实数据库主键关联，再由事实的`source_record_id`对应原始输入记录号；非能源台账按活动的业务记录编号对应工单或通勤运输记录。结果按匹配到的活动ID查询，不依赖活动名称、记录顺序或demo专属payload标记。新seed不再写入`input_record`，未修改业务生成器以保留该字段。

单事实活动可使用直接外键，或生成合同中的单元素`source_fact_ids`。若两者同时存在，则必须一致。当前每个案例只对应一条月度事实；多事实月度归集、外来事实、来源类型错误、重复或冲突关联均明确校验失败，不将单个案例数量覆盖整个归集组。

回归覆盖无标记、字段刷新、逆序活动、直接外键或来源集合，以及真实服务的“重新生成全部能源活动→选择GWP→核算→validate→重复seed”。60项单元测试及3项隔离集成测试通过；实际库仅执行只读诊断和validate，两租户企业案例检查均通过。本次没有重装、补写字段或修改实际业务数据。首次只读整包检查仍另报GHG合法`energy_type=electricity`为能源编码别名，该字段合同问题已交能源owner修正，不在demo中隐藏诊断或改写业务值。

证据：`/tmp/woheng-entry-link-diagnostic.log`、`/tmp/woheng-entry-link-unit.log`、`/tmp/woheng-entry-link-isolated.log`、`/tmp/woheng-entry-link-readonly-validate.log`。

能源owner完成GHG枚举与能源编码的诊断合同修复后，使用相同命令再次只读校验，退出码为0。泰州和湖州的`energy_type_issues`均为0，企业案例检查均通过，边界3087和3088的`readyForCalculation`均为true，各包含8条活动。最终日志为`/tmp/woheng-entry-final-readonly-validate.log`。复验未执行seed/install或修改实际记录；`workload_status`仍为`not_provided`，上述结果不表示完整能效对标已具备数据条件。
