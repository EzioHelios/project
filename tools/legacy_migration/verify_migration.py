"""Verify legacy XTCK ledgers against canonical GHG activity records."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "py"))

from migrate_xtck_data import (
    LEGACY_LEDGER_TABLES,
    LEGACY_MASTER_TABLES,
    _async_url,
    _meter_source_stats,
    _read_source_rows,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import models as m
from app.db.models import Team
from app.domain.ghg_inventory.models import GhgActivityRecord, GhgCalculationRun, GhgParameterValue
from app.domain.ghg_inventory.usecases.legacy_xtck import map_legacy_activity
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY, install_tenant_events


async def verify() -> None:
    """Fail when traceable source rows are missing from the canonical target."""
    old_db_url = os.environ.get("OLD_DB_URL")
    new_db_url = os.environ.get("NEW_DB_URL")
    team_slug = os.environ.get("TARGET_TEAM_SLUG")
    if not old_db_url or not new_db_url or not team_slug:
        msg = "请设置 OLD_DB_URL、NEW_DB_URL 和 TARGET_TEAM_SLUG 后再运行校验脚本。"
        raise RuntimeError(msg)

    source_rows = await asyncio.to_thread(_read_source_rows, old_db_url)
    master_rows = await asyncio.to_thread(_read_source_rows, old_db_url, LEGACY_MASTER_TABLES)
    _, meter_high_watermark = await asyncio.to_thread(_meter_source_stats, old_db_url)
    expected = sum(len(source_rows[table]) for table in LEGACY_LEDGER_TABLES)
    expected_importable = 0
    for table in LEGACY_LEDGER_TABLES:
        for row in source_rows[table]:
            spec = map_legacy_activity(table, row)
            if row.get("id") is not None and spec is not None and spec.activity_amount >= 0:
                expected_importable += 1

    install_tenant_events()
    engine = create_async_engine(_async_url(new_db_url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            session.info[TENANT_BYPASS_SESSION_KEY] = True
            team = await session.scalar(select(Team).where(Team.slug == team_slug))
            if team is None:
                msg = f"目标租户不存在: {team_slug}"
                raise ValueError(msg)
            await session.commit()
            session.info.pop(TENANT_BYPASS_SESSION_KEY, None)
            session.info[TENANT_ID_SESSION_KEY] = team.id
            imported = int(
                await session.scalar(
                    select(func.count())
                    .select_from(GhgActivityRecord)
                    .where(GhgActivityRecord.source_system == "xtck_legacy")
                )
                or 0
            )
            parameters = int(await session.scalar(select(func.count()).select_from(GhgParameterValue)) or 0)
            runs = int(await session.scalar(select(func.count()).select_from(GhgCalculationRun)) or 0)
            target_equipment_codes = set((await session.scalars(select(m.MonitorEquipment.code))).all())
            meter_run = await session.scalar(
                select(m.DataMigrationRun).where(
                    m.DataMigrationRun.run_code == f"xtck-external-meter:{meter_high_watermark}",
                    m.DataMigrationRun.status == "completed",
                )
            )
    finally:
        await engine.dispose()

    if imported < expected_importable:
        msg = (
            "Canonical XTCK migration is incomplete: "
            f"source_rows={expected} importable_rows={expected_importable} imported={imported}"
        )
        raise RuntimeError(msg)
    if imported and (parameters == 0 or runs == 0):
        msg = f"Canonical completion is missing: activities={imported} parameters={parameters} runs={runs}"
        raise RuntimeError(msg)
    source_equipment_codes = {
        str(row.get("code") or "") for row in master_rows["dataapp_monitorequipment"] if row.get("code")
    }
    missing_equipment = source_equipment_codes - target_equipment_codes
    if missing_equipment:
        msg = f"Canonical master-data migration is incomplete: missing_equipment={sorted(missing_equipment)}"
        raise RuntimeError(msg)
    if os.environ.get("XTCK_SKIP_METERS", "").lower() not in {"1", "true", "yes"} and meter_run is None:
        msg = f"Canonical meter migration is incomplete: source_high_watermark={meter_high_watermark}"
        raise RuntimeError(msg)


if __name__ == "__main__":
    asyncio.run(verify())
