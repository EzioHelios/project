# 工业能碳后台视觉系统与重构路线图

调研日期：2026-06-13  
适用项目：工业能碳后台，React / Tailwind / shadcn 技术栈

## 0. 路线原则

后续重构不应从“每页做得更好看”开始，而应从“全局规则收口”开始。工业感不是深色和发光线，工业感是可靠、可追溯、状态明确、数据密度适中、操作成本低。

### 0.1 当前阶段范围

当前阶段只覆盖后台侧边栏中的两个核心菜单组：

- `能源运营`：`/energy/consumption`、`/energy/intensity`、`/energy/analysis`、`/energy/benchmark`、`/energy/flow`、`/energy/balance`、`/energy/budget`
- `碳核算`：`/carbon/accounting`、`/carbon/product-footprint`、`/carbon/supply-chain`、`/carbon/verification`、`/carbon/assets`

`carbon-mgmt/*`、`energy-carbon/*`、平台管理、权限管理、团队、用户、数据管理和大屏路由不作为本阶段页面级迁移目标。只有当这些文件被上述菜单页面直接嵌入为业务组件时，才允许做必要的兼容调整。

本路线图的目标是：

1. 补齐后台产品级 tokens。
2. 统一基础组件和页面模板。
3. 先试点 `/carbon/accounting` 与 `/energy/analysis`。
4. 确认后批量迁移，而不是逐页手工重写。

## 1. 视觉方向判断

### 1.1 不做什么

- 不做全局深色工业风。
- 不做发光边框、网格背景、粒子、3D 管道作为后台主视觉。
- 不用大段说明文案填空。
- 不把每页都做成 dashboard。
- 不让 shadcn 默认 Card 风格成为产品主视觉。

### 1.2 做什么

- 浅色、高密度、低装饰的企业后台基底。
- 深色只用于实时监控、值班看板、报警中心等特殊场景。
- 用细分隔线、紧凑表格、统一状态、清晰 hierarchy 建立“工业软件可靠感”。
- 用 Context Bar、Table Toolbar、Status Badge、Audit Timeline 等组件统一业务表达。
- 图表强调单位、口径、来源和钻取，不强调“酷”。

## 2. Phase 0：资产盘点与视觉冻结

目标：停止继续逐页自由发挥，先盘点现状。

### 2.0 试点复盘修正

第一轮 `/carbon/accounting` 与 `/energy/analysis` 试点暴露出两个必须先修正的系统问题：

1. Page Header 仍然偏大，并且出现了面包屑 / 顶栏 / eyebrow / title 的语义重复。
2. 图表只迁移了外层页面结构，没有建立统一图表主题，仍然带有各图表组件自行定义颜色和样式的问题。

当前修正方向：

1. `AdminPageHeader` 已收敛为紧凑标题、状态 / meta、操作，不再默认渲染 eyebrow 或 description。
2. `ChartPanel` 与 `createAdminChartOption()` 已建立，后续图表迁移必须删除页面内散落的颜色、tooltip、legend、axis 和 grid 样式。
3. `AdminTableToolbar`、`AdminDataTable` 与 `AdminTableStateRow` 已建立，下一步应优先迁移高频 Ledger / CRUD 页面，而不是继续复制旧 Card 表格。

因此下一轮不得继续按页面自由美化。必须先用这些组件修正试点页，再批量迁移 Ledger、Analysis、Audit 三类高频页面。

### 2.0.1 标题区专项冻结

问题判断：

- 标题上方重复小副标题是当前后台最明显的“AI 模板感”来源之一。
- 大标题区挤压首屏业务数据，让后台看起来像营销页或介绍页。
- `meta` 被滥用为另一种 description，会重新制造重复文案。

冻结规则：

- `AdminPageHeader` 不接受 eyebrow / description。
- 页面内容区只允许一个 page title。
- 导航层级由 shell、breadcrumb、sidebar 表达，不在内容标题区重复。
- `meta` 只放机器可审计事实，例如周期、组织、权限范围、锁定状态、更新时间。
- 超过三个页面动作时，只保留一个主动作，其余进入 toolbar 或更多菜单。

验收方式：

```bash
rg -n "eyebrow=|description=|CardDescription|meta=\".*(管理|中心|平台|用于|帮助|说明)" src/js/web/src/routes src/js/web/src/components
rg -n "<AdminPageHeader" src/js/web/src/routes src/js/web/src/components
```

截图检查：

