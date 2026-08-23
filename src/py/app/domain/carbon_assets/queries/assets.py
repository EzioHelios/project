"""Read models for the carbon asset workbench."""

from __future__ import annotations

# ruff: noqa: EM101, TRY003
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import desc, func, select

from app.db import models as m
from app.domain.carbon_assets.domain.policies import calculate_compliance_position

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class AssetQuery:
    instrument_id: int | None = None
    account_id: int | None = None
    lot_id: int | None = None
    cycle_id: int | None = None
    status: str | None = None
    instrument_class: str | None = None
    keyword: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    limit: int = 50
    offset: int = 0


class CarbonAssetQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def page(self, model: type[Any], query: AssetQuery) -> dict[str, Any]:
        conditions: list[Any] = []
        if query.status and hasattr(model, "status"):
            conditions.append(model.status == query.status)
        for field in ("instrument_id", "account_id", "lot_id", "cycle_id"):
            value = getattr(query, field)
            if value is not None and hasattr(model, field):
                conditions.append(getattr(model, field) == value)
        if query.instrument_class and hasattr(model, "instrument_class"):
            conditions.append(model.instrument_class == query.instrument_class)
        date_field = next(
            (getattr(model, field) for field in ("trade_date", "occurred_on", "usage_date") if hasattr(model, field)),
            None,
        )
        if query.date_from and date_field is not None:
            conditions.append(date_field >= query.date_from)
        if query.date_to and date_field is not None:
            conditions.append(date_field <= query.date_to)
        if query.keyword:
            text_fields = [name for name in ("code", "name", "account_code", "account_name", "lot_no", "cycle_code", "cycle_name", "scenario_code", "scenario_name") if hasattr(model, name)]
            if text_fields:
                conditions.append(func.concat_ws(" ", *[getattr(model, field) for field in text_fields]).ilike(f"%{query.keyword.strip()}%"))
        base = select(model).where(*conditions)
        total = int(await self.session.scalar(select(func.count()).select_from(base.subquery())) or 0)
        order_col = getattr(model, "created_at", model.id)
        rows = list((await self.session.scalars(base.order_by(desc(order_col)).limit(query.limit).offset(query.offset))).all())
        return {"items": [model_payload(row) for row in rows], "total": total, "limit": query.limit, "offset": query.offset}

    async def lot_balance(self, lot_id: int) -> Decimal:
        lot = await self.session.get(m.CarbonAssetLot, lot_id)
        if lot is None:
            raise ValueError("asset lot not found")
        movements = await self.session.scalar(
            select(func.coalesce(func.sum(m.CarbonAssetMovement.quantity_delta), 0)).where(m.CarbonAssetMovement.lot_id == lot_id)
        )
        return Decimal(lot.issued_quantity) + Decimal(movements or 0)

    async def balances(self) -> list[dict[str, Any]]:
        issued = (
            select(m.CarbonAssetLot.instrument_id, func.sum(m.CarbonAssetLot.issued_quantity).label("issued"))
            .group_by(m.CarbonAssetLot.instrument_id)
            .subquery()
        )
        delta = (
            select(m.CarbonAssetMovement.instrument_id, func.sum(m.CarbonAssetMovement.quantity_delta).label("delta"))
            .group_by(m.CarbonAssetMovement.instrument_id)
            .subquery()
        )
        stmt = (
            select(
                m.CarbonAssetInstrument.id,
                m.CarbonAssetInstrument.code,
                m.CarbonAssetInstrument.name,
                m.CarbonAssetInstrument.instrument_class,
                m.CarbonAssetInstrument.native_unit,
                func.coalesce(issued.c.issued, 0).label("issued"),
                func.coalesce(delta.c.delta, 0).label("delta"),
            )
            .outerjoin(issued, issued.c.instrument_id == m.CarbonAssetInstrument.id)
            .outerjoin(delta, delta.c.instrument_id == m.CarbonAssetInstrument.id)
            .order_by(m.CarbonAssetInstrument.instrument_class)
        )
        rows = (await self.session.execute(stmt)).all()
        result: list[dict[str, Any]] = []
        for row in rows:
            balance = Decimal(row.issued or 0) + Decimal(row.delta or 0)
            result.append({"instrumentId": row.id, "code": row.code, "name": row.name, "instrumentClass": row.instrument_class, "nativeUnit": row.native_unit, "balance": float(balance)})
        return result

    async def latest_quotes(self) -> list[dict[str, Any]]:
        ranked = (
            select(m.CarbonMarketQuote.id, func.row_number().over(partition_by=m.CarbonMarketQuote.instrument_id, order_by=m.CarbonMarketQuote.trade_date.desc()).label("rn"))
            .subquery()
        )
        rows: list[m.CarbonMarketQuote] = list((await self.session.scalars(select(m.CarbonMarketQuote).join(ranked, ranked.c.id == m.CarbonMarketQuote.id).where(ranked.c.rn == 1))).all())
        return [model_payload(row) for row in rows]

    async def compliance_position(self, cycle_id: int | None = None) -> dict[str, Any] | None:
        cycle = await self.session.get(m.CarbonComplianceCycle, cycle_id) if cycle_id else await self.session.scalar(
            select(m.CarbonComplianceCycle).where(m.CarbonComplianceCycle.status.in_(("draft", "open"))).order_by(m.CarbonComplianceCycle.period_end.desc()).limit(1)
        )
        if cycle is None:
            return None
        rule = await self.session.get(m.CarbonComplianceRuleVersion, cycle.rule_version_id)
        if rule is None:
            raise ValueError("compliance rule not found")
        balances = {row["instrumentClass"]: Decimal(str(row["balance"])) for row in await self.balances()}
        position = calculate_compliance_position(
            obligation_tco2e=Decimal(cycle.required_surrender_tco2e),
            cea_available_tco2e=balances.get("CEA", Decimal(0)),
            ccer_available_tco2e=balances.get("CCER", Decimal(0)),
            max_offset_ratio=Decimal(rule.max_offset_ratio),
        )
        return {"cycle": model_payload(cycle), "position": {key: float(value) for key, value in asdict(position).items()}}

    async def overview(self) -> dict[str, Any]:
        balances = await self.balances()
        quotes = await self.latest_quotes()
        quote_by_instrument = {int(row["instrumentId"]): Decimal(str(row["closePrice"])) for row in quotes}
        valued_balances: list[dict[str, Any]] = []
        for row in balances:
            market_price = quote_by_instrument.get(int(row["instrumentId"]), Decimal(0))
            market_value = Decimal(str(row["balance"])) * market_price
            valued_balances.append(
                {
                    **row,
                    "marketPrice": float(market_price),
                    "marketValueCny": float(market_value),
                }
            )
        portfolio_value = sum(Decimal(str(row["marketValueCny"])) for row in valued_balances)
        movements = list((await self.session.scalars(select(m.CarbonAssetMovement).order_by(m.CarbonAssetMovement.posted_at.desc()).limit(8))).all())
        compliance = await self.compliance_position()
        return {
            "balances": valued_balances,
            "portfolioValueCny": float(portfolio_value),
            "activeCycle": compliance["cycle"] if compliance else None,
            "compliancePosition": compliance["position"] if compliance else None,
            "latestQuotes": quotes,
            "recentMovements": [model_payload(row) for row in movements],
        }


def model_payload(row: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, (date, datetime)):
            value = value.isoformat()
        key = "".join(word.capitalize() if index else word for index, word in enumerate(column.name.split("_")))
        result[key] = value
    return result
