# 工业能碳后台产品调研 Benchmark

调研日期：2026-06-13  
适用项目：工业能碳后台，React / Tailwind / shadcn 技术栈  
产出目标：为后续后台视觉系统、页面 archetype、CRUD 规范和两页试点改造提供设计依据。

## 0. 核心判断

成熟工业、数据、能碳软件的“高级感”主要来自四件事：

1. **对象模型清楚**：用户知道自己正在看企业、组织边界、区域、设备、测点、活动数据、排放因子、核算批次、审核记录中的哪一个对象。
2. **上下文稳定**：周期、组织、Scope、能源介质、设备范围、数据来源等筛选条件在页面顶部稳定存在，而不是散落在卡片里。
3. **状态和链路可追溯**：数据是否缺失、是否估算、是否已审核、因子来自哪里、计算何时完成、谁提交过证据，都能被追溯。
4. **高密度但不嘈杂**：表格、筛选、状态、图表和操作按钮有统一秩序。视觉不是大屏、不是营销页，也不是把 SaaS 卡片铺满。

本项目后续不宜直接做“深色发光工业风”。深色界面应只保留给实时监控、报警、值班看板、设备态势等低交互或半值守场景。台账、核算、审核、配置、因子维护、报表生成等高频输入页面应以浅色、高密度、低装饰的企业后台为主。

## 1. 调研样本与来源

本次调研将样本分为四类：

- 工业软件：Siemens WinCC Unified、Schneider Electric EcoStruxure Power Monitoring Expert、AVEVA PI Vision、GE Vernova Proficy Operations Hub。
- 数据软件：Grafana、Datadog、Snowflake Snowsight、Power BI / Fabric、Superset、Metabase。
- 能碳 / ESG 软件：SAP Sustainability Footprint Management、Salesforce Net Zero Cloud、IBM Envizi、Watershed、Persefoni、Normative、国内能碳产品公开材料。
- 企业后台规范：SAP Fiori、Ant Design ProComponents、Carbon Design System、PatternFly、Atlassian Design System。

说明：公开页面不总是能提供完整产品截图，尤其是企业软件的后台详情页和审核流。本调研以官方文档、产品页、公开帮助文档和公开示例为主，截图仅作为后续人工采样字段，不把截图打包进本文档。

## 2. 工业软件 UI 观察

### 2.1 Siemens WinCC Unified

官方文档中的 Trend control 用于展示当前过程数据或日志中的 tag 值，强调趋势控件、实时值、历史值和可配置布局。它的启发不是“界面要黑”，而是工业软件首先要把**过程变量、时间序列、状态和控制对象**稳定建模。[1]

可借鉴：

- 图表是过程数据的容器，不是装饰。每条曲线背后有明确 tag、单位、时间范围、采样频率。
- 趋势、报警、实时值可以作为设备详情页或能源分析页的局部模块。
- 工业图形页可以更自由，但后台管理页不应照搬 HMI 画布。

不适合直接照搬：

- HMI 的大字号状态块、按钮矩阵、设备图元不适合作为碳核算和台账页面的主视觉。
- 过强的实时监控感会让“核算、审核、配置”误读成“中控室”。

### 2.2 Schneider Electric EcoStruxure Power Monitoring Expert

EcoStruxure PME 的操作文档把 Web Applications 明确拆为 Dashboards、Diagrams、Trends、Alarms、Reports、Settings，同时还保留报警 annunciator。这说明工业能源软件不是一个泛泛的 dashboard，而是一组有边界的应用入口。[2]

可借鉴：

- 导航应按“看数、看图、看趋势、看报警、出报告、做设置”组织，而不是按数据库表堆菜单。
- 报警、趋势、报表、设置是不同工作模式，页面密度和操作能力应不同。
- 诊断型页面需要能从汇总跳到具体设备、测点、事件或原始数据。

不适合直接照搬：

- 电力监控产品中的单线图、实时控制操作不一定适合企业碳核算。
- 如果照搬“设备监控一屏”，碳管理对象会被设备资产吞掉。

### 2.3 AVEVA PI Vision

