# ruff: noqa: S608
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.domain.energy.queries.common import jsonable_mapping, period_param, ratio_or_none
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


BALANCED_THRESHOLD_PCT = 2.0
WARNING_THRESHOLD_PCT = 10.0


@dataclass(frozen=True, slots=True)
class EnergyBalanceQuery:
    """Read-model query parameters for metering-boundary energy balance."""

    period_start: str | None = None
    period_end: str | None = None
    granularity: str = "day"
    boundary_id: int | None = None
    energy_type_code: str | None = None


class EnergyBalanceQueryService:
    """Query service for metering-boundary energy balance."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def calculation(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        boundary = await self._selected_boundary(query.boundary_id)
        if boundary is None:
            return {"boundary": None, "summary": _empty_summary("no_boundary"), "rows": [], "filters": _filters(query)}

        member_rows = await self._member_rows(int(boundary["id"]))
        input_total = await self._input_total(query, boundary)
        allocated_total = await self._allocated_total(query, member_rows)
        member_count = len([row for row in member_rows if row["confirmation_status"] == "confirmed"])
        input_amount = float(input_total["amount"] or 0)
        allocated_amount = float(allocated_total["amount"] or 0)
        difference = input_amount - allocated_amount
        error_pct = ratio_or_none(abs(difference) * 100, input_amount, 2)
        status = _balance_status(
            input_amount=input_amount,
            member_count=member_count,
            error_pct=error_pct,
            has_input_meter=bool(boundary.get("meter_equipment_id")),
        )
        return {
            "boundary": boundary,
            "summary": {
                "status": status,
                "input_energy": round(input_amount, 4),
                "allocated_energy": round(allocated_amount, 4),
                "unallocated_energy": round(difference, 4),
                "balance_error_pct": error_pct,
                "input_record_count": int(input_total["record_count"] or 0),
                "allocated_record_count": int(allocated_total["record_count"] or 0),
                "member_count": member_count,
                "metering_coverage_pct": ratio_or_none(allocated_amount * 100, input_amount, 2),
                "energy_type_code": query.energy_type_code,
            },
            "rows": [
                _row("input", "边界输入", input_amount, "总表/进线表", input_total["record_count"]),
                _row("allocated", "已归集用能", allocated_amount, "确认成员表计", allocated_total["record_count"]),
                _row("unallocated", "未归集差异", difference, "输入减已归集", None),
                _row("error_pct", "平衡误差率", error_pct, "差异绝对值/输入", None, unit="%"),
            ],
            "filters": _filters(query),
        }

    async def diagnostics(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        calculation = await self.calculation(query)
        boundary = calculation["boundary"]
        summary = calculation["summary"]
        items: list[dict[str, Any]] = []
        if boundary is None:
            items.append(_diagnostic("no_boundary", "未配置计量边界", "请先维护基地或区域的计量边界。", "blocking"))
            return {"items": items, "summary": summary, "filters": _filters(query)}
        if not boundary.get("meter_equipment_id"):
            items.append(_diagnostic("missing_input_meter", "缺少边界输入表", "请为边界选择总表或进线表。", "blocking"))
        if summary["input_energy"] <= 0:
            items.append(_diagnostic("missing_input_facts", "边界输入无能源事实", "请确认总表已接入并生成当前期间能源事实。", "blocking"))
        if summary["member_count"] <= 0:
            items.append(_diagnostic("missing_members", "缺少确认成员", "请维护并确认区域、设备或分表成员。", "blocking"))
        if summary["allocated_record_count"] <= 0:
            items.append(_diagnostic("missing_member_facts", "成员无能源事实", "请确认成员设备已生成能源事实。", "warning"))
        if summary["status"] in {"warning", "unbalanced"}:
            items.append(
                _diagnostic(
                    summary["status"],
                    "平衡差异偏大",
                    "请检查是否存在未归集分表、重复成员或总分表期间不一致。",
                    "warning" if summary["status"] == "warning" else "high",
                    value=summary["balance_error_pct"],
                    unit="%",
                )
            )
        items.extend(await self._unassigned_fact_diagnostics(query, boundary))
        items.extend(await self._duplicate_member_diagnostics(int(boundary["id"])))
        if not items:
            items.append(_diagnostic("balanced", "边界已闭合", "当前期间边界输入与成员归集差异在阈值内。", "ok"))
        return {"items": items, "summary": summary, "filters": _filters(query)}

    async def _selected_boundary(self, boundary_id: int | None) -> dict[str, Any] | None:
        team_id = require_session_tenant_id(self._session)
        base_sql = """
            select b.*, e.code as meter_equipment_code, e.name as meter_equipment_name, s.code as sector_code,
                   s.name as sector_name
            from metering_measurement_boundary b
            left join dataapp_monitorequipment e on e.team_id = b.team_id and e.id = b.meter_equipment_id
            left join dataapp_monitorsector s on s.team_id = b.team_id and s.id = b.sector_id
            where b.team_id = :team_id
        """
        params: dict[str, Any] = {"team_id": str(team_id)}
        if boundary_id is not None:
            row = (
                await self._session.execute(
                    text(f"{base_sql} and b.id = :boundary_id"),
                    {**params, "boundary_id": boundary_id},
                )
            ).mappings().first()
            return jsonable_mapping(dict(row)) if row else None
        row = (
            await self._session.execute(
                text(
                    f"""
                    {base_sql} and b.status = 'active'
                    order by case when b.boundary_type = 'site' then 0 else 1 end, b.code
                    limit 1
                    """
                ),
                params,
            )
        ).mappings().first()
        return jsonable_mapping(dict(row)) if row else None

    async def _member_rows(self, boundary_id: int) -> list[dict[str, Any]]:
        team_id = require_session_tenant_id(self._session)
        rows = (
            await self._session.execute(
                text(
                    """
                    select m.*, e.code as equipment_code, e.name as equipment_name, s.code as sector_code,
                           s.name as sector_name
                    from metering_measurement_boundary_member m
                    left join dataapp_monitorequipment e on e.team_id = m.team_id and e.id = m.equipment_id
                    left join dataapp_monitorsector s on s.team_id = m.team_id and s.id = m.sector_id
                    where m.team_id = :team_id and m.boundary_id = :boundary_id
                    order by m.member_role, m.member_code
                    """
                ),
                {"team_id": str(team_id), "boundary_id": boundary_id},
            )
        ).mappings().all()
        return [jsonable_mapping(dict(row)) for row in rows]

    async def _input_total(self, query: EnergyBalanceQuery, boundary: dict[str, Any]) -> dict[str, Any]:
        if not boundary.get("meter_equipment_id"):
            return {"amount": 0, "record_count": 0}
        where_sql, params = self._fact_filters(query, alias="f")
        row = (
            await self._session.execute(
                text(
                    f"""
                    select coalesce(sum(f.amount), 0) as amount, count(*)::int as record_count
                    from dataapp_energyintervalfact f
                    where {where_sql} and f.equipment_id = :equipment_id
                    """
                ),
                {**params, "equipment_id": int(boundary["meter_equipment_id"])},
            )
        ).mappings().one()
        return jsonable_mapping(dict(row))

    async def _allocated_total(self, query: EnergyBalanceQuery, member_rows: list[dict[str, Any]]) -> dict[str, Any]:
        equipment_ids = sorted(
            {
                int(row["equipment_id"])
                for row in member_rows
                if row.get("equipment_id") is not None
                and row.get("confirmation_status") == "confirmed"
                and row.get("member_role") != "input_meter"
            }
        )
        sector_ids = sorted(
            {
                int(row["sector_id"])
                for row in member_rows
                if row.get("sector_id") is not None
                and row.get("equipment_id") is None
                and row.get("confirmation_status") == "confirmed"
                and row.get("member_role") != "input_meter"
            }
        )
        if not equipment_ids and not sector_ids:
            return {"amount": 0, "record_count": 0}
        where_sql, params = self._fact_filters(query, alias="f")
        row = (
            await self._session.execute(
                text(
                    f"""
                    select coalesce(sum(f.amount), 0) as amount, count(*)::int as record_count
                    from dataapp_energyintervalfact f
                    left join dataapp_monitorequipment e on e.team_id = f.team_id and e.id = f.equipment_id
                    where {where_sql}
                      and (f.equipment_id = any(:equipment_ids) or e.sector_id = any(:sector_ids))
                    """
                ),
                {**params, "equipment_ids": equipment_ids or [-1], "sector_ids": sector_ids or [-1]},
            )
        ).mappings().one()
        return jsonable_mapping(dict(row))

    async def _unassigned_fact_diagnostics(self, query: EnergyBalanceQuery, boundary: dict[str, Any]) -> list[dict[str, Any]]:
        where_sql, params = self._fact_filters(query, alias="f")
        row = (
            await self._session.execute(
                text(
                    f"""
                    select count(*)::int as record_count, coalesce(sum(f.amount), 0) as amount
                    from dataapp_energyintervalfact f
                    where {where_sql} and (f.measurement_boundary_id is null or f.measurement_boundary_id <> :boundary_id)
                    """
                ),
                {**params, "boundary_id": int(boundary["id"])},
            )
        ).mappings().one()
        data = jsonable_mapping(dict(row))
        if int(data["record_count"] or 0) <= 0:
            return []
        return [
            _diagnostic(
                "unassigned_facts",
                "存在未绑定本边界的能源事实",
                "请检查能源事实是否需要归入其他边界或补充边界成员。",
                "warning",
                value=data["amount"],
                unit="kWh",
                count=data["record_count"],
            )
        ]

    async def _duplicate_member_diagnostics(self, boundary_id: int) -> list[dict[str, Any]]:
        team_id = require_session_tenant_id(self._session)
        rows = (
            await self._session.execute(
                text(
                    """
                    select coalesce(equipment_id::text, 'sector:' || sector_id::text, member_code) as object_key,
                           count(*)::int as record_count
                    from metering_measurement_boundary_member
                    where team_id = :team_id and boundary_id = :boundary_id and confirmation_status = 'confirmed'
                    group by coalesce(equipment_id::text, 'sector:' || sector_id::text, member_code)
                    having count(*) > 1
                    """
                ),
                {"team_id": str(team_id), "boundary_id": boundary_id},
            )
        ).mappings().all()
        return [
            _diagnostic("duplicate_member", f"成员重复: {row['object_key']}", "请保留一个确认成员, 避免重复归集。", "high", count=row["record_count"])
            for row in rows
        ]

    def _fact_filters(self, query: EnergyBalanceQuery, *, alias: str) -> tuple[str, dict[str, Any]]:
        team_id = require_session_tenant_id(self._session)
        granularity = query.granularity if query.granularity in {"hour", "day"} else "day"
        conditions = [f"{alias}.team_id = :team_id", f"{alias}.is_current = true", f"{alias}.granularity = :granularity"]
        params: dict[str, Any] = {"team_id": str(team_id), "granularity": granularity}
        if query.period_start:
            conditions.append(f"{alias}.period_end >= (:period_start)::timestamp")
            params["period_start"] = period_param(query.period_start)
        if query.period_end:
            conditions.append(f"{alias}.period_start <= (:period_end)::timestamp")
            params["period_end"] = period_param(query.period_end)
        if query.energy_type_code and query.energy_type_code != "all":
            conditions.append(f"{alias}.energy_type_code = :energy_type_code")
            params["energy_type_code"] = query.energy_type_code
        return " and ".join(conditions), params


def _empty_summary(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "input_energy": 0,
        "allocated_energy": 0,
        "unallocated_energy": 0,
        "balance_error_pct": None,
        "input_record_count": 0,
        "allocated_record_count": 0,
        "member_count": 0,
        "metering_coverage_pct": None,
        "energy_type_code": None,
    }


def _row(
    code: str,
    label: str,
    value: float | None,
    source_name: str,
    record_count: int | None,
    *,
    unit: str = "kWh",
) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "value": round(value, 4) if value is not None else None,
        "unit": unit,
        "source_name": source_name,
        "record_count": record_count,
    }


def _diagnostic(
    code: str,
    title: str,
    suggestion: str,
    severity: str,
    *,
    value: float | None = None,
    unit: str | None = None,
    count: int | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "suggestion": suggestion,
        "severity": severity,
        "value": value,
        "unit": unit,
        "count": count,
    }


def _balance_status(*, input_amount: float, member_count: int, error_pct: float | None, has_input_meter: bool) -> str:
    status = "unbalanced"
    if not has_input_meter:
        status = "missing_input_meter"
    elif input_amount <= 0 or error_pct is None:
        status = "missing_input_facts"
    elif member_count <= 0:
        status = "missing_members"
    elif error_pct <= BALANCED_THRESHOLD_PCT:
        status = "balanced"
    elif error_pct <= WARNING_THRESHOLD_PCT:
        status = "warning"
    return status


def _filters(query: EnergyBalanceQuery) -> dict[str, Any]:
    return {
        "period_start": query.period_start,
        "period_end": query.period_end,
        "granularity": query.granularity,
        "boundary_id": query.boundary_id,
        "energy_type_code": query.energy_type_code,
    }
