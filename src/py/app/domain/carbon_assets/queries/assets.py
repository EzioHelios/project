from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_assets.domain.policies import (
    allowance_available,
    compliance_risk_level,
    credit_available,
    forecast_position,
    inventory_position_status,
)
from app.domain.energy.controllers._utils import model_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

KG_PER_TONNE = Decimal(1000)
MAX_FORECAST_MONTHS = 60
MONTHS_PER_YEAR = 12
NON_REAL_ASSET_SOURCE_NAMES = {"enterprise_asset_rule", "enterprise_assumption", "real-company-write-validation"}
NON_REAL_ASSET_STANDARD_CODES = {"enterprise_assumption", "enterprise_asset_rule"}


@dataclass(frozen=True, slots=True)
class CarbonAssetsQuery:
    period_id: int | None = None
    scenario_id: int | None = None
    account_id: int | None = None
    asset_type: str | None = None
    status: str | None = None
    market: str | None = None
    keyword: str | None = None
    limit: int = 50
    offset: int = 0


class CarbonAssetsQueryService:
    """Read models for carbon assets and compliance positions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def periods(self, query: CarbonAssetsQuery) -> dict[str, Any]:
        conditions = []
        if query.status and query.status != "all":
            conditions.append(m.CarbonCompliancePeriod.status == query.status)
        if query.market and query.market != "all":
            conditions.append(m.CarbonCompliancePeriod.market == query.market)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append((m.CarbonCompliancePeriod.period_name.ilike(pattern)) | (m.CarbonCompliancePeriod.period_code.ilike(pattern)))
        stmt = select(m.CarbonCompliancePeriod).where(*conditions).order_by(m.CarbonCompliancePeriod.period_start.desc())
        page = await self._page(stmt, query, include_rows=True)
        page["items"] = [await self._period_payload(row) for row in page.pop("_rows")]
        page["data"] = page["items"]
        return page

    async def accounts(self, query: CarbonAssetsQuery) -> dict[str, Any]:
        conditions = []
        if query.asset_type and query.asset_type != "all":
            conditions.append(m.CarbonAssetAccount.asset_type == query.asset_type)
        if query.status and query.status != "all":
            conditions.append(m.CarbonAssetAccount.status == query.status)
        if query.market and query.market != "all":
            conditions.append(m.CarbonAssetAccount.market == query.market)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append((m.CarbonAssetAccount.account_name.ilike(pattern)) | (m.CarbonAssetAccount.account_code.ilike(pattern)))
        stmt = select(m.CarbonAssetAccount).where(*conditions).order_by(m.CarbonAssetAccount.id.desc())
        page = await self._page(stmt, query, include_rows=True)
        page["items"] = [await self._account_payload(row) for row in page.pop("_rows")]
        page["data"] = page["items"]
        return page

    async def allowances(self, query: CarbonAssetsQuery) -> dict[str, Any]:
        conditions = []
        if query.period_id is not None:
            conditions.append(m.CarbonQuotaAllocation.period_id == query.period_id)
        if query.account_id is not None:
            conditions.append(m.CarbonQuotaAllocation.account_id == query.account_id)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append(m.CarbonQuotaAllocation.allocation_no.ilike(pattern))
        stmt = select(m.CarbonQuotaAllocation).where(*conditions).order_by(m.CarbonQuotaAllocation.id.desc())
        page = await self._page(stmt, query, include_rows=True)
        page["items"] = [await self._allowance_payload(row) for row in page.pop("_rows")]
        page["data"] = page["items"]
        return page

    async def credits(self, query: CarbonAssetsQuery) -> dict[str, Any]:
        conditions = []
        if query.account_id is not None:
            conditions.append(m.CarbonCreditHolding.account_id == query.account_id)
        if query.asset_type and query.asset_type != "all":
            conditions.append(m.CarbonCreditHolding.credit_type == query.asset_type)
        if query.status and query.status != "all":
            conditions.append(m.CarbonCreditHolding.status == query.status)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append((m.CarbonCreditHolding.holding_no.ilike(pattern)) | (m.CarbonCreditHolding.project_name.ilike(pattern)))
        stmt = select(m.CarbonCreditHolding).where(*conditions).order_by(m.CarbonCreditHolding.id.desc())
        page = await self._page(stmt, query, include_rows=True)
        page["items"] = [self._credit_payload(row) for row in page.pop("_rows")]
        page["data"] = page["items"]
        return page

    async def transactions(self, query: CarbonAssetsQuery) -> dict[str, Any]:
        conditions = []
        if query.account_id is not None:
            conditions.append(m.CarbonAssetTransaction.account_id == query.account_id)
        if query.asset_type and query.asset_type != "all":
            conditions.append(m.CarbonAssetTransaction.asset_type == query.asset_type)
        if query.status and query.status != "all":
            conditions.append(m.CarbonAssetTransaction.status == query.status)
        stmt = select(m.CarbonAssetTransaction).where(*conditions).order_by(m.CarbonAssetTransaction.id.desc())
        return await self._page(stmt, query)

    async def surrenders(self, query: CarbonAssetsQuery) -> dict[str, Any]:
        conditions = []
        if query.period_id is not None:
            conditions.append(m.CarbonSurrenderRecord.period_id == query.period_id)
        if query.account_id is not None:
            conditions.append(m.CarbonSurrenderRecord.account_id == query.account_id)
        if query.asset_type and query.asset_type != "all":
            conditions.append(m.CarbonSurrenderRecord.asset_type == query.asset_type)
        if query.status and query.status != "all":
            conditions.append(m.CarbonSurrenderRecord.status == query.status)
        stmt = select(m.CarbonSurrenderRecord).where(*conditions).order_by(m.CarbonSurrenderRecord.id.desc())
        return await self._page(stmt, query)

    async def forecast_scenarios(self, query: CarbonAssetsQuery) -> dict[str, Any]:
        conditions = []
        if query.period_id is not None:
            conditions.append(m.CarbonAssetForecastScenario.period_id == query.period_id)
        if query.status and query.status != "all":
            conditions.append(m.CarbonAssetForecastScenario.status == query.status)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append(
                (m.CarbonAssetForecastScenario.scenario_name.ilike(pattern)) | (m.CarbonAssetForecastScenario.scenario_code.ilike(pattern))
            )
        stmt = select(m.CarbonAssetForecastScenario).where(*conditions).order_by(
            m.CarbonAssetForecastScenario.created_at.desc(), m.CarbonAssetForecastScenario.id.desc()
        )
        page = await self._page(stmt, query, include_rows=True)
        page["items"] = [await self._forecast_scenario_payload(row) for row in page.pop("_rows")]
        page["data"] = page["items"]
        return page

    async def summary(self) -> dict[str, Any]:
        period_count = await self._count(m.CarbonCompliancePeriod)
        account_count = await self._count(m.CarbonAssetAccount)
        allowance_available = await self._allowance_available()
        credit_available_value = await self._credit_available()
        latest_period = await self._session.scalar(select(m.CarbonCompliancePeriod).order_by(m.CarbonCompliancePeriod.period_start.desc()).limit(1))
        latest_position = await self.compliance_position(latest_period.id) if latest_period else _empty_position()
        return {
            "period_count": period_count,
            "account_count": account_count,
            "allowance_available": _float(allowance_available),
            "credit_available": _float(credit_available_value),
            "latest_position": latest_position,
        }

    async def source_readiness(self) -> dict[str, Any]:
        period_count = await self._count(m.CarbonCompliancePeriod)
        account_count = await self._count(m.CarbonAssetAccount)
        allowance_count = await self._count(m.CarbonQuotaAllocation)
        credit_count = await self._count(m.CarbonCreditHolding)
        transaction_count = await self._count(m.CarbonAssetTransaction)
        surrender_count = await self._count(m.CarbonSurrenderRecord)
        forecast_scenario_count = await self._count(m.CarbonAssetForecastScenario)
        traceable_ledger_count = sum(
            [
                await self._traceable_asset_count(m.CarbonQuotaAllocation),
                await self._traceable_asset_count(m.CarbonCreditHolding),
                await self._traceable_asset_count(m.CarbonAssetTransaction, m.CarbonAssetTransaction.status != "simulated"),
                await self._traceable_asset_count(m.CarbonSurrenderRecord),
            ]
        )
        simulation_seed_count = sum(
            [
                await self._simulation_seed_count(m.CarbonCompliancePeriod),
                await self._simulation_seed_count(m.CarbonAssetAccount),
                await self._simulation_seed_count(m.CarbonAssetForecastScenario),
            ]
        )
        simulated_transaction_count = await self._count(
            m.CarbonAssetTransaction,
            (m.CarbonAssetTransaction.status == "simulated") | (_source_key(m.CarbonAssetTransaction.source_name).in_(NON_REAL_ASSET_SOURCE_NAMES)),
        )
        ledger_total_count = allowance_count + credit_count + transaction_count + surrender_count
        unverified_ledger_count = max(0, ledger_total_count - traceable_ledger_count - simulated_transaction_count)
        total_records = period_count + account_count + ledger_total_count + forecast_scenario_count
        if traceable_ledger_count > 0:
            status = "real_source_ready" if unverified_ledger_count == 0 else "partial_source"
        elif total_records == 0:
            status = "source_missing"
        elif simulation_seed_count > 0 or simulated_transaction_count > 0:
            status = "simulation_only"
        else:
            status = "unverified_source"
        return {
            "status": status,
            "period_count": period_count,
            "account_count": account_count,
            "allowance_count": allowance_count,
            "credit_count": credit_count,
            "transaction_count": transaction_count,
            "surrender_count": surrender_count,
            "forecast_scenario_count": forecast_scenario_count,
            "ledger_total_count": ledger_total_count,
            "traceable_ledger_count": traceable_ledger_count,
            "simulation_seed_count": simulation_seed_count,
            "simulated_transaction_count": simulated_transaction_count,
            "unverified_ledger_count": unverified_ledger_count,
        }

    async def alerts(self, query: CarbonAssetsQuery) -> dict[str, Any]:
        periods = (
            await self._session.execute(select(m.CarbonCompliancePeriod).order_by(m.CarbonCompliancePeriod.period_start.desc()).limit(20))
        ).scalars().all()
        positions = [await self.compliance_position(period.id) for period in periods]
        items = [
            {
                "period_id": item["period_id"],
                "period_name": item["period_name"],
                "risk_level": item["risk_level"],
                "gap_amount": item["gap_amount"],
                "gap_rate": item["gap_rate"],
                "message": _risk_message(item),
                "inventory_status": item["inventory_status"],
                "inventory_message": item["inventory_message"],
            }
            for item in positions
            if query.status in (None, "all") or item["risk_level"] == query.status
        ]
        return {"items": items, "data": items}

    async def recommendations(self, period_id: int | None = None) -> dict[str, Any]:
        period = await self._period_or_latest(period_id)
        if period is None:
            return {"items": [{"priority": "medium", "action": "先创建履约周期并绑定已锁定组织排放清单"}], "data": []}
        position = await self.compliance_position(period.id)
        items = []
        if not position["inventory_locked"]:
            items.append({"priority": "high", "action": position["inventory_message"]})
        elif position["verified_emission"] <= 0:
            items.append({"priority": "high", "action": "已锁定组织排放清单为零排放, 需复核核算范围和清单结果"})
        if position["gap_amount"] > 0:
            items.append({"priority": "high", "action": "补充配额、CCER 或其他可用信用, 并复核清缴计划"})
        if position["credit_available"] > 0 and position["allowance_available"] <= 0:
            items.append({"priority": "medium", "action": "确认 CCER/绿证是否可用于当前履约周期, 避免把不可用资产纳入履约余额"})
        if not items:
            items.append({"priority": "low", "action": "维持配额台账、信用持仓和清缴记录的月度复核"})
        return {"items": items, "data": items}

    async def compliance_position(self, period_id: int | None) -> dict[str, Any]:
        period = await self._period_or_latest(period_id)
        if period is None:
            return _empty_position()
        inventory = await self._verified_inventory(period)
        verified_emission = inventory["verified_emission"]
        allowance_value = await self._allowance_available(period.id)
        credit_value = await self._credit_available()
        surrendered_amount = await self._surrendered_amount(period.id)
        available_assets = allowance_value + credit_value
        net_position = available_assets + surrendered_amount - verified_emission
        gap_amount = abs(net_position) if net_position < 0 else Decimal(0)
        gap_rate = gap_amount / verified_emission if verified_emission > 0 else Decimal(0)
        risk_level = (
            compliance_risk_level(
                gap_amount,
                verified_emission,
                period.risk_threshold_yellow,
                period.risk_threshold_orange,
                period.risk_threshold_red,
            )
            if inventory["inventory_locked"]
            else inventory["inventory_status"]
        )
        return {
            "period_id": period.id,
            "period_name": period.period_name,
            "period_code": period.period_code,
            "market": period.market,
            "status": period.status,
            "verified_emission": _float(verified_emission),
            "allowance_available": _float(allowance_value),
            "credit_available": _float(credit_value),
            "surrendered_amount": _float(surrendered_amount),
            "available_assets": _float(available_assets),
            "net_position": _float(net_position),
            "gap_amount": _float(gap_amount),
            "gap_rate": _float(gap_rate),
            "risk_level": risk_level,
            "accounting_batch_id": period.accounting_batch_id,
            "boundary_id": period.boundary_id,
            "inventory_status": inventory["inventory_status"],
            "inventory_locked": inventory["inventory_locked"],
            "inventory_message": inventory["inventory_message"],
            "accounting_batch_status": inventory["accounting_batch_status"],
            "accounting_inventory_status": inventory["accounting_inventory_status"],
            "inventory_locked_at": inventory["inventory_locked_at"],
        }

    async def forecast(self, period_id: int | None = None, scenario_id: int | None = None) -> dict[str, Any]:
        scenario = await self._scenario_or_active(period_id, scenario_id)
        period = await self._period_or_latest(scenario.period_id if scenario else period_id)
        if period is None:
            return {"position": _empty_position(), "scenario": None, "result": _empty_forecast_result(), "monthly_points": []}
        position = await self.compliance_position(period.id)
        scenario_payload = await self._forecast_scenario_payload(scenario) if scenario else _default_scenario_payload(period)
        if not position["inventory_locked"]:
            result = _empty_forecast_result()
            result["risk_level"] = position["risk_level"]
            return {"position": position, "scenario": scenario_payload, "result": result, "monthly_points": []}
        verified_emission = Decimal(str(position["verified_emission"]))
        allowance_value = await self._allowance_available(period.id)
        credit_value = await self._credit_available()
        surrendered_amount = await self._surrendered_amount(period.id)
        scenario_values = _scenario_values(scenario)
        result = forecast_position(
            verified_emission=verified_emission,
            allowance_available_value=allowance_value,
            credit_available_value=credit_value,
            surrendered_amount=surrendered_amount,
            emission_growth_rate=scenario_values["emission_growth_rate"],
            planned_reduction=scenario_values["planned_reduction"],
            planned_allowance_purchase=scenario_values["planned_allowance_purchase"],
            planned_credit_purchase=scenario_values["planned_credit_purchase"],
            planned_surrender=scenario_values["planned_surrender"],
            allowance_price=scenario_values["allowance_price"],
            credit_price=scenario_values["credit_price"],
            yellow=period.risk_threshold_yellow,
            orange=period.risk_threshold_orange,
            red=period.risk_threshold_red,
        )
        monthly_points = _monthly_points(
            period=period,
            scenario=scenario,
            forecast_result=result,
            allowance_available_value=allowance_value,
            credit_available_value=credit_value,
            surrendered_amount=surrendered_amount,
            planned_allowance_purchase=scenario_values["planned_allowance_purchase"],
            planned_credit_purchase=scenario_values["planned_credit_purchase"],
            planned_surrender=scenario_values["planned_surrender"],
        )
        return {
            "position": position,
            "scenario": scenario_payload,
            "result": {key: _float(value) if isinstance(value, Decimal) else value for key, value in result.items()},
            "monthly_points": monthly_points,
        }

    async def _period_payload(self, row: m.CarbonCompliancePeriod) -> dict[str, Any]:
        payload = model_to_dict(row)
        payload["position"] = await self.compliance_position(row.id)
        return payload

    async def _account_payload(self, row: m.CarbonAssetAccount) -> dict[str, Any]:
        payload = model_to_dict(row)
        if row.asset_type == "quota":
            payload["available_amount"] = _float(await self._allowance_available(account_id=row.id))
        else:
            payload["available_amount"] = _float(await self._credit_available(account_id=row.id))
        return payload

    async def _allowance_payload(self, row: m.CarbonQuotaAllocation) -> dict[str, Any]:
        payload = model_to_dict(row)
        payload["available_amount"] = _float(
            allowance_available(row.allocated_amount, row.adjustment_amount, row.used_amount, row.frozen_amount)
        )
        period = await self._session.get(m.CarbonCompliancePeriod, row.period_id)
        account = await self._session.get(m.CarbonAssetAccount, row.account_id)
        payload["period_name"] = period.period_name if period else None
        payload["account_name"] = account.account_name if account else None
        return payload

    def _credit_payload(self, row: m.CarbonCreditHolding) -> dict[str, Any]:
        payload = model_to_dict(row)
        payload["available_amount"] = _float(credit_available(row.quantity, row.used_quantity, row.frozen_quantity))
        return payload

    async def _forecast_scenario_payload(self, row: m.CarbonAssetForecastScenario) -> dict[str, Any]:
        payload = model_to_dict(row)
        period = await self._session.get(m.CarbonCompliancePeriod, row.period_id)
        payload["period_name"] = period.period_name if period else None
        return payload

    async def _page(self, stmt: Any, query: CarbonAssetsQuery, *, include_rows: bool = False) -> dict[str, Any]:
        total = int((await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await self._session.execute(stmt.limit(_limit(query.limit)).offset(max(0, query.offset)))).scalars().all()
        items = [model_to_dict(row) for row in rows]
        page = {"items": items, "data": items, "total": total, "limit": _limit(query.limit), "offset": max(0, query.offset)}
        if include_rows:
            page["_rows"] = rows
        return page

    async def _count(self, model: type[Any], *conditions: Any) -> int:
        return int((await self._session.execute(select(func.count()).select_from(model).where(*conditions))).scalar_one() or 0)

    async def _traceable_asset_count(self, model: type[Any], *conditions: Any) -> int:
        source_key = _source_key(model.source_name)
        filters = [
            source_key != "",
            source_key.not_in(NON_REAL_ASSET_SOURCE_NAMES),
            ~source_key.like("real_company_package:%"),
            *conditions,
        ]
        if hasattr(model, "standard_code"):
            filters.append(func.lower(func.coalesce(model.standard_code, "")).not_in(NON_REAL_ASSET_STANDARD_CODES))
        return await self._count(model, *filters)

    async def _simulation_seed_count(self, model: type[Any]) -> int:
        source_key = _source_key(model.source_name)
        conditions = [source_key.in_(NON_REAL_ASSET_SOURCE_NAMES) | source_key.like("real_company_package:%")]
        if hasattr(model, "standard_code"):
            conditions.append(func.lower(func.coalesce(model.standard_code, "")) == "enterprise_assumption")
        if hasattr(model, "confidence_level"):
            conditions.append(func.lower(func.coalesce(model.confidence_level, "")) == "assumption")
        if hasattr(model, "market"):
            conditions.append(func.lower(func.coalesce(model.market, "")) == "simulation")
        return await self._count(model, *conditions)

    async def _period_or_latest(self, period_id: int | None) -> m.CarbonCompliancePeriod | None:
        if period_id is not None:
            return await self._session.get(m.CarbonCompliancePeriod, period_id)
        return await self._session.scalar(select(m.CarbonCompliancePeriod).order_by(m.CarbonCompliancePeriod.period_start.desc()).limit(1))

    async def _scenario_or_active(self, period_id: int | None, scenario_id: int | None) -> m.CarbonAssetForecastScenario | None:
        if scenario_id is not None:
            return await self._session.get(m.CarbonAssetForecastScenario, scenario_id)
        period = await self._period_or_latest(period_id)
        if period is None:
            return None
        return await self._session.scalar(
            select(m.CarbonAssetForecastScenario)
            .where(
                m.CarbonAssetForecastScenario.period_id == period.id,
                m.CarbonAssetForecastScenario.status == "active",
            )
            .order_by(m.CarbonAssetForecastScenario.updated_at.desc(), m.CarbonAssetForecastScenario.id.desc())
            .limit(1)
        )

    async def _verified_inventory(self, period: m.CarbonCompliancePeriod) -> dict[str, Any]:
        if not period.accounting_batch_id:
            return _inventory_payload(
                verified_emission=Decimal(0),
                status=inventory_position_status(has_batch=False, is_locked=False, has_total=False),
                batch=None,
            )
        batch = await self._session.get(m.CarbonAccountingBatch, period.accounting_batch_id)
        if batch is None:
            return _inventory_payload(
                verified_emission=Decimal(0),
                status=inventory_position_status(has_batch=False, is_locked=False, has_total=False),
                batch=None,
            )
        is_locked = batch.status == "locked" and batch.inventory_status == "locked"
        status = inventory_position_status(has_batch=True, is_locked=is_locked, has_total=batch.total_co2e is not None)
        verified_emission = Decimal(batch.total_co2e or 0) / KG_PER_TONNE if status == "locked" else Decimal(0)
        return _inventory_payload(verified_emission=verified_emission, status=status, batch=batch)

    async def _allowance_available(self, period_id: int | None = None, account_id: int | None = None) -> Decimal:
        conditions = []
        if period_id is not None:
            conditions.append(m.CarbonQuotaAllocation.period_id == period_id)
        if account_id is not None:
            conditions.append(m.CarbonQuotaAllocation.account_id == account_id)
        row = (
            await self._session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            m.CarbonQuotaAllocation.allocated_amount
                            + m.CarbonQuotaAllocation.adjustment_amount
                            - m.CarbonQuotaAllocation.used_amount
                            - m.CarbonQuotaAllocation.frozen_amount
                        ),
                        0,
                    )
                ).where(*conditions)
            )
        ).scalar_one()
        return Decimal(row or 0)

    async def _credit_available(self, account_id: int | None = None) -> Decimal:
        conditions = [m.CarbonCreditHolding.status == "active"]
        if account_id is not None:
            conditions.append(m.CarbonCreditHolding.account_id == account_id)
        row = (
            await self._session.execute(
                select(
                    func.coalesce(
                        func.sum(m.CarbonCreditHolding.quantity - m.CarbonCreditHolding.used_quantity - m.CarbonCreditHolding.frozen_quantity),
                        0,
                    )
                ).where(*conditions)
            )
        ).scalar_one()
        return Decimal(row or 0)

    async def _surrendered_amount(self, period_id: int) -> Decimal:
        row = (
            await self._session.execute(
                select(func.coalesce(func.sum(m.CarbonSurrenderRecord.amount), 0)).where(
                    m.CarbonSurrenderRecord.period_id == period_id,
                    m.CarbonSurrenderRecord.status == "completed",
                )
            )
        ).scalar_one()
        return Decimal(row or 0)


def _limit(value: int) -> int:
    return max(1, min(int(value or 50), 200))


def _float(value: Decimal | float | None) -> float:
    return float(value or 0)


def _source_key(column: Any) -> Any:
    return func.lower(func.coalesce(column, ""))


def _empty_position() -> dict[str, Any]:
    return {
        "period_id": None,
        "period_name": None,
        "period_code": None,
        "market": None,
        "status": "empty",
        "verified_emission": 0,
        "allowance_available": 0,
        "credit_available": 0,
        "surrendered_amount": 0,
        "available_assets": 0,
        "net_position": 0,
        "gap_amount": 0,
        "gap_rate": 0,
        "risk_level": "empty",
        "accounting_batch_id": None,
        "boundary_id": None,
        "inventory_status": "empty",
        "inventory_locked": False,
        "inventory_message": "未创建履约周期",
        "accounting_batch_status": None,
        "accounting_inventory_status": None,
        "inventory_locked_at": None,
    }


def _empty_forecast_result() -> dict[str, Any]:
    return {
        "forecast_emission": 0,
        "forecast_available_assets": 0,
        "forecast_surrendered": 0,
        "forecast_net_position": 0,
        "forecast_gap_amount": 0,
        "forecast_gap_rate": 0,
        "funding_need": 0,
        "risk_level": "empty",
    }


def _inventory_payload(*, verified_emission: Decimal, status: str, batch: m.CarbonAccountingBatch | None) -> dict[str, Any]:
    return {
        "verified_emission": verified_emission,
        "inventory_status": status,
        "inventory_locked": status == "locked",
        "inventory_message": _inventory_message(status),
        "accounting_batch_status": batch.status if batch else None,
        "accounting_inventory_status": batch.inventory_status if batch else None,
        "inventory_locked_at": batch.locked_at.isoformat() if batch and batch.locked_at else None,
    }


def _inventory_message(status: str) -> str:
    if status == "locked":
        return "已使用锁定组织排放清单"
    if status == "missing_batch":
        return "履约周期未绑定组织排放清单批次"
    if status == "unlocked_inventory":
        return "绑定的组织排放清单尚未锁定, 不能作为正式履约缺口口径"
    if status == "missing_inventory_total":
        return "已锁定组织排放清单缺少排放总量"
    return "组织排放清单状态不可用"


def _scenario_values(scenario: m.CarbonAssetForecastScenario | None) -> dict[str, Decimal]:
    if scenario is None:
        return {
            "emission_growth_rate": Decimal(0),
            "planned_reduction": Decimal(0),
            "planned_allowance_purchase": Decimal(0),
            "planned_credit_purchase": Decimal(0),
            "planned_surrender": Decimal(0),
            "allowance_price": Decimal(0),
            "credit_price": Decimal(0),
        }
    return {
        "emission_growth_rate": Decimal(scenario.emission_growth_rate or 0),
        "planned_reduction": Decimal(scenario.planned_reduction or 0),
        "planned_allowance_purchase": Decimal(scenario.planned_allowance_purchase or 0),
        "planned_credit_purchase": Decimal(scenario.planned_credit_purchase or 0),
        "planned_surrender": Decimal(scenario.planned_surrender or 0),
        "allowance_price": Decimal(scenario.allowance_price or 0),
        "credit_price": Decimal(scenario.credit_price or 0),
    }


def _default_scenario_payload(period: m.CarbonCompliancePeriod) -> dict[str, Any]:
    return {
        "id": None,
        "period_id": period.id,
        "period_name": period.period_name,
        "scenario_code": "baseline",
        "scenario_name": "基线预测",
        "status": "baseline",
        "forecast_start": period.period_start,
        "forecast_end": period.period_end,
        "currency": "CNY",
        **dict.fromkeys(_scenario_values(None), 0),
    }


def _monthly_points(
    *,
    period: m.CarbonCompliancePeriod,
    scenario: m.CarbonAssetForecastScenario | None,
    forecast_result: dict[str, Decimal | str],
    allowance_available_value: Decimal,
    credit_available_value: Decimal,
    surrendered_amount: Decimal,
    planned_allowance_purchase: Decimal,
    planned_credit_purchase: Decimal,
    planned_surrender: Decimal,
) -> list[dict[str, Any]]:
    start = (scenario.forecast_start if scenario else None) or period.period_start
    end = (scenario.forecast_end if scenario else None) or period.period_end
    month_labels = _month_labels(start, end)
    total = max(1, len(month_labels))
    points: list[dict[str, Any]] = []
    forecast_emission = Decimal(forecast_result["forecast_emission"]) if isinstance(forecast_result["forecast_emission"], Decimal) else Decimal(0)
    for index, label in enumerate(month_labels, start=1):
        ratio = Decimal(index) / Decimal(total)
        projected_emission = forecast_emission * ratio
        projected_assets = (
            allowance_available_value
            + credit_available_value
            + surrendered_amount
            + (planned_allowance_purchase + planned_credit_purchase + planned_surrender) * ratio
        )
        gap = projected_emission - projected_assets
        gap = gap if gap > 0 else Decimal(0)
        points.append(
            {
                "month": label,
                "projected_emission": _float(projected_emission),
                "projected_assets": _float(projected_assets),
                "projected_gap": _float(gap),
                "gap_rate": _float(gap / projected_emission) if projected_emission > 0 else 0,
                "risk_level": compliance_risk_level(gap, projected_emission, period.risk_threshold_yellow, period.risk_threshold_orange, period.risk_threshold_red),
            }
        )
    return points


def _month_labels(start: Any, end: Any) -> list[str]:
    labels: list[str] = []
    year = int(start.year)
    month = int(start.month)
    end_year = int(end.year)
    end_month = int(end.month)
    while (year, month) <= (end_year, end_month) and len(labels) < MAX_FORECAST_MONTHS:
        labels.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > MONTHS_PER_YEAR:
            month = 1
            year += 1
    return labels or [f"{start.year:04d}-{start.month:02d}"]


def _risk_message(item: dict[str, Any]) -> str:
    if not item.get("inventory_locked"):
        return str(item.get("inventory_message") or "未绑定已锁定组织排放清单")
    if item["risk_level"] in {"red", "orange", "yellow"}:
        return "履约资产余额不足, 需补充配额或可用信用"
    if item["verified_emission"] <= 0:
        return "已锁定组织排放清单为零排放"
    return "履约资产余额正常"