PI Vision 的事件表和 Event Frames 模式强调事件的开始、结束、属性、上下文和确认。这对能碳平台有价值：核算异常、缺失数据、补录、审核驳回都可以被视为事件，而不是简单的红黄绿状态。[3]

可借鉴：

- 把异常、审核、补录、因子变更、计算失败建模为事件记录。
- 详情页内提供“事件表 + 时间线 + 关联对象”，而不是只做 Toast 和弹窗。
- 状态的确认和评论应留痕。

不适合直接照搬：

- PI Vision 更偏过程历史和事件回放，碳核算还需要组织边界、标准来源、因子版本和证据附件。

### 2.4 GE Vernova Proficy Operations Hub

GE Vernova 把 Proficy Operations Hub 定位为 Web-based visualization 和 operations intelligence，可连接 historian、MES 和第三方系统，支持监控、数据录入、问题分析和跨层级决策。[4]

可借鉴：

- 工业后台不应只有“看板”，还应支持数据录入、问题追踪和跨系统数据上下文。
- 页面需要区分实时数据、历史数据、人工录入数据、计算输出。
- 数据分析页面应提供“从 KPI 到明细”的钻取路径。

不适合直接照搬：

- 低代码可视化平台的自由画布会加剧本项目“每页自由拼 UI”的问题。我们应抽象模板，而不是开放每页自由布局。

## 3. 数据软件 UI 观察

### 3.1 Grafana

Grafana 官方文档将 panel 定义为 dashboard 的基本 building block，由 query 和 visualization 构成。变量用于动态改变 dashboard 里的查询，tooltip 用于呈现数据点细节。[5][6][7]

可借鉴：

- 能源分析页可以采用“固定上下文筛选 + panel 网格”的模式。
- 每个 panel 必须声明数据源、查询维度、时间范围、单位、空状态和钻取目标。
- Tooltip 应显示数值、单位、时间、同比 / 环比、数据来源，而不是只显示一个数。

不适合直接照搬：

- Grafana 风格过强，直接套用会让产品像通用监控平台。
- 变量太多会导致 filter bar 变成飞行仪表盘。业务筛选要分主筛选和高级筛选。

### 3.2 Datadog

Datadog dashboard 支持 Timeseries、Table、Top List、Heatmap、Event Stream 等多种 widgets；template variables 可以按 tag、attribute、facet 动态过滤或分组，并支持 saved views。[8][9][10]

可借鉴：

- 能碳分析页需要“保存视图”：例如按园区、能源介质、车间、Scope、月度等组合保存。
- 事件 overlay 的思路适合把“停产、检修、数据缺失、因子切换、价格变化”叠加到能耗趋势上。
- Widget 类型不应无限扩展，平台应先定义可控的图表白名单。

不适合直接照搬：

- Datadog 是可观测性产品，标签体系强。能碳系统还需要标准、口径、证据和审核链路，不能只有 tags。

### 3.3 Snowflake Snowsight

Snowsight 的 dashboard 是由 query results 生成的 chart tiles，worksheet 数据可转为 bar、line、scatter、heat grid、scorecard，并提供 dashboard / worksheet 过滤。[11][12][13]

可借鉴：

- 分析页要承认“图表来自查询结果”，因此需要暴露查询口径、更新时间和数据粒度。
- Scorecard 适合 KPI strip，但只能显示关键指标，不能滥用成装饰卡片。
- Filter 应能同时作用于 dashboard 和数据明细。

不适合直接照搬：

- Snowsight 面向数据工程和 SQL 分析，本项目要把业务语言置于 SQL 之前。

### 3.4 Power BI / Fabric、Superset、Metabase

这些 BI / 自助分析工具共同模式是：数据源、模型、图表、筛选、分享和权限。它们对本项目的启发是“分析页面要可解释”，但不应把企业后台全部 BI 化。

可借鉴：

- 图表应有统一 legend、tooltip、单位、空状态、导出能力。
- 分析页可以支持钻取和交叉过滤。
- 复杂图表应优先服务业务问题，例如能效异常、碳排热点、预算偏差。

不适合直接照搬：

- BI 侧边字段面板不适合普通能碳业务人员。
- 把所有业务对象都做成图表会牺牲 CRUD 和审核效率。

