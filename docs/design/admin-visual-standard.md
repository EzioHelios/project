# Backend Admin Visual Standard

This document defines the visual and product rules for the admin platform. The bigscreen routes are intentionally separate and are not governed by this standard.

## Product Direction

The admin platform is an industrial energy-carbon operations system. It should feel restrained, reliable, audit-friendly, and built for repeated operational use.

Core qualities:

- Operational before decorative.
- Dense enough for daily work, but not crowded.
- Traceable and audit-friendly.
- Business-facing language, not implementation language.
- One coherent admin product, independent from the bigscreen visual style.

Avoid:

- Generic SaaS card dashboards.
- Marketing hero layouts.
- Neon blue cyber dashboards outside bigscreen routes.
- Green environmental poster styling.
- Visible implementation notes, roadmap text, or developer-facing explanations.

## Visual System

### Palette

Use a cool industrial neutral base with one low-saturation energy-carbon accent.

- Background: cool off-white and pale blue-gray.
- Main text: graphite/navy, never pure black.
- Primary: deep industrial graphite.
- Accent: low-saturation carbon green or electric teal, used sparingly for active, verified, and positive states.
- Warning/risk: amber and red only for real operational state.

Chart colors must come from the shared energy-carbon palette. Do not let every chart invent its own palette.

### Typography

- Do not use Inter as the intentional product font.
- Use a high-quality sans stack suitable for Chinese/English enterprise UIs.
- Numeric values must use tabular numbers.
- Large page titles should be controlled and workbench-like, not marketing-scale.
- Keep labels short and scannable.

### Header Density

Backend page headers must be compact and single-purpose. The page title area should identify the current work surface, not repeat navigation context.

- Use one visible page title only.
- Do not show an eyebrow/subtitle above the title when the same context already appears in breadcrumb or sidebar.
- Do not render both `碳排放管理 / 碳排放核算` and another `碳核算 / 碳排放核算` block in the same first viewport.
- Default header height should stay compact: title row plus optional action row, not a marketing hero.
- Page description is off by default. Do not use `meta` as a second title line. Use metadata chips, status badges, or context fields instead of prose.
- If a page needs context, put it in `ContextBar`, breadcrumb, status badge, or audit footer.
- The page shell owns navigation context. `AdminPageHeader` owns only the current work surface title, status, meta facts, and actions.
- Do not add a small heading above the title to create hierarchy. In admin pages, that pattern is usually duplicated navigation, not useful information.

Header density budget:

- Content header target height: 48px to 64px when no `ContextBar` is present.
- Content header maximum height: 80px including wrapped actions. If it exceeds this, actions must move into a more menu or the context must move below the header.
- Title size: 24px to 28px. Do not use display or hero typography in admin routes.
- One optional meta row is allowed only for machine-auditable facts: period, organization, lock state, data freshness, approval state, or permission scope.
- Explanatory text such as "用于查看...", "帮助用户...", "当前页面..." is not header metadata.
- The header should not consume more than roughly 10% of a 768px-high viewport. If it does, the page is drifting toward a hero layout.
- Button groups should remain one row. If more than three actions are needed, keep one primary action and move the rest into secondary menu or toolbar actions.

Header hard gates:

- A migrated admin page must not pass `eyebrow` or `description` to `AdminPageHeader`.
- A migrated admin page must not keep a local `<h1>` / `<h2>` title block above or next to `AdminPageHeader`.
- `meta` cannot contain a module label, marketing noun, or helper sentence. It must be a factual value such as `2026 Q2`, `已锁定`, `上海工厂`, or `更新于 09:30`.
- If breadcrumb/sidebar/topbar already says "碳排放管理", the content header must not repeat "碳排放管理" as a small label.
- When screenshot reviewing a page, reject it if the first viewport is dominated by title copy instead of data, controls, table rows, or charts.

Header ownership rules:

| UI area | Owns | Must not own |
| --- | --- | --- |
| App shell / breadcrumb | Product area, module path, parent object path | Page-local status or business explanation |
| `AdminPageHeader` | Current page title, status badge, concise meta facts, primary actions | Eyebrow, long description, repeated module name |
| `AdminFilterBar` / `ContextBar` | Period, organization, scope, filters, operating context | Page title or explanatory copy |
| Table / audit footer | Source, standard, effective date, confidence, reviewer | Marketing or tutorial text |

Recommended compact header structure:

1. Breadcrumb or module path in the app top bar.
2. Content header with title, status, and actions.
3. Module-level tabs when the page has peer workflow views.
4. `AdminFilterBar` / `ContextBar` immediately below when filters or operating scope are needed.
5. `MetricStrip` below filters so KPI values clearly reflect the active filter state.
6. Tables, charts, detail panels, and secondary tabs in the content area.

Scaffold hard gates:

- New or migrated admin pages should use `AdminPageScaffold` when they combine tabs, filters, metrics, and content.
- Standard order is `AdminPageHeader -> primary TabsList -> AdminFilterBar/ContextBar -> MetricStrip -> content`.
- Do not place KPI cards above filters when the values are filter-dependent.
- Do not place module-level tabs below KPI cards. Tabs define the view; filters define the slice; metrics summarize the slice.
- Secondary tabs are allowed inside content panels only when they switch detail subsections for a selected object.

Anti-pattern:

