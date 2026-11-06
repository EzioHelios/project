# ruff: noqa: T201
"""Read a tenant-scoped, repeatable, read-only warehouse snapshot to gzip NDJSON.

Run inside the configured warehouse app container. No credentials or raw payloads
are emitted. The output contains restricted equipment identities and belongs in
an ignored internal working directory, never a publishable competition package.
"""

import argparse
import asyncio
import contextlib
import gzip
import json
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

with contextlib.redirect_stdout(sys.stderr):
    from sqlalchemy import select, text

    from app.db import models as m
    from app.lib.settings import get_settings
    from app.lib.tenancy import TENANT_ID_SESSION_KEY


CUTOFF_LOCAL = datetime(2026, 9, 28)  # noqa: DTZ001 - database stores naive Yunji local time
CUTOFF_UTC_NAIVE = datetime(2026, 9, 27, 16)  # noqa: DTZ001 - database stores naive MQTT UTC time
TENANTS = [
    ("S01", "00000000-0000-7000-8000-000000000001"),
    ("S02", "00000000-0000-7000-8000-000000000002"),
]
FACT_COLUMNS = [
    "id",
    "equipment_id",
    "reading_time",
    "normalized_value",
    "raw_value",
    "unit",
    "quality_status",
    "source_system",
    "source_record_id",
    "mapping_version",
    "binding_id",
    "source_message_id",
    "received_at",
    "source_time_field",
]


