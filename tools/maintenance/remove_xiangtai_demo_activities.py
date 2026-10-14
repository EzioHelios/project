"""Remove only the 67 reviewed synthetic Xiangtai activities, with backup and drift checks."""

# ruff: noqa: T201 - explicit maintenance plan and execution output.

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select, text

from app.db import models as m
from app.domain.accounts.deps import provide_users_service
from app.domain.ghg_inventory import models as g
from app.domain.metering.models import Scope2ElectricityReconciliation
from app.lib.deps import provide_services
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

TEAM_ID = UUID("00000000-0000-7000-8000-000000000001")
SNAPSHOT_SHA256 = "17513ceabfb65128e7354bd088add9de813349152b49f6d3091b4839ef67faab"
EXPECTED_COUNT = 67
EXPECTED_DERIVED_COUNT = 6


def require(condition: bool, message: str) -> None:
    """Stop rather than broaden the approved cleanup scope."""
    if not condition:
        raise ValueError(message)


def serialize(rows: list[g.GhgActivityRecord]) -> list[dict]:
    """Match the reviewed snapshot representation, including timestamps and payloads."""
    return json.loads(
        json.dumps(
            [{column.key: getattr(row, column.key) for column in row.__table__.columns} for row in rows], default=str
        )
    )


async def main(*, snapshot: Path, backup: Path | None, apply: bool) -> None:
    """Plan by default; apply is one tenant-scoped atomic transaction."""
    raw = snapshot.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SNAPSHOT_SHA256, "Reviewed snapshot hash mismatch")
    expected = sorted(json.loads(raw)["xiangtai"]["GhgActivityRecord"], key=lambda row: row["id"])
    require(len(expected) == EXPECTED_COUNT, "Expected exactly 67 reviewed activities")
    ids = [row["id"] for row in expected]
    codes = [row["record_code"] for row in expected]
    require(
        all(
            row["team_id"] == str(TEAM_ID)
            and row["source_system"] == "legacy_migration"
            and any(marker in (row["remarks"] or "") for marker in ("[demo_seed]", "[carbon_mvp_seed]"))
            for row in expected
        ),
        "Unexpected source in reviewed snapshot",
    )

    async with provide_services(provide_users_service) as (users,):
        session = users.repository.session
        session.info.update({TENANT_ID_SESSION_KEY: TEAM_ID, TENANT_BYPASS_SESSION_KEY: False})
        team = await session.get(m.Team, TEAM_ID)
        require(team is not None and team.name == "祥泰仓库", "Tenant identity changed")
        rows = list(
            (
                await session.scalars(
                    select(g.GhgActivityRecord)
                    .where(g.GhgActivityRecord.team_id == TEAM_ID, g.GhgActivityRecord.id.in_(ids))
                    .order_by(g.GhgActivityRecord.id)
                    .with_for_update()
                )
            ).all()
        )
        if not rows:
            remaining = await session.scalar(
                select(func.count()).select_from(g.GhgActivityRecord).where(g.GhgActivityRecord.record_code.in_(codes))
            )
            require(remaining == 0, "Reviewed codes reappeared with different IDs")
            print(json.dumps({"status": "already_absent", "deleted": 0}))
            await session.rollback()
            return
        require(serialize(rows) == expected, "Records changed after review; no deletion performed")
        refs = {}
        for model in (g.GhgActivityAllocation, g.GhgParameterAssignment, g.GhgCalculationResult):
            refs[model.__name__] = await session.scalar(
                select(func.count()).select_from(model).where(model.activity_id.in_(ids))
            )
        refs["evidence_links"] = await session.scalar(
            select(func.count()).select_from(g.GhgEvidenceLink).where(g.GhgEvidenceLink.record_code.in_(codes))
        )
        derived = list(
            (
                await session.scalars(
                    select(Scope2ElectricityReconciliation)
                    .where(Scope2ElectricityReconciliation.activity_record_id.in_(ids))
                    .execution_options(include_revision_history=True)
                    .with_for_update()
                )
            ).all()
        )
        expected_by_id = {row["id"]: row for row in expected}
        require(len(derived) == EXPECTED_DERIVED_COUNT, "Expected six reviewed synthetic electricity summaries")
        for summary in derived:
            source = expected_by_id[summary.activity_record_id]
            require(
                source["source_record_type"] == "Scope2ElectricityBill"
                and summary.source_priority == "ghg_activity"
                and summary.meter_total_kwh == 0
                and summary.source_snapshot.get("activity_ids") == [source["id"]]
                and not summary.source_snapshot.get("aggregate_ids")
                and str(summary.billing_month) == source["period_start"][:7],
                "Summary includes other sources; review required",
            )
        inventories = {row["inventory_code"] for row in expected}
        for model in (g.GhgCalculationRun, g.GhgInventoryReport):
            refs[model.__name__] = await session.scalar(
                select(func.count()).select_from(model).where(model.inventory_code.in_(inventories))
            )
        require(not any(refs.values()), f"Referenced records found; review required before deletion: {refs}")
        legacy_tables = (
            await session.scalars(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename IN ('dataapp_scope1mobilecombustion', 'dataapp_scope1stationarycombustion', "
                    "'dataapp_scope1refrigerantleak', 'dataapp_scope2electricitybill', 'dataapp_scope2purchasedenergy', "
                    "'dataapp_scope3wastedisposal', 'dataapp_scope3thirdpartytransport')"
                )
            )
        ).all()
        require(not legacy_tables, "Legacy scope tables remain; review recurrence risk")
        plan = {
            "team_id": str(TEAM_ID),
            "count": len(rows),
            "record_codes": codes,
            "references": refs,
            "retire_summary_ids": sorted(row.id for row in derived),
        }
        if not apply:
            print(json.dumps({"status": "planned", **plan}))
            await session.rollback()
            return
        if backup is None:
            msg = "A new backup path is required"
            raise ValueError(msg)
        # Exclusive creation prevents replacing a recovery artifact on a repeated invocation.
        with backup.open("x") as stream:
            backup.chmod(0o600)
            json.dump(
                {"plan": plan, "activities": expected, "derived": serialize(derived)},
                stream,
                ensure_ascii=False,
                indent=2,
            )
        for summary in derived:
            summary.is_current = False
            summary.status = "superseded"
            summary.source_snapshot = {
                **summary.source_snapshot,
                "retirement_reason": "Reviewed synthetic activity removed on 2026-10-13",
                "removed_record_code": expected_by_id[summary.activity_record_id]["record_code"],
            }
        await session.flush()
        for row in rows:
            await session.delete(row)
        await session.flush()
        remaining = await session.scalar(
            select(func.count()).select_from(g.GhgActivityRecord).where(g.GhgActivityRecord.id.in_(ids))
        )
        require(remaining == 0, "Delete verification failed")
        await session.commit()
        print(
            json.dumps(
                {"status": "deleted", "deleted": len(rows), "retired_summaries": len(derived), "backup": str(backup)}
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(**vars(parser.parse_args())))
