from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class SupplyChainCarbonQuery:
    supplier_id: int | None = None
    task_id: int | None = None
    status: str | None = None
    task_type: str | None = None
    data_type: str | None = None
    keyword: str | None = None
    limit: int = 50
    offset: int = 0


class SupplyChainCarbonQueryService:
    """Read models for supply-chain carbon workflows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def suppliers(self, query: SupplyChainCarbonQuery) -> dict[str, Any]:
        conditions = []
        if query.status and query.status != "all":
            conditions.append(m.SupplyChainSupplier.status == query.status)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append((m.SupplyChainSupplier.name.ilike(pattern)) | (m.SupplyChainSupplier.supplier_code.ilike(pattern)))
        stmt = select(m.SupplyChainSupplier).where(*conditions).order_by(m.SupplyChainSupplier.id.desc())
        page = await self._page(stmt, query, include_rows=True)
        page["items"] = [await self._supplier_payload(row) for row in page.pop("_rows")]
        page["data"] = page["items"]
        return page

    async def sites(self, query: SupplyChainCarbonQuery) -> dict[str, Any]:
        conditions = []
        if query.supplier_id is not None:
            conditions.append(m.SupplierSite.supplier_id == query.supplier_id)
        if query.status and query.status != "all":
            conditions.append(m.SupplierSite.status == query.status)
        stmt = select(m.SupplierSite).where(*conditions).order_by(m.SupplierSite.id.desc())
        return await self._page(stmt, query)

    async def tasks(self, query: SupplyChainCarbonQuery) -> dict[str, Any]:
        conditions = []
        if query.supplier_id is not None:
            conditions.append(m.SupplierDisclosureTask.supplier_id == query.supplier_id)
        if query.status and query.status != "all":
            conditions.append(m.SupplierDisclosureTask.status == query.status)
        if query.task_type and query.task_type != "all":
            conditions.append(m.SupplierDisclosureTask.task_type == query.task_type)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append((m.SupplierDisclosureTask.task_name.ilike(pattern)) | (m.SupplierDisclosureTask.task_no.ilike(pattern)))
        stmt = select(m.SupplierDisclosureTask).where(*conditions).order_by(m.SupplierDisclosureTask.id.desc())
        page = await self._page(stmt, query, include_rows=True)
        page["items"] = [await self._task_payload(row) for row in page.pop("_rows")]
        page["data"] = page["items"]
        return page

    async def data_items(self, query: SupplyChainCarbonQuery) -> dict[str, Any]:
        conditions = []
        if query.task_id is not None:
            conditions.append(m.SupplierCarbonData.task_id == query.task_id)
        if query.supplier_id is not None:
            conditions.append(m.SupplierCarbonData.supplier_id == query.supplier_id)
        if query.data_type and query.data_type != "all":
            conditions.append(m.SupplierCarbonData.data_type == query.data_type)
        if query.status and query.status != "all":
            conditions.append(m.SupplierCarbonData.status == query.status)
        stmt = select(m.SupplierCarbonData).where(*conditions).order_by(m.SupplierCarbonData.id.desc())
        return await self._page(stmt, query)

    async def evidence_items(self, query: SupplyChainCarbonQuery) -> dict[str, Any]:
        conditions = []
        if query.task_id is not None:
            conditions.append(m.SupplierEvidence.task_id == query.task_id)
        if query.status and query.status != "all":
            conditions.append(m.SupplierEvidence.review_status == query.status)
        stmt = select(m.SupplierEvidence).where(*conditions).order_by(m.SupplierEvidence.id.desc())
        return await self._page(stmt, query)

    async def review_decisions(self, query: SupplyChainCarbonQuery) -> dict[str, Any]:
        conditions = []
        if query.task_id is not None:
            conditions.append(m.SupplierReviewDecision.task_id == query.task_id)
        stmt = select(m.SupplierReviewDecision).where(*conditions).order_by(m.SupplierReviewDecision.id.desc())
        return await self._page(stmt, query)

    async def releases(self, query: SupplyChainCarbonQuery) -> dict[str, Any]:
        conditions = []
        if query.task_id is not None:
            conditions.append(m.SupplierDisclosureRelease.task_id == query.task_id)
        if query.status and query.status != "all":
            conditions.append(m.SupplierDisclosureRelease.status == query.status)
        stmt = select(m.SupplierDisclosureRelease).where(*conditions).order_by(m.SupplierDisclosureRelease.id.desc())
        return await self._page(stmt, query)

    async def summary(self) -> dict[str, Any]:
        supplier_count = await self._count(m.SupplyChainSupplier)
        task_count = await self._count(m.SupplierDisclosureTask)
        submitted_count = await self._count(m.SupplierDisclosureTask, m.SupplierDisclosureTask.status == "submitted")
        approved_count = await self._count(m.SupplierDisclosureTask, m.SupplierDisclosureTask.status == "approved")
        high_risk_count = await self._count(m.SupplyChainSupplier, m.SupplyChainSupplier.risk_level == "high")
        return {
            "supplier_count": supplier_count,
            "task_count": task_count,
            "submitted_task_count": submitted_count,
            "approved_task_count": approved_count,
            "high_risk_supplier_count": high_risk_count,
        }

    async def analysis(self) -> dict[str, Any]:
        supplier_rows = (
            await self._session.execute(
                select(
                    m.SupplierCarbonData.supplier_id,
                    m.SupplyChainSupplier.name,
                    m.SupplyChainSupplier.risk_level,
                    func.count(m.SupplierCarbonData.id),
                    func.coalesce(func.sum(m.SupplierCarbonData.co2e_amount), 0),
                    func.coalesce(func.sum(m.SupplierCarbonData.pcf_value), 0),
                )
                .join(m.SupplyChainSupplier, m.SupplyChainSupplier.id == m.SupplierCarbonData.supplier_id)
                .where(m.SupplierCarbonData.status == "approved")
                .group_by(m.SupplierCarbonData.supplier_id, m.SupplyChainSupplier.name, m.SupplyChainSupplier.risk_level)
                .order_by(func.coalesce(func.sum(m.SupplierCarbonData.co2e_amount), 0).desc())
                .limit(20)
            )
        ).all()
        category_rows = (
            await self._session.execute(
                select(
                    m.SupplierCarbonData.scope_category,
                    func.count(m.SupplierCarbonData.id),
                    func.coalesce(func.sum(m.SupplierCarbonData.co2e_amount), 0),
                    func.coalesce(func.sum(m.SupplierCarbonData.pcf_value), 0),
                )
                .where(m.SupplierCarbonData.status == "approved")
                .group_by(m.SupplierCarbonData.scope_category)
                .order_by(func.coalesce(func.sum(m.SupplierCarbonData.co2e_amount), 0).desc())
                .limit(20)
            )
        ).all()
        supplier_ranking = [
            {
                "supplier_id": row[0],
                "supplier_name": row[1],
                "risk_level": row[2],
                "data_count": int(row[3] or 0),
                "co2e_amount": float(row[4] or 0),
                "pcf_value_sum": float(row[5] or 0),
            }
            for row in supplier_rows
        ]
        high_carbon_categories = [
            {
                "scope_category": row[0] or "uncategorized",
                "data_count": int(row[1] or 0),
                "co2e_amount": float(row[2] or 0),
                "pcf_value_sum": float(row[3] or 0),
            }
            for row in category_rows
        ]
        recommendations = _recommendations(supplier_ranking, high_carbon_categories)
        return {
            "supplier_ranking": supplier_ranking,
            "high_carbon_categories": high_carbon_categories,
            "recommendations": recommendations,
        }

    async def _supplier_payload(self, row: m.SupplyChainSupplier) -> dict[str, Any]:
        payload = model_to_dict(row)
        payload["task_count"] = await self._count(m.SupplierDisclosureTask, m.SupplierDisclosureTask.supplier_id == row.id)
        payload["approved_task_count"] = await self._count(
            m.SupplierDisclosureTask,
            m.SupplierDisclosureTask.supplier_id == row.id,
            m.SupplierDisclosureTask.status == "approved",
        )
        return payload

    async def _task_payload(self, row: m.SupplierDisclosureTask) -> dict[str, Any]:
        payload = model_to_dict(row)
        supplier = await self._session.get(m.SupplyChainSupplier, row.supplier_id)
        payload["supplier_name"] = supplier.name if supplier else None
        payload["data_count"] = await self._count(m.SupplierCarbonData, m.SupplierCarbonData.task_id == row.id)
        payload["evidence_count"] = await self._count(m.SupplierEvidence, m.SupplierEvidence.task_id == row.id)
        return payload

    async def _page(self, stmt: Any, query: SupplyChainCarbonQuery, *, include_rows: bool = False) -> dict[str, Any]:
        total = int((await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await self._session.execute(stmt.limit(_limit(query.limit)).offset(max(0, query.offset)))).scalars().all()
        items = [model_to_dict(row) for row in rows]
        page = {"items": items, "data": items, "total": total, "limit": _limit(query.limit), "offset": max(0, query.offset)}
        if include_rows:
            page["_rows"] = rows
        return page

    async def _count(self, model: type[Any], *conditions: Any) -> int:
        return int((await self._session.execute(select(func.count()).select_from(model).where(*conditions))).scalar_one() or 0)


def _limit(value: int) -> int:
    return max(1, min(int(value or 50), 200))


def _recommendations(suppliers: list[dict[str, Any]], categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = [
        {
            "target_type": "supplier",
            "target_name": supplier["supplier_name"],
            "priority": "high" if supplier["risk_level"] == "high" else "medium",
            "action": "复核供应商数据质量并要求补充低碳替代方案",
        }
        for supplier in suppliers[:3]
        if supplier["risk_level"] == "high" or supplier["co2e_amount"] > 0
    ]
    items.extend(
        [
            {
                "target_type": "category",
                "target_name": category["scope_category"],
                "priority": "medium",
                "action": "优先核对高碳品类的采购量、运输方式和供应商 PCF 边界",
            }
            for category in categories[:3]
        ]
    )
    return items
