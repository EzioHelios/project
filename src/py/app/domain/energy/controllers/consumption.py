from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from litestar import Controller, delete, get, patch, post
from litestar.exceptions import ClientException, NotFoundException
from litestar.params import Body, Parameter
from litestar.response import Response
from sqlalchemy import func, select

from app.db import models as m
from app.domain.accounts.guards import requires_superuser
from app.domain.energy.queries.consumption import (
    ENERGY_CONSUMPTION_EXPORT_HEADERS,
    EnergyConsumptionQuery,
    EnergyConsumptionQueryService,
)
from app.domain.energy.usecases.energy_types import canonicalize_energy_type_code
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

ADMIN_BODY = Body()
ENERGY_INTERVAL_FACT_SORT_FIELDS = {
    "id",
    "period_start",
    "period_end",
    "energy_type_code",
    "equipment_code",
    "equipment_name",
    "area_name",
    "amount",
    "unit",
    "data_quality",
    "source_system",
    "source_record_id",
}
ENERGY_INTERVAL_FACT_EXPORT_HEADERS = [
    "source_system",
    "source_record_id",
    "energy_type_code",
    "equipment_code",
    "equipment_name",
    "area_id",
    "area_name",
    "use_system_code",
    "use_system_name",
    "granularity",
    "period_start",
    "period_end",
    "amount",
    "unit",
    "cost_cny",
    "tariff_segment_type",
    "reading_count",
    "data_quality",
    "remark",
]
YEAR_MONTH_LENGTH = 7
DATE_LENGTH = 10


