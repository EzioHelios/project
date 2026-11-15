from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING
from uuid import uuid4

from litestar.exceptions import ClientException
from sqlalchemy import select

from app.db import models as m
from app.domain.energy.usecases.energy_types import canonicalize_energy_type_code
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

YEAR_MONTH_LENGTH = 7
DATE_LENGTH = 10


async def _normalize_energy_interval_fact_data(db_session: AsyncSession, data: dict) -> dict:
    source_system = _text(data.get("source_system")) or "manual_entry"
    source_record_id = _text(data.get("source_record_id")) or f"ENTRY-{uuid4().hex}"
    energy_value = _text(data.get("energy_type_code") or data.get("energy_type_name"))
    energy_code = canonicalize_energy_type_code(energy_value)
    energy_type = await db_session.scalar(select(m.EnergyType).where(m.EnergyType.code == energy_code))
    if energy_type is None:
        matches = list((await db_session.scalars(select(m.EnergyType).where(m.EnergyType.name == energy_value))).all())
        if len(matches) != 1:
            raise ClientException(detail="请选择有效的能源种类", status_code=400)
        energy_type = matches[0]
    energy_type_code = energy_type.code
    unit = _text(data.get("unit")) or energy_type.original_unit
    allowed_units = set(
        (
            await db_session.scalars(
                select(m.EnergyUnitConversion.from_unit).where(
                    m.EnergyUnitConversion.energy_type_code == energy_type_code,
                    m.EnergyUnitConversion.is_enabled.is_(True),
                )
            )
        ).all()
    )
    allowed_units.add(energy_type.original_unit)
    if not unit or unit not in allowed_units:
        raise ClientException(detail="单位不适用于所选能源。请选择已配置的计量单位", status_code=400)
    period_start = _parse_datetime(data.get("period_start"), field_name="period_start")
    period_end = _parse_datetime(data.get("period_end") or data.get("period_start"), field_name="period_end")
    if period_end < period_start:
        raise ClientException(detail="结束时间不能早于开始时间", status_code=400)
    objects = await _resolve_objects(db_session, data)
    amount = _required_decimal(data, "amount")
    cost_cny = _decimal_or_none(data.get("cost_cny"))
    if amount < 0 or (cost_cny is not None and cost_cny < 0):
        raise ClientException(detail="能源用量和费用不能为负数", status_code=400)

    return {
        "source_system": source_system,
        "source_record_id": source_record_id,
        "energy_type_code": energy_type_code,
        **objects,
        "use_system_code": _nullable_text(data.get("use_system_code")),
        "use_system_name": _nullable_text(data.get("use_system_name")),
        "granularity": _text(data.get("granularity")) or "month",
        "period_start": period_start,
        "period_end": period_end,
        "amount": amount,
        "unit": unit,
        "cost_cny": cost_cny,
        "tariff_segment_type": _nullable_text(data.get("tariff_segment_type")),
        "reading_count": _int_or_none(data.get("reading_count")),
        "data_quality": _data_quality(data.get("data_quality")),
        "remark": _nullable_text(data.get("remark")),
    }


async def _resolve_objects(db_session: AsyncSession, data: dict) -> dict:
    team_id = require_session_tenant_id(db_session)
    equipment_id = _int_or_none(data.get("equipment_id"))
    area_id = _nullable_text(data.get("area_id"))
    equipment_code = _nullable_text(data.get("equipment_code"))
    equipment_name = _nullable_text(data.get("equipment_name"))
    area_name = _nullable_text(data.get("area_name"))
    if area_id:
        area = await db_session.scalar(
            select(m.MonitorSector).where(
                m.MonitorSector.team_id == team_id,
                m.MonitorSector.id == _int_or_none(area_id),
            )
        )
        if area is None:
            raise ClientException(detail="选择的区域不存在", status_code=400)
        area_name = area.name
    elif area_name:
        areas = list(
            (
                await db_session.scalars(
                    select(m.MonitorSector).where(
                        m.MonitorSector.team_id == team_id,
                        m.MonitorSector.name == area_name,
                    )
                )
            ).all()
        )
        if len(areas) != 1:
            raise ClientException(detail="区域名称不存在或不唯一。请选择区域", status_code=400)
        area_id = str(areas[0].id)
    equipment = None
    if equipment_id is not None or equipment_code or equipment_name:
        conditions = [m.MonitorEquipment.team_id == team_id]
        if equipment_id is not None:
            conditions.append(m.MonitorEquipment.id == equipment_id)
        elif equipment_code:
            conditions.append(m.MonitorEquipment.code == equipment_code)
        else:
            conditions.append(m.MonitorEquipment.name == equipment_name)
            if area_id:
                conditions.append(m.MonitorEquipment.sector_id == int(area_id))
        devices = list((await db_session.scalars(select(m.MonitorEquipment).where(*conditions))).all())
        if len(devices) != 1:
            raise ClientException(detail="设备不存在或名称不唯一。请选择所属区域及设备", status_code=400)
        equipment = devices[0]
        equipment_id, equipment_code, equipment_name = equipment.id, equipment.code, equipment.name
        if area_id and equipment.sector_id is not None and int(area_id) != equipment.sector_id:
            raise ClientException(detail="设备不属于所选区域", status_code=400)
        if not area_id and equipment.sector_id is not None:
            area = await db_session.scalar(
                select(m.MonitorSector).where(
                    m.MonitorSector.team_id == team_id,
                    m.MonitorSector.id == equipment.sector_id,
                )
            )
            if area is None:
                raise ClientException(detail="设备所属区域不存在", status_code=400)
            area_id, area_name = str(area.id), area.name
    return {
        "equipment_id": equipment_id,
        "equipment_code": equipment_code,
        "equipment_name": equipment_name,
        "area_id": area_id,
        "area_name": area_name,
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
        value = Decimal(text_value.replace(",", ""))
    except InvalidOperation as exc:
        raise ClientException(detail="数值字段格式不正确", status_code=400) from exc
    if not value.is_finite():
        raise ClientException(detail="数值必须为有限数字", status_code=400)
    return value


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
    allowed = {"measured", "manual", "imported", "estimated", "generated", "provisional"}
    if text_value not in allowed:
        raise ClientException(detail="数据质量值无效", status_code=400)
    return text_value
