"""Enterprise input returns saved records and generates only monthly canonical facts."""

from __future__ import annotations

import base64
from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO

import msgspec
import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.db import models as m
from app.domain.factor_library.usecases.factors import CalculationFactorMaintenance
from app.domain.ghg_inventory.infrastructure.workbook import build_template_bytes
from app.domain.ghg_inventory.queries.inventory import GhgInventoryQueryService
from app.domain.ghg_inventory.schemas import GhgActivityGenerateResponse, GhgImportBatchResponse
from app.domain.ghg_inventory.usecases.allocations import ReplaceActivityAllocations
from app.domain.ghg_inventory.usecases.calculation import RunInventoryCalculation
from app.domain.ghg_inventory.usecases.import_workbook import (
    CommitCategoryWorkbook,
    PreviewCategoryWorkbook,
    workbook_context,
)
from app.domain.ghg_inventory.usecases.maintenance import GhgInventoryMaintenance
from tests.integration.ghg_inventory.test_maintenance import _context

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


def _workbook(context, rows):
    workbook = load_workbook(BytesIO(build_template_bytes(context)))
    sheet = workbook["03_活动数据"]
    codes = [cell.value for cell in sheet[2]]
    for row in rows:
        sheet.append([row.get(code) for code in codes])
    stream = BytesIO()
    workbook.save(stream)
    return base64.b64encode(stream.getvalue()).decode()


async def test_single_sheet_entry_commit_names_batch_and_conflict(session) -> None:  # noqa: PLR0915 - import lifecycle and combined status/batch filters
    _, organization, period, area, equipment = await _context(session)
    context = await workbook_context(
        session,
        {
            "inventory_code": period.code,
            "reporting_period_id": period.id,
            "organization_code": organization.code,
            "facility_code": area.code,
            "iso_category_code": "1.4",
            "method_code": "F05_INVENTORY",
            "reporting_profile_code": "CORPORATE_ISO14064_GHGP",
        },
    )
    request = {
        **context,
        "file_name": "空调维护.xlsx",
        "workbook_base64": _workbook(
            context,
            [
                {
                    "source_name": "办公楼空调维护",
                    "area_name": area.name,
                    "equipment_name": equipment.name,
                    "facility_or_device": equipment.name,
                    "gas_code": "R32",
                    "activity_amount": 0,
                    "activity_unit": "kg",
                    "period_start": "2026-01-01",
                    "period_end": "2026-01-31",
                }
            ],
        ),
    }
    batch = await PreviewCategoryWorkbook(session).execute(request)
    assert batch.status == "previewed"
    assert batch.warning_count == 0
    query = GhgInventoryQueryService(session)
    preview_dto = msgspec.convert(await query.import_result_payload(batch), type=GhgImportBatchResponse)
    assert preview_dto.preview.activities[0].source_name == "办公楼空调维护"
    assert preview_dto.preview.activities[0].equipment_name == equipment.name
    assert preview_dto.preview.activities[0].activity_amount == 0
    assert preview_dto.committed_count == 0
    commit = CommitCategoryWorkbook(session)
    batch = await commit.execute(batch.batch_code, acknowledge_warnings=False)
    response = msgspec.convert(await query.import_result_payload(batch), type=GhgImportBatchResponse)
    assert response.committed_count == 1
    record = response.committed_rows[0]
    assert record.organization_name == organization.name
    assert record.facility_name == area.name
    assert record.source_name == "办公楼空调维护"
    assert record.allocated_equipment_names == [equipment.name]
    assert record.batch_code == batch.batch_code
    assert Decimal(response.summary[0].activity_amount) == 0
    assert response.activity_filters == {"inventoryCode": period.code, "batchCode": batch.batch_code}
    saved = await session.scalar(
        select(m.GhgActivityRecord).where(m.GhgActivityRecord.record_code == record.record_code)
    )
    await GhgInventoryMaintenance(session).update_activity(
        saved.record_code,
        {
            "record_code": saved.record_code,
            "inventory_code": saved.inventory_code,
            "organization_code": saved.organization_code,
            "facility_code": saved.facility_code,
            "source_code": saved.source_code,
            "activity_code": saved.activity_code,
            "activity_name": saved.activity_name,
            "period_start": saved.period_start.isoformat(),
            "period_end": saved.period_end.isoformat(),
            "iso_category_code": saved.iso_category_code,
            "activity_amount": "3",
            "activity_unit": saved.activity_unit,
            "data_source_type": saved.data_source_type,
            "measurement_method": saved.measurement_method,
            "source_payload": {"gas_code": "R32", "facility_or_device": equipment.name},
        },
    )
    assert saved.source_system == "xlsx_import"
    assert saved.source_record_type == "ghg_import_batch"
    assert saved.source_record_id == batch.id
    repeated = await commit.execute(batch.batch_code, acknowledge_warnings=False)
    current = await query.import_result_payload(repeated)
    assert current["committedCount"] == 1
    assert Decimal(current["committedRows"][0]["activityAmount"]) == 3
    conflict = await PreviewCategoryWorkbook(session).execute(request)
    assert conflict.status == "blocked"
    assert conflict.valid_count == 0
    assert "RECORD_ALREADY_EXISTS" in {row["issueCode"] for row in conflict.preview_snapshot["issues"]}
    with pytest.raises(ValueError, match="阻断错误"):
        await commit.execute(conflict.batch_code, acknowledge_warnings=False)
    filtered = await query.activities(
        inventory_code=None, category_code=None, quality_status=None, batch_code=batch.batch_code, limit=100, offset=0
    )
    assert filtered["total"] == 1
    args = {
        "inventory_code": period.code,
        "category_code": "1.4",
        "quality_status": None,
        "batch_code": batch.batch_code,
        "limit": 1,
        "offset": 0,
    }
    assert (await query.activities(**args, status="available"))["total"] == 1
    saved.status = "archived"
    await session.commit()
    assert (await query.activities(**args, status="available"))["total"] == 0
    assert (await query.activities(**args, status="approved"))["total"] == 0
    assert (await query.activities(**args, status="archived"))["total"] == 1
    assert (await query.activities(**args))["total"] == 1
    page = await query.activities(**{**args, "offset": 1}, status="archived")
    assert page["total"] == 1
    assert page["items"] == []
    assert (
        await query.activities(
            inventory_code=None, category_code=None, quality_status=None, batch_code="missing", limit=100, offset=0
        )
    )["total"] == 0


