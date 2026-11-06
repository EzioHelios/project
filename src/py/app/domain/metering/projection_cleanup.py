"""Tenant-scoped, resumable cleanup of obsolete derived statistics (dry-run by default)."""

from __future__ import annotations

# SQL identifiers are fixed TABLES entries or quoted PostgreSQL catalog names. Values are bound.
# ruff: noqa: S608
import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class CleanupTable:
    name: str
    keys: str
    period: str


MAX_BATCH_SIZE = 5000

TABLES = (
    CleanupTable("dataapp_energyintervalfact", "source_system, source_record_id", "to_char(period_start, 'YYYY-MM')"),
    CleanupTable("dataapp_scope2meteraggregate", "ammeter_id, billing_month", "billing_month"),
    CleanupTable("metering_scope2_electricity_reconciliation", "billing_month", "billing_month"),
)

REFERENCE_TYPE_NAMES = {
    "dataapp_energyintervalfact": ("EnergyIntervalFact",),
    "dataapp_scope2meteraggregate": ("Scope2MeterAggregate", "scope2_meter_aggregate"),
    "metering_scope2_electricity_reconciliation": (
        "Scope2ElectricityReconciliation",
        "scope2_electricity_reconciliation",
    ),
}


class CleanupBlockedError(RuntimeError):
    """Unsafe or ambiguous cleanup must be resolved before any deletion."""


