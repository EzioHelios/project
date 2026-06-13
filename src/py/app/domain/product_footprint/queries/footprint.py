from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ProductFootprintQuery:
    study_id: int | None = None
    status: str | None = None
    result_status: str | None = None
    product_code: str | None = None
    keyword: str | None = None
    limit: int = 50
    offset: int = 0


class ProductFootprintQueryService:
    """Read models for product carbon footprint workflows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def studies(self, query: ProductFootprintQuery) -> dict[str, Any]:
        conditions = []
        if query.status and query.status != "all":
            conditions.append(m.ProductFootprintStudy.status == query.status)
        if query.result_status and query.result_status != "all":
            conditions.append(m.ProductFootprintStudy.result_status == query.result_status)
        if query.product_code:
            conditions.append(m.ProductFootprintStudy.product_code == query.product_code)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append(
                (m.ProductFootprintStudy.study_code.ilike(pattern))
                | (m.ProductFootprintStudy.study_name.ilike(pattern))
                | (m.ProductFootprintStudy.product_name.ilike(pattern))
            )
        stmt = select(m.ProductFootprintStudy).where(*conditions).order_by(m.ProductFootprintStudy.id.desc())
        page = await self._page(stmt, query, include_rows=True)
        page["items"] = [await self._study_payload(row) for row in page.pop("_rows")]
        page["data"] = page["items"]
        return page

    async def boundary(self, study_id: int) -> dict[str, Any] | None:
        obj = await self._session.scalar(select(m.ProductSystemBoundary).where(m.ProductSystemBoundary.study_id == study_id))
        return model_to_dict(obj) if obj else None

    async def stages(self, query: ProductFootprintQuery) -> dict[str, Any]:
        conditions = []
        if query.study_id is not None:
            conditions.append(m.ProductLifeCycleStage.study_id == query.study_id)
        stmt = select(m.ProductLifeCycleStage).where(*conditions).order_by(m.ProductLifeCycleStage.sequence, m.ProductLifeCycleStage.id)
        return await self._page(stmt, query)

    async def inventory_items(self, query: ProductFootprintQuery) -> dict[str, Any]:
        conditions = []
        if query.study_id is not None:
            conditions.append(m.ProductFootprintInventoryItem.study_id == query.study_id)
        stmt = (
            select(m.ProductFootprintInventoryItem)
            .where(*conditions)
            .order_by(m.ProductFootprintInventoryItem.id.desc())
        )
        page = await self._page(stmt, query, include_rows=True)
        page["items"] = [await self._item_payload(row) for row in page.pop("_rows")]
        page["data"] = page["items"]
        return page

    async def allocation_rules(self, query: ProductFootprintQuery) -> dict[str, Any]:
        conditions = []
        if query.study_id is not None:
            conditions.append(m.ProductFootprintAllocationRule.study_id == query.study_id)
        stmt = (
            select(m.ProductFootprintAllocationRule)
            .where(*conditions)
            .order_by(m.ProductFootprintAllocationRule.id.desc())
        )
        return await self._page(stmt, query)

    async def results(self, query: ProductFootprintQuery) -> dict[str, Any]:
        conditions = []
        if query.study_id is not None:
            conditions.append(m.ProductFootprintResult.study_id == query.study_id)
        if query.result_status and query.result_status != "all":
            conditions.append(m.ProductFootprintResult.result_status == query.result_status)
        stmt = (
            select(m.ProductFootprintResult)
            .where(*conditions)
            .order_by(m.ProductFootprintResult.result_version.desc(), m.ProductFootprintResult.id.desc())
        )
        return await self._page(stmt, query)

    async def report(self, study_id: int) -> dict[str, Any]:
        study = await self._session.get(m.ProductFootprintStudy, study_id)
        if study is None:
            return {}
        latest_result = await self._session.scalar(
            select(m.ProductFootprintResult)
            .where(m.ProductFootprintResult.study_id == study_id)
            .order_by(m.ProductFootprintResult.result_version.desc())
            .limit(1)
        )
        items = (
            await self._session.execute(
                select(m.ProductFootprintInventoryItem)
                .where(m.ProductFootprintInventoryItem.study_id == study_id)
                .order_by(m.ProductFootprintInventoryItem.id)
            )
        ).scalars().all()
        return {
            "study": await self._study_payload(study),
            "boundary": await self.boundary(study_id),
            "stages": (await self.stages(ProductFootprintQuery(study_id=study_id, limit=200)))["items"],
            "inventory_items": [await self._item_payload(item) for item in items],
            "allocation_rules": (await self.allocation_rules(ProductFootprintQuery(study_id=study_id, limit=200)))["items"],
            "latest_result": model_to_dict(latest_result) if latest_result else None,
            "stage_summary": latest_result.stage_payload if latest_result else [],
            "quality_summary": _quality_summary(items),
        }

    async def summary(self) -> dict[str, Any]:
        study_count = await self._count(m.ProductFootprintStudy)
        calculated_count = await self._count(m.ProductFootprintStudy, m.ProductFootprintStudy.result_status == "calculated")
        incomplete_count = await self._count(m.ProductFootprintStudy, m.ProductFootprintStudy.result_status == "incomplete_inventory")
        item_count = await self._count(m.ProductFootprintInventoryItem)
        latest = await self._session.scalar(select(m.ProductFootprintStudy).order_by(m.ProductFootprintStudy.id.desc()).limit(1))
        return {
            "study_count": study_count,
            "calculated_count": calculated_count,
            "incomplete_count": incomplete_count,
            "inventory_item_count": item_count,
            "latest_study": await self._study_payload(latest) if latest else None,
        }

    async def _page(self, stmt: Any, query: ProductFootprintQuery, *, include_rows: bool = False) -> dict[str, Any]:
        total = int((await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await self._session.execute(stmt.limit(_limit(query.limit)).offset(max(0, query.offset)))).scalars().all()
        items = [model_to_dict(row) for row in rows]
        page = {"items": items, "data": items, "total": total, "limit": _limit(query.limit), "offset": max(0, query.offset)}
        if include_rows:
            page["_rows"] = rows
        return page

    async def _study_payload(self, row: m.ProductFootprintStudy | None) -> dict[str, Any]:
        if row is None:
            return {}
        payload = model_to_dict(row)
        payload["inventory_count"] = await self._count(m.ProductFootprintInventoryItem, m.ProductFootprintInventoryItem.study_id == row.id)
        payload["result_count"] = await self._count(m.ProductFootprintResult, m.ProductFootprintResult.study_id == row.id)
        latest = await self._session.scalar(
            select(m.ProductFootprintResult)
            .where(m.ProductFootprintResult.study_id == row.id)
            .order_by(m.ProductFootprintResult.result_version.desc())
            .limit(1)
        )
        payload["latest_result"] = model_to_dict(latest) if latest else None
        return payload

    async def _item_payload(self, row: m.ProductFootprintInventoryItem) -> dict[str, Any]:
        payload = model_to_dict(row)
        if row.stage_id:
            stage = await self._session.get(m.ProductLifeCycleStage, row.stage_id)
            payload["stage_code"] = stage.stage_code if stage else None
            payload["stage_name"] = stage.stage_name if stage else None
        return payload

    async def _count(self, model: type[Any], *conditions: Any) -> int:
        return int((await self._session.execute(select(func.count()).select_from(model).where(*conditions))).scalar_one() or 0)


def _limit(value: int) -> int:
    return max(1, min(int(value or 50), 200))


def _quality_summary(items: list[m.ProductFootprintInventoryItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in items:
        key = item.calc_status or "unknown"
        summary[key] = summary.get(key, 0) + 1
    return summary
