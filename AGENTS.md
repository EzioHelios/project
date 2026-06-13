# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Litestar Fullstack reference application — a production-ready fullstack web API built with Litestar (Python ASGI framework) and a React SPA frontend served via Vite. Uses PostgreSQL, SQLAlchemy 2.0, Advanced Alchemy, SAQ (async task queue with Redis), and Granian as the ASGI server.

## Common Commands

### Setup
```bash
make install          # Full install: uv venv, deps, bun install for frontend
cp .env.local.example .env
make start-infra      # Start PostgreSQL via Docker
app database upgrade   # Run Alembic migrations
app run               # Start the dev server (Granian)
```

### Testing
```bash
uv run pytest src/py/tests --quiet                     # Run all tests (uses xdist auto parallelism)
uv run pytest src/py/tests/unit -k "test_name"         # Run a single test by name
uv run pytest src/py/tests -m unit                     # Run only unit tests
uv run pytest src/py/tests -m integration              # Run only integration tests
```
Tests require a PostgreSQL instance (provided by `pytest-databases` Docker fixture). The conftest sets environment variables before any app imports — settings are cached on first import.

### Linting & Type Checking
```bash
make ruff             # Ruff check + format (Python)
make biome            # Biome lint (JS/TS, runs via bun in src/js/web)
make mypy             # mypy via dmypy daemon
make pyright          # pyright
make lint             # All: ruff + mypy + pyright + slotscheck + biome + codespell
make pre-commit       # Run all pre-commit hooks
```

### Build
```bash
make build            # Build emails + frontend assets + Python wheel
make types            # Export OpenAPI schema → generate TypeScript types/client
```

### Database Migrations (Alembic via Advanced Alchemy)
```bash
app database upgrade          # Apply migrations
app database downgrade        # Rollback
app database make-migrations  # Auto-generate a new migration
```

## Architecture

### Source Layout
```
src/
├── py/                       # Python backend (hatch source root)
│   ├── app/                  # Main application package
│   │   ├── server/           # ASGI app factory, core plugin, static files
│   │   ├── domain/           # Business domains (DDD-style)
│   │   ├── db/               # SQLAlchemy models, Alembic migrations, fixtures
│   │   ├── lib/              # Shared utilities: settings, email, crypto, logging, validation
│   │   ├── cli/              # CLI commands (extends Litestar CLI)
│   │   ├── config.py         # Instantiates all config objects from settings
│   │   └── utils/            # General-purpose helpers
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── conftest.py       # DB fixtures, env setup (must set env BEFORE app imports)
│       └── factories.py      # Polyfactory model factories
└── js/
    ├── web/                  # React SPA (Vite + TanStack Router + Tailwind CSS)
    │   └── src/routes/       # File-based routing (_app/ = authenticated, _public/ = guest)
    └── templates/            # React Email templates → compiled to static HTML
```

### Key Architectural Patterns

**App factory**: `src/py/app/server/asgi.py:create_app()` creates the Litestar instance with a single `ApplicationCore` plugin (`server/core.py`) that wires all routes, guards, dependencies, and sub-plugins.

**Domain modules**: Each domain (`accounts`, `teams`, `tags`, `carbon`, `system`, `admin`) follows a consistent structure:
- `controllers/` — Litestar route handlers (one file per concern, prefixed with `_`)
- `services/` — Business logic layer using Advanced Alchemy service/repository pattern
- `schemas/` — Pydantic models for request/response DTOs
- `deps.py` — Dependency providers for the domain
- `guards.py` — Route guards for authorization

**Database models**: All SQLAlchemy models live in `src/py/app/db/models/` (prefixed with `_`) and are re-exported from `db/models/__init__.py`. Models use Advanced Alchemy's `UUIDAuditBase`.

**Settings**: `src/py/app/lib/settings.py` — dataclass-based settings loaded from environment variables (via `python-dotenv`). Settings are cached via `@lru_cache` on `get_settings()`. Configuration objects are instantiated in `app/config.py`.

**Authentication**: JWT-based auth with refresh tokens, MFA (TOTP via pyotp), and OAuth support (httpx-oauth). Auth guard is in `domain/accounts/guards.py`.

**Frontend integration**: Litestar-Vite serves the React SPA. `make types` generates TypeScript API client from the OpenAPI schema using `@hey-api`.

## Multi-Tenant Development Notes

Carbon business data is team-scoped. The tenant infrastructure lives in `src/py/app/lib/tenancy.py` and is wired through `DatabaseSettings.get_config()` in `src/py/app/lib/settings.py`.

