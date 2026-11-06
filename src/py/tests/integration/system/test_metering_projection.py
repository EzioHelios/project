from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import models as m
from app.domain.energy.queries.analysis import EnergyAnalysisQuery, EnergyAnalysisQueryService
from app.domain.energy.queries.balance import EnergyBalanceQuery, EnergyBalanceQueryService
from app.domain.energy.queries.benchmark import EnergyBenchmarkQuery, EnergyBenchmarkQueryService
from app.domain.energy.queries.flow import EnergyFlowQuery, EnergyFlowQueryService
from app.domain.metering.controllers.readings import _consumption_rows
from app.domain.metering.projection import ElectricityProjectionUseCase, reconcile_scope2_electricity
from app.domain.production_denominator.queries import ProductionDenominatorQueryService, ProductionOutputQuery
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

pytestmark = pytest.mark.anyio


def _reading(team_id, equipment_id: int, reading_time: datetime, value: str) -> m.MeterReadingFact:
    source_id = reading_time.isoformat()
    return m.MeterReadingFact(
        team_id=team_id,
        source_system="test_meter",
        source_record_id=source_id,
        equipment_id=equipment_id,
        source_point_code="ZYGDN",
        source_point_name="正向有功总电能",
        point_code="forward_active_total",
        point_name="正向有功总电能",
        energy_direction="forward",
        energy_kind="active",
        tou_period="total",
        value_kind="register_index",
        raw_value=value,
        normalized_value=Decimal(value),
        unit="kWh",
        quality_status="valid",
        reading_time=reading_time,
        mapping_version="test-v1",
    )