- 768px 高度视口中，标题区不应形成 hero。
- 无 ContextBar 时，内容标题区目标高度 48px 到 64px，极限 80px。
- 第一屏必须露出主要数据区、表格或图表，而不是只看到标题和说明。

### 2.0.2 图表主题专项冻结

问题判断：

- 当前图表技术栈 `echarts` / `echarts-for-react` 本身足够支持统一视觉。
- 现状问题是各页面或组件自行定义颜色、tooltip、legend、axis、grid，导致同一平台出现多个 BI 风格。
- 只把图表包进统一 Card 不够，必须把 ECharts option 的视觉字段收回共享层。

冻结规则：

- 普通后台路由不直接渲染 `ReactECharts`，必须经由 `ChartPanel` 或共享图表 wrapper。
- 趋势、排行、构成、仪表盘、桑基、热力图、组合图都必须有共享 builder。
- 页面只传数据、字段名、单位、来源、更新时间、阈值和钻取行为。
- 页面不得定义局部 palette、tooltip 壳、legend 样式、axis 样式、grid 样式、series 装饰样式。
- 图表说明文案默认删除，用 title、unit、source、updatedAt、legend、axis、tooltip、drilldown 表达。

验收方式：

```bash
rg -n "ReactECharts|echarts-for-react" src/js/web/src/routes src/js/web/src/components
rg -n "CHART_COLORS|PIE_COLORS|color: \\[|color: \"#|backgroundColor: \"#" src/js/web/src/routes src/js/web/src/components
rg -n "tooltip: \\{|legend: \\{|grid: \\{|axisLabel: \\{|splitLine: \\{|itemStyle: \\{" src/js/web/src/routes src/js/web/src/components
```

截图检查：

- 趋势、排行、构成、异常图的 palette、tooltip、legend、轴线和 panel shell 属于同一系统。
- 图表没有默认 ECharts 蓝、随机 pie 色或高饱和看板色。
- 每个分析图至少能看到单位、来源、更新时间或明确的业务口径之一。

### 2.1 动作

- 盘点所有后台路由。
- 给每个路由标注 archetype。
- 盘点现有 tokens、组件、重复样式。
- 盘点所有状态文案、badge 颜色、表格列格式。
- 选出高频业务页面和低频配置页面。

### 2.2 输出

- `admin-route-inventory.md`
- `component-inventory.md`
- `status-taxonomy.md`
- `migration-candidate-list.md`

### 2.3 验收

- 所有页面都有 archetype。
- 所有状态都有归属语义。
- 不再新增临时页面布局。

## 3. Phase 1：Tokens 补齐

目标：建立能支撑高密度后台的视觉变量。

### 3.1 颜色 tokens

建议分层：

```ts
const adminColors = {
  bg: {
    app: 'hsl(var(--admin-bg-app))',
    page: 'hsl(var(--admin-bg-page))',
    panel: 'hsl(var(--admin-bg-panel))',
    subtle: 'hsl(var(--admin-bg-subtle))',
  },
  border: {
    default: 'hsl(var(--admin-border))',
    strong: 'hsl(var(--admin-border-strong))',
    focus: 'hsl(var(--admin-border-focus))',
  },
  text: {
    primary: 'hsl(var(--admin-text-primary))',
    secondary: 'hsl(var(--admin-text-secondary))',
    muted: 'hsl(var(--admin-text-muted))',
    inverse: 'hsl(var(--admin-text-inverse))',
  },
  status: {
    draft: 'hsl(var(--status-draft))',
    pending: 'hsl(var(--status-pending))',
    success: 'hsl(var(--status-success))',
    warning: 'hsl(var(--status-warning))',
    danger: 'hsl(var(--status-danger))',
    locked: 'hsl(var(--status-locked))',
    inactive: 'hsl(var(--status-inactive))',
  }
}
```

颜色原则：

- 主色只用于主操作、焦点、选中状态。
- 状态色只用于状态语义。
- 背景大面积使用中性灰白，不使用蓝黑渐变。
- 表格分隔线要轻，但足够可读。

### 3.2 字体与数字 tokens

建议：

- 后台基础字号：13px 或 14px。
- 表格字号：13px。
- KPI 数字：20px 到 28px，不宜过大。
- 数字使用 tabular nums。
- 单位和口径说明使用 muted text。

### 3.3 间距与密度 tokens

建议：