## 4. 能碳 / ESG 软件观察

### 4.1 GHG Protocol 作为对象和流程底座

GHG Protocol Corporate Standard 为企业级温室气体清单提供要求和指南，并强调一致性、透明性和可核查的清单。Scope 3 Standard 提供企业价值链排放核算方法，覆盖 15 类 Scope 3 活动；Scope 3 Calculation Guidance 进一步给出每类排放的计算方法和示例。[14][15][16]

对产品结构的启发：

- 系统必须把组织边界、运营边界、Scope、排放源、活动数据、因子、计算方法、证据、审核状态作为一等对象。
- “数据质量”和“计算依据”不是详情页角落里的补充信息，而是碳管理软件的骨架。
- Scope 1/2/3 不应只是筛选标签，应影响页面结构、字段、计算方法和证据要求。

### 4.2 SAP Sustainability Footprint Management

SAP SFM 强调企业和产品碳足迹计算、ERP 数据基础、排放因子管理、规模化计算和 footprint analytics。官方页面提到使用 ERP 中的 material flows、production activity、energy consumption、supplier information 作为数据基础，并提供 45,000+ 预置因子映射。[17]

可借鉴：

- 能碳后台应从 ERP / 业务系统数据进入，而不是所有数据都靠人工填报。
- 因子管理要能区分预置因子、供应商特定因子、自定义因子、版本和适用范围。
- 产品碳足迹和组织碳核算虽然都叫碳，但页面 archetype 应分开。

不适合直接照搬：

- SAP 生态依赖 ERP 语境较重，本项目需要保持轻量，不应把页面做成 SAP 复杂度。

### 4.3 Salesforce Net Zero Cloud

Salesforce Net Zero Cloud 公开帮助文档强调将排放活动映射到 GHG 类别，并支持手动将采购汇总数据匹配到 Scope 3 排放因子。[18][19]

可借鉴：

- 活动数据台账需要“匹配因子”的工作流，不能只在表格里存一个 factor_id。
- Scope 3 类目需要专门的字段结构，例如采购、差旅、物流、废弃物等。
- 因子匹配需要可审核、可批量、可回滚。

不适合直接照搬：

- Salesforce 对象模型和页面范式强绑定 CRM 平台，本项目可以吸收对象化思路，但不必复制 Salesforce 式记录页。

### 4.4 IBM Envizi

IBM Envizi 文档明确其排放和能源计算引擎基于 GHG Protocol，并有来自 eGRID、UK Defra、IEA、EORA66 等的因子库；算法按 data type、factor set、region、time period 匹配因子，并可为了审计查看计算中使用的因子。[20] Envizi 还说明 Scope 1 & 2 模块会捕获 activity data，转换和标准化数据，应用 conversion factors，输出 emissions 和 energy use。[21]

可借鉴：

- 因子匹配必须解释“为什么选择这个因子”：数据类型、地区、时间、因子集、版本。
- 计算结果详情页应包含 calculation trace。
- 数据健康、因子审计、异常修正要成为一类标准页面，而不是报错弹窗。

不适合直接照搬：

- Envizi 是大型 ESG suite，模块多、概念密。我们需要把基础对象先做稳。

### 4.5 Watershed、Persefoni、Normative

Watershed 公开页面强调 500,000+ emissions factors、data lineage、review workflows、AI transparency 和完整报告质量控制。[22] Persefoni 强调 Scope 1/2/3、GHG Protocol 对齐、监管报告和 audit / assurance 能力。[23] Normative 强调 Scope 1/2/3、349,000 verified emission factors、AI 分类和质量控制、GHG Protocol 标准。[24]

可借鉴：

- 能碳平台的竞争力不在“漂亮 dashboard”，而在数据质量、因子库、追溯链、报告口径和审核效率。
- AI 可以用于数据清洗、字段匹配、因子建议、异常提示，但页面必须保留人工 review 和解释权。
- 证据附件、审批记录、因子来源、计算版本应在同一个业务上下文里可查看。

不适合直接照搬：

- 海外产品强调监管披露和咨询服务。本项目如果面向工业园区 / 企业能源场景，还需要更多设备、测点、分项分时、尖峰谷平和能效对标能力。

