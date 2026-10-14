from datetime import date, datetime
from decimal import Decimal

import pytest

from app.db import models as m
from app.domain.carbon.services._bigscreen_operations import BigscreenOperationsService
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = pytest.mark.anyio


async def test_latest_reading_seek_preserves_filters_ties_empty_devices_and_tenant_scope(session):
    teams = [m.Team(name="Readings A", slug="readings-a"), m.Team(name="Readings B", slug="readings-b")]
    session.add_all(teams)
    await session.flush()
    for index, team in enumerate(teams):
        session.info[TENANT_ID_SESSION_KEY] = team.id
        devices = [
            m.MonitorEquipment(code="LATEST", name="Latest", category=0, is_enable=True),
            m.MonitorEquipment(code="EMPTY", name="Empty", category=0, is_enable=True),
            m.MonitorEquipment(code="DISABLED", name="Disabled", category=0, is_enable=False),
            m.MonitorEquipment(code="NULL", name="Null value", category=1, is_enable=True),
        ]
        session.add_all(devices)
        await session.flush()
        for seq, (device, day, source, quality, point, kind, amount) in enumerate(
            [
                (0, 1, "mqtt", "valid", "forward_active_total", "register_index", "100"),
                (0, 2, "mqtt", "valid", "forward_active_total", "register_index", "110"),
                (0, 2, "mqtt", "valid", "forward_active_total", "register_index", str(111 + index)),
                (0, 3, "demo_seed", "valid", "forward_active_total", "register_index", "999"),
                (0, 4, "mqtt", "invalid", "forward_active_total", "register_index", "999"),
                (0, 5, "mqtt", "valid", "reverse_active_total", "register_index", "999"),
                (0, 6, "mqtt", "valid", "forward_active_total", "interval_delta", "999"),
                (2, 2, "mqtt", "valid", "forward_active_total", "register_index", "999"),
                (3, 2, "mqtt", "valid", "forward_active_total", "register_index", None),
            ]
        ):
            session.add(
                m.MeterReadingFact(
                    equipment_id=devices[device].id,
                    source_system=source,
                    source_record_id=str(seq),
                    source_point_code=point,
                    point_code=point,
                    point_name="Meter register",
                    energy_direction="forward",
                    energy_kind="active",
                    tou_period="total",
                    value_kind=kind,
                    normalized_value=Decimal(amount) if amount is not None else None,
                    unit="kWh",
                    quality_status=quality,
                    reading_time=datetime(2026, 10, day),  # noqa: DTZ001 - business timestamps are naive.
                    mapping_version="1",
                )
            )
            await session.flush()
        await session.commit()
    for index, team in enumerate(teams):
        session.info[TENANT_ID_SESSION_KEY] = team.id
        view = await BigscreenOperationsService(session).build(start=date(2026, 10, 1), end=date(2026, 10, 6))
        devices = {d["name"]: d for d in view["devices"]}
        assert set(devices) == {"Latest", "Empty", "Null value"}
        assert devices["Latest"]["register_value"] == 111 + index
        assert devices["Latest"]["last_reading"] == "2026-10-02T00:00:00"
        assert devices["Latest"]["register_unit"] == "kWh"
        assert devices["Empty"]["last_reading"] is None
        assert devices["Empty"]["register_value"] is None
        assert devices["Null value"]["last_reading"] == "2026-10-02T00:00:00"
        assert devices["Null value"]["register_value"] is None


async def test_screen_meter_totals_exclude_demo_and_do_not_mix_tenants(session):
    teams = [m.Team(name="Screen A", slug="screen-a"), m.Team(name="Screen B", slug="screen-b")]
    session.add_all(teams)
    await session.flush()
    for index, team in enumerate(teams):
        session.info[TENANT_ID_SESSION_KEY] = team.id
        area = m.MonitorSector(code="AREA", name="Area")
        session.add(area)
        await session.flush()
        equipment = m.MonitorEquipment(code="METER", name="Meter", category=0, sector_id=area.id, is_enable=True)
        session.add(equipment)
        await session.flush()
        camera = m.VideoMonitor(location="Camera", f_area="登记功能区")
        session.add(camera)
        await session.flush()
        session.add_all(
            [
                m.AlarmEvent(
                    event_type=2,
                    event_desc="用电告警",
                    sector_id=area.id,
                    equipment_id=equipment.id,
                    is_handle=False,
                    alarm_level="critical",
                ),
                m.AlarmEvent(event_type=2, event_desc="无区域记录", is_handle=True),
                m.VedioAlarmEvent(event_type=1, equipment_id=camera.id, is_handle=False),
            ]
        )
        for source, quality, amount, revision in [
            ("meter_daily", "measured", str(index + 1), True),
            ("demo_seed", "measured", "999", True),
            ("meter_projection", "simulated", "999", True),
            ("meter_daily", "measured", "999", False),
            ("manual", "measured", "999", True),
        ]:
            session.add(
                m.EnergyIntervalFact(
                    team_id=team.id,
                    source_system=source,
                    source_record_id=f"{source}-{quality}-{revision}",
                    energy_type_code="electricity",
                    equipment_id=equipment.id,
                    equipment_name=equipment.name,
                    area_id=area.code,
                    area_name=area.name,
                    granularity="day",
                    period_start=datetime(2026, 10, 1),  # noqa: DTZ001 - interval columns store naive business time.
                    period_end=datetime(2026, 10, 2),  # noqa: DTZ001
                    amount=Decimal(amount),
                    unit="kWh",
                    data_quality=quality,
                    is_current=revision,
                )
            )
        await session.commit()
    for index, team in enumerate(teams):
        session.info[TENANT_ID_SESSION_KEY] = team.id
        service = BigscreenOperationsService(session)
        view = await service.build(start=date(2026, 10, 1), end=date(2026, 10, 2))
        assert view["energy_kpis"][0]["value"] == index + 1
        roots = [node for node in view["energy_flow"]["nodes"] if node["category"] == "source"]
        assert sum(node["value"] for node in roots) == index + 1
        assert view["energy_flow"]["unit"] == "kWh"
        assert view["trend"][1]["value"] is None
        assert view["energy_calendar"][0]["value"] is None
        assert view["energy_calendar"][1]["value"] == index + 1
        assert view["energy_calendar"][2]["value"] == index + 1
        assert view["energy_calendar"][1]["recorded_days"] == 1
        assert view["energy_calendar"][1]["calendar_days"] == 2
        assert sum(row["value"] for row in view["area_ranking"]) == index + 1
        assert {item["name"]: item["value"] for item in view["power_alarms"]["region_distribution"]} == {
            "Area": 1,
            "未关联区域": 1,
        }
        assert sum(item["value"] for item in view["power_alarms"]["status_distribution"]) == 2
        assert view["safety"]["region_distribution"] == [{"name": "登记功能区", "value": 1}]
        linked = next(item for item in view["power_alarms"]["recent"] if item["title"] == "用电告警")
        assert linked["device"] == "Meter"
        assert linked["area"] == "Area"
        assert linked["level"] == "严重"
        empty = await service.build(start=date(2026, 10, 1), end=date(2026, 10, 2), area="OTHER")
        assert empty["energy_kpis"][0]["value"] is None
        assert empty["energy_flow"]["nodes"] == []
        assert all(item["value"] is None for item in empty["energy_calendar"])