async def test_projection_is_idempotent_and_bill_supersedes_meter_total(session) -> None:  # noqa: PLR0915
    team = m.Team(name="投影测试租户", slug="projection-test")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    area = m.MonitorSector(code="HMAZ-PZK", name="平置库")
    session.add(area)
    await session.flush()
    meter = m.MonitorEquipment(code="JY-METER-202501020786", name="安方2号电表", sector_id=area.id, is_enable=True)
    candidate_group = m.MonitorEquipment(code="AF-PZK-AGV-GRP", name="AGV设备组", sector_id=area.id, is_enable=True)
    session.add_all([meter, candidate_group])
    await session.flush()
    boundary = m.MeasurementBoundary(
        code="AF-B-M002",
        name="安方2号计量边界",
        boundary_type="compound_circuit",
        meter_equipment_id=meter.id,
        sector_id=area.id,
        include_in_scope2=True,
        status="active",
        mapping_version="anfang-v1",
    )
    session.add(boundary)
    await session.flush()
    session.add(m.EnergyUseSystem(code="agv_logistics", name="AGV物流系统", system_type="electricity_end_use"))
    session.add(
        m.EnergyUseSystemBinding(
            system_code="agv_logistics",
            equipment_id=meter.id,
            equipment_code=meter.code,
            equipment_name=meter.name,
            sector_id=area.id,
            area_id=area.code,
            area_name=area.name,
            is_primary=True,
        )
    )
    session.add(
        m.MeasurementBoundaryMember(
            boundary_id=boundary.id,
            member_code=candidate_group.code,
            member_type="equipment_group",
            equipment_id=candidate_group.id,
            confirmation_status="candidate",
        )
    )
    session.add_all(
        [
            _reading(team.id, meter.id, datetime.fromisoformat("2026-04-30T23:00:00"), "100"),
            _reading(team.id, meter.id, datetime.fromisoformat("2026-05-01T00:00:00"), "110"),
            _reading(team.id, meter.id, datetime.fromisoformat("2026-05-01T01:00:00"), "125"),
        ]
    )
    await session.commit()

    use_case = ElectricityProjectionUseCase(session)
    first = await use_case.rebuild_month("2026-05")
    repeated = await use_case.rebuild_month("2026-05")

    assert first.reused is False
    assert first.hourly_facts == 2
    assert first.daily_facts == 1
    assert first.scope2_aggregates == 1
    assert repeated.reused is True
    aggregate = await session.scalar(select(m.Scope2MeterAggregate))
    reconciliation = await session.scalar(select(m.Scope2ElectricityReconciliation))
    hourly = (
        await session.scalars(select(m.EnergyIntervalFact).where(m.EnergyIntervalFact.granularity == "hour"))
    ).all()
    assert aggregate is not None
    assert aggregate.ammeter_id == meter.code
    aggregate_id = aggregate.id
    hourly_ids = [row.id for row in hourly]
    assert aggregate.total_kwh == Decimal(25)
    assert aggregate.status == "provisional"
    assert reconciliation is not None
    assert reconciliation.source_priority == "meter_aggregate"
    assert reconciliation.organization_total_kwh == Decimal(25)
    assert all((row.source_snapshot or {}).get("confirmed_member_codes") == [] for row in hourly)
    assert all(row.use_system_name == "AGV物流系统" for row in hourly)

    previous_reading = await session.scalar(
        select(m.MeterReadingFact).where(
            m.MeterReadingFact.equipment_id == meter.id,
            m.MeterReadingFact.reading_time == datetime.fromisoformat("2026-04-30T23:00:00"),
        )
    )
    assert previous_reading is not None
    previous_reading.raw_value = "105"
    previous_reading.normalized_value = Decimal(105)
    await session.commit()

    corrected = await use_case.rebuild_month("2026-05")
    corrected_repeat = await use_case.rebuild_month("2026-05")
    assert corrected.reused is False
    assert corrected.run_id != first.run_id
    assert corrected_repeat.reused is True
    current_aggregate = await session.scalar(select(m.Scope2MeterAggregate))
    assert current_aggregate is not None
    assert current_aggregate.total_kwh == Decimal(20)
    assert current_aggregate.id == aggregate_id
    current_hourly = (
        await session.scalars(select(m.EnergyIntervalFact).where(m.EnergyIntervalFact.granularity == "hour"))
    ).all()
    assert sorted(row.id for row in current_hourly) == sorted(hourly_ids)
    assert all(row.revision_no == 1 for row in current_hourly)

    session.add(
        m.GhgActivityRecord(
            record_code="ELEC-2026-05",
            inventory_code="INV-2026",
            organization_code="ORG-001",
            facility_code="FAC-001",
            source_code="PURCHASED-ELECTRICITY",
            activity_code="ELECTRICITY-2026-05",
            activity_name="2026年5月外购电力",
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
            iso_category_code="2.1",
            ghg_scope="scope2",
            source_mechanism="purchased_energy",
            value_chain_position="internal",
            boundary_status="included",
            activity_amount=Decimal(30),
            activity_unit="kWh",
            data_source_type="invoice",
            measurement_method="electricity_bill",
            quality_status="pass",
            status="approved",
            source_system="xlsx_import",
        )
    )
    await session.commit()
    bill_reconciliation = await reconcile_scope2_electricity(session, "2026-05")

    assert bill_reconciliation.source_priority == "ghg_activity"
    assert bill_reconciliation.organization_total_kwh == Decimal(30)
    assert bill_reconciliation.allocated_kwh == Decimal(20)
    assert bill_reconciliation.unallocated_kwh == Decimal(10)
    history = (
        await session.scalars(
            select(m.Scope2ElectricityReconciliation)
            .where(m.Scope2ElectricityReconciliation.billing_month == "2026-05")
            .execution_options(include_revision_history=True)
        )
    ).all()
    assert len(history) == 1
    assert sum(row.is_current for row in history) == 1


async def test_database_rejects_derived_history(session) -> None:
    from sqlalchemy.exc import IntegrityError

    team = m.Team(name="Current only", slug="current-only")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    session.add(
        m.EnergyIntervalFact(
            source_system="projection",
            source_record_id="one",
            energy_type_code="electricity",
            granularity="hour",
            period_start=datetime.fromisoformat("2026-05-01"),
            period_end=datetime.fromisoformat("2026-05-01T01:00:00"),
            amount=Decimal(9),
            revision_no=2,
            is_current=False,
        )
    )
    with pytest.raises(IntegrityError, match="current_only"):
        await session.flush()
    await session.rollback()


