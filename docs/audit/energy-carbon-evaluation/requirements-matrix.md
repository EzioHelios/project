# 评价方案 74 项功能审查矩阵

本矩阵用于跟踪《工业企业和园区数字化能碳管理中心评价方案》74 项检测项目与当前桌面端页面的对应关系。状态会随逐阶段实测更新。

| 编号 | 检测项目 | 当前主要对应路由 | 当前审查状态 | 下一步 |
| --- | --- | --- | --- | --- |
| 1 | 概览 | `/home`, `/bigscreen/overview`, `/bigscreen/power`, `/bigscreen/carbon` | 部分有效 | P1 继续核验实时性、项目/园区切换、动态数据来源。 |
| 2 | 项目中心 | `/home`, `/data/company`, `/data/monitor-area` | 待取证 | 需要确认是否有单项目中心和项目级配置闭环。 |
| 3 | 监测中心 | `/energy-carbon/monitor`, `/data/point-monitoring`, `/data/meter`, `/data/video`, `/data/terminals` | 部分有效 | P1 已完成第一轮整改：设备台账新增接入与质量主线；监测中心 360 详情仍待增强。 |
| 4 | 告警中心 | `/energy-carbon/alerts`, `/data/alarm-rules` | 部分有效 | P1 已完成第一轮整改：告警中心可确认、转工单、关闭；规则页已改业务表单；工单深度闭环待复核。 |
| 5 | 能源消费量与强度计算 | `/energy/intensity` | 待审查 | P2 审查。 |
| 6 | 能耗双控管理 | `/energy/budget` | 待审查 | P2 审查。 |
| 7 | 能源消费分析与策略推荐 | `/energy/analysis` | 待审查 | P2 审查。 |
| 8 | 能流分析 | `/energy/flow` | 待审查 | P2 审查。 |
| 9 | 能效对标 | `/energy/benchmark` | 待审查 | P2 审查。 |
| 10 | 能效平衡与优化 | `/energy/balance` | 待审查 | P2 审查。 |
| 11 | 综能智控即时控制 | `/microgrid/operations`, `/microgrid/optimization` | 待审查 | P3 重点判断是否存在真实控制动作。 |
| 12 | 综能智控场景控制 | `/microgrid/settings`, `/microgrid/dispatch` | 待审查 | P3 重点判断策略配置和执行记录。 |
| 13 | 碳盘查支撑 | `/carbon/verification`, `/carbon/organization/*`, `/carbon-mgmt/*` | 待审查 | P4 审查。 |
| 14 | 碳告警与预警 | `/energy-carbon/alerts`, `/carbon/organization/inventory` | 待审查 | P4 复核碳告警规则、处置和预测。 |
| 15 | 碳配额录入与余额展示 | `/carbon/assets/ledger`, `/carbon/assets/overview` | 待审查 | P5 审查。 |
| 16 | CCER 项目接入与估值模型 | `/carbon/reduction/methodologies`, `/carbon/assets/certificates` | 待审查 | P5 审查。 |
| 17 | 碳资产交易模拟与收益分析 | `/carbon/assets/simulation`, `/carbon/assets/market` | 待审查 | P5 审查。 |
| 18 | 碳资产履约风险预警 | `/carbon/assets/compliance`, `/carbon/assets/overview` | 待审查 | P5 审查。 |
| 19 | 碳足迹计算 | `/carbon/product-footprint` | 待审查 | P6 审查。 |
| 20 | 碳排数据库 | `/carbon-mgmt/factors`, `/carbon-mgmt/calculation-factors` | 待审查 | P6/P4 审查。 |
| 21 | 碳足迹模型符合性验证 | `/carbon/product-footprint` | 待审查 | P6 审查。 |
| 22 | 绿电绿证抵扣逻辑验证 | `/carbon/assets/certificates`, `/carbon/product-footprint` | 待审查 | P5/P6 审查。 |
| 23 | 碳标识认证接口对接测试 | `/carbon/product-footprint` | 待审查 | P6 判断是否不适用或待建设。 |
| 24 | 数据分析 | `/energy/analysis`, `/carbon/organization/overview`, `/bigscreen/*` | 待审查 | 按相关阶段交叉审查。 |
| 25 | 组织/活动碳盘查 | `/carbon/organization/*`, `/carbon-mgmt/activities`, `/carbon-mgmt/category/*` | 待审查 | P4 审查。 |
| 26 | 供应商数据采集 | `/carbon/supply-chain` | 待审查 | P6 审查。 |
| 27 | 供应商碳盘查任务管理 | `/carbon/supply-chain` | 待审查 | P6 审查。 |
| 28 | 下游客户碳足迹披露 | `/carbon/supply-chain`, `/carbon/product-footprint` | 待审查 | P6 审查。 |
| 29 | 供应链碳分析 | `/carbon/supply-chain` | 待审查 | P6 审查。 |
| 30 | 数据采集方式覆盖 | `/data/terminals`, `/data/point-monitoring`, `/data/meter`, `/carbon-mgmt/import` | 部分有效 | P1 已完成第一轮整改：客户侧设备入口合并到设备台账，设备详情内承载接入配置。 |
| 31 | 数据质量校验 | `/data/terminals`, `/data/point-monitoring`, `/data/meter`, `/carbon-mgmt/import`, `/carbon/verification` | 部分有效 | P1 已完成第一轮整改：设备台账增加质量 Tab；跨能耗/碳核算的质量阻断仍待建设。 |
| 32 | 因子库管理 | `/carbon-mgmt/factors`, `/carbon-mgmt/calculation-factors` | 待审查 | P4 审查。 |
| 33 | 数据导出与追溯 | `/data/terminals`, `/data/point-monitoring`, `/data/meter`, `/energy/consumption`, `/carbon/verification` | 部分有效 | P1 已完成第一轮整改：设备台账提供进入实时读数/监测/告警的主线动作；统一追溯链路仍待建设。 |
| 34 | 光功率预测 | `/microgrid/forecast` | 待审查 | P3 审查。 |
| 35 | 关口功率预测 | `/microgrid/forecast` | 待审查 | P3 审查。 |
| 36 | 负荷预测 | `/microgrid/forecast` | 待审查 | P3 审查。 |
| 37 | 指标选择与展示 | `/microgrid/forecast`, `/bigscreen/*` | 待审查 | P3 审查。 |
| 38 | 源网荷储组网图 | `/microgrid/overview`, `/microgrid/operations` | 待审查 | P3 审查。 |
| 39 | 策略运行控制 | `/microgrid/optimization`, `/microgrid/dispatch` | 待审查 | P3 审查。 |
| 40 | 运行模式切换 | `/microgrid/operations`, `/microgrid/settings` | 待审查 | P3 审查。 |
| 41 | 调度看板日期选择 | `/microgrid/dispatch` | 待审查 | P3 审查。 |
| 42 | 调度看板事件记录 | `/microgrid/dispatch` | 待审查 | P3 审查。 |
| 43 | 调度指令记录 | `/microgrid/dispatch` | 待审查 | P3 审查。 |
| 44 | 虚拟电厂概览 | `/microgrid/overview` | 待审查 | P3 判断当前是否承接 VPP。 |
| 45 | 组网管理 | `/microgrid/settings/assets` | 待审查 | P3 审查。 |
| 46 | 调度运行 | `/microgrid/dispatch`, `/microgrid/operations` | 待审查 | P3 审查。 |
| 47 | 运行分析 | `/microgrid/operations`, `/microgrid/forecast` | 待审查 | P3 审查。 |
| 48 | 收益分析 | `/microgrid/optimization` | 待审查 | P3 审查。 |
| 49 | 创建规划 | `/carbon/climate`, `/energy/budget`, `/carbon/reduction/projects` | 待审查 | P5 审查。 |
| 50 | 规划结果 | `/carbon/climate`, `/carbon/reduction/overview` | 待审查 | P5 审查。 |
| 51 | 规划分析 | `/carbon/climate`, `/carbon/reduction/overview` | 待审查 | P5 审查。 |
| 52 | 规划配置 | `/carbon/climate`, `/carbon/reduction/methodologies` | 待审查 | P5 审查。 |
| 53 | 设备库管理 | `/data/terminals` | 待审查 | P7 审查。 |
| 54 | 设备台账管理 | `/data/terminals` | 待审查 | P7 审查。 |
| 55 | 个人信息管理 | `/profile` | 待审查 | P7 审查。 |
| 56 | 组织与成员管理 | `/admin/teams`, `/teams` | 待审查 | P7 审查。 |
| 57 | 角色管理 | `/auth/roles`, `/admin/roles` | 待审查 | P7 审查。 |
| 58 | 权限管理 | `/admin/roles` | 待审查 | P7 审查。 |
| 59 | 接口响应时间 | 前端各业务接口、压测脚本 | 待审查 | P7 需要性能证据。 |
| 60 | 运行稳定性 | 部署与监控材料 | 待审查 | P7 需要运行证据。 |
| 61 | 浏览器兼容性 | 前端构建与浏览器实测 | 待审查 | P7 需要兼容性证据。 |
| 62 | 系统扩展性 | 数据模型、配置项、动态字典 | 待审查 | P7 审查。 |
| 63 | 并发能力 | 压测脚本和报告 | 待审查 | P7 需要性能证据。 |
| 64 | 系统容量 | 数据规模、分页、索引、压测 | 待审查 | P7 需要容量证据。 |
| 65 | 场景适应性 | 多行业/多租户 demo profile | 待审查 | P7 审查。 |
| 66 | 多租户支持 | 租户切换、RLS、团队权限 | 待审查 | P7 审查。 |
| 67 | 多组织适配 | 组织档案、区域树、团队 | 待审查 | P7 审查。 |
| 68 | 行业适配 | 行业 profile、能源品类、因子、业务台账 | 待审查 | P7 审查。 |
| 69 | 数据安全 | 认证、权限、租户隔离 | 待审查 | P7 审查。 |
| 70 | 合规认证 | 合规材料、制度文档、系统证据 | 待审查 | P7 需要材料证据。 |
| 71 | 弱口令防护 | 登录策略、密码策略、失败控制 | 待审查 | P7 审查。 |
| 72 | 等保测评 | 等保材料或接口 | 待审查 | P7 需要材料证据。 |
| 73 | 数据分级分类 | 数据分类、权限、脱敏、导出控制 | 待审查 | P7 审查。 |
| 74 | 审计日志 | `/admin/audit` | 待审查 | P7 审查。 |