### 4.6 国内能碳产品公开材料

阿里云能耗宝定位为“碳管理 + 能耗优化”，覆盖核算碳排量、产品碳足迹、降碳方案和碳中和路径。[25] 腾讯云碳引擎公开资料强调数据汇接、预置行业模板、参数库、公式编辑和从能耗监测升级为碳排放监测。[26][27] 华为园区数字能源方案强调能源设备统一接入、统一管理、能量流和碳排流一屏可视、用能分析和源网荷储协同。[28] 百度智能云材料提到 IoT 采集、系统对接、在线填报、活动管理、核算公式管理、参数因子管理、填报表格管理等能力。[29]

可借鉴：

- 国内能碳平台普遍把“数据接入 + 模板 + 因子 + 公式 + 能耗监测升级”作为核心。
- 工业园区场景中，能源流、碳排流、设备接入、分项计量、尖峰谷平分析是重要页面线索。
- 公式编辑和参数库需要作为“受控配置”处理，不能变成自由脚本黑箱。

不适合直接照搬：

- 公开材料常偏解决方案展示，容易有大屏化、宣传化倾向。后台产品要回到台账、配置、审核、导入、错误处理和权限。

## 5. 企业 CRUD / 后台规范观察

### 5.1 SAP Fiori List Report 与 Object Page

SAP Fiori 将 List Report 和 Object Page 作为企业应用核心 floorplan。Table Toolbar 中包含按重要性排序的操作、表格个性化、批量编辑、导出、复制、粘贴、应用操作、危险操作消息、标准创建删除、对象页搜索和编辑等规则。[30][31]

可借鉴：

- 本项目应建立 Ledger Page 和 Detail Page 标准模板，类似 List Report + Object Page。
- 操作按钮按频率和风险分层：主操作、次操作、批量操作、更多、危险操作。
- 表格工具栏和筛选条应统一，不能每页自由摆。

### 5.2 Carbon / PatternFly / Atlassian 状态与空状态

Carbon Design System 把 empty state 定义为页面或容器没有数据可显示时的状态。[32] PatternFly 把空状态拆为 required configuration、no access、back-end failure、success、creation 等类型，并强调标题应说明用户需要做什么。[33] Atlassian Lozenge 将状态标记定义为用于快速识别项目状态的视觉指示器。[34]

可借鉴：

- 空状态需要告诉用户下一步，不要写“暂无数据”了事。
- 权限不足、未配置、后端失败、已完成、首次创建是不同空状态。
- 状态 badge 应有语义体系，不应每页随意定义颜色。

## 6. 可以沉淀为本项目的成熟模式

### 6.1 页面模式

| 页面模式 | 外部对应 | 本项目用途 | 核心区域 |
| --- | --- | --- | --- |
| Workbench 工作台 | ESG / 工业任务中心 | 今日待处理、异常、核算进度、审核任务 | KPI strip、任务队列、风险提示、快捷入口 |
| Ledger 台账 | SAP List Report、企业 CRUD | 活动数据、能耗数据、排放源、设备测点、因子库 | 筛选条、表格、批量操作、导入导出 |
| Analysis 分析 | Grafana、Datadog、BI | 能耗趋势、碳排热点、能效对标、预算偏差 | Context filter、KPI、图表网格、异常明细 |
| Audit 审核 | Envizi、Watershed、事件流 | 核算批次、审核记录、证据链、驳回补正 | 状态流、证据附件、差异说明、审计日志 |
| Reference Data 主数据 | SAP / IBM 因子管理 | 企业档案、组织边界、排放因子、计算因子 | 主列表、详情、版本、适用范围 |
| Settings 配置 | 企业后台设置 | 权限、字典、公式、模板、阈值、通知 | 分组设置、风险提示、变更记录 |

### 6.2 核心布局范式

后台页面建议统一为以下结构：

