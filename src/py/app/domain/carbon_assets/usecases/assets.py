from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from litestar.exceptions import PermissionDeniedException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db import models as m
from app.domain.carbon_assets.domain.policies import (
    allowance_available,
    credit_available,
    ensure_period_open,
    simulate_transaction,
    validate_account_payload,
    validate_forecast_payload,
    validate_non_negative_amount,
    validate_period_payload,
    validate_positive_amount,
)
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


MAX_LEDGER_IMPORT_ROWS = 1000
SUPPORTED_LEDGER_DATASETS = {
    "compliance_period",
    "asset_account",
    "quota_allocation",
    "credit_holding",
    "asset_transaction",
    "surrender_record",
}


@dataclass(slots=True)
class CarbonAssetLedgerImportResult:
    """Result for tenant-scoped carbon asset ledger CSV imports."""

    received_count: int
    imported_count: int = 0
    skipped_count: int = 0
    errors: list[dict[str, Any]] = dataclass_field(default_factory=list)


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
FORECAST_SCENARIO_FIELDS = {
    "period_id",
    "scenario_code",
    "scenario_name",
    "base_year",
    "forecast_start",
    "forecast_end",
    "emission_growth_rate",
    "planned_reduction",
    "planned_allowance_purchase",
    "planned_credit_purchase",
    "planned_surrender",
    "allowance_price",
    "credit_price",
    "currency",
    "status",
    "source_name",
    "confidence_level",
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
    "emission_growth_rate",
    "planned_reduction",
    "planned_allowance_purchase",
    "planned_credit_purchase",
    "planned_surrender",
    "allowance_price",
    "credit_price",
}
DATE_FIELDS = {"period_start", "period_end", "surrender_due_date", "valid_from", "valid_to", "trade_date", "forecast_start", "forecast_end"}
DATETIME_FIELDS = {"surrendered_at"}
INTEGER_FIELDS = {
    "boundary_id",
    "accounting_batch_id",
    "period_id",
    "account_id",
    "quota_allocation_id",
    "credit_holding_id",
    "vintage_year",
    "base_year",
}


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

    async def create_forecast_scenario(self, data: dict[str, Any]) -> m.CarbonAssetForecastScenario:
        payload = _payload(data, FORECAST_SCENARIO_FIELDS, required={"period_id", "scenario_code", "scenario_name"})
        payload.setdefault("emission_growth_rate", Decimal(0))
        payload.setdefault("planned_reduction", Decimal(0))
        payload.setdefault("planned_allowance_purchase", Decimal(0))
        payload.setdefault("planned_credit_purchase", Decimal(0))
        payload.setdefault("planned_surrender", Decimal(0))
        payload.setdefault("allowance_price", Decimal(0))
        payload.setdefault("credit_price", Decimal(0))
        payload.setdefault("currency", "CNY")
        payload.setdefault("status", "draft")
        payload.setdefault("source_name", "enterprise_asset_rule")
        await self._validate_forecast(payload)
        obj = m.CarbonAssetForecastScenario(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_forecast_scenario(self, scenario_id: int, data: dict[str, Any]) -> m.CarbonAssetForecastScenario:
        obj = await self._get_or_raise(m.CarbonAssetForecastScenario, scenario_id, "预测情景不存在")
        payload = _payload(data, FORECAST_SCENARIO_FIELDS - {"scenario_code"})
        next_payload = {**{key: getattr(obj, key) for key in FORECAST_SCENARIO_FIELDS if hasattr(obj, key)}, **payload}
        await self._validate_forecast(next_payload)
        _assign(obj, payload)
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

    async def _validate_forecast(self, payload: dict[str, Any]) -> None:
        await self._get_or_raise(m.CarbonCompliancePeriod, int(payload["period_id"]), "履约周期不存在")
        validate_forecast_payload(payload)

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


class CarbonAssetLedgerImportUseCase:
    """Application workflow for importing traceable carbon asset ledger rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def import_rows(self, *, rows: list[dict[str, Any]], source_name: str | None = None) -> CarbonAssetLedgerImportResult:
        if self._session.info.get(TENANT_ID_SESSION_KEY) is None:
            msg = "导入需要先选择一个企业租户。"
            raise PermissionDeniedException(detail=msg)

        result = CarbonAssetLedgerImportResult(received_count=len(rows))
        if len(rows) > MAX_LEDGER_IMPORT_ROWS:
            result.errors.append({"row_number": 0, "message": "单次导入最多支持 1000 行。"})
            return result

        for index, raw_row in enumerate(rows, start=2):
            try:
                row = {str(key).strip(): value for key, value in raw_row.items()}
                dataset = _required_text(row, "dataset")
                if dataset not in SUPPORTED_LEDGER_DATASETS:
                    result.skipped_count += 1
                    result.errors.append({"row_number": index, "message": f"不支持的资产台账数据集: {dataset}"})
                    continue
                async with self._session.begin_nested():
                    if dataset == "compliance_period":
                        await self._upsert_period(row, source_name)
                    elif dataset == "asset_account":
                        await self._upsert_account(row, source_name)
                    elif dataset == "quota_allocation":
                        await self._upsert_allowance(row, source_name)
                    elif dataset == "credit_holding":
                        await self._upsert_credit(row, source_name)
                    elif dataset == "asset_transaction":
                        await self._upsert_transaction(row, source_name)
                    elif dataset == "surrender_record":
                        await self._upsert_surrender(row, source_name)
                result.imported_count += 1
            except (TypeError, ValueError) as exc:
                result.skipped_count += 1
                result.errors.append({"row_number": index, "message": str(exc)})
            except SQLAlchemyError as exc:
                result.skipped_count += 1
                result.errors.append({"row_number": index, "message": str(exc).splitlines()[0][:240]})

        if result.imported_count:
            await self._session.commit()
        else:
            await self._session.rollback()
        return result

    async def _upsert_period(self, row: dict[str, Any], source_name: str | None) -> None:
        period_code = _required_text(row, "period_code")
        payload = {
            "period_code": period_code,
            "period_name": _text(row.get("period_name")) or period_code,
            "market": _text(row.get("market")) or "national",
            "period_start": _required_date(row, "period_start"),
            "period_end": _required_date(row, "period_end"),
            "surrender_due_date": _date_or_none(row.get("surrender_due_date")),
            "status": _text(row.get("status")) or "open",
            "source_name": _source_name(row, source_name),
            "standard_code": _text(row.get("standard_code")),
            "confidence_level": _text(row.get("confidence_level")) or "high",
            "remark": _ledger_remark(row),
        }
        validate_period_payload(
            {**payload, "risk_threshold_yellow": Decimal("0.0300"), "risk_threshold_orange": Decimal("0.0800"), "risk_threshold_red": Decimal("0.1500")}
        )
        obj = await self._period_by_code(period_code)
        if obj is None:
            self._session.add(
                m.CarbonCompliancePeriod(
                    **payload,
                    risk_threshold_yellow=Decimal("0.0300"),
                    risk_threshold_orange=Decimal("0.0800"),
                    risk_threshold_red=Decimal("0.1500"),
                )
            )
        else:
            _assign(obj, payload)

    async def _upsert_account(self, row: dict[str, Any], source_name: str | None) -> None:
        account_code = _required_text(row, "account_code")
        payload = {
            "account_code": account_code,
            "account_name": _text(row.get("account_name")) or account_code,
            "asset_type": _required_text(row, "asset_type"),
            "market": _text(row.get("market")) or "national",
            "currency": _text(row.get("currency")) or "CNY",
            "status": _text(row.get("account_status")) or _text(row.get("status")) or "active",
            "registry_account_no": _text(row.get("registry_account_no")),
            "owner_name": _text(row.get("owner_name")),
            "source_name": _source_name(row, source_name),
            "standard_code": _text(row.get("standard_code")),
            "remark": _ledger_remark(row),
        }
        validate_account_payload(payload)
        obj = await self._account_by_code(account_code)
        if obj is None:
            self._session.add(m.CarbonAssetAccount(**payload))
        else:
            _assign(obj, payload)

    async def _upsert_allowance(self, row: dict[str, Any], source_name: str | None) -> None:
        period = await self._period_by_code(_required_text(row, "period_code"))
        if period is None:
            msg = "配额记录引用的履约周期不存在"
            raise ValueError(msg)
        account = await self._account_by_code(_required_text(row, "account_code"))
        if account is None:
            msg = "配额记录引用的资产账户不存在"
            raise ValueError(msg)
        if account.asset_type != "quota":
            msg = "配额记录必须引用配额账户"
            raise ValueError(msg)
        allocation_no = _required_text(row, "allocation_no")
        payload = {
            "period_id": period.id,
            "account_id": account.id,
            "allocation_no": allocation_no,
            "quota_type": _text(row.get("quota_type")) or "CEA",
            "allocated_amount": _decimal_or_zero(row.get("allocated_amount")),
            "adjustment_amount": _decimal_or_zero(row.get("adjustment_amount")),
            "used_amount": _decimal_or_zero(row.get("used_amount")),
            "frozen_amount": _decimal_or_zero(row.get("frozen_amount")),
            "unit": _text(row.get("unit")) or "tCO2e",
            "source_name": _source_name(row, source_name),
            "standard_code": _text(row.get("standard_code")),
            "remark": _ledger_remark(row),
        }
        for field_name in ("allocated_amount", "adjustment_amount", "used_amount", "frozen_amount"):
            validate_non_negative_amount(payload[field_name], field_name)
        obj = await self._allowance_by_no(allocation_no)
        if obj is None:
            self._session.add(m.CarbonQuotaAllocation(**payload))
        else:
            _assign(obj, payload)

    async def _upsert_credit(self, row: dict[str, Any], source_name: str | None) -> None:
        account = await self._account_by_code(_required_text(row, "account_code"))
        if account is None:
            msg = "信用/绿证持仓引用的资产账户不存在"
            raise ValueError(msg)
        if account.asset_type not in {"ccer", "green_certificate", "carbon_credit"}:
            msg = "信用/绿证持仓必须引用 CCER、绿证或碳信用账户"
            raise ValueError(msg)
        holding_no = _required_text(row, "holding_no")
        payload = {
            "account_id": account.id,
            "holding_no": holding_no,
            "credit_type": _text(row.get("credit_type")) or account.asset_type,
            "project_code": _text(row.get("project_code")),
            "project_name": _text(row.get("project_name")),
            "registry": _text(row.get("registry")),
            "vintage_year": _int_or_none(row.get("vintage_year")),
            "quantity": _required_decimal(row, "quantity"),
            "used_quantity": _decimal_or_zero(row.get("used_quantity")),
            "frozen_quantity": _decimal_or_zero(row.get("frozen_quantity")),
            "unit": _text(row.get("unit")) or "tCO2e",
            "market_price": _decimal_or_none(row.get("market_price")),
            "currency": _text(row.get("currency")) or account.currency or "CNY",
            "status": _text(row.get("status")) or "active",
            "source_name": _source_name(row, source_name),
            "standard_code": _text(row.get("standard_code")),
            "remark": _ledger_remark(row),
        }
        validate_positive_amount(payload["quantity"], "quantity")
        for field_name in ("used_quantity", "frozen_quantity", "market_price"):
            if payload[field_name] is not None:
                validate_non_negative_amount(payload[field_name], field_name)
        obj = await self._credit_by_no(holding_no)
        if obj is None:
            self._session.add(m.CarbonCreditHolding(**payload))
        else:
            _assign(obj, payload)

    async def _upsert_transaction(self, row: dict[str, Any], source_name: str | None) -> None:
        account = await self._account_by_code(_required_text(row, "account_code"))
        if account is None:
            msg = "交易记录引用的资产账户不存在"
            raise ValueError(msg)
        transaction_no = _required_text(row, "transaction_no")
        amount = _required_decimal(row, "amount")
        validate_positive_amount(amount, "amount")
        payload = {
            "account_id": account.id,
            "transaction_no": transaction_no,
            "asset_type": _text(row.get("asset_type")) or account.asset_type,
            "transaction_type": _required_text(row, "transaction_type"),
            "amount": amount,
            "unit_price": _decimal_or_zero(row.get("unit_price")),
            "currency": _text(row.get("currency")) or account.currency or "CNY",
            "fee_rate": _decimal_or_zero(row.get("fee_rate")),
            "tax_rate": _decimal_or_zero(row.get("tax_rate")),
            "trade_date": _date_or_none(row.get("trade_date")),
            "counterparty": _text(row.get("counterparty")),
            "status": _text(row.get("status")) or "confirmed",
            "source_name": _source_name(row, source_name),
            "remark": _ledger_remark(row),
        }
        obj = await self._transaction_by_no(transaction_no)
        if obj is None:
            self._session.add(m.CarbonAssetTransaction(**payload))
        else:
            _assign(obj, payload)

    async def _upsert_surrender(self, row: dict[str, Any], source_name: str | None) -> None:
        period = await self._period_by_code(_required_text(row, "period_code"))
        if period is None:
            msg = "清缴记录引用的履约周期不存在"
            raise ValueError(msg)
        account = await self._account_by_code(_required_text(row, "account_code"))
        if account is None:
            msg = "清缴记录引用的资产账户不存在"
            raise ValueError(msg)
        surrender_no = _required_text(row, "surrender_no")
        amount = _required_decimal(row, "amount")
        validate_positive_amount(amount, "amount")
        allocation = await self._allowance_by_no(str(row.get("allocation_no") or "").strip()) if row.get("allocation_no") else None
        credit = await self._credit_by_no(str(row.get("holding_no") or "").strip()) if row.get("holding_no") else None
        payload = {
            "period_id": period.id,
            "account_id": account.id,
            "surrender_no": surrender_no,
            "asset_type": _text(row.get("asset_type")) or account.asset_type,
            "quota_allocation_id": allocation.id if allocation else None,
            "credit_holding_id": credit.id if credit else None,
            "amount": amount,
            "unit": _text(row.get("unit")) or "tCO2e",
            "status": _text(row.get("surrender_status")) or _text(row.get("status")) or "completed",
            "surrendered_at": _datetime_or_none(row.get("surrendered_at")),
            "purpose": _text(row.get("purpose")) or "compliance",
            "source_name": _source_name(row, source_name),
            "remark": _ledger_remark(row),
        }
        obj = await self._surrender_by_no(surrender_no)
        if obj is None:
            self._session.add(m.CarbonSurrenderRecord(**payload))
        else:
            _assign(obj, payload)

    async def _period_by_code(self, code: str) -> m.CarbonCompliancePeriod | None:
        return await self._session.scalar(select(m.CarbonCompliancePeriod).where(m.CarbonCompliancePeriod.period_code == code).limit(1))

    async def _account_by_code(self, code: str) -> m.CarbonAssetAccount | None:
        return await self._session.scalar(select(m.CarbonAssetAccount).where(m.CarbonAssetAccount.account_code == code).limit(1))

    async def _allowance_by_no(self, allocation_no: str) -> m.CarbonQuotaAllocation | None:
        return await self._session.scalar(select(m.CarbonQuotaAllocation).where(m.CarbonQuotaAllocation.allocation_no == allocation_no).limit(1))

    async def _credit_by_no(self, holding_no: str) -> m.CarbonCreditHolding | None:
        return await self._session.scalar(select(m.CarbonCreditHolding).where(m.CarbonCreditHolding.holding_no == holding_no).limit(1))

    async def _transaction_by_no(self, transaction_no: str) -> m.CarbonAssetTransaction | None:
        return await self._session.scalar(select(m.CarbonAssetTransaction).where(m.CarbonAssetTransaction.transaction_no == transaction_no).limit(1))

    async def _surrender_by_no(self, surrender_no: str) -> m.CarbonSurrenderRecord | None:
        return await self._session.scalar(select(m.CarbonSurrenderRecord).where(m.CarbonSurrenderRecord.surrender_no == surrender_no).limit(1))


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


def _required_date(row: dict[str, Any], key: str) -> date:
    value = _date_or_none(row.get(key))
    if value is None:
        msg = f"{key} is required"
        raise ValueError(msg)
    return value


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _decimal_or_zero(value: Any) -> Decimal:
    return _decimal_or_none(value) or Decimal(0)


def _required_decimal(row: dict[str, Any], key: str) -> Decimal:
    value = _decimal_or_none(row.get(key))
    if value is None:
        msg = f"{key} is required"
        raise ValueError(msg)
    return value


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip() or None


def _required_text(row: dict[str, Any], key: str) -> str:
    value = _text(row.get(key))
    if not value:
        msg = f"{key} is required"
        raise ValueError(msg)
    return value


def _source_name(row: dict[str, Any], default_source_name: str | None) -> str:
    return _text(row.get("source_name")) or _text(default_source_name) or "企业碳资产台账"


def _ledger_remark(row: dict[str, Any]) -> str | None:
    parts = []
    if remark := _text(row.get("remark")):
        parts.append(remark)
    if source_file := _text(row.get("source_file")):
        parts.append(f"source_file={source_file}")
    if evidence_file := _text(row.get("evidence_file")):
        parts.append(f"evidence_file={evidence_file}")
    return "; ".join(parts) or None


def _model_payload(obj: object) -> dict[str, Any]:
    from app.domain.energy.controllers._utils import model_to_dict

    return model_to_dict(obj)
