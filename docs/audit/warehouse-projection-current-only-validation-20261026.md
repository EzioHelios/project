# 仓储投影改造：生产部署与验收记录

日期：2026-10-26（北京时间）。阶段：生产清理、部署和自然定时验收全部完成（用户明确授权不备份失效派生版本）。

## 已实现

- `metering/projection.py`：小时／日事实和电表月汇总按不含版本号的业务键 UPSERT；月对账原位更新。保留当前 ID，无业务变化不写入，已失效区间在原子事务内删除。
- 有界输入：SQLAlchemy 流式读取，每批最多 1000 行，禁止隐式关系加载；私有临时文件固定本轮输入，任务结束自动删除。按电表计算，最多保留单表月度小时／日桶，问题分批写入。元数据数量、临时文件空间和进程 RSS 设上限。
- 不再查询／加载派生历史。临时 seen 表仅服务本次原子发布，事务提交或回滚时删除。成功结果与水位共同提交，失败保留上次完整结果。
- 对账摘要包含实际电量及账单内容，稳定 ID 下的内容变化仍能识别。分摊按完整业务输入比较，忽略废弃的能源 revision 元数据，旧业务快照不被改写。
- `metering/jobs.py`、`projection_guard.py`：保留原有 cron 和队列，只为电量投影增加 Redis 持久尝试状态、2100 秒租约、1 小时／6 小时退避、连续三次失败熔断。SIGKILL 后尝试计数仍存在。失败月份不阻止其他月份／租户。
- 同租户重建及清理采用相同非阻塞 advisory lock。`METERING_PROJECTION_ENABLED=false` 可禁用投影；Redis `metering:projection:paused=1` 只暂停电量投影调度和手工投影 CLI。没有修改采集或其他任务的调度配置。
- 调度除新水位外，还对超过 24 小时未校验的旧月份进行有界复查，以识别原位修正、映射变化及被移除的数据。当前实现按月扫描、按内容差异写入，尚未实现仅扫描脏时间窗口。
- `projection_cleanup.py` 与 `app metering cleanup-projection-history`：默认只读预演；实际删除须显式提供 apply、已暂停写入以及备份已验证或明确豁免备份标志。按租户／月份过滤、固定 ID 截止点、2000 行批次、批间限速、超时、可重复执行，核对当前内容摘要。阻断重复当前键、外键、未审查的多态引用、盘查 fact_ids 引用和不完整分摊快照。
- 迁移 `c0261026a001`：先拒绝未清理数据，再为三张表建立不含版本号的唯一约束和 current-only 检查约束。迁移自身不删除数据。导入程序同步使用新唯一约束。

### 兼容字段的明确边界

没有保留旧版本行，也没有建立历史归档表。新行 revision_no 默认 1；旧当前行的 revision_no 冻结为原数字，supersedes_id 清空，is_current 只能为 true，业务唯一键禁止追加第二行。冻结这个数字是为了保持既有盘查凭证的事实哈希；它不再支持历史检索或版本递增。待消费方完全移除这些字段后，可单独删除兼容列。

## 本地测试

测试均使用 pytest 创建的隔离 PostgreSQL／Redis 容器，不连接生产数据库运行写入测试。

```sh
uv run pytest \
  src/py/tests/integration/system/test_projection_cleanup.py \
  src/py/tests/integration/system/test_metering_projection.py \
  src/py/tests/integration/system/test_projection_guard.py \
  src/py/tests/integration/material_allocation/test_allocation_usecase.py \
  src/py/tests/unit/test_metering_projection_jobs.py \
  src/py/tests/unit/lib/test_worker.py \
  src/py/tests/unit/lib/test_mqtt_ingest_worker.py \
  -n 0 -q --no-cov
```

结果：最终相关测试集 **40 项通过**（35.32 秒）；迁移增加锁等待上限后，清理／迁移的 **2 项测试**再次通过。测试不设全仓覆盖率门槛，本次并未运行整个仓库测试集。

验证范围：重跑幂等、稳定 ID 更新、撤销不复活、账单优先级、模拟数据来源、失败原子回滚、同租户并发互斥、租户隔离、清理重复执行、外键与 JSON 引用拦截、脏库拒绝迁移、清理后升级、旧分摊快照兼容、SIGKILL 后退避／熔断、其他租户继续执行、原采集 worker 与其他 worker 配置。

