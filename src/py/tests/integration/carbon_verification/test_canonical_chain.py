"""Integration coverage for the canonical organization-GHG verification chain."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_verification.queries.canonical import (
    CanonicalVerificationQueryService,
    VerificationQuery,
)
from app.domain.carbon_verification.queries.findings import CarbonVerificationFindingQueryService, FindingQuery
from app.domain.carbon_verification.queries.projects import CarbonVerificationProjectQueryService, ProjectQuery
from app.domain.carbon_verification.usecases.evidence import CanonicalEvidenceUseCase
from app.domain.carbon_verification.usecases.findings import CarbonVerificationFindingUseCase
from app.domain.carbon_verification.usecases.projects import CarbonVerificationProjectUseCase
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def test_report_bound_verification_requires_reviewed_evidence_and_closed_findings(  # noqa: PLR0915
    session, tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    team = m.Team(name="Verification Tenant", slug="verification-tenant")
    profile = m.GhgReportingProfile(
        code="VERIFY-PROFILE",
        name="组织温室气体盘查",
        version="1",
        standard_code="ISO 14064-1",
        standard_version="2018",
        effective_from=date(2026, 1, 1),
    )
    method = m.GhgCalculationMethodDefinition(
        code="VERIFY-F08",
        version="1",
        name="购入电力核算",
        formula_family="F08",
        formula_expression={"expression": "activity * factor"},
        human_formula="活动数据乘以排放因子",
        standard_code="ISO 14064-1",
        applicable_categories=["2.1"],
        effective_from=date(2026, 1, 1),
    )
    session.add_all([team, profile, method])
    await session.flush()
    session.info[TENANT_BYPASS_SESSION_KEY] = True
    organization = m.ReportingOrganization(team_id=team.id, code="VERIFY-ORG", name="核查测试组织")
    session.add(organization)
    await session.flush()
    period = m.ReportingPeriod(
        team_id=team.id,
        reporting_org_id=organization.id,
        code="2026",
        name="2026年度",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
    )
    session.add(period)
    await session.flush()
    boundary = m.OrganizationBoundary(
        team_id=team.id,
        reporting_org_id=organization.id,
        period_id=period.id,
        boundary_no="VERIFY-BOUNDARY",
        boundary_name="组织核算边界",
        operational_boundary={"scopes": ["scope2"], "scope2Methods": ["location"]},
        status="published",
    )
    session.add(boundary)
    await session.flush()
    source = m.GhgEmissionSource(
        team_id=team.id,
        inventory_code="VERIFY-INV",
        organization_boundary_id=boundary.id,
        reporting_period_id=period.id,
        organization_code=organization.code,
        facility_code="FACILITY-1",
        source_code="GRID-POWER",
        source_name="购入电力",
        iso_category_code="2.1",
        source_mechanism="energy",
    )
    session.add(source)
    await session.flush()
    activity = m.GhgActivityRecord(
        team_id=team.id,
        record_code="VERIFY-ACTIVITY",
        inventory_code="VERIFY-INV",
        reporting_period_id=period.id,
        organization_boundary_id=boundary.id,
        emission_source_id=source.id,
        organization_code=organization.code,
        facility_code="FACILITY-1",
        source_code=source.source_code,
        activity_code="PURCHASED-ELECTRICITY",
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
        measurement_method="关口电表",
        status="approved",
        quality_status="pass",
        boundary_status="included",
    )
    session.add(activity)
    await session.flush()
    run = m.GhgCalculationRun(
        team_id=team.id,
        run_code="VERIFY-RUN",
        inventory_code="VERIFY-INV",
        reporting_profile_id=profile.id,
        reporting_org_id=organization.id,
        reporting_period_id=period.id,
        organization_boundary_id=boundary.id,
        default_scope2_method="location",
        status="completed",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    session.add_all(
        [
            m.GhgCalculationResult(
                team_id=team.id,
                run_id=run.id,
                activity_id=activity.id,
                method_id=method.id,
                iso_category_code="2.1",
                ghg_scope="scope2",
                gas_code="CO2",
                gas_mass_kg=Decimal(100),
                gwp_value=Decimal(1),
                gwp_version="AR6",
                co2e_kg=Decimal(100),
                scope2_method="location",
                formula_snapshot={},
            ),
            m.GhgParameterAssignment(
                team_id=team.id,
                run_id=run.id,
                activity_id=activity.id,
                method_id=method.id,
                parameter_code="ef_co2",
                parameter_role="emission_factor",
                value=Decimal("0.1"),
                unit="kgCO2e/kWh",
                source_mode="factor_library",
                source_name="国家电网排放因子",
                selection_rule="按地区和年份匹配",
                snapshot={},
            ),
        ]
    )
    await session.flush()
    report = m.GhgInventoryReport(
        team_id=team.id,
        report_code="VERIFY-REPORT",
        version=1,
        title="2026年度组织温室气体盘查报告",
        inventory_code=run.inventory_code,
        run_id=run.id,
        reporting_org_id=organization.id,
        reporting_period_id=period.id,
        organization_boundary_id=boundary.id,
        reporting_profile_id=profile.id,
        status="published",
        published_at=datetime.now(UTC),
    )
    session.add(report)
    await session.commit()
    session.info.clear()
    session.info[TENANT_ID_SESSION_KEY] = team.id

    project_use_case = CarbonVerificationProjectUseCase(session)
    project = await project_use_case.create_project(
        {"project_name": "年度组织碳核查", "inventory_report_id": report.id}
    )
    assert project.inventory_report_id == report.id
    assert project.calculation_run_id == run.id
    assert project.readiness_status == "attention"
    session.add(
        m.CarbonVerificationProject(
            team_id=team.id,
            project_no="VERIFY-ARCHIVED",
            project_name="历史核查项目",
            status="archived",
            readiness_status="blocked",
        )
    )
    await session.commit()
    project_list = await CarbonVerificationProjectQueryService(session).list_projects(ProjectQuery())
    assert project_list["summary"]["total"] == 1
    assert [item["project_no"] for item in project_list["items"]] == [project.project_no]

    query = VerificationQuery(project_id=project.id)
    summary = await CanonicalVerificationQueryService(session).summary(query)
    assert summary["totals"]["total_kg_co2e"] == 100
    assert summary["inventory_source"]["mode"] == "published_inventory_report"

    evidence_use_case = CanonicalEvidenceUseCase(session)
    evidence = await evidence_use_case.upload(
        project_id=project.id,
        record_type="activity",
        record_code=activity.record_code,
        evidence_role="activity_evidence",
        document_type="application/pdf",
        file_name="electricity-invoice.pdf",
        content_type="application/pdf",
        content=b"test-evidence",
        uploaded_by="reviewer@example.com",
        evidence_code="EVD-VERIFY-001",
        link_code="EL-VERIFY-001",
    )
    repeated_evidence = await evidence_use_case.upload(
        project_id=project.id,
        record_type="activity",
        record_code=activity.record_code,
        evidence_role="activity_evidence",
        document_type="application/pdf",
        file_name="electricity-invoice.pdf",
        content_type="application/pdf",
        content=b"test-evidence",
        uploaded_by="reviewer@example.com",
        evidence_code="EVD-VERIFY-001",
        link_code="EL-VERIFY-001",
    )
    assert repeated_evidence.id == evidence.id
    assert (
        await session.scalar(
            select(func.count(m.GhgEvidenceLink.id)).where(m.GhgEvidenceLink.evidence_id == evidence.id)
        )
        == 1
    )
    await session.refresh(project)
    assert project.readiness_status == "attention"
    assert (await evidence_use_case.file_path(evidence.evidence_code)).read_bytes() == b"test-evidence"

    await evidence_use_case.review(
        project_id=project.id,
        evidence_code=evidence.evidence_code,
        decision="approved",
        reviewer="reviewer@example.com",
    )
    await session.refresh(project)
    assert project.readiness_status == "ready"

    finding = await CarbonVerificationFindingUseCase(session).create_finding(
        {
            "project_id": project.id,
            "issue_type": "sampling",
            "title": "补充抽样说明",
            "record_type": "activity",
            "record_code": activity.record_code,
        }
    )
    finding_list = await CarbonVerificationFindingQueryService(session).list_findings(
        FindingQuery(project_id=project.id)
    )
    assert finding_list["total"] == 1
    assert finding_list["summary"]["total"] == 1
    assert finding_list["summary"]["open_count"] == 1
    await session.refresh(project)
    assert project.readiness_status == "attention"
    await CarbonVerificationFindingUseCase(session).update_finding(finding.id, {"status": "closed"})
    await session.refresh(project)
    assert project.readiness_status == "ready"

    await project_use_case.update_project(project.id, {"status": "in_progress"})
    completed = await project_use_case.update_project(
        project.id,
        {
            "status": "completed",
            "conclusion_status": "approved",
            "conclusion": "核算结果在既定边界和重要性水平下不存在重大错报。",
        },
    )
    assert completed.status == "completed"
    assert completed.conclusion_status == "approved"
    report_context = await CanonicalVerificationQueryService(session).report_context(query)
    assert report_context["formal_readiness"]["status"] == "ready"
    assert report_context["inventory"]["iso_category_summary"] == [
        {
            "iso_category_code": "2",
            "label": "输入能源产生的间接温室气体排放",
            "kg_co2e": 100.0,
            "t_co2e": 0.1,
        }
    ]
