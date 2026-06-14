"""碳核算引擎：活动量 × 排放因子 = CO₂e 排放量（参考 xtck_deploy dataapp/services/emission_calculator.py）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.carbon.models import EmissionFactor

logger = logging.getLogger(__name__)


FACTOR_SUB_CATEGORY_ALIASES: dict[tuple[str, str, str], tuple[str, ...]] = {
    ("scope1", "fuel", "天然气"): ("natural_gas",),
    ("scope1", "fuel", "燃气"): ("natural_gas",),
    ("scope3", "waste", "废铝渣"): ("铝渣",),
}

FACTOR_UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "m3": ("m³", "Nm³", "nm3"),
    "m³": ("m3", "Nm³", "nm3"),
    "nm3": ("Nm³", "m3", "m³"),
}


@dataclass
class EmissionComputation:
    """Resolved factor plus computed CO2e payload."""

    co2e: Decimal
    scope: str
    category: str
    sub_category: str
    activity_amount: Decimal
    activity_unit: str
    factor_value: Decimal
    factor_unit: str
    factor_year: int
    factor_source: str


async def resolve_emission_factor(
    session: AsyncSession,
    scope: str,
    category: str,
    sub_category: str,
    unit: str,
    year: int | None = None,
) -> EmissionFactor | None:
    """Resolve a matching emission factor row for the requested activity."""
    preferred_sub_categories = _preferred_sub_categories(scope, category, sub_category)
    if scope == "scope2" and category == "electricity" and sub_category == "grid_electricity":
        preferred_sub_categories = [
            "grid_electricity_jiangsu",
            "grid_electricity_national",
            "grid_electricity",
        ]
    preferred_units = _preferred_units(unit)

    sub_category_rank = case(
        *[(EmissionFactor.sub_category == candidate, index) for index, candidate in enumerate(preferred_sub_categories)],
        else_=len(preferred_sub_categories),
    )

    base_stmt = (
        select(EmissionFactor)
        .where(
            EmissionFactor.scope == scope,
            EmissionFactor.category == category,
            EmissionFactor.sub_category.in_(preferred_sub_categories),
            EmissionFactor.unit.in_(preferred_units),
            EmissionFactor.is_active.is_(True),
        )
        .order_by(sub_category_rank.asc(), EmissionFactor.year.desc(), EmissionFactor.id.desc())
    )

    if year is not None:
        exact_stmt = base_stmt.where(EmissionFactor.year == year)
        exact_result = await session.execute(exact_stmt)
        exact_factor = exact_result.scalars().first()
        if exact_factor is not None:
            return exact_factor

    result = await session.execute(base_stmt)
    return result.scalars().first()


def _preferred_sub_categories(scope: str, category: str, sub_category: str) -> list[str]:
    aliases = FACTOR_SUB_CATEGORY_ALIASES.get((scope, category, sub_category), ())
    return list(dict.fromkeys((sub_category, *aliases)))


def _preferred_units(unit: str) -> list[str]:
    aliases = FACTOR_UNIT_ALIASES.get(unit, ())
    return list(dict.fromkeys((unit, *aliases)))


async def calc_co2e(
    session: AsyncSession,
    scope: str,
    category: str,
    sub_category: str,
    activity_amount: float | Decimal | int,
    unit: str,
    year: int | None = None,
) -> Decimal | None:
    """查询排放因子库并计算 CO₂e 排放量。

    Args:
        session: 数据库会话
        scope: scope1 / scope2 / scope3
        category: fuel / electricity / refrigerant / waste / transport
        sub_category: 与模型枚举一致，如 diesel_0 / R22 / waste_paper
        activity_amount: 活动量数值
        unit: 活动量单位，如 L / kg / kWh / t
        year: 数据年份，默认取因子库最新年份

    Returns:
        CO₂e 数值（kg），未找到因子时返回 None
    """
    factor = await resolve_emission_factor(session, scope, category, sub_category, unit, year)
    if factor is None:
        logger.warning(
            "未找到排放因子: scope=%s category=%s sub_category=%s unit=%s year=%s",
            scope, category, sub_category, unit, year,
        )
        return None
    amount = Decimal(str(activity_amount))
    co2e = amount * factor.factor_value
    logger.info(
        "碳核算: %s%s × %s %s = %s kgCO₂e [%s]",
        activity_amount, unit, factor.factor_value, factor.factor_unit, co2e, factor.source,
    )
    return co2e


async def compute_emission_result(
    session: AsyncSession,
    scope: str,
    category: str,
    sub_category: str,
    activity_amount: float | Decimal | int,
    unit: str,
    year: int | None = None,
) -> EmissionComputation | None:
    """Resolve factor and return the full computation payload."""
    factor = await resolve_emission_factor(session, scope, category, sub_category, unit, year)
    if factor is None:
        return None
    amount = Decimal(str(activity_amount))
    co2e = amount * factor.factor_value
    return EmissionComputation(
        co2e=co2e,
        scope=scope,
        category=category,
        sub_category=sub_category,
        activity_amount=amount,
        activity_unit=unit,
        factor_value=factor.factor_value,
        factor_unit=factor.factor_unit,
        factor_year=factor.year,
        factor_source=factor.source,
    )


async def calc_scope1_fuel(
    session: AsyncSession,
    fuel_type: str,
    amount: float | Decimal,
    unit: str,
    year: int | None = None,
) -> Decimal | None:
    """Scope 1：燃料燃烧"""
    return await calc_co2e(session, "scope1", "fuel", fuel_type, amount, unit, year)


async def calc_scope1_refrigerant(
    session: AsyncSession,
    refrigerant_type: str,
    amount_kg: float | Decimal,
    year: int | None = None,
) -> Decimal | None:
    """Scope 1：制冷剂逸散"""
    return await calc_co2e(session, "scope1", "refrigerant", refrigerant_type, amount_kg, "kg", year)


async def calc_scope2_electricity(
    session: AsyncSession,
    kwh: float | Decimal,
    year: int | None = None,
) -> Decimal | None:
    """Scope 2：网购电力"""
    return await calc_co2e(session, "scope2", "electricity", "grid_electricity", kwh, "kWh", year)


async def calc_scope3_waste(
    session: AsyncSession,
    waste_category: str,
    weight_ton: float | Decimal,
    year: int | None = None,
) -> Decimal | None:
    """Scope 3：废弃物"""
    return await calc_co2e(session, "scope3", "waste", waste_category, weight_ton, "t", year)


async def calc_scope3_transport(
    session: AsyncSession,
    vehicle_type: str,
    distance_km: float | Decimal,
    load_ton: float | Decimal,
    year: int | None = None,
) -> Decimal | None:
    """Scope 3：外购运输（吨公里法）"""
    ton_km = Decimal(str(distance_km)) * Decimal(str(load_ton))
    return await calc_co2e(session, "scope3", "transport", vehicle_type, ton_km, "t·km", year)