async def test_unconfigured_or_retired_boundaries_never_become_scope2_total(session) -> None:
    team = m.Team(name="计量边界验证", slug="boundary-eligibility")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    meter = m.MonitorEquipment(code="ELECTRIC-METER", name="名称不是边界依据", is_enable=True)
    session.add(meter)
    await session.flush()
    session.add_all(
        [
            _reading(team.id, meter.id, datetime.fromisoformat("2026-05-01T00:00:00"), "100"),
            _reading(team.id, meter.id, datetime.fromisoformat("2026-05-01T01:00:00"), "125"),
        ]
    )
    await session.commit()
    use_case = ElectricityProjectionUseCase(session)
    missing = await use_case.rebuild_month("2026-05")
    assert missing.hourly_facts == 1
    assert missing.scope2_aggregates == 0
    summary = await session.scalar(select(m.Scope2ElectricityReconciliation))
    assert summary.status == "incomplete"
    assert summary.source_priority == "none"

    boundary = m.MeasurementBoundary(
        code="CONFIRMED-IMPORT",
        name="已配置购电边界",
        meter_equipment_id=meter.id,
        include_in_scope2=True,
        energy_direction="import",
        status="active",
    )
    session.add(boundary)
    await session.commit()
    configured = await use_case.rebuild_month("2026-05")
    assert configured.scope2_aggregates == 1
    assert (await session.scalar(select(m.Scope2MeterAggregate))).total_kwh == Decimal(25)

    boundary.include_in_scope2 = False
    await session.commit()
    excluded = await use_case.rebuild_month("2026-05")
    assert excluded.scope2_aggregates == 0
    assert (await session.scalars(select(m.Scope2MeterAggregate))).all() == []
    history = (
        await session.scalars(select(m.Scope2MeterAggregate).execution_options(include_revision_history=True))
    ).all()
    assert history == []
    assert (await session.scalar(select(m.Scope2ElectricityReconciliation))).status == "incomplete"

    reading = await session.scalar(
        select(m.MeterReadingFact).where(m.MeterReadingFact.normalized_value == Decimal(125))
    )
    reading.quality_status = "invalid"
    await session.commit()
    invalidated = await use_case.rebuild_month("2026-05")
    assert invalidated.hourly_facts == 0
    assert (await session.scalars(select(m.EnergyIntervalFact))).all() == []

    reading.quality_status = "valid"
    await session.commit()
    restored = await use_case.rebuild_month("2026-05")
    assert not restored.reused
    assert restored.hourly_facts == 1
    assert (
        await session.scalar(
            select(func.sum(m.EnergyIntervalFact.amount)).where(m.EnergyIntervalFact.granularity == "hour")
        )
        == 25
    )
    assert (await use_case.rebuild_month("2026-05")).reused