def _fact(equipment, area, code, energy, amount, unit, *, month=1, granularity="month", snapshot=None, boundary=None):
    return m.EnergyIntervalFact(
        source_system="enterprise_test",
        source_record_id=code,
        energy_type_code=energy,
        equipment_id=equipment.id,
        equipment_code=equipment.code,
        equipment_name=equipment.name,
        area_id=str(area.id),
        area_name=area.name,
        granularity=granularity,
        period_start=datetime(2026, month, 1, tzinfo=UTC).replace(tzinfo=None),
        period_end=datetime(2026, month, 28, tzinfo=UTC).replace(tzinfo=None),
        amount=Decimal(amount),
        unit=unit,
        is_current=True,
        source_snapshot=snapshot,
        measurement_boundary_id=boundary.id if boundary else None,
    )


async def test_monthly_energy_generation_units_names_factors_and_boundary(session) -> None:  # noqa: PLR0915 - correction and recalculation preserve historical snapshots
    team, organization, period, area, equipment = await _context(session)
    other_equipment = m.MonitorEquipment(code="SUB", name="车间分表", sector_id=area.id)
    session.add(other_equipment)
    await session.flush()
    boundary = m.MeasurementBoundary(
        code="SUB", name="分表边界", meter_equipment_id=other_equipment.id, sector_id=area.id, include_in_scope2=False
    )
    session.add(boundary)
    await session.flush()
    session.add_all(
        [
            _fact(equipment, area, "electricity", "purchased_electricity", 1000, "kWh"),
            _fact(equipment, area, "electricity-feb", "purchased_electricity", 1200, "kWh", month=2),
            _fact(equipment, area, "gas", "natural_gas", 20, "m3"),
            _fact(equipment, area, "diesel", "diesel", 30, "L", snapshot={"iso_category_code": "1.2"}),
            _fact(other_equipment, area, "sub", "purchased_electricity", 999, "kWh"),
            _fact(equipment, area, "electricity-hour", "purchased_electricity", 9999, "kWh", granularity="hour"),
            _fact(equipment, area, "electricity-day", "purchased_electricity", 9999, "kWh", granularity="day"),
            m.EmployeeCommute(name="柴油通勤", car_power_type=0, mileage=12.5),
        ]
    )
    await session.commit()
    usecase = GhgInventoryMaintenance(session)
    args = {
        "inventory_code": period.code,
        "reporting_period_id": period.id,
        "organization_boundary_id": None,
        "source_types": ["energy_electricity", "energy_natural_gas", "energy_diesel", "employee_commute"],
        "facility_code": area.code,
    }
    response = await usecase.generate_activities(**args)
    dto = msgspec.convert(response, type=GhgActivityGenerateResponse)
    assert dto.created_count == 4
    assert dto.failed_count == 0
    assert {row.activity_unit: Decimal(row.activity_amount) for row in dto.summary} == {
        "kWh": Decimal(2200),
        "m3": Decimal(20),
        "L": Decimal(30),
    }
    assert all(row.allocated_equipment_names == [equipment.name] for row in dto.records)
    assert {row.period_start for row in dto.records} == {"2026-01-01", "2026-02-01"}
    assert all(row.iso_category_code != "3.3" for row in dto.records)
    assert any("没有日期" in message for message in dto.messages)
    assert any("尚未选择排放因子" in message for message in dto.messages)
    first_codes = set(dto.record_codes)
    repeated = await usecase.generate_activities(**args)
    assert repeated["createdCount"] == 0
    assert repeated["updatedCount"] == 4
    assert set(repeated["recordCodes"]) == first_codes
    only_diesel = await usecase.generate_activities(**{**args, "iso_category_code": "1.2"})
    assert len(only_diesel["records"]) == 1
    assert only_diesel["records"][0]["activityUnit"] == "L"
    assert (
        await session.scalar(select(m.GhgActivityRecord).where(m.GhgActivityRecord.iso_category_code == "3.3")) is None
    )

    # Existing factor selection remains the only factor application workflow.
    profile = m.GhgReportingProfile(
        code="TEST-PROFILE",
        name="测试报告",
        version="1",
        standard_code="TEST",
        standard_version="1",
        effective_from=date(2026, 1, 1),
        status="published",
    )
    methods = []
    for code, parameter, unit in [
        ("F08_PURCHASED_ENERGY", "ENERGY_FACTOR", "kgCO2e/kWh"),
        ("F02_EF", "EMISSION_FACTOR", "kgCO2e/unit"),
    ]:
        method = m.GhgCalculationMethodDefinition(
            code=code,
            version="1",
            name=code,
            formula_family=code.split("_")[0],
            formula_expression={},
            human_formula="测试方法",
            standard_code="TEST",
            applicable_categories=[],
            effective_from=date(2026, 1, 1),
            status="published",
        )
        session.add(method)
        await session.flush()
        session.add(
            m.GhgMethodParameterDefinition(
                method_id=method.id,
                parameter_code=parameter,
                parameter_name="测试因子",
                parameter_role="emission_factor",
                allowed_units=[unit],
                required=True,
            )
        )
        methods.append(method)
    session.add(profile)
    await session.commit()
    factors = CalculationFactorMaintenance(session)
    for record in dto.records:
        factor = m.EmissionFactor(
            team_id=team.id,
            scope=record.ghg_scope,
            category="electricity" if record.iso_category_code == "2.1" else "fuel",
            sub_category="test-" + record.record_code,
            unit=record.activity_unit,
            factor_value=Decimal(2),
            factor_unit=f"kgCO2e/{record.activity_unit}",
            year=2026,
            source="仅测试假设",
            review_status="approved",
            is_active=True,
        )
        session.add(factor)
        await session.commit()
        await factors.apply_activity_factor(
            inventory_code=period.code, record_code=record.record_code, factor_id=factor.id, parameter_code=None
        )
    refreshed = await usecase.generate_activities(**args)
    assert all(row["parameterSetCode"] for row in refreshed["records"])
    run = await RunInventoryCalculation(session).execute(
        inventory_code=period.code,
        reporting_profile_code=profile.code,
        reporting_period_id=period.id,
        reporting_org_id=organization.id,
    )
    assert run.total_co2e_kg == Decimal(4500)
    old_run_snapshot = await _run_snapshot(session, run)
    existing_records = list((await session.scalars(select(m.GhgActivityRecord))).all())
    activity_before = {
        row.id: (row.record_code, row.parameter_set_code, row.source_payload["factor_id"]) for row in existing_records
    }
    allocations_before = [
        (row.id, row.activity_id, row.area_id, row.equipment_id, row.allocation_ratio)
        for row in (await session.scalars(select(m.GhgActivityAllocation).order_by(m.GhgActivityAllocation.id))).all()
    ]
    sources_before = {
        row.id: (row.source_name, row.source_payload, row.default_area_id, row.updated_at)
        for row in (await session.scalars(select(m.GhgEmissionSource))).all()
    }
    changed_fact = await session.scalar(
        select(m.EnergyIntervalFact).where(m.EnergyIntervalFact.source_record_id == "electricity")
    )
    changed_fact.amount = Decimal(9000)
    equipment.name = "新的设备名称"
    changed_fact.equipment_name = equipment.name
    await session.commit()
    corrected = await usecase.generate_activities(**args)
    assert corrected["createdCount"] == 0
    assert corrected["updatedCount"] == 4
    assert corrected["failedCount"] == 0
    assert set(corrected["recordCodes"]) == first_codes
    assert len(corrected["records"]) == 4
    assert {row["activityUnit"]: Decimal(row["activityAmount"]) for row in corrected["summary"]} == {
        "kWh": Decimal(10200),
        "m3": Decimal(20),
        "L": Decimal(30),
    }
    for row in existing_records:
        await session.refresh(row)
        assert (row.record_code, row.parameter_set_code, row.source_payload["factor_id"]) == activity_before[row.id]
    changed_activity = next(row for row in existing_records if row.source_record_id == changed_fact.id)
    assert changed_activity.activity_amount == Decimal(9000)
    assert [
        (row.id, row.activity_id, row.area_id, row.equipment_id, row.allocation_ratio)
        for row in (await session.scalars(select(m.GhgActivityAllocation).order_by(m.GhgActivityAllocation.id))).all()
    ] == allocations_before
    assert {
        row.id: (row.source_name, row.source_payload, row.default_area_id, row.updated_at)
        for row in (await session.scalars(select(m.GhgEmissionSource))).all()
    } == sources_before
    assert await _run_snapshot(session, run) == old_run_snapshot
    new_run = await RunInventoryCalculation(session).execute(
        inventory_code=period.code,
        reporting_profile_code=profile.code,
        reporting_period_id=period.id,
        reporting_org_id=organization.id,
    )
    assert new_run.id != run.id
    assert new_run.total_co2e_kg == Decimal(20500)
    assert await _run_snapshot(session, run) == old_run_snapshot
    new_result = await session.scalar(
        select(m.GhgCalculationResult).where(
            m.GhgCalculationResult.run_id == new_run.id,
            m.GhgCalculationResult.activity_id == changed_activity.id,
        )
    )
    assert Decimal(new_result.formula_snapshot["activity"]["value"]) == Decimal(9000)
    assert new_result.co2e_kg == Decimal(18000)


