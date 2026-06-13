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

### Surfaces

- Cards are for grouped business objects only.
- Prefer borders, dividers, section headers, and table density over stacked card boxes.
- Avoid heavy shadows and glowing effects.
- Inner controls should have tighter radius than outer containers.

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