清理演练：两个租户分别构造 2020 行（100 个当前键及一个仅有历史的撤销键，20 个版本），每租户删除 1920 行，保留 100 个当前 ID 和相同电量摘要；处理第一个租户不改变第二个租户。复跑删除数为 0。数据库迁移先拒绝脏数据，清理后成功建立约束。

压力测试：数据库端生成 **120,000 条读数**，首次重算与重复校验合计 **8.46 秒**，Python 进程峰值 RSS **245.30 MiB**，输出始终为 **34 个小时结果 + 2 个日结果**，重复运行不增行。数据来自隔离测试，不能替代生产 worker 并发环境验收。

静态检查：本次修改的 Python 文件通过 Ruff；投影、任务、清理、退避四个核心模块通过 Pyright（0 errors）。

## 生产只读预演

首次盘点已保存于 `warehouse-projection-dry-run-20261026.json`。通过现有容器 Python 的标准输入执行只读查询，没有向容器写入代码或重建任务；事务显式 READ ONLY，查询设超时。

| 范围 | 总行数 | 当前行数 | 失效版本候选数 |
| --- | ---: | ---: | ---: |
| 四个活跃租户、三张派生表、所有月份 | 1,762,775 | 282,358 | 1,480,417 |

用户随后明确授权直接清理、不备份历史重复数据；最终已删除 1,480,417 行，保留 282,358 个当前行。各租户清理前后当前结果摘要一致。

初次工具保守报告了祥泰月对账与 `ghg_activity_record.source_record_id` 的 45 次数字碰撞。后续只读分组确认类型为 `source_system=energy_fact / source_record_type=meter_month`；本地生成脚本明确把设备 ID 写入这个字段，故不是月对账外键。工具已针对这一已核实语义排除误报，同时新增 `source_payload.fact_ids` 的实际能源事实引用检查。

14:33 SSH 恢复；最新 JSON fact_ids 检查及全租户复核通过，四个租户均无引用冲突。历史超时不再是当前阻塞项。

## 生产实施与验收清单

- 已完成：全租户 schema／引用复核、无备份清理、当前内容摘要核对。
- 已完成：相互匹配的 app／worker 代码与数据库约束发布，原 app 模板修复保留。
- 已完成：两家仓库 10 月重建、水位推进、紧接复跑复用，以及全部 26 个租户月份追赶。
- 已完成：真实 SAQ 队列连续 7 轮成功，最后两轮 pending_months=0、deferred=0、failed=0。原始 MQTT 读数在此期间持续新增，少量当前月份再次处理属于新数据推进。
- 已完成：15:00 其他自然定时任务、15:07 微电网历史任务均完成；15:10 电量投影自然定时任务于 15:11:09 完成。手动入队验收与自然 cron 分别保存证据。

## 运维入口与参数

只读预演示例：

```sh
app metering cleanup-projection-history --team <已核实租户slug> --report /tmp/projection-cleanup-preview.json
```

今后再次执行同类清理时使用 `--apply --writers-paused --backup-waived`；可指定 `--month YYYY-MM --batch-size 2000 --pause-ms 50`。本轮已按用户授权使用备份豁免执行实际清理。

投影预算：`METERING_PROJECTION_BATCH_SIZE` 默认 1000（上限 1000），`METERING_PROJECTION_SPOOL_MB` 默认 1024，`METERING_PROJECTION_RSS_MB` 默认 768。元数据保护上限 10000 行。Redis 熔断状态在 `metering:projection:<team_uuid>:<YYYY-MM>`；人工复核并确认无运行中任务后才能重置状态，不能自动清空所有状态来掩盖反复失败。

回滚不能仅启动仍追加历史版本的旧 worker；本次不备份失效派生版本，删除后不提供历史数据恢复；原始读数继续保留。生产共享 worker 已配置 2 GiB 内存上限，投影自身在 768 MiB RSS 时提前失败并退避；未修改宿主机 Swap 配置。


## 生产执行记录