```ts
const adminDensity = {
  pagePadding: '16px',
  sectionGap: '12px',
  panelPadding: '12px',
  tableRowCompact: '36px',
  tableRowDefault: '44px',
  toolbarHeight: '40px',
  filterHeight: '40px',
}
```

### 3.4 Radius 与 Shadow

- 企业后台卡片 radius 建议 6 到 8px。
- 尽量少用 shadow，更多依靠边框和背景层级。
- Drawer、Popover、Dropdown 可使用轻阴影。
- 不使用大面积玻璃拟态。

## 4. Phase 2：基础组件建设

目标：让“同类页面长得像同一个产品”。

### 4.1 必做组件

1. `AdminShell`：左导航、顶部栏、内容区。
2. `AdminPageHeader`：紧凑标题、状态、主操作、次操作；默认不显示 eyebrow / description。
3. `ContextBar`：业务上下文筛选。
4. `FilterDrawer`：高级筛选。
5. `DataTable`：统一表格封装。
6. `TableToolbar`：搜索、列配置、密度、导入导出、批量操作。
7. `StatusBadge`：全局状态体系。
8. `QualityBadge`：数据质量体系。
9. `MetricStrip`：KPI strip。
10. `ChartPanel`：统一图表容器。
11. `createAdminChartOption` / `adminChartTheme`：统一 ECharts 主题、轴线、网格、tooltip、legend、series 样式。
12. `ObjectDetailDrawer`：列表详情抽屉。
13. `AuditTimeline`：审核和变更记录。
14. `EvidenceUploader`：证据附件。
15. `ImportWizard`：导入流程。
16. `FactorSelector`：因子匹配。
17. `CalculationTrace`：计算追踪。
18. `EmptyState` / `ErrorState`：状态页。

### 4.2 组件约束

- `Card` 不直接在业务页面裸用，必须包进 `AdminPanel` 或 `ChartPanel`。
- 所有表格必须通过 `DataTable`。
- 所有状态必须通过 `StatusBadge`。
- 所有主筛选必须通过 `ContextBar`。
- 所有导入必须通过 `ImportWizard`。
- 所有证据附件必须通过 `EvidenceUploader`。
- 所有页面标题必须通过 `AdminPageHeader`，并遵守“无重复 eyebrow、无默认 description”的紧凑规则。
- 所有 ECharts 必须通过 `ChartPanel` 和统一 theme / option factory，不允许页面组件直接定义全量视觉 option。

### 4.3 组件 API 示例

```tsx
<AdminPageHeader
  title="活动数据台账"
  status={<StatusBadge status="reviewing" />}
  primaryAction={{ label: '新增活动数据', onClick: openCreate }}
  secondaryActions={[
    { label: '导入', onClick: openImport },
    { label: '导出', onClick: exportRows },
  ]}
/>
```

```tsx
<ContextBar
  value={filters}
  onChange={setFilters}
  fields={[
    { key: 'period', label: '周期', type: 'monthRange' },
    { key: 'orgId', label: '组织', type: 'orgTree' },
    { key: 'scope', label: 'Scope', type: 'select' },
    { key: 'status', label: '状态', type: 'statusSelect' },
  ]}
/>
```

## 5. Phase 3：页面模板建设

目标：把 archetype 变成可复用页面模板。

### 5.1 WorkbenchTemplate

适用：工作台、待办中心、异常中心。

区块：

- Header
- Context
- KPI strip
- Task queue
- Exception list
- Recent activity

### 5.2 LedgerTemplate

适用：活动数据、能耗数据、设备测点、因子、证据、预算。

区块：

- Header
- Context / Filter
- Toolbar
- Table
- Pagination
- Detail drawer

### 5.3 AnalysisTemplate

适用：能源分析、碳排分析、能效对标、预算偏差。

区块：

- Header
- Context
- Saved views
- KPI strip
- Chart grid
- Breakdown table
- Drilldown drawer

Header 要求：

- 顶部栏或面包屑显示模块路径，例如“能源运营 / 用能分析”。
- 页面内容区只显示“用能分析”一个标题。
- 不在标题下方显示“能源运营”或解释性段落。

### 5.4 AuditTemplate

适用：碳核算、审核、证据、报告锁定。

区块：

- Header
- Status flow
- Summary strip
- Validation list
- Evidence panel
- Calculation trace
- Audit timeline
- Action bar

### 5.5 ReferenceDataTemplate

适用：企业档案、组织边界、区域、设备、因子、标准来源。

区块：

