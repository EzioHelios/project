"""Report exports distinguish reporting organizations from linked enterprise names."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.db import models as m
from app.domain.ghg_inventory.usecases.reports import ExportInventoryReport


@pytest.mark.unit
@pytest.mark.anyio
async def test_export_uses_selected_organization_and_actual_activity_coverage(monkeypatch):
    objects = {
        m.GhgCalculationRun: SimpleNamespace(id=1, default_scope2_method="location", input_snapshot={}),
        m.GhgReportingProfile: SimpleNamespace(standard_code="ISO 14064-1", name="ISO 14064-1"),
        m.ReportingOrganization: SimpleNamespace(
            enterprise_id=9, name="报告设施", code="FAC-01", legal_entity_code=None, organization_type="facility"
        ),
        m.ReportingPeriod: SimpleNamespace(
            period_start=date(2026, 1, 1), period_end=date(2026, 12, 31), base_year=None
        ),
        m.OrganizationBoundary: SimpleNamespace(
            id=3,
            standard_code=None,
            status="published",
            boundary_no="B-1",
            boundary_name="计量范围",
            boundary_method="operational_control",
            remark=None,
            operational_boundary={},
        ),
        m.EnterpriseInfo: SimpleNamespace(
            name="关联企业",
            unify_code="91320000TESTCODE123",
            industry=None,
            location="运营地址",
            other_info={},
            belong_unit="所属单位",
        ),
    }
    session = SimpleNamespace(
        get=AsyncMock(side_effect=lambda model, _id: objects[model]),
        scalars=AsyncMock(return_value=SimpleNamespace(all=list)),
    )
    usecase = ExportInventoryReport(session)
    rows = [
        (
            SimpleNamespace(ghg_scope="scope2", scope2_method="location", method_id=1, formula_snapshot={}),
            SimpleNamespace(id=1, record_code="A1", period_start=date(2026, 3, 1), period_end=date(2026, 8, 31)),
            None,
            None,
        )
    ]
    monkeypatch.setattr(usecase, "_result_rows", AsyncMock(return_value=rows))
    for name in ("_evidence_rows", "_factor_rows", "_exclusion_rows"):
        monkeypatch.setattr(usecase, name, AsyncMock(return_value=[]))
    monkeypatch.setattr(usecase, "_organization_template", AsyncMock(return_value={}))
    for name in ("_activity_rows", "_quality_rows"):
        monkeypatch.setattr(usecase, name, Mock(return_value=[]))
    monkeypatch.setattr(usecase, "_inventory_summary", Mock(return_value={}))
    report = SimpleNamespace(
        run_id=1,
        reporting_profile_id=2,
        reporting_org_id=3,
        reporting_period_id=4,
        organization_boundary_id=5,
        metrics_snapshot={},
        report_code="RPT-1",
        version=1,
        inventory_code="INV-1",
        status="draft",
        title="盘查报告",
        content_snapshot={},
    )
    objects[m.GhgCalculationRun].run_code = "RUN-1"
    context = await usecase.report_context(report)
    assert context["enterprise"]["name"] == "报告设施"
    assert context["enterprise"]["unify_code"] is None
    assert context["enterprise"]["linked_enterprise_unify_code"] == "91320000TESTCODE123"
    assert "compiled_at" not in context["project"]
    assert context["enterprise"]["registered_address"] is None
    assert context["enterprise"]["operation_address"] == "运营地址"
    assert context["reporting_period"]["period_end"] == "2026-12-31"
    assert context["reporting_period"]["data_period_start"] == "2026-03-01"
    assert context["reporting_period"]["data_period_end"] == "2026-08-31"
    assert context["inventory_source"]["status"] == "draft"
    objects[m.EnterpriseInfo].unify_code = None
    assert (await usecase.report_context(report))["enterprise"]["unify_code"] is None


@pytest.mark.unit
@pytest.mark.anyio
async def test_report_device_membership_uses_calculation_snapshot(monkeypatch):
    session = SimpleNamespace(
        scalars=AsyncMock(
            return_value=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(id=1, name="行吊计量表"),
                    SimpleNamespace(id=2, name="堆垛机计量表"),
                ]
            )
        )
    )
    usecase = ExportInventoryReport(session)
    monkeypatch.setattr(usecase, "_activity_rows", Mock(return_value=[{"record_code": "A1"}]))
    run = SimpleNamespace(
        input_snapshot={
            "allocations": [
                {
                    "recordCode": "A1",
                    "items": [
                        {"equipmentId": 1, "ratio": "0.4", "areaPath": "/A"},
                        {"equipmentId": 2, "ratio": "0.6", "areaPath": "/B"},
                    ],
                }
            ]
        }
    )
    rows = await usecase._allocated_activity_rows(run, [], [])
    assert rows[0]["device_allocations"] == [
        {"device_id": 1, "device_name": "行吊计量表", "ratio": "0.4", "area_path": "/A"},
        {"device_id": 2, "device_name": "堆垛机计量表", "ratio": "0.6", "area_path": "/B"},
    ]
