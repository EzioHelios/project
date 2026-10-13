# 计量边界核验、能源调度与第二批组件实施

## 范围

本轮仅本地验证，前端18101；未部署线上，未更新生产数据库，未生成客户模拟数据。
旧项目依据及总分表结论见[祥泰计量边界核验](xiangtai-metering-boundary-20261012.md)。

## 已实施组件

| 清单ID | 变更 | 本轮验收与剩余项 |
| --- | --- | --- |
| O07 | 共用历史告警分布组件：类型、区域、处理状态切换 | 祥泰4575条历史记录；区域缺失单列，Top之外合并其他不丢数量。尚未增加历史告警独立期间筛选，不跟随能源期间冒充当期事件 |
| O08 | 最近事件详情增加区域、设备、等级、处理记录字段 | 通过已有外键查询；未关联设备保持缺失，不从描述提取编码猜测关联 |
| P08 | 最近采样列表、电表排行均可打开电表详情 | 点击真实设备ID；列明期间电量、累计示值、采样时间、所属区域、台账状态。未补地图坐标，不冒称已完成GIS设备落点 |
| V06/V07 | 历史安全告警类型、摄像头功能区分布 | 245条；功能区来自事件设备ID关联摄像头台账。旧配置存在名称与功能区不一致，待核实；未做区域点图筛选通道联动 |
| V08 | 历史安全告警处理状态分布与详情 | 结果态可见；无真实回放证据，不展示假回放，不自动处理历史事件 |

组件复用 `operations.tsx`、现有大屏图表层和面板皮肤。未增加业务事实表、旧接口兼容层或按设备名称分类规则。

## 新旧对照与截图

旧版运行时缺远程报表配置及模型，旧截图只作为布局参考，不能作为业务计算正确性基准。

| 页面/操作 | 原版结构参考 | 本轮结果态 |
| --- | --- | --- |
| 总览与告警区域 | [原总览](../../.storage/bigscreen-audit-20261012/old-overview.jpg) | [区域分布](../../.storage/bigscreen-audit-20261012/phase2/xiangtai-overview-alert-regions.jpg)、[处理状态](../../.storage/bigscreen-audit-20261012/phase2/xiangtai-overview-alert-status.jpg) |
| 电量监控 | [原电能页](../../.storage/bigscreen-audit-20261012/old-power.jpg) | [祥泰电量](../../.storage/bigscreen-audit-20261012/phase2/xiangtai-power.jpg)、[排行点击详情](../../.storage/bigscreen-audit-20261012/phase2/xiangtai-ranking-meter-detail.jpg) |
| 视频历史安全事件 | [原视频页](../../.storage/bigscreen-audit-20261012/old-video.jpg) | [功能区分布](../../.storage/bigscreen-audit-20261012/phase2/xiangtai-video-safety-regions.jpg)、[事件详情](../../.storage/bigscreen-audit-20261012/phase2/xiangtai-video-alert-detail.jpg) |
| 切换安方 | 不借用祥泰数据 | [电量](../../.storage/bigscreen-audit-20261012/phase2/anfang-power.jpg)、[电表详情](../../.storage/bigscreen-audit-20261012/phase2/anfang-meter-detail.jpg) |
| 1440×810布局 | 延续当前大屏框架 | [电量布局](../../.storage/bigscreen-audit-20261012/phase2/xiangtai-power-1440.jpg)、[总览布局](../../.storage/bigscreen-audit-20261012/phase2/xiangtai-overview-regions-1440.jpg) |

[18张截图清单](../../.storage/bigscreen-audit-20261012/phase2/evidence-manifest.json)记录页面、租户、截图路径与验收边界。最后两张为补算后再次查询的[祥泰](../../.storage/bigscreen-audit-20261012/phase2/xiangtai-power-after-catchup.jpg)及[安方](../../.storage/bigscreen-audit-20261012/phase2/anfang-power-after-catchup.jpg)结果。碳排页仅做既有结果展示回归，不等于重新验收碳核算；安方档案/通勤/告警空状态没有用其他租户数据填充。

浏览器测试：Codex内置浏览器，真实已登录账号，页面租户选择器切换；等待页面ready、全部图表finished与模型加载结束后截图。电表排行柱体点击实测通过。1920×1080与1440×810已检查，结束后恢复窗口尺寸。

初次请求曾因后端仍加载旧响应契约出现 `items is not iterable`。重启本地app后重新测试及取证，未通过兼容空数组隐藏问题；最终截图不采用该失败状态。

## 运行验收

运行日志保存在 `.storage/bigscreen-audit-20261012/`。

- `queue-catchup-final.log`：恢复后两批分别处理4个月/24154小时事实、3个月/22033小时事实，最后返回 `pending_months=0`。保留了先前中断任务failed的记录，未删除失败记录。
- `phase2-energy-verification.log`：2026-10-01至10-12的只读查询，安方54.48kWh、祥泰2084.48kWh；小时/日/月查询总量一致，趋势之和、区域之和、设备之和均与总量相等。两仓查询时待投影月份均为空。持续到达的新采样等待下一轮正常调度，不将待处理永远为0作为实时系统承诺。
- `phase2-tests-acceptance.log`：41项通过，覆盖租户隔离、接口、边界缺失/停用、无效示值、失败重试、输入回退、并发幂等及预测后台线程。1条Pyomo测试日志线程在清理时出现I/O关闭警告，保留记录，不描述为零警告。
- 首次联合测试受到重复启动同名测试数据库容器干扰，已停止重叠测试并串行重跑。旧能量平衡测试改用当前calculation/diagnostics契约，明确验证祥泰有边界时安方仍无边界，未恢复被删除的业务接口。
- `phase2-build.log`：前端构建通过，有既有大chunk提示。TypeScript通过；本轮变更Python Ruff、组件Biome和git diff空白检查通过。
- `phase2-frontend-tests.log`：7个大屏测试文件、27项通过；Node localStorage实验特性提示保留。
- 预测任务20:30实际cron耗时14.980秒，能源聚合20:10实际cron耗时72.970秒。后续补跑仍通过SAQ worker，不直接绕过任务队列执行。
- `phase2-scheduler-completed.log`：20:40:00.257再次自动执行能源聚合，20:40:04.915完成，耗时4.658秒，处理1个月/2208条小时事实，pending_months=0。正常增量已在修复后实测，不仅是一次历史补跑成功。

## 仍需条件

- 祥泰总分表：需带设备编码的单线图/接线表，现有代码与SQL没有非重叠配置依据。
- 光伏/充电分项：旧设备ID配置已找到，但发电寄存器、正反向、电气接入关系仍需确认，未擅自新增发电量。
- 云集实时采集：HTTP 429限流，聚合可以处理既有数据，不能据此称采集已恢复。
- 视频台账：部分事件类型“火点”对应描述“异常跌倒”；设备名称含室外、功能区却为室内B01。保留原关联，需核实原字典及配置；摄像头实际播放、GIS坐标仍未验收。
- 调度历史更正：新增读数按水位触发；存量更正、边界变更、跨月基点影响需要显式重算，未加入自动依赖失效逻辑。