async def _run_snapshot(session, run):
    await session.refresh(run)
    results = (
        await session.scalars(
            select(m.GhgCalculationResult)
            .where(m.GhgCalculationResult.run_id == run.id)
            .order_by(m.GhgCalculationResult.id)
            .execution_options(populate_existing=True)
        )
    ).all()
    assignments = (
        await session.scalars(
            select(m.GhgParameterAssignment)
            .where(m.GhgParameterAssignment.run_id == run.id)
            .order_by(m.GhgParameterAssignment.id)
            .execution_options(populate_existing=True)
        )
    ).all()
    return deepcopy(
        (
            run.total_co2e_kg,
            run.input_snapshot,
            run.summary_snapshot,
            run.quality_snapshot,
            [(row.id, row.activity_id, row.co2e_kg, row.gas_mass_kg, row.formula_snapshot) for row in results],
            [(row.id, row.activity_id, row.value, row.unit, row.snapshot) for row in assignments],
        )
    )


async def test_invalid_monthly_overlap_and_unclassified_diesel_do_not_generate(session) -> None:
    _, _, period, area, equipment = await _context(session)
    session.add_all(
        [
            _fact(equipment, area, "a", "purchased_electricity", 10, "kWh"),
            _fact(equipment, area, "b", "purchased_electricity", 20, "kWh"),
            _fact(equipment, area, "diesel", "diesel", 30, "L"),
        ]
    )
    await session.commit()
    response = await GhgInventoryMaintenance(session).generate_activities(
        inventory_code=period.code,
        reporting_period_id=period.id,
        organization_boundary_id=None,
        source_types=["energy_electricity", "energy_diesel"],
    )
    assert response["createdCount"] == 0
    assert response["failedCount"] == 2
    assert response["records"] == []
    assert any("未确定固定源或移动源" in message for message in response["messages"])


