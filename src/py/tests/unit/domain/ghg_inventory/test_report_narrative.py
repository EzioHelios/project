"""Report prose, immutable submitted content and activity aggregation contracts."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.ghg_inventory.domain.report_narrative import validate_narrative
from app.domain.ghg_inventory.usecases.reports import ExportInventoryReport, UpdateInventoryReport
from app.domain.master_data.enterprise_profile import EnterpriseProfileUpdate, update_enterprise_profile
from app.domain.organization_boundary.usecases.boundary import PERIOD_FIELDS, _payload
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = pytest.mark.unit


def test_base_year_can_be_cleared_and_rejects_invalid_years():
    assert _payload({"base_year": None}, PERIOD_FIELDS) == {"base_year": None}
    assert _payload({"base_year": "2025"}, PERIOD_FIELDS) == {"base_year": 2025}
    for value in (True, 0, -1, 10000, "2025.5", "abc"):
        with pytest.raises(ValueError, match="整数年份"):
            _payload({"base_year": value}, PERIOD_FIELDS)


def test_narrative_rejects_unknown_keys_and_preserves_empty_removal():
    assert validate_narrative({"purpose": " purpose ", "quality_controls": " "}) == {"purpose": "purpose"}
    with pytest.raises(ValueError):
        validate_narrative({"approved_by": "Someone"})
    with pytest.raises(ValueError):
        validate_narrative({"purpose": "a" * 10001})


@pytest.mark.anyio
async def test_edit_preserves_run_snapshot_and_rejects_noneditable_report():
    report = SimpleNamespace(status="draft", content_snapshot={"inputSnapshot": {"run": 1}, "reportContext": {}})
    session = SimpleNamespace(
        info={TENANT_ID_SESSION_KEY: uuid4()}, scalar=AsyncMock(return_value=report), commit=AsyncMock()
    )
    await UpdateInventoryReport(session).execute(
        report_code="R", version=1, title="Title", change_summary=None, narrative={"purpose": "盘查"}
    )
    assert report.content_snapshot == {"inputSnapshot": {"run": 1}, "narrative": {"purpose": "盘查"}}
    report.status = "published"
    with pytest.raises(ValueError, match="允许编辑"):
        await UpdateInventoryReport(session).execute(
            report_code="R", version=1, title="X", change_summary=None, narrative={"purpose": "覆盖"}
        )
    assert session.commit.await_count == 1


@pytest.mark.anyio
async def test_submitted_export_reads_snapshot_without_live_queries():
    frozen = {"enterprise": {"name": "原名称"}, "inventory_source": {"status": "submitted"}}
    report = SimpleNamespace(status="published", content_snapshot={"reportContext": frozen})
    session = SimpleNamespace(get=AsyncMock())
    context = await ExportInventoryReport(session).report_context(report)
    assert context["enterprise"]["name"] == "原名称"
    assert context["inventory_source"]["status"] == "published"
    assert frozen["inventory_source"]["status"] == "submitted"
    session.get.assert_not_awaited()
    report.content_snapshot = {}
    with pytest.raises(ValueError, match="快照"):
        await ExportInventoryReport(session).report_context(report)


def test_multigas_results_do_not_duplicate_activity_amount():
    activity = SimpleNamespace(
        record_code="A1",
        activity_name="燃料",
        source_code="S1",
        activity_amount=Decimal(10),
        activity_unit="t",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        data_source_type="measured",
        measurement_method="称重",
    )
    results = [
        (SimpleNamespace(ghg_scope="scope1", iso_category_code="1.1", co2e_kg=Decimal(value)), activity, None, None)
        for value in (20, 30)
    ]
    rows = ExportInventoryReport(None)._activity_rows(results, [])
    assert len(rows) == 1
    assert rows[0]["activity_amount"] == "10"
    assert rows[0]["computed_co2e"] == "50"


@pytest.mark.anyio
async def test_enterprise_edit_preserves_unrelated_json_and_requires_tenant_record():
    row = SimpleNamespace(name="原名称", other_info={"scene": "retain"})
    session = SimpleNamespace(
        info={TENANT_ID_SESSION_KEY: uuid4()}, scalar=AsyncMock(return_value=row), commit=AsyncMock()
    )
    await update_enterprise_profile(
        session, 1, EnterpriseProfileUpdate(name="祥泰仓库", organization_description="资料")
    )
    assert row.other_info == {"scene": "retain", "organization_description": "资料"}
    session.scalar.return_value = None
    with pytest.raises(ValueError, match="不存在"):
        await update_enterprise_profile(session, 2, EnterpriseProfileUpdate(name="其他租户"))
    with pytest.raises(ValidationError):
        EnterpriseProfileUpdate(name="主体", team_id=str(uuid4()))
    with pytest.raises(ValidationError):
        EnterpriseProfileUpdate(name="主体", park_area=-1)