class EnergyConsumptionController(Controller):
    tags = ["Energy"]

    @get("/api/energy/interval-facts")
    async def list_energy_interval_facts(
        self,
        db_session: AsyncSession,
        keyword: str | None = None,
        search: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
        energy_type_code: str | None = None,
        data_quality: str | None = None,
        source_system: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "period_start",
        sort_order: str = "desc",
    ) -> Response[dict]:
        team_id = require_session_tenant_id(db_session)
        conditions = [m.EnergyIntervalFact.team_id == team_id, m.EnergyIntervalFact.is_current.is_(True)]
        if period_start:
            conditions.append(
                m.EnergyIntervalFact.period_end >= _parse_datetime(period_start, field_name="period_start")
            )
        if period_end:
            conditions.append(m.EnergyIntervalFact.period_start <= _parse_datetime(period_end, field_name="period_end"))
        if energy_type_code and energy_type_code != "all":
            conditions.append(m.EnergyIntervalFact.energy_type_code == energy_type_code)
        if data_quality and data_quality != "all":
            conditions.append(m.EnergyIntervalFact.data_quality == data_quality)
        if source_system and source_system != "all":
            conditions.append(m.EnergyIntervalFact.source_system == source_system)
        query_text = (keyword or search or "").strip()
        if query_text:
            pattern = f"%{query_text}%"
            conditions.append(
                m.EnergyIntervalFact.energy_type_code.ilike(pattern)
                | m.EnergyIntervalFact.equipment_code.ilike(pattern)
                | m.EnergyIntervalFact.equipment_name.ilike(pattern)
                | m.EnergyIntervalFact.area_name.ilike(pattern)
                | m.EnergyIntervalFact.source_record_id.ilike(pattern)
                | m.EnergyIntervalFact.source_system.ilike(pattern)
            )

        limit_clamped = max(1, min(limit, 200))
        offset_clamped = max(0, offset)
        order_column = getattr(
            m.EnergyIntervalFact,
            sort_field if sort_field in ENERGY_INTERVAL_FACT_SORT_FIELDS else "period_start",
        )
        order_by = order_column.asc() if sort_order == "asc" else order_column.desc()
        total = int(
            await db_session.scalar(select(func.count()).select_from(m.EnergyIntervalFact).where(*conditions)) or 0
        )
        rows = list(
            (
                await db_session.scalars(
                    select(m.EnergyIntervalFact)
                    .where(*conditions)
                    .order_by(order_by, m.EnergyIntervalFact.id.desc())
                    .limit(limit_clamped)
                    .offset(offset_clamped)
                )
            ).all()
        )
        return Response(
            content={
                "items": [_energy_interval_fact_payload(row) for row in rows],
                "total": total,
                "limit": limit_clamped,
                "offset": offset_clamped,
            }
        )

    @get("/api/energy/interval-facts/export")
    async def export_energy_interval_facts(self, db_session: AsyncSession) -> Response[str]:
        team_id = require_session_tenant_id(db_session)
        rows = list(
            (
                await db_session.scalars(
                    select(m.EnergyIntervalFact)
                    .where(m.EnergyIntervalFact.team_id == team_id, m.EnergyIntervalFact.is_current.is_(True))
                    .order_by(m.EnergyIntervalFact.period_start.desc(), m.EnergyIntervalFact.id.desc())
                    .limit(5000)
                )
            ).all()
        )
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=ENERGY_INTERVAL_FACT_EXPORT_HEADERS)
        writer.writeheader()
        for row in rows:
            payload = _energy_interval_fact_payload(row)
            writer.writerow({header: payload.get(header) for header in ENERGY_INTERVAL_FACT_EXPORT_HEADERS})
        return Response(
            content="\ufeff" + output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"content-disposition": 'attachment; filename="energy_interval_facts.csv"'},
        )

    @post("/api/energy/interval-facts", guards=[requires_superuser])
    async def create_energy_interval_fact(
        self,
        db_session: AsyncSession,
        data: dict = ADMIN_BODY,
    ) -> Response[dict]:
        team_id = require_session_tenant_id(db_session)
        payload = await _normalize_energy_interval_fact_data(db_session, data)
        exists = await db_session.scalar(
            select(m.EnergyIntervalFact.id).where(
                m.EnergyIntervalFact.team_id == team_id,
                m.EnergyIntervalFact.source_system == payload["source_system"],
                m.EnergyIntervalFact.source_record_id == payload["source_record_id"],
                m.EnergyIntervalFact.revision_no == 1,
            )
        )
        if exists is not None:
            raise ClientException(detail="同一数据来源和记录编码已存在", status_code=400)
        obj = m.EnergyIntervalFact(team_id=team_id, revision_no=1, is_current=True, **payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "创建成功", "data": _energy_interval_fact_payload(obj)})

    @patch("/api/energy/interval-facts/{record_id:int}", guards=[requires_superuser])
    async def update_energy_interval_fact(
        self,
        db_session: AsyncSession,
        record_id: int,
        data: dict = ADMIN_BODY,
    ) -> Response[dict]:
        team_id = require_session_tenant_id(db_session)
        obj = await db_session.get(m.EnergyIntervalFact, record_id)
        if obj is None or obj.team_id != team_id:
            raise NotFoundException(detail="记录不存在")
        payload = await _normalize_energy_interval_fact_data(db_session, data)
        duplicate = await db_session.scalar(
            select(m.EnergyIntervalFact.id).where(
                m.EnergyIntervalFact.team_id == team_id,
                m.EnergyIntervalFact.source_system == payload["source_system"],
                m.EnergyIntervalFact.source_record_id == payload["source_record_id"],
                m.EnergyIntervalFact.revision_no == obj.revision_no,
                m.EnergyIntervalFact.id != obj.id,
            )
        )
        if duplicate is not None:
            raise ClientException(detail="同一数据来源和记录编码已存在", status_code=400)
        for field, value in payload.items():
            setattr(obj, field, value)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "更新成功", "data": _energy_interval_fact_payload(obj)})

    @delete("/api/energy/interval-facts/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_energy_interval_fact(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        team_id = require_session_tenant_id(db_session)
        obj = await db_session.get(m.EnergyIntervalFact, record_id)
        if obj is None or obj.team_id != team_id:
            raise NotFoundException(detail="记录不存在")
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/energy/consumption/facts")
    async def list_energy_consumption_facts(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        energy_type_code: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        status: str | None = "approved",
        area_id: str | None = None,
        area_keyword: str | None = None,
        source_record_type: str | None = None,
        keyword: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "period_start",
        sort_order: str = "desc",
    ) -> Response[dict]:
        data = await EnergyConsumptionQueryService(db_session).facts(
            EnergyConsumptionQuery(
                period_start=period_start,
                period_end=period_end,
                energy_type_code=energy_type_code,
                scope=scope_filter,
                status=status,
                area_id=area_id,
                area_keyword=area_keyword,
                source_record_type=source_record_type,
                keyword=keyword,
                limit=limit,
                offset=offset,
                sort_field=sort_field,
                sort_order=sort_order,
            )
        )
        return Response(content=data)

    @get("/api/energy/consumption/summary")
    async def get_energy_consumption_summary(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        energy_type_code: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        status: str | None = "approved",
        area_id: str | None = None,
        area_keyword: str | None = None,
        source_record_type: str | None = None,
        keyword: str | None = None,
        group_by: str = "energy_type",
    ) -> Response[dict]:
        payload = await EnergyConsumptionQueryService(db_session).summary(
            EnergyConsumptionQuery(
                period_start=period_start,
                period_end=period_end,
                energy_type_code=energy_type_code,
                scope=scope_filter,
                status=status,
                area_id=area_id,
                area_keyword=area_keyword,
                source_record_type=source_record_type,
                keyword=keyword,
                group_by=group_by,
            )
        )
        return Response(content=payload)

    @get("/api/energy/consumption/export")
    async def export_energy_consumption(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        energy_type_code: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        status: str | None = "approved",
        area_id: str | None = None,
        area_keyword: str | None = None,
        source_record_type: str | None = None,
        keyword: str | None = None,
    ) -> Response[str]:
        rows = await EnergyConsumptionQueryService(db_session).export_rows(
            EnergyConsumptionQuery(
                period_start=period_start,
                period_end=period_end,
                energy_type_code=energy_type_code,
                scope=scope_filter,
                status=status,
                area_id=area_id,
                area_keyword=area_keyword,
                source_record_type=source_record_type,
                keyword=keyword,
            )
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(ENERGY_CONSUMPTION_EXPORT_HEADERS)
        for item in rows:
            writer.writerow([item.get(header) for header in ENERGY_CONSUMPTION_EXPORT_HEADERS])
        return Response(
            content="\ufeff" + output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"content-disposition": 'attachment; filename="energy_consumption.csv"'},
        )


def _energy_interval_fact_payload(row: m.EnergyIntervalFact) -> dict:
    return {
        "id": row.id,
        "source_system": row.source_system,
        "source_record_id": row.source_record_id,
        "energy_type_code": row.energy_type_code,
        "equipment_id": row.equipment_id,
        "equipment_code": row.equipment_code,
        "equipment_name": row.equipment_name,
        "area_id": row.area_id,
        "area_name": row.area_name,
        "use_system_code": row.use_system_code,
        "use_system_name": row.use_system_name,
        "granularity": row.granularity,
        "period_start": row.period_start.isoformat() if row.period_start else None,
        "period_end": row.period_end.isoformat() if row.period_end else None,
        "amount": float(row.amount) if row.amount is not None else None,
        "unit": row.unit,
        "cost_cny": float(row.cost_cny) if row.cost_cny is not None else None,
        "tariff_segment_type": row.tariff_segment_type,
        "reading_count": row.reading_count,
        "data_quality": row.data_quality,
        "revision_no": row.revision_no,
        "is_current": row.is_current,
        "remark": row.remark,
    }


async def _normalize_energy_interval_fact_data(db_session: AsyncSession, data: dict) -> dict:
    source_system = _text(data.get("source_system")) or "manual_entry"
    source_record_id = _required_text(data, "source_record_id")
    energy_type_code = canonicalize_energy_type_code(_required_text(data, "energy_type_code"))
    if not energy_type_code:
        raise ClientException(detail="能源种类不能为空", status_code=400)
    period_start = _parse_datetime(data.get("period_start"), field_name="period_start")
    period_end = _parse_datetime(data.get("period_end") or data.get("period_start"), field_name="period_end")
    if period_end < period_start:
        raise ClientException(detail="结束时间不能早于开始时间", status_code=400)
    equipment_id = _int_or_none(data.get("equipment_id"))
    area_id = _nullable_text(data.get("area_id"))
    equipment_code = _nullable_text(data.get("equipment_code"))
    equipment_name = _nullable_text(data.get("equipment_name"))
    area_name = _nullable_text(data.get("area_name"))
    if equipment_id is not None:
        equipment = await db_session.get(m.MonitorEquipment, equipment_id)
        if equipment is None:
            raise ClientException(detail="选择的设备不存在", status_code=400)
        equipment_code = equipment.code
        equipment_name = equipment.name
        if not area_id and equipment.sector_id is not None:
            area_id = str(equipment.sector_id)
    if area_id and area_id.isdigit():
        area = await db_session.get(m.MonitorSector, int(area_id))
        if area is None:
            raise ClientException(detail="选择的区域不存在", status_code=400)
        area_name = area.name

    return {
        "source_system": source_system,
        "source_record_id": source_record_id,
        "energy_type_code": energy_type_code,
        "equipment_id": equipment_id,
        "equipment_code": equipment_code,
        "equipment_name": equipment_name,
        "area_id": area_id,
        "area_name": area_name,
        "use_system_code": _nullable_text(data.get("use_system_code")),
        "use_system_name": _nullable_text(data.get("use_system_name")),
        "granularity": _text(data.get("granularity")) or "month",
        "period_start": period_start,
        "period_end": period_end,
        "amount": _required_decimal(data, "amount"),
        "unit": _text(data.get("unit")) or "kWh",
        "cost_cny": _decimal_or_none(data.get("cost_cny")),
        "tariff_segment_type": _nullable_text(data.get("tariff_segment_type")),
        "reading_count": _int_or_none(data.get("reading_count")),
        "data_quality": _data_quality(data.get("data_quality")),
        "remark": _nullable_text(data.get("remark")),
    }


def _parse_datetime(value: object, *, field_name: str) -> datetime:
    text_value = _text(value)
    if not text_value:
        raise ClientException(detail=f"缺少时间字段 {field_name}", status_code=400)
    if len(text_value) == YEAR_MONTH_LENGTH:
        text_value = f"{text_value}-01T00:00:00"
    elif len(text_value) == DATE_LENGTH:
        text_value = f"{text_value}T00:00:00"
    try:
        return datetime.fromisoformat(text_value.replace(" ", "T"))
    except ValueError as exc:
        raise ClientException(detail=f"时间字段格式不正确: {field_name}", status_code=400) from exc


def _required_text(data: dict, field_name: str) -> str:
    value = _text(data.get(field_name))
    if not value:
        raise ClientException(detail=f"缺少必填字段 {field_name}", status_code=400)
    return value


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _nullable_text(value: object) -> str | None:
    text_value = _text(value)
    return text_value or None


def _decimal_or_none(value: object) -> Decimal | None:
    text_value = _text(value)
    if not text_value:
        return None
    try:
        return Decimal(text_value.replace(",", ""))
    except InvalidOperation as exc:
        raise ClientException(detail="数值字段格式不正确", status_code=400) from exc


def _required_decimal(data: dict, field_name: str) -> Decimal:
    value = _decimal_or_none(data.get(field_name))
    if value is None:
        raise ClientException(detail=f"缺少必填数值 {field_name}", status_code=400)
    return value


def _int_or_none(value: object) -> int | None:
    text_value = _text(value)
    if not text_value:
        return None
    try:
        return int(text_value)
    except ValueError as exc:
        raise ClientException(detail="整数字段格式不正确", status_code=400) from exc


def _data_quality(value: object) -> str:
    text_value = _text(value) or "measured"
    allowed = {"measured", "manual", "imported", "estimated"}
    if text_value not in allowed:
        raise ClientException(detail="数据质量必须为 measured/manual/imported/estimated", status_code=400)
    return text_value