async def test_catalog_meter_points_use_enabled_configured_device_points(session) -> None:
    from app.domain.ghg_inventory.controllers.inventory import GhgInventoryController

    _, _, _, _area, equipment = await _context(session)
    equipment.energy_type = "natural_gas"
    active = m.DevicePoint(device_id=equipment.id, point_code="volume", point_name="燃气累计体积", unit="m3")
    disabled = m.DevicePoint(device_id=equipment.id, point_code="disabled", point_name="已停用体积", is_enabled=False)
    session.add_all([active, disabled])
    await session.commit()
    payload = await GhgInventoryController.catalog.fn(None, db_session=session)
    assert len(payload.meter_points) == 1
    point = payload.meter_points[0]
    assert point.equipment_id == equipment.id
    assert point.code == f"{equipment.code}:volume"
    assert point.name == f"{equipment.name} / 燃气累计体积"
    assert point.unit == "m3"
    assert point.energy_type == "natural_gas"


async def test_regeneration_preserves_manual_allocations_and_selected_factor(session) -> None:
    team, _, period, area, equipment = await _context(session)
    fact = _fact(equipment, area, "preserve", "purchased_electricity", 1000, "kWh")
    session.add(fact)
    await session.commit()
    usecase = GhgInventoryMaintenance(session)
    args = {
        "inventory_code": period.code,
        "reporting_period_id": period.id,
        "organization_boundary_id": None,
        "source_types": ["energy_electricity"],
    }
    generated = await usecase.generate_activities(**args)
    record_code = generated["recordCodes"][0]
    activity = await session.scalar(select(m.GhgActivityRecord).where(m.GhgActivityRecord.record_code == record_code))
    child = m.MonitorSector(code="CHILD", name="人工归集车间", parent_id=area.id, path="/ROOT/CHILD", level=1)
    session.add(child)
    await session.flush()
    child_device = m.MonitorEquipment(code="CHILD-DEVICE", name="人工归集设备", sector_id=child.id)
    session.add(child_device)
    await session.flush()
    allocations = await ReplaceActivityAllocations(session).execute(
        inventory_code=period.code,
        record_code=record_code,
        allocations=[
            {
                "allocation_code": "MANUAL-A",
                "area_id": child.id,
                "equipment_id": child_device.id,
                "allocation_role": "energy_consumption",
                "allocation_ratio": "0.25",
                "source_kind": "manual",
            },
            {
                "allocation_code": "MANUAL-B",
                "area_id": area.id,
                "equipment_id": equipment.id,
                "allocation_role": "energy_consumption",
                "allocation_ratio": "0.75",
                "source_kind": "manual",
            },
        ],
    )
    allocation_before = {
        row.id: (row.area_id, row.equipment_id, row.allocation_code, row.allocation_ratio, row.source_kind)
        for row in allocations
    }
    source = await session.get(m.GhgEmissionSource, activity.emission_source_id)
    source.source_name = "人工维护的购电对象"
    factor = m.EmissionFactor(
        team_id=team.id,
        scope="scope2",
        category="electricity",
        sub_category="test-only",
        unit="kWh",
        factor_value=Decimal("0.5"),
        factor_unit="kgCO2e/kWh",
        year=2026,
        source="仅限测试的排放因子假设",
        review_status="approved",
        is_active=True,
    )
    session.add(factor)
    await session.commit()
    await CalculationFactorMaintenance(session).apply_activity_factor(
        inventory_code=period.code, record_code=record_code, factor_id=factor.id, parameter_code=None
    )
    parameter_before = activity.parameter_set_code
    selected_before = {
        key: activity.source_payload[key]
        for key in ("method_code", "factor_id", "factor_source", "factor_year", "factor_unit", "gas_code")
    }
    parameter_values_before = [
        (row.id, row.value_code, row.value, row.source_name)
        for row in (await session.scalars(select(m.GhgParameterValue))).all()
    ]
    fact.amount = Decimal(2000)
    await session.commit()
    repeated = await usecase.generate_activities(**args)
    assert repeated["createdCount"] == 0
    assert repeated["updatedCount"] == 1
    assert Decimal(repeated["records"][0]["activityAmount"]) == 2000
    assert repeated["records"][0]["sourceName"] == "人工维护的购电对象"
    assert equipment.name is not None and child_device.name is not None
    assert repeated["records"][0]["allocatedEquipmentNames"] == sorted([equipment.name, child_device.name])
    await session.refresh(activity)
    await session.refresh(source)
    assert activity.parameter_set_code == parameter_before
    assert {key: activity.source_payload[key] for key in selected_before} == selected_before
    assert source.default_area_id == child.id
    assert source.default_equipment_id == child_device.id
    assert {
        row.id: (row.area_id, row.equipment_id, row.allocation_code, row.allocation_ratio, row.source_kind)
        for row in (
            await session.scalars(
                select(m.GhgActivityAllocation).where(m.GhgActivityAllocation.activity_id == activity.id)
            )
        ).all()
    } == allocation_before
    assert [
        (row.id, row.value_code, row.value, row.source_name)
        for row in (await session.scalars(select(m.GhgParameterValue))).all()
    ] == parameter_values_before