async def test_projection_retries_after_atomic_write_failure(session, monkeypatch) -> None:
    team = m.Team(name="Projection retry", slug="projection-retry")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    meter = m.MonitorEquipment(code="RETRY-METER", name="Meter", is_enable=True)
    session.add(meter)
    await session.flush()
    session.add_all(
        [
            _reading(team.id, meter.id, datetime.fromisoformat("2026-05-01T00:00:00"), "100"),
            _reading(team.id, meter.id, datetime.fromisoformat("2026-05-01T01:00:00"), "125"),
        ]
    )
    await session.commit()
    use_case = ElectricityProjectionUseCase(session)
    original = use_case._write_quality_issues

    async def fail_write(*_args):
        msg = "interrupted projection"
        raise RuntimeError(msg)

    monkeypatch.setattr(use_case, "_write_quality_issues", fail_write)
    with pytest.raises(RuntimeError, match="interrupted projection"):
        await use_case.rebuild_month("2026-05")
    assert (await session.scalars(select(m.EnergyIntervalFact))).all() == []
    assert (await session.scalar(select(m.EnergyProjectionRun))).status == "failed"
    monkeypatch.setattr(use_case, "_write_quality_issues", original)
    retried = await use_case.rebuild_month("2026-05")
    assert retried.hourly_facts == 1
    assert (await use_case.rebuild_month("2026-05")).reused

    reading = await session.scalar(
        select(m.MeterReadingFact).where(m.MeterReadingFact.normalized_value == Decimal(125))
    )
    reading.normalized_value = Decimal(126)
    await session.commit()
    tenant_id = session.info[TENANT_ID_SESSION_KEY]
    factory = async_sessionmaker(session.bind, expire_on_commit=False)

    async def rebuild_in_worker():
        async with factory() as worker_session:
            worker_session.info[TENANT_ID_SESSION_KEY] = tenant_id
            return await ElectricityProjectionUseCase(worker_session).rebuild_month("2026-05")

    concurrent = await asyncio.gather(rebuild_in_worker(), rebuild_in_worker(), return_exceptions=True)
    from app.domain.metering.projection import ProjectionUnavailableError

    assert sum(isinstance(result, ProjectionUnavailableError) for result in concurrent) == 1
    assert sum(getattr(result, "hourly_facts", 0) for result in concurrent) == 1


async def test_overlapping_boundaries_fail_without_guessing_priority(session) -> None:
    team = m.Team(name="边界冲突验证", slug="boundary-conflict")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    meter = m.MonitorEquipment(code="METER-CONFLICT", name="电表", is_enable=True)
    session.add(meter)
    await session.flush()
    for code in ("FIRST", "SECOND"):
        session.add(m.MeasurementBoundary(code=code, name=code, meter_equipment_id=meter.id, status="active"))
    await session.commit()
    with pytest.raises(ValueError, match="多个计量边界"):
        await ElectricityProjectionUseCase(session).rebuild_month("2026-05")


