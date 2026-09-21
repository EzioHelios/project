"""Explicit, idempotent PCF references to current material allocation results."""

# ruff: noqa: RUF001
from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.db import models as m
from app.domain.material_allocation.policies import MaterialAllocationError
from app.domain.material_allocation.usecases import CalculateMaterialCarbonAllocation
from app.lib.tenancy import require_session_tenant_id


class MaterialResultImportUseCase:
    def __init__(self, session: Any) -> None:
        self.session = session
        self.tenant_id = require_session_tenant_id(session)

    async def import_result(self, study_id: int, result_id: int, stage_id: int) -> m.ProductFootprintInventoryItem:
        study = await self.session.scalar(
            select(m.ProductFootprintStudy)
            .where(m.ProductFootprintStudy.id == study_id, m.ProductFootprintStudy.team_id == self.tenant_id)
            .with_for_update()
        )
        result = await self.session.scalar(
            select(m.MaterialCarbonAllocationResult)
            .where(
                m.MaterialCarbonAllocationResult.id == result_id,
                m.MaterialCarbonAllocationResult.team_id == self.tenant_id,
            )
            .with_for_update()
        )
        stage = await self.session.scalar(
            select(m.ProductLifeCycleStage).where(
                m.ProductLifeCycleStage.id == stage_id,
                m.ProductLifeCycleStage.team_id == self.tenant_id,
                m.ProductLifeCycleStage.study_id == study_id,
                m.ProductLifeCycleStage.included.is_(True),
            )
        )
        if not study or not result or not stage or result.data_status != "ready":
            msg = "请选择当前研究的有效阶段和有效分摊结果"
            raise MaterialAllocationError(msg)
        run = await self.session.get(m.MaterialCarbonAllocationRun, result.run_id)
        await CalculateMaterialCarbonAllocation(self.session).require_current(run)
        operation = await self.session.get(m.MaterialHandlingOperation, result.operation_id)
        if study.product_id != operation.material_id:
            msg = "结果物资与研究产品不一致，不能直接引用"
            raise MaterialAllocationError(msg)
        if (
            run.period_start.date() < study.period_start
            or (run.period_end - timedelta(microseconds=1)).date() > study.period_end
        ):
            msg = "分摊期间不在研究期间内"
            raise MaterialAllocationError(msg)
        item = (
            await self.session.get(m.ProductFootprintInventoryItem, result.product_footprint_item_id)
            if result.product_footprint_item_id
            else None
        )
        if item and item.study_id != study_id:
            msg = "结果已被其他研究引用，请先取消原引用"
            raise MaterialAllocationError(msg)
        # Unknown manual energy provenance cannot establish a non-overlapping boundary.
        other_energy = list(
            await self.session.scalars(
                select(m.ProductFootprintInventoryItem).where(
                    m.ProductFootprintInventoryItem.team_id == self.tenant_id,
                    m.ProductFootprintInventoryItem.study_id == study_id,
                    m.ProductFootprintInventoryItem.included.is_(True),
                    m.ProductFootprintInventoryItem.activity_type == "energy",
                )
            )
        )
        if any(other.source_type != "material_allocation" for other in other_energy):
            msg = "研究已有其他电力输入，请明确并消除重复能源边界后引用"
            raise MaterialAllocationError(msg)
        source_ref = f"material-hour:{run.id}:operation:{operation.id}"
        payload = {
            "study_id": study_id,
            "stage_id": stage_id,
            "item_no": f"MHA-{run.id}-{operation.id}",
            "activity_type": "energy",
            "item_name": f"{result.material_name}仓储作业电力",
            "activity_amount": result.allocated_energy_kwh,
            "activity_unit": "kWh",
            "factor_id": run.factor_id,
            "factor_value": result.emission_factor,
            "factor_unit": "kgCO2e/kWh",
            "factor_source": run.input_snapshot["factor"]["source"],
            "computed_co2e": result.allocated_co2e_kg,
            "data_quality": result.energy_source_snapshot["data_quality"],
            "calc_status": "ready",
            "source_type": "material_allocation",
            "source_ref": source_ref,
            "allocation_ratio": 1,
            "included": True,
            "evidence_path": run.input_hash,
        }
        if item is None:
            item = m.ProductFootprintInventoryItem(team_id=self.tenant_id, **payload)
            self.session.add(item)
            await self.session.flush()
            result.product_footprint_item_id = item.id
        else:
            for key, value in payload.items():
                setattr(item, key, value)
        study.result_status = "pending"
        await self.session.flush()
        return item

    async def unlink(self, item_id: int) -> None:
        item = await self.session.scalar(
            select(m.ProductFootprintInventoryItem)
            .where(
                m.ProductFootprintInventoryItem.id == item_id,
                m.ProductFootprintInventoryItem.team_id == self.tenant_id,
                m.ProductFootprintInventoryItem.source_type == "material_allocation",
            )
            .with_for_update()
        )
        if item is None:
            msg = "物资分摊引用不存在"
            raise MaterialAllocationError(msg)
        result = await self.session.scalar(
            select(m.MaterialCarbonAllocationResult).where(
                m.MaterialCarbonAllocationResult.team_id == self.tenant_id,
                m.MaterialCarbonAllocationResult.product_footprint_item_id == item.id,
            )
        )
        if result:
            result.product_footprint_item_id = None
        study = await self.session.get(m.ProductFootprintStudy, item.study_id)
        study.result_status = "pending"
        await self.session.delete(item)
        await self.session.flush()

    async def validate_study(self, study_id: int) -> None:
        study = await self.session.scalar(
            select(m.ProductFootprintStudy).where(
                m.ProductFootprintStudy.team_id == self.tenant_id,
                m.ProductFootprintStudy.id == study_id,
            )
        )
        items = list(
            await self.session.scalars(
                select(m.ProductFootprintInventoryItem).where(
                    m.ProductFootprintInventoryItem.team_id == self.tenant_id,
                    m.ProductFootprintInventoryItem.study_id == study_id,
                    m.ProductFootprintInventoryItem.source_type == "material_allocation",
                    m.ProductFootprintInventoryItem.included.is_(True),
                )
            )
        )
        if items and await self.session.scalar(
            select(m.ProductFootprintInventoryItem.id)
            .where(
                m.ProductFootprintInventoryItem.team_id == self.tenant_id,
                m.ProductFootprintInventoryItem.study_id == study_id,
                m.ProductFootprintInventoryItem.included.is_(True),
                m.ProductFootprintInventoryItem.activity_type == "energy",
                m.ProductFootprintInventoryItem.source_type != "material_allocation",
            )
            .limit(1)
        ):
            msg = "研究存在其他电力输入，请先消除重复能源边界"
            raise MaterialAllocationError(msg)
        for item in items:
            result = await self.session.scalar(
                select(m.MaterialCarbonAllocationResult).where(
                    m.MaterialCarbonAllocationResult.team_id == self.tenant_id,
                    m.MaterialCarbonAllocationResult.product_footprint_item_id == item.id,
                )
            )
            if not result or result.data_status != "ready":
                msg = "物资分摊引用已失效，请重新计算并同步"
                raise MaterialAllocationError(msg)
            run = await self.session.get(m.MaterialCarbonAllocationRun, result.run_id)
            await CalculateMaterialCarbonAllocation(self.session).require_current(run)
            operation = await self.session.get(m.MaterialHandlingOperation, result.operation_id)
            stage = await self.session.get(m.ProductLifeCycleStage, item.stage_id)
            if (
                not study
                or study.product_id != operation.material_id
                or not stage
                or not stage.included
                or stage.study_id != study_id
                or run.period_start.date() < study.period_start
                or (run.period_end - timedelta(microseconds=1)).date() > study.period_end
            ):
                msg = "研究产品、期间或阶段已变更，请重新引用作业结果"
                raise MaterialAllocationError(msg)
            if item.evidence_path != run.input_hash:
                msg = "物资分摊已更新，请同步引用"
                raise MaterialAllocationError(msg)