1. **Page Header**：标题、对象类型、面包屑、主操作、状态。
2. **Context Bar**：周期、组织、Scope、区域、能源介质、数据来源等关键上下文。
3. **Summary Strip**：只放 3 到 6 个关键指标，包含单位和更新时间。
4. **Main Content**：表格、图表网格、审核流、详情区。
5. **Side Panel / Drawer**：高级筛选、字段配置、因子匹配、证据预览、计算追踪。
6. **Audit Footer / Timeline**：详情页底部展示创建人、更新时间、提交人、审核人、版本、日志。

### 6.3 视觉判断标准

真工业 / 真企业后台：

- 高密度表格有清晰列规则。
- 状态 badge、时间、单位、数值格式一致。
- 筛选条件稳定，图表口径可解释。
- 详情页能追溯数据来源、因子、计算、证据、审核。
- 操作按钮少而准，危险操作被收纳和确认。

AI 工业风假象：

- 深色背景 + 蓝绿发光线框，但没有业务层级。
- 每页都有大卡片和说明文案，像宣传页。
- KPI 无单位、无时间、无来源。
- 图表只有“漂亮趋势”，没有 tooltip、legend、口径、异常和钻取。
- 表格像数据库 dump，缺少业务状态、证据、审核和批量操作。

## 7. 对本项目的直接结论

1. **先做 archetype，不先做皮肤**：页面应先被归类为 Workbench、Ledger、Analysis、Audit、Reference Data、Settings。
2. **台账优先于卡片**：绝大多数后台功能都应以 Ledger 模式重新组织，而不是卡片堆叠。
3. **分析页统一 Context Bar**：组织、周期、能源介质、Scope、区域、设备等必须在顶部稳定呈现。
4. **碳核算页需要 Audit 化**：`/carbon/accounting` 不应只是计算结果看板，应包含核算批次、活动数据、因子匹配、计算追踪、证据、审核状态。
5. **能源分析页需要 Data Platform 化，但保持业务语言**：`/energy/analysis` 可以借鉴 Grafana / Datadog 的 panel grid、变量和 saved view，但字段命名要是工业能耗语言。
6. **CRUD 要统一组件化**：筛选、表格、状态、操作、导入、详情、空状态、错误状态、审计字段应由全局组件控制。
7. **深色只给监控类场景**：大多数管理页面采用浅色、紧凑、低装饰。深色可用于实时态势、值班大屏、报警中心的局部模式。

## 8. 后续截图采样模板

后续人工采样每张截图用以下字段记录：

- 产品名称：
- 页面类型：Workbench / Ledger / Analysis / Audit / Reference Data / Settings / Detail
- 使用场景：
- 信息密度：低 / 中 / 高
- 背景与主色：
- 导航方式：
- 筛选区位置：
- 表格结构：
- 图表结构：
- 操作按钮层级：
- 状态表达方式：
- 空 / 错误 / 权限状态：
- 审计与数据来源：
- 值得借鉴：
- 不适合本项目：

## 9. 参考来源

