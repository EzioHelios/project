from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select

from app.db import models as m

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


PLAN_FIELDS = {
    "code",
    "name",
    "budget_year",
    "period_type",
    "period_start",
    "period_end",
    "target_scope",
    "target_code",
    "target_name",
    "energy_budget_tce",
    "carbon_budget_co2e",
    "denominator_plan",
    "denominator_unit",
    "energy_intensity_budget",
    "carbon_intensity_budget",
    "status",
    "source_name",
    "standard_code",
    "confidence_level",
    "remark",
}
ALLOCATION_FIELDS = {
    "period_month",
    "target_scope",
    "target_code",
    "target_name",
    "energy_budget_tce",
    "carbon_budget_co2e",
    "denominator_budget",
    "denominator_unit",
    "energy_intensity_budget",
    "carbon_intensity_budget",
    "status",
    "source_name",
    "standard_code",
    "confidence_level",
    "remark",
}
ADJUSTMENT_FIELDS = {
    "plan_id",
    "allocation_id",
    "adjustment_no",
    "adjustment_type",
    "effective_month",
    "original_energy_budget_tce",
    "original_carbon_budget_co2e",
    "adjusted_energy_budget_tce",
    "adjusted_carbon_budget_co2e",
    "reason",
    "status",
    "requested_by",
    "approved_by",
    "approved_at",
    "source_name",
    "standard_code",
    "confidence_level",
    "remark",
}
DECIMAL_FIELDS = {
    "energy_budget_tce",
    "carbon_budget_co2e",
    "denominator_plan",
    "energy_intensity_budget",
    "carbon_intensity_budget",
    "denominator_budget",
    "original_energy_budget_tce",
    "original_carbon_budget_co2e",
    "adjusted_energy_budget_tce",
    "adjusted_carbon_budget_co2e",
}
DATE_FIELDS = {"period_start", "period_end", "period_month", "effective_month"}
DECEMBER = 12


