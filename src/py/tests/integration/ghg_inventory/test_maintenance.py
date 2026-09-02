from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import models as m
from app.domain.ghg_inventory.models import GhgActivityRecord, GhgEmissionSource
from app.domain.ghg_inventory.usecases.maintenance import GhgInventoryMaintenance
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def _context(session):
    team = m.Team(name="GHG Maintenance Tenant", slug="ghg-maintenance-tenant")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    organization = m.ReportingOrganization(code="ORG-MAINT", name="维护测试组织")
    session.add(organization)
    await session.flush()
    period = m.ReportingPeriod(
        reporting_org_id=organization.id,
        code="MAINT-2026",
        name="2026年度",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        status="active",
    )
    area = m.MonitorSector(code="ROOT", name="测试区域", path="/ROOT", level=0)
    session.add_all([period, area])
    await session.flush()
    equipment = m.MonitorEquipment(code="METER-01", name="电表01", sector_id=area.id)
    session.add(equipment)
    await session.commit()
    return team, organization, period, area, equipment


async def test_emission_source_and_activity_crud(session) -> None:
    _, organization, period, area, _equipment = await _context(session)
    usecase = GhgInventoryMaintenance(session)

    source = await usecase.create_source(
        {
            "inventory_code": period.code,
            "reporting_period_id": period.id,
            "organization_code": organization.code,
            "facility_code": area.code,
            "source_code": "SRC-ELEC-01",
            "source_name": "总进线购入电力",
            "iso_category_code": "2.1",
            "default_area_id": area.id,
        }
    )
    assert source.source_mechanism == "energy"

    source = await usecase.update_source(
        "SRC-ELEC-01",
        {
            "inventory_code": period.code,
            "reporting_period_id": period.id,
            "organization_code": organization.code,
            "facility_code": area.code,
            "source_code": "SRC-ELEC-01",
            "source_name": "总进线购入电力更新",
            "iso_category_code": "2.1",
            "default_area_id": area.id,
        },
    )
    assert source.source_name == "总进线购入电力更新"

    activity = await usecase.create_activity(
        {
            "record_code": "ACT-ELEC-01",
            "inventory_code": period.code,
            "reporting_period_id": period.id,
            "organization_code": organization.code,
            "facility_code": area.code,
            "source_code": source.source_code,
            "activity_code": "purchased-electricity",
            "activity_name": "购入电力",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "iso_category_code": "2.1",
            "activity_amount": "1000",
            "activity_unit": "kWh",
            "data_source_type": "measured",
            "measurement_method": "电表计量",
            "source_payload": {
                "energy_type": "electricity",
                "supplier_name": "电网购电",
                "meter_point": "METER-01",
                "scope2_method": "location",
            },
        }
    )
    assert activity.ghg_scope == "scope2"

    activity = await usecase.update_activity(
        "ACT-ELEC-01",
        {
            "record_code": "ACT-ELEC-01",
            "inventory_code": period.code,
            "reporting_period_id": period.id,
            "organization_code": organization.code,
            "facility_code": area.code,
            "source_code": source.source_code,
            "activity_code": "purchased-electricity",
            "activity_name": "购入电力更新",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "iso_category_code": "2.1",
            "activity_amount": "1200",
            "activity_unit": "kWh",
            "data_source_type": "measured",
            "measurement_method": "电表计量",
            "source_payload": {
                "energy_type": "electricity",
                "supplier_name": "电网购电",
                "meter_point": "METER-01",
                "scope2_method": "location",
            },
        },
    )
    assert activity.activity_name == "购入电力更新"
    assert activity.activity_amount == Decimal(1200)

    stopped_source = await usecase.delete_source(inventory_code=period.code, source_code=source.source_code)
    assert stopped_source is not None
    assert stopped_source.status == "inactive"

    deleted = await usecase.delete_activity(inventory_code=period.code, record_code=activity.record_code)
    assert deleted is None
    assert await session.scalar(select(GhgActivityRecord).where(GhgActivityRecord.record_code == activity.record_code)) is None