- Header
- Search / Filter
- Master list
- Detail panel
- Version / Impact preview

### 5.6 SettingsTemplate

适用：权限、字典、公式、模板、规则、集成。

区块：

- Settings navigation
- Section header
- Form sections
- Preview / Test
- Change log

## 6. Phase 4：两个试点页面

### 6.1 `/carbon/accounting`

目标：把碳核算从普通看板改为审核型业务页面。

建议信息架构：

1. Header：核算批次、周期、组织、状态、主操作“提交审核 / 通过 / 驳回”。
2. Context Bar：企业、组织边界、核算周期、Scope、口径。
3. Status Flow：草稿、校验、待审核、已通过、已锁定。
4. Summary Strip：排放总量、活动数据完整率、因子匹配率、异常数、证据缺失数。
5. Tabs：
   - 活动数据
   - 因子匹配
   - 计算结果
   - 异常校验
   - 核查证据
   - 审核日志
6. Right Rail：当前处理人、风险提示、下一步动作。

重点组件：

- `AuditTemplate`
- `StatusFlow`
- `CalculationTrace`
- `EvidenceUploader`
- `QualityBadge`
- `FactorSelector`

验收标准：

- 页面能解释每个排放数从哪里来。
- 每个异常有处理入口。
- 因子有来源、版本和适用范围。
- 证据与活动数据有关联。
- 审核动作有原因和留痕。

### 6.2 `/energy/analysis`

目标：把能源分析从卡片堆叠改为分析型页面。

建议信息架构：

1. Header：能源分析、保存视图、导出。
2. Context Bar：周期、组织、区域、能源介质、设备、粒度。
3. KPI Strip：总能耗、单位产值能耗、峰谷比、同比、异常点数。
4. Chart Grid：
   - 能耗趋势
   - 分项构成
   - 尖峰谷平
   - 区域 / 设备 Top
   - 异常事件 overlay
5. Bottom Table：异常明细或测点明细。
6. Drilldown Drawer：原始数据、测点、设备、关联事件。

重点组件：

- `AnalysisTemplate`
- `ChartPanel`
- `MetricStrip`
- `SavedViewSelector`
- `AnomalyTable`
- `DrilldownDrawer`

验收标准：

- 每个图表有单位、口径、更新时间。
- 图表能钻取到明细。
- 筛选条件可保存。
- 空状态能说明缺数据、未接入或筛选无结果。
- 不使用装饰性大屏元素。

## 7. Phase 5：批量迁移策略

### 7.1 迁移顺序

1. 全局 shell 和 tokens。
2. 状态体系和 DataTable。
3. 高频 Ledger 页面。
4. 核算 / 审核页面。
5. 分析页面。
6. 主数据页面。
7. 配置页面。
8. 低频页面收尾。

当前标题 / 图表专项修正的执行顺序：

1. 标题区 pass：删除重复 eyebrow、副标题、header 说明文案，拒绝把 `meta` 当成 description 使用。
2. 图表层 pass：先把 ECharts 视觉 option 收回 `admin-chart-theme.ts` 或共享 builder，再改页面布局。
3. 表格 / 面板 pass：把裸 `Card` 表格壳替换为 `AdminPanel`、`AdminTableToolbar`、`AdminDataTable`、`AdminTableStateRow`。
4. 截图 pass：至少检查一个 Ledger、一个 Analysis、一个 Audit、一个 Reference Data 页面，桌面高度以 768px 为基准。

不要从逐页装饰开始。当前目标是减少能表达视觉风格的位置，让标题、图表、表格壳都回到共享系统。

### 7.2 页面迁移步骤

每个页面按以下步骤迁移：

1. 标注 archetype。
2. 抽出数据字段和操作。
3. 替换 PageHeader。
4. 替换 ContextBar / FilterBar。
5. 替换 DataTable 或 ChartPanel。
6. 接入 StatusBadge / QualityBadge。
7. 补空状态和错误状态。
8. 补详情 drawer 或详情页。
9. 补审计字段。
10. 回归测试。

标题区迁移补充步骤：

- 检查顶栏、面包屑、PageHeader 是否重复表达同一语义。
- 删除默认 eyebrow 和 description。
- 检查 `AdminPageHeader meta` 是否只是另一种副标题；如果是，删除或改为状态 / 周期 / 组织 / 数据更新时间。
- 把必要上下文下沉到 ContextBar、status badge、表格列或 audit footer。
- 控制内容标题区高度：无 ContextBar 时 48px 到 64px，极限不超过 80px。
- 截图确认第一屏标题区高度没有挤压业务内容。

