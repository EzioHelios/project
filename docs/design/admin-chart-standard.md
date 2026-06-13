# Admin Chart Standard

This project uses `echarts` and `echarts-for-react`. The chart stack supports centralized visual control; the product issue is not technical capability, but lack of a shared chart layer.

## Goals

- Charts should feel like industrial energy-carbon analysis tools, not default BI widgets.
- Chart visuals must be consistent across energy, carbon, audit, and reference-data pages.
- Chart panels must explain unit, scope, freshness, source, and drilldown path without adding prose-heavy page copy.

## Required Architecture

```text
domain data component
  -> ChartPanel
    -> shared chart builder / createAdminChartOption(baseOption)
      -> adminChartTheme / semantic chart tokens
        -> ReactEChartsCore
```

Do not let domain pages directly control chart color, axis style, tooltip style, legend style, panel surface, loading, or empty state.

The long-term target is not "every page remembers to copy the same ECharts option". The target is a two-level chart layer:

1. `ChartPanel` owns the panel shell, metadata row, empty/loading/error shape, and ECharts renderer.
2. Shared chart builders own visual options for trend, ranking, distribution, gauge, sankey, heat grid, and combo charts.

Domain pages should call the shared builder with data and business semantics. They should not assemble visual option objects from scratch.

## Implementation Status

- `src/js/web/src/components/admin-ui/chart-panel.tsx` exists and should be the default chart wrapper.
- `src/js/web/src/lib/admin-chart-theme.ts` exists and owns the shared palette, axis helpers, and `createAdminChartOption()`.
- Shared chart builders for trend, combo trend, ranking, distribution, gauge, and sankey have been added to `src/js/web/src/lib/admin-chart-theme.ts`.
- Domain pages should migrate toward this layer instead of continuing local ECharts styling. Heat-grid and any future specialized chart types should be added to the shared chart layer before page adoption.

## ChartPanel Contract

`ChartPanel` should own:

- Title
- Unit
- Metric scope
- Data source
- Updated time
- Loading state
- Empty state
- Error state
- Export action
- Drilldown action
- ECharts rendering shell

`ChartPanel` should not become a prose card. Avoid the `description` prop for ordinary chart explanation. If a sentence is needed to explain what a chart means, first ask whether the title, unit, source, tooltip, legend, axis name, or drilldown table is missing.

Recommended API:

```tsx
<ChartPanel
  title="用能系统排行"
  unit="kWh"
  source="电表聚合"
  updatedAt={summary?.totals.max_period}
  option={option}
  height={320}
  actions={<Button variant="ghost" size="sm">查看明细</Button>}
/>
```

## ECharts Theme Scope

The shared theme must define:

- `color`: ordered palette for energy, carbon, scope 1/2/3, warning, danger, neutral.
- `textStyle`: shared font family and size.
- `grid`: compact defaults that align chart content across panels.
- `axisLine`, `axisTick`, `axisLabel`, `splitLine`: low-noise industrial style.
- `legend`: consistent top/inline placement, circle icons, muted label color.
- `tooltip`: dark readable surface, tabular numbers, unit formatting.
- `series`: default line, bar, pie, gauge, sankey behavior.
- `loading`: non-decorative loading skeleton or muted spinner.

ECharts supports both registered themes and option-level composition. This project may use either implementation internally, but domain pages must see only shared builders and `ChartPanel`.

Required customization surface:

| Area | Centralized decision |
| --- | --- |
| Theme registration | Register one admin chart theme before rendering ECharts, or compose every option through `createAdminChartOption()`. Do not mix unthemed local options into migrated pages. |
| Palette | Semantic color order for energy, carbon, scope, cost, baseline, warning, danger, and muted comparison series. |
| Grid | Consistent left/right/top/bottom margins so charts align across a grid. |
| Axes | Muted axis line, no heavy ticks, low-noise split lines, tabular numeric labels, unit-aware names. |
| Tooltip | Dark readable surface, compact rows, marker + series + value + unit, optional source/freshness, no default white ECharts tooltip. |
| Legend | Stable top/inline placement, small icon, muted text, wrapped/scroll behavior for long series lists. |
| Series | Standard bar width, line symbol behavior, pie ring radius, gauge progress style, sankey node/link style, heat-grid cell treatment. |
| States | Shared loading, empty, error, drilldown affordance, and export action placement. |

## Domain Page Restrictions

Domain components may choose chart type, data series, labels, units, source, updated time, and drilldown behavior. They must not define the visual shell.

Do not define these inside domain pages:

- Page-local `CHART_COLORS`, `PIE_COLORS`, or arbitrary hex color arrays.
- Default ECharts blue as the implicit primary color.
- Tooltip background, border, shadow, font, or generic formatter shell unless the shared helper exposes the specific business formatter.
- Axis line, split line, grid, legend, series radius, bar width, symbol, label style, gauge progress style, sankey node color, or pie ring radius as visual decoration.
- Card-like chart wrappers outside `ChartPanel`.
- Explanatory `description` strings that tell the user why a chart exists.

Allowed domain-level option fields:

