"""Transactional carbon asset workflows."""

from __future__ import annotations

# ruff: noqa: EM101, TRY003
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_assets.domain.policies import (
    available_balance,
    calculate_cost_result,
    ensure_nonnegative,
    ensure_positive,
    validate_environmental_usage,
    validate_instrument,
    validate_movement,
    validate_settlement_line,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.carbon_assets import schemas


class CarbonAssetUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_instrument(self, data: schemas.InstrumentRequest) -> m.CarbonAssetInstrument:
        validate_instrument(data.instrument_class, data.native_unit, data.compliance_eligible)
        row = m.CarbonAssetInstrument(**data.to_dict())
        return await self._save(row)

    async def create_account(self, data: schemas.AccountRequest) -> m.CarbonAssetAccount:
        await self._get(m.CarbonAssetInstrument, data.instrument_id, "instrument not found")
        return await self._save(m.CarbonAssetAccount(**data.to_dict()))

    async def create_lot(self, data: schemas.LotRequest) -> m.CarbonAssetLot:
        ensure_positive(Decimal(str(data.issued_quantity)), "issued quantity")
        account = await self._get(m.CarbonAssetAccount, data.account_id, "account not found")
        payload = data.to_dict()
        payload["instrument_id"] = account.instrument_id
        payload["issued_quantity"] = Decimal(str(data.issued_quantity))
        if data.acquisition_unit_cost is not None:
            payload["acquisition_unit_cost"] = Decimal(str(data.acquisition_unit_cost))
        return await self._save(m.CarbonAssetLot(**payload))

    async def post_movement(self, data: schemas.MovementRequest) -> m.CarbonAssetMovement:
        lot = await self._get(m.CarbonAssetLot, data.lot_id, "asset lot not found")
        delta = Decimal(str(data.quantity_delta))
        validate_movement(data.movement_type, delta)
        if data.movement_type == "unfreeze" and delta > await self._frozen_lot_balance(lot.id):
            raise ValueError("unfreeze quantity exceeds the frozen lot balance")
        await self._ensure_lot_balance(lot, delta)
        payload = data.to_dict()
        payload.update({
            "movement_no": await self._next_no("CAMV"), "account_id": lot.account_id,
            "instrument_id": lot.instrument_id, "quantity_delta": delta, "posted_at": datetime.now(UTC),
            "unit_price": Decimal(str(data.unit_price)) if data.unit_price is not None else None,
            "fee_amount": Decimal(str(data.fee_amount)),
        })
        return await self._save(m.CarbonAssetMovement(**payload))

    async def reverse_movement(self, movement_id: int, data: schemas.ReversalRequest) -> m.CarbonAssetMovement:
        original = await self._get(m.CarbonAssetMovement, movement_id, "movement not found")
        existing = await self.session.scalar(select(m.CarbonAssetMovement.id).where(m.CarbonAssetMovement.reverses_movement_id == movement_id))
        if existing is not None:
            raise ValueError("movement has already been reversed")
        delta = -Decimal(original.quantity_delta)
        validate_movement("reversal", delta, reversed_delta=Decimal(original.quantity_delta))
        lot = await self._get(m.CarbonAssetLot, original.lot_id, "asset lot not found")
        await self._ensure_lot_balance(lot, delta)
        row = m.CarbonAssetMovement(
            movement_no=await self._next_no("CAMV"), account_id=original.account_id,
            instrument_id=original.instrument_id, lot_id=original.lot_id, movement_type="reversal",
            quantity_delta=delta, unit_price=original.unit_price, fee_amount=Decimal(0), currency=original.currency,
            occurred_on=data.occurred_on, posted_at=datetime.now(UTC), reference_type="movement_reversal",
            reference_id=original.id, reverses_movement_id=original.id, source_name="ledger_correction",
            evidence_ref=data.evidence_ref, remark=data.reason,
        )
        return await self._save(row)

    async def create_rule(self, data: schemas.RuleVersionRequest) -> m.CarbonComplianceRuleVersion:
        ratio = Decimal(str(data.max_offset_ratio))
        if not Decimal(0) <= ratio <= Decimal(1):
            raise ValueError("max offset ratio must be between zero and one")
        payload = data.to_dict()
        payload["max_offset_ratio"] = ratio
        return await self._save(m.CarbonComplianceRuleVersion(**payload))

    async def create_cycle(self, data: schemas.ComplianceCycleRequest) -> m.CarbonComplianceCycle:
        if data.period_end < data.period_start:
            raise ValueError("cycle end date cannot be earlier than start date")
        await self._get(m.CarbonComplianceRuleVersion, data.rule_version_id, "compliance rule not found")
        payload = data.to_dict()
        payload["covered_emissions_tco2e"] = Decimal(str(data.covered_emissions_tco2e))
        payload["required_surrender_tco2e"] = Decimal(str(data.required_surrender_tco2e))
        ensure_nonnegative(payload["covered_emissions_tco2e"], "covered emissions")
        ensure_positive(payload["required_surrender_tco2e"], "required surrender")
        return await self._save(m.CarbonComplianceCycle(**payload))

    async def create_settlement(self, data: schemas.SettlementRequest) -> m.CarbonComplianceSettlement:
        cycle = await self._get(m.CarbonComplianceCycle, data.cycle_id, "compliance cycle not found")
        rule = await self._get(m.CarbonComplianceRuleVersion, cycle.rule_version_id, "compliance rule not found")
        settlement = m.CarbonComplianceSettlement(
            settlement_no=await self._next_no("CAST"), cycle_id=cycle.id, status="draft",
            rule_snapshot={"ruleCode": rule.rule_code, "version": rule.version, "maxOffsetRatio": float(rule.max_offset_ratio)},
            source_name=data.source_name, evidence_ref=data.evidence_ref, remark=data.remark,
        )
        self.session.add(settlement)
        await self.session.flush()
        cea = Decimal(0)
        ccer = Decimal(0)
        for line_data in data.lines:
            lot = await self._get(m.CarbonAssetLot, line_data.lot_id, "asset lot not found")
            instrument = await self._get(m.CarbonAssetInstrument, lot.instrument_id, "instrument not found")
            validate_settlement_line(instrument.instrument_class, line_data.purpose)
            quantity = Decimal(str(line_data.quantity))
            ensure_positive(quantity, "settlement quantity")
            await self._ensure_lot_balance(lot, -quantity)
            self.session.add(m.CarbonComplianceSettlementLine(
                settlement_id=settlement.id, lot_id=lot.id, instrument_class=instrument.instrument_class,
                quantity=quantity, purpose=line_data.purpose,
            ))
            if instrument.instrument_class == "CEA":
                cea += quantity
            else:
                ccer += quantity
        if ccer > Decimal(cycle.required_surrender_tco2e) * Decimal(rule.max_offset_ratio):
            raise ValueError("CCER offset exceeds the frozen compliance rule limit")
        if cea + ccer > Decimal(cycle.required_surrender_tco2e):
            raise ValueError("settlement exceeds the required surrender quantity")
        settlement.total_cea_tco2e = cea
        settlement.total_ccer_tco2e = ccer
        await self.session.commit()
        return settlement

    async def post_settlement(self, settlement_id: int) -> m.CarbonComplianceSettlement:
        settlement = await self._get(m.CarbonComplianceSettlement, settlement_id, "settlement not found")
        if settlement.status != "draft":
            raise ValueError("only a draft settlement can be posted")
        lines = list((await self.session.scalars(select(m.CarbonComplianceSettlementLine).where(m.CarbonComplianceSettlementLine.settlement_id == settlement.id))).all())
        quantities_by_lot: dict[int, Decimal] = {}
        for line in lines:
            quantities_by_lot[line.lot_id] = quantities_by_lot.get(line.lot_id, Decimal(0)) + Decimal(line.quantity)
        locked_lots: dict[int, m.CarbonAssetLot] = {}
        for lot_id, quantity in quantities_by_lot.items():
            lot = await self.session.scalar(
                select(m.CarbonAssetLot).where(m.CarbonAssetLot.id == lot_id).with_for_update()
            )
            if lot is None:
                raise ValueError("asset lot not found")
            await self._ensure_lot_balance(lot, -quantity)
            locked_lots[lot_id] = lot
        for line in lines:
            lot = locked_lots[line.lot_id]
            movement = m.CarbonAssetMovement(
                movement_no=await self._next_no("CAMV"), account_id=lot.account_id, instrument_id=lot.instrument_id,
                lot_id=lot.id, movement_type="surrender" if line.instrument_class == "CEA" else "offset",
                quantity_delta=-Decimal(line.quantity), fee_amount=Decimal(0), currency="CNY",
                occurred_on=datetime.now(UTC).date(), posted_at=datetime.now(UTC), reference_type="compliance_settlement",
                reference_id=settlement.id, source_name=settlement.source_name, evidence_ref=settlement.evidence_ref,
            )
            self.session.add(movement)
            await self.session.flush()
            line.movement_id = movement.id
        settlement.status = "completed"
        settlement.submitted_at = datetime.now(UTC)
        settlement.completed_at = datetime.now(UTC)
        await self.session.commit()
        return settlement

    async def record_usage(self, data: schemas.EnvironmentalUsageRequest) -> m.EnvironmentalAssetUsage:
        lot = await self._get(m.CarbonAssetLot, data.lot_id, "asset lot not found")
        instrument = await self._get(m.CarbonAssetInstrument, lot.instrument_id, "instrument not found")
        validate_environmental_usage(instrument.instrument_class, data.purpose)
        quantity = Decimal(str(data.quantity))
        ensure_positive(quantity, "usage quantity")
        await self._ensure_lot_balance(lot, -quantity)
        movement = m.CarbonAssetMovement(
            movement_no=await self._next_no("CAMV"), account_id=lot.account_id, instrument_id=lot.instrument_id,
            lot_id=lot.id, movement_type="consume", quantity_delta=-quantity, fee_amount=Decimal(0), currency="CNY",
            occurred_on=datetime.now(UTC).date(), posted_at=datetime.now(UTC), reference_type="environmental_usage",
            source_name="environmental_asset_usage", evidence_ref=data.evidence_ref,
        )
        self.session.add(movement)
        await self.session.flush()
        payload = data.to_dict()
        payload.update({"usage_no": await self._next_no("CAUS"), "quantity": quantity, "used_at": datetime.now(UTC), "movement_id": movement.id})
        usage = m.EnvironmentalAssetUsage(**payload)
        self.session.add(usage)
        await self.session.flush()
        movement.reference_id = usage.id
        await self.session.commit()
        return usage

    async def create_quote(self, data: schemas.MarketQuoteRequest) -> m.CarbonMarketQuote:
        instrument = await self._get(m.CarbonAssetInstrument, data.instrument_id, "instrument not found")
        if data.quote_unit != instrument.native_unit:
            raise ValueError("quote unit must match the instrument native unit")
        if data.source_kind not in {"observed", "imported"}:
            raise ValueError("only observed or imported market quotes are accepted")
        payload = data.to_dict()
        for field in ("close_price", "open_price", "high_price", "low_price", "volume", "turnover"):
            value = payload.get(field)
            if value is not None:
                payload[field] = Decimal(str(value))
                ensure_nonnegative(payload[field], field.replace("_", " "))
        ensure_positive(payload["close_price"], "close price")
        if payload.get("high_price") is not None and payload["high_price"] < payload["close_price"]:
            raise ValueError("high price cannot be lower than close price")
        if payload.get("low_price") is not None and payload["low_price"] > payload["close_price"]:
            raise ValueError("low price cannot be higher than close price")
        return await self._save(m.CarbonMarketQuote(**payload))

    async def create_scenario(self, data: schemas.CostScenarioRequest) -> m.CarbonCostScenario:
        if data.cycle_id is not None:
            await self._get(m.CarbonComplianceCycle, data.cycle_id, "compliance cycle not found")
        return await self._save(m.CarbonCostScenario(**data.to_dict()))

    async def run_scenario(self, scenario_id: int) -> m.CarbonCostRun:
        scenario = await self._get(m.CarbonCostScenario, scenario_id, "cost scenario not found")
        cycle = await self._get(m.CarbonComplianceCycle, scenario.cycle_id, "compliance cycle not found") if scenario.cycle_id else None
        if cycle is None:
            raise ValueError("cost scenario must reference a compliance cycle")
        rule = await self._get(m.CarbonComplianceRuleVersion, cycle.rule_version_id, "compliance rule not found")
        balances = await self._class_balances()
        parameters = dict(scenario.parameters or {})
        cea_price = Decimal(str(parameters.get("ceaPrice", 0)))
        ccer_price = Decimal(str(parameters.get("ccerPrice", 0)))
        safety_margin = Decimal(str(parameters.get("safetyMarginRatio", 0)))
        ensure_nonnegative(cea_price, "CEA price")
        ensure_nonnegative(ccer_price, "CCER price")
        if not Decimal(0) <= safety_margin <= Decimal(1):
            raise ValueError("safety margin ratio must be between zero and one")
        result = calculate_cost_result(
            obligation_tco2e=Decimal(cycle.required_surrender_tco2e), cea_balance_tco2e=balances.get("CEA", Decimal(0)),
            ccer_balance_tco2e=balances.get("CCER", Decimal(0)), max_offset_ratio=Decimal(rule.max_offset_ratio),
            cea_price=cea_price, ccer_price=ccer_price, safety_margin_ratio=safety_margin,
        )
        run = m.CarbonCostRun(
            run_no=await self._next_no("CACR"), scenario_id=scenario.id, status="completed",
            input_snapshot={"scenario": parameters, "cycleId": cycle.id, "requiredSurrenderTco2e": float(cycle.required_surrender_tco2e), "ruleVersionId": rule.id},
            quote_snapshot={"ceaPrice": float(cea_price), "ccerPrice": float(ccer_price), "currency": "CNY"},
            balance_snapshot={key: float(value) for key, value in balances.items()},
            result_summary={key: float(value) for key, value in result.items()}, period_results=[], completed_at=datetime.now(UTC),
        )
        return await self._save(run)

    async def _class_balances(self) -> dict[str, Decimal]:
        issued = {row[0]: Decimal(row[1] or 0) for row in (await self.session.execute(
            select(m.CarbonAssetInstrument.instrument_class, func.sum(m.CarbonAssetLot.issued_quantity))
            .join(m.CarbonAssetLot, m.CarbonAssetLot.instrument_id == m.CarbonAssetInstrument.id)
            .group_by(m.CarbonAssetInstrument.instrument_class)
        )).all()}
        deltas = {row[0]: Decimal(row[1] or 0) for row in (await self.session.execute(
            select(m.CarbonAssetInstrument.instrument_class, func.sum(m.CarbonAssetMovement.quantity_delta))
            .join(m.CarbonAssetMovement, m.CarbonAssetMovement.instrument_id == m.CarbonAssetInstrument.id)
            .group_by(m.CarbonAssetInstrument.instrument_class)
        )).all()}
        return {kind: issued.get(kind, Decimal(0)) + deltas.get(kind, Decimal(0)) for kind in ("CEA", "CCER", "GREEN_CERTIFICATE")}

    async def _ensure_lot_balance(self, lot: m.CarbonAssetLot, delta: Decimal) -> None:
        movement_total = Decimal(await self.session.scalar(select(func.coalesce(func.sum(m.CarbonAssetMovement.quantity_delta), 0)).where(m.CarbonAssetMovement.lot_id == lot.id)) or 0)
        available_balance(Decimal(lot.issued_quantity), movement_total + delta)

    async def _frozen_lot_balance(self, lot_id: int) -> Decimal:
        rows = list(
            (
                await self.session.execute(
                    select(
                        m.CarbonAssetMovement.id,
                        m.CarbonAssetMovement.movement_type,
                        m.CarbonAssetMovement.quantity_delta,
                        m.CarbonAssetMovement.reverses_movement_id,
                    )
                    .where(m.CarbonAssetMovement.lot_id == lot_id)
                    .order_by(m.CarbonAssetMovement.id)
                )
            ).all()
        )
        movement_types = {row.id: row.movement_type for row in rows}
        frozen = Decimal(0)
        for row in rows:
            affects_frozen = row.movement_type in {"freeze", "unfreeze"} or (
                row.movement_type == "reversal"
                and movement_types.get(row.reverses_movement_id) in {"freeze", "unfreeze"}
            )
            if affects_frozen:
                frozen -= Decimal(row.quantity_delta)
        return max(Decimal(0), frozen)

    async def _get(self, model: type[Any], object_id: int | None, message: str) -> Any:
        row = await self.session.get(model, object_id) if object_id is not None else None
        if row is None:
            raise ValueError(message)
        return row

    async def _save(self, row: Any) -> Any:
        self.session.add(row)
        await self.session.commit()
        return row

    async def _next_no(self, prefix: str) -> str:
        return f"{prefix}-{datetime.now(UTC):%Y%m%d%H%M%S%f}"
