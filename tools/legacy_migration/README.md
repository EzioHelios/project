# Legacy Migration Tools

Utilities in this directory support one-off migration and validation work from the legacy XTCK database.

Required environment variables vary by script:

- `OLD_DB_URL`: source legacy PostgreSQL connection string.
- `NEW_DB_URL`: target PostgreSQL connection string when comparing or copying between databases.
- `TARGET_TEAM_SLUG`: target tenant for the canonical XTCK inventory import.
- `DATABASE_URL`: target app database, used by scripts that load app settings.
- `SQL_DUMP_PATH`: path to a legacy SQL dump.
- `VIEWS_SQL_PATH`: optional output/input path for recreated views, defaulting to files in this directory.

These scripts are operational tooling, not application runtime code.

`migrate_all.py` is a compatibility entry point for `migrate_xtck_data.py`. The
canonical migration reads legacy Scope ledgers, upserts `GhgActivityRecord`, and
then completes parameter values and calculation runs through the warehouse
inventory use case. Legacy warehouse areas and equipment are remapped by stable
business code, while cumulative meter indices are streamed directly into
`MeterReadingFact` with a resumable `DataMigrationRun`. Set
`XTCK_SKIP_METERS=true` to defer the large meter migration, or
`XTCK_ACTIVITIES_ONLY=true` only when boundary and calculation completion must
be deferred.