- `xAxis.data`, `yAxis.name`, `dataset`, `series.data`, `series.name`, `series.type`.
- Business labels and units.
- Mark lines / mark points when they represent real thresholds, alarms, baselines, or events.
- Drilldown event metadata.

If a chart needs a new visual style, first extend `admin-chart-theme.ts`, then consume the shared helper from the domain page.

## Refactor Plan

Chart cleanup must happen in this order:

1. Inventory local chart styling with source scans.
2. Add or extend a shared builder for the chart type.
3. Move visual option fields into `src/js/web/src/lib/admin-chart-theme.ts`.
4. Keep domain wrappers focused on data mapping, units, labels, source, freshness, thresholds, and drilldown metadata.
5. Render through `ChartPanel`.
6. Screenshot review the migrated page against at least one trend, ranking, composition, and anomaly chart.

Do not migrate charts by wrapping a visually unchanged local option in `ChartPanel`. That only changes the container and leaves the UI problem intact.

Recommended scans:

```bash
rg -n "CHART_COLORS|PIE_COLORS|color: \\[|color: \"#|backgroundColor: \"#" src/js/web/src
rg -n "tooltip: \\{|legend: \\{|grid: \\{|axisLabel: \\{|splitLine: \\{|itemStyle: \\{|label: \\{" src/js/web/src/routes src/js/web/src/components
rg -n "ReactECharts|echarts-for-react" src/js/web/src
```

Migration priority:

1. Shared carbon analytics wrappers in `components/carbon/analytics-panels.tsx`.
2. Energy-carbon analysis routes using `TrendChart`, `DistributionChart`, `CompositeTrendChart`, and `FlowGraph`.
3. Standalone admin charts in reference-data, factor, quality, monitor, and audit pages.
4. Public or non-admin charts only after backend admin routes are stable.

Bigscreen chart components are intentionally out of scope for this admin chart standard unless they are reused inside normal backend pages.

## Shared Builder Status

The current codebase has shared wrappers in `components/carbon/analytics-panels.tsx`, and their visual ECharts option details have been moved into `src/js/web/src/lib/admin-chart-theme.ts`. This keeps route and domain components focused on data mapping and business labels.

Current builders:

1. `createTrendChartOption(points, series, { periodKey })`
2. `createComboTrendChartOption(points, { bars, lines, leftAxisName, rightAxisName, periodKey })`
3. `createRankingChartOption(items, { unit, colorKey, limit })`
4. `createDistributionChartOption(items, { unit })`
5. `createGaugeChartOption(value, { suffix })`
6. `createSankeyChartOption(nodes, links, { categoryColorMap })`

Remaining builder:

1. `createHeatGridChartOption(cells, { xUnit, yUnit })`

Each builder must live in the shared chart layer or a shared domain chart package, not inside a route component.

## Palette Rules

Suggested semantic palette:

| Token | Use |
| --- | --- |
| `chart.energy` | Electricity and general energy volume. |
| `chart.carbon` | Carbon emission amount. |
| `chart.scope1` | Scope 1. |
| `chart.scope2` | Scope 2. |
| `chart.scope3` | Scope 3. |
| `chart.cost` | Cost / price. |
| `chart.warning` | Threshold risk. |
| `chart.danger` | Alarm / exceeded threshold. |
| `chart.neutral` | Baseline, average, inactive series. |

Do not use saturated blue as a catch-all. Do not introduce page-local pie color arrays.

## Chart Type Rules

| Business question | Preferred chart | Avoid |
| --- | --- | --- |
| Trend over time | Line, area, bar + line combo | Donut |
| Ranking | Horizontal bar, ranked list, Pareto | Pie with many slices |
| Composition | Stacked bar, 100% stacked bar | Donut unless 2-4 stable categories |
| Anomaly | Trend with event markers + table | Standalone scorecard |
| Flow | Sankey only when nodes/links are meaningful | Decorative 3D pipes |
| Equipment / region comparison | Bar, heat grid, tree table | Map unless geography matters |

## Interaction Rules

- Tooltip must show label, value, unit, time, and source where available.
- Clicking a chart should drill into a table, drawer, or route with filters applied.
- Legend interaction should not hide all data without an empty hint.
- Export should be available for analysis pages after the theme layer is stable.

## Acceptance Checklist

- No hardcoded chart palette inside page/domain components.
- All analysis charts use `ChartPanel`.
- All ECharts options pass through `createAdminChartOption()`.
- Axis, legend, tooltip, grid, loading, empty, and error states are visually consistent.
- Domain pages do not define visual `tooltip`, `legend`, `grid`, `axisLabel`, `splitLine`, `itemStyle`, or `label` blocks unless the field represents real business data or threshold labels.
- Chart panels use metadata fields for unit/source/freshness instead of explanatory descriptions.
- Screenshot review confirms charts no longer look like unstyled default ECharts.
- `rg "CHART_COLORS|PIE_COLORS|color: \"#|backgroundColor: \"#"` over migrated chart components does not reveal page-local visual palettes.
- `rg "tooltip: \\{|legend: \\{|grid: \\{|axisLabel: \\{|splitLine: \\{|itemStyle: \\{"` over migrated route components does not reveal page-local visual styling.