- 14:33 重新建立 SSH 连接。扩展 JSON 事实引用复核通过；四个租户、三张派生表全量清理范围无冲突。
- 14:35 确认无运行中业务任务后切换 app／worker 到过渡修复镜像，`METERING_PROJECTION_ENABLED=false`。清除的只是上一轮开机遗留、所属 worker 已不存在的孤立投影任务。MQTT 与 EMQX 未重启。
- 14:36–14:42 按 5,000 行批次清理，批间等待 50ms。无历史重复数据备份；审计报告只保存数量、引用检查和当前内容摘要。
- 清理删除量：祥泰 843,666；安方 635,351；泰州 700；湖州 700。合计 1,480,417。每个租户清理前后当前 ID／内容摘要一致。
- 14:43 升级数据库 `f9a0b1c2d3e4 → c0261026a001`；迁移锁等待 2 秒、单语句上限 120 秒。
- 14:43–14:44 受控完成两个主要租户 10 月重建，各自立即重复执行并复用同一个成功 run；当前月份移出当时待处理清单。
- 14:45 再次等待业务任务排空后完成最终 app／worker 镜像切换；worker 内存上限 2 GiB，禁用额外 Swap 扩张。投影 RSS 预算 768 MiB、输入临时文件预算 1 GiB。
- 14:46 恢复投影调度，使用真实 SAQ 队列按原有每租户每轮最多 3 个月的边界追赶旧月份。原 cron 保持每小时 10、40 分，采集及其他任务调度未修改。
- 最终镜像以两个服务各自原镜像为基础，只覆盖经哈希核对的 11 个 Python 文件。保留 app 原有独立报表模板修复。镜像名：`warehouse-carbon:projection-app-20261026-v2`、`warehouse-carbon:projection-worker-20261026-v2`。

| 10 月租户 | 输入条数 | 原成功水位 | 新成功水位 | 重建结果 | 随后复跑 |
| --- | ---: | ---: | ---: | --- | --- |
| 祥泰 | 24,248 | 7,936,336 | 8,152,690 | 6,070 小时 + 260 日 | reused=true |
| 安方 | 55,056 | 7,937,204 | 8,153,398 | 4,856 小时 + 208 日 | reused=true |

两个月受控验证的 Python 进程峰值 RSS 为 220.67 MiB。恢复 SAQ 调度后的完整 worker 进程另行持续采样，最终数据见生产审计目录。

审计材料：`warehouse-projection-production-20261026/`，包含逐租户清理前后报告、10 月验收和发布源文件哈希。配置回退文件及发布上下文保留在服务器 `/root/warehouse/projection-20261026/` 及部署目录；其中没有历史重复数据备份。

若需临时止血，优先仅设置 Redis `metering:projection:paused=1`，保持其他任务运行。不能直接启动仍追加历史版本的旧代码；它与新唯一约束不兼容。已清理的旧派生行不恢复，必要时基于原始读数向前重建。


追赶后复核：四个租户分别完成 16／4／3／3 个月份。三张表分别保有 283,674／570／28 行，全部 is_current=true、supersedes_id=NULL；六个新增业务唯一／当前态约束均已验证。随后原始采集持续推进，表行数可因新读数生成当前统计而正常变化。


## 最终自然周期验收（15:11）

- 15:10:00 自然 cron 启动，15:11:09 完成，耗时 **69.221 秒**。四个租户中有新读数的两个 10 月成功推进；`pending_months=0`、`deferred=0`、`failed=0`。
- 祥泰 10 月最终成功水位 **8,154,190**，安方 **8,154,502**。成功结束时间分别为北京时间 15:10:53、15:11:09。
- 自然周期前后区间事实总行数 **283,674 → 283,682**；处理 10,934 个小时结果后，没有追加整月版本副本。三张表失效行和历史链引用均为 **0**，最终行数为 283,682／570／28。
- 最终 worker 容器内核记录峰值 **343.61 MiB**，SAQ 进程峰值 RSS **394.75 MiB**；容器上限 **2 GiB**，应用提前退出预算 **768 MiB**。`memory.events` 中 max、oom、oom_kill 均为 **0**；本次开机内核 OOM 杀进程数 **0**，app／worker 异常重启数 **0**。
- MQTT 和 EMQX 保持原容器，原始 MQTT 数据持续新增。15:00 认证清理、OAuth 刷新、设备状态同步、微电网预测，15:02 优化、15:07 微电网历史投影均完成。
- 云集采集接口依然返回改造前已有的外部 HTTP 429 限流；本次没有修改其采集逻辑，也不把任务返回 completed 等同于该外部接口采集成功。MQTT 实际新增读数已单独核实。
- 应用最终 HTTP 检查为 200。临时观察进程已结束，正常每小时 10／40 分调度保持开启；没有遗留暂停标志。

最终证据：`natural-cron.json`、`final-database-audit.json`、`final-resources.json`、`worker-verification.log`、`memory-samples.jsonl`。`release-bundle.json` 记录服务器上的最终源代码补丁包及 SHA256；该包仅含代码和发布清单，不含历史重复数据。
