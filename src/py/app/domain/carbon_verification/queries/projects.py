from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import func, select

from app.db import models as m

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ProjectQuery:
    status: str | None = None
    reporting_org_id: int | None = None
    period_id: int | None = None
    inventory_report_id: int | None = None
    verification_year: int | None = None
    limit: int = 100
    offset: int = 0


class CarbonVerificationProjectQueryService:
    """Read model service for formal verification projects."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project(self, project_id: int) -> dict[str, Any]:
        row = await self._session.get(m.CarbonVerificationProject, project_id)
        if row is None:
            msg = "核查项目不存在"
            raise ValueError(msg)
        return await self.project_payload(row)

    async def list_projects(self, query: ProjectQuery) -> dict[str, Any]:
        stmt = select(m.CarbonVerificationProject).order_by(m.CarbonVerificationProject.id.desc())
        count_stmt = select(func.count(m.CarbonVerificationProject.id))
        for condition in _conditions(query):
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        rows = (
            (await self._session.execute(stmt.limit(_limit(query.limit)).offset(max(0, query.offset)))).scalars().all()
        )
        total = int(await self._session.scalar(count_stmt) or 0)
        return {
            "items": [await self.project_payload(row) for row in rows],
            "total": total,
            "limit": _limit(query.limit),
            "offset": max(0, query.offset),
            "summary": await self.summary(query),
            "filters": _filters(query),
        }

    async def summary(self, query: ProjectQuery | None = None) -> dict[str, Any]:
        stmt = select(m.CarbonVerificationProject)
        if query is not None:
            for condition in _conditions(query):
                stmt = stmt.where(condition)
        rows = list((await self._session.execute(stmt)).scalars().all())
        return {
            "total": len(rows),
            "by_status": _count_by(rows, "status"),
            "active_count": sum(1 for row in rows if row.status in {"draft", "in_progress", "review"}),
            "completed_count": sum(1 for row in rows if row.status == "completed"),
        }

    async def project_payload(self, row: m.CarbonVerificationProject) -> dict[str, Any]:
        finding_count = await self._count(m.CarbonVerificationFinding, m.CarbonVerificationFinding.project_id == row.id)
        open_finding_count = await self._count(
            m.CarbonVerificationFinding,
            m.CarbonVerificationFinding.project_id == row.id,
            m.CarbonVerificationFinding.status.in_(("open", "rectifying", "resolved")),
        )
        evidence_count = await self._project_evidence_count(row)
        export_count = await self._count(
            m.CarbonVerificationExportJob, m.CarbonVerificationExportJob.project_id == row.id
        )
        return {
            "id": row.id,
            "project_no": row.project_no,
            "project_name": row.project_name,
            "project_type": row.project_type,
            "status": row.status,
            "verification_year": row.verification_year,
            "reporting_org_id": row.reporting_org_id,
            "reporting_org_name": row.organization.name if row.organization else None,
            "period_id": row.period_id,
            "period_name": row.period.name if row.period else None,
            "period_start": row.period.period_start.isoformat() if row.period else None,
            "period_end": row.period.period_end.isoformat() if row.period else None,
            "boundary_id": row.boundary_id,
            "boundary_name": row.boundary.boundary_name if row.boundary else None,
            "boundary_no": row.boundary.boundary_no if row.boundary else None,
            "inventory_report_id": row.inventory_report_id,
            "report_code": row.inventory_report.report_code if row.inventory_report else None,
            "report_version": row.inventory_report.version if row.inventory_report else None,
            "report_title": row.inventory_report.title if row.inventory_report else None,
            "report_status": row.inventory_report.status if row.inventory_report else None,
            "calculation_run_id": row.calculation_run_id,
            "run_code": row.calculation_run.run_code if row.calculation_run else None,
            "inventory_code": row.calculation_run.inventory_code if row.calculation_run else None,
            "template_version_id": row.template_version_id,
            "template_name": row.template_version.template_name if row.template_version else None,
            "template_version": row.template_version.version if row.template_version else None,
            "planned_start": row.planned_start.isoformat() if row.planned_start else None,
            "planned_end": row.planned_end.isoformat() if row.planned_end else None,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "lead_reviewer": row.lead_reviewer,
            "responsible_person": row.responsible_person,
            "verifier_org": row.verifier_org,
            "assurance_level": row.assurance_level,
            "materiality_threshold_pct": (
                str(row.materiality_threshold_pct) if row.materiality_threshold_pct is not None else None
            ),
            "verification_basis": row.verification_basis,
            "sampling_strategy": row.sampling_strategy,
            "site_visit_required": row.site_visit_required,
            "site_visit_status": row.site_visit_status,
            "conclusion_status": row.conclusion_status,
            "readiness_status": row.readiness_status,
            "conclusion": row.conclusion,
            "scope_description": row.scope_description,
            "finding_summary": cast("dict[str, Any] | None", cast("Any", row).finding_summary),
            "artifact_counts": {
                "finding_count": finding_count,
                "open_finding_count": open_finding_count,
                "evidence_count": evidence_count,
                "export_count": export_count,
            },
            "source_name": row.source_name,
            "standard_code": row.standard_code,
            "confidence_level": row.confidence_level,
            "remark": row.remark,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    async def _count(self, model: type[Any], *conditions: Any) -> int:
        return int(
            (await self._session.execute(select(func.count()).select_from(model).where(*conditions))).scalar_one() or 0
        )

    async def _project_evidence_count(self, row: m.CarbonVerificationProject) -> int:
        project_links = int(
            await self._session.scalar(
                select(func.count(func.distinct(m.GhgEvidenceLink.evidence_id))).where(
                    m.GhgEvidenceLink.record_type == "verification_project",
                    m.GhgEvidenceLink.record_code == row.project_no,
                )
            )
            or 0
        )
        if row.calculation_run is None:
            return project_links
        activity_codes = select(m.GhgActivityRecord.record_code).where(
            m.GhgActivityRecord.inventory_code == row.calculation_run.inventory_code
        )
        activity_links = int(
            await self._session.scalar(
                select(func.count(func.distinct(m.GhgEvidenceLink.evidence_id))).where(
                    m.GhgEvidenceLink.record_type == "activity",
                    m.GhgEvidenceLink.record_code.in_(activity_codes),
                )
            )
            or 0
        )
        return project_links + activity_links


def _conditions(query: ProjectQuery) -> list[Any]:
    conditions: list[Any] = []
    if query.status is None:
        conditions.append(m.CarbonVerificationProject.status != "archived")
    elif query.status != "all":
        conditions.append(m.CarbonVerificationProject.status == query.status)
    if query.reporting_org_id is not None:
        conditions.append(m.CarbonVerificationProject.reporting_org_id == query.reporting_org_id)
    if query.period_id is not None:
        conditions.append(m.CarbonVerificationProject.period_id == query.period_id)
    if query.inventory_report_id is not None:
        conditions.append(m.CarbonVerificationProject.inventory_report_id == query.inventory_report_id)
    if query.verification_year is not None:
        conditions.append(m.CarbonVerificationProject.verification_year == query.verification_year)
    return conditions


def _count_by(rows: Sequence[m.CarbonVerificationProject], attr: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        value = str(getattr(row, attr, None) or "unknown")
        result[value] = result.get(value, 0) + 1
    return result


def _filters(query: ProjectQuery) -> dict[str, Any]:
    return {
        "status": query.status,
        "reporting_org_id": query.reporting_org_id,
        "period_id": query.period_id,
        "inventory_report_id": query.inventory_report_id,
        "verification_year": query.verification_year,
        "limit": query.limit,
        "offset": query.offset,
    }


def _limit(value: int) -> int:
    return max(1, min(int(value or 100), 500))
