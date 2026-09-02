# 评价方案 74 项功能审查矩阵

本矩阵用于跟踪《工业企业和园区数字化能碳管理中心评价方案》74 项检测项目与当前桌面端页面的对应关系。状态会随逐阶段实测更新。

| 编号 | 检测项目 | 当前主要对应路由 | 当前审查状态 | 下一步 |
| --- | --- | --- | --- | --- |
| 1 | 概览 | `/home`, `/bigscreen/overview`, `/bigscreen/power`, `/bigscreen/carbon` | 部分有效 | P1 继续核验实时性、项目/园区切换、动态数据来源。 |
| 2 | 项目中心 | `/home`, `/data/company`, `/data/monitor-area` | 待取证 | 需要确认是否有单项目中心和项目级配置闭环。 |
| 3 | 监测中心 | `/energy-carbon/monitor`, `/data/point-monitoring`, `/data/meter`, `/data/video`, `/data/terminals` | 部分有效 | P1 已完成第一轮整改：设备台账新增接入与质量主线；监测中心 360 详情仍待增强。 |
| 4 | 告警中心 | `/energy-carbon/alerts`, `/data/alarm-rules` | 部分有效 | P1 已完成第一轮整改：告警中心可确认、转工单、关闭；规则页已改业务表单；工单深度闭环待复核。 |
| 5 | 能源消费量与强度计算 | `/energy/intensity`, `/energy/consumption`, `/data/meter`, `/data/production-output` | 部分有效 | P2A 先验证自动计量、能源事实、活动数据和作业量分母维护；P2B 再补业务对象选择、强度计算明细、来源追溯。 |
| 6 | 能耗双控管理 | `/energy/budget` | 部分有效 | P2 已完成代码级预审：补目标编辑/停用/删除、动作式审批、对象选择和建议转调整。 |
| 7 | 能源消费分析与策略推荐 | `/energy/analysis` | 部分有效 | P2 已完成代码级预审：补异常详情、来源下钻、策略转整改/预算调整/工单闭环。 |
| 8 | 能流分析 | `/energy/flow` | 部分有效 | P2 已完成代码级预审：补能流关系维护口径、损耗阈值来源、报告保存或导出。 |
| 9 | 能效对标 | `/energy/benchmark` | 部分有效 | P2 已完成代码级预审：补标杆对象选择、编辑动作、整改建议转措施或任务。 |
| 10 | 能效平衡与优化 | `/energy/balance` | 部分有效 | P2 已完成代码级预审：验证模拟保存回读，补对象选择、状态流转和效果复核。 |
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
| 30 | 数据采集方式覆盖 | `/data/terminals`, `/data/point-monitoring`, `/data/meter`, `/carbon-mgmt/import`, `/api/energy/imports/datasets`, `/data/production-output` | 部分有效 | P1 已完成区域、设备、测点和基于已有接入通道的 MQTT 绑定/映射/测试；P2A 继续验证非电表能源导入、活动数据导入、作业量分母维护和经营台账来源。 |
| 31 | 数据质量校验 | `/data/terminals`, `/data/point-monitoring`, `/data/meter`, `/carbon-mgmt/import`, `/energy/consumption`, `/carbon/verification` | 部分有效 | P1 已完成设备台账质量 Tab；P2A 需验证读数质量、能源事实质量、导入预检、活动质量与后续计算阻断关系。 |
| 32 | 因子库管理 | `/carbon-mgmt/factors`, `/carbon-mgmt/calculation-factors` | 待审查 | P4 审查。 |
| 33 | 数据导出与追溯 | `/data/terminals`, `/data/point-monitoring`, `/data/meter`, `/energy/consumption`, `/carbon-mgmt/activities`, `/carbon/verification` | 部分有效 | P2A 先按来源类型验证追溯：自动读数、能源事实、活动记录、作业量分母和经营台账；统一追溯链路仍待建设。 |
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
| 53 | 设备库管理 | `/data/terminals` | 已闭环 | 已验证设备新增、编辑、挂区域、停用、恢复、删除、测点维护和 MQTT 绑定/映射。 |
| 54 | 设备台账管理 | `/data/terminals` | 已闭环 | 已验证设备列表、详情、基础信息编辑、采集配置展示和设备生命周期动作。 |
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
