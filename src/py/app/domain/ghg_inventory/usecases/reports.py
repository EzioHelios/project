"""Internal organization-inventory report lifecycle."""

from __future__ import annotations

import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_verification.domain.reporting import (
    SCOPE3_CATEGORY_LABELS,
    formal_report_readiness,
    readiness_dict,
)
from app.domain.carbon_verification.infrastructure.report_renderer import ReportDocumentRenderer
from app.domain.carbon_verification.queries.templates import (
    CarbonVerificationTemplateQueryService,
    default_template_payload,
)
from app.domain.ghg_inventory.domain.catalog import CATEGORY_BY_CODE
from app.domain.ghg_inventory.models import (
    GhgActivityRecord,
    GhgCalculationMethodDefinition,
    GhgCalculationResult,
    GhgCalculationRun,
    GhgEmissionSource,
    GhgEvidenceLink,
    GhgInventoryReport,
    GhgInventoryReportReview,
    GhgParameterAssignment,
)
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

ResultRow = tuple[GhgCalculationResult, GhgActivityRecord, GhgCalculationMethodDefinition, GhgEmissionSource | None]


@dataclass(frozen=True, slots=True)
class InventoryReportExportFile:
    """One downloadable artifact rendered from an inventory report version."""

    filename: str
    content: bytes
    content_type: str


async def build_inventory_evidence_snapshot(session: AsyncSession, inventory_code: str) -> dict[str, int | str]:
    """Build the report evidence snapshot from the current inventory evidence links."""
    activity_codes = set(
        (
            await session.scalars(
                select(GhgActivityRecord.record_code).where(GhgActivityRecord.inventory_code == inventory_code)
            )
        ).all()
    )
    evidence_count = int(
        await session.scalar(
            select(func.count())
            .select_from(GhgEvidenceLink)
            .where(
                GhgEvidenceLink.record_type == "activity",
                GhgEvidenceLink.record_code.in_(activity_codes),
            )
        )
        or 0
    )
    linked_record_count = int(
        await session.scalar(
            select(func.count(func.distinct(GhgEvidenceLink.record_code))).where(
                GhgEvidenceLink.record_type == "activity",
                GhgEvidenceLink.record_code.in_(activity_codes),
            )
        )
        or 0
    )
    coverage_pct = (
        (Decimal(linked_record_count) * Decimal(100) / Decimal(len(activity_codes))).quantize(Decimal("0.01"))
        if activity_codes
        else Decimal(0)
    )
    return {
        "activityCount": len(activity_codes),
        "linkedActivityCount": linked_record_count,
        "evidenceLinkCount": evidence_count,
        "coveragePct": str(coverage_pct),
    }