@pytest.mark.parametrize("lock_field", ["status", "locked_at"])
async def test_generation_refuses_locked_reporting_period_without_writes(session, lock_field) -> None:
    _, _, period, area, equipment = await _context(session)
    session.add(_fact(equipment, area, "locked", "purchased_electricity", 1000, "kWh"))
    setattr(
        period,
        lock_field,
        "locked" if lock_field == "status" else datetime(2026, 2, 1, tzinfo=UTC).replace(tzinfo=None),
    )
    await session.commit()
    with pytest.raises(ValueError, match="报告期已锁定"):
        await GhgInventoryMaintenance(session).generate_activities(
            inventory_code=period.code,
            reporting_period_id=period.id,
            organization_boundary_id=None,
            source_types=["energy_electricity"],
        )
    assert not list((await session.scalars(select(m.GhgActivityRecord))).all())
    assert not list((await session.scalars(select(m.GhgEmissionSource))).all())


@pytest.mark.parametrize(("binding", "category"), [("equipment", "1.1"), ("equipment", "1.2"), ("facility", "1.2")])
async def test_diesel_crud_without_snapshot_reuses_configured_source(session, binding, category) -> None:
    from app.domain.energy.controllers.consumption import EnergyConsumptionController

    _, organization, period, area, equipment = await _context(session)
    session.add(m.EnergyType(code="diesel", name="柴油", category="fuel", default_scope="scope1", original_unit="L"))
    session.add(
        m.GhgParameterValue(
            value_code=f"{period.code}:DIESEL-DEFAULT:EMISSION_FACTOR",
            version=1,
            parameter_code="EMISSION_FACTOR",
            parameter_name="测试因子",
            parameter_role="emission_factor",
            value=Decimal("0.5"),
            unit="kgCO2e/L",
            source_mode="custom_approved",
            source_name="仅测试假设",
            approval_status="approved",
            status="active",
        )
    )
    await session.commit()
    usecase = GhgInventoryMaintenance(session)
    source = await usecase.create_source(
        {
            "inventory_code": period.code,
            "organization_code": organization.code,
            "facility_code": area.code,
            "reporting_period_id": period.id,
            "source_code": "DIESEL-USE",
            "source_name": "企业柴油用途",
            "iso_category_code": category,
            "default_area_id": area.id,
            "default_equipment_id": equipment.id if binding == "equipment" else None,
            "default_allocation_role": "asset_location" if category == "1.2" else "physical_origin",
            "source_payload": {"method_code": "F02_EF", "parameter_set_code": "DIESEL-DEFAULT"},
        }
    )
    await EnergyConsumptionController.create_energy_interval_fact.fn(
        None,
        db_session=session,
        data={
            "energy_type_code": "diesel",
            "equipment_id": equipment.id,
            "area_id": str(area.id),
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "amount": "30",
            "unit": "L",
            "granularity": "month",
            "source_record_id": "UI-DIESEL",
            "data_quality": "measured",
        },
    )
    fact = await session.scalar(
        select(m.EnergyIntervalFact).where(m.EnergyIntervalFact.source_record_id == "UI-DIESEL")
    )
    assert fact.source_snapshot is None
    args = {
        "inventory_code": period.code,
        "reporting_period_id": period.id,
        "organization_boundary_id": None,
        "facility_code": area.code,
        "source_types": ["energy_diesel"],
        "iso_category_code": category,
    }
    first = await usecase.generate_activities(**args)
    assert first["createdCount"] == 1
    record = first["records"][0]
    assert record["sourceCode"] == source.source_code
    assert record["sourceName"] == source.source_name
    assert record["isoCategoryCode"] == category
    assert Decimal(record["activityAmount"]) == 30
    assert record["parameterSetCode"] == "DIESEL-DEFAULT"
    activity = await session.scalar(
        select(m.GhgActivityRecord).where(m.GhgActivityRecord.record_code == record["recordCode"])
    )
    assert activity.emission_source_id == source.id
    assert activity.source_payload["method_code"] == "F02_EF"
    allocations = list(
        (
            await session.scalars(
                select(m.GhgActivityAllocation).where(m.GhgActivityAllocation.activity_id == activity.id)
            )
        ).all()
    )
    assert len(allocations) == 1
    assert allocations[0].area_id == source.default_area_id
    assert allocations[0].equipment_id == source.default_equipment_id
    assert allocations[0].allocation_role == source.default_allocation_role
    second = await usecase.generate_activities(**args)
    assert second["createdCount"] == 0
    assert second["updatedCount"] == 1
    assert second["recordCodes"] == first["recordCodes"]
    assert len(list((await session.scalars(select(m.GhgEmissionSource))).all())) == 1
    assert len(list((await session.scalars(select(m.GhgActivityRecord))).all())) == 1