async def test_activity_delete_archives_when_calculated(session) -> None:
    _, organization, period, area, _equipment = await _context(session)
    profile = m.GhgReportingProfile(
        code="MAINT-PROFILE",
        name="维护测试配置",
        version="1",
        standard_code="ISO 14064-1",
        standard_version="2018",
        effective_from=date(2026, 1, 1),
    )
    method = m.GhgCalculationMethodDefinition(
        code="MAINT-METHOD",
        version="1",
        name="维护测试方法",
        formula_family="F02",
        formula_expression={},
        human_formula="活动量 x 因子",
        standard_code="ISO 14064-1",
        applicable_categories=["2.1"],
        applicable_gases=["CO2"],
        effective_from=date(2026, 1, 1),
    )
    session.add_all([profile, method])
    await session.flush()
    source = m.GhgEmissionSource(
        inventory_code=period.code,
        organization_code=organization.code,
        facility_code=area.code,
        source_code="SRC-ARCHIVE",
        source_name="归档测试排放源",
        iso_category_code="2.1",
        source_mechanism="energy",
    )
    activity = m.GhgActivityRecord(
        record_code="ACT-ARCHIVE",
        inventory_code=period.code,
        reporting_period_id=period.id,
        organization_code=organization.code,
        facility_code=area.code,
        source_code=source.source_code,
        activity_code="purchased-electricity",
        activity_name="归档测试活动",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        iso_category_code="2.1",
        ghg_scope="scope2",
        source_mechanism="energy",
        value_chain_position="upstream",
        activity_amount=Decimal(100),
        activity_unit="kWh",
        data_source_type="measured",
        measurement_method="电表",
        source_payload={"energy_type": "electricity", "supplier_name": "电网购电", "meter_point": "METER", "scope2_method": "location"},
        status="approved",
    )
    session.add_all([source, activity])
    await session.flush()
    run = m.GhgCalculationRun(
        run_code="RUN-ARCHIVE",
        inventory_code=period.code,
        reporting_profile_id=profile.id,
        reporting_period_id=period.id,
        status="completed",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    session.add(
        m.GhgCalculationResult(
            run_id=run.id,
            activity_id=activity.id,
            method_id=method.id,
            iso_category_code="2.1",
            ghg_scope="scope2",
            gas_code="CO2",
            gas_mass_kg=Decimal(10),
            gwp_version="AR6",
            co2e_kg=Decimal(10),
            formula_snapshot={},
        )
    )
    await session.commit()

    result = await GhgInventoryMaintenance(session).delete_activity(inventory_code=period.code, record_code=activity.record_code)
    assert result is not None
    assert result.status == "archived"


async def test_activity_generation_is_idempotent(session) -> None:
    _, _organization, period, area, equipment = await _context(session)
    session.add_all(
        [
            m.EnergyIntervalFact(
                source_system="test",
                source_record_id="energy-1",
                energy_type_code="purchased_electricity",
                equipment_id=equipment.id,
                equipment_code=equipment.code,
                equipment_name=equipment.name,
                area_id=str(area.id),
                area_name=area.name,
                granularity="month",
                period_start=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
                period_end=datetime(2026, 1, 31, tzinfo=UTC).replace(tzinfo=None),
                amount=Decimal(1000),
                unit="kWh",
                is_current=True,
            ),
            m.EmployeeCommute(name="张三", category="office", car_power_type=1, mileage=12.5, unit_consumption=8.0),
        ]
    )
    await session.commit()

    usecase = GhgInventoryMaintenance(session)
    first = await usecase.generate_activities(
        inventory_code=period.code,
        reporting_period_id=period.id,
        organization_boundary_id=None,
        source_types=["energy_electricity", "employee_commute"],
    )
    second = await usecase.generate_activities(
        inventory_code=period.code,
        reporting_period_id=period.id,
        organization_boundary_id=None,
        source_types=["energy_electricity", "employee_commute"],
    )

    assert first["createdCount"] == 2
    assert second["createdCount"] == 0
    assert second["updatedCount"] == 2
    records = list((await session.scalars(select(GhgActivityRecord).where(GhgActivityRecord.inventory_code == period.code))).all())
    sources = list((await session.scalars(select(GhgEmissionSource).where(GhgEmissionSource.inventory_code == period.code))).all())
    assert len(records) == 2
    assert len(sources) == 2
    assert {row.iso_category_code for row in records} == {"2.1", "3.3"}
