# Backend Admin Visual Migration Candidate List

This list keeps the redesign scoped and repeatable.

## Phase 1: Foundation

- Added admin-specific CSS tokens for background, panels, borders, status, quality, scopes, and density.
- Added `components/admin-ui` for backend page composition.
- Added compact `AdminPageHeader`, `AdminPanel`, `ContextBar`, `MetricStrip`, `StatusBadge`, `ChartPanel`, `AdminTableToolbar`, `AdminDataTable`, and `AdminTableStateRow`.
- Kept bigscreen routes separate.
- Kept primitive `components/ui` neutral and reusable.

## Phase 2: Pilots

| Page | Archetype | Goal |
| --- | --- | --- |
| `/carbon/accounting` | Audit | Show accounting workflow, data readiness, scope entry points, pending review, and result access with shared Admin UI components. |
| `/energy/analysis` | Analysis | Replace local KPI cards and filter bar with shared context bar and metric strip; preserve existing API and chart logic. |

### Phase 2 Correction Before Further Page Migration

The first pilot is not accepted as final visual quality. Current correction status:

- Done: `/carbon/accounting` and `/energy/analysis` use compact `AdminPageHeader`.
- Done: the shared chart layer exists and `/energy/analysis` chart panels use `ChartPanel` plus `createAdminChartOption()`.
- Done: migrated admin route/domain chart call sites no longer pass page-local hex color values; chart series use semantic `colorKey`.
- Done: energy and carbon entry wrapper pages have started replacing repeated `PageHeader eyebrow` with `AdminPageHeader`.
- Done: authenticated app routes and shared admin components no longer render legacy `<PageHeader>`; public about page remains outside the backend admin standard.
- Done: `/carbon-mgmt/scope2` and `/carbon-mgmt/scope2-records` have compact headers.
- Done: `ScopeRecordPage` and `Scope2RecordsPanel` started using `AdminTableToolbar`, `AdminDataTable`, and `AdminTableStateRow`.
- Done: shared `CrudDataPage` now uses `AdminPageHeader`, `AdminPanel`, `AdminTableToolbar`, `AdminDataTable`, and `AdminTableStateRow`.
- Done: shared `ReadonlyLedgerPage`, `EventWorkbenchPage`, `TasksPage`, and the employee commute ledger use Admin UI table shells and unified table states.
- Done: common row detail drawers now prefer business field labels from configured columns/fields instead of showing only raw backend keys.
- Done: authenticated admin routes/components no longer render `AdminPageHeader` eyebrow/description or legacy `<PageHeader>` in the page body.
- Done: obvious `AdminPageHeader meta` misuse in platform placeholder/home pages has been removed; `meta` should not be used as a disguised subtitle.
- Done: shared chart visual option details for trend, combo trend, ranking, distribution, gauge, and sankey have moved from `components/carbon/analytics-panels.tsx` into `src/js/web/src/lib/admin-chart-theme.ts`.
- Done: `components/carbon/analytics-panels.tsx` no longer passes explanatory `description` strings into `ChartPanel`.
- Done: shared `components/carbon/analytics-panels.tsx` KPI, diagnostics, mini-stat, and ledger table wrappers now use `MetricStrip`, `AdminPanel`, `AdminDataTable`, and `AdminTableStateRow` instead of naked `Card`.
- Done: `components/carbon/energy-guide-pages.tsx` started migrating its highest-density energy consumption/intensity KPI and table shells to `MetricStrip`, `AdminPanel`, `AdminDataTable`, and `AdminTableStateRow`; remaining Card count dropped substantially but the file is not complete.
- Done: `components/carbon/energy-guide-pages.tsx` continued migration across energy analysis, energy flow, and energy balance table/KPI shells; it is no longer the largest Card hotspot.
- Done: `components/carbon/verification-panels.tsx` migrated verification project/evidence/issue/material/report KPI strips and table shells to `MetricStrip`, `MetricTile`, `AdminPanel`, `AdminDataTable`, and `AdminTableStateRow`; the file no longer imports or renders naked `Card`.
- Done: `components/carbon/product-footprint-panel.tsx` migrated product footprint tab panels, result KPI tiles, table shells, and empty rows to the shared Admin UI system; the file no longer imports or renders naked `Card`.
- Remaining: re-screenshot Scope / CRUD pages once a local authenticated server is available.
- Remaining: continue replacing naked `Card` table shells with `AdminPanel` / `AdminDataTable`.

## Phase 3: CRUD And Ledger Migration

- Convert `/data/*` master-data pages to Reference Data or Ledger templates.
- Convert `/carbon-mgmt/scope*` to Ledger template with status, quality, evidence, and audit fields.
- Remove raw object renderers from product-facing business pages.
- Standardize table density, toolbar actions, import/export, detail drawer, and empty state.
- Prioritize shared files before single pages: `components/platform/data-admin-pages.tsx`, `components/platform/master-data-workbench.tsx`, and `components/carbon/scope-record-page.tsx`.
- Keep detail drawers business-labeled; do not expose raw JSON / backend keys unless behind a technical section for administrators.

## Phase 4: Audit And Analysis Completion

- Convert verification, pending, and audit pages to Audit templates.
- Convert energy flow, balance, benchmark, budget, and intensity pages to Analysis templates.
- First migrate shared chart wrappers/builders, then migrate individual analysis routes.
- Continue moving any newly discovered visual ECharts option details into `src/js/web/src/lib/admin-chart-theme.ts` or a shared chart-builder module.
- Standardize chart panel headers, legends, units, source/freshness metadata, empty/loading states, and drilldown actions.
- Remove hardcoded chart palettes and page-local tooltip/legend/axis/grid styling from domain components.
- Remove explanatory `ChartPanel description` strings unless they represent a required legal/audit notice; use title, unit, source, updated time, axis labels, legends, and tooltip values instead.

## Phase 5: Regression Checks

- Run `bunx biome check .`.
- Run `bun run build`.
- Capture screenshots for at least desktop admin routes and verify there is no login-blocked visual regression where authenticated access is available.
- Review remaining pages against the no-AI-gradient, no-hero, no-explanation-copy, no-raw-json rules.