When adding a new team-owned business table:
- Inherit `TeamScopedMixin` on the SQLAlchemy model so it gets a non-null `team_id` FK to `team.id`.
- Add the table to the tenant migration path: create/backfill `team_id`, add the FK/index, and enable/force PostgreSQL RLS with a policy based on `current_setting('app.tenant_id', true)` and `current_setting('app.tenant_bypass', true)`.
- Prefer team-local uniqueness for business identifiers, for example `UniqueConstraint("team_id", "code", ...)` instead of global `unique=True`.
- Add focused integration tests for query isolation, automatic `team_id` assignment on writes, and cross-team write rejection.

Tenant context rules:
- Non-superusers can access an explicit team only if they are a member. If they belong to exactly one team and no team is requested, that team becomes the default tenant.
- Superusers bypass tenant filtering unless they explicitly request a team. Bypass writes without `team_id` fall back to `DEFAULT_TENANT_ID` for legacy compatibility.
- The request session stores tenant metadata in `session.info` and also sets PostgreSQL transaction-local settings. Use the injected `AsyncSession`; avoid ad hoc engine connections for tenant-scoped data because they may miss the tenant settings.

Query and raw SQL guidance:
- ORM queries against `TeamScopedMixin` models are filtered automatically by SQLAlchemy session events.
- Raw SQL and database views are protected only if the underlying tables have RLS and the query runs through the tenant-aware session. Do not disable RLS or use privileged database roles for application queries.
- Use `execution_options(include_all_tenants=True)` only for deliberate administrative reads, and keep those paths guarded by superuser checks.

Current scope:
- Tenant-scoped carbon models include enterprise info, monitor sectors/equipment, telemetry, alarms, energy values, carbon activity records, meter aggregates, and carbon audit logs.
- Identity/platform tables such as users, teams, roles, permissions, invitations, tags, factor libraries, factor categories, raw factor records, API result key mappings, and device types remain global unless a product requirement says otherwise.

## Code Conventions

- Python line length: 120 characters (ruff)
- Ruff selects ALL rules with specific ignores; uses Google-style docstrings
- Relative imports are banned — use absolute imports (`from app.domain.accounts...`)
- Known first-party packages for isort: `tests`, `app`
- Python source root is `src/py` (configured in hatch and ruff)
- Frontend uses bun as package manager, biome for linting
- Test markers: `unit`, `integration`, `slow`, `auth`, `email`, `oauth`, `services`, `models`, `endpoints`, `security`, `teams`

## Standards and Domain Knowledge Management

Energy and carbon modules must be grounded in traceable standards, policy documents, or explicit enterprise assumptions. Do not invent calculation formulas, benchmark thresholds, loss ratios, energy-balance paths, terminology, or optimization rules without recording the source.

When implementing or changing business logic for energy efficiency benchmarking, energy flow, energy balance, energy intensity, carbon accounting, product carbon footprint, or related evaluation pages:

- First check `docs/评价方案/` for existing standard research and terminology notes.
- If the needed standard is missing or stale, search authoritative sources before implementation. Prefer official sources such as 国家标准全文公开系统, 国家发展改革委, 国家市场监督管理总局, 工信部, 生态环境部, ISO/GHG Protocol official pages, and published industry standards.
- Record the standard name, standard number, status, implementation date, source URL, applicable module, and implementation implication in a repository Markdown note under `docs/评价方案/`.
- Any code-level formula or threshold must be traceable to one of:
  - a cited national/industry/international standard;
  - a cited policy document;
  - a clearly labeled enterprise assumption or sample/demo assumption.
- If using an enterprise or demo assumption, expose it as configuration or data with `source_name`, `standard_code`, `confidence_level`, `valid_from`, or equivalent traceability fields where practical.
- Product UI must not show developer-facing caveats, but data tables may show neutral audit fields such as source, standard, effective date, confidence, and applicable scope.
- If standards conflict, are unavailable, or only provide high-level principles, document the gap and avoid presenting the result as certified, official, or fully standards-compliant.

Priority references for current energy-management work include:

- GB/T 2589-2020 `综合能耗计算通则`
- GB/T 3484-2009 `企业能量平衡通则`
- GB/T 28749-2012 `企业能量平衡网络图绘制方法`
- GB/T 36714-2018 `用能单位能效对标指南`
- GB/T 36713-2018 `能源管理体系 能源基准和能源绩效参数`
- GB/T 13234-2018 `用能单位节能量计算方法`
- GB/T 23331-2020 `能源管理体系 要求及使用指南`
- GB/T 15316-2024 `节能监测技术通则`
- 国家发展改革委等部门发布的工业重点领域能效标杆/基准水平、重点用能产品设备能效先进/节能/准入水平文件。