async def test_energy_read_models_are_explicitly_tenant_scoped(session) -> None:  # noqa: PLR0915
    xiangtai = m.Team(name="祥泰仓库", slug="flow-xiangtai")
    anfang = m.Team(name="安方中心库", slug="flow-anfang")
    session.add_all([xiangtai, anfang])
    await session.flush()

    session.info[TENANT_BYPASS_SESSION_KEY] = True
    xiangtai_area = m.MonitorSector(team_id=xiangtai.id, code="XT-D1", name="点1-室外行吊")
    anfang_area = m.MonitorSector(team_id=anfang.id, code="HMAZ-PZK", name="平置库")
    session.add_all([xiangtai_area, anfang_area])
    await session.flush()
    xiangtai_meter = m.MonitorEquipment(
        team_id=xiangtai.id,
        code="XT-M001",
        name="祥泰室外行吊电表",
        sector_id=xiangtai_area.id,
        is_enable=True,
    )
    anfang_meter = m.MonitorEquipment(
        team_id=anfang.id,
        code="AF-M002",
        name="安方平置库电表",
        sector_id=anfang_area.id,
        is_enable=True,
    )
    session.add_all([xiangtai_meter, anfang_meter])
    await session.flush()
    session.add(
        m.MeasurementBoundary(
            team_id=xiangtai.id,
            code="XT-ONLY-BOUNDARY",
            name="Other tenant boundary",
            meter_equipment_id=xiangtai_meter.id,
            status="active",
        )
    )
    session.add_all(
        [
            m.EnergyIntervalFact(
                team_id=xiangtai.id,
                source_system="projection",
                source_record_id="xiangtai:day:2026-08-01",
                energy_type_code="purchased_electricity",
                equipment_id=xiangtai_meter.id,
                equipment_code=xiangtai_meter.code,
                equipment_name=xiangtai_meter.name,
                area_id="XT-D1",
                area_name="点1-室外行吊",
                use_system_code="warehouse_handling",
                use_system_name="仓储搬运系统",
                granularity="day",
                period_start=datetime.fromisoformat("2026-08-01T00:00:00"),
                period_end=datetime.fromisoformat("2026-08-02T00:00:00"),
                amount=Decimal(100),
                revision_no=1,
                is_current=True,
            ),
            m.EnergyIntervalFact(
                team_id=anfang.id,
                source_system="projection",
                source_record_id="anfang:day:2026-08-01",
                energy_type_code="purchased_electricity",
                equipment_id=anfang_meter.id,
                equipment_code=anfang_meter.code,
                equipment_name=anfang_meter.name,
                area_id="HMAZ-PZK",
                area_name="平置库",
                use_system_code="charging",
                use_system_name="充电系统",
                granularity="day",
                period_start=datetime.fromisoformat("2026-08-01T00:00:00"),
                period_end=datetime.fromisoformat("2026-08-02T00:00:00"),
                amount=Decimal(25),
                revision_no=1,
                is_current=True,
            ),
            m.EquipmentWorkloadFact(
                team_id=xiangtai.id,
                source_system="test",
                source_record_id="xiangtai:workload:2026-08-01",
                equipment_id=xiangtai_meter.id,
                equipment_code=xiangtai_meter.code,
                equipment_name=xiangtai_meter.name,
                area_id=xiangtai_area.code,
                area_name=xiangtai_area.name,
                workload_type="run_hours",
                period_start=datetime.fromisoformat("2026-08-01T00:00:00"),
                period_end=datetime.fromisoformat("2026-08-02T00:00:00"),
                workload_amount=Decimal(20),
                workload_unit="h",
                run_hours=Decimal(20),
                record_status="confirmed",
            ),
            m.EquipmentWorkloadFact(
                team_id=anfang.id,
                source_system="test",
                source_record_id="anfang:workload:2026-08-01",
                equipment_id=anfang_meter.id,
                equipment_code=anfang_meter.code,
                equipment_name=anfang_meter.name,
                area_id=anfang_area.code,
                area_name=anfang_area.name,
                workload_type="run_hours",
                period_start=datetime.fromisoformat("2026-08-01T00:00:00"),
                period_end=datetime.fromisoformat("2026-08-02T00:00:00"),
                workload_amount=Decimal(5),
                workload_unit="h",
                run_hours=Decimal(5),
                record_status="confirmed",
            ),
            m.ProductionOutputFact(
                team_id=xiangtai.id,
                source_system="test",
                source_record_id="xiangtai:output:2026-08-01",
                product_code="XT-THROUGHPUT",
                product_name="祥泰出库作业量",
                output_kind="throughput",
                period_start=date(2026, 8, 1),
                period_end=date(2026, 8, 1),
                good_qty=Decimal(1000),
                standard_qty=Decimal(1000),
                unit="托",
                standard_unit="托",
                record_status="confirmed",
            ),
            m.ProductionOutputFact(
                team_id=anfang.id,
                source_system="test",
                source_record_id="anfang:output:2026-08-01",
                product_code="AF-THROUGHPUT",
                product_name="安方出库作业量",
                output_kind="throughput",
                period_start=date(2026, 8, 1),
                period_end=date(2026, 8, 1),
                good_qty=Decimal(80),
                standard_qty=Decimal(80),
                unit="托",
                standard_unit="托",
                record_status="confirmed",
            ),
            _reading(xiangtai.id, xiangtai_meter.id, datetime.fromisoformat("2026-08-01T00:00:00"), "100"),
            _reading(xiangtai.id, xiangtai_meter.id, datetime.fromisoformat("2026-08-01T01:00:00"), "200"),
            _reading(anfang.id, anfang_meter.id, datetime.fromisoformat("2026-08-01T00:00:00"), "10"),
            _reading(anfang.id, anfang_meter.id, datetime.fromisoformat("2026-08-01T01:00:00"), "35"),
        ]
    )
    await session.flush()
    xiangtai_profile = m.EnergyBenchmarkProfile(
        team_id=xiangtai.id,
        name="祥泰设备标杆",
        source_name="test",
        is_enabled=True,
    )
    anfang_profile = m.EnergyBenchmarkProfile(
        team_id=anfang.id,
        name="安方设备标杆",
        source_name="test",
        is_enabled=True,
    )
    session.add_all([xiangtai_profile, anfang_profile])
    await session.flush()
    session.add_all(
        [
            m.EnergyBenchmarkItem(
                team_id=xiangtai.id,
                profile_id=xiangtai_profile.id,
                target_type="device",
                target_code=str(xiangtai_meter.id),
                target_name=xiangtai_meter.name,
                metric_code="kwh_per_run_hour",
                metric_name="单位运行小时用电",
                benchmark_value=Decimal(1),
                unit="kWh/h",
                is_enabled=True,
            ),
            m.EnergyBenchmarkItem(
                team_id=anfang.id,
                profile_id=anfang_profile.id,
                target_type="device",
                target_code=str(anfang_meter.id),
                target_name=anfang_meter.name,
                metric_code="kwh_per_run_hour",
                metric_name="单位运行小时用电",
                benchmark_value=Decimal(5),
                unit="kWh/h",
                is_enabled=True,
            ),
        ]
    )
    await session.commit()

    session.info.clear()
    session.info[TENANT_ID_SESSION_KEY] = anfang.id
    result = await EnergyFlowQueryService(session).graph(EnergyFlowQuery(granularity="day"))
    balance = await EnergyBalanceQueryService(session).calculation(EnergyBalanceQuery(granularity="day"))
    balance_diagnostics = await EnergyBalanceQueryService(session).diagnostics(EnergyBalanceQuery(granularity="day"))
    analysis = await EnergyAnalysisQueryService(session).summary(
        EnergyAnalysisQuery(
            period_start="2026-08-01T00:00:00",
            period_end="2026-08-02T00:00:00",
            granularity="day",
        )
    )
    meter_rows = await _consumption_rows(
        session,
        start_dt=datetime.fromisoformat("2026-08-01T00:00:00"),
        end_dt=datetime.fromisoformat("2026-08-02T00:00:00"),
        point_code="forward_active_total",
        granularity=None,
        area_id=None,
        equipment_id=None,
    )
    production = await ProductionDenominatorQueryService(session).summary(
        ProductionOutputQuery(
            period_start="2026-08-01",
            period_end="2026-08-01",
            record_status="confirmed",
        )
    )
    benchmark = await EnergyBenchmarkQueryService(session).comparisons(
        EnergyBenchmarkQuery(
            period_start="2026-08-01T00:00:00",
            period_end="2026-08-02T00:00:00",
            target_type="device",
            metric_code="kwh_per_run_hour",
        )
    )

    assert result["summary"]["total_input"] == 25.0
    assert result["summary"]["loss_rate_pct"] is None
    assert result["summary"]["data_quality"] == "metered_allocation_without_loss_measurement"
    assert any(node["name"] == "平置库" for node in result["nodes"])
    assert all(node["name"] != "点1-室外行吊" for node in result["nodes"])
    assert all(node["category"] != "loss" for node in result["nodes"])
    assert balance["boundary"] is None
    assert balance["summary"]["status"] == "no_boundary"
    assert balance["rows"] == []
    assert balance_diagnostics["items"][0]["code"] == "no_boundary"
    assert analysis["totals"]["total_energy"] == 25.0
    assert analysis["workload"]["workload_amount"] == 5.0
    assert analysis["by_equipment"][0]["equipment_name"] == "安方平置库电表"
    assert len(meter_rows) == 1
    assert meter_rows[0]["equipment_name"] == "安方平置库电表"
    assert meter_rows[0]["total_kwh"] == Decimal(25)
    assert production["totals"]["total_standard_qty"] == 80.0
    assert [row["product_code"] for row in production["by_product"]] == ["AF-THROUGHPUT"]
    assert benchmark["total"] == 1
    assert benchmark["items"][0]["target_code"] == str(anfang_meter.id)
    assert benchmark["items"][0]["benchmark_value"] == 5.0


