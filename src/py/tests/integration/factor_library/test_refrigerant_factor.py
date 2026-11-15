"""Apply a refrigerant GWP through the business service, then calculate gas mass."""

from datetime import date
from decimal import Decimal

import pytest
from litestar.exceptions import ClientException
from sqlalchemy import select

from app.db import models as m
from app.domain.factor_library.usecases.factors import CalculationFactorMaintenance
from app.domain.ghg_inventory.domain.catalog import CATEGORY_BY_CODE, METHOD_BY_CODE
from app.domain.ghg_inventory.usecases.allocations import ReplaceActivityAllocations
from app.domain.ghg_inventory.usecases.calculation import RunInventoryCalculation
from app.domain.ghg_inventory.usecases.maintenance import GhgInventoryMaintenance
from tests.integration.ghg_inventory.test_maintenance import _context

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def _refrigerant_context(session, *, method_code="F02_EF", amount="2.4"):
    team, organization, period, area, equipment = await _context(session)
    definition = METHOD_BY_CODE[method_code]
    method = m.GhgCalculationMethodDefinition(
        code=definition.code,
        name=definition.name,
        version="1",
        formula_family=definition.family,
        formula_expression={},
        human_formula=definition.formula,
        standard_code="TEST",
        applicable_categories=["1.4"],
        effective_from=date(2026, 1, 1),
        status="published",
    )
    profile = m.GhgReportingProfile(
        code="TEST-GWP",
        name="测试方案",
        version="1",
        standard_code="TEST",
        standard_version="1",
        effective_from=date(2026, 1, 1),
        status="published",
    )
    factor = m.EmissionFactor(
        team_id=team.id,
        scope="scope1",
        category="refrigerant",
        sub_category="r32",
        unit="kg",
        factor_value=Decimal(675),
        factor_unit="kgCO2e/kg",
        year=2026,
        source="测试GWP假设",
        source_system="enterprise",
        projection_status="manual",
        review_status="approved",
        is_active=True,
    )
    session.add_all([method, profile, factor])
    await session.flush()
    for parameter in definition.parameters:
        session.add(
            m.GhgMethodParameterDefinition(
                method_id=method.id,
                parameter_code=parameter["code"],
                parameter_name=parameter["name"],
                parameter_role=parameter["role"],
                required=parameter["required"],
                allowed_units=parameter["units"],
            )
        )
    await session.commit()
    maintenance = GhgInventoryMaintenance(session)
    await maintenance.create_source(
        {
            "inventory_code": period.code,
            "reporting_period_id": period.id,
            "organization_code": organization.code,
            "facility_code": area.code,
            "source_code": "AC-R32",
            "source_name": "办公空调",
            "iso_category_code": "1.4",
            "default_area_id": area.id,
            "default_equipment_id": equipment.id,
        }
    )
    activity = await maintenance.create_activity(
        {
            "inventory_code": period.code,
            "reporting_period_id": period.id,
            "organization_code": organization.code,
            "facility_code": area.code,
            "source_code": "AC-R32",
            "record_code": "R32-MAINTENANCE",
            "activity_code": "maintenance",
            "activity_name": "空调维修逸散量",
            "iso_category_code": "1.4",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "activity_amount": amount,
            "activity_unit": "kg",
            "data_source_type": "ledger",
            "measurement_method": "维修记录",
            "source_payload": {"gas_code": "R32", "method_code": method_code, "facility_or_device": equipment.name},
        }
    )
    await ReplaceActivityAllocations(session).execute(
        inventory_code=period.code,
        record_code=activity.record_code,
        allocations=[
            {
                "area_id": area.id,
                "equipment_id": equipment.id,
                "allocation_ratio": "1",
                "allocation_role": "physical_origin",
                "source_kind": "manual",
            }
        ],
    )
    return organization, period, profile, activity, factor


@pytest.mark.parametrize("amount", ["2.4", "0"])
async def test_apply_gwp_and_calculate_preserves_real_gas_and_mass(session, amount):
    organization, period, profile, activity, factor = await _refrigerant_context(session, amount=amount)
    assert CATEGORY_BY_CODE["1.4"].default_methods[0] == "F02_EF"
    service = CalculationFactorMaintenance(session)
    candidates = await service.factor_candidates(inventory_code=period.code, record_code=activity.record_code)
    assert candidates["items"][0].match_reason == "推荐匹配"
    for _ in range(2):
        applied = await service.apply_activity_factor(
            inventory_code=period.code,
            record_code=activity.record_code,
            factor_id=factor.id,
            parameter_code=None,
        )
        assert applied.parameter_code == "GWP"
        assert activity.source_payload["gas_code"] == "R32"
        assert activity.source_payload["method_code"] == "F02_EF"
    parameters = list((await session.scalars(select(m.GhgParameterValue))).all())
    assert len(parameters) == 2
    by_code = {row.parameter_code: row for row in parameters}
    assert by_code["GWP"].parameter_role == "characterization"
    assert by_code["EMISSION_FACTOR"].value == 1
    assert by_code["EMISSION_FACTOR"].unit == "kg/kg"
    run = await RunInventoryCalculation(session).execute(
        inventory_code=period.code,
        reporting_profile_code=profile.code,
        reporting_period_id=period.id,
        reporting_org_id=organization.id,
    )
    result = await session.scalar(select(m.GhgCalculationResult).where(m.GhgCalculationResult.run_id == run.id))
    assert result.gas_code == "R32"
    assert result.gas_mass_kg == Decimal(amount)
    assert result.co2e_kg == Decimal(amount) * 675
    assignment = await session.scalar(
        select(m.GhgParameterAssignment).where(m.GhgParameterAssignment.parameter_code == "GWP")
    )
    assert assignment.parameter_role == "characterization"