async def test_ambiguous_diesel_sources_require_explicit_source_selection(session) -> None:
    _, organization, period, area, equipment = await _context(session)
    usecase = GhgInventoryMaintenance(session)
    for code, category in [("STATIONARY", "1.1"), ("MOBILE", "1.2")]:
        await usecase.create_source(
            {
                "inventory_code": period.code,
                "organization_code": organization.code,
                "facility_code": area.code,
                "source_code": code,
                "source_name": code,
                "iso_category_code": category,
                "default_area_id": area.id,
                "default_equipment_id": equipment.id,
            }
        )
    session.add(_fact(equipment, area, "ambiguous-diesel", "diesel", 30, "L"))
    await session.commit()
    args = {
        "inventory_code": period.code,
        "reporting_period_id": period.id,
        "organization_boundary_id": None,
        "source_types": ["energy_diesel"],
    }
    blocked = await usecase.generate_activities(**args)
    assert blocked["createdCount"] == 0
    assert blocked["failedCount"] == 1
    assert any("匹配多个排放源" in message for message in blocked["messages"])
    explicit = await usecase.generate_activities(**args, source_code="MOBILE")
    assert explicit["createdCount"] == 1
    assert explicit["records"][0]["sourceCode"] == "MOBILE"
    assert explicit["records"][0]["isoCategoryCode"] == "1.2"
    repeated = await usecase.generate_activities(**args, source_code="MOBILE")
    assert repeated["createdCount"] == 0
    assert repeated["updatedCount"] == 1
    assert len(list((await session.scalars(select(m.GhgEmissionSource))).all())) == 2