class CreateInventoryReport:
    """Freeze a completed calculation run into a new internal report version."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, *, run_code: str, title: str, change_summary: str | None) -> GhgInventoryReport:
        require_session_tenant_id(self.session)
        run = await self.session.scalar(select(GhgCalculationRun).where(GhgCalculationRun.run_code == run_code))
        if run is None:
            msg = "核算运行不存在"
            raise ValueError(msg)
        if run.status != "completed":
            msg = "只有已完成的核算运行才能生成盘查报告"
            raise ValueError(msg)
        if not all((run.reporting_org_id, run.reporting_period_id, run.organization_boundary_id)):
            msg = "核算运行缺少报告组织、报告期间或组织边界"
            raise ValueError(msg)
        report_code = f"RPT-{run.reporting_org_id}-{run.reporting_period_id}"
        latest_version = int(
            await self.session.scalar(
                select(func.max(GhgInventoryReport.version)).where(GhgInventoryReport.report_code == report_code)
            )
            or 0
        )
        evidence_snapshot = await build_inventory_evidence_snapshot(self.session, run.inventory_code)
        report = GhgInventoryReport(
            report_code=report_code,
            version=latest_version + 1,
            title=title,
            inventory_code=run.inventory_code,
            run_id=run.id,
            reporting_org_id=run.reporting_org_id,
            reporting_period_id=run.reporting_period_id,
            organization_boundary_id=run.organization_boundary_id,
            reporting_profile_id=run.reporting_profile_id,
            status="draft",
            content_snapshot={
                "runCode": run.run_code,
                "inputSnapshot": run.input_snapshot,
                "qualitySnapshot": run.quality_snapshot,
            },
            metrics_snapshot=run.summary_snapshot,
            evidence_snapshot=evidence_snapshot,
            change_summary=change_summary,
        )
        self.session.add(report)
        await self.session.commit()
        return report


class TransitionInventoryReport:
    """Apply one auditable internal report status transition."""

    TRANSITIONS = {
        "submit": ("draft", "submitted"),
        "resubmit": ("rejected", "submitted"),
        "approve": ("submitted", "approved"),
        "reject": ("submitted", "rejected"),
        "publish": ("approved", "published"),
        "archive": ("published", "archived"),
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self,
        *,
        report_code: str,
        version: int,
        action: str,
        actor: str,
        comment: str | None,
    ) -> GhgInventoryReport:
        require_session_tenant_id(self.session)
        transition = self.TRANSITIONS.get(action)
        if transition is None:
            msg = "不支持的报告操作"
            raise ValueError(msg)
        report = await self.session.scalar(
            select(GhgInventoryReport).where(
                GhgInventoryReport.report_code == report_code,
                GhgInventoryReport.version == version,
            )
        )
        if report is None:
            msg = "盘查报告不存在"
            raise ValueError(msg)
        expected_status, target_status = transition
        if report.status != expected_status:
            msg = f"报告当前状态为{report.status}; 不能执行{action}"
            raise ValueError(msg)
        if action == "reject" and not (comment or "").strip():
            msg = "退回报告时必须填写审核意见"
            raise ValueError(msg)
        now = datetime.now().astimezone()
        original_status = report.status
        report.status = target_status
        if action in {"submit", "resubmit"}:
            report.submitted_by = actor
            report.submitted_at = now
        elif action == "approve":
            report.approved_by = actor
            report.approved_at = now
        elif action == "publish":
            report.published_at = now
        self.session.add(
            GhgInventoryReportReview(
                report_id=report.id,
                action=action,
                from_status=original_status,
                to_status=target_status,
                actor=actor,
                comment=comment,
                acted_at=now,
            )
        )
        await self.session.commit()
        return report


class UpdateInventoryReport:
    """Edit mutable report metadata before formal publication."""

    EDITABLE_STATUSES = {"draft", "rejected"}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self,
        *,
        report_code: str,
        version: int,
        title: str,
        change_summary: str | None,
    ) -> GhgInventoryReport:
        require_session_tenant_id(self.session)
        report = await self.session.scalar(
            select(GhgInventoryReport).where(
                GhgInventoryReport.report_code == report_code,
                GhgInventoryReport.version == version,
            )
        )
        if report is None:
            msg = "盘查报告不存在"
            raise ValueError(msg)
        if report.status not in self.EDITABLE_STATUSES:
            msg = "只有草稿或退回状态的盘查报告允许编辑"
            raise ValueError(msg)
        report.title = title
        report.change_summary = change_summary
        await self.session.commit()
        return report


class DeleteInventoryReport:
    """Delete draft reports and archive reports that have entered the formal lifecycle."""

    DELETABLE_STATUSES = {"draft", "rejected"}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, *, report_code: str, version: int, actor: str) -> dict[str, str | int | bool | None]:
        require_session_tenant_id(self.session)
        report = await self.session.scalar(
            select(GhgInventoryReport).where(
                GhgInventoryReport.report_code == report_code,
                GhgInventoryReport.version == version,
            )
        )
        if report is None:
            msg = "盘查报告不存在"
            raise ValueError(msg)
        if report.status in self.DELETABLE_STATUSES:
            await self.session.delete(report)
            await self.session.commit()
            return {"report_code": report_code, "version": version, "deleted": True, "status": None}
        if report.status == "archived":
            return {"report_code": report_code, "version": version, "deleted": False, "status": report.status}
        now = datetime.now().astimezone()
        original_status = report.status
        report.status = "archived"
        self.session.add(
            GhgInventoryReportReview(
                report_id=report.id,
                action="archive",
                from_status=original_status,
                to_status="archived",
                actor=actor,
                comment="报告台账归档",
                acted_at=now,
            )
        )
        await self.session.commit()
        return {"report_code": report_code, "version": version, "deleted": False, "status": "archived"}


class ExportInventoryReport:
    """Render a versioned organization-inventory report from the report ledger."""

    SUPPORTED_FORMATS = {"docx", "pdf"}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self,
        *,
        report_code: str,
        version: int,
        file_format: str,
    ) -> InventoryReportExportFile:
        require_session_tenant_id(self.session)
        normalized_format = file_format.strip().lower()
        if normalized_format not in self.SUPPORTED_FORMATS:
            msg = "报告导出格式仅支持docx或pdf"
            raise ValueError(msg)
        report = await self.session.scalar(
            select(GhgInventoryReport).where(
                GhgInventoryReport.report_code == report_code,
                GhgInventoryReport.version == version,
            )
        )
        if report is None:
            msg = "盘查报告不存在"
            raise ValueError(msg)
        context = await self._report_context(report)
        with tempfile.TemporaryDirectory(prefix="ghg-report-") as temp_dir:
            rendered_files = ReportDocumentRenderer(
                template_path=Path(str(context["template"].get("path") or "")),
                output_dir=Path(temp_dir),
            ).render(context)
            selected = next(
                (item for item in rendered_files if item.path.lower().endswith(f".{normalized_format}")),
                None,
            )
            if selected is None:
                msg = "当前运行环境未生成所选格式文件"
                raise ValueError(msg)
            return InventoryReportExportFile(
                filename=f"organization-ghg-report-{report.report_code}-v{report.version}.{normalized_format}",
                content=selected.content,
                content_type=selected.content_type,
            )

    async def _report_context(self, report: GhgInventoryReport) -> dict[str, Any]:
        run = await self.session.get(GhgCalculationRun, report.run_id)
        if run is None:
            msg = "盘查报告引用的核算运行不存在"
            raise ValueError(msg)
        profile = await self.session.get(m.GhgReportingProfile, report.reporting_profile_id)
        organization = await self.session.get(m.ReportingOrganization, report.reporting_org_id)
        period = await self.session.get(m.ReportingPeriod, report.reporting_period_id)
        boundary = await self.session.get(m.OrganizationBoundary, report.organization_boundary_id)
        if organization is None or period is None or boundary is None:
            msg = "盘查报告缺少报告主体、报告期或组织边界"
            raise ValueError(msg)
        enterprise = (
            await self.session.get(m.EnterpriseInfo, organization.enterprise_id)
            if organization.enterprise_id is not None
            else None
        )
        scope2_method = str(report.metrics_snapshot.get("defaultScope2Method") or run.default_scope2_method or "location")
        rows = [
            row
            for row in await self._result_rows(run.id)
            if row[0].ghg_scope != "scope2" or row[0].scope2_method in {"not_applicable", scope2_method}
        ]
        activity_ids = {activity.id for _result, activity, _method, _source in rows}
        record_codes = {activity.record_code for _result, activity, _method, _source in rows}
        evidence_rows = await self._evidence_rows(record_codes)
        factor_rows = await self._factor_rows(run.id, activity_ids)
        inventory = self._inventory_summary(run=run, rows=rows, scope2_method=scope2_method)
        template = await self._organization_template()
        context = {
            "project": {
                "report_code": report.report_code,
                "report_version": f"v{report.version}",
                "run_code": run.run_code,
                "verification_basis": boundary.standard_code or profile.standard_code if profile else None,
            },
            "template": template,
            "standard": {"name": template.get("standard_name"), "code": template.get("standard_code")},
            "enterprise": {
                "name": (enterprise.name if enterprise else None) or organization.name,
                "code": organization.code,
                "unify_code": (enterprise.unify_code if enterprise else None) or organization.legal_entity_code,
                "organization_type": organization.organization_type,
                "industry": enterprise.industry if enterprise else None,
                "registered_address": enterprise.location if enterprise else None,
                "operation_address": enterprise.location if enterprise else None,
            },
            "reporting_period": {
                "year": period.period_start.year,
                "period_start": period.period_start.isoformat(),
                "period_end": period.period_end.isoformat(),
                "base_year": period.base_year,
            },
            "inventory": inventory,
            "activity_data": self._activity_rows(rows, evidence_rows),
            "factor_parameters": factor_rows,
            "quality_issues": self._quality_rows(rows),
            "verification_findings": [],
            "verification_attachments": evidence_rows,
            "exclusions": await self._exclusion_rows(boundary.id),
            "inventory_source": {
                "status": report.status,
                "boundary_status": boundary.status,
                "boundary_no": boundary.boundary_no,
                "boundary_name": boundary.boundary_name,
                "inventory_code": report.inventory_code,
                "run_code": run.run_code,
            },
        }
        context["formal_readiness"] = readiness_dict(formal_report_readiness(context))
        return context

    async def _result_rows(self, run_id: int) -> list[ResultRow]:
        rows = await self.session.execute(
            select(
                GhgCalculationResult,
                GhgActivityRecord,
                GhgCalculationMethodDefinition,
                GhgEmissionSource,
            )
            .join(GhgActivityRecord, GhgActivityRecord.id == GhgCalculationResult.activity_id)
            .join(GhgCalculationMethodDefinition, GhgCalculationMethodDefinition.id == GhgCalculationResult.method_id)
            .outerjoin(GhgEmissionSource, GhgEmissionSource.id == GhgActivityRecord.emission_source_id)
            .where(GhgCalculationResult.run_id == run_id)
            .order_by(GhgActivityRecord.record_code, GhgCalculationResult.gas_code, GhgCalculationResult.scope2_method)
        )
        return [tuple(row) for row in rows.all()]

    async def _factor_rows(self, run_id: int, activity_ids: set[int]) -> list[dict[str, Any]]:
        if not activity_ids:
            return []
        activities = {
            item.id: item
            for item in (
                await self.session.scalars(select(GhgActivityRecord).where(GhgActivityRecord.id.in_(activity_ids)))
            ).all()
        }
        assignments = (
            await self.session.scalars(
                select(GhgParameterAssignment)
                .where(GhgParameterAssignment.run_id == run_id, GhgParameterAssignment.activity_id.in_(activity_ids))
                .order_by(GhgParameterAssignment.activity_id, GhgParameterAssignment.parameter_code)
            )
        ).all()
        return [
            {
                "record_code": activities[item.activity_id].record_code,
                "scope": activities[item.activity_id].ghg_scope,
                "factor_source": item.source_name,
                "factor_version": item.source_version or item.standard_code or item.selection_rule,
                "factor_unit": item.unit,
            }
            for item in assignments
            if item.activity_id in activities
        ]

    async def _evidence_rows(self, record_codes: set[str]) -> list[dict[str, Any]]:
        if not record_codes:
            return []
        rows = (
            await self.session.execute(
                select(GhgEvidenceLink, m.GhgEvidenceFile)
                .join(m.GhgEvidenceFile, m.GhgEvidenceFile.id == GhgEvidenceLink.evidence_id)
                .where(GhgEvidenceLink.record_type == "activity", GhgEvidenceLink.record_code.in_(record_codes))
                .order_by(GhgEvidenceLink.record_code, m.GhgEvidenceFile.evidence_code)
            )
        ).all()
        return [
            {
                "evidence_code": evidence.evidence_code,
                "record_code": link.record_code,
                "file_name": evidence.file_name,
                "attachment_type": evidence.document_type,
                "material_status": self._material_status(link.review_status, evidence.verification_status),
                "sha256": evidence.sha256,
            }
            for link, evidence in rows
        ]

    async def _exclusion_rows(self, boundary_id: int) -> list[dict[str, Any]]:
        facilities = (
            await self.session.scalars(
                select(m.BoundaryFacility)
                .where(m.BoundaryFacility.boundary_id == boundary_id, m.BoundaryFacility.included.is_(False))
                .order_by(m.BoundaryFacility.id)
            )
        ).all()
        return [
            {
                "name": item.facility_name or item.facility_code or "未命名边界对象",
                "reason": item.exclusion_reason,
                "impact": item.remark,
            }
            for item in facilities
        ]

    async def _organization_template(self) -> dict[str, Any]:
        template = await CarbonVerificationTemplateQueryService(self.session).active_template()
        if template.get("implementation_status") == "supported" and template.get("renderer_kind") == "generic_a4":
            return template
        return default_template_payload()

    def _inventory_summary(
        self,
        *,
        run: GhgCalculationRun,
        rows: list[ResultRow],
        scope2_method: str,
    ) -> dict[str, Any]:
        total_kg = self._total_kg(run, rows, scope2_method)
        scope_groups: dict[str, Decimal] = defaultdict(Decimal)
        gas_groups: dict[str, Decimal] = defaultdict(Decimal)
        iso_groups: dict[str, Decimal] = defaultdict(Decimal)
        scope2_groups: dict[str, Decimal] = defaultdict(Decimal)
        scope3_groups: dict[str, Decimal] = defaultdict(Decimal)
        source_groups: dict[tuple[str, str], dict[str, Any]] = {}
        for result, activity, _method, source in rows:
            source_name = (source.source_name if source is not None else activity.activity_name) or activity.source_code
            source_key = (result.ghg_scope, source_name)
            source_item = source_groups.setdefault(
                source_key,
                {"scope": result.ghg_scope, "record_label": source_name, "record_codes": set(), "t_co2e": Decimal(0)},
            )
            source_item["record_codes"].add(activity.record_code)
            source_item["t_co2e"] += result.co2e_kg / Decimal(1000)
            scope_groups[result.ghg_scope] += result.co2e_kg
            gas_groups[result.gas_code] += result.co2e_kg
            iso_groups[result.iso_category_code.split(".", 1)[0]] += result.co2e_kg
            if result.ghg_scope == "scope2":
                scope2_groups[result.scope2_method] += result.co2e_kg
            if result.ghg_scope == "scope3" and activity.scope3_category is not None:
                scope3_groups[str(activity.scope3_category)] += result.co2e_kg
        return {
            "default_scope2_method": scope2_method,
            "gwp_versions": sorted({result.gwp_version for result, *_rest in rows}),
            "totals": {"total_t_co2e": str(total_kg / Decimal(1000))},
            "scope_summary": [
                {"scope": key, "record_count": self._record_count(rows, ghg_scope=key), "kg_co2e": str(value), "t_co2e": str(value / Decimal(1000))}
                for key, value in sorted(scope_groups.items())
            ],
            "gas_summary": [
                {"gas_code": key, "kg_co2e": str(value), "t_co2e": str(value / Decimal(1000))}
                for key, value in sorted(gas_groups.items())
            ],
            "iso_category_summary": [
                {"label": CATEGORY_BY_CODE.get(key, CATEGORY_BY_CODE.get(f"{key}.1")).name if CATEGORY_BY_CODE.get(key) or CATEGORY_BY_CODE.get(f"{key}.1") else key, "kg_co2e": str(value), "t_co2e": str(value / Decimal(1000))}
                for key, value in sorted(iso_groups.items())
            ],
            "scope2_method_summary": [
                {"method": key, "kg_co2e": str(value), "t_co2e": str(value / Decimal(1000))}
                for key, value in sorted(scope2_groups.items())
            ],
            "scope3_category_summary": [
                {"label": SCOPE3_CATEGORY_LABELS.get(key, key), "kg_co2e": str(value), "t_co2e": str(value / Decimal(1000))}
                for key, value in sorted(scope3_groups.items())
            ],
            "source_summary": [
                {
                    "scope": item["scope"],
                    "record_label": item["record_label"],
                    "record_count": len(item["record_codes"]),
                    "t_co2e": str(item["t_co2e"]),
                }
                for item in sorted(source_groups.values(), key=lambda value: value["t_co2e"], reverse=True)
            ],
        }

    def _activity_rows(self, rows: list[ResultRow], evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ready_evidence = {row["record_code"] for row in evidence_rows if row.get("material_status") == "ready"}
        return [
            {
                "record_code": activity.record_code,
                "scope": result.ghg_scope,
                "iso_category_code": result.iso_category_code,
                "activity_name": activity.activity_name,
                "source_category": (source.source_name if source is not None else activity.source_code),
                "activity_amount": str(activity.activity_amount),
                "activity_unit": activity.activity_unit,
                "computed_co2e": str(result.co2e_kg),
                "evidence_status": "ready" if activity.record_code in ready_evidence else "pending",
            }
            for result, activity, _method, source in rows
        ]

    @staticmethod
    def _quality_rows(rows: list[ResultRow]) -> list[dict[str, Any]]:
        return [
            {
                "record_code": activity.record_code,
                "title": f"{activity.activity_name}核算质量状态为{result.quality_status}",
                "severity": "high" if result.quality_status == "failed" else "medium",
                "action": "复核活动数据、因子参数和证据材料",
            }
            for result, activity, _method, _source in rows
            if result.quality_status != "pass"
        ]

    @staticmethod
    def _total_kg(run: GhgCalculationRun, rows: list[ResultRow], scope2_method: str) -> Decimal:
        summary = dict(run.summary_snapshot or {})
        key = "totalMarketCo2eKg" if scope2_method == "market" else "totalLocationCo2eKg"
        if summary.get(key) is not None:
            return Decimal(str(summary[key]))
        if run.total_co2e_kg is not None and scope2_method == run.default_scope2_method:
            return run.total_co2e_kg
        return sum((result.co2e_kg for result, *_rest in rows), Decimal(0))

    @staticmethod
    def _record_count(rows: list[ResultRow], *, ghg_scope: str) -> int:
        return len({activity.record_code for result, activity, _method, _source in rows if result.ghg_scope == ghg_scope})

    @staticmethod
    def _material_status(link_status: str, evidence_status: str) -> str:
        ready_statuses = {"approved", "pass", "ready", "verified"}
        return "ready" if link_status in ready_statuses and evidence_status in ready_statuses else "pending"