class ProjectionCleanup:
    def __init__(
        self, session: AsyncSession, *, month: str | None = None, batch_size: int = 2000, pause_ms: int = 50
    ) -> None:
        self.session = session
        self.team = session.info.get(TENANT_ID_SESSION_KEY)
        if self.team is None or session.info.get(TENANT_BYPASS_SESSION_KEY):
            msg = "Cleanup requires an explicit tenant without bypass"
            raise CleanupBlockedError(msg)
        if not 1 <= batch_size <= MAX_BATCH_SIZE:
            msg = "batch_size must be between 1 and 5000"
            raise ValueError(msg)
        if month is not None:
            from app.domain.metering.projection import month_window

            month_window(month)
        self.month, self.batch_size = month, batch_size
        self.pause_seconds = max(0, min(pause_ms, 10000)) / 1000
        self.params = {"team": str(self.team), "month": month, "batch": batch_size}

    def scope(self, table: CleanupTable) -> str:
        return "team_id = CAST(:team AS uuid)" + (f" AND {table.period} = :month" if self.month else "")

    async def _timeouts(self) -> None:
        await self.session.execute(text("SET LOCAL statement_timeout = '30s'"))
        await self.session.execute(text("SET LOCAL lock_timeout = '2s'"))

    async def _lock(self) -> None:
        key = int.from_bytes(hashlib.sha256(f"electricity:{self.team}".encode()).digest()[:8], signed=True)
        if not await self.session.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}):
            msg = "Tenant projection is running"
            raise CleanupBlockedError(msg)

    async def _digest(self, table: CleanupTable) -> str:
        digest = hashlib.sha256()
        # Exclude only compatibility/audit fields changed intentionally by normalization.
        rows = await self.session.stream(
            text(
                f"SELECT to_jsonb(t) - 'revision_no' - 'supersedes_id' - 'updated_at' AS payload "
                f"FROM {table.name} t WHERE {self.scope(table)} AND is_current ORDER BY id"
            ).execution_options(yield_per=self.batch_size),
            self.params,
        )
        try:
            async for row in rows:
                digest.update(json.dumps(row.payload, sort_keys=True, default=str).encode())
                digest.update(b"\n")
        finally:
            await rows.close()
        return digest.hexdigest()

    async def _references(self, table: CleanupTable) -> list[dict[str, Any]]:
        """Report hard and conventional polymorphic references; do not silently SET NULL."""
        refs: list[dict[str, Any]] = []
        catalog = (
            (
                await self.session.execute(
                    text("""
            SELECT ns.nspname AS schema, c.relname AS tab, a.attname AS col
            FROM pg_constraint fk JOIN pg_class c ON c.oid=fk.conrelid
            JOIN pg_namespace ns ON ns.oid=c.relnamespace
            JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=ANY(fk.conkey)
            WHERE fk.contype='f' AND fk.confrelid=to_regclass(:table)
        """),
                    {"table": table.name},
                )
            )
            .mappings()
            .all()
        )
        quote = self.session.bind.dialect.identifier_preparer.quote
        doomed = f"SELECT id FROM {table.name} WHERE {self.scope(table)} AND NOT is_current"
        for ref in catalog:
            if ref["tab"] == table.name and ref["col"] == "supersedes_id":
                continue
            count = await self.session.scalar(
                text(
                    f"SELECT count(*) FROM {quote(ref['schema'])}.{quote(ref['tab'])} "
                    f"WHERE {quote(ref['col'])} IN ({doomed})"
                ),
                self.params,
            )
            if count:
                refs.append({"table": ref["tab"], "column": ref["col"], "count": count})
        # Unknown application tables with record references are conservatively blocked on ID matches.
        # False positives must be reviewed, never interpreted as permission to erase source records.
        columns = (
            (
                await self.session.execute(
                    text("""
            SELECT c.table_schema, c.table_name, c.column_name FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.table_schema=c.table_schema AND t.table_name=c.table_name AND t.table_type='BASE TABLE'
            WHERE c.table_schema=current_schema() AND c.column_name IN ('record_id','source_record_id')
              AND data_type IN ('integer','bigint')
        """)
                )
            )
            .mappings()
            .all()
        )
        for ref in columns:
            table_columns = set(
                (
                    await self.session.scalars(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema=:schema AND table_name=:table"
                        ),
                        {"schema": ref["table_schema"], "table": ref["table_name"]},
                    )
                ).all()
            )
            tenant_filter = " AND team_id=CAST(:team AS uuid)" if "team_id" in table_columns else ""
            type_filter = ""
            discriminator = (
                "source_record_type"
                if ref["column_name"] == "source_record_id" and "source_record_type" in table_columns
                else "record_type"
                if ref["column_name"] == "record_id" and "record_type" in table_columns
                else None
            )
            if discriminator:
                accepted = ",".join(f"'{name}'" for name in REFERENCE_TYPE_NAMES[table.name])
                type_filter = f" AND {quote(discriminator)} IN ({accepted})"
            # These two documented generators use equipment IDs, not fact/reconciliation IDs.
            # See prepare_xiangtai_meter_activities.py and maintenance._generate_purchased_electricity.
            exclude_equipment_refs = (
                " AND NOT (coalesce(source_record_type,'')='meter_month' AND source_system='energy_fact' "
                "OR coalesce(source_record_type,'')='energy_interval_fact' AND source_system='generated')"
                if ref["table_name"] == "ghg_activity_record" and ref["column_name"] == "source_record_id"
                else ""
            )
            count = await self.session.scalar(
                text(
                    f"SELECT count(*) FROM {quote(ref['table_schema'])}.{quote(ref['table_name'])} "
                    f"WHERE {quote(ref['column_name'])} IN ({doomed})"
                    f"{tenant_filter}{type_filter}{exclude_equipment_refs}"
                ),
                self.params,
            )
            if count:
                refs.append(
                    {
                        "table": ref["table_name"],
                        "column": ref["column_name"],
                        "count": count,
                        "kind": "polymorphic_review_required",
                    }
                )
        if table.name == "dataapp_energyintervalfact":
            # Activity preparation scripts consume these IDs directly; do not erase their input.
            count = await self.session.scalar(
                text(
                    "SELECT count(*) FROM ghg_activity_record a WHERE a.team_id=CAST(:team AS uuid) "
                    "AND EXISTS (SELECT 1 FROM jsonb_array_elements_text("
                    "CASE WHEN jsonb_typeof(a.source_payload::jsonb->'fact_ids')='array' "
                    "THEN a.source_payload::jsonb->'fact_ids' ELSE '[]'::jsonb END) ref(id) "
                    f"JOIN {table.name} fact ON fact.id=CASE WHEN ref.id ~ '^[0-9]+$' THEN ref.id::bigint END WHERE fact.team_id=CAST(:team AS uuid) "
                    "AND NOT fact.is_current)"
                ),
                self.params,
            )
            if count:
                refs.append(
                    {
                        "table": "ghg_activity_record",
                        "column": "source_payload.fact_ids",
                        "count": count,
                        "kind": "source_fact_reference",
                    }
                )
            for tab, col in (
                ("carbon_material_allocation_run", "input_snapshot"),
                ("carbon_material_allocation_result", "energy_source_snapshot"),
            ):
                if not await self.session.scalar(text("SELECT to_regclass(:name)"), {"name": tab}):
                    continue
                count = await self.session.scalar(
                    text(
                        f"SELECT count(*) FROM {tab} WHERE team_id=CAST(:team AS uuid) "
                        f"AND {col}->'energy'->>'id' IN (SELECT id::text FROM {table.name} "
                        f"WHERE {self.scope(table)} AND NOT is_current) "
                        f"AND ({col}->'energy'->>'amount' IS NULL OR {col}->'energy'->>'source' IS NULL "
                        f"OR {col}->'energy'->>'key' IS NULL)"
                    ),
                    self.params,
                )
                if count:
                    refs.append({"table": tab, "column": col, "count": count, "kind": "incomplete_snapshot"})
        return refs

    async def report(self) -> dict[str, Any]:
        await self._timeouts()
        result: dict[str, Any] = {"team_id": str(self.team), "month": self.month, "tables": [], "blocked": False}
        for table in TABLES:
            scope = self.scope(table)
            counts = (
                (
                    await self.session.execute(
                        text(
                            f"SELECT count(*) AS total, count(*) FILTER (WHERE is_current) AS retained, "
                            f"count(*) FILTER (WHERE NOT is_current) AS obsolete, coalesce(max(id),0) AS cutoff "
                            f"FROM {table.name} WHERE {scope}"
                        ),
                        self.params,
                    )
                )
                .mappings()
                .one()
            )
            conflicts = await self.session.scalar(
                text(
                    f"SELECT count(*) FROM (SELECT {table.keys} FROM {table.name} WHERE {scope} "
                    f"GROUP BY {table.keys} HAVING count(*) FILTER (WHERE is_current) > 1) conflicts"
                ),
                self.params,
            )
            refs = await self._references(table)
            result["tables"].append(
                {
                    "table": table.name,
                    **counts,
                    "conflicts": conflicts,
                    "references": refs,
                    "current_digest": await self._digest(table),
                }
            )
            result["blocked"] |= bool(conflicts or refs)
        return result

    async def execute(
        self,
        *,
        apply: bool = False,
        writers_paused: bool = False,
        backup_verified: bool = False,
        backup_waived: bool = False,
    ) -> dict[str, Any]:
        if apply and not (writers_paused and (backup_verified or backup_waived)):
            msg = "Applying cleanup requires paused writers and either a verified backup or an explicit backup waiver"
            raise CleanupBlockedError(msg)
        await self._lock()
        before = await self.report()
        if not apply:
            await self.session.rollback()
            return {"dry_run": True, **before}
        if before["blocked"]:
            msg = "Cleanup has duplicate-current keys or unresolved references; inspect dry-run report"
            raise CleanupBlockedError(msg)
        await self.session.commit()
        deleted = {}
        for table, entry in zip(TABLES, before["tables"], strict=True):
            params = {**self.params, "cutoff": entry["cutoff"]}
            scope = self.scope(table) + " AND id <= :cutoff"
            total = 0
            while True:
                await self._timeouts()
                await self._lock()
                ids = (
                    await self.session.scalars(
                        text(
                            f"SELECT id FROM {table.name} WHERE {scope} AND NOT is_current ORDER BY id LIMIT :batch FOR UPDATE"
                        ),
                        params,
                    )
                ).all()
                if not ids:
                    break
                # Break self-revision links explicitly, with a tenant predicate on the update as well.
                await self.session.execute(
                    text(
                        f"UPDATE {table.name} SET supersedes_id=NULL WHERE team_id=CAST(:team AS uuid) "
                        "AND supersedes_id=ANY(:ids)"
                    ),
                    {**params, "ids": ids},
                )
                await self.session.execute(
                    text(f"DELETE FROM {table.name} WHERE {scope} AND NOT is_current AND id=ANY(:ids)"),
                    {**params, "ids": ids},
                )
                await self.session.commit()
                total += len(ids)
                await asyncio.sleep(self.pause_seconds)
            # Keep frozen legacy revision numbers so existing content hashes remain valid; remove only the chain.
            while True:
                await self._timeouts()
                await self._lock()
                ids = (
                    await self.session.scalars(
                        text(
                            f"SELECT id FROM {table.name} WHERE {scope} AND is_current "
                            "AND supersedes_id IS NOT NULL ORDER BY id LIMIT :batch FOR UPDATE"
                        ),
                        params,
                    )
                ).all()
                if not ids:
                    break
                await self.session.execute(
                    text(f"UPDATE {table.name} SET supersedes_id=NULL WHERE {scope} AND id=ANY(:ids)"),
                    {**params, "ids": ids},
                )
                await self.session.commit()
            await self.session.commit()
            deleted[table.name] = total
        after = await self.report()
        for old, new in zip(before["tables"], after["tables"], strict=True):
            if old["current_digest"] != new["current_digest"] or new["obsolete"] or new["conflicts"]:
                msg = "Post-cleanup validation failed; keep projection paused"
                raise CleanupBlockedError(msg)
        await self.session.commit()
        return {"dry_run": False, "before": before, "after": after, "deleted": deleted, "backup_waived": backup_waived}
