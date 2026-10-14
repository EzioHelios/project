# Backend Admin Route Inventory

This inventory maps the authenticated SPA routes to the page archetypes defined in `docs/design/admin-page-archetypes.md`.
Bigscreen routes are listed separately and must not inherit the normal backend admin visual system.

## Archetype Rules

- Workbench: cross-domain command center, shortcuts, exceptions, and current operating status.
- Ledger: operational records, intake tables, transaction-like business rows, and scoped CRUD.
- Analysis: charts, comparisons, diagnostics, benchmarking, strategies, and trend views.
- Audit: review queues, approval state, evidence, verification, locking, and exception handling.
- Reference Data: dictionaries, master data, emission factors, equipment catalogs, meters, mappings.
- Settings: identity, permission, tenant, schedules, profile, system configuration.

## Route Mapping

| Route family | Representative routes | Archetype | Migration note |
| --- | --- | --- | --- |
| `/home`, `/platform` | `/home`, `/platform` | Workbench | Use one-screen operational summary, current exceptions, and role-based shortcuts. |
| `/carbon/accounting` | `/carbon/accounting` | Audit | Pilot page. Use accounting workflow, data readiness, scope tabs, pending review, and locked-result states. |
| `/carbon/*` | `/carbon/assets`, `/carbon/supply-chain`, `/carbon/product-footprint`, `/carbon/verification` | Analysis / Audit | Keep analysis pages chart-led; verification pages audit-led. Remove marketing-style explanations. |
| `/carbon-mgmt/scope*` | Scope 1/2/3 records, bills, reconciliation, transport, waste | Ledger | Convert to ledger template with context bar, table toolbar, status badge, detail drawer, import path. |
| `/carbon-mgmt/pending`, `/carbon-mgmt/audit`, `/carbon-mgmt/verification` | Review and verification flows | Audit | Use review queue, evidence summary, decision actions, audit trail. |
| `/carbon-mgmt/factors`, `/carbon-mgmt/calculation-factors` | Factor libraries and calculation factors | Reference Data | Show source, standard, effective date, confidence, version, and applicability as auditable columns. |
| `/energy/analysis` | `/energy/analysis` | Analysis | Pilot page. Use context bar, metric strip, tabbed chart panels, anomaly table, strategy evidence. |
| `/energy/*` | consumption, flow, balance, benchmark, budget, intensity | Ledger / Analysis | Consumption is ledger; flow/balance/benchmark/budget/intensity are analysis pages. |
| `/energy-carbon/*` | monitor, alerts, quality, factors, flows, energy, carbon | Workbench / Analysis / Ledger | Split overview from operational subpages; avoid mixed dashboard card stacks. |
| `/data/company` | enterprise profile | Reference Data | Pilot-adjacent master-data page. Use field groups instead of raw object rendering. |
| `/data/monitor-area`, `/data/device-*`, `/data/terminals`, `/data/meter` | Organization, equipment, terminal, and meter catalogs | Reference Data | Use master-data CRUD template with ownership, status, and source columns. |
| `/data/energy-*`, `/data/production-*`, `/data/inbound`, `/data/outbound`, `/data/commute` | activity and production records | Ledger | Use ledger CRUD template with period, source, status, quality, and audit fields. |
| `/data/alarm-*`, `/data/video*` | alarm and video rules/events | Ledger / Settings | Events are ledger; rule configuration is settings. |
| `/data/api-key-mapping` | API key/result mappings | Reference Data | Treat as integration reference data with mapping state. |
| `/auth/*`, `/admin/*`, `/teams/*`, `/profile`, `/tasks/*` | users, roles, teams, schedules, audit | Settings | Keep compact enterprise-admin style; permissions and audit pages should expose traceable changes. |

## Bigscreen Exclusion

The following routes are presentation surfaces and remain outside the admin visual migration:

- `/bigscreen`
- `/bigscreen/carbon`
- `/bigscreen/intro`
- `/bigscreen/model`
- `/bigscreen/overview`
- `/bigscreen/power`

大屏使用统一路由并根据当前租户加载业务数据；不为演示场景单设客户可访问的大屏路由。

## First Migration Order

1. Global tokens and admin-ui components.
2. `/carbon/accounting` as the Audit archetype pilot.
3. `/energy/analysis` as the Analysis archetype pilot.
4. Shared CRUD shell for `/data/*` and `/carbon-mgmt/scope*`.
5. Settings pages and remaining analysis pages.
