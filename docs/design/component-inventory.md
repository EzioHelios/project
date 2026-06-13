# Backend Admin Component Inventory

This file records the reusable UI layer needed for a consistent industrial energy-carbon admin platform.

## Component Layers

| Layer | Location | Purpose |
| --- | --- | --- |
| Primitive UI | `src/js/web/src/components/ui` | Button, Card, Table, Tabs, Input, Select, Badge, Sidebar. These should stay generic. |
| Admin UI | `src/js/web/src/components/admin-ui` | Business-facing backend patterns: panels, context bars, metric strips, status badges, empty states, CRUD shells. |
| Domain Components | `src/js/web/src/components/carbon`, `platform`, `admin` | Domain logic, API data shaping, workflow-specific views. These should consume Admin UI instead of inventing local visual patterns. |

## Required Admin UI Components

| Component | Status | Usage |
| --- | --- | --- |
| `AdminPanel` | Added | Standard backend panel surface with compact border, header, actions, and content spacing. |
| `AdminSectionHeader` | Added | Small panel-local title/action row. |
| `ContextBar` | Added | Filter and scope controls. Use for dates, tenant/team, area, equipment, status, and query actions. |
| `MetricStrip`, `MetricTile` | Added | KPI groups with stable compact density and tabular numeric values. |
| `StatusBadge`, `QualityBadge` | Added | Shared operational status and data-quality language. |
| `AdminEmptyState` | Added | Quiet empty state for tables and panels without illustration or marketing copy. |
| `AdminPageHeader` | Added | Compact page title, status, meta, and actions. No eyebrow or default description. |
| `ChartPanel` | Added | Unified chart container with title, unit, source, updated time, empty state, and ECharts rendering shell. |
| `adminChartPalette`, `createAdminChartOption` | Added | Shared ECharts palette, grid, tooltip, legend, axis, and series defaults. |
| Shared chart builders | Partial | Trend, combo trend, ranking, distribution, gauge, and sankey option builders live in `admin-chart-theme.ts`; heat-grid remains to add when needed. |
| `AdminTableToolbar` | Added | Shared search, filter, refresh, reset, create, import/export, and batch-action row. |
| `AdminDataTable`, `AdminTableStateRow` | Added | Shared table frame and loading/empty/error rows for Ledger and Reference Data pages. |
| `CrudPageShell` | Planned | Page header, context bar, toolbar, table, detail drawer, and import action. |
| `ColumnVisibilityMenu` | Planned | Column visibility and ordering for high-density ledgers. |
| `DetailDrawer` | Planned | Read/edit detail surface with audit trail and related records. |
| `ImportWizard` | Planned | Upload, mapping, validation, preview, submit, result. |
| `AuditTrail` | Planned | Actor, action, before/after, evidence, and timestamp list. |

## Current Duplication To Remove

- Local KPI cards assembled from `Card`, `CardHeader`, and `CardContent`.
- Filter bars styled per page with ad hoc grid classes.
- Status labels rendered as plain strings or page-local `Badge` variants.
- Empty table rows written directly in each table.
- Raw JSON/object renderers in product pages.
- Page-level explanatory copy that belongs in documentation or configuration.
- Repeated page title context across top bar, breadcrumb, eyebrow, and content header.
- Chart colors, tooltip styles, legends, grids, and axis styles defined inside individual page components.

## Migration Rule

When editing a business page, first select the archetype from `docs/design/admin-route-inventory.md`, then compose the page from Admin UI components. Do not introduce a new card style, chart container style, status color, or filter bar unless it is first added to this inventory.

Page titles, CRUD tables, and charts are now hard gates:

- Do not add `eyebrow` to a page header unless there is no breadcrumb/top-bar context and the information is not duplicated.
- Do not pass `description` to `AdminPageHeader` for normal business pages; `AdminPageHeader` should not support prose descriptions.
- Do not use `meta` as a subtitle. `meta` is only for compact operational facts such as period, organization, lock state, freshness, permission scope, or approval status.
- Do not build table loading/empty/error rows inline. Use `AdminTableStateRow` so density, tone, and copy stay consistent.
- Do not add chart-specific color arrays or full visual `option` styling in domain pages. Extend `adminChartTheme` or a shared chart builder instead.
- Do not add chart prose descriptions by default. Use title, unit, source, updated time, axis labels, legends, tooltip values, and drilldown tables.