标题区扫描命令：

```bash
rg -n "PageHeader|AdminPageHeader|eyebrow=|description=|CardDescription|meta=\".*(管理|中心|平台|用于|帮助|说明)" src/js/web/src/routes src/js/web/src/components
rg -n "<h1|<h2" src/js/web/src/routes/_app src/js/web/src/components
```

标题区验收标准：

- 内容区只出现一个页面标题。
- 没有标题上方的小副标题。
- Header 不超过 80px，除非包含真实的状态 / 操作换行。
- 首屏必须露出业务数据、表格或图表。

图表迁移补充步骤：

- 先替换为 `ChartPanel`。
- 再把图表 option 接入 `createAdminChartOption()`。
- 移除页面内硬编码颜色、tooltip 样式、legend 样式、grid 样式。
- 把趋势、排行、构成、仪表盘、桑基、热力图沉淀为共享 chart builder，不在 route 组件里写视觉 option。
- 删除 chart description prose；用 title、unit、source、updatedAt、axis、legend 和 tooltip 表达。
- 截图确认趋势、构成、排行、异常图表属于同一视觉体系。

图表层扫描命令：

```bash
rg -n "ReactECharts|echarts-for-react" src/js/web/src/routes src/js/web/src/components
rg -n "CHART_COLORS|PIE_COLORS|color: \\[|color: \"#|backgroundColor: \"#" src/js/web/src/routes src/js/web/src/components
rg -n "tooltip: \\{|legend: \\{|grid: \\{|axisLabel: \\{|splitLine: \\{|itemStyle: \\{" src/js/web/src/routes src/js/web/src/components
```

图表层验收标准：

- 普通后台路由不直接拥有 ECharts renderer。
- 页面不定义视觉 option，只传数据、单位、来源、更新时间、阈值和钻取。
- 新图表类型先进入共享 builder，再进入页面。
- 趋势、排行、构成和异常图的 palette、tooltip、legend、axis、grid 属于同一视觉体系。

### 7.3 降低成本策略

- 先不重写业务逻辑，只替换布局外壳和基础组件。
- 表格列配置逐页迁移，但表格壳统一。
- 状态枚举先做兼容映射，再逐步清理后端枚举。
- 分析页先统一 ChartPanel，不急着统一所有图表库细节。
- 导入流程先选一个高频对象试点，稳定后复制。

## 8. 视觉 QA 检查表

每个页面上线前检查：

- 页面是否归属于明确 archetype？
- Header、Context、Toolbar、Content 顺序是否统一？
- 是否出现无来源的大段说明文案？
- Header 是否重复显示模块名 / 页面名？
- Header 是否过高导致首屏业务内容下移？
- 是否裸用 shadcn Card 拼页面？
- 是否出现无单位 KPI？
- 是否出现无口径图表？
- 图表颜色、tooltip、legend、axis 是否来自统一 theme？
- 是否出现自定义状态色？
- 表格数值是否右对齐？
- 空状态是否有下一步动作？
- 错误状态是否可理解？
- 审计字段是否完整？
- 危险操作是否二次确认？
- 深色或发光效果是否有明确场景理由？

## 9. 技术落地建议

### 9.1 Tailwind 层

新增 admin token class：

```css
.admin-page {
  @apply min-h-screen bg-[hsl(var(--admin-bg-page))] text-[hsl(var(--admin-text-primary))];
}

.admin-panel {
  @apply rounded-md border bg-[hsl(var(--admin-bg-panel))];
}

.admin-toolbar {
  @apply flex h-10 items-center gap-2 border-b px-3;
}

.admin-table-density-compact tr {
  height: var(--admin-table-row-compact);
}
```

### 9.2 shadcn 层

保留 shadcn 作为底层组件库，但业务页面不直接由 shadcn primitives 拼装。建议分三层：

1. Primitive：Button、Input、Select、Dialog、Table。
2. Admin Component：DataTable、ContextBar、StatusBadge、ChartPanel。
3. Page Template：LedgerTemplate、AnalysisTemplate、AuditTemplate。

### 9.3 状态枚举层

建立统一映射：

