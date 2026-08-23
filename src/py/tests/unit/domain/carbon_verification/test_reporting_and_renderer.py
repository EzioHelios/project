from __future__ import annotations

import zipfile
from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from app.domain.carbon_verification.domain.regulatory_templates import select_descriptor
from app.domain.carbon_verification.domain.reporting import formal_report_readiness
from app.domain.carbon_verification.infrastructure.report_renderer import ReportDocumentRenderer

if TYPE_CHECKING:
    from pathlib import Path


def _report() -> dict[str, object]:
    activity = {
        "record_code": "ACT-001",
        "scope": "scope2",
        "iso_category_code": "2",
        "activity_name": "外购电力",
        "activity_amount": 1000,
        "activity_unit": "kWh",
        "computed_co2e": 570,
        "evidence_status": "ready",
    }
    return {
        "project": {
            "report_code": "RPT-2026-001",
            "report_version": 1,
            "run_code": "RUN-2026-001",
            "verification_basis": "ISO 14064-3:2019",
        },
        "template": {
            "template_code": "organization_ghg_generic",
            "standard_name": "工业企业温室气体排放核算和报告通则",
            "standard_code": "GB/T 32150—2025",
            "version": "v2026.07.01",
            "schema_version": "2026.1",
            "implementation_status": "supported",
            "renderer_kind": "generic_a4",
            "report_purpose": "organization_inventory",
        },
        "standard": {"name": "ISO 14064-1", "code": "ISO 14064-1:2018"},
        "enterprise": {"name": "示例制造企业", "code": "ORG-001", "unify_code": "91320000EXAMPLE"},
        "reporting_period": {
            "year": 2026,
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
            "base_year": 2025,
        },
        "inventory_source": {
            "status": "published",
            "boundary_no": "BOUNDARY-2026-01",
            "boundary_status": "published",
        },
        "inventory": {
            "totals": {"total_kg_co2e": 570, "total_t_co2e": 0.57},
            "scope_summary": [{"scope": "scope2", "kg_co2e": 570, "t_co2e": 0.57}],
            "source_summary": [{"scope": "scope2", "record_label": "外购电力", "record_count": 1, "t_co2e": 0.57}],
            "gas_summary": [{"gas_code": "co2", "kg_co2e": 570, "t_co2e": 0.57}],
            "iso_category_summary": [{"label": "输入能源产生的间接温室气体排放", "kg_co2e": 570, "t_co2e": 0.57}],
            "scope2_method_summary": [{"method": "location_based", "kg_co2e": 570, "t_co2e": 0.57}],
            "scope3_category_summary": [],
            "gwp_versions": ["IPCC AR6"],
            "default_scope2_method": "location_based",
        },
        "activity_data": [activity],
        "factor_parameters": [
            {
                "record_code": "ACT-001",
                "scope": "scope2",
                "factor_source": "全国电网排放因子",
                "factor_version": "2026",
                "factor_unit": "kgCO2e/kWh",
            }
        ],
        "verification_attachments": [
            {
                "evidence_code": "EV-001",
                "record_code": "ACT-001",
                "file_name": "电费账单.pdf",
                "attachment_type": "invoice",
                "material_status": "ready",
                "sha256": "a" * 64,
            }
        ],
        "quality_issues": [],
        "verification_findings": [],
        "exclusions": [],
        "formal_readiness": {"status": "ready", "blocking_count": 0, "warning_count": 0, "checks": []},
    }


@pytest.mark.unit
def test_formal_report_readiness_requires_a_complete_frozen_chain() -> None:
    report = _report()
    readiness = formal_report_readiness(report)
    assert readiness.status == "ready"
    report["verification_attachments"] = []
    blocked = formal_report_readiness(report)
    assert blocked.status == "blocked"
    assert any(check.code == "evidence" and check.status == "blocked" for check in blocked.checks)


@pytest.mark.unit
def test_report_renderer_creates_a4_docx_with_dynamic_rows(tmp_path: Path) -> None:
    report = _report()
    report["formal_readiness"] = {
        "status": "ready",
        "blocking_count": 0,
        "warning_count": 0,
        "checks": [],
    }
    files = ReportDocumentRenderer(template_path=None, output_dir=tmp_path).render(report)
    docx = next(item for item in files if item.path.endswith(".docx"))
    with zipfile.ZipFile(BytesIO(docx.content)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
        section_xml = document_xml[document_xml.rfind("<w:sectPr") :]
    assert "示例制造企业" in document_xml
    assert "ACT-001" in document_xml
    assert "电费账单.pdf" in document_xml
    assert 'w:w="11906"' in section_xml
    assert 'w:h="16838"' in section_xml


@pytest.mark.unit
def test_report_renderer_rejects_unimplemented_regulatory_adapter(tmp_path: Path) -> None:
    report = _report()
    template = report["template"]
    assert isinstance(template, dict)
    template["implementation_status"] = "registered"
    template["renderer_kind"] = "ets_power_2026"
    with pytest.raises(ValueError, match="尚未实现"):
        ReportDocumentRenderer(template_path=None, output_dir=tmp_path).render(report)


@pytest.mark.unit
def test_national_ets_routing_never_silently_falls_back_to_generic() -> None:
    descriptor = select_descriptor(purpose="national_ets", industry="钢铁制造", year=2026)
    assert descriptor.standard_code == "CETS-AG-03.01-V01-2024"
    with pytest.raises(ValueError, match="未找到"):
        select_descriptor(purpose="national_ets", industry="未知行业", year=2026)
