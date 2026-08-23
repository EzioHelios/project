from __future__ import annotations

import datetime
from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_verification.domain.policies import finding_readiness

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class FindingQuery:
    project_id: int | None = None
    status: str | None = None
    severity: str | None = None
    record_type: str | None = None
    limit: int = 100
    offset: int = 0


class CarbonVerificationFindingQueryService:
    """Read model service for verification findings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_finding(self, finding_id: int) -> dict[str, Any]:
        row = await self._session.get(m.CarbonVerificationFinding, finding_id)
        if row is None:
            msg = "核查发现不存在"
            raise ValueError(msg)
        return _finding_payload(row)

    async def list_findings(self, query: FindingQuery) -> dict[str, Any]:
        stmt = select(m.CarbonVerificationFinding).order_by(m.CarbonVerificationFinding.id.desc())
        count_stmt = select(func.count(m.CarbonVerificationFinding.id))
        for condition in _conditions(query):
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        rows = (
            (await self._session.execute(stmt.limit(_limit(query.limit)).offset(max(0, query.offset)))).scalars().all()
        )
        total = int(await self._session.scalar(count_stmt) or 0)
        summary = await self.summary(query)
        return {
            "items": [_finding_payload(row) for row in rows],
            "total": total,
            "limit": _limit(query.limit),
            "offset": max(0, query.offset),
            "summary": summary,
            "filters": _filters(query),
        }

    async def summary(self, query: FindingQuery | None = None) -> dict[str, Any]:
        stmt = select(m.CarbonVerificationFinding)
        if query is not None:
            for condition in _conditions(query):
                stmt = stmt.where(condition)
        rows = list((await self._session.execute(stmt)).scalars().all())
        statuses = [row.status for row in rows]
        return {
            "total": len(rows),
            "by_status": _count_by(rows, "status"),
            "by_severity": _count_by(rows, "severity"),
            "open_count": sum(1 for row in rows if row.status in {"open", "rectifying"}),
            "overdue_count": _overdue_count(rows),
            "readiness": finding_readiness(statuses),
        }


def _conditions(query: FindingQuery) -> list[Any]:
    conditions: list[Any] = []
    if query.project_id is not None:
        conditions.append(m.CarbonVerificationFinding.project_id == query.project_id)
    if query.status and query.status != "all":
        conditions.append(m.CarbonVerificationFinding.status == query.status)
    if query.severity and query.severity != "all":
        conditions.append(m.CarbonVerificationFinding.severity == query.severity)
    if query.record_type and query.record_type != "all":
        conditions.append(m.CarbonVerificationFinding.record_type == query.record_type)
    return conditions


def _finding_payload(row: m.CarbonVerificationFinding) -> dict[str, Any]:
    return {
        "id": row.id,
        "finding_no": row.finding_no,
        "project_id": row.project_id,
        "issue_type": row.issue_type,
        "finding_type": row.finding_type,
        "severity": row.severity,
        "title": row.title,
        "description": row.description,
        "action_required": row.action_required,
        "record_type": row.record_type,
        "record_id": row.record_id,
        "record_code": row.record_code,
        "scope": row.scope,
        "display_name": row.display_name,
        "period": row.period,
        "status": row.status,
        "owner": row.owner,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "correction_comment": row.correction_comment,
        "correction_evidence": row.correction_evidence,
        "reviewer": row.reviewer,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "source_name": row.source_name,
        "standard_code": row.standard_code,
        "source_payload": cast("dict[str, Any] | None", cast("Any", row).source_payload),
        "remark": row.remark,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _count_by(rows: Sequence[m.CarbonVerificationFinding], attr: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        value = str(getattr(row, attr, None) or "unknown")
        result[value] = result.get(value, 0) + 1
    return result


def _overdue_count(rows: Sequence[m.CarbonVerificationFinding]) -> int:
    today = datetime.datetime.now(UTC).date()
    return sum(1 for row in rows if row.due_date is not None and row.due_date < today and row.status != "closed")


def _filters(query: FindingQuery) -> dict[str, Any]:
    return {
        "status": query.status,
        "project_id": query.project_id,
        "severity": query.severity,
        "record_type": query.record_type,
        "limit": query.limit,
        "offset": query.offset,
    }


def _limit(value: int) -> int:
    return max(1, min(int(value or 100), 500))