```ts
export const statusMeta = {
  draft: { label: '草稿', tone: 'neutral' },
  submitted: { label: '已提交', tone: 'info' },
  reviewing: { label: '审核中', tone: 'warning' },
  approved: { label: '已通过', tone: 'success' },
  rejected: { label: '已驳回', tone: 'danger' },
  locked: { label: '已锁定', tone: 'locked' },
  inactive: { label: '已停用', tone: 'muted' },
}
```

### 9.4 图表层

`ChartPanel` 应包住图表库，统一处理：

- 标题
- 副标题 / 口径
- 单位
- 时间范围
- 数据来源
- 加载状态
- 空状态
- 错误状态
- 导出
- 钻取

本项目图表技术栈为 `echarts` / `echarts-for-react`，支持以下全局自定义能力：

- `echarts.registerTheme()` 注册工业能碳后台主题。
- 统一 `color` palette。
- 统一 `grid`、`axisLine`、`axisLabel`、`splitLine`。
- 统一 `tooltip` 背景、边框、字号、数值格式。
- 统一 `legend` 位置、图标和文字样式。
- 统一 line / bar / pie / gauge / sankey series 样式。
- 统一 loading、empty、error、drilldown 和 export action。

`src/js/web/src/components/admin-ui/chart-panel.tsx` 和 `src/js/web/src/lib/admin-chart-theme.ts` 已建立。后续迁移必须逐步删除 `components/carbon/analytics-panels.tsx`、能源分析组件和其他分析页中散落的 `CHART_COLORS`、`PIE_COLORS`、硬编码 hex 颜色、局部 tooltip / legend / axis 样式。

迁移完成的图表组件必须满足：

- 图表容器来自 `ChartPanel`。
- ECharts option 经过 `createAdminChartOption()`。
- 颜色优先使用 `adminChartPalette` 或语义 `colorKey`。
- 图表 panel 显示单位、来源、更新时间中的至少一个可审计信息。
- 截图确认图表不再像默认 ECharts 或独立 BI 插件。

## 10. 里程碑建议

### Milestone 1：规范冻结

输出：四份文档、route inventory、status taxonomy。  
时间：1 到 2 天。

### Milestone 2：组件底座

输出：AdminShell、紧凑 AdminPageHeader、ContextBar、DataTable、StatusBadge、MetricStrip、ChartPanel、adminChartTheme。
时间：3 到 5 天。

补充验收：

- `AdminPageHeader` 不支持 eyebrow / description。
- 标题区截图确认没有重复小副标题。
- `ChartPanel` 和 chart theme 已经覆盖 tooltip、legend、axis、grid、palette、empty/loading/error 基础状态。

### Milestone 3：碳核算试点

输出：`/carbon/accounting` AuditTemplate 版。  
时间：3 到 5 天。

补充验收：

- 碳核算页面不再通过 `Card` 堆叠解释性模块。
- 关键图表从共享 chart builder 生成，不在页面里定义视觉 option。
- 表格、审核状态、证据和审计字段复用 Admin UI。

### Milestone 4：能源分析试点

输出：`/energy/analysis` AnalysisTemplate 版。  
时间：3 到 5 天。

补充验收：

- 分析页图表统一使用 ChartPanel + chart builder。
- 图表标题区只保留标题、单位、来源、更新时间和操作。
- 截图对比趋势、排行、构成、异常图，确认属于同一视觉系统。

### Milestone 5：批量迁移

输出：高频台账页和主数据页统一。  
时间：按页面数量估算，每页 0.5 到 1.5 天。

## 11. 最终验收指标

产品体验指标：

- 同类页面结构一致。
- 用户能在 3 秒内识别页面类型和主操作。
- 用户能理解每个指标的单位、口径、来源。
- 台账页能支撑高频筛选、批量操作和导入导出。
- 审核页能完整追踪数据、因子、证据和状态。

工程指标：

- 新增页面不再裸拼 Card。
- 80% 以上列表页复用 DataTable。
- 80% 以上状态复用 StatusBadge。
- 关键页面拥有统一 EmptyState / ErrorState。
- 图表页复用 ChartPanel。
- 图表 option 不在页面组件里散落定义视觉样式。
- PageHeader 不重复显示面包屑已有的信息。
- 导入流程复用 ImportWizard。

视觉指标：

- 主色和状态色不混用。
- 表格密度统一。
- 卡片阴影和圆角统一。
- 深色模式仅在明确场景使用。
- 页面没有营销式填充文案。
- 标题区不形成 hero，占用高度可控。
- 图表风格统一，不出现默认 ECharts 或随机配色。
