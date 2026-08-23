"""Canonical organization-carbon verification adapter for the Xiangtai demo package."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_verification.usecases.evidence import CanonicalEvidenceUseCase
from app.domain.carbon_verification.usecases.findings import CarbonVerificationFindingUseCase
from app.domain.carbon_verification.usecases.projects import CarbonVerificationProjectUseCase
from app.domain.ghg_inventory.usecases.reports import CreateInventoryReport, TransitionInventoryReport

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.demo.catalog import DemoPackageManifest, DemoVerificationEvidenceSpec, DemoVerificationSpec


@dataclass(frozen=True, slots=True)
class DemoVerificationResult:
    """Canonical verification records created or reused by the adapter."""

    report_id: int
    project_id: int
    evidence_files: int
    evidence_links: int
    findings: int


class XiangtaiVerificationDemoAdapter:
    """Build a report-bound project with auditable evidence and findings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self,
        *,
        manifest: DemoPackageManifest,
        spec: DemoVerificationSpec,
    ) -> DemoVerificationResult:
        report = await self._published_report(manifest.reporting_year)
        project = await self._project(report=report, manifest=manifest, spec=spec)
        activities = list(
            (
                await self.session.scalars(
                    select(m.GhgActivityRecord)
                    .where(m.GhgActivityRecord.inventory_code == report.inventory_code)
                    .order_by(m.GhgActivityRecord.iso_category_code, m.GhgActivityRecord.period_start)
                )
            ).all()
        )
        if not activities:
            msg = "The published inventory report has no activity records for verification evidence."
            raise ValueError(msg)

        evidence_ids: set[int] = set()
        for evidence_spec in spec.evidence:
            targets = self._targets(project=project, activities=activities, evidence_spec=evidence_spec)
            content = self._evidence_content(
                report=report,
                project=project,
                activities=activities,
                evidence_spec=evidence_spec,
            )
            evidence = None
            for record_type, record_code in targets:
                evidence = await CanonicalEvidenceUseCase(self.session).upload(
                    project_id=project.id,
                    record_type=record_type,
                    record_code=record_code,
                    evidence_role=evidence_spec.evidence_role,
                    document_type=evidence_spec.document_type,
                    file_name=evidence_spec.file_name,
                    content_type=evidence_spec.content_type,
                    content=content,
                    uploaded_by="组织碳核查工作组",
                    evidence_code=evidence_spec.code,
                    link_code=self._link_code(evidence_spec.code, record_type, record_code),
                )
            if evidence is None:
                msg = f"Evidence specification {evidence_spec.code!r} has no valid target."
                raise ValueError(msg)
            evidence.document_no = evidence_spec.code
            evidence.issuer = "组织碳核查工作组"
            evidence.period_start = date(manifest.reporting_year, 1, 1)
            evidence.period_end = date(manifest.reporting_year, 12, 31)
            evidence.valid_from = date(manifest.reporting_year, 1, 1)
            evidence.valid_to = date(manifest.reporting_year + 1, 12, 31)
            await self.session.commit()
            if evidence_spec.review_status == "approved":
                await CanonicalEvidenceUseCase(self.session).review(
                    project_id=project.id,
                    evidence_code=evidence.evidence_code,
                    decision="approved",
                    reviewer="核查组长",
                )
            evidence_ids.add(evidence.id)

        finding_count = await self._findings(
            project=project,
            activities=activities,
            manifest=manifest,
            spec=spec,
        )
        link_count = int(
            await self.session.scalar(
                select(func.count(m.GhgEvidenceLink.id)).where(m.GhgEvidenceLink.evidence_id.in_(evidence_ids))
            )
            or 0
        )
        await CarbonVerificationProjectUseCase(self.session).refresh_project_status(project.id)
        await self.session.refresh(project)
        return DemoVerificationResult(
            report_id=report.id,
            project_id=project.id,
            evidence_files=len(evidence_ids),
            evidence_links=link_count,
            findings=finding_count,
        )

    async def _published_report(self, reporting_year: int) -> m.GhgInventoryReport:
        report = await self.session.scalar(
            select(m.GhgInventoryReport)
            .join(m.ReportingPeriod, m.ReportingPeriod.id == m.GhgInventoryReport.reporting_period_id)
            .where(
                m.ReportingPeriod.period_end == date(reporting_year, 12, 31),
                m.GhgInventoryReport.status == "published",
            )
            .order_by(m.GhgInventoryReport.version.desc(), m.GhgInventoryReport.id.desc())
        )
        if report is not None:
            return report
        run = await self.session.scalar(
            select(m.GhgCalculationRun)
            .join(m.ReportingPeriod, m.ReportingPeriod.id == m.GhgCalculationRun.reporting_period_id)
            .where(
                m.ReportingPeriod.period_end == date(reporting_year, 12, 31),
                m.GhgCalculationRun.status == "completed",
            )
            .order_by(m.GhgCalculationRun.completed_at.desc(), m.GhgCalculationRun.id.desc())
        )
        if run is None:
            msg = f"No completed organization-inventory run exists for {reporting_year}."
            raise ValueError(msg)
        report = await CreateInventoryReport(self.session).execute(
            run_code=run.run_code,
            title=f"{reporting_year}年度组织温室气体盘查报告",
            change_summary="形成组织碳核查基准版本",
        )
        transitions = TransitionInventoryReport(self.session)
        for action, actor, comment in (
            ("submit", "盘查编制负责人", "提交内部审核"),
            ("approve", "可持续发展负责人", "审核通过"),
            ("publish", "组织碳平台主管", "批准发布"),
        ):
            report = await transitions.execute(
                report_code=report.report_code,
                version=report.version,
                action=action,
                actor=actor,
                comment=comment,
            )
        return report

    async def _project(
        self,
        *,
        report: m.GhgInventoryReport,
        manifest: DemoPackageManifest,
        spec: DemoVerificationSpec,
    ) -> m.CarbonVerificationProject:
        use_case = CarbonVerificationProjectUseCase(self.session)
        project = await self.session.scalar(
            select(m.CarbonVerificationProject).where(m.CarbonVerificationProject.project_no == spec.project_no)
        )
        payload = {
            "project_no": spec.project_no,
            "project_name": spec.project_name,
            "project_type": spec.project_type,
            "inventory_report_id": report.id,
            "verification_year": manifest.reporting_year,
            "planned_start": date(manifest.reporting_year, 3, 1),
            "planned_end": date(manifest.reporting_year, 9, 30),
            "lead_reviewer": "核查组长",
            "responsible_person": "可持续发展负责人",
            "verifier_org": "企业内部核查工作组",
            "assurance_level": spec.assurance_level,
            "materiality_threshold_pct": spec.materiality_threshold_pct,
            "verification_basis": spec.verification_basis,
            "sampling_strategy": spec.sampling_strategy,
            "site_visit_required": spec.site_visit_required,
            "site_visit_status": spec.site_visit_status,
            "conclusion_status": spec.conclusion_status,
            "scope_description": spec.scope_description,
            "source_name": manifest.source_name,
            "standard_code": "ISO 14064-3:2019",
            "confidence_level": "high",
            "remark": "组织碳盘查与核查证据链",
        }
        if project is None:
            project = await use_case.create_project(payload)
        elif project.source_name != manifest.source_name:
            msg = f"Verification project number {spec.project_no!r} is already owned by non-demo data."
            raise ValueError(msg)
        elif project.status in {"draft", "in_progress"}:
            project = await use_case.update_project(project.id, payload)
        if project.status == "draft":
            project = await use_case.update_project(project.id, {"status": "in_progress"})
        return project

    async def _findings(
        self,
        *,
        project: m.CarbonVerificationProject,
        activities: list[m.GhgActivityRecord],
        manifest: DemoPackageManifest,
        spec: DemoVerificationSpec,
    ) -> int:
        use_case = CarbonVerificationFindingUseCase(self.session)
        for finding_spec in spec.findings:
            activity = next(
                (item for item in activities if item.iso_category_code == finding_spec.iso_category_code),
                None,
            )
            if activity is None:
                msg = f"Verification finding {finding_spec.finding_no!r} has no matching activity."
                raise ValueError(msg)
            finding = await self.session.scalar(
                select(m.CarbonVerificationFinding).where(
                    m.CarbonVerificationFinding.finding_no == finding_spec.finding_no
                )
            )
            if finding is None:
                finding = await use_case.create_finding(
                    {
                        "finding_no": finding_spec.finding_no,
                        "project_id": project.id,
                        "issue_type": finding_spec.issue_type,
                        "finding_type": finding_spec.finding_type,
                        "severity": finding_spec.severity,
                        "title": finding_spec.title,
                        "description": finding_spec.description,
                        "action_required": finding_spec.action_required,
                        "record_type": "activity",
                        "record_id": activity.id,
                        "record_code": activity.record_code,
                        "scope": activity.ghg_scope,
                        "display_name": activity.activity_name,
                        "period": activity.period_start.strftime("%Y-%m"),
                        "owner": "数据平台主管",
                        "due_date": date(manifest.reporting_year, 9, 15),
                        "source_name": manifest.source_name,
                        "standard_code": "ISO 14064-3:2019",
                    }
                )
            elif finding.source_name != manifest.source_name:
                msg = f"Verification finding number {finding_spec.finding_no!r} is already owned by non-demo data."
                raise ValueError(msg)
            if finding_spec.status == "closed" and finding.status != "closed":
                finding = await use_case.update_finding(
                    finding.id,
                    {
                        "status": "closed",
                        "correction_comment": "已完成抽样复核并归档工作底稿。",
                        "reviewer": "核查组长",
                    },
                )
        return len(spec.findings)

    @staticmethod
    def _targets(
        *,
        project: m.CarbonVerificationProject,
        activities: list[m.GhgActivityRecord],
        evidence_spec: DemoVerificationEvidenceSpec,
    ) -> list[tuple[str, str]]:
        if evidence_spec.target_kind == "verification_project":
            return [("verification_project", project.project_no)]
        category_codes = set(evidence_spec.iso_category_codes)
        return [
            ("activity", item.record_code) for item in activities if item.iso_category_code in category_codes
        ]

    @staticmethod
    def _evidence_content(
        *,
        report: m.GhgInventoryReport,
        project: m.CarbonVerificationProject,
        activities: list[m.GhgActivityRecord],
        evidence_spec: DemoVerificationEvidenceSpec,
    ) -> bytes:
        if evidence_spec.target_kind == "verification_project":
            text = (
                f"核查项目: {project.project_name}\n"
                f"项目编号: {project.project_no}\n"
                f"盘查报告: {report.report_code} V{report.version}\n"
                f"核查依据: {project.verification_basis}\n"
                f"核查范围: {project.scope_description}\n"
            )
            return text.encode("utf-8")
        selected = [
            item for item in activities if item.iso_category_code in set(evidence_spec.iso_category_codes)
        ]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "记录编号",
                "ISO类别",
                "活动名称",
                "开始日期",
                "结束日期",
                "活动数据",
                "单位",
                "数据来源",
                "质量状态",
            ]
        )
        for activity in selected:
            writer.writerow(
                [
                    activity.record_code,
                    activity.iso_category_code,
                    activity.activity_name,
                    activity.period_start.isoformat(),
                    activity.period_end.isoformat(),
                    str(activity.activity_amount),
                    activity.activity_unit,
                    activity.data_source_type,
                    activity.quality_status,
                ]
            )
        return ("\ufeff" + output.getvalue()).encode("utf-8")

    @staticmethod
    def _link_code(evidence_code: str, record_type: str, record_code: str) -> str:
        compact = f"{evidence_code}-{record_type[:3]}-{record_code}".replace("_", "-")
        return compact[:96]