## Frontend Product UI Rules

- Business pages should show data, controls, statuses, results, and actions. Do not show implementation notes, evaluation-guide copy, roadmap text, "how this page works" prose, or developer-facing calculation explanations in the product UI.
- Do not add visible tabs/cards/sections titled like `口径说明`, `计算口径`, `使用说明`, `功能说明`, `数据来源说明`, or similar explanatory surfaces. Put those details in docs, specs, admin configuration, or field-level data tables only when the business user needs to edit or audit the value itself.
- Page headers should be compact workbench headers: title + optional status/meta + actions. Do not add an eyebrow or repeated subtitle when the module path already appears in the shell, sidebar, or breadcrumb.
- Header descriptions are off by default. Do not use `meta` as a disguised subtitle. Use concise meta chips only for operational facts such as period, lock state, data freshness, tenant, or approval status.
- Chart and card descriptions should be omitted by default. Use concise labels, units, legends, filters, and table columns instead of prose explaining what the chart means.

### Backend Admin Visual Standard

The admin platform is an industrial energy-carbon operations system. It should feel restrained, reliable, audit-friendly, and built for repeated operational use. The bigscreen routes are a separate presentation surface and should not be used as the visual model for normal admin pages.

Before changing or creating admin UI, read the relevant design docs first:
- `docs/design/research/admin-ui-benchmark.md` — product research and benchmark rationale.
- `docs/design/admin-visual-standard.md` — visual direction and product UI guardrails.
- `docs/design/admin-page-archetypes.md` — page archetypes and layout rules.
- `docs/design/admin-crud-standard.md` — CRUD, table, form, import, detail, and audit patterns.
- `docs/design/admin-chart-standard.md` — chart theme, panel, palette, tooltip, axis, and drilldown rules.
- `docs/design/admin-visual-system-roadmap.md` — phased global refactor roadmap.

For UI/UX work, prefer global visual-system changes over one-off page rewrites. Start with tokens, shared components, page archetypes, and CRUD templates; only then migrate individual pages. Do not create a bespoke visual direction for a single route unless the design docs explicitly identify it as a separate surface.

Admin UI direction:
- Use cool industrial neutrals with one low-saturation energy-carbon accent.
- Prefer operational density, clear hierarchy, and auditability over decorative SaaS visuals.
- Do not use marketing hero layouts, neon cyber styling, green poster-style environmental branding, excessive gradients, or glow effects in backend pages.
- Do not use `Inter` as the intentional product font for the admin platform; use the shared font tokens from `src/js/web/src/styles.css`.
- Numeric values must use tabular numeric styling.

Navigation and page structure:
- Navigation labels must be short and business-facing. Avoid long sentence-like labels.
- Business modules should be grouped around workflows such as energy operations, carbon accounting, data ledgers, monitoring, factors/standards, and system administration.
- Permissions, scheduled jobs, API mappings, and low-level platform tools should not visually compete with core energy-carbon workflows.
- Page titles should not be duplicated between the application shell and the page body.
- Admin pages must use `AdminPageHeader` instead of adding page-local title blocks. The default header must not render an eyebrow or descriptive paragraph.
- Admin headers must fit a compact workbench rhythm: one title row plus optional actions/meta. If context needs more than one short row, move it to `ContextBar`, a table column, or an audit field.

Component rules:
- Cards are for grouped business objects only. Do not wrap every section in generic card boxes.
- Prefer dividers, table density, KPI strips, segmented controls, and compact status rows for operational pages.
- Empty/loading/error states must match the page structure and should not use generic spinners or casual copy.
- Do not expose backend field names, UUIDs, raw JSON, raw API names, or implementation identifiers unless the page is explicitly a system/debug tool.
- CRUD pages should follow `docs/design/admin-crud-standard.md`: ContextBar, TableToolbar, DataTable, DetailDrawer, ImportWizard, StatusBadge, and audit trail patterns before bespoke layouts.
- Chart pages must use `ChartPanel` plus `createAdminChartOption()` from `src/js/web/src/lib/admin-chart-theme.ts`; do not define page-local color arrays, default ECharts palettes, tooltip shells, legend styling, axis styling, chart card wrappers, or chart description prose in domain pages.
- When a chart needs a new visual behavior, add or extend a shared chart helper in `src/js/web/src/lib/admin-chart-theme.ts` or a shared chart wrapper first. Page components may pass data, labels, units, source, updated time, thresholds, and drilldown metadata only.
- Every admin route should map to an archetype from `docs/design/admin-page-archetypes.md` before implementation: Workbench, Ledger, Analysis, Audit, Reference Data, or Settings.