async def test_large_projection_is_bounded_and_does_not_accumulate_versions(session, monkeypatch):
    import json
    from time import monotonic

    from sqlalchemy import text

    from app.domain.metering import projection

    team = m.Team(name="Projection load test", slug="projection-load-test")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    meter = m.MonitorEquipment(code="LOAD-METER", name="Load test", is_enable=True)
    session.add(meter)
    await session.flush()
    # Generate 120k source facts in PostgreSQL, without constructing a Python list.
    await session.execute(
        text("""
        INSERT INTO metering_meter_reading_fact
        (id, team_id, source_system, source_record_id, equipment_id, source_point_code,
         point_code, point_name, energy_direction, energy_kind, tou_period, value_kind,
         normalized_value, unit, quality_status, reading_time, mapping_version)
        SELECT nextval('metering_meter_reading_fact_id_seq'), CAST(:team AS uuid), 'load_test', i::text,
               :meter, 'total', 'forward_active_total', 'Total', 'forward', 'active', 'total',
               'register_index', i, 'kWh', 'valid', timestamp '2026-10-01' + i * interval '1 second', 'test'
        FROM generate_series(1,120000) i
    """),
        {"team": str(team.id), "meter": meter.id},
    )
    await session.commit()
    metrics = []
    original = projection.ProjectionMonitor.check

    def capture(self, stage, rows):
        original(self, stage, rows)
        metrics.append({"stage": stage, "rows": rows, "peak_rss_mb": self.peak_mb, "rss_mb": self.last_mb})

    monkeypatch.setattr(projection.ProjectionMonitor, "check", capture)
    use_case = ElectricityProjectionUseCase(session)
    start = monotonic()
    first = await use_case.rebuild_month("2026-10")
    assert first.source_count == 120000
    assert first.hourly_facts == 34
    assert first.daily_facts == 2
    assert (
        await session.scalar(
            select(func.sum(m.EnergyIntervalFact.amount)).where(m.EnergyIntervalFact.granularity == "hour")
        )
        == 119999
    )
    repeated = await use_case.rebuild_month("2026-10")
    assert repeated.reused
    assert await session.scalar(select(func.count()).select_from(m.EnergyIntervalFact)) == 36
    assert max(item["rss_mb"] for item in metrics) < 768
    print(  # noqa: T201 - retain measurable benchmark evidence in the test log.
        "PROJECTION_BENCHMARK="
        + json.dumps(
            {
                "source_rows": first.source_count,
                "output_rows": 36,
                "two_runs_seconds": round(monotonic() - start, 2),
                "peak_rss_mb": max(item["peak_rss_mb"] for item in metrics),
            }
        )
    )


