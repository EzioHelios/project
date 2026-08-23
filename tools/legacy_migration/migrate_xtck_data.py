"""Import legacy XTCK carbon ledgers into the canonical GHG inventory.

The source database is read-only. This command does not recreate or populate
the removed Scope 1/2/3 tables. By default it also completes the warehouse
boundary, parameter values and calculation runs through the canonical use case.

Required environment variables:
- OLD_DB_URL: legacy XTCK PostgreSQL URL (sync driver)
- NEW_DB_URL: current application PostgreSQL URL (async or sync driver)
- TARGET_TEAM_SLUG: tenant receiving the records

Optional environment variables:
- TARGET_ORGANIZATION_CODE (default WAREHOUSE-ORG)
- TARGET_FACILITY_CODE (default ROOT)
- XTCK_SKIP_METERS=true to defer canonical meter-fact migration
- XTCK_METER_BATCH_SIZE and XTCK_TARGET_FACT_CHUNK tune resumable batches
- XTCK_ACTIVITIES_ONLY=true to skip warehouse completion/calculation
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "py"))

from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import models as m
from app.db.models import Team
from app.domain.ghg_inventory.usecases.legacy_xtck import LegacyXtckInventoryImport, LegacyXtckMasterDataImport
from app.domain.ghg_inventory.usecases.tenant_dataset import CompleteWarehouseTenantInventory
from app.domain.metering.reading_facts import LEGACY_FIELD_TO_POINT, METER_POINT_SPECS, VALUE_KIND_REGISTER_INDEX
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY, install_tenant_events

LEGACY_LEDGER_TABLES = (
    "dataapp_scope1mobilecombustion",
    "dataapp_scope1stationarycombustion",
    "dataapp_scope1refrigerantleak",
    "dataapp_scope2electricitybill",
    "dataapp_scope2purchasedenergy",
    "dataapp_scope3wastedisposal",
    "dataapp_scope3thirdpartytransport",
)
LEGACY_MASTER_TABLES = (
    "dataapp_enterpriseinfo",
    "dataapp_monitorsector",
    "dataapp_monitorsectorphoto",
    "dataapp_monitorequipment",
    "dataapp_videomonitor",
)
METER_REGISTER_FIELDS = ("ZYGDNSZ", "FYGDNSZ", "ZWGDNSZ", "FWGDNSZ")
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


def _sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://")


def _async_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


def _read_source_rows(
    old_db_url: str, table_names: tuple[str, ...] = LEGACY_LEDGER_TABLES
) -> dict[str, list[dict[str, object]]]:
    engine = create_engine(_sync_url(old_db_url))
    metadata = MetaData()
    result: dict[str, list[dict[str, object]]] = {}
    try:
        with engine.connect() as connection:
            metadata.reflect(bind=connection, only=lambda name, _: name in table_names)
            for table_name in table_names:
                table = metadata.tables.get(table_name)
                if table is None:
                    result[table_name] = []
                    continue
                result[table_name] = [dict(row) for row in connection.execute(select(table)).mappings()]
    finally:
        engine.dispose()
    return result


def _meter_source_stats(old_db_url: str) -> tuple[int, int]:
    engine = create_engine(_sync_url(old_db_url))
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text("select count(*) as source_count, coalesce(max(id), 0) as high_watermark from dataapp_ammeterindexvalue")
            ).one()
            return int(row.source_count), int(row.high_watermark)
    finally:
        engine.dispose()


def _read_meter_batch(old_db_url: str, *, last_source_id: int, high_watermark: int, batch_size: int) -> list[dict[str, Any]]:
    engine = create_engine(_sync_url(old_db_url))
    try:
        with engine.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    text(
                        """
                        select id, zygdnsz, fygdnsz, zwgdnsz, fwgdnsz,
                               coalesce(reading_time, end_time, start_time, add_time) as reading_time,
                               equipment_id, address, data_source
                        from dataapp_ammeterindexvalue
                        where id > :last_source_id and id <= :high_watermark
                        order by id
                        limit :batch_size
                        """
                    ),
                    {
                        "last_source_id": last_source_id,
                        "high_watermark": high_watermark,
                        "batch_size": batch_size,
                    },
                ).mappings()
            ]
    finally:
        engine.dispose()


async def _migrate_meter_facts(session: AsyncSession, *, old_db_url: str, team_id: UUID) -> tuple[int, int]:
    """Stream external legacy register indices into the canonical fact table."""
    batch_size = min(max(int(os.environ.get("XTCK_METER_BATCH_SIZE", "5000")), 1), 20_000)
    target_chunk_size = min(max(int(os.environ.get("XTCK_TARGET_FACT_CHUNK", "2000")), 1), 2500)
    source_count, high_watermark = await asyncio.to_thread(_meter_source_stats, old_db_url)
    run_code = f"xtck-external-meter:{high_watermark}"
    run = await session.scalar(select(m.DataMigrationRun).where(m.DataMigrationRun.run_code == run_code))
    if run is not None and run.status == "completed":
        return int(run.target_rows), int(run.skipped_rows)
    if run is None:
        run = m.DataMigrationRun(
            run_code=run_code,
            migration_type="xtck_external_meter_register",
            source_table="dataapp_ammeterindexvalue",
            target_table="metering_meter_reading_fact",
            source_high_watermark=str(high_watermark),
            last_source_id=0,
            status="running",
            source_rows=source_count,
            target_rows=0,
            skipped_rows=0,
            started_at=datetime.now(UTC).replace(tzinfo=None),
            run_config={
                "sourceBatchSize": batch_size,
                "targetFactChunkSize": target_chunk_size,
                "valueKind": VALUE_KIND_REGISTER_INDEX,
            },
        )
        session.add(run)
        await session.commit()

    equipment_rows = (await session.scalars(select(m.MonitorEquipment))).all()
    equipment_by_code = {row.code: row.id for row in equipment_rows}
    inserted_total = int(run.target_rows or 0)
    skipped_total = int(run.skipped_rows or 0)
    last_source_id = int(run.last_source_id or 0)
    while last_source_id < high_watermark:
        rows = await asyncio.to_thread(
            _read_meter_batch,
            old_db_url,
            last_source_id=last_source_id,
            high_watermark=high_watermark,
            batch_size=batch_size,
        )
        if not rows:
            break
        payload: list[dict[str, Any]] = []
        for row in rows:
            source_id = int(row["id"])
            equipment_code = str(row.get("equipment_id") or row.get("address") or "")
            equipment_id = equipment_by_code.get(equipment_code)
            reading_time = row.get("reading_time")
            if equipment_id is None or not isinstance(reading_time, datetime):
                skipped_total += sum(row.get(field.lower()) is not None for field in METER_REGISTER_FIELDS)
                continue
            reading_time = reading_time.replace(tzinfo=None)
            source_type = int(row["data_source"]) if row.get("data_source") is not None else None
            source_system = (
                {0: "yunji_legacy", 1: "infrared_hw_legacy"}.get(source_type, "legacy_meter")
                if source_type is not None
                else "legacy_meter"
            )
            for source_point_code in METER_REGISTER_FIELDS:
                value = row.get(source_point_code.lower())
                if value is None:
                    continue
                point_code, value_kind = LEGACY_FIELD_TO_POINT[source_point_code]
                spec = METER_POINT_SPECS[point_code]
                payload.append(
                    {
                        "team_id": team_id,
                        "source_system": source_system,
                        "source_record_id": f"legacy:{source_id}:{source_point_code.lower()}",
                        "source_message_id": None,
                        "binding_id": None,
                        "equipment_id": equipment_id,
                        "source_point_code": source_point_code,
                        "source_point_name": spec.point_name,
                        "point_code": point_code,
                        "point_name": spec.point_name,
                        "energy_direction": spec.energy_direction,
                        "energy_kind": spec.energy_kind,
                        "tou_period": spec.tou_period,
                        "value_kind": value_kind,
                        "raw_value": str(value),
                        "normalized_value": Decimal(str(value)),
                        "unit": spec.unit,
                        "quality_status": "valid",
                        "source_type": source_type,
                        "reading_time": reading_time,
                        "mapping_version": "xtck_canonical_v1",
                    }
                )
        inserted = 0
        for offset in range(0, len(payload), target_chunk_size):
            chunk = payload[offset : offset + target_chunk_size]
            result = await session.execute(
                postgresql_insert(m.MeterReadingFact)
                .values(chunk)
                .on_conflict_do_nothing(constraint="uq_metering_fact_source_record_point")
                .returning(m.MeterReadingFact.id)
            )
            chunk_inserted = len(result.scalars().all())
            inserted += chunk_inserted
            inserted_total += chunk_inserted
            skipped_total += len(chunk) - chunk_inserted
        last_source_id = int(rows[-1]["id"])
        run.last_source_id = last_source_id
        run.target_rows = inserted_total
        run.skipped_rows = skipped_total
        await session.commit()
    run.status = "completed"
    run.finished_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    return inserted_total, skipped_total


async def migrate_xtck_data() -> None:
    """Run the tenant-safe canonical import and optional warehouse completion."""
    old_db_url = os.environ.get("OLD_DB_URL")
    new_db_url = os.environ.get("NEW_DB_URL")
    team_slug = os.environ.get("TARGET_TEAM_SLUG")
    if not old_db_url or not new_db_url or not team_slug:
        msg = "请设置 OLD_DB_URL、NEW_DB_URL 和 TARGET_TEAM_SLUG 后再运行迁移脚本。"
        raise RuntimeError(msg)

    source_rows = await asyncio.to_thread(_read_source_rows, old_db_url, LEGACY_LEDGER_TABLES)
    master_rows = await asyncio.to_thread(_read_source_rows, old_db_url, LEGACY_MASTER_TABLES)
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
            team_id = team.id
            await session.commit()
            session.info.pop(TENANT_BYPASS_SESSION_KEY, None)
            session.info[TENANT_ID_SESSION_KEY] = team_id

            master = await LegacyXtckMasterDataImport(session).execute(master_rows)
            logger.info(
                "Canonical master data imported: enterprises=%s sectors=%s photos=%s equipment=%s videos=%s",
                master.enterprises,
                master.sectors,
                master.sector_photos,
                master.equipment,
                master.video_monitors,
            )

            if os.environ.get("XTCK_SKIP_METERS", "").lower() not in {"1", "true", "yes"}:
                inserted, skipped = await _migrate_meter_facts(session, old_db_url=old_db_url, team_id=team_id)
                logger.info("Canonical meter facts imported: inserted=%s skipped_or_duplicate=%s", inserted, skipped)

            imported = await LegacyXtckInventoryImport(
                session,
                organization_code=os.environ.get("TARGET_ORGANIZATION_CODE", "WAREHOUSE-ORG"),
                facility_code=os.environ.get("TARGET_FACILITY_CODE", "ROOT"),
            ).execute(source_rows)
            logger.info(
                "Canonical activities imported: "
                f"source={imported.source_rows} created={imported.created} updated={imported.updated} "
                f"skipped={imported.skipped} inventories={','.join(imported.inventory_codes)}"
            )

            if os.environ.get("XTCK_ACTIVITIES_ONLY", "").lower() not in {"1", "true", "yes"}:
                completed = await CompleteWarehouseTenantInventory(session).execute()
                logger.info(
                    "Canonical inventory completed: "
                    f"activities={completed.activities} parameters={completed.parameter_values} "
                    f"runs={completed.calculation_runs} reports={completed.inventory_reports}"
                )
    finally:
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(migrate_xtck_data())


if __name__ == "__main__":
    main()
