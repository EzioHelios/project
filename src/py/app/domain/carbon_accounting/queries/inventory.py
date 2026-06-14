from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import case, func, select, text

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict
from app.lib.tenancy import TENANT_ID_SESSION_KEY

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

    async def readiness(self) -> dict[str, Any]:
        team_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        if team_id is None:
            return _empty_readiness()
        counts_row = (
            await self._session.execute(
                text(
                    """
                    select
                        (
                            select count(*)::int
                            from carbon_reporting_organization
                            where team_id = :team_id and status = 'active'
                        ) as reporting_org_count,
                        (
                            select count(*)::int
                            from carbon_reporting_period
                            where team_id = :team_id
                        ) as reporting_period_count,
                        (
                            select count(*)::int
                            from carbon_organization_boundary
                            where team_id = :team_id and status = 'published'
                        ) as published_boundary_count,
                        (
                            select count(*)::int
                            from carbon_accounting_batch
                            where team_id = :team_id
                        ) as batch_count,
                        (
                            select count(*)::int
                            from carbon_emission_inventory_item
                            where team_id = :team_id and included is true
                        ) as included_inventory_item_count,
                        (
                            select count(*)::int
                            from dataapp_scope1mobilecombustion
                            where team_id = :team_id and status = 'approved'
                        ) as scope1_mobile_count,
                        (
                            select count(*)::int
                            from dataapp_scope1stationarycombustion
                            where team_id = :team_id and status = 'approved'
                        ) as scope1_stationary_count,
                        (
                            select count(*)::int
                            from dataapp_scope1refrigerantleak
                            where team_id = :team_id and status = 'approved'
                        ) as scope1_refrigerant_count,
                        (
                            select count(*)::int
                            from dataapp_scope2electricitybill
                            where team_id = :team_id and status = 'approved'
                        ) as scope2_electricity_count,
                        (
                            select count(*)::int
                            from dataapp_scope2purchasedenergy
                            where team_id = :team_id and status = 'approved'
                        ) as scope2_purchased_energy_count,
                        (
                            select count(*)::int
                            from dataapp_scope2meteraggregate
                            where team_id = :team_id and status = 'approved'
                        ) as scope2_meter_aggregate_count,
                        (
                            select count(*)::int
                            from dataapp_scope3wastedisposal
                            where team_id = :team_id and status = 'approved'
                        ) as scope3_waste_count,
                        (
                            select count(*)::int
                            from dataapp_scope3thirdpartytransport
                            where team_id = :team_id and status = 'approved'
                        ) as scope3_transport_count
                    """
                ),
                {"team_id": str(team_id)},
            )
        ).mappings().one()
        latest_batch = (
            (
                await self._session.execute(
                    select(m.CarbonAccountingBatch)
                    .where(m.CarbonAccountingBatch.team_id == team_id)
                    .order_by(m.CarbonAccountingBatch.id.desc())
                    .limit(1)
                    .execution_options(include_all_tenants=True)
                )
            )
            .scalars()
            .first()
        )
        counts = {key: int(value or 0) for key, value in dict(counts_row).items()}
        scope1_count = counts["scope1_mobile_count"] + counts["scope1_stationary_count"] + counts["scope1_refrigerant_count"]
        scope2_count = counts["scope2_electricity_count"] + counts["scope2_purchased_energy_count"] + counts["scope2_meter_aggregate_count"]
        scope3_count = counts["scope3_waste_count"] + counts["scope3_transport_count"]
        source_record_count = scope1_count + scope2_count + scope3_count
        counts.update({"scope1_record_count": scope1_count, "scope2_record_count": scope2_count, "scope3_record_count": scope3_count, "source_record_count": source_record_count})

        missing: list[str] = []
        if source_record_count == 0:
            missing.append("scope_activity_records")
        if counts["published_boundary_count"] == 0:
            missing.append("published_boundary")
        if counts["included_inventory_item_count"] == 0:
            missing.append("included_inventory_items")

        if source_record_count == 0:
            readiness_status = "source_missing"
        elif counts["published_boundary_count"] == 0:
            readiness_status = "boundary_missing"
        elif counts["batch_count"] == 0:
            readiness_status = "batch_missing"
        elif counts["included_inventory_item_count"] == 0:
            readiness_status = "inventory_empty"
        elif latest_batch and latest_batch.missing_result_count > 0:
            readiness_status = "partial"
        else:
            readiness_status = "ready"

        return {
            "status": readiness_status,
            "counts": counts,
            "missing": missing,
            "latest_batch": self._batch_payload(latest_batch) if latest_batch else None,
            "items": [
                {
                    "key": "published_boundary",
                    "label": "已发布组织边界",
                    "count": counts["published_boundary_count"],
                    "status": "ready" if counts["published_boundary_count"] > 0 else "source_missing",
                },
                {
                    "key": "scope1_activity_records",
                    "label": "Scope1 已审核记录",
                    "count": scope1_count,
                    "status": "ready" if scope1_count > 0 else "source_missing",
                },
                {
                    "key": "scope2_activity_records",
                    "label": "Scope2 已审核记录",
                    "count": scope2_count,
                    "status": "ready" if scope2_count > 0 else "source_missing",
                },
                {
                    "key": "scope3_activity_records",
                    "label": "Scope3 已审核记录",
                    "count": scope3_count,
                    "status": "ready" if scope3_count > 0 else "source_missing",
                },
                {
                    "key": "included_inventory_items",
                    "label": "已纳入清单记录",
                    "count": counts["included_inventory_item_count"],
                    "status": "ready" if counts["included_inventory_item_count"] > 0 else "source_missing",
                },
            ],
        }

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
        tenant_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        execution_options: dict[str, bool] = {}
        if tenant_id is not None:
            conditions.append(m.CarbonEmissionInventoryItem.team_id == tenant_id)
            execution_options["include_all_tenants"] = True
        if query.batch_id is not None:
            conditions.append(m.CarbonEmissionInventoryItem.batch_id == query.batch_id)
        if query.scope and query.scope != "all":
            conditions.append(m.CarbonEmissionInventoryItem.scope == query.scope)
        if query.quality_status and query.quality_status != "all":
            conditions.append(m.CarbonEmissionInventoryItem.quality_status == query.quality_status)
        stmt = select(m.CarbonEmissionInventoryItem).where(*conditions).order_by(m.CarbonEmissionInventoryItem.scope.asc(), m.CarbonEmissionInventoryItem.id.asc())
        count_stmt = select(func.count(m.CarbonEmissionInventoryItem.id)).where(*conditions)
        if execution_options:
            stmt = stmt.execution_options(**execution_options)
            count_stmt = count_stmt.execution_options(**execution_options)
        return await self._page(stmt, query, count_stmt=count_stmt)

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

    async def revision_diff(self, batch_id: int) -> dict[str, Any]:
        batch = await self._session.get(m.CarbonAccountingBatch, batch_id)
        if batch is None:
            msg = "核算批次不存在"
            raise ValueError(msg)
        if batch.parent_batch_id is None:
            msg = "当前批次不是修订批次"
            raise ValueError(msg)
        parent = await self._session.get(m.CarbonAccountingBatch, batch.parent_batch_id)
        if parent is None:
            msg = "来源批次不存在"
            raise ValueError(msg)
        parent_items = await self._batch_items(parent.id)
        current_items = await self._batch_items(batch.id)
        status = _revision_diff_status(parent_items=parent_items, current_items=current_items, batch=batch)
        changes = _revision_changes(parent_items, current_items) if status == "ready" else []
        parent_scopes = _scope_totals(parent_items)
        current_scopes = _scope_totals(current_items)
        scope_keys = sorted(set(parent_scopes) | set(current_scopes))
        return {
            "status": status,
            "batch": self._batch_payload(batch),
            "parent_batch": self._batch_payload(parent),
            "totals": {
                "parent_kg_co2e": _float(parent.total_co2e),
                "current_kg_co2e": _float(batch.total_co2e),
                "delta_kg_co2e": _float((batch.total_co2e or Decimal(0)) - (parent.total_co2e or Decimal(0))),
                "parent_t_co2e": _float((parent.total_co2e or Decimal(0)) / Decimal(1000)),
                "current_t_co2e": _float((batch.total_co2e or Decimal(0)) / Decimal(1000)),
                "delta_t_co2e": _float(((batch.total_co2e or Decimal(0)) - (parent.total_co2e or Decimal(0))) / Decimal(1000)),
                "added_count": sum(1 for item in changes if item["change_type"] == "added"),
                "removed_count": sum(1 for item in changes if item["change_type"] == "removed"),
                "changed_count": sum(1 for item in changes if item["change_type"] == "changed"),
                "change_count": len(changes),
            },
            "scope_deltas": [_scope_delta(scope, parent_scopes.get(scope), current_scopes.get(scope)) for scope in scope_keys],
            "changes": changes[:200],
        }

    async def _batch_items(self, batch_id: int) -> list[m.CarbonEmissionInventoryItem]:
        return (
            (
                await self._session.execute(
                    select(m.CarbonEmissionInventoryItem)
                    .where(m.CarbonEmissionInventoryItem.batch_id == batch_id)
                    .order_by(m.CarbonEmissionInventoryItem.scope.asc(), m.CarbonEmissionInventoryItem.id.asc())
                )
            )
            .scalars()
            .all()
        )

    async def _page(self, stmt: Any, query: InventoryQuery, *, include_rows: bool = False, count_stmt: Any | None = None) -> dict[str, Any]:
        limit = _limit(query.limit)
        offset = max(0, query.offset)
        total_statement = count_stmt if count_stmt is not None else select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(total_statement)).scalar_one() or 0)
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
        payload["is_revision"] = row.parent_batch_id is not None or row.revision_no > 1
        payload["parent_batch_no"] = row.parent_batch.batch_no if row.parent_batch else None
        payload["parent_batch_name"] = row.parent_batch.batch_name if row.parent_batch else None
        return payload


