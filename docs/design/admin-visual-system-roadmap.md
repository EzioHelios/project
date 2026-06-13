# 工业能碳后台视觉系统与重构路线图

调研日期：2026-06-13  
适用项目：工业能碳后台，React / Tailwind / shadcn 技术栈

## 0. 路线原则

后续重构不应从“每页做得更好看”开始，而应从“全局规则收口”开始。工业感不是深色和发光线，工业感是可靠、可追溯、状态明确、数据密度适中、操作成本低。

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
2. `AdminPageHeader`：标题、描述、状态、主操作、次操作。
3. `ContextBar`：业务上下文筛选。
4. `FilterDrawer`：高级筛选。
5. `DataTable`：统一表格封装。
6. `TableToolbar`：搜索、列配置、密度、导入导出、批量操作。
7. `StatusBadge`：全局状态体系。
8. `QualityBadge`：数据质量体系。
9. `MetricStrip`：KPI strip。
10. `ChartPanel`：统一图表容器。
11. `ObjectDetailDrawer`：列表详情抽屉。
12. `AuditTimeline`：审核和变更记录。
13. `EvidenceUploader`：证据附件。
14. `ImportWizard`：导入流程。
15. `FactorSelector`：因子匹配。
16. `CalculationTrace`：计算追踪。
17. `EmptyState` / `ErrorState`：状态页。

### 4.2 组件约束

- `Card` 不直接在业务页面裸用，必须包进 `AdminPanel` 或 `ChartPanel`。
- 所有表格必须通过 `DataTable`。
- 所有状态必须通过 `StatusBadge`。
- 所有主筛选必须通过 `ContextBar`。
- 所有导入必须通过 `ImportWizard`。
- 所有证据附件必须通过 `EvidenceUploader`。

### 4.3 组件 API 示例

```tsx
<AdminPageHeader
  title="活动数据台账"
  description="维护核算周期内的排放活动数据和证据。"
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
- 是否裸用 shadcn Card 拼页面？
- 是否出现无单位 KPI？
- 是否出现无口径图表？
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

## 10. 里程碑建议

### Milestone 1：规范冻结

输出：四份文档、route inventory、status taxonomy。  
时间：1 到 2 天。

### Milestone 2：组件底座

输出：AdminShell、PageHeader、ContextBar、DataTable、StatusBadge、MetricStrip、ChartPanel。  
时间：3 到 5 天。

### Milestone 3：碳核算试点

输出：`/carbon/accounting` AuditTemplate 版。  
时间：3 到 5 天。

### Milestone 4：能源分析试点

输出：`/energy/analysis` AnalysisTemplate 版。  
时间：3 到 5 天。

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
- 导入流程复用 ImportWizard。

视觉指标：

- 主色和状态色不混用。
- 表格密度统一。
- 卡片阴影和圆角统一。
- 深色模式仅在明确场景使用。
- 页面没有营销式填充文案。