async def main(include_legacy: bool = False) -> None:
    db = get_settings().db.get_config()
    factory = db.create_session_maker()
    with gzip.GzipFile(fileobj=sys.stdout.buffer, mode="wb", mtime=0) as out:

        def emit(record: dict[str, Any]) -> None:
            out.write((json.dumps(record, ensure_ascii=False, default=str) + "\n").encode())

        emit(
            {
                "kind": "snapshot",
                "source_environment": "production_warehouse",
                "created_at": datetime.now(UTC).isoformat(),
                "cutoff_local_exclusive": "2026-09-28T00:00:00+08:00",
                "fact_columns": FACT_COLUMNS,
                "read_only": True,
                "includes_legacy_archive": include_legacy,
            }
        )
        for site, team in TENANTS:
            team_id = UUID(team)
            async with factory() as session:
                session.info[TENANT_ID_SESSION_KEY] = team_id
                await session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                await session.execute(text("SET TRANSACTION READ ONLY"))
                await session.execute(text("SET LOCAL ROLE pg_read_all_data"))
                await session.execute(text("SET LOCAL statement_timeout = '120s'"))
                role = (
                    await session.execute(
                        text(
                            "SELECT rolsuper,rolbypassrls,current_setting('app.tenant_id',true),"
                            "current_setting('app.tenant_bypass',true),current_setting('transaction_read_only') "
                            "FROM pg_roles WHERE rolname=current_user"
                        )
                    )
                ).one()
                if role[0] or role[1] or role[2] != team or role[3] != "false" or role[4] != "on":
                    raise RuntimeError("Read-only tenant enforcement failed")
                rls = (
                    await session.execute(
                        text(
                            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                            "WHERE relname='metering_meter_reading_fact'"
                        )
                    )
                ).one()
                if not all(rls):
                    raise RuntimeError("Canonical fact RLS must be enabled and forced")
                equipment_fields = [
                    "id",
                    "code",
                    "name",
                    "location",
                    "category",
                    "parent_device_id",
                    "protocol",
                    "rated_power_kw",
                    "is_enable",
                ]
                equipment = (
                    (
                        await session.execute(
                            select(*[getattr(m.MonitorEquipment, k) for k in equipment_fields])
                            .where(m.MonitorEquipment.team_id == team_id)
                            .order_by(m.MonitorEquipment.id)
                        )
                    )
                    .mappings()
                    .all()
                )
                binding_fields = ["id", "equipment_id", "meter_key", "identity_status", "scaling_mode", "multiplier"]
                bindings = (
                    (
                        await session.execute(
                            select(*[getattr(m.MqttDeviceBinding, k) for k in binding_fields]).where(
                                m.MqttDeviceBinding.team_id == team_id
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
                point_fields = ["binding_id", "source_tag", "point_code", "unit", "multiplier", "mapping_version"]
                mappings = (
                    (
                        await session.execute(
                            select(*[getattr(m.MqttPointMapping, k) for k in point_fields]).where(
                                m.MqttPointMapping.team_id == team_id,
                                m.MqttPointMapping.point_code == "forward_active_total",
                                m.MqttPointMapping.enabled.is_(True),
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
                emit(
                    {
                        "kind": "site",
                        "site_id": site,
                        "team_id": team,
                        "equipment": [dict(x) for x in equipment],
                        "bindings": [dict(x) for x in bindings],
                        "point_mappings": [dict(x) for x in mappings],
                        "effective_role": "pg_read_all_data",
                        "fact_rls_forced": True,
                        "identity_query_explicit_team_filter": True,
                        "transaction_started_at": (await session.execute(text("SELECT now()"))).scalar_one(),
                    }
                )
                cutoff = CUTOFF_LOCAL if site == "S01" else CUTOFF_UTC_NAIVE
                f, inbound = m.MeterReadingFact, m.MqttInboundMessage
                stmt = (
                    select(
                        f.id,
                        f.equipment_id,
                        f.reading_time,
                        f.normalized_value,
                        f.raw_value,
                        f.unit,
                        f.quality_status,
                        f.source_system,
                        f.source_record_id,
                        f.mapping_version,
                        f.binding_id,
                        f.source_message_id,
                        inbound.received_at,
                    )
                    .outerjoin(inbound, (f.source_message_id == inbound.id) & (inbound.team_id == team_id))
                    .where(
                        f.team_id == team_id,
                        f.point_code == "forward_active_total",
                        f.value_kind == "register_index",
                        f.reading_time < cutoff,
                        f.source_system.in_(["yunji", "yunji_legacy", "mqtt_szscada"]),
                    )
                    .order_by(f.equipment_id, f.reading_time, f.id)
                    .execution_options(yield_per=5000)
                )
                count = 0
                async for row in await session.stream(stmt):
                    emit({"kind": "fact", "site_id": site, "values": [*row, "reading_time"]})
                    count += 1
                if include_legacy:
                    archive_rls = (
                        await session.execute(
                            text(
                                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                                "WHERE relname='dataapp_ammeterindexvalue'"
                            )
                        )
                    ).one()
                    emit(
                        {
                            "kind": "legacy_scope",
                            "site_id": site,
                            "table": "dataapp_ammeterindexvalue",
                            "rls": list(archive_rls),
                            "explicit_team_filter": True,
                            "session_tenant_bypass": False,
                        }
                    )
                    legacy_stmt = text("""
                        SELECT id,equipment_id,coalesce(reading_time,end_time,start_time,add_time),
                               zygdnsz,zygdnsz::text,'kWh',
                               CASE WHEN zygdnsz IS NULL THEN 'invalid' ELSE 'valid' END,
                               CASE data_source WHEN 0 THEN 'yunji_legacy_archive'
                                 WHEN 1 THEN 'infrared_legacy_archive' ELSE 'legacy_meter_archive' END,
                               concat('legacy', chr(58), id::text, chr(58), 'zygdnsz'),'legacy_archive_v1',
                               NULL,NULL,NULL,
                               CASE WHEN reading_time IS NOT NULL THEN 'reading_time'
                                 WHEN end_time IS NOT NULL THEN 'legacy_period_end'
                                 WHEN start_time IS NOT NULL THEN 'legacy_period_start'
                                 ELSE 'legacy_ingest_time' END
                        FROM dataapp_ammeterindexvalue
                        WHERE team_id=:team AND equipment_id IS NOT NULL
                          AND source_message_id IS NULL
                          AND coalesce(reading_time,end_time,start_time,add_time) < :cutoff
                        ORDER BY equipment_id,id
                    """).execution_options(yield_per=5000)
                    archive_count = 0
                    async for row in await session.stream(legacy_stmt, {"team": team_id, "cutoff": cutoff}):
                        emit({"kind": "fact", "site_id": site, "values": list(row)})
                        archive_count += 1
                    count += archive_count
                    print(f"{site}: included {archive_count} legacy register rows", file=sys.stderr, flush=True)
                emit({"kind": "site_end", "site_id": site, "rows": count})
                print(f"{site}: exported {count} register observations", file=sys.stderr, flush=True)
                await session.rollback()
    await get_settings().db.get_engine().dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-legacy", action="store_true")
    asyncio.run(main(parser.parse_args().include_legacy))