```tsx
<TopBar>碳排放管理 / 碳排放核算</TopBar>
<PageHeader eyebrow="碳核算" title="碳排放核算" />
```

Preferred:

```tsx
<TopBar>碳排放管理 / 碳排放核算</TopBar>
<AdminPageHeader title="碳排放核算" status={<StatusBadge status="pending" />} />
```

### Surfaces

- Cards are for grouped business objects only.
- Prefer borders, dividers, section headers, and table density over stacked card boxes.
- Avoid heavy shadows and glowing effects.
- Inner controls should have tighter radius than outer containers.

### Charts

The project uses `echarts` / `echarts-for-react`, which supports global theme registration and option-level customization. Chart styling must be centralized.

- Do not define chart colors inside page components.
- Do not use default ECharts blue, random pie colors, or saturated dashboard palettes.
- Do not let chart cards use a visual style separate from `AdminPanel`.
- All charts must pass through `ChartPanel` and a shared `createAdminChartOption()` / `adminChartTheme`.
- Axes, grid, legend, tooltip, labels, loading, empty, and drilldown affordances must be consistent across analysis pages.
- Chart panel descriptions are off by default. Each chart should communicate through title, unit, source, updated time, legend, axis name, tooltip, and drilldown target.
- Page components may choose data, chart type, labels, units, thresholds, source, updated time, and drilldown behavior. They must not own visual option details.
- Pie/donut charts are allowed only when part-to-whole comparison is genuinely the task; prefer bar, stacked bar, trend, heat grid, and ranked lists for operational analysis.

ECharts customization is required, not optional. The shared chart layer must control:

- Palette order and semantic colors.
- Grid margins and chart content alignment.
- Axis line, tick, label, split line, and unit style.
- Tooltip surface, number formatting, unit formatting, source/freshness display, and marker style.
- Legend placement, icon, label color, disabled state, and overflow behavior.
- Line, bar, pie, gauge, sankey, heat-grid, and combo defaults.
- Loading, empty, error, drilldown, and export states.

Chart visual density budget:

- Normal analysis chart height: 280px to 360px.
- Compact chart height: 220px to 260px only when paired with a table or ranked list.
- Panel title row: one title plus optional unit/source/freshness/action metadata. No chart subtitle paragraph.
- Axis labels should stay readable at table-adjacent density; rotate labels only when truncation would be worse.
- A page with multiple charts should use one shared grid rhythm. Do not mix unrelated chart panel padding, legends, or tooltip treatments.

Chart hard gates:

- A migrated admin chart must not render `ReactECharts` directly from a route file.
- A migrated admin chart must not define `CHART_COLORS`, `PIE_COLORS`, local hex palettes, local tooltip shells, local legend styling, local axis styling, or local grid styling.
- `ChartPanel` alone is not sufficient. The option must be produced by `createAdminChartOption()` or a shared chart builder that itself uses the admin chart theme.
- If the chart type is not yet supported by the shared chart layer, add the shared builder first, then migrate the page.
- Each analysis chart must expose at least one audit/context field through panel metadata or axis/tooltip semantics: unit, source, updated time, period, scope, or data grain.
- Screenshot review must compare at least one trend, ranking, composition, and anomaly chart where available; they should clearly belong to the same admin product.

## Page Rules

Every business page should answer, within the first viewport:

- What object or period is being operated on?
- What is the current status?
- What requires action?
- What data or result supports the decision?
- What is the primary next action?

Do not use business pages for:

- "How this page works" prose.
- Calculation caveats.
- Implementation notes.
- Raw API debug output.
- Backend field names or UUIDs, unless the page is explicitly a system/debug page.

## Navigation

Navigation labels should be short, business-facing, and stable.

Recommended grouping:

- 工作台
- 能源运营
- 碳核算
- 数据台账
- 设备与监测
- 因子与口径
- 系统管理

Avoid placing permissions, cron jobs, API key mapping, and raw platform tools at the same hierarchy level as carbon accounting workflows.

## Page Archetypes

Use these archetypes instead of one-off page structures:

- `OverviewPage`: workbench overview, status, risks, actions.
- `LedgerPage`: searchable table, filters, imports, edits.
- `AnalysisPage`: compact filters, KPI strip, charts, ranked diagnostics.
- `AuditPage`: approvals, evidence, status history.
- `ReferenceDataPage`: factors, standards, source confidence, effective dates.

## Component Standards

- KPI numbers use tabular numeric styling.
- Tables should be compact and readable.
- Tabs are for peer workflow states, not explanatory sections.
- Empty, loading, and error states must match the page structure.
- Buttons should express command hierarchy: one primary action, secondary outline actions, tertiary text actions.
- Use icons only when they improve scanning; do not decorate every label.

## Vibe Coding Guardrails

When an agent creates or modifies admin UI:

1. Start from this standard and the existing component system.
2. Do not invent a new visual direction for a single page.
3. Do not add explanatory copy to fill whitespace.
4. Do not expose raw data structures to business users.
5. Prefer one clear page archetype over bespoke layout.
6. Verify the result with a screenshot before considering the UI done.

## V2 Theme and Domain System

The runtime theme, energy/carbon domain mapping, component variants, and chart builder contract are defined in [`admin-design-system-v2.md`](./admin-design-system-v2.md). This document remains the product-level visual direction; the V2 document is the implementation contract.
