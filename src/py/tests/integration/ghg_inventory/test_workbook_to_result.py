"""Verify that a category workbook can be imported and calculated."""

import base64
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.db import models as m
from app.domain.ghg_inventory.infrastructure.workbook import build_template_bytes
from app.domain.ghg_inventory.models import GhgCalculationResult
from app.domain.ghg_inventory.usecases.calculation import RunInventoryCalculation
from app.domain.ghg_inventory.usecases.import_workbook import CommitCategoryWorkbook, PreviewCategoryWorkbook
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


def _set_row(workbook, sheet_name: str, values: dict[str, object], *, row: int = 3) -> None:
    sheet = workbook[sheet_name]
    codes = [str(cell.value or "") for cell in sheet[2]]
    for column, code in enumerate(codes, start=1):
        if code in values:
            sheet.cell(row=row, column=column, value=values[code])


async def test_category_workbook_import_reaches_organization_result(session) -> None:
    team = m.Team(name="Workbook Flow Tenant", slug="workbook-flow-tenant")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    organization = m.ReportingOrganization(code="ORG-TEST", name="测试组织")
    session.add(organization)
    await session.flush()
    period = m.ReportingPeriod(
        reporting_org_id=organization.id,
        code="INV-TEST-2026",
        name="2026 年测试盘查期",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        status="active",
    )
    area = m.MonitorSector(code="ROOT", name="测试区域", path="/ROOT", level=0)
    profile = m.GhgReportingProfile(
        code="CORPORATE_ISO14064_GHGP",
        name="测试报告方案",
        version="1",
        standard_code="ISO 14064-1",
        standard_version="2018",
        effective_from=date(2026, 1, 1),
        status="published",
    )
    method = m.GhgCalculationMethodDefinition(
        code="F08_PURCHASED_ENERGY",
        version="1",
        name="购入能源因子法",
        formula_family="F08",
        formula_expression={},
        human_formula="购入电量乘以排放因子",
        standard_code="TEST-METHOD",
        applicable_categories=["2.1"],
        effective_from=date(2026, 1, 1),
        status="published",
    )
    session.add_all([period, area, profile, method])
    await session.flush()
    boundary = m.OrganizationBoundary(
        reporting_org_id=organization.id,
        period_id=period.id,
        boundary_no="BND-TEST-2026",
        boundary_name="测试组织边界",
        status="published",
    )
    parameter = m.GhgMethodParameterDefinition(
        method_id=method.id,
        parameter_code="ENERGY_FACTOR",
        parameter_name="购入电力排放因子",
        parameter_role="emission_factor",
        allowed_units=["kgCO2e/kWh"],
        required=True,
    )
    session.add_all([boundary, parameter])
    await session.flush()
    session.add(m.BoundaryFacility(boundary_id=boundary.id, area_id=area.id, facility_type="area", included=True))
    await session.commit()

    context = {
        "inventory_code": period.code,
        "reporting_period_id": period.id,
        "organization_code": organization.code,
        "facility_code": area.code,
        "iso_category_code": "2.1",
        "reporting_profile_code": profile.code,
        "method_code": method.code,
    }
    workbook = load_workbook(BytesIO(build_template_bytes(context)))
    _set_row(workbook, "01_组织与边界", {**context, "boundary_method": "operational_control"})
    _set_row(
        workbook,
        "02_排放源",
        {
            "source_code": "SRC-PCC-01",
            "source_name": "测试购入电力",
            "activity_type": "purchased_electricity",
            "facility_code": area.code,
            "iso_category_code": "2.1",
        },
    )
    _set_row(
        workbook,
        "03_活动数据",
        {
            "record_code": "ACT-PCC-01",
            "source_code": "SRC-PCC-01",
            "activity_code": "PURCHASED-ELECTRICITY",
            "activity_name": "测试购入电力",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "activity_amount": 1000,
            "activity_unit": "kWh",
            "data_source_type": "measured",
            "measurement_method": "计量表",
            "parameter_set_code": "FACTOR-TEST",
            "boundary_status": "included",
            "energy_type": "electricity",
            "supplier_name": "测试供电方",
            "meter_point": "PCC-01",
            "scope2_method": "location",
        },
    )
    _set_row(
        workbook,
        "03A_区域设备归集",
        {
            "allocation_code": "ALLOC-PCC-01",
            "record_code": "ACT-PCC-01",
            "source_code": "SRC-PCC-01",
            "area_code": area.code,
            "allocation_role": "energy_consumption",
            "allocation_ratio": 1,
            "source_kind": "manual",
        },
    )
    _set_row(
        workbook,
        "04_参数与因子",
        {
            "parameter_set_code": "FACTOR-TEST",
            "parameter_code": "ENERGY_FACTOR",
            "parameter_name": "测试排放因子",
            "parameter_role": "emission_factor",
            "value": 0.55,
            "unit": "kgCO2e/kWh",
            "source_mode": "authority_published",
            "source_name": "测试来源",
            "evidence_code": "EVID-FACTOR",
        },
    )
    for row, code, name, document_type in (
        (3, "EVID-FACTOR", "测试因子依据", "standard"),
        (4, "EVID-METER", "测试计量记录", "meter_ledger"),
    ):
        _set_row(
            workbook,
            "05_证据索引",
            {
                "evidence_code": code,
                "file_name": name,
                "document_type": document_type,
                "storage_key": f"test/{code}",
                "sha256": ("a" if row == 3 else "b") * 64,
                "confidentiality": "internal",
                "verification_status": "verified",
            },
            row=row,
        )
    _set_row(
        workbook,
        "06_数据证据关联",
        {
            "link_code": "LINK-ACT-PCC",
            "record_type": "activity",
            "record_code": "ACT-PCC-01",
            "evidence_code": "EVID-METER",
            "evidence_role": "activity",
            "coverage_ratio": 1,
        },
    )
    buffer = BytesIO()
    workbook.save(buffer)
    batch = await PreviewCategoryWorkbook(session).execute(
        {
            **context,
            "file_name": "organization-import-test.xlsx",
            "workbook_base64": base64.b64encode(buffer.getvalue()).decode(),
        }
    )
    assert batch.status == "previewed"
    assert (batch.valid_count, batch.error_count) == (1, 0)
    batch = await CommitCategoryWorkbook(session).execute(batch.batch_code, acknowledge_warnings=False)
    assert batch.status == "committed"
    run = await RunInventoryCalculation(session).execute(
        inventory_code=period.code,
        reporting_profile_code=profile.code,
        reporting_period_id=period.id,
        reporting_org_id=organization.id,
        organization_boundary_id=boundary.id,
    )
    assert run.status == "completed"
    assert run.total_co2e_kg == Decimal(550)
    result = await session.scalar(select(GhgCalculationResult).where(GhgCalculationResult.run_id == run.id))
    assert result is not None
    assert result.iso_category_code == "2.1"
    assert result.co2e_kg == Decimal(550)
