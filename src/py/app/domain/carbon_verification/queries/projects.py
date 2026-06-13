from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ProjectQuery:
    status: str | None = None
    reporting_org_id: int | None = None
    period_id: int | None = None
    accounting_batch_id: int | None = None
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
        rows = (await self._session.execute(stmt.limit(_limit(query.limit)).offset(max(0, query.offset)))).scalars().all()
        total = int(await self._session.scalar(count_stmt) or 0)
        return {
            "items": [await self.project_payload(row) for row in rows],
            "total": total,
            "limit": _limit(query.limit),
            "offset": max(0, query.offset),
            "summary": await self.summary(),
            "filters": _filters(query),
        }

    async def summary(self) -> dict[str, Any]:
        rows = (await self._session.execute(select(m.CarbonVerificationProject))).scalars().all()
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
        attachment_count = await self._count(m.CarbonVerificationAttachment, m.CarbonVerificationAttachment.project_id == row.id)
        export_count = await self._count(m.CarbonVerificationExportJob, m.CarbonVerificationExportJob.project_id == row.id)
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
            "accounting_batch_id": row.accounting_batch_id,
            "batch_no": row.accounting_batch.batch_no if row.accounting_batch else None,
            "batch_name": row.accounting_batch.batch_name if row.accounting_batch else None,
            "batch_status": row.accounting_batch.status if row.accounting_batch else None,
            "batch_inventory_status": row.accounting_batch.inventory_status if row.accounting_batch else None,
            "batch_locked": _batch_locked(row.accounting_batch) if row.accounting_batch else False,
            "batch_locked_at": row.accounting_batch.locked_at.isoformat() if row.accounting_batch and row.accounting_batch.locked_at else None,
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
            "readiness_status": row.readiness_status,
            "conclusion": row.conclusion,
            "scope_description": row.scope_description,
            "finding_summary": row.finding_summary,
            "artifact_counts": {
                "finding_count": finding_count,
                "open_finding_count": open_finding_count,
                "attachment_count": attachment_count,
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
        return int((await self._session.execute(select(func.count()).select_from(model).where(*conditions))).scalar_one() or 0)


def _conditions(query: ProjectQuery) -> list[Any]:
    conditions = []
    if query.status and query.status != "all":
        conditions.append(m.CarbonVerificationProject.status == query.status)
    if query.reporting_org_id is not None:
        conditions.append(m.CarbonVerificationProject.reporting_org_id == query.reporting_org_id)
    if query.period_id is not None:
        conditions.append(m.CarbonVerificationProject.period_id == query.period_id)
    if query.accounting_batch_id is not None:
        conditions.append(m.CarbonVerificationProject.accounting_batch_id == query.accounting_batch_id)
    if query.verification_year is not None:
        conditions.append(m.CarbonVerificationProject.verification_year == query.verification_year)
    return conditions


def _count_by(rows: list[m.CarbonVerificationProject], attr: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        value = str(getattr(row, attr, None) or "unknown")
        result[value] = result.get(value, 0) + 1
    return result


def _batch_locked(batch: m.CarbonAccountingBatch) -> bool:
    return batch.status == "locked" and batch.inventory_status == "locked"


def _filters(query: ProjectQuery) -> dict[str, Any]:
    return {
        "status": query.status,
        "reporting_org_id": query.reporting_org_id,
        "period_id": query.period_id,
        "accounting_batch_id": query.accounting_batch_id,
        "verification_year": query.verification_year,
        "limit": query.limit,
        "offset": query.offset,
    }


def _limit(value: int) -> int:
    return max(1, min(int(value or 100), 500))
