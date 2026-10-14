"""Internal organization-inventory report lifecycle."""

from __future__ import annotations

import tempfile
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_verification.domain.reporting import (
    ISO_CATEGORY_LABELS,
    SCOPE3_CATEGORY_LABELS,
    formal_report_readiness,
    readiness_dict,
)
from app.domain.carbon_verification.infrastructure.report_renderer import ReportDocumentRenderer
from app.domain.carbon_verification.queries.templates import (
    CarbonVerificationTemplateQueryService,
    default_template_payload,
)
from app.domain.ghg_inventory.domain.report_narrative import validate_narrative
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
        if action in {"submit", "resubmit"}:
            context = await ExportInventoryReport(self.session).report_context(report)
            report.content_snapshot = {**report.content_snapshot, "reportContext": context}
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
        narrative: dict[str, str] | None = None,
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
        if narrative is not None:
            snapshot = dict(report.content_snapshot or {})
            snapshot["narrative"] = validate_narrative(narrative)
            snapshot.pop("reportContext", None)
            report.content_snapshot = snapshot
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
        context = await self.report_context(report)
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

    async def report_context(self, report: GhgInventoryReport) -> dict[str, Any]:
        snapshot = dict(report.content_snapshot or {})
        if report.status not in {"draft", "rejected"}:
            if not snapshot.get("reportContext"):
                msg = "此报告版本未保存完整正文快照; 请从核算结果创建新版本后提交"
                raise ValueError(msg)
            context = deepcopy(snapshot["reportContext"])
            context["inventory_source"]["status"] = report.status
            context["formal_readiness"] = readiness_dict(formal_report_readiness(context))
            return context
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
        scope2_method = str(
            report.metrics_snapshot.get("defaultScope2Method") or run.default_scope2_method or "location"
        )
        rows = [
            row
            for row in await self._result_rows(run.id)
            if row[0].ghg_scope != "scope2" or row[0].scope2_method in {"not_applicable", scope2_method}
        ]
        activity_ids = {activity.id for _result, activity, _method, _source in rows}
        record_codes = {activity.record_code for _result, activity, _method, _source in rows}
        factor_rows = await self._factor_rows(run.id, activity_ids)
        evidence_rows = await self._evidence_rows(record_codes, factor_rows)
        inventory = self._inventory_summary(run=run, rows=rows, scope2_method=scope2_method)
        template = await self._organization_template()
        enterprise_details = dict(enterprise.other_info or {}) if enterprise else {}
        facilities = list(
            (
                await self.session.scalars(
                    select(m.BoundaryFacility)
                    .where(m.BoundaryFacility.boundary_id == boundary.id)
                    .order_by(m.BoundaryFacility.id)
                )
            ).all()
        )
        context = {
            "project": {
                "report_code": report.report_code,
                "report_version": f"v{report.version}",
                "title": report.title,
                "run_code": run.run_code,
                "verification_basis": boundary.standard_code or profile.standard_code if profile else None,
            },
            "template": template,
            "standard": {"name": profile.name if profile else None, "code": profile.standard_code if profile else None},
            "narrative": snapshot.get("narrative", {}),
            "organization_details": enterprise_details,
            "methods": list(
                {str(result.method_id): dict(result.formula_snapshot or {}) for result, *_ in rows}.values()
            ),
            "facilities": [
                {
                    "name": item.facility_name,
                    "code": item.facility_code,
                    "included": item.included,
                    "reason": item.exclusion_reason,
                    "source": item.source_name,
                }
                for item in facilities
            ],
            "enterprise": {
                "name": organization.name,
                "code": organization.code,
                "unify_code": organization.legal_entity_code,
                "linked_enterprise_name": enterprise.name if enterprise else None,
                "linked_enterprise_unify_code": enterprise.unify_code if enterprise else None,
                "organization_type": organization.organization_type,
                "industry": enterprise.industry if enterprise else None,
                "registered_address": (enterprise.other_info or {}).get("registered_address") if enterprise else None,
                "operation_address": enterprise.location if enterprise else None,
                "belong_unit": enterprise.belong_unit if enterprise else None,
            },
            "reporting_period": {
                "year": period.period_start.year,
                "period_start": period.period_start.isoformat(),
                "period_end": period.period_end.isoformat(),
                "base_year": period.base_year,
                "data_period_start": min(
                    (activity.period_start.isoformat() for _, activity, _, _ in rows), default=None
                ),
                "data_period_end": max((activity.period_end.isoformat() for _, activity, _, _ in rows), default=None),
            },
            "inventory": inventory,
            "activity_data": await self._allocated_activity_rows(run, rows, evidence_rows),
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
                "consolidation_method": boundary.boundary_method,
                "boundary_remark": boundary.remark,
                "operational_boundary": boundary.operational_boundary,
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
        definitions = (
            await self.session.scalars(
                select(m.GhgMethodParameterDefinition).where(
                    m.GhgMethodParameterDefinition.method_id.in_({item.method_id for item in assignments})
                )
            )
        ).all()
        names = {(item.method_id, item.parameter_code): item.parameter_name for item in definitions}
        return [
            {
                "record_code": activities[item.activity_id].record_code,
                "scope": activities[item.activity_id].ghg_scope,
                "factor_source": item.source_name,
                "factor_version": item.source_version or item.standard_code or item.selection_rule,
                "factor_unit": item.unit,
                "parameter_code": item.parameter_code,
                "parameter_name": names.get((item.method_id, item.parameter_code)),
                "factor_value": str(item.value),
                "standard_code": item.standard_code,
                "clause_reference": item.clause_reference,
                "table_reference": item.table_reference,
                "snapshot": item.snapshot,
            }
            for item in assignments
            if item.activity_id in activities
        ]

    async def _evidence_rows(self, record_codes: set[str], factor_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        evidence_rows = [
            {
                "evidence_code": evidence.evidence_code,
                "record_code": link.record_code,
                "file_name": evidence.file_name,
                "attachment_type": evidence.document_type,
                "material_status": self._material_status(link.review_status, evidence.verification_status),
                "sha256": evidence.sha256,
                "evidence_role": "activity",
            }
            for link, evidence in rows
        ]
        factor_codes = {
            row["snapshot"]["evidenceCode"] for row in factor_rows if (row.get("snapshot") or {}).get("evidenceCode")
        }
        files = (
            (
                await self.session.scalars(
                    select(m.GhgEvidenceFile).where(m.GhgEvidenceFile.evidence_code.in_(factor_codes))
                )
            ).all()
            if factor_codes
            else []
        )
        by_code = {item.evidence_code: item for item in files}
        for row in factor_rows:
            evidence = by_code.get((row.get("snapshot") or {}).get("evidenceCode"))
            if evidence is not None:
                evidence_rows.append(
                    {
                        "evidence_code": evidence.evidence_code,
                        "record_code": row["record_code"],
                        "file_name": evidence.file_name,
                        "attachment_type": evidence.document_type,
                        "material_status": self._material_status("ready", evidence.verification_status),
                        "sha256": evidence.sha256,
                        "evidence_role": "factor",
                    }
                )
        return evidence_rows

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
            "gwp_versions": sorted(
                {
                    result.gwp_version
                    for result, *_rest in rows
                    if result.gwp_version and result.gwp_version != "reporting-profile"
                }
            ),
            "totals": {"total_t_co2e": str(total_kg / Decimal(1000))},
            "scope_summary": [
                {
                    "scope": key,
                    "record_count": self._record_count(rows, ghg_scope=key),
                    "kg_co2e": str(value),
                    "t_co2e": str(value / Decimal(1000)),
                }
                for key, value in sorted(scope_groups.items())
            ],
            "gas_summary": [
                {"gas_code": key, "kg_co2e": str(value), "t_co2e": str(value / Decimal(1000))}
                for key, value in sorted(gas_groups.items())
            ],
            "iso_category_summary": [
                {
                    "iso_category_code": key,
                    "label": ISO_CATEGORY_LABELS.get(key, key),
                    "kg_co2e": str(value),
                    "t_co2e": str(value / Decimal(1000)),
                }
                for key, value in sorted(iso_groups.items())
            ],
            "scope2_method_summary": [
                {"method": key, "kg_co2e": str(value), "t_co2e": str(value / Decimal(1000))}
                for key, value in sorted(scope2_groups.items())
            ],
            "scope3_category_summary": [
                {
                    "label": SCOPE3_CATEGORY_LABELS.get(key, key),
                    "kg_co2e": str(value),
                    "t_co2e": str(value / Decimal(1000)),
                }
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

    async def _allocated_activity_rows(
        self, run: GhgCalculationRun, rows: list[ResultRow], evidence_rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        activities = self._activity_rows(rows, evidence_rows)
        allocations = {item["recordCode"]: item["items"] for item in (run.input_snapshot or {}).get("allocations", [])}
        equipment_ids = {
            item["equipmentId"] for items in allocations.values() for item in items if item.get("equipmentId")
        }
        equipment = (
            list(
                (
                    await self.session.scalars(
                        select(m.MonitorEquipment).where(m.MonitorEquipment.id.in_(equipment_ids))
                    )
                ).all()
            )
            if equipment_ids
            else []
        )
        names = {item.id: item.name for item in equipment}
        for activity in activities:
            # Ratios and membership belong to the calculation snapshot, not today's editable allocations.
            activity["device_allocations"] = [
                {
                    "device_id": item.get("equipmentId"),
                    "device_name": names.get(item.get("equipmentId")),
                    "area_path": item.get("areaPath"),
                    "ratio": item["ratio"],
                }
                for item in allocations.get(activity["record_code"], [])
            ]
        return activities

    def _activity_rows(self, rows: list[ResultRow], evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ready_evidence = {
            row["record_code"]
            for row in evidence_rows
            if row.get("material_status") == "ready" and row.get("evidence_role") != "factor"
        }
        activities: dict[str, dict[str, Any]] = {}
        for result, activity, _method, source in rows:
            row = activities.setdefault(
                activity.record_code,
                {
                    "record_code": activity.record_code,
                    "scope": result.ghg_scope,
                    "iso_category_code": result.iso_category_code,
                    "activity_name": activity.activity_name,
                    "source_category": (source.source_name if source is not None else activity.source_code),
                    "activity_amount": str(activity.activity_amount),
                    "activity_unit": activity.activity_unit,
                    "computed_co2e": "0",
                    "period_start": activity.period_start.isoformat(),
                    "period_end": activity.period_end.isoformat(),
                    "data_source_type": activity.data_source_type,
                    "measurement_method": activity.measurement_method,
                    "evidence_status": "ready" if activity.record_code in ready_evidence else "pending",
                },
            )
            row["computed_co2e"] = str(Decimal(row["computed_co2e"]) + result.co2e_kg)
        return list(activities.values())

    @staticmethod
    def _quality_rows(rows: list[ResultRow]) -> list[dict[str, Any]]:
        return [
            {
                "record_code": activity.record_code,
                "title": "核算记录待复核" if result.quality_status != "failed" else "核算记录检查未通过",
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
        return len(
            {activity.record_code for result, activity, _method, _source in rows if result.ghg_scope == ghg_scope}
        )

    @staticmethod
    def _material_status(link_status: str, evidence_status: str) -> str:
        ready_statuses = {"approved", "pass", "ready", "verified"}
        return "ready" if link_status in ready_statuses and evidence_status in ready_statuses else "pending"
