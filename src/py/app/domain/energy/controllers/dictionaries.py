from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from litestar import Controller, delete, get, patch, post
from litestar.exceptions import ClientException, NotFoundException
from litestar.params import Body, Parameter
from litestar.response import Response
from sqlalchemy import func, or_, select, text

from app.db import models as m
from app.domain.accounts.guards import requires_superuser
from app.domain.carbon.deps import provide_energy_type_service
from app.domain.energy.controllers._utils import model_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

ADMIN_BODY = Body()
ENERGY_TYPE_SORT_FIELDS = {
    "id",
    "code",
    "name",
    "category",
    "default_scope",
    "original_unit",
    "standard_unit",
    "standard_factor",
    "standard_code",
    "is_enabled",
}
UNIT_CONVERSION_SORT_FIELDS = {
    "id",
    "energy_type_code",
    "from_unit",
    "to_unit",
    "multiply_factor",
    "standard_code",
    "is_default",
    "is_enabled",
}


class EnergyDictionaryController(Controller):
    tags = ["Energy"]
    dependencies = {"energy_type_service": provide_energy_type_service}

    @get("/api/energy/types")
    async def list_energy_types(
        self,
        db_session: AsyncSession,
        category: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        include_disabled: bool = False,
        keyword: str | None = None,
        search: str | None = None,
        limit: int = 200,
        offset: int = 0,
        sort_field: str = "default_scope",
        sort_order: str = "asc",
    ) -> Response[dict]:
        conditions = []
        if category:
            conditions.append(m.EnergyType.category == category)
        if scope_filter:
            conditions.append(m.EnergyType.default_scope == scope_filter)
        if not include_disabled:
            conditions.append(m.EnergyType.is_enabled.is_(True))
        query_text = (keyword or search or "").strip()
        if query_text:
            pattern = f"%{query_text}%"
            conditions.append(
                or_(
                    m.EnergyType.code.ilike(pattern),
                    m.EnergyType.name.ilike(pattern),
                    m.EnergyType.category.ilike(pattern),
                    m.EnergyType.default_scope.ilike(pattern),
                    m.EnergyType.standard_code.ilike(pattern),
                )
            )
        limit_clamped = max(1, min(limit, 500))
        offset_clamped = max(0, offset)
        order_column = getattr(m.EnergyType, sort_field if sort_field in ENERGY_TYPE_SORT_FIELDS else "default_scope")
        order_by = order_column.desc() if sort_order == "desc" else order_column.asc()
        total = int(
            await db_session.scalar(
                select(func.count()).select_from(m.EnergyType).where(*(conditions or [text("1=1")]))
            )
            or 0
        )
        rows = (
            (
                await db_session.execute(
                    select(m.EnergyType)
                    .where(*(conditions or [text("1=1")]))
                    .order_by(order_by, m.EnergyType.category.asc(), m.EnergyType.id.asc())
                    .limit(limit_clamped)
                    .offset(offset_clamped)
                )
            )
            .scalars()
            .all()
        )
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "items": [model_to_dict(row) for row in rows],
                    "total": total,
                    "limit": limit_clamped,
                    "offset": offset_clamped,
                },
            }
        )

    @post("/api/energy/types", guards=[requires_superuser])
    async def create_energy_type(self, db_session: AsyncSession, data: dict = ADMIN_BODY) -> Response[dict]:
        payload = _normalize_energy_type_payload(data)
        exists = await db_session.scalar(select(m.EnergyType.id).where(m.EnergyType.code == payload["code"]))
        if exists is not None:
            raise ClientException(detail="能源种类编码已存在", status_code=400)
        obj = m.EnergyType(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/energy/types/{record_id:int}", guards=[requires_superuser])
    async def update_energy_type(
        self, db_session: AsyncSession, record_id: int, data: dict = ADMIN_BODY
    ) -> Response[dict]:
        obj = await db_session.get(m.EnergyType, record_id)
        if obj is None:
            raise NotFoundException(detail="能源种类不存在")
        payload = _normalize_energy_type_payload(data)
        duplicate = await db_session.scalar(
            select(m.EnergyType.id).where(m.EnergyType.code == payload["code"], m.EnergyType.id != obj.id)
        )
        if duplicate is not None:
            raise ClientException(detail="能源种类编码已存在", status_code=400)
        for field, value in payload.items():
            setattr(obj, field, value)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "更新成功", "data": model_to_dict(obj)})

    @delete("/api/energy/types/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_energy_type(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        obj = await db_session.get(m.EnergyType, record_id)
        if obj is None:
            raise NotFoundException(detail="能源种类不存在")
        in_use = int(
            await db_session.scalar(
                select(func.count())
                .select_from(m.EnergyIntervalFact)
                .where(m.EnergyIntervalFact.energy_type_code == obj.code)
            )
            or 0
        )
        if in_use > 0:
            raise ClientException(detail="能源种类已被能源数据使用, 请停用或调整后再删除", status_code=400)
        await db_session.execute(
            m.EnergyUnitConversion.__table__.delete().where(m.EnergyUnitConversion.energy_type_code == obj.code)
        )
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/energy/unit-conversions")
    async def list_energy_unit_conversions(
        self,
        db_session: AsyncSession,
        energy_type_code: str | None = None,
        include_disabled: bool = False,
        keyword: str | None = None,
        search: str | None = None,
        limit: int = 200,
        offset: int = 0,
        sort_field: str = "energy_type_code",
        sort_order: str = "asc",
    ) -> Response[dict]:
        conditions = []
        if energy_type_code:
            conditions.append(m.EnergyUnitConversion.energy_type_code == energy_type_code)
        if not include_disabled:
            conditions.append(m.EnergyUnitConversion.is_enabled.is_(True))
        query_text = (keyword or search or "").strip()
        if query_text:
            pattern = f"%{query_text}%"
            conditions.append(
                or_(
                    m.EnergyUnitConversion.energy_type_code.ilike(pattern),
                    m.EnergyUnitConversion.from_unit.ilike(pattern),
                    m.EnergyUnitConversion.to_unit.ilike(pattern),
                    m.EnergyUnitConversion.standard_code.ilike(pattern),
                    m.EnergyUnitConversion.conversion_factor_source.ilike(pattern),
                )
            )
        limit_clamped = max(1, min(limit, 500))
        offset_clamped = max(0, offset)
        order_column = getattr(
            m.EnergyUnitConversion,
            sort_field if sort_field in UNIT_CONVERSION_SORT_FIELDS else "energy_type_code",
        )
        order_by = order_column.desc() if sort_order == "desc" else order_column.asc()
        total = int(
            await db_session.scalar(
                select(func.count()).select_from(m.EnergyUnitConversion).where(*(conditions or [text("1=1")]))
            )
            or 0
        )
        rows = (
            (
                await db_session.execute(
                    select(m.EnergyUnitConversion)
                    .where(*(conditions or [text("1=1")]))
                    .order_by(
                        order_by,
                        m.EnergyUnitConversion.from_unit.asc(),
                        m.EnergyUnitConversion.to_unit.asc(),
                    )
                    .limit(limit_clamped)
                    .offset(offset_clamped)
                )
            )
            .scalars()
            .all()
        )
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "items": [model_to_dict(row) for row in rows],
                    "total": total,
                    "limit": limit_clamped,
                    "offset": offset_clamped,
                },
            }
        )

    @post("/api/energy/unit-conversions", guards=[requires_superuser])
    async def create_energy_unit_conversion(self, db_session: AsyncSession, data: dict = ADMIN_BODY) -> Response[dict]:
        payload = _normalize_unit_conversion_payload(data)
        await _ensure_energy_type_exists(db_session, payload["energy_type_code"])
        exists = await db_session.scalar(
            select(m.EnergyUnitConversion.id).where(
                m.EnergyUnitConversion.energy_type_code == payload["energy_type_code"],
                m.EnergyUnitConversion.from_unit == payload["from_unit"],
                m.EnergyUnitConversion.to_unit == payload["to_unit"],
            )
        )
        if exists is not None:
            raise ClientException(detail="同一能源种类和单位换算已存在", status_code=400)
        obj = m.EnergyUnitConversion(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/energy/unit-conversions/{record_id:int}", guards=[requires_superuser])
    async def update_energy_unit_conversion(
        self, db_session: AsyncSession, record_id: int, data: dict = ADMIN_BODY
    ) -> Response[dict]:
        obj = await db_session.get(m.EnergyUnitConversion, record_id)
        if obj is None:
            raise NotFoundException(detail="单位换算不存在")
        payload = _normalize_unit_conversion_payload(data)
        await _ensure_energy_type_exists(db_session, payload["energy_type_code"])
        duplicate = await db_session.scalar(
            select(m.EnergyUnitConversion.id).where(
                m.EnergyUnitConversion.energy_type_code == payload["energy_type_code"],
                m.EnergyUnitConversion.from_unit == payload["from_unit"],
                m.EnergyUnitConversion.to_unit == payload["to_unit"],
                m.EnergyUnitConversion.id != obj.id,
            )
        )
        if duplicate is not None:
            raise ClientException(detail="同一能源种类和单位换算已存在", status_code=400)
        for field, value in payload.items():
            setattr(obj, field, value)
        await db_session.commit()
        await db_session.refresh(obj)
        return Response(content={"code": 200, "msg": "更新成功", "data": model_to_dict(obj)})

    @delete("/api/energy/unit-conversions/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_energy_unit_conversion(self, db_session: AsyncSession, record_id: int) -> Response[dict]:
        obj = await db_session.get(m.EnergyUnitConversion, record_id)
        if obj is None:
            raise NotFoundException(detail="单位换算不存在")
        await db_session.delete(obj)
        await db_session.commit()
        return Response(content={"code": 200, "msg": "已删除"})


def _normalize_energy_type_payload(data: dict) -> dict:
    return {
        "code": _required_text(data, "code"),
        "name": _required_text(data, "name"),
        "category": _text(data.get("category")) or "fuel",
        "default_scope": _text(data.get("default_scope")) or "scope1",
        "original_unit": _nullable_text(data.get("original_unit")),
        "standard_unit": _nullable_text(data.get("standard_unit")) or "kgce",
        "standard_factor": _decimal_or_none(data.get("standard_factor")),
        "standard_code": _nullable_text(data.get("standard_code")),
        "conversion_factor_source": _nullable_text(data.get("conversion_factor_source")),
        "is_enabled": _bool(data.get("is_enabled"), default=True),
        "remark": _nullable_text(data.get("remark")),
    }


def _normalize_unit_conversion_payload(data: dict) -> dict:
    factor = _decimal_or_none(data.get("multiply_factor"))
    if factor is None:
        raise ClientException(detail="缺少换算系数", status_code=400)
    return {
        "energy_type_code": _required_text(data, "energy_type_code"),
        "from_unit": _required_text(data, "from_unit"),
        "to_unit": _required_text(data, "to_unit"),
        "multiply_factor": factor,
        "standard_code": _nullable_text(data.get("standard_code")),
        "conversion_factor_source": _nullable_text(data.get("conversion_factor_source")),
        "is_default": _bool(data.get("is_default"), default=False),
        "is_enabled": _bool(data.get("is_enabled"), default=True),
        "remark": _nullable_text(data.get("remark")),
    }


async def _ensure_energy_type_exists(db_session: AsyncSession, code: str) -> None:
    exists = await db_session.scalar(select(m.EnergyType.id).where(m.EnergyType.code == code))
    if exists is None:
        raise ClientException(detail="能源种类不存在", status_code=400)


def _required_text(data: dict, field_name: str) -> str:
    value = _text(data.get(field_name))
    if not value:
        raise ClientException(detail=f"缺少必填字段 {field_name}", status_code=400)
    return value


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _nullable_text(value: object) -> str | None:
    value_text = _text(value)
    return value_text or None


def _decimal_or_none(value: object) -> Decimal | None:
    value_text = _text(value)
    if not value_text:
        return None
    try:
        return Decimal(value_text.replace(",", ""))
    except InvalidOperation as exc:
        raise ClientException(detail="数值字段格式不正确", status_code=400) from exc


def _bool(value: object, *, default: bool) -> bool:
    value_text = _text(value).lower()
    if not value_text:
        return default
    return value_text in {"1", "true", "yes", "y", "启用", "是"}
