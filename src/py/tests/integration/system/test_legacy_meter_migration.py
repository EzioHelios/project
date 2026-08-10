from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import func, select, text

from app.db import models as m
from app.domain.metering.legacy_migration import LegacyMeterReadingMigration
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = pytest.mark.anyio


async def test_legacy_migration_expands_non_null_fields_and_is_resumable(session) -> None:
    team = m.Team(name="祥泰仓库", slug="xiangtai")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    meter = m.MonitorEquipment(code="XT-M001", name="祥泰1号电表", is_enable=True)
    session.add(meter)
    await session.commit()

    await session.execute(
        text(
            """
            create table dataapp_ammeterindexvalue (
                id bigserial primary key,
                team_id uuid not null,
                equipment_id bigint,
                data_source integer,
                source_message_id bigint,
                reading_time timestamp,
                start_time timestamp,
                end_time timestamp,
                add_time timestamp,
                zygdn numeric,
                fygdn numeric,
                zwgdn numeric,
                fwgdn numeric,
                zygdnsz numeric,
                fygdnsz numeric,
                zwgdnsz numeric,
                fwgdnsz numeric
            )
            """
        )
    )
    await session.execute(text("create sequence test_meter_fact_id_seq"))
    await session.execute(
        text(
            "alter table metering_meter_reading_fact "
            "alter column id set default nextval('test_meter_fact_id_seq'::regclass)"
        )
    )
    await session.execute(
        text(
            """
            insert into dataapp_ammeterindexvalue (
                team_id, equipment_id, data_source, source_message_id, reading_time,
                zygdn, fygdn, zygdnsz, zwgdnsz
            ) values
                (:team_id, :equipment_id, 0, null, '2026-07-10 00:00:00', 10, 1, 100, 20),
                (:team_id, :equipment_id, 0, 123, '2026-07-10 00:05:00', 11, null, 101, null),
                (:team_id, null, 0, null, '2026-07-10 00:10:00', 12, null, 102, null)
            """
        ),
        {"team_id": team.id, "equipment_id": meter.id},
    )
    await session.commit()
    migration = LegacyMeterReadingMigration(
        session,
        team_id=team.id,
        from_time=datetime.fromisoformat("2026-05-01T00:00:00"),
        batch_size=1,
    )

    preview = await migration.execute(dry_run=True)
    first = await migration.execute()
    repeated = await migration.execute()

    facts = (await session.scalars(select(m.MeterReadingFact).order_by(m.MeterReadingFact.source_record_id))).all()
    source_count = await session.scalar(text("select count(*) from dataapp_ammeterindexvalue"))
    fact_count = await session.scalar(select(func.count()).select_from(m.MeterReadingFact))
    await session.execute(text("drop table dataapp_ammeterindexvalue"))
    await session.execute(text("alter table metering_meter_reading_fact alter column id drop default"))
    await session.execute(text("drop sequence test_meter_fact_id_seq"))
    await session.commit()
    assert preview.source_rows == 1
    assert preview.expected_facts == 4
    assert first.inserted_facts == 4
    assert first.duplicate_facts == 0
    assert repeated.inserted_facts == 4
    assert fact_count == 4
    assert source_count == 3
    assert {fact.value_kind for fact in facts} == {"legacy_quantity", "register_index"}
    assert all(fact.source_record_id.startswith("legacy:1:") for fact in facts)