@pytest.mark.parametrize("status", ["locked", "archived"])
async def test_generation_returns_retained_protected_record_without_mutation(session, status) -> None:
    _, _, period, area, equipment = await _context(session)
    fact = _fact(equipment, area, "retained", "purchased_electricity", 1000, "kWh")
    session.add(fact)
    await session.commit()
    usecase = GhgInventoryMaintenance(session)
    args = {
        "inventory_code": period.code,
        "reporting_period_id": period.id,
        "organization_boundary_id": None,
        "source_types": ["energy_electricity"],
    }
    first = await usecase.generate_activities(**args)
    activity = await session.scalar(
        select(m.GhgActivityRecord).where(m.GhgActivityRecord.record_code == first["recordCodes"][0])
    )
    activity.status = status
    fact.amount = Decimal(2000)
    await session.commit()
    before = (activity.activity_amount, activity.source_payload, activity.updated_at)
    retained = await usecase.generate_activities(**args)
    assert retained["createdCount"] == retained["updatedCount"] == retained["failedCount"] == 0
    assert retained["skippedCount"] == 1
    assert retained["recordCodes"] == first["recordCodes"]
    assert retained["records"][0]["status"] == status
    assert Decimal(retained["records"][0]["activityAmount"]) == 1000
    assert Decimal(retained["summary"][0]["activityAmount"]) == 1000
    await session.refresh(activity)
    assert (activity.activity_amount, activity.source_payload, activity.updated_at) == before