[1] Siemens, WinCC Unified Trend control documentation, accessed 2026-06-13: https://docs.tia.siemens.cloud/r/en-us/v20/configuring-screens-rt-unified/overview-of-screen-objects-rt-unified/controls-rt-unified/trend-control-rt-unified  
[2] Schneider Electric, EcoStruxure Power Monitoring Expert 2024, Operate, accessed 2026-06-13: https://product-help.se.com/docs/EcoStruxure/Power-Monitoring-Expert-2024/content/6_operating/operating_systemguide.htm  
[3] AVEVA, PI Vision Create an events table, accessed 2026-06-13: https://docs.aveva.com/bundle/pi-vision/page/1010049.html  
[4] GE Vernova, Proficy Operations Hub, accessed 2026-06-13: https://www.gevernova.com/software/products/hmi-scada/operations-hub  
[5] Grafana, Panels and visualizations, accessed 2026-06-13: https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/  
[6] Grafana, Variables, accessed 2026-06-13: https://grafana.com/docs/grafana/latest/visualizations/dashboards/variables/  
[7] Grafana Cloud, Configure tooltips, accessed 2026-06-13: https://grafana.com/docs/grafana-cloud/visualizations/panels-visualizations/configure-tooltips/  
[8] Datadog, Dashboard widgets, accessed 2026-06-13: https://docs.datadoghq.com/dashboards/widgets/  
[9] Datadog, Template variables, accessed 2026-06-13: https://docs.datadoghq.com/dashboards/template_variables/  
[10] Datadog, Widget types, accessed 2026-06-13: https://docs.datadoghq.com/dashboards/widgets/types/  
[11] Snowflake, Visualizing data with dashboards, accessed 2026-06-13: https://docs.snowflake.com/en/user-guide/ui-snowsight-dashboards  
[12] Snowflake, Filter query results in dashboards and worksheets, accessed 2026-06-13: https://docs.snowflake.com/en/user-guide/ui-snowsight-filters  
[13] Snowflake, Visualizing worksheet data, accessed 2026-06-13: https://docs.snowflake.com/en/user-guide/ui-snowsight-visualizations  
[14] GHG Protocol, Corporate Standard, accessed 2026-06-13: https://ghgprotocol.org/corporate-standard  
[15] GHG Protocol, Corporate Value Chain Scope 3 Standard, accessed 2026-06-13: https://ghgprotocol.org/corporate-value-chain-scope-3-standard  
[16] GHG Protocol, Scope 3 Calculation Guidance, accessed 2026-06-13: https://ghgprotocol.org/scope-3-calculation-guidance-2  
[17] SAP, Sustainability Footprint Management, accessed 2026-06-13: https://www.sap.com/products/scm/sustainability-footprint-management.html  
[18] Salesforce Help, Emissions activities and scope categories, accessed 2026-06-13: https://help.salesforce.com/s/articleView?id=ind.netzero_manager_emissions_activities_and_their_emissions_scope_categories.htm&language=en_US&type=5  
[19] Salesforce Help, Match procurement data to emission factors, accessed 2026-06-13: https://help.salesforce.com/s/articleView?id=ind.netzero_manager_link_to_emission_factors.htm&language=en_US&type=5  
[20] IBM Docs, Envizi ESG Suite product overview, accessed 2026-06-13: https://www.ibm.com/docs/en/envizi-esg-suite?topic=product-overview  
[21] IBM Docs, Scope 1 & 2 GHG Accounting, accessed 2026-06-13: https://www.ibm.com/docs/en/envizi-esg-suite?topic=modules-scope-1-2-ghg-accounting  
[22] Watershed, Sustainability AI platform, accessed 2026-06-13: https://watershed.com/  
[23] Persefoni, Carbon footprint measurement and analytics, accessed 2026-06-13: https://www.persefoni.com/business/carbon-footprint-measurement-analytics  
[24] Normative, Carbon accounting software, accessed 2026-06-13: https://normative.io/  
[25] 阿里云，能耗宝，accessed 2026-06-13: https://cn.aliyun.com/product/applicationservice/energyexpert  
[26] 腾讯云，碳引擎产品简介 PDF，accessed 2026-06-13: https://main.qcloudimg.com/raw/document/product/pdf/1498_60505_cn.pdf  
[27] 腾讯云，碳引擎截图页，第 5 到 6 页，accessed 2026-06-13.  
[28] 华为数字能源，低碳园区解决方案，accessed 2026-06-13: https://digitalpower.huawei.com/cn/antoeco/lc-campus  
[29] 百度智能云，度能 AIoT 能碳数智化平台，accessed 2026-06-13: https://cloud.baidu.com/article/298869  
[30] SAP Fiori Design System, List report floorplan, accessed 2026-06-13: https://www.sap.com/design-system/fiori-design-web/v1-84/page-types/floorplans/list-report-floorplan-sap-fiori-element/usage  
[31] SAP Fiori Design System, Table toolbar, accessed 2026-06-13: https://www.sap.com/design-system/fiori-design-web/v1-145/discover/frameworks/sap-fiori-elements/tables-and-lists/tables-toolbar  
[32] Carbon Design System, Empty states, accessed 2026-06-13: https://carbondesignsystem.com/patterns/empty-states-pattern/  
[33] PatternFly, Empty state design guidelines, accessed 2026-06-13: https://www.patternfly.org/components/empty-state/design-guidelines/  
[34] Atlassian Design System, Lozenge, accessed 2026-06-13: https://atlassian.design/components/lozenge
