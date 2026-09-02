from __future__ import annotations

import base64
from datetime import date
from decimal import Decimal

import pytest
from litestar.exceptions import PermissionDeniedException
from sqlalchemy import func, select

from app.db import models as m
from app.domain.factor_library.schemas import CalculationFactorWriteRequest
from app.domain.factor_library.usecases.factors import CalculationFactorMaintenance
from app.domain.ghg_inventory.models import GhgActivityRecord, GhgParameterValue
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def _tenant_context(session):
    team = m.Team(name="Factor Maintenance Tenant", slug="factor-maintenance-tenant")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id

    organization = m.ReportingOrganization(code="ORG-FACTOR", name="因子测试组织")
    session.add(organization)
    await session.flush()
    period = m.ReportingPeriod(
        reporting_org_id=organization.id,
        code="FACTOR-2026",
        name="2026年度",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        status="active",
    )
    session.add(period)
    await session.commit()
    return team, organization, period


async def _shared_factor(session) -> m.EmissionFactor:
    factor = m.EmissionFactor(
        scope="scope2",
        category="electricity",
        sub_category="grid_electricity_jiangsu",
        unit="kWh",
        factor_value=Decimal("0.5827"),
        factor_unit="kgCO2e/kWh",
        year=2026,
        source="共享电力排放因子",
        source_system="ncsc_ghg_efdb",
        projection_status="direct",
        review_status="approved",
        is_active=True,
    )
    session.add(factor)
    await session.commit()
    return factor


async def test_enterprise_factor_crud_and_shared_readonly(session) -> None:
    team, _organization, _period = await _tenant_context(session)
    shared = await _shared_factor(session)
    usecase = CalculationFactorMaintenance(session)

    listed = await usecase.list_factors(limit=20, offset=0, keyword=None, scope="scope2", category="electricity", is_active=True, owner=None)
    assert listed["total"] == 1
    assert listed["items"][0].owner_type == "shared"
    assert listed["items"][0].editable is False

    created = await usecase.create_factor(
        CalculationFactorWriteRequest(
            scope="scope2",
            category="electricity",
            sub_category="grid_electricity_zhejiang",
            unit="kWh",
            factor_value=Decimal("0.5153"),
            factor_unit="kgCO2e/kWh",
            year=2026,
            source="企业审定浙江电力因子",
            source_system="enterprise",
            projection_status="manual",
            review_status="approved",
            is_active=True,
        )
    )
    assert created.owner_type == "enterprise"
    assert created.editable is True

    updated = await usecase.update_factor(
        created.id,
        CalculationFactorWriteRequest(
            scope="scope2",
            category="electricity",
            sub_category="grid_electricity_zhejiang",
            unit="kWh",
            factor_value=Decimal("0.5000"),
            factor_unit="kgCO2e/kWh",
            year=2026,
            source="企业审定浙江电力因子",
            source_system="enterprise",
            projection_status="manual",
            review_status="approved",
            is_active=True,
        ),
    )
    assert updated.factor_value == "0.5000"

    with pytest.raises(PermissionDeniedException):
        await usecase.update_factor(
            shared.id,
            CalculationFactorWriteRequest(
                scope="scope2",
                category="electricity",
                sub_category="grid_electricity_jiangsu",
                unit="kWh",
                factor_value=Decimal("0.5827"),
                factor_unit="kgCO2e/kWh",
                year=2026,
                source="共享电力排放因子",
                source_system="ncsc_ghg_efdb",
                projection_status="direct",
                review_status="approved",
                is_active=True,
            ),
        )

    await usecase.delete_factor(created.id)
    remaining = await session.scalar(select(m.EmissionFactor).where(m.EmissionFactor.id == created.id, m.EmissionFactor.team_id == team.id))
    assert remaining is None


async def test_factor_template_import_is_idempotent(session) -> None:
    team, _organization, _period = await _tenant_context(session)
    usecase = CalculationFactorMaintenance(session)
    csv_text = (
        "scope,category,sub_category,unit,factor_value,factor_unit,year,source,source_system,"
        "source_snapshot_id,raw_record_id,projection_status,review_status,is_active,note\n"
        "scope1,fuel,diesel,L,2.63,kgCO2e/L,2026,企业审定柴油因子,enterprise,,,manual,approved,true,\n"
    )
    csv_base64 = base64.b64encode(csv_text.encode()).decode()

    preview = await usecase.preview_import(file_name="calculation-factor-template.csv", csv_base64=csv_base64)
    assert preview.error_count == 0
    assert preview.create_count == 1

    first = await usecase.commit_import(file_name="calculation-factor-template.csv", csv_base64=csv_base64)
    assert first.create_count == 1
    second = await usecase.commit_import(file_name="calculation-factor-template.csv", csv_base64=csv_base64)
    assert second.update_count == 1

    count = await session.scalar(
        select(func.count()).select_from(m.EmissionFactor).where(m.EmissionFactor.team_id == team.id, m.EmissionFactor.sub_category == "diesel")
    )
    assert count == 1


async def test_apply_activity_factor_writes_parameter_value(session) -> None:
    team, organization, period = await _tenant_context(session)
    method = m.GhgCalculationMethodDefinition(
        code="F08_PURCHASED_ENERGY",
        version="1",
        name="购入能源核算",
        formula_family="F08",
        formula_expression={},
        human_formula="活动量 x 能源因子",
        standard_code="ISO 14064-1",
        applicable_categories=["2.1"],
        applicable_gases=["CO2e"],
        effective_from=date(2026, 1, 1),
    )
    session.add(method)
    await session.flush()
    session.add(
        m.GhgMethodParameterDefinition(
            method_id=method.id,
            parameter_code="ENERGY_FACTOR",
            parameter_name="购入能源排放因子",
            parameter_role="emission_factor",
            allowed_units=["kgCO2e/kWh"],
        )
    )
    factor = m.EmissionFactor(
        team_id=team.id,
        scope="scope2",
        category="electricity",
        sub_category="electricity",
        unit="kWh",
        factor_value=Decimal("0.5000"),
        factor_unit="kgCO2e/kWh",
        year=2026,
        source="企业审定电力因子",
        source_system="enterprise",
        projection_status="manual",
        review_status="approved",
        is_active=True,
    )
    activity = GhgActivityRecord(
        record_code="ACT-FACTOR-01",
        inventory_code=period.code,
        reporting_period_id=period.id,
        organization_code=organization.code,
        facility_code="PLANT-01",
        source_code="SRC-ELEC-01",
        activity_code="purchased-electricity",
        activity_name="购入电力",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        iso_category_code="2.1",
        ghg_scope="scope2",
        source_mechanism="energy",
        value_chain_position="upstream",
        activity_amount=Decimal(1000),
        activity_unit="kWh",
        data_source_type="measured",
        measurement_method="电表计量",
        source_payload={"energy_type": "electricity"},
        status="approved",
    )
    session.add_all([factor, activity])
    await session.commit()

    result = await CalculationFactorMaintenance(session).apply_activity_factor(
        inventory_code=period.code,
        record_code=activity.record_code,
        factor_id=factor.id,
        parameter_code=None,
    )
    assert result.parameter_code == "ENERGY_FACTOR"
    assert result.factor_value == "0.5000"

    saved = await session.scalar(
        select(GhgParameterValue).where(
            GhgParameterValue.team_id == team.id,
            GhgParameterValue.value_code == f"{period.code}:ACT-FACTOR-01-PS1:ENERGY_FACTOR",
        )
    )
    assert saved is not None
    assert saved.value == Decimal("0.500000000000")
