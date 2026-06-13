from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import case, func, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class InventoryQuery:
    batch_id: int | None = None
    boundary_id: int | None = None
    reporting_org_id: int | None = None
    period_id: int | None = None
    scope: str | None = None
    status: str | None = None
    quality_status: str | None = None
    limit: int = 50
    offset: int = 0


class CarbonAccountingInventoryQueryService:
    """Read models for accounting batches and emission inventories."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def batches(self, query: InventoryQuery) -> dict[str, Any]:
        conditions = []
        if query.boundary_id is not None:
            conditions.append(m.CarbonAccountingBatch.boundary_id == query.boundary_id)
        if query.reporting_org_id is not None:
            conditions.append(m.CarbonAccountingBatch.reporting_org_id == query.reporting_org_id)
        if query.period_id is not None:
            conditions.append(m.CarbonAccountingBatch.period_id == query.period_id)
        if query.status and query.status != "all":
            conditions.append(m.CarbonAccountingBatch.status == query.status)
        stmt = select(m.CarbonAccountingBatch).where(*conditions).order_by(m.CarbonAccountingBatch.id.desc())
        page = await self._page(stmt, query, include_rows=True)
        rows = page.pop("_rows")
        page["items"] = [self._batch_payload(row) for row in rows]
        page["data"] = page["items"]
        return page

    async def inventory_items(self, query: InventoryQuery) -> dict[str, Any]:
        conditions = []
        if query.batch_id is not None:
            conditions.append(m.CarbonEmissionInventoryItem.batch_id == query.batch_id)
        if query.scope and query.scope != "all":
            conditions.append(m.CarbonEmissionInventoryItem.scope == query.scope)
        if query.quality_status and query.quality_status != "all":
            conditions.append(m.CarbonEmissionInventoryItem.quality_status == query.quality_status)
        stmt = select(m.CarbonEmissionInventoryItem).where(*conditions).order_by(m.CarbonEmissionInventoryItem.scope.asc(), m.CarbonEmissionInventoryItem.id.asc())
        return await self._page(stmt, query)

    async def inventory_summary(self, batch_id: int) -> dict[str, Any]:
        batch = await self._session.get(m.CarbonAccountingBatch, batch_id)
        if batch is None:
            msg = "核算批次不存在"
            raise ValueError(msg)
        scope_rows = (
            await self._session.execute(
                select(
                    m.CarbonEmissionInventoryItem.scope,
                    func.count(m.CarbonEmissionInventoryItem.id),
                    func.sum(case((m.CarbonEmissionInventoryItem.included.is_(True), m.CarbonEmissionInventoryItem.computed_co2e), else_=0)),
                    func.sum(case((m.CarbonEmissionInventoryItem.included.is_(True), 1), else_=0)),
                )
                .where(m.CarbonEmissionInventoryItem.batch_id == batch.id)
                .group_by(m.CarbonEmissionInventoryItem.scope)
                .order_by(m.CarbonEmissionInventoryItem.scope.asc())
            )
        ).all()
        quality_rows = (
            await self._session.execute(
                select(m.CarbonEmissionInventoryItem.quality_status, func.count(m.CarbonEmissionInventoryItem.id))
                .where(m.CarbonEmissionInventoryItem.batch_id == batch.id)
                .group_by(m.CarbonEmissionInventoryItem.quality_status)
            )
        ).all()
        return {
            "batch": self._batch_payload(batch),
            "totals": {
                "total_kg_co2e": _float(batch.total_co2e),
                "total_t_co2e": _float((batch.total_co2e or Decimal(0)) / Decimal(1000)),
                "record_count": batch.record_count,
                "included_record_count": batch.included_record_count,
                "missing_result_count": batch.missing_result_count,
            },
            "scope_summary": [
                {
                    "scope": scope,
                    "record_count": int(count or 0),
                    "included_record_count": int(included or 0),
                    "kg_co2e": _float(total),
                    "t_co2e": _float((total or Decimal(0)) / Decimal(1000)),
                }
                for scope, count, total, included in scope_rows
            ],
            "quality_summary": {str(status): int(count or 0) for status, count in quality_rows},
        }

    async def _page(self, stmt: Any, query: InventoryQuery, *, include_rows: bool = False) -> dict[str, Any]:
        limit = _limit(query.limit)
        offset = max(0, query.offset)
        total = int((await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await self._session.execute(stmt.limit(limit).offset(offset))).scalars().all()
        items = [model_to_dict(row) for row in rows]
        page = {"items": items, "data": items, "total": total, "limit": limit, "offset": offset}
        if include_rows:
            page["_rows"] = rows
        return page

    def _batch_payload(self, row: m.CarbonAccountingBatch) -> dict[str, Any]:
        payload = model_to_dict(row)
        payload["organization_name"] = row.organization.name if row.organization else None
        payload["period_name"] = row.period.name if row.period else None
        payload["period_start"] = row.period.period_start.isoformat() if row.period else None
        payload["period_end"] = row.period.period_end.isoformat() if row.period else None
        payload["boundary_no"] = row.boundary.boundary_no if row.boundary else None
        payload["boundary_name"] = row.boundary.boundary_name if row.boundary else None
        return payload


def _limit(value: int) -> int:
    return max(1, min(int(value or 50), 200))


def _float(value: Decimal | float | None) -> float:
    if value is None:
        return 0.0
    return float(value)
