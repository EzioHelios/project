from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.db import models as m
from app.domain.carbon_assets.domain.policies import (
    allowance_available,
    credit_available,
    ensure_period_open,
    simulate_transaction,
    validate_account_payload,
    validate_non_negative_amount,
    validate_period_payload,
    validate_positive_amount,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


PERIOD_FIELDS = {
    "period_code",
    "period_name",
    "market",
    "period_start",
    "period_end",
    "surrender_due_date",
    "boundary_id",
    "accounting_batch_id",
    "status",
    "risk_threshold_yellow",
    "risk_threshold_orange",
    "risk_threshold_red",
    "source_name",
    "standard_code",
    "confidence_level",
    "remark",
}
ACCOUNT_FIELDS = {
    "account_code",
    "account_name",
    "asset_type",
    "market",
    "currency",
    "status",
    "registry_account_no",
    "owner_name",
    "source_name",
    "standard_code",
    "remark",
}
ALLOWANCE_FIELDS = {
    "period_id",
    "account_id",
    "allocation_no",
    "quota_type",
    "allocated_amount",
    "adjustment_amount",
    "used_amount",
    "frozen_amount",
    "unit",
    "valid_from",
    "valid_to",
    "source_name",
    "standard_code",
    "remark",
}
CREDIT_FIELDS = {
    "account_id",
    "holding_no",
    "credit_type",
    "project_code",
    "project_name",
    "registry",
    "vintage_year",
    "quantity",
    "used_quantity",
    "frozen_quantity",
    "unit",
    "market_price",
    "currency",
    "valid_from",
    "valid_to",
    "status",
    "source_name",
    "standard_code",
    "remark",
}
TRANSACTION_FIELDS = {
    "account_id",
    "transaction_no",
    "asset_type",
    "transaction_type",
    "amount",
    "unit_price",
    "currency",
    "fee_rate",
    "tax_rate",
    "trade_date",
    "counterparty",
    "status",
    "scenario_payload",
    "source_name",
    "remark",
}
SURRENDER_FIELDS = {
    "period_id",
    "account_id",
    "surrender_no",
    "asset_type",
    "quota_allocation_id",
    "credit_holding_id",
    "amount",
    "unit",
    "status",
    "surrendered_at",
    "purpose",
    "source_name",
    "remark",
}
DECIMAL_FIELDS = {
    "risk_threshold_yellow",
    "risk_threshold_orange",
    "risk_threshold_red",
    "allocated_amount",
    "adjustment_amount",
    "used_amount",
    "frozen_amount",
    "quantity",
    "used_quantity",
    "frozen_quantity",
    "market_price",
    "amount",
    "unit_price",
    "fee_rate",
    "tax_rate",
}
DATE_FIELDS = {"period_start", "period_end", "surrender_due_date", "valid_from", "valid_to", "trade_date"}
DATETIME_FIELDS = {"surrendered_at"}
INTEGER_FIELDS = {"boundary_id", "accounting_batch_id", "period_id", "account_id", "quota_allocation_id", "credit_holding_id", "vintage_year"}


class CarbonAssetsUseCase:
    """Application workflows for carbon asset commands."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_period(self, data: dict[str, Any]) -> m.CarbonCompliancePeriod:
        payload = _payload(data, PERIOD_FIELDS, required={"period_code", "period_name", "period_start", "period_end"})
        payload.setdefault("market", "national")
        payload.setdefault("status", "open")
        payload.setdefault("risk_threshold_yellow", Decimal("0.0300"))
        payload.setdefault("risk_threshold_orange", Decimal("0.0800"))
        payload.setdefault("risk_threshold_red", Decimal("0.1500"))
        await self._validate_refs(payload)
        validate_period_payload(payload)
        obj = m.CarbonCompliancePeriod(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_period(self, period_id: int, data: dict[str, Any]) -> m.CarbonCompliancePeriod:
        obj = await self._get_or_raise(m.CarbonCompliancePeriod, period_id, "履约周期不存在")
        payload = _payload(data, PERIOD_FIELDS - {"period_code"})
        await self._validate_refs(payload)
        next_payload = {**{key: getattr(obj, key) for key in PERIOD_FIELDS if hasattr(obj, key)}, **payload}
        validate_period_payload(next_payload)
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def create_account(self, data: dict[str, Any]) -> m.CarbonAssetAccount:
        payload = _payload(data, ACCOUNT_FIELDS, required={"account_code", "account_name", "asset_type"})
        payload.setdefault("market", "national")
        payload.setdefault("currency", "CNY")
        payload.setdefault("status", "active")
        validate_account_payload(payload)
        obj = m.CarbonAssetAccount(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_account(self, account_id: int, data: dict[str, Any]) -> m.CarbonAssetAccount:
        obj = await self._get_or_raise(m.CarbonAssetAccount, account_id, "资产账户不存在")
        payload = _payload(data, ACCOUNT_FIELDS - {"account_code"})
        next_payload = {**{key: getattr(obj, key) for key in ACCOUNT_FIELDS if hasattr(obj, key)}, **payload}
        validate_account_payload(next_payload)
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def create_allowance(self, data: dict[str, Any]) -> m.CarbonQuotaAllocation:
        payload = _payload(data, ALLOWANCE_FIELDS, required={"period_id", "account_id", "allocation_no"})
        payload.setdefault("quota_type", "CEA")
        payload.setdefault("allocated_amount", Decimal(0))
        payload.setdefault("adjustment_amount", Decimal(0))
        payload.setdefault("used_amount", Decimal(0))
        payload.setdefault("frozen_amount", Decimal(0))
        payload.setdefault("unit", "tCO2e")
        await self._validate_allowance(payload)
        obj = m.CarbonQuotaAllocation(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_allowance(self, allocation_id: int, data: dict[str, Any]) -> m.CarbonQuotaAllocation:
        obj = await self._get_or_raise(m.CarbonQuotaAllocation, allocation_id, "配额记录不存在")
        period = await self._get_or_raise(m.CarbonCompliancePeriod, obj.period_id, "履约周期不存在")
        ensure_period_open(period.status)
        payload = _payload(data, ALLOWANCE_FIELDS - {"period_id", "account_id", "allocation_no"})
        for field in ("allocated_amount", "adjustment_amount", "used_amount", "frozen_amount"):
            if field in payload:
                validate_non_negative_amount(payload[field], field)
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def create_credit(self, data: dict[str, Any]) -> m.CarbonCreditHolding:
        payload = _payload(data, CREDIT_FIELDS, required={"account_id", "holding_no", "credit_type", "quantity"})
        payload.setdefault("used_quantity", Decimal(0))
        payload.setdefault("frozen_quantity", Decimal(0))
        payload.setdefault("unit", "tCO2e")
        payload.setdefault("currency", "CNY")
        payload.setdefault("status", "active")
        await self._validate_credit(payload)
        obj = m.CarbonCreditHolding(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_credit(self, credit_id: int, data: dict[str, Any]) -> m.CarbonCreditHolding:
        obj = await self._get_or_raise(m.CarbonCreditHolding, credit_id, "信用/绿证持仓不存在")
        payload = _payload(data, CREDIT_FIELDS - {"account_id", "holding_no"})
        for field in ("quantity", "used_quantity", "frozen_quantity", "market_price"):
            if field in payload:
                validate_non_negative_amount(payload[field], field)
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def simulate_transaction(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = _payload(data, TRANSACTION_FIELDS, required={"account_id", "asset_type", "transaction_type", "amount", "unit_price"})
        account = await self._get_or_raise(m.CarbonAssetAccount, int(payload["account_id"]), "资产账户不存在")
        payload.setdefault("transaction_no", await self._next_no(m.CarbonAssetTransaction, "CATX"))
        payload.setdefault("currency", account.currency or "CNY")
        payload.setdefault("fee_rate", Decimal(0))
        payload.setdefault("tax_rate", Decimal(0))
        payload.setdefault("trade_date", datetime.now(UTC).date())
        payload.setdefault("status", "simulated")
        payload.setdefault("source_name", "enterprise_asset_rule")
        simulated = simulate_transaction(payload["amount"], payload["unit_price"], payload.get("fee_rate"), payload.get("tax_rate"))
        obj = m.CarbonAssetTransaction(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return {
            **_model_payload(obj),
            **{key: float(value) for key, value in simulated.items()},
        }

    async def create_surrender(self, data: dict[str, Any]) -> m.CarbonSurrenderRecord:
        payload = _payload(data, SURRENDER_FIELDS, required={"period_id", "account_id", "asset_type", "amount"})
        payload.setdefault("surrender_no", await self._next_no(m.CarbonSurrenderRecord, "CASR"))
        payload.setdefault("unit", "tCO2e")
        payload.setdefault("status", "completed")
        payload.setdefault("purpose", "compliance")
        period = await self._get_or_raise(m.CarbonCompliancePeriod, int(payload["period_id"]), "履约周期不存在")
        ensure_period_open(period.status)
        await self._get_or_raise(m.CarbonAssetAccount, int(payload["account_id"]), "资产账户不存在")
        validate_positive_amount(payload["amount"])
        await self._apply_surrender_usage(payload)
        if payload["status"] == "completed" and payload.get("surrendered_at") is None:
            payload["surrendered_at"] = datetime.now(UTC).replace(tzinfo=None)
        obj = m.CarbonSurrenderRecord(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def _validate_refs(self, payload: dict[str, Any]) -> None:
        if payload.get("boundary_id") and await self._session.get(m.OrganizationBoundary, payload["boundary_id"]) is None:
            msg = "组织边界不存在"
            raise ValueError(msg)
        if payload.get("accounting_batch_id") and await self._session.get(m.CarbonAccountingBatch, payload["accounting_batch_id"]) is None:
            msg = "核算批次不存在"
            raise ValueError(msg)

    async def _validate_allowance(self, payload: dict[str, Any]) -> None:
        period = await self._get_or_raise(m.CarbonCompliancePeriod, int(payload["period_id"]), "履约周期不存在")
        ensure_period_open(period.status)
        account = await self._get_or_raise(m.CarbonAssetAccount, int(payload["account_id"]), "资产账户不存在")
        if account.asset_type != "quota":
            msg = "配额记录必须选择配额账户"
            raise ValueError(msg)
        for field in ("allocated_amount", "adjustment_amount", "used_amount", "frozen_amount"):
            validate_non_negative_amount(payload.get(field), field)

    async def _validate_credit(self, payload: dict[str, Any]) -> None:
        account = await self._get_or_raise(m.CarbonAssetAccount, int(payload["account_id"]), "资产账户不存在")
        if account.asset_type not in {"ccer", "green_certificate", "carbon_credit"}:
            msg = "信用/绿证持仓必须选择 CCER、绿证或碳信用账户"
            raise ValueError(msg)
        validate_positive_amount(payload.get("quantity"), "quantity")
        for field in ("used_quantity", "frozen_quantity", "market_price"):
            if payload.get(field) is not None:
                validate_non_negative_amount(payload.get(field), field)

    async def _apply_surrender_usage(self, payload: dict[str, Any]) -> None:
        amount = payload["amount"]
        if payload.get("quota_allocation_id"):
            allowance = await self._get_or_raise(m.CarbonQuotaAllocation, int(payload["quota_allocation_id"]), "配额记录不存在")
            available = allowance_available(allowance.allocated_amount, allowance.adjustment_amount, allowance.used_amount, allowance.frozen_amount)
            if amount > available:
                msg = "清缴数量超过配额可用余额"
                raise ValueError(msg)
            allowance.used_amount = (allowance.used_amount or Decimal(0)) + amount
            payload["account_id"] = allowance.account_id
            payload["asset_type"] = "quota"
        elif payload.get("credit_holding_id"):
            credit = await self._get_or_raise(m.CarbonCreditHolding, int(payload["credit_holding_id"]), "信用/绿证持仓不存在")
            available = credit_available(credit.quantity, credit.used_quantity, credit.frozen_quantity)
            if amount > available:
                msg = "清缴数量超过信用/绿证可用余额"
                raise ValueError(msg)
            credit.used_quantity = (credit.used_quantity or Decimal(0)) + amount
            payload["account_id"] = credit.account_id
            payload["asset_type"] = credit.credit_type
        else:
            msg = "清缴记录必须关联配额或信用/绿证持仓"
            raise ValueError(msg)

    async def _next_no(self, model: type[Any], prefix: str) -> str:
        latest = await self._session.scalar(select(model.id).order_by(model.id.desc()).limit(1))
        return f"{prefix}-{int(latest or 0) + 1:05d}"

    async def _get_or_raise(self, model: type[Any], obj_id: int, message: str) -> Any:
        obj = await self._session.get(model, obj_id)
        if obj is None:
            raise ValueError(message)
        return obj


def _payload(data: dict[str, Any], fields: set[str], *, required: set[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in data.items():
        if key not in fields:
            continue
        if key in DECIMAL_FIELDS:
            payload[key] = _decimal_or_none(value)
        elif key in DATE_FIELDS:
            payload[key] = _date_or_none(value)
        elif key in DATETIME_FIELDS:
            payload[key] = _datetime_or_none(value)
        elif key in INTEGER_FIELDS:
            payload[key] = int(value) if value not in (None, "") else None
        elif isinstance(value, str):
            payload[key] = value.strip() or None
        else:
            payload[key] = value
    for key in required or set():
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    return payload


def _assign(obj: object, payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        setattr(obj, key, value)


def _date_or_none(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
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


def _model_payload(obj: object) -> dict[str, Any]:
    from app.domain.energy.controllers._utils import model_to_dict

    return model_to_dict(obj)