async def test_manual_fact_duplicates_ignore_frozen_legacy_revision(session):
    from litestar.exceptions import ClientException

    from app.domain.energy.controllers.consumption import EnergyConsumptionController

    team = m.Team(name="Current-only CRUD", slug="projection-crud")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    payload = {
        "source_system": "manual_entry",
        "source_record_id": "existing",
        "energy_type_code": "electricity",
        "period_start": "2026-10-01",
        "amount": "10",
    }
    existing = m.EnergyIntervalFact(
        team_id=team.id,
        source_system="manual_entry",
        source_record_id="existing",
        energy_type_code="electricity",
        period_start=datetime.fromisoformat("2026-10-01"),
        period_end=datetime.fromisoformat("2026-10-01"),
        amount=Decimal(10),
        unit="kWh",
        revision_no=20,
    )
    other = m.EnergyIntervalFact(
        team_id=team.id,
        source_system="manual_entry",
        source_record_id="other",
        energy_type_code="electricity",
        period_start=datetime.fromisoformat("2026-10-01"),
        period_end=datetime.fromisoformat("2026-10-01"),
        amount=Decimal(20),
        unit="kWh",
        revision_no=1,
    )
    session.add_all([existing, other])
    await session.commit()
    with pytest.raises(ClientException, match="同一数据来源"):
        await EnergyConsumptionController.create_energy_interval_fact.fn(None, session, payload)
    with pytest.raises(ClientException, match="同一数据来源"):
        await EnergyConsumptionController.update_energy_interval_fact.fn(None, session, other.id, payload)