class EnergyBudgetUseCase:
    """Application workflow for budget commands."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_plan(self, data: dict[str, Any]) -> m.EnergyCarbonBudgetPlan:
        payload = _plan_payload(data, require_required=True)
        obj = m.EnergyCarbonBudgetPlan(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_plan(self, plan_id: int, data: dict[str, Any]) -> m.EnergyCarbonBudgetPlan:
        obj = await self._session.get(m.EnergyCarbonBudgetPlan, plan_id)
        if obj is None:
            msg = "预算方案不存在"
            raise ValueError(msg)
        payload = _plan_payload(data, require_required=False)
        for key, value in payload.items():
            setattr(obj, key, value)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete_plan(self, plan_id: int) -> None:
        obj = await self._session.get(m.EnergyCarbonBudgetPlan, plan_id)
        if obj is None:
            msg = "预算方案不存在"
            raise ValueError(msg)
        await self._session.delete(obj)
        await self._session.commit()

    async def generate_allocations(self, plan_id: int, data: dict[str, Any] | None = None) -> dict[str, Any]:
        plan = await self._session.get(m.EnergyCarbonBudgetPlan, plan_id)
        if plan is None:
            msg = "预算方案不存在"
            raise ValueError(msg)
        data = data or {}
        replace_existing = bool(data.get("replace_existing", True))
        if replace_existing:
            await self._session.execute(delete(m.EnergyCarbonBudgetAllocation).where(m.EnergyCarbonBudgetAllocation.plan_id == plan.id))
            await self._session.flush()

        months = _months_between(plan.period_start, plan.period_end)
        if not months:
            msg = "预算期间无有效月份"
            raise ValueError(msg)
        energy_weights = _weights(data.get("energy_weights"), len(months))
        carbon_weights = _weights(data.get("carbon_weights"), len(months))
        denominator_weights = _weights(data.get("denominator_weights"), len(months))
        created = []
        for index, month in enumerate(months):
            denominator = _weighted(plan.denominator_plan, denominator_weights[index])
            energy_budget = _weighted(plan.energy_budget_tce, energy_weights[index])
            carbon_budget = _weighted(plan.carbon_budget_co2e, carbon_weights[index])
            allocation = m.EnergyCarbonBudgetAllocation(
                plan_id=plan.id,
                period_month=month,
                target_scope=plan.target_scope,
                target_code=plan.target_code,
                target_name=plan.target_name,
                energy_budget_tce=energy_budget,
                carbon_budget_co2e=carbon_budget,
                denominator_budget=denominator,
                denominator_unit=plan.denominator_unit,
                energy_intensity_budget=_ratio_decimal(energy_budget, denominator),
                carbon_intensity_budget=_ratio_decimal(carbon_budget, denominator),
                status="active",
                source_name=plan.source_name or "年度预算月度分解",
                standard_code=plan.standard_code,
                confidence_level=plan.confidence_level,
            )
            self._session.add(allocation)
            created.append(allocation)
        await self._session.commit()
        return {"plan_id": plan.id, "created_count": len(created)}

    async def update_allocation(self, allocation_id: int, data: dict[str, Any]) -> m.EnergyCarbonBudgetAllocation:
        obj = await self._session.get(m.EnergyCarbonBudgetAllocation, allocation_id)
        if obj is None:
            msg = "月度预算不存在"
            raise ValueError(msg)
        payload = _generic_payload(data, ALLOCATION_FIELDS)
        for key, value in payload.items():
            setattr(obj, key, value)
        if "energy_budget_tce" in payload or "denominator_budget" in payload:
            obj.energy_intensity_budget = _ratio_decimal(obj.energy_budget_tce, obj.denominator_budget)
        if "carbon_budget_co2e" in payload or "denominator_budget" in payload:
            obj.carbon_intensity_budget = _ratio_decimal(obj.carbon_budget_co2e, obj.denominator_budget)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def create_adjustment(self, data: dict[str, Any]) -> m.EnergyCarbonBudgetAdjustment:
        payload = await self._adjustment_payload(data, require_required=True)
        obj = m.EnergyCarbonBudgetAdjustment(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_adjustment(self, adjustment_id: int, data: dict[str, Any]) -> m.EnergyCarbonBudgetAdjustment:
        obj = await self._session.get(m.EnergyCarbonBudgetAdjustment, adjustment_id)
        if obj is None:
            msg = "调整记录不存在"
            raise ValueError(msg)
        payload = await self._adjustment_payload(data, require_required=False)
        for key, value in payload.items():
            setattr(obj, key, value)
        if obj.status == "approved" and obj.approved_at is None:
            obj.approved_at = datetime.now(UTC).replace(tzinfo=None)
        if obj.status == "approved":
            await self._apply_adjustment(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete_adjustment(self, adjustment_id: int) -> None:
        obj = await self._session.get(m.EnergyCarbonBudgetAdjustment, adjustment_id)
        if obj is None:
            msg = "调整记录不存在"
            raise ValueError(msg)
        await self._session.delete(obj)
        await self._session.commit()

    async def _adjustment_payload(self, data: dict[str, Any], *, require_required: bool) -> dict[str, Any]:
        payload = _generic_payload(data, ADJUSTMENT_FIELDS)
        if require_required and not payload.get("plan_id"):
            msg = "预算方案不能为空"
            raise ValueError(msg)
        if require_required and not payload.get("adjustment_no"):
            payload["adjustment_no"] = await self._next_adjustment_no()
        if payload.get("allocation_id"):
            allocation = await self._session.get(m.EnergyCarbonBudgetAllocation, payload["allocation_id"])
            if allocation is None:
                msg = "月度预算不存在"
                raise ValueError(msg)
            payload.setdefault("plan_id", allocation.plan_id)
            payload.setdefault("effective_month", allocation.period_month)
            payload.setdefault("original_energy_budget_tce", allocation.energy_budget_tce)
            payload.setdefault("original_carbon_budget_co2e", allocation.carbon_budget_co2e)
        if payload.get("plan_id"):
            plan = await self._session.get(m.EnergyCarbonBudgetPlan, payload["plan_id"])
            if plan is None:
                msg = "预算方案不存在"
                raise ValueError(msg)
        payload.setdefault("status", "draft")
        payload.setdefault("adjustment_type", "reforecast")
        return payload

    async def _next_adjustment_no(self) -> str:
        latest = await self._session.scalar(
            select(m.EnergyCarbonBudgetAdjustment.id).order_by(m.EnergyCarbonBudgetAdjustment.id.desc()).limit(1)
        )
        return f"ECB-ADJ-{int(latest or 0) + 1:05d}"

    async def _apply_adjustment(self, adjustment: m.EnergyCarbonBudgetAdjustment) -> None:
        if adjustment.allocation_id is None:
            return
        allocation = await self._session.get(m.EnergyCarbonBudgetAllocation, adjustment.allocation_id)
        if allocation is None:
            return
        if adjustment.adjusted_energy_budget_tce is not None:
            allocation.energy_budget_tce = adjustment.adjusted_energy_budget_tce
        if adjustment.adjusted_carbon_budget_co2e is not None:
            allocation.carbon_budget_co2e = adjustment.adjusted_carbon_budget_co2e
        allocation.energy_intensity_budget = _ratio_decimal(allocation.energy_budget_tce, allocation.denominator_budget)
        allocation.carbon_intensity_budget = _ratio_decimal(allocation.carbon_budget_co2e, allocation.denominator_budget)


def _plan_payload(data: dict[str, Any], *, require_required: bool) -> dict[str, Any]:
    payload = _generic_payload(data, PLAN_FIELDS)
    if require_required:
        if not payload.get("name"):
            msg = "预算名称不能为空"
            raise ValueError(msg)
        if not payload.get("budget_year"):
            msg = "预算年度不能为空"
            raise ValueError(msg)
        budget_year = int(payload["budget_year"])
        payload.setdefault("code", f"ECB-{budget_year}")
        payload.setdefault("period_start", date(budget_year, 1, 1))
        payload.setdefault("period_end", date(budget_year, 12, 31))
    if "budget_year" in payload:
        payload["budget_year"] = int(payload["budget_year"])
    payload.setdefault("period_type", "annual")
    payload.setdefault("target_scope", "enterprise")
    payload.setdefault("status", "draft")
    if payload.get("energy_intensity_budget") is None:
        payload["energy_intensity_budget"] = _ratio_decimal(payload.get("energy_budget_tce"), payload.get("denominator_plan"))
    if payload.get("carbon_intensity_budget") is None:
        payload["carbon_intensity_budget"] = _ratio_decimal(payload.get("carbon_budget_co2e"), payload.get("denominator_plan"))
    return payload


def _generic_payload(data: dict[str, Any], fields: set[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in data.items():
        if key not in fields:
            continue
        if key in DECIMAL_FIELDS:
            payload[key] = _decimal_or_none(value)
        elif key in DATE_FIELDS:
            payload[key] = _date_or_none(value)
        elif key == "approved_at":
            payload[key] = _datetime_or_none(value)
        elif isinstance(value, str):
            payload[key] = value.strip() or None
        else:
            payload[key] = value
    return payload


def _months_between(start: date, end: date) -> list[date]:
    current = date(start.year, start.month, 1)
    end_month = date(end.year, end.month, 1)
    months = []
    while current <= end_month:
        months.append(current)
        current = date(current.year + 1, 1, 1) if current.month == DECEMBER else date(current.year, current.month + 1, 1)
    return months


def _weights(value: Any, size: int) -> list[Decimal]:
    if not isinstance(value, list) or len(value) != size:
        return [Decimal(1) / Decimal(size)] * size
    numbers = [_decimal_or_none(item) or Decimal(0) for item in value]
    total = sum(numbers)
    if total <= 0:
        return [Decimal(1) / Decimal(size)] * size
    return [item / total for item in numbers]


def _weighted(value: Decimal | None, weight: Decimal) -> Decimal | None:
    if value is None:
        return None
    return (value * weight).quantize(Decimal("0.000001"))


def _ratio_decimal(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return (numerator / denominator).quantize(Decimal("0.000001"))


def _date_or_none(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _datetime_or_none(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))