async def test_gwp_keeps_explicit_inventory_method_and_existing_parameters(session):
    organization, period, profile, activity, factor = await _refrigerant_context(session, method_code="F05_INVENTORY")
    activity.parameter_set_code = "INVENTORY-PARAMS"
    for code in ["OPENING_STOCK", "PURCHASES", "CHARGES", "CLOSING_STOCK", "TRANSFERS", "RECOVERY"]:
        session.add(
            m.GhgParameterValue(
                value_code=f"{period.code}:INVENTORY-PARAMS:{code}",
                version=1,
                parameter_code=code,
                parameter_name=code,
                parameter_role="activity",
                value=Decimal("2.4") if code == "CHARGES" else Decimal(0),
                unit="kg",
                source_mode="measured",
                source_name="测试库存记录",
                approval_status="approved",
                status="active",
            )
        )
    await session.commit()
    await CalculationFactorMaintenance(session).apply_activity_factor(
        inventory_code=period.code,
        record_code=activity.record_code,
        factor_id=factor.id,
        parameter_code="GWP",
    )
    assert activity.source_payload["method_code"] == "F05_INVENTORY"
    assert (
        await session.scalar(
            select(m.GhgParameterValue.id).where(m.GhgParameterValue.parameter_code == "EMISSION_FACTOR")
        )
        is None
    )
    run = await RunInventoryCalculation(session).execute(
        inventory_code=period.code,
        reporting_profile_code=profile.code,
        reporting_period_id=period.id,
        reporting_org_id=organization.id,
    )
    result = await session.scalar(select(m.GhgCalculationResult).where(m.GhgCalculationResult.run_id == run.id))
    assert result.gas_code == "R32"
    assert result.gas_mass_kg == Decimal("2.4")
    assert result.co2e_kg == Decimal(1620)


@pytest.mark.parametrize("invalid", ["gas", "unit", "factor_activity_unit", "factor_unit", "missing_gas"])
async def test_gwp_rejects_wrong_gas_or_units_before_mutation(session, invalid):
    _, period, _, activity, factor = await _refrigerant_context(session)
    if invalid == "gas":
        factor.sub_category = "r410a"
    elif invalid == "unit":
        activity.activity_unit = "t"
    elif invalid == "factor_activity_unit":
        factor.unit = "t"
    elif invalid == "factor_unit":
        factor.factor_unit = "kgCO2e/t"
    else:
        activity.source_payload = {"method_code": "F02_EF"}
    await session.commit()
    payload = dict(activity.source_payload)
    with pytest.raises(ClientException):
        await CalculationFactorMaintenance(session).apply_activity_factor(
            inventory_code=period.code,
            record_code=activity.record_code,
            factor_id=factor.id,
            parameter_code="GWP",
        )
    assert activity.parameter_set_code is None
    assert activity.source_payload == payload
    assert await session.scalar(select(m.GhgParameterValue.id)) is None


@pytest.mark.parametrize("old_value", ["0.5", "675"])
async def test_applying_gwp_rejects_incompatible_existing_factor_without_writes(session, old_value):
    _, period, _, activity, factor = await _refrigerant_context(session)
    activity.parameter_set_code = "CONFIGURED"
    existing = m.GhgParameterValue(
        value_code=f"{period.code}:CONFIGURED:EMISSION_FACTOR",
        version=1,
        parameter_code="EMISSION_FACTOR",
        parameter_name="企业质量系数",
        parameter_role="emission_factor",
        value=Decimal(old_value),
        unit="kg/kg",
        source_mode="custom_approved",
        source_name="企业配置",
        approval_status="approved",
        status="active",
    )
    session.add(existing)
    await session.commit()
    payload = dict(activity.source_payload)
    with pytest.raises(ClientException, match="质量换算系数"):
        await CalculationFactorMaintenance(session).apply_activity_factor(
            inventory_code=period.code,
            record_code=activity.record_code,
            factor_id=factor.id,
            parameter_code="GWP",
        )
    assert existing.value == Decimal(old_value)
    assert existing.source_name == "企业配置"
    assert activity.source_payload == payload
    assert (
        await session.scalar(select(m.GhgParameterValue.id).where(m.GhgParameterValue.parameter_code == "GWP")) is None
    )
