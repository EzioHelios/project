"""Shared, tenant-aware result slicing for organization GHG analytics."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import Select, func, literal, or_, select

from app.domain.carbon.models import MonitorEquipment, MonitorSector
from app.domain.ghg_inventory.models import (
    GhgActivityAllocation,
    GhgActivityRecord,
    GhgCalculationMethodDefinition,
    GhgCalculationResult,
    GhgCalculationRun,
    GhgEmissionSource,
)

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class GhgAnalyticsFilter:
    """Canonical filter shared by overview, results, trend, flow and export."""

    run_code: str | None = None
    scope2_method: str = "location"
    date_from: date | None = None
    date_to: date | None = None
    ghg_scope: str | None = None
    iso_category_code: str | None = None
    source_code: str | None = None
    source_mechanism: str | None = None
    area_id: int | None = None
    include_descendants: bool = True
    equipment_id: int | None = None
    quality_status: str | None = None
    keyword: str | None = None
    sort_by: str = "period_start"
    sort_order: str = "desc"

    def without_run(self) -> GhgAnalyticsFilter:
        return replace(self, run_code=None)


@dataclass(frozen=True, slots=True)
class GhgAttributedResultRow:
    result: GhgCalculationResult
    activity: GhgActivityRecord
    method: GhgCalculationMethodDefinition
    source: GhgEmissionSource | None
    attribution_ratio: Decimal

    @property
    def attributed_co2e_kg(self) -> Decimal:
        return self.result.co2e_kg * self.attribution_ratio


@dataclass(frozen=True, slots=True)
class GhgResultSlice:
    run: GhgCalculationRun
    rows: list[GhgAttributedResultRow]
    total: int


class GhgResultSliceQuery:
    """Build one consistent SQL result slice without duplicating allocation joins."""

    _SORT_COLUMNS: dict[str, Any] = {
        "period_start": GhgActivityRecord.period_start,
        "activity_name": GhgActivityRecord.activity_name,
        "co2e_kg": GhgCalculationResult.co2e_kg,
        "quality_status": GhgCalculationResult.quality_status,
    }

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        query: GhgAnalyticsFilter,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> GhgResultSlice:
        self._validate(query)
        run = await self.resolve_run(query.run_code)
        ratio = await self._attribution_ratio(query)
        stmt = self._base_statement(run.id, query, ratio)
        total = int(await self._session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
        sort_column = self._SORT_COLUMNS.get(query.sort_by, GhgActivityRecord.period_start)
        order = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()
        stmt = stmt.order_by(order, GhgActivityRecord.record_code, GhgCalculationResult.id)
        if limit is not None:
            stmt = stmt.limit(limit).offset(max(offset, 0))
        raw_rows = (await self._session.execute(stmt)).all()
        rows = [
            GhgAttributedResultRow(
                result=cast("GhgCalculationResult", row[0]),
                activity=cast("GhgActivityRecord", row[1]),
                method=cast("GhgCalculationMethodDefinition", row[2]),
                source=cast("GhgEmissionSource | None", row[3]),
                attribution_ratio=Decimal(str(row[4] or 0)),
            )
            for row in raw_rows
        ]
        return GhgResultSlice(run=run, rows=rows, total=total)

    async def resolve_run(self, run_code: str | None) -> GhgCalculationRun:
        stmt = select(GhgCalculationRun)
        if run_code:
            stmt = stmt.where(GhgCalculationRun.run_code == run_code)
        else:
            stmt = stmt.where(GhgCalculationRun.status == "completed").order_by(
                GhgCalculationRun.completed_at.desc(), GhgCalculationRun.id.desc()
            )
        run = await self._session.scalar(stmt.limit(1))
        if run is None:
            msg = "没有可用的组织温室气体核算运行"
            raise ValueError(msg)
        return run

    def _base_statement(self, run_id: int, query: GhgAnalyticsFilter, ratio: Any) -> Select[Any]:
        conditions: list[Any] = [
            GhgCalculationResult.run_id == run_id,
            or_(
                GhgCalculationResult.ghg_scope != "scope2",
                GhgCalculationResult.scope2_method == query.scope2_method,
            ),
        ]
        if query.date_from is not None:
            conditions.append(GhgActivityRecord.period_start >= query.date_from)
        if query.date_to is not None:
            conditions.append(GhgActivityRecord.period_end <= query.date_to)
        if query.ghg_scope:
            conditions.append(GhgCalculationResult.ghg_scope == query.ghg_scope)
        if query.iso_category_code:
            # The six ISO 14064-1 categories are represented by their leading
            # digit ("1" … "6"), while detailed categories use codes such as
            # "1.1".  A top-level drilldown must therefore include every
            # detailed category below it; leaf selections remain exact.
            if "." in query.iso_category_code:
                conditions.append(GhgCalculationResult.iso_category_code == query.iso_category_code)
            else:
                conditions.append(GhgCalculationResult.iso_category_code.like(f"{query.iso_category_code}.%"))
        if query.source_code:
            conditions.append(GhgActivityRecord.source_code == query.source_code)
        if query.source_mechanism:
            conditions.append(GhgActivityRecord.source_mechanism == query.source_mechanism)
        if query.quality_status:
            conditions.append(GhgCalculationResult.quality_status == query.quality_status)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append(
                or_(
                    GhgActivityRecord.record_code.ilike(pattern),
                    GhgActivityRecord.activity_name.ilike(pattern),
                    GhgActivityRecord.source_code.ilike(pattern),
                    GhgEmissionSource.source_name.ilike(pattern),
                )
            )
        if query.area_id is not None or query.equipment_id is not None:
            conditions.append(ratio > 0)
        return (
            select(
                GhgCalculationResult,
                GhgActivityRecord,
                GhgCalculationMethodDefinition,
                GhgEmissionSource,
                ratio.label("attribution_ratio"),
            )
            .join(GhgActivityRecord, GhgActivityRecord.id == GhgCalculationResult.activity_id)
            .join(GhgCalculationMethodDefinition, GhgCalculationMethodDefinition.id == GhgCalculationResult.method_id)
            .outerjoin(GhgEmissionSource, GhgEmissionSource.id == GhgActivityRecord.emission_source_id)
            .where(*conditions)
        )

    async def _attribution_ratio(self, query: GhgAnalyticsFilter) -> Any:
        if query.area_id is None and query.equipment_id is None:
            return literal(Decimal(1))
        area_ids: set[int] | None = None
        if query.area_id is not None:
            area_ids = await self.area_ids(query.area_id, include_descendants=query.include_descendants)
        if query.equipment_id is not None:
            equipment = await self._session.get(MonitorEquipment, query.equipment_id)
            if equipment is None:
                msg = "设备不存在"
                raise ValueError(msg)
            if area_ids is not None and equipment.sector_id not in area_ids:
                msg = "设备不属于所选区域或其子区域"
                raise ValueError(msg)
        allocation_filters: list[Any] = [GhgActivityAllocation.status == "active"]
        if area_ids is not None:
            allocation_filters.append(GhgActivityAllocation.area_id.in_(area_ids))
        if query.equipment_id is not None:
            allocation_filters.append(GhgActivityAllocation.equipment_id == query.equipment_id)
        ratio_sq = (
            select(
                GhgActivityAllocation.activity_id.label("activity_id"),
                func.sum(GhgActivityAllocation.allocation_ratio).label("ratio"),
            )
            .where(*allocation_filters)
            .group_by(GhgActivityAllocation.activity_id)
            .subquery()
        )
        return func.coalesce(
            select(ratio_sq.c.ratio)
            .where(ratio_sq.c.activity_id == GhgCalculationResult.activity_id)
            .scalar_subquery(),
            Decimal(0),
        )

    async def area_ids(self, area_id: int, *, include_descendants: bool = True) -> set[int]:
        root = await self._session.get(MonitorSector, area_id)
        if root is None:
            msg = "区域不存在"
            raise ValueError(msg)
        if not include_descendants:
            return {area_id}
        rows = list((await self._session.execute(select(MonitorSector.id, MonitorSector.parent_id))).all())
        children: dict[int, list[int]] = {}
        for item_id, parent_id in rows:
            if parent_id is not None:
                children.setdefault(parent_id, []).append(item_id)
        output = {area_id}
        pending = [area_id]
        while pending:
            current = pending.pop()
            for child in children.get(current, []):
                if child not in output:
                    output.add(child)
                    pending.append(child)
        return output

    @staticmethod
    def _validate(query: GhgAnalyticsFilter) -> None:
        if query.scope2_method not in {"location", "market"}:
            msg = "Scope 2口径只能选择地点法或市场法"
            raise ValueError(msg)
        if query.date_from and query.date_to and query.date_from > query.date_to:
            msg = "开始日期不能晚于结束日期"
            raise ValueError(msg)
        if query.sort_order not in {"asc", "desc"}:
            msg = "排序方向只能为asc或desc"
            raise ValueError(msg)
