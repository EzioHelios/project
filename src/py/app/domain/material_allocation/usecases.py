"""Handling commands flush; their caller owns commit/rollback."""

# ruff: noqa: RUF001
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.db import models as m
from app.domain.material_allocation.policies import (
    MaterialAllocationError,
    allocate,
    fingerprint,
    interval_payload,
    intervals,
    overlap_seconds,
    utc,
)
from app.domain.material_allocation.schemas import HourCalculation, OperationCreate, OperationUpdate
from app.lib.tenancy import require_session_tenant_id


class MaterialHandlingOperationUseCase:
    def __init__(self, session: Any) -> None:
        self.session = session
        self.tenant_id = require_session_tenant_id(session)

    async def get(self, operation_id: int) -> m.MaterialHandlingOperation:
        row = await self.session.scalar(
            select(m.MaterialHandlingOperation)
            .where(
                m.MaterialHandlingOperation.id == operation_id,
                m.MaterialHandlingOperation.team_id == self.tenant_id,
            )
            .with_for_update()
        )
        if row is None:
            msg = "物资作业记录不存在"
            raise MaterialAllocationError(msg)
        return row

    async def references(self, equipment_id: int, material_id: int) -> dict[str, Any]:
        equipment = await self.session.scalar(
            select(m.MonitorEquipment)
            .where(
                m.MonitorEquipment.id == equipment_id,
                m.MonitorEquipment.team_id == self.tenant_id,
                m.MonitorEquipment.is_enable.is_(True),
            )
            .with_for_update()
        )
        product = await self.session.scalar(
            select(m.ProductionProduct).where(
                m.ProductionProduct.id == material_id,
                m.ProductionProduct.team_id == self.tenant_id,
                m.ProductionProduct.is_enabled.is_(True),
            )
        )
        if equipment is None or product is None:
            msg = "请选择当前租户已启用的设备和物资"
            raise MaterialAllocationError(msg)
        area = await self.session.scalar(
            select(m.MonitorSector).where(
                m.MonitorSector.id == equipment.sector_id,
                m.MonitorSector.team_id == self.tenant_id,
            )
        )
        if area is None or not product.default_unit:
            msg = "请先维护设备所属区域和物资计量单位"
            raise MaterialAllocationError(msg)
        return {
            "equipment_code": equipment.code,
            "equipment_name": equipment.name,
            "area_id": area.id,
            "area_code": area.code,
            "area_name": area.name,
            "material_code": product.code,
            "material_name": product.name,
            "material_spec": product.spec,
            "material_category": product.category,
            "unit": product.default_unit,
        }

    async def create(self, data: OperationCreate) -> m.MaterialHandlingOperation:
        return await self.receive(
            data, source_system="manual", source_record_id=uuid4().hex, data_quality="reported", source_payload={}
        )

    async def receive(
        self,
        data: OperationCreate,
        *,
        source_system: str,
        source_record_id: str,
        data_quality: str,
        source_payload: dict,
    ) -> m.MaterialHandlingOperation:
        refs = await self.references(data.equipment_id, data.material_id)
        existing = await self.session.scalar(
            select(m.MaterialHandlingOperation).where(
                m.MaterialHandlingOperation.team_id == self.tenant_id,
                m.MaterialHandlingOperation.source_system == source_system,
                m.MaterialHandlingOperation.source_record_id == source_record_id,
            )
        )
        payload = data.model_dump(exclude={"active_intervals"})
        payload.update(self._times(intervals(data.active_intervals)))
        if existing:
            if any(getattr(existing, key) != value for key, value in payload.items()):
                msg = "同一来源记录的业务内容不一致"
                raise MaterialAllocationError(msg)
            return existing
        row = m.MaterialHandlingOperation(
            team_id=self.tenant_id,
            source_system=source_system,
            source_record_id=source_record_id,
            source_payload=source_payload,
            data_quality=data_quality,
            operation_status="draft",
            **payload,
            **refs,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    @staticmethod
    def _times(merged: list) -> dict:
        return {
            "active_intervals": interval_payload(merged),
            "period_start": merged[0][0],
            "period_end": merged[-1][1],
            "duration_minutes": sum((Decimal(str((b - a).total_seconds())) for a, b in merged), Decimal(0)) / 60,
        }

    async def update(self, operation_id: int, data: OperationUpdate) -> m.MaterialHandlingOperation:
        row = await self.get(operation_id)
        payload = data.model_dump(exclude_unset=True)
        if any(value is None and key not in {"weight_kg", "remark"} for key, value in payload.items()):
            msg = "必填字段不能清空"
            raise MaterialAllocationError(msg)
        if "active_intervals" in payload:
            payload.update(self._times(intervals(payload["active_intervals"])))
        business_change = any(key != "remark" and getattr(row, key) != value for key, value in payload.items())
        if business_change:
            if row.source_system == "vision" and not str(payload.get("remark") or "").strip():
                msg = "修改识别作业的业务数据时，请填写本次修正原因"
                raise MaterialAllocationError(msg)
            refs = await self.references(
                payload.get("equipment_id", row.equipment_id), payload.get("material_id", row.material_id)
            )
            await invalidate_operation(self.session, row)
            payload.update(refs)
            payload["operation_status"] = "draft"
        for key, value in payload.items():
            setattr(row, key, value)
        await self.session.flush()
        return row

    async def confirm(self, operation_id: int) -> m.MaterialHandlingOperation:
        row = await self.get(operation_id)
        refs = await self.references(row.equipment_id, row.material_id)
        intervals(row.active_intervals or [])
        if row.operation_status != "confirmed" or any(getattr(row, key) != value for key, value in refs.items()):
            for key, value in refs.items():
                setattr(row, key, value)
            row.operation_status = "confirmed"
            await invalidate_operation(self.session, row)
        await self.session.flush()
        return row

    async def append_observed_intervals(self, operation_id: int, active: list[dict]) -> None:
        row = await self.get(operation_id)
        if row.source_system != "vision" or row.operation_status != "draft":
            msg = "只有待确认的视觉作业可以追加识别片段"
            raise MaterialAllocationError(msg)
        merged = self._times(intervals((row.active_intervals or []) + active))
        for key, value in merged.items():
            setattr(row, key, value)
        await self.session.flush()

    async def withdraw(self, operation_id: int) -> m.MaterialHandlingOperation:
        row = await self.get(operation_id)
        row.operation_status = "draft"
        await invalidate_operation(self.session, row)
        await self.session.flush()
        return row

    async def delete(self, operation_id: int) -> None:
        row = await self.get(operation_id)
        used = await self.session.scalar(
            select(m.MaterialCarbonAllocationResult.id).where(m.MaterialCarbonAllocationResult.operation_id == row.id)
        )
        if used:
            msg = "作业已有分摊结果，请撤回确认后重新计算，不可删除"
            raise MaterialAllocationError(msg)
        await self.session.delete(row)
        await self.session.flush()


async def invalidate_run(session: Any, run: m.MaterialCarbonAllocationRun) -> None:
    run.status = "stale"
    results = list(
        await session.scalars(
            select(m.MaterialCarbonAllocationResult).where(
                m.MaterialCarbonAllocationResult.team_id == run.team_id,
                m.MaterialCarbonAllocationResult.run_id == run.id,
            )
        )
    )
    for result in results:
        result.data_status = "stale"
        if result.product_footprint_item_id:
            item = await session.get(m.ProductFootprintInventoryItem, result.product_footprint_item_id)
            if item:
                item.calc_status = "stale_source"
                study = await session.get(m.ProductFootprintStudy, item.study_id)
                if study:
                    study.result_status = "stale_source"


async def invalidate_operation(session: Any, operation: m.MaterialHandlingOperation) -> None:
    runs = await session.scalars(
        select(m.MaterialCarbonAllocationRun).where(
            m.MaterialCarbonAllocationRun.team_id == operation.team_id,
            m.MaterialCarbonAllocationRun.equipment_id == operation.equipment_id,
            m.MaterialCarbonAllocationRun.period_start < operation.period_end,
            m.MaterialCarbonAllocationRun.period_end > operation.period_start,
        )
    )
    for run in runs:
        await invalidate_run(session, run)


class CalculateMaterialCarbonAllocation:
    def __init__(self, session: Any) -> None:
        self.session = session
        self.tenant_id = require_session_tenant_id(session)

    async def inputs(self, data: HourCalculation, start: datetime) -> tuple[dict, list, Decimal, Decimal]:
        end = start + timedelta(hours=1)
        factor = await self.session.scalar(
            select(m.EmissionFactor).where(
                m.EmissionFactor.id == data.factor_id,
                (m.EmissionFactor.team_id.is_(None) | (m.EmissionFactor.team_id == self.tenant_id)),
                m.EmissionFactor.is_active.is_(True),
                m.EmissionFactor.review_status == "approved",
            )
        )
        if factor is None or factor.unit != "kWh" or factor.factor_unit != "kgCO2e/kWh":
            msg = "请选择已确认、适用的电力因子（kgCO2e/kWh）"
            raise MaterialAllocationError(msg)
        if factor.factor_value < 0 or not factor.source:
            msg = "因子缺少有效数值或来源"
            raise MaterialAllocationError(msg)
        facts = list(
            await self.session.scalars(
                select(m.EnergyIntervalFact).where(
                    m.EnergyIntervalFact.team_id == self.tenant_id,
                    m.EnergyIntervalFact.equipment_id == data.equipment_id,
                    m.EnergyIntervalFact.is_current.is_(True),
                    m.EnergyIntervalFact.granularity == "hour",
                    m.EnergyIntervalFact.source_system == data.energy_source_system,
                    m.EnergyIntervalFact.energy_type_code.in_(("electricity", "purchased_electricity")),
                    m.EnergyIntervalFact.period_start < end,
                    m.EnergyIntervalFact.period_end > start,
                )
            )
        )
        if len(facts) != 1 or facts[0].period_start != start or facts[0].period_end != end:
            msg = f"{start.isoformat()} 需要唯一完整的设备小时电量，不能缺失或重复"
            raise MaterialAllocationError(msg)
        fact = facts[0]
        fact_amount = Decimal(str(fact.amount))
        if fact.unit not in {"kWh", "MWh"} or not fact_amount.is_finite() or fact_amount < 0:
            msg = "设备电量必须是非负的 kWh 或 MWh"
            raise MaterialAllocationError(msg)
        energy = fact_amount * (1000 if fact.unit == "MWh" else 1)
        operations = list(
            await self.session.scalars(
                select(m.MaterialHandlingOperation)
                .where(
                    m.MaterialHandlingOperation.team_id == self.tenant_id,
                    m.MaterialHandlingOperation.equipment_id == data.equipment_id,
                    m.MaterialHandlingOperation.operation_status == "confirmed",
                    m.MaterialHandlingOperation.period_start < end,
                    m.MaterialHandlingOperation.period_end > start,
                )
                .order_by(m.MaterialHandlingOperation.id)
            )
        )
        occupied: list[tuple[datetime, datetime, int]] = []
        samples = []
        for op in operations:
            if not op.material_id:
                msg = "作业缺少物资主数据，请先修订并确认"
                raise MaterialAllocationError(msg)
            active = intervals(op.active_intervals or [])
            for a, b in active:
                a, b = max(start, a), min(end, b)
                if b > a:
                    if any(a < ob and b > oa and oid != op.id for oa, ob, oid in occupied):
                        msg = "同一设备存在重叠作业时段，请修正作业记录"
                        raise MaterialAllocationError(msg)
                    occupied.append((a, b, op.id))
            samples.append(
                {
                    "id": op.id,
                    "material_id": op.material_id,
                    "material_code": op.material_code,
                    "batch_no": op.batch_no,
                    "quantity": str(op.quantity),
                    "unit": op.unit,
                    "intervals": interval_payload(active),
                    "quality": op.data_quality,
                    "seconds": str(overlap_seconds(active, start, end)),
                }
            )
        snapshot = {
            "command": data.model_dump(mode="json"),
            "hour": start.isoformat(),
            "energy": {
                "id": fact.id,
                "revision": fact.revision_no,
                "amount": str(energy),
                "quality": fact.data_quality,
                "source": fact.source_system,
                "key": fact.source_record_id,
            },
            "factor": {
                "id": factor.id,
                "value": str(factor.factor_value),
                "unit": factor.factor_unit,
                "source": factor.source,
                "year": factor.year,
                "version": factor.source_snapshot_id,
            },
            "operations": samples,
        }
        snapshot["command"]["period_start"] = start.replace(tzinfo=UTC).isoformat()
        snapshot["command"]["period_end"] = end.replace(tzinfo=UTC).isoformat()
        return snapshot, operations, energy, factor.factor_value

    async def execute(self, data: HourCalculation) -> list[m.MaterialCarbonAllocationRun]:  # noqa: PLR0915
        start, end = utc(data.period_start), utc(data.period_end)
        if (
            end <= start
            or end - start > timedelta(days=31)
            or any((v.minute or v.second or v.microsecond) for v in (start, end))
        ):
            msg = "请选择不超过31天的整小时计算区间"
            raise MaterialAllocationError(msg)
        device = await self.session.scalar(
            select(m.MonitorEquipment)
            .where(
                m.MonitorEquipment.id == data.equipment_id,
                m.MonitorEquipment.team_id == self.tenant_id,
                m.MonitorEquipment.is_enable.is_(True),
            )
            .with_for_update()
        )
        if device is None:
            msg = "设备不存在或已停用"
            raise MaterialAllocationError(msg)
        runs = []
        while start < end:
            snapshot, operations, energy, factor = await self.inputs(data, start)
            digest = fingerprint(snapshot)
            run = await self.session.scalar(
                select(m.MaterialCarbonAllocationRun)
                .where(
                    m.MaterialCarbonAllocationRun.team_id == self.tenant_id,
                    m.MaterialCarbonAllocationRun.equipment_id == device.id,
                    m.MaterialCarbonAllocationRun.period_start == start,
                )
                .with_for_update()
            )
            if run and run.input_hash == digest and run.status == "completed":
                runs.append(run)
                start += timedelta(hours=1)
                continue
            if run is None:
                run = m.MaterialCarbonAllocationRun(
                    team_id=self.tenant_id,
                    run_code=f"MCA-{device.id}-{start:%Y%m%d%H}",
                    equipment_id=device.id,
                    period_start=start,
                    period_end=start + timedelta(hours=1),
                    emission_factor=factor,
                    allocation_method=data.assumption,
                    revision=0,
                )
                self.session.add(run)
                await self.session.flush()
            await invalidate_run(self.session, run)
            existing = {
                row.operation_id: row
                for row in await self.session.scalars(
                    select(m.MaterialCarbonAllocationResult).where(
                        m.MaterialCarbonAllocationResult.run_id == run.id,
                        m.MaterialCarbonAllocationResult.team_id == self.tenant_id,
                    )
                )
            }
            total_energy, total_carbon = Decimal(0), Decimal(0)
            for op, sample in zip(operations, snapshot["operations"], strict=True):
                seconds = Decimal(sample["seconds"])
                result = existing.get(op.id)
                if seconds == 0:
                    continue
                amount = allocate(energy, seconds)
                carbon = (amount * factor).quantize(Decimal("0.000001"))
                values = {
                    key: getattr(op, key)
                    for key in (
                        "operation_no",
                        "operation_type",
                        "equipment_id",
                        "equipment_code",
                        "equipment_name",
                        "equipment_type",
                        "area_id",
                        "area_code",
                        "area_name",
                        "material_code",
                        "material_name",
                        "material_spec",
                        "material_category",
                        "batch_no",
                    )
                }
                values.update(
                    source_energy_kwh=energy,
                    driver_amount=seconds,
                    total_driver_amount=Decimal(3600),
                    allocation_ratio=seconds / 3600,
                    allocated_energy_kwh=amount,
                    emission_factor=factor,
                    allocated_co2e_kg=carbon,
                    allocation_method=data.assumption,
                    data_status="ready",
                    energy_source_snapshot={
                        **snapshot,
                        "data_quality": "simulated"
                        if "simulated" in {op.data_quality, snapshot["energy"]["quality"]}
                        else "estimated",
                    },
                )
                if result is None:
                    result = m.MaterialCarbonAllocationResult(
                        team_id=self.tenant_id, run_id=run.id, operation_id=op.id, **values
                    )
                    self.session.add(result)
                else:
                    for key, value in values.items():
                        setattr(result, key, value)
                total_energy += amount
                total_carbon += carbon
            run.input_snapshot = snapshot
            run.input_hash = digest
            run.factor_id = data.factor_id
            run.emission_factor = factor
            run.allocation_method = data.assumption
            run.total_energy_kwh = total_energy
            run.total_co2e_kg = total_carbon
            run.unallocated_energy_kwh = energy - total_energy
            run.revision += 1
            run.status = "completed"
            run.completed_at = datetime.now(UTC).replace(tzinfo=None)
            run.summary_snapshot = {
                "source_energy_kwh": str(energy),
                "unallocated_energy_kwh": str(energy - total_energy),
            }
            runs.append(run)
            start += timedelta(hours=1)
        await self.session.flush()
        return runs

    async def require_current(self, run: m.MaterialCarbonAllocationRun) -> None:
        if run.team_id != self.tenant_id or run.status != "completed" or not run.input_hash:
            msg = "分摊结果需要重新计算"
            raise MaterialAllocationError(msg)
        data = HourCalculation.model_validate((run.input_snapshot or {}).get("command", {}))
        snapshot, _, _, _ = await self.inputs(data, run.period_start)
        if fingerprint(snapshot) != run.input_hash:
            msg = "能源、因子或作业已变更，请重新计算"
            raise MaterialAllocationError(msg)
