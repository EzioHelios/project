from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from litestar import Controller, delete, get, patch, post
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import case, func, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict, ok_data
from app.domain.energy.queries.balance import EnergyBalanceQuery, EnergyBalanceQueryService
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


BALANCE_BODY = Body()
BOUNDARY_FIELDS = {
    "code",
    "name",
    "boundary_type",
    "meter_equipment_id",
    "sector_id",
    "use_system_code",
    "energy_direction",
    "include_in_scope2",
    "valid_from",
    "valid_to",
    "status",
    "mapping_version",
    "source_name",
    "confidence_level",
    "remark",
}
MEMBER_FIELDS = {
    "boundary_id",
    "member_code",
    "member_type",
    "sector_id",
    "equipment_id",
    "member_role",
    "allocation_weight",
    "confirmation_status",
    "valid_from",
    "valid_to",
    "source_name",
    "remark",
}


class EnergyBalanceController(Controller):
    tags = ["Energy"]

    @get("/api/energy/balance/boundaries")
    async def list_energy_balance_boundaries(
        self,
        db_session: AsyncSession,
        keyword: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        team_id = require_session_tenant_id(db_session)
        conditions = [m.MeasurementBoundary.team_id == team_id]
        if keyword:
            value = f"%{keyword.strip()}%"
            conditions.append((m.MeasurementBoundary.code.ilike(value)) | (m.MeasurementBoundary.name.ilike(value)))
        if status and status != "all":
            conditions.append(m.MeasurementBoundary.status == status)
        stmt = (
            select(m.MeasurementBoundary)
            .where(*conditions)
            .order_by(case((m.MeasurementBoundary.boundary_type == "site", 0), else_=1), m.MeasurementBoundary.code.asc())
        )
        total = int((await db_session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await db_session.execute(stmt.limit(_limit(limit)).offset(max(0, offset)))).scalars().all()
        return Response(content=_page([model_to_dict(row) for row in rows], total, _limit(limit), max(0, offset)))

    @post("/api/energy/balance/boundaries")
    async def create_energy_balance_boundary(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BALANCE_BODY,
    ) -> Response[dict]:
        payload = await _boundary_payload(db_session, data, require_required=True)
        if isinstance(payload, Response):
            return payload
        obj = m.MeasurementBoundary(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/energy/balance/boundaries/{boundary_id:int}")
    async def update_energy_balance_boundary(
        self,
        db_session: AsyncSession,
        boundary_id: int,
        data: dict[str, Any] = BALANCE_BODY,
    ) -> Response[dict]:
        obj = await db_session.get(m.MeasurementBoundary, boundary_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "计量边界不存在"}, status_code=404)
        payload = await _boundary_payload(db_session, data, require_required=False)
        if isinstance(payload, Response):
            return payload
        for key, value in payload.items():
            setattr(obj, key, value)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @delete("/api/energy/balance/boundaries/{boundary_id:int}", status_code=200)
    async def delete_energy_balance_boundary(self, db_session: AsyncSession, boundary_id: int) -> Response[dict]:
        obj = await db_session.get(m.MeasurementBoundary, boundary_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "计量边界不存在"}, status_code=404)
        fact_count = int(
            await db_session.scalar(
                select(func.count()).select_from(m.EnergyIntervalFact).where(m.EnergyIntervalFact.measurement_boundary_id == boundary_id)
            )
            or 0
        )
        if fact_count:
            return Response(content={"code": 400, "msg": "计量边界已被能源事实使用, 请停用后保留追溯。"}, status_code=400)
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/energy/balance/boundary-members")
    async def list_energy_balance_boundary_members(
        self,
        db_session: AsyncSession,
        boundary_id: int | None = None,
        confirmation_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[dict]:
        team_id = require_session_tenant_id(db_session)
        conditions = [m.MeasurementBoundaryMember.team_id == team_id]
        if boundary_id is not None:
            conditions.append(m.MeasurementBoundaryMember.boundary_id == boundary_id)
        if confirmation_status and confirmation_status != "all":
            conditions.append(m.MeasurementBoundaryMember.confirmation_status == confirmation_status)
        stmt = select(m.MeasurementBoundaryMember).where(*conditions).order_by(m.MeasurementBoundaryMember.member_code.asc())
        total = int((await db_session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await db_session.execute(stmt.limit(_limit(limit)).offset(max(0, offset)))).scalars().all()
        return Response(content=_page([model_to_dict(row) for row in rows], total, _limit(limit), max(0, offset)))

    @post("/api/energy/balance/boundary-members")
    async def create_energy_balance_boundary_member(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BALANCE_BODY,
    ) -> Response[dict]:
        payload = await _member_payload(db_session, data, require_required=True)
        if isinstance(payload, Response):
            return payload
        obj = m.MeasurementBoundaryMember(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/energy/balance/boundary-members/{member_id:int}")
    async def update_energy_balance_boundary_member(
        self,
        db_session: AsyncSession,
        member_id: int,
        data: dict[str, Any] = BALANCE_BODY,
    ) -> Response[dict]:
        obj = await db_session.get(m.MeasurementBoundaryMember, member_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "边界成员不存在"}, status_code=404)
        payload = await _member_payload(db_session, data, require_required=False)
        if isinstance(payload, Response):
            return payload
        for key, value in payload.items():
            setattr(obj, key, value)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content=ok_data(model_to_dict(obj)))

    @delete("/api/energy/balance/boundary-members/{member_id:int}", status_code=200)
    async def delete_energy_balance_boundary_member(self, db_session: AsyncSession, member_id: int) -> Response[dict]:
        obj = await db_session.get(m.MeasurementBoundaryMember, member_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "边界成员不存在"}, status_code=404)
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/energy/balance/calculation")
    async def get_energy_balance_calculation(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "day",
        boundary_id: int | None = None,
        energy_type_code: str | None = None,
    ) -> Response[dict]:
        data = await EnergyBalanceQueryService(db_session).calculation(
            EnergyBalanceQuery(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                boundary_id=boundary_id,
                energy_type_code=energy_type_code,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/balance/diagnostics")
    async def get_energy_balance_diagnostics(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "day",
        boundary_id: int | None = None,
        energy_type_code: str | None = None,
    ) -> Response[dict]:
        data = await EnergyBalanceQueryService(db_session).diagnostics(
            EnergyBalanceQuery(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                boundary_id=boundary_id,
                energy_type_code=energy_type_code,
            )
        )
        return Response(content=ok_data(data))


async def _boundary_payload(db_session: AsyncSession, data: dict[str, Any], *, require_required: bool) -> dict[str, Any] | Response[dict]:
    payload = {key: _coerce_value(key, value) for key, value in data.items() if key in BOUNDARY_FIELDS}
    if require_required:
        missing = [key for key in ("code", "name") if not str(payload.get(key) or "").strip()]
        if missing:
            return Response(content={"code": 400, "msg": f"缺少字段: {', '.join(missing)}"}, status_code=400)
    if "code" in payload and payload["code"] is not None:
        payload["code"] = str(payload["code"]).strip()
    if "name" in payload and payload["name"] is not None:
        payload["name"] = str(payload["name"]).strip()
    if payload.get("meter_equipment_id") is not None and await db_session.get(m.MonitorEquipment, int(payload["meter_equipment_id"])) is None:
        return Response(content={"code": 400, "msg": "输入表设备不存在"}, status_code=400)
    if payload.get("sector_id") is not None and await db_session.get(m.MonitorSector, int(payload["sector_id"])) is None:
        return Response(content={"code": 400, "msg": "区域不存在"}, status_code=400)
    return payload


async def _member_payload(db_session: AsyncSession, data: dict[str, Any], *, require_required: bool) -> dict[str, Any] | Response[dict]:
    payload = {key: _coerce_value(key, value) for key, value in data.items() if key in MEMBER_FIELDS}
    if require_required:
        missing = [key for key in ("boundary_id", "member_code", "member_type") if payload.get(key) in (None, "")]
        if missing:
            return Response(content={"code": 400, "msg": f"缺少字段: {', '.join(missing)}"}, status_code=400)
    if payload.get("boundary_id") is not None and await db_session.get(m.MeasurementBoundary, int(payload["boundary_id"])) is None:
        return Response(content={"code": 400, "msg": "计量边界不存在"}, status_code=400)
    if payload.get("equipment_id") is not None and await db_session.get(m.MonitorEquipment, int(payload["equipment_id"])) is None:
        return Response(content={"code": 400, "msg": "设备不存在"}, status_code=400)
    if payload.get("sector_id") is not None and await db_session.get(m.MonitorSector, int(payload["sector_id"])) is None:
        return Response(content={"code": 400, "msg": "区域不存在"}, status_code=400)
    if "member_code" in payload and payload["member_code"] is not None:
        payload["member_code"] = str(payload["member_code"]).strip()
    payload.setdefault("member_role", "covered")
    payload.setdefault("confirmation_status", "confirmed")
    return payload


def _coerce_value(key: str, value: Any) -> Any:
    if value == "":
        return None
    if key in {"valid_from", "valid_to"} and isinstance(value, str) and value:
        return date.fromisoformat(value)
    if key in {"meter_equipment_id", "sector_id", "boundary_id", "equipment_id"} and value is not None:
        return int(value)
    if key == "allocation_weight" and value is not None:
        return Decimal(str(value))
    return value


def _page(items: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": limit, "offset": offset, "code": 200, "data": items}


def _limit(value: int) -> int:
    return max(1, min(value, 200))