def _limit(value: int) -> int:
    return max(1, min(int(value or 50), 200))


def _float(value: Decimal | float | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _empty_readiness() -> dict[str, Any]:
    counts = {
        "reporting_org_count": 0,
        "reporting_period_count": 0,
        "published_boundary_count": 0,
        "batch_count": 0,
        "included_inventory_item_count": 0,
        "scope1_mobile_count": 0,
        "scope1_stationary_count": 0,
        "scope1_refrigerant_count": 0,
        "scope2_electricity_count": 0,
        "scope2_purchased_energy_count": 0,
        "scope2_meter_aggregate_count": 0,
        "scope3_waste_count": 0,
        "scope3_transport_count": 0,
        "scope1_record_count": 0,
        "scope2_record_count": 0,
        "scope3_record_count": 0,
        "source_record_count": 0,
    }
    return {
        "status": "source_missing",
        "counts": counts,
        "missing": ["scope_activity_records", "published_boundary", "included_inventory_items"],
        "latest_batch": None,
        "items": [
            {"key": "published_boundary", "label": "已发布组织边界", "count": 0, "status": "source_missing"},
            {"key": "scope1_activity_records", "label": "Scope1 已审核记录", "count": 0, "status": "source_missing"},
            {"key": "scope2_activity_records", "label": "Scope2 已审核记录", "count": 0, "status": "source_missing"},
            {"key": "scope3_activity_records", "label": "Scope3 已审核记录", "count": 0, "status": "source_missing"},
            {"key": "included_inventory_items", "label": "已纳入清单记录", "count": 0, "status": "source_missing"},
        ],
    }


def _revision_diff_status(
    *,
    parent_items: list[m.CarbonEmissionInventoryItem],
    current_items: list[m.CarbonEmissionInventoryItem],
    batch: m.CarbonAccountingBatch,
) -> str:
    if not parent_items:
        return "parent_inventory_empty"
    if batch.inventory_status == "empty" or not current_items:
        return "empty_revision_inventory"
    return "ready"


def _revision_changes(
    parent_items: list[m.CarbonEmissionInventoryItem],
    current_items: list[m.CarbonEmissionInventoryItem],
) -> list[dict[str, Any]]:
    parent_map = {_item_key(item): item for item in parent_items}
    current_map = {_item_key(item): item for item in current_items}
    changes: list[dict[str, Any]] = []
    for key in sorted(set(parent_map) | set(current_map)):
        before = parent_map.get(key)
        after = current_map.get(key)
        if before is None and after is not None:
            changes.append(_change_payload("added", None, after))
        elif before is not None and after is None:
            changes.append(_change_payload("removed", before, None))
        elif before is not None and after is not None and _item_changed(before, after):
            changes.append(_change_payload("changed", before, after))
    return changes


def _item_key(item: m.CarbonEmissionInventoryItem) -> tuple[str, int]:
    return item.record_type, item.record_id


def _item_changed(before: m.CarbonEmissionInventoryItem, after: m.CarbonEmissionInventoryItem) -> bool:
    return any(
        (
            before.included != after.included,
            before.activity_amount != after.activity_amount,
            before.activity_unit != after.activity_unit,
            before.computed_co2e != after.computed_co2e,
            before.factor_source != after.factor_source,
            before.factor_year != after.factor_year,
            before.factor_unit != after.factor_unit,
            before.quality_status != after.quality_status,
        )
    )


def _change_payload(
    change_type: str,
    before: m.CarbonEmissionInventoryItem | None,
    after: m.CarbonEmissionInventoryItem | None,
) -> dict[str, Any]:
    row = after or before
    before_kg = _included_kg(before)
    after_kg = _included_kg(after)
    return {
        "change_type": change_type,
        "record_type": row.record_type if row else None,
        "record_id": row.record_id if row else None,
        "scope": row.scope if row else None,
        "record_label": row.record_label if row else None,
        "display_name": row.display_name if row else None,
        "period": row.period if row else None,
        "before_included": before.included if before else None,
        "after_included": after.included if after else None,
        "before_activity_amount": _float(before.activity_amount) if before else None,
        "after_activity_amount": _float(after.activity_amount) if after else None,
        "activity_unit": (after or before).activity_unit if (after or before) else None,
        "before_kg_co2e": _float(before_kg),
        "after_kg_co2e": _float(after_kg),
        "delta_kg_co2e": _float(after_kg - before_kg),
        "before_quality_status": before.quality_status if before else None,
        "after_quality_status": after.quality_status if after else None,
        "before_factor_source": before.factor_source if before else None,
        "after_factor_source": after.factor_source if after else None,
    }


def _scope_totals(items: list[m.CarbonEmissionInventoryItem]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for item in items:
        bucket = buckets.setdefault(item.scope, {"kg_co2e": Decimal(0), "record_count": 0, "included_record_count": 0})
        bucket["record_count"] += 1
        if item.included:
            bucket["included_record_count"] += 1
            bucket["kg_co2e"] += item.computed_co2e or Decimal(0)
    return buckets


def _scope_delta(scope: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    before_kg = before["kg_co2e"] if before else Decimal(0)
    after_kg = after["kg_co2e"] if after else Decimal(0)
    return {
        "scope": scope,
        "before_kg_co2e": _float(before_kg),
        "after_kg_co2e": _float(after_kg),
        "delta_kg_co2e": _float(after_kg - before_kg),
        "before_t_co2e": _float(before_kg / Decimal(1000)),
        "after_t_co2e": _float(after_kg / Decimal(1000)),
        "delta_t_co2e": _float((after_kg - before_kg) / Decimal(1000)),
        "before_record_count": int(before["record_count"] if before else 0),
        "after_record_count": int(after["record_count"] if after else 0),
        "before_included_record_count": int(before["included_record_count"] if before else 0),
        "after_included_record_count": int(after["included_record_count"] if after else 0),
    }


def _included_kg(item: m.CarbonEmissionInventoryItem | None) -> Decimal:
    if item is None or not item.included:
        return Decimal(0)
    return item.computed_co2e or Decimal(0)
