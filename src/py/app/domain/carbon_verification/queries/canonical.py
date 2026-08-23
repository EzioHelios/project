"""Canonical read model for report-bound organization GHG verification."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import and_, func, or_, select

from app.db import models as m
from app.domain.carbon_verification.domain.policies import MATERIAL_RULES, material_readiness
from app.domain.carbon_verification.domain.reporting import (
    ISO_CATEGORY_LABELS,
    SCOPE3_CATEGORY_LABELS,
    formal_report_readiness,
    readiness_dict,
    validate_report_context,
)
from app.domain.carbon_verification.queries.templates import CarbonVerificationTemplateQueryService

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class VerificationQuery:
    """Project-scoped verification query."""

    project_id: int | None = None
    year: int | None = None
    status: str | None = None
    scope: str | None = None
    limit: int = 200
    offset: int = 0


class CanonicalVerificationQueryService:
    """Build verification views only from a published report and its frozen run."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def source_readiness(self) -> dict[str, Any]:
        project_count = await self._count(
            m.CarbonVerificationProject, m.CarbonVerificationProject.inventory_report_id.is_not(None)
        )
        evidence_count = await self._count(m.GhgEvidenceFile)
        reviewed_evidence_count = await self._count(
            m.GhgEvidenceFile, m.GhgEvidenceFile.verification_status.in_(("reviewed", "approved"))
        )
        finding_count = await self._count(m.CarbonVerificationFinding)
        export_count = await self._count(m.CarbonVerificationExportJob)
        return {
            "status": "ready" if project_count else "project_missing",
            "project_count": project_count,
            "evidence_count": evidence_count,
            "reviewed_evidence_count": reviewed_evidence_count,
            "finding_count": finding_count,
            "export_job_count": export_count,
        }

    async def summary(self, query: VerificationQuery) -> dict[str, Any]:
        context = await self._context(query)
        records = await self._records(context, query)
        totals = self._totals(records)
        issues = self._issues(records)
        template = await CarbonVerificationTemplateQueryService(self.session).active_template(
            project_id=context.project.id
        )
        return {
            "project": self._project_ref(context),
            "enterprise": self._enterprise(context),
            "reporting_period": self._period(context),
            "inventory_source": self._inventory_source(context),
            "standard": self._standard(context),
            "totals": totals,
            "scope_summary": self._scope_summary(records),
            "record_count": len(records),
            "issue_count": len(issues),
            "readiness": material_readiness([str(item["material_status"]) for item in records]),
            "template": template,
        }

    async def evidence_manifest(self, query: VerificationQuery) -> dict[str, Any]:
        context = await self._context(query)
        records = await self._records(context, query)
        record_by_code = {str(row["record_code"]): row for row in records}
        activity_codes = list(record_by_code)
        links = list(
            (
                await self.session.execute(
                    select(m.GhgEvidenceLink, m.GhgEvidenceFile)
                    .join(m.GhgEvidenceFile, m.GhgEvidenceFile.id == m.GhgEvidenceLink.evidence_id)
                    .where(
                        or_(
                            and_(
                                m.GhgEvidenceLink.record_type == "activity",
                                m.GhgEvidenceLink.record_code.in_(activity_codes),
                            ),
                            and_(
                                m.GhgEvidenceLink.record_type == "verification_project",
                                m.GhgEvidenceLink.record_code == context.project.project_no,
                            ),
                        )
                    )
                    .order_by(m.GhgEvidenceFile.id.desc())
                )
            ).all()
        )
        linked_activity_codes = {link.record_code for link, _file in links if link.record_type == "activity"}
        items = [self._evidence_item(link, file, record_by_code.get(link.record_code)) for link, file in links]
        missing = [self._record_ref(record) for record in records if record["record_code"] not in linked_activity_codes]
        return {
            "items": items[query.offset : query.offset + self._limit(query.limit)],
            "missing": missing,
            "summary": {
                "evidence_count": len(items),
                "linked_activity_count": len(linked_activity_codes),
                "missing_evidence_count": len(missing),
                "record_count": len(records),
            },
            "inventory_source": self._inventory_source(context),
            "filters": self._filters(query),
        }

    async def issues(self, query: VerificationQuery) -> dict[str, Any]:
        context = await self._context(query)
        items = self._issues(await self._records(context, query))
        return {
            "items": items[query.offset : query.offset + self._limit(query.limit)],
            "total": len(items),
            "summary": self._count_by(items, "issue_type"),
            "filters": self._filters(query),
        }

    async def audit_trail(self, query: VerificationQuery) -> dict[str, Any]:
        context = await self._context(query)
        activity_codes = list(
            (
                await self.session.scalars(
                    select(m.GhgActivityRecord.record_code).where(
                        m.GhgActivityRecord.inventory_code == context.run.inventory_code
                    )
                )
            ).all()
        )
        evidence_links = list(
            (
                await self.session.execute(
                    select(m.GhgEvidenceLink, m.GhgEvidenceFile)
                    .join(m.GhgEvidenceFile, m.GhgEvidenceFile.id == m.GhgEvidenceLink.evidence_id)
                    .where(
                        m.GhgEvidenceLink.record_type == "activity",
                        m.GhgEvidenceLink.record_code.in_(activity_codes),
                    )
                )
            ).all()
        )
        reviews = list(
            (
                await self.session.scalars(
                    select(m.GhgInventoryReportReview)
                    .where(m.GhgInventoryReportReview.report_id == context.report.id)
                    .order_by(m.GhgInventoryReportReview.acted_at)
                )
            ).all()
        )
        findings = list(
            (
                await self.session.scalars(
                    select(m.CarbonVerificationFinding)
                    .where(m.CarbonVerificationFinding.project_id == context.project.id)
                    .order_by(m.CarbonVerificationFinding.updated_at)
                )
            ).all()
        )
        items = [
            {
                "record_type": "verification_project",
                "record_code": context.project.project_no,
                "action": "created",
                "comment": None,
                "operator": None,
                "created_at": context.project.created_at.isoformat() if context.project.created_at else None,
            }
        ]
        items.extend(
            {
                "record_type": "inventory_report",
                "record_code": context.report.report_code,
                "action": item.action,
                "comment": item.comment,
                "operator": item.actor,
                "created_at": item.acted_at.isoformat(),
            }
            for item in reviews
        )
        items.extend(
            {
                "record_type": "verification_finding",
                "record_code": item.finding_no,
                "action": item.status,
                "comment": item.correction_comment,
                "operator": item.reviewer or item.owner,
                "created_at": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in findings
        )
        for link, evidence_file in evidence_links:
            items.append(
                {
                    "record_type": "evidence",
                    "record_code": evidence_file.evidence_code,
                    "action": "uploaded",
                    "comment": link.record_code,
                    "operator": link.reviewer,
                    "created_at": evidence_file.created_at.isoformat() if evidence_file.created_at else None,
                }
            )
            if link.reviewed_at:
                items.append(
                    {
                        "record_type": "evidence",
                        "record_code": evidence_file.evidence_code,
                        "action": link.review_status,
                        "comment": link.record_code,
                        "operator": link.reviewer,
                        "created_at": link.reviewed_at.isoformat(),
                    }
                )
        items.sort(key=lambda item: str(item.get("created_at") or ""))
        return {"items": items, "total": len(items), "filters": self._filters(query)}

    async def material_package(self, query: VerificationQuery) -> dict[str, Any]:
        context = await self._context(query)
        records = await self._records(context, query)
        evidence = await self.evidence_manifest(query)
        issues = self._issues(records)
        audit = await self.audit_trail(query)
        finding_count = await self._count(
            m.CarbonVerificationFinding, m.CarbonVerificationFinding.project_id == context.project.id
        )
        open_finding_count = await self._count(
            m.CarbonVerificationFinding,
            m.CarbonVerificationFinding.project_id == context.project.id,
            m.CarbonVerificationFinding.status.in_(("open", "rectifying", "resolved")),
        )
        counts = {
            "boundary": 1,
            "inventory": len(records),
            "activity": len(records),
            "factor": sum(1 for row in records if row.get("factor_source")),
            "evidence": int(evidence["summary"]["evidence_count"]),
            "audit": int(audit["total"]),
            "quality": len(issues) + finding_count,
        }
        readiness = material_readiness([str(row["material_status"]) for row in records])
        if readiness == "ready" and open_finding_count:
            readiness = "attention"
        group_statuses = {
            "boundary": "ready",
            "inventory": "ready"
            if records and not any(row["material_status"] == "missing_result" for row in records)
            else "blocked",
            "activity": material_readiness([str(row["material_status"]) for row in records]),
            "factor": "ready" if records and all(row.get("factor_source") for row in records) else "blocked",
            "evidence": (
                "ready"
                if not evidence["summary"]["missing_evidence_count"]
                and all(item["material_status"] == "ready" for item in evidence["items"])
                else "attention"
            ),
            "audit": "ready" if audit["total"] else "attention",
            "quality": "ready" if not issues and not open_finding_count else "attention",
        }
        groups = [
            {
                "code": rule.code,
                "title": rule.title,
                "material_group": rule.material_group,
                "required": rule.required,
                "item_count": counts.get(rule.material_group, 0),
                "status": group_statuses.get(rule.material_group, "ready"),
            }
            for rule in MATERIAL_RULES
        ]
        return {
            "package_code": f"{context.project.project_no}-v{context.report.version}",
            "readiness": readiness,
            "groups": groups,
            "manifest": self._manifest(context),
            "inventory_source": self._inventory_source(context),
            "filters": self._filters(query),
        }

    async def report_context(self, query: VerificationQuery) -> dict[str, Any]:
        context = await self._context(query)
        records = await self._records(context, query)
        summary = await self.summary(query)
        evidence = await self.evidence_manifest(query)
        findings = list(
            (
                await self.session.scalars(
                    select(m.CarbonVerificationFinding)
                    .where(m.CarbonVerificationFinding.project_id == context.project.id)
                    .order_by(m.CarbonVerificationFinding.id)
                )
            ).all()
        )
        template = await CarbonVerificationTemplateQueryService(self.session).active_template(
            project_id=context.project.id
        )
        result_summaries = await self._result_summaries(context, query)
        report = {
            "project": self._project_ref(context),
            "template": template,
            "standard": self._standard(context),
            "enterprise": summary["enterprise"],
            "reporting_period": summary["reporting_period"],
            "inventory": {
                "totals": summary["totals"],
                "scope_summary": summary["scope_summary"],
                "source_summary": self._source_summary(records),
                **result_summaries,
                "source": summary["inventory_source"],
            },
            "activity_data": [self._activity_row(row) for row in records],
            "factor_parameters": self._factor_rows(records),
            "quality_issues": self._issues(records),
            "verification_findings": [self._finding_row(row) for row in findings],
            "verification_attachments": evidence["items"],
            "exclusions": [
                {
                    "name": item.facility_name or item.facility_code or "未命名边界对象",
                    "reason": item.exclusion_reason,
                    "impact": item.remark,
                }
                for item in context.boundary.facilities
                if not item.included
            ],
            "export_fields": self._template_field_map(),
            "inventory_source": summary["inventory_source"],
            "filters": self._filters(query),
        }
        report["formal_readiness"] = readiness_dict(formal_report_readiness(report))
        validate_report_context(report)
        return report

    async def _context(self, query: VerificationQuery) -> _VerificationContext:
        stmt = select(m.CarbonVerificationProject).where(
            m.CarbonVerificationProject.inventory_report_id.is_not(None),
            m.CarbonVerificationProject.status != "archived",
        )
        if query.project_id is not None:
            stmt = stmt.where(m.CarbonVerificationProject.id == query.project_id)
        else:
            stmt = stmt.order_by(m.CarbonVerificationProject.id.desc())
        project = await self.session.scalar(stmt.limit(1))
        if project is None or project.inventory_report is None or project.calculation_run is None:
            msg = "没有绑定已发布盘查报告的核查项目"
            raise ValueError(msg)
        if project.inventory_report.status != "published":
            msg = "核查项目绑定的盘查报告尚未发布"
            raise ValueError(msg)
        if project.calculation_run.status != "completed":
            msg = "核查项目绑定的核算运行尚未完成"
            raise ValueError(msg)
        profile = await self.session.get(m.GhgReportingProfile, project.inventory_report.reporting_profile_id)
        period = await self.session.get(m.ReportingPeriod, project.inventory_report.reporting_period_id)
        organization = await self.session.get(m.ReportingOrganization, project.inventory_report.reporting_org_id)
        boundary = await self.session.get(m.OrganizationBoundary, project.inventory_report.organization_boundary_id)
        enterprise = (
            await self.session.get(m.EnterpriseInfo, organization.enterprise_id)
            if organization is not None and organization.enterprise_id is not None
            else None
        )
        if profile is None or period is None or organization is None or boundary is None:
            msg = "核查项目缺少报告标准、报告期、组织或边界快照"
            raise ValueError(msg)
        return _VerificationContext(
            project,
            project.inventory_report,
            project.calculation_run,
            profile,
            period,
            organization,
            boundary,
            enterprise,
        )

    async def _records(self, context: _VerificationContext, query: VerificationQuery) -> list[dict[str, Any]]:
        activities = list(
            (
                await self.session.scalars(
                    select(m.GhgActivityRecord)
                    .where(
                        m.GhgActivityRecord.inventory_code == context.run.inventory_code,
                        m.GhgActivityRecord.boundary_status == "included",
                    )
                    .order_by(m.GhgActivityRecord.period_start, m.GhgActivityRecord.record_code)
                )
            ).all()
        )
        if query.scope and query.scope != "all":
            activities = [item for item in activities if item.ghg_scope == query.scope]
        activity_ids = [item.id for item in activities]
        source_rows = list(
            (
                await self.session.execute(
                    select(
                        m.GhgEmissionSource.id, m.GhgEmissionSource.source_code, m.GhgEmissionSource.source_name
                    ).where(m.GhgEmissionSource.inventory_code == context.run.inventory_code)
                )
            ).all()
        )
        source_names_by_id = {source_id: source_name for source_id, _source_code, source_name in source_rows}
        source_names_by_code = {source_code: source_name for _source_id, source_code, source_name in source_rows}
        result_rows = (
            await self.session.execute(
                select(m.GhgCalculationResult.activity_id, func.sum(m.GhgCalculationResult.co2e_kg))
                .where(
                    m.GhgCalculationResult.run_id == context.run.id,
                    m.GhgCalculationResult.activity_id.in_(activity_ids),
                    or_(
                        m.GhgCalculationResult.ghg_scope != "scope2",
                        m.GhgCalculationResult.scope2_method == context.run.default_scope2_method,
                    ),
                )
                .group_by(m.GhgCalculationResult.activity_id)
            )
        ).all()
        totals = {activity_id: Decimal(value or 0) for activity_id, value in result_rows}
        assignments = list(
            (
                await self.session.scalars(
                    select(m.GhgParameterAssignment).where(
                        m.GhgParameterAssignment.run_id == context.run.id,
                        m.GhgParameterAssignment.activity_id.in_(activity_ids),
                    )
                )
            ).all()
        )
        assignment_by_activity: dict[int, list[Any]] = {}
        for item in assignments:
            assignment_by_activity.setdefault(item.activity_id, []).append(item)
        evidence_rows = (
            await self.session.execute(
                select(m.GhgEvidenceLink.record_code, m.GhgEvidenceFile.verification_status)
                .join(m.GhgEvidenceFile, m.GhgEvidenceFile.id == m.GhgEvidenceLink.evidence_id)
                .where(
                    m.GhgEvidenceLink.record_type == "activity",
                    m.GhgEvidenceLink.record_code.in_([item.record_code for item in activities]),
                )
            )
        ).all()
        evidence_statuses: dict[str, set[str]] = {}
        for record_code, verification_status in evidence_rows:
            evidence_statuses.setdefault(record_code, set()).add(verification_status)
        records: list[dict[str, Any]] = []
        for activity in activities:
            parameters = assignment_by_activity.get(activity.id, [])
            co2e = totals.get(activity.id)
            if co2e is None:
                material_status = "missing_result"
            elif not parameters:
                material_status = "missing_factor"
            elif activity.record_code not in evidence_statuses:
                material_status = "missing_evidence"
            elif not evidence_statuses[activity.record_code].intersection(
                {"reviewed", "approved"}
            ) or activity.quality_status not in {"pass", "ready", "approved"}:
                material_status = "pending_review"
            else:
                material_status = "ready"
            records.append(
                {
                    "record_type": "activity",
                    "record_id": activity.id,
                    "record_code": activity.record_code,
                    "record_label": (
                        source_names_by_id.get(activity.emission_source_id)
                        or source_names_by_code.get(activity.source_code)
                        or activity.national_source_category
                        or activity.activity_name
                    ),
                    "scope": activity.ghg_scope,
                    "iso_category_code": activity.iso_category_code,
                    "scope3_category": activity.scope3_category,
                    "display_name": activity.activity_name,
                    "period": f"{activity.period_start.isoformat()}~{activity.period_end.isoformat()}",
                    "status": activity.status,
                    "activity_amount": activity.activity_amount,
                    "activity_unit": activity.activity_unit,
                    "computed_co2e": co2e,
                    "factor_source": "; ".join(sorted({item.source_name for item in parameters})) or None,
                    "factor_year": "; ".join(
                        sorted({item.source_version for item in parameters if item.source_version})
                    )
                    or None,
                    "factor_unit": "; ".join(sorted({item.unit for item in parameters})) or None,
                    "attachment": None,
                    "material_status": material_status,
                }
            )
        return records

    @staticmethod
    def _totals(records: list[dict[str, Any]]) -> dict[str, Any]:
        total = sum((Decimal(row.get("computed_co2e") or 0) for row in records), Decimal(0))
        return {
            "total_kg_co2e": float(total),
            "total_t_co2e": float(total / Decimal(1000)),
            "missing_result_count": sum(1 for row in records if row["material_status"] == "missing_result"),
        }

    @staticmethod
    def _scope_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in records:
            scope = str(row["scope"])
            item = grouped.setdefault(scope, {"scope": scope, "record_count": 0, "kg_co2e": Decimal(0)})
            item["record_count"] += 1
            item["kg_co2e"] += Decimal(row.get("computed_co2e") or 0)
        return [
            {
                "scope": row["scope"],
                "record_count": row["record_count"],
                "kg_co2e": float(row["kg_co2e"]),
                "t_co2e": float(row["kg_co2e"] / Decimal(1000)),
            }
            for row in grouped.values()
        ]

    @staticmethod
    def _source_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for row in records:
            key = (str(row["scope"]), str(row["record_label"]))
            item = grouped.setdefault(
                key,
                {"scope": key[0], "record_label": key[1], "record_count": 0, "kg_co2e": Decimal(0)},
            )
            item["record_count"] += 1
            item["kg_co2e"] += Decimal(row.get("computed_co2e") or 0)
        return [
            {
                **row,
                "kg_co2e": float(row["kg_co2e"]),
                "t_co2e": float(row["kg_co2e"] / Decimal(1000)),
            }
            for row in grouped.values()
        ]

    @staticmethod
    def _issues(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        labels = {
            "missing_result": ("缺少核算结果", "high", "重新执行并完成组织温室气体核算。"),
            "missing_factor": ("缺少计算参数", "high", "补充并审核计算参数及其来源。"),
            "missing_evidence": ("缺少原始凭证", "medium", "上传并关联活动数据原始凭证。"),
            "pending_review": ("活动数据待复核", "medium", "完成活动数据及证据复核。"),
        }
        items: list[dict[str, Any]] = []
        for row in records:
            status = str(row["material_status"])
            if status == "ready":
                continue
            title, severity, action = labels[status]
            items.append(
                {
                    "issue_type": status,
                    "severity": severity,
                    "title": title,
                    "record_type": "activity",
                    "record_code": row["record_code"],
                    "scope": row["scope"],
                    "display_name": row["display_name"],
                    "period": row["period"],
                    "action": action,
                }
            )
        return items

    @staticmethod
    def _activity_row(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "record_type": record["record_type"],
            "record_code": record["record_code"],
            "scope": record["scope"],
            "iso_category_code": record["iso_category_code"],
            "scope3_category": record["scope3_category"],
            "source_category": record["record_label"],
            "activity_name": record["display_name"],
            "period": record["period"],
            "activity_amount": record["activity_amount"],
            "activity_unit": record["activity_unit"],
            "computed_co2e": record["computed_co2e"],
            "status": record["status"],
            "evidence_status": record["material_status"],
        }

    @staticmethod
    def _factor_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "record_code": row["record_code"],
                "factor_source": row["factor_source"],
                "factor_unit": row["factor_unit"],
                "factor_version": row["factor_year"],
                "scope": row["scope"],
            }
            for row in records
            if row.get("factor_source")
        ]

    @staticmethod
    def _finding_row(row: m.CarbonVerificationFinding) -> dict[str, Any]:
        return {
            "finding_no": row.finding_no,
            "issue_type": row.issue_type,
            "severity": row.severity,
            "title": row.title,
            "record_type": row.record_type,
            "record_code": row.record_code,
            "scope": row.scope,
            "display_name": row.display_name,
            "period": row.period,
            "status": row.status,
            "action_required": row.action_required,
            "correction_comment": row.correction_comment,
            "reviewer": row.reviewer,
            "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        }

    @staticmethod
    def _evidence_item(
        link: m.GhgEvidenceLink, file: m.GhgEvidenceFile, record: dict[str, Any] | None
    ) -> dict[str, Any]:
        return {
            "evidence_code": file.evidence_code,
            "record_type": link.record_type,
            "record_code": link.record_code,
            "scope": record.get("scope") if record else None,
            "display_name": record.get("display_name") if record else file.file_name,
            "period": record.get("period") if record else None,
            "path": file.storage_key,
            "material_status": "ready" if file.verification_status in {"reviewed", "approved"} else "pending_review",
            "attachment_type": file.document_type,
            "file_name": file.file_name,
            "sha256": file.sha256,
            "source": "ghg_evidence",
            "evidence_role": link.evidence_role,
            "review_status": link.review_status,
        }

    @staticmethod
    def _record_ref(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "record_type": record["record_type"],
            "record_code": record["record_code"],
            "scope": record["scope"],
            "display_name": record["display_name"],
            "period": record["period"],
            "material_status": record["material_status"],
        }

    @staticmethod
    def _project_ref(context: _VerificationContext) -> dict[str, Any]:
        project = context.project
        return {
            "id": project.id,
            "project_no": project.project_no,
            "project_name": project.project_name,
            "report_code": context.report.report_code,
            "report_version": context.report.version,
            "run_code": context.run.run_code,
            "assurance_level": project.assurance_level,
            "materiality_threshold_pct": (
                str(project.materiality_threshold_pct) if project.materiality_threshold_pct is not None else None
            ),
            "verification_basis": project.verification_basis,
            "sampling_strategy": project.sampling_strategy,
            "site_visit_required": project.site_visit_required,
            "site_visit_status": project.site_visit_status,
            "conclusion_status": project.conclusion_status,
        }

    @staticmethod
    def _enterprise(context: _VerificationContext) -> dict[str, Any]:
        enterprise = context.enterprise
        other_info = cast("dict[str, Any] | None", getattr(enterprise, "other_info", None)) if enterprise else None
        return {
            "name": context.organization.name,
            "code": context.organization.code,
            "unify_code": context.organization.legal_entity_code or (enterprise.unify_code if enterprise else None),
            "organization_type": context.organization.organization_type,
            "industry": enterprise.industry if enterprise else None,
            "registered_address": enterprise.location if enterprise else None,
            "operation_address": enterprise.location if enterprise else None,
            "people_count": enterprise.people_count if enterprise else None,
            "other_info": other_info,
        }

    @staticmethod
    def _period(context: _VerificationContext) -> dict[str, Any]:
        return {
            "year": context.period.period_end.year,
            "period_start": context.period.period_start.isoformat(),
            "period_end": context.period.period_end.isoformat(),
            "base_year": context.period.base_year,
        }

    @staticmethod
    def _standard(context: _VerificationContext) -> dict[str, Any]:
        return {
            "name": context.profile.name,
            "code": context.profile.standard_code,
            "version": context.profile.version,
            "source_name": "ghg_reporting_profile",
            "gwp_versions": [],
        }

    async def _result_summaries(self, context: _VerificationContext, query: VerificationQuery) -> dict[str, Any]:
        rows = list(
            (
                await self.session.execute(
                    select(m.GhgCalculationResult, m.GhgActivityRecord.scope3_category)
                    .join(m.GhgActivityRecord, m.GhgActivityRecord.id == m.GhgCalculationResult.activity_id)
                    .where(
                        m.GhgCalculationResult.run_id == context.run.id,
                        m.GhgActivityRecord.boundary_status == "included",
                    )
                )
            ).all()
        )
        if query.scope and query.scope != "all":
            rows = [(result, scope3) for result, scope3 in rows if result.ghg_scope == query.scope]

        def included_result(result: m.GhgCalculationResult) -> bool:
            return result.ghg_scope != "scope2" or result.scope2_method == context.run.default_scope2_method

        included = [(result, scope3) for result, scope3 in rows if included_result(result)]
        gas = self._group_result_rows(included, lambda result, _scope3: result.gas_code, "gas_code")
        iso = self._group_result_rows(
            included,
            lambda result, _scope3: result.iso_category_code.split(".", 1)[0],
            "iso_category_code",
            labels=ISO_CATEGORY_LABELS,
        )
        scope2 = self._group_result_rows(
            [(result, scope3) for result, scope3 in rows if result.ghg_scope == "scope2"],
            lambda result, _scope3: result.scope2_method,
            "method",
        )
        scope3 = self._group_result_rows(
            [(result, category) for result, category in included if result.ghg_scope == "scope3"],
            lambda _result, category: str(category) if category is not None else "unclassified",
            "scope3_category",
            labels=SCOPE3_CATEGORY_LABELS,
        )
        return {
            "gas_summary": gas,
            "iso_category_summary": iso,
            "scope2_method_summary": scope2,
            "scope3_category_summary": scope3,
            "gwp_versions": sorted({result.gwp_version for result, _scope3 in rows if result.gwp_version}),
            "default_scope2_method": context.run.default_scope2_method,
        }

    @staticmethod
    def _group_result_rows(
        rows: list[tuple[m.GhgCalculationResult, int | None]],
        key_fn: Callable[[m.GhgCalculationResult, int | None], str | int | None],
        key_name: str,
        *,
        labels: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        grouped: dict[str, Decimal] = {}
        for result, scope3_category in rows:
            key = str(key_fn(result, scope3_category) or "unclassified")
            grouped[key] = grouped.get(key, Decimal(0)) + Decimal(result.co2e_kg or 0)
        return [
            {
                key_name: key,
                "label": (labels or {}).get(key, key),
                "kg_co2e": float(value),
                "t_co2e": float(value / Decimal(1000)),
            }
            for key, value in sorted(grouped.items())
        ]

    @staticmethod
    def _inventory_source(context: _VerificationContext) -> dict[str, Any]:
        return {
            "mode": "published_inventory_report",
            "status": context.report.status,
            "locked": True,
            "report_id": context.report.id,
            "report_code": context.report.report_code,
            "report_version": context.report.version,
            "run_id": context.run.id,
            "run_code": context.run.run_code,
            "scope2_method": context.run.default_scope2_method,
            "boundary_id": context.boundary.id,
            "boundary_no": context.boundary.boundary_no,
            "boundary_name": context.boundary.boundary_name,
            "boundary_method": context.boundary.boundary_method,
            "boundary_version": context.boundary.version,
            "boundary_status": context.boundary.status,
        }

    @staticmethod
    def _manifest(context: _VerificationContext) -> list[dict[str, Any]]:
        year = context.period.period_end.year
        return [
            {"path": f"report/{year}-organization-ghg-report.docx", "type": "report_docx"},
            {"path": "data/activity-data.csv", "type": "activity_data"},
            {"path": "data/factor-parameters.csv", "type": "factor_parameters"},
            {"path": "evidence/evidence-manifest.csv", "type": "evidence_manifest"},
            {"path": "quality/issues.csv", "type": "quality_issues"},
            {"path": "audit/audit-trail.csv", "type": "audit_trail"},
            {"path": "manifest.json", "type": "manifest"},
        ]

    @staticmethod
    def _template_field_map() -> list[dict[str, str]]:
        return [
            {"field": "{{ enterprise_name }}", "source": "enterprise.name"},
            {"field": "{{ report_year }}", "source": "reporting_period.year"},
            {"field": "{{ accounting_standard_code }}", "source": "standard.code"},
            {"field": "{{ scope_summary }}", "source": "inventory.scope_summary"},
            {"field": "{{ activity_data }}", "source": "activity_data"},
            {"field": "{{ factor_parameters }}", "source": "factor_parameters"},
            {"field": "{{ evidence_manifest }}", "source": "verification_attachments"},
        ]

    @staticmethod
    def _filters(query: VerificationQuery) -> dict[str, Any]:
        return {
            "project_id": query.project_id,
            "year": query.year,
            "status": query.status,
            "scope": query.scope,
            "limit": query.limit,
            "offset": query.offset,
        }

    @staticmethod
    def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
        result: dict[str, int] = {}
        for item in items:
            value = str(item.get(key) or "unknown")
            result[value] = result.get(value, 0) + 1
        return result

    @staticmethod
    def _limit(value: int) -> int:
        return max(1, min(int(value or 200), 500))

    async def _count(self, model: type[Any], *conditions: Any) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


@dataclass(frozen=True, slots=True)
class _VerificationContext:
    project: m.CarbonVerificationProject
    report: m.GhgInventoryReport
    run: m.GhgCalculationRun
    profile: m.GhgReportingProfile
    period: m.ReportingPeriod
    organization: m.ReportingOrganization
    boundary: m.OrganizationBoundary
    enterprise: m.EnterpriseInfo | None
