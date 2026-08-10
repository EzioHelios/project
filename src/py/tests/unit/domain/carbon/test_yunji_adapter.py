from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app.db import models as m
from app.domain.carbon.collectors.yunji_adapter import YunjiAdapter
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY


def test_yunji_normalize_converts_timestamps_and_preserves_meter_address() -> None:
    raw = {
        "IsSuccess": True,
        "_meta": {"start_time": "2026-07-10 15:00:00", "end_time": "2026-07-10 16:00:00"},
        "Data": [
            {
                "Address": "YJ-METER-001",
                "AmmeterID": "YJ-METER-001",
                "AmmeterName": "测试电表",
                "AreaID": "area-1",
                "AreaName": "测试区域",
                "ReadingDate": "2026-07-10 15:45",
                "ZYGDN": 10.1,
                "FYGDN": 0,
                "ZWGDN": 2.3,
                "FWGDN": 0,
                "ZYGDNSZ": 10.1,
                "FYGDNSZ": 0,
                "ZWGDNSZ": 2.3,
                "FWGDNSZ": 0,
            }
        ],
    }

    adapter = YunjiAdapter()
    try:
        rows = adapter.normalize(raw)
    finally:
        # The test does not open a network connection, but the adapter owns this client.
        import asyncio

        asyncio.run(adapter.client.aclose())

    assert len(rows) == 1
    assert rows[0]["equipment_id"] == "YJ-METER-001"
    assert rows[0]["reading_time"].isoformat() == "2026-07-10T15:45:00"
    assert rows[0]["start_time"].isoformat() == "2026-07-10T15:00:00"


@pytest.mark.anyio
async def test_yunji_save_binds_duplicate_address_to_explicit_tenant(session) -> None:
    first_team = m.Team(name="云集租户一", slug="yunji-tenant-one")
    second_team = m.Team(name="云集租户二", slug="yunji-tenant-two")
    session.add_all([first_team, second_team])
    await session.flush()
    session.info[TENANT_BYPASS_SESSION_KEY] = True
    first_meter = m.MonitorEquipment(
        team_id=first_team.id,
        code="YJ-METER-ONE",
        external_device_id="SHARED-YJ-ADDRESS",
        name="租户一电表",
        is_enable=True,
    )
    second_meter = m.MonitorEquipment(
        team_id=second_team.id,
        code="YJ-METER-TWO",
        external_device_id="SHARED-YJ-ADDRESS",
        name="租户二电表",
        is_enable=True,
    )
    session.add_all([first_meter, second_meter])
    await session.commit()

    adapter = YunjiAdapter()
    try:
        inserted = await adapter.save(
            session,
            [
                {
                    "team_id": second_team.id,
                    "equipment_id": "SHARED-YJ-ADDRESS",
                    "address": "SHARED-YJ-ADDRESS",
                    "reading_time": datetime.fromisoformat("2026-08-10T12:00:00"),
                    "readings": [
                        {
                            "source_point_code": "ZYGDNSZ",
                            "source_point_name": "正向有功总电能表码",
                            "point_code": "forward_active_total",
                            "value_kind": "register_index",
                            "raw_value": "128.5",
                            "normalized_value": "128.5",
                        }
                    ],
                }
            ],
        )
    finally:
        await adapter.client.aclose()

    facts = (await session.scalars(select(m.MeterReadingFact).execution_options(include_all_tenants=True))).all()
    assert inserted == 1
    assert len(facts) == 1
    assert facts[0].team_id == second_team.id
    assert facts[0].equipment_id == second_meter.id