async def test_warehouse_ledger_dates_missing_amounts_and_commute_are_tenant_scoped(session):
    from app.domain.carbon.services._bigscreen_ledger import ledger_overview

    teams = [m.Team(name="Ledger A", slug="ledger-a"), m.Team(name="Ledger B", slug="ledger-b")]
    session.add_all(teams)
    await session.flush()
    for index, team in enumerate(teams):
        session.info[TENANT_ID_SESSION_KEY] = team.id
        session.add_all(
            [
                m.InMoney(rkrq="2024/1/2", shje=10000 * (index + 1)),
                m.InMoney(rkrq="2024-01-03", shje=None),
                m.InMoney(rkrq="2024-02-30", shje=90000),
                m.InMoney(rkrq=None, shje=10000),
                m.OutMoney(gzrq="2024-3-1", je=0),
                m.EmployeeCommute(name="Test", car_power_type=2),
            ]
        )
        await session.commit()
    for index, team in enumerate(teams):
        session.info[TENANT_ID_SESSION_KEY] = team.id
        result = await ledger_overview(session)
        assert result["trend"] == [
            {"period": "2024-01", "inbound": index + 1, "outbound": None},
            {"period": "2024-02", "inbound": None, "outbound": None},
            {"period": "2024-03", "inbound": None, "outbound": 0},
        ]
        assert result["coverage"][0] == {
            "kind": "inbound",
            "records": 4,
            "dated_records": 2,
            "undated_records": 2,
            "missing_amount": 1,
        }
        view = await BigscreenOperationsService(session).build()
        assert view["commute_power"] == [{"name": "电力", "value": 1}]


async def test_event_history_filters_pagination_and_tenant_isolation(session):
    teams = [m.Team(name="Events A", slug="events-a"), m.Team(name="Events B", slug="events-b")]
    session.add_all(teams)
    await session.flush()
    for team in teams:
        session.info[TENANT_ID_SESSION_KEY] = team.id
        camera = m.VideoMonitor(location="Camera", f_area="堆场")
        session.add(camera)
        await session.flush()
        for day in range(1, 14):
            moment = datetime(2026, 10, day, 23, 59)  # noqa: DTZ001 - legacy event columns use naive timestamps.
            session.add(
                m.AlarmEvent(event_type=2, event_desc=f"{team.slug}-{day}", event_time=moment, is_handle=day % 2 == 0)
            )
            session.add(m.VedioAlarmEvent(event_type=1, equipment_id=camera.id, event_time=moment, is_handle=False))
        session.add(m.AlarmEvent(event_type=4, event_desc="carbon", is_handle=None))
        await session.commit()
    for team in teams:
        session.info[TENANT_ID_SESSION_KEY] = team.id
        service = BigscreenOperationsService(session)
        first = await service.alerts(event_types=[2], page_size=10)
        second = await service.alerts(event_types=[2], page_size=10, page=2)
        assert first["total"] == second["total"] == 13
        assert len(first["recent"]) == 10
        assert len(second["recent"]) == 3
        assert {row["id"] for row in first["recent"]}.isdisjoint(row["id"] for row in second["recent"])
        assert all(row["title"].startswith(team.slug) for row in first["recent"])
        filtered = await service.alerts(
            event_types=[2],
            start=date(2026, 10, 2),
            end=date(2026, 10, 4),
            status="handled",
            area="未关联区域",
        )
        assert filtered["total"] == 2
        assert sum(row["value"] for row in filtered["distribution"]) == 2
        assert sum(row["value"] for row in filtered["region_distribution"]) == 2
        assert sum(row["value"] for row in filtered["status_distribution"]) == 2
        video = await service.alerts(video=True, area="堆场", end=date(2026, 10, 1))
        assert video["total"] == 1
        assert video["recent"][0]["device"] == "Camera"
        assert (await service.alerts(area="missing"))["total"] == 0
        assert (await service.alerts(event_types=[4]))["total"] == 1
        for kwargs in [
            {"page": 0},
            {"page_size": 51},
            {"status": "bad"},
            {"start": date(2026, 10, 2), "end": date(2026, 10, 1)},
        ]:
            with pytest.raises(ValueError):
                await service.alerts(**kwargs)
