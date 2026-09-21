"""Read models for material handling carbon allocation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict
from app.domain.material_allocation.usecases import CalculateMaterialCarbonAllocation, MaterialAllocationError
from app.lib.tenancy import require_session_tenant_id


class MaterialAllocationQueryService:
    """Query material handling operations, runs and allocation results."""

    def __init__(self, session: Any) -> None:
        self._session = session
        self.tenant_id = require_session_tenant_id(session)

    async def options(self) -> dict[str, Any]:
        result = {}
        for key, model in (
            ("devices", m.MonitorEquipment),
            ("materials", m.ProductionProduct),
            ("studies", m.ProductFootprintStudy),
            ("stages", m.ProductLifeCycleStage),
        ):
            result[key] = [
                model_to_dict(row)
                for row in await self._session.scalars(select(model).where(model.team_id == self.tenant_id))
            ]
        result["factors"] = [
            model_to_dict(row)
            for row in await self._session.scalars(
                select(m.EmissionFactor).where(
                    (m.EmissionFactor.team_id.is_(None) | (m.EmissionFactor.team_id == self.tenant_id)),
                    m.EmissionFactor.is_active.is_(True),
                    m.EmissionFactor.review_status == "approved",
                    m.EmissionFactor.unit == "kWh",
                    m.EmissionFactor.factor_unit == "kgCO2e/kWh",
                )
            )
        ]
        rows = (
            await self._session.execute(
                select(m.EnergyIntervalFact.equipment_id, m.EnergyIntervalFact.source_system)
                .where(
                    m.EnergyIntervalFact.team_id == self.tenant_id,
                    m.EnergyIntervalFact.is_current.is_(True),
                    m.EnergyIntervalFact.granularity == "hour",
                )
                .distinct()
            )
        ).all()
        result["sources"] = [{"equipment_id": r[0], "source_system": r[1]} for r in rows]
        return result

    async def operations(self, filters: dict[str, Any]) -> dict[str, Any]:
        conditions = []
        keyword = filters.get("keyword")
        if keyword:
            like = f"%{keyword}%"
            conditions.append(
                (m.MaterialHandlingOperation.operation_no.ilike(like))
                | (m.MaterialHandlingOperation.material_code.ilike(like))
                | (m.MaterialHandlingOperation.material_name.ilike(like))
                | (m.MaterialHandlingOperation.equipment_code.ilike(like))
            )
        conditions.extend(
            getattr(m.MaterialHandlingOperation, field) == filters[field]
            for field in ("operation_type", "equipment_type", "material_code", "batch_no", "operation_status")
            if filters.get(field)
        )
        return await self._paged(m.MaterialHandlingOperation, conditions, filters, sort_default="period_start")

    async def runs(self, filters: dict[str, Any]) -> dict[str, Any]:
        conditions = []
        if filters.get("status"):
            conditions.append(m.MaterialCarbonAllocationRun.status == filters["status"])
        data = await self._paged(m.MaterialCarbonAllocationRun, conditions, filters, sort_default="created_at")
        devices = {
            row.id: row.name
            for row in await self._session.scalars(
                select(m.MonitorEquipment).where(
                    m.MonitorEquipment.team_id == self.tenant_id,
                    m.MonitorEquipment.id.in_([item["equipment_id"] for item in data["items"]]),
                )
            )
        }
        for item in data["items"]:
            item["equipment_name"] = devices.get(item["equipment_id"])
        return data

    async def results(self, filters: dict[str, Any]) -> dict[str, Any]:
        conditions = []
        if filters.get("study_id"):
            product_id = await self._session.scalar(
                select(m.ProductFootprintStudy.product_id).where(
                    m.ProductFootprintStudy.team_id == self.tenant_id,
                    m.ProductFootprintStudy.id == int(filters["study_id"]),
                )
            )
            operation_ids = select(m.MaterialHandlingOperation.id).where(
                m.MaterialHandlingOperation.team_id == self.tenant_id,
                m.MaterialHandlingOperation.material_id == (product_id or -1),
            )
            conditions.append(m.MaterialCarbonAllocationResult.operation_id.in_(operation_ids))
        if filters.get("run_id"):
            conditions.append(m.MaterialCarbonAllocationResult.run_id == int(filters["run_id"]))
        if filters.get("run_code"):
            run = await self._session.scalar(
                select(m.MaterialCarbonAllocationRun.id).where(
                    m.MaterialCarbonAllocationRun.run_code == filters["run_code"]
                )
            )
            conditions.append(m.MaterialCarbonAllocationResult.run_id == (run or -1))
        conditions.extend(
            getattr(m.MaterialCarbonAllocationResult, field) == filters[field]
            for field in ("material_code", "batch_no", "equipment_code", "data_status")
            if filters.get(field)
        )
        return await self._paged(m.MaterialCarbonAllocationResult, conditions, filters, sort_default="created_at")

    async def summary(self) -> dict[str, Any]:
        operation_count = int(await self._session.scalar(select(func.count(m.MaterialHandlingOperation.id))) or 0)
        valid_runs = []
        for run in await self._session.scalars(
            select(m.MaterialCarbonAllocationRun).where(
                m.MaterialCarbonAllocationRun.team_id == self.tenant_id,
                m.MaterialCarbonAllocationRun.status == "completed",
            )
        ):
            try:
                await CalculateMaterialCarbonAllocation(self._session).require_current(run)
            except ValueError:
                continue
            valid_runs.append(run)
        ready_count = int(
            await self._session.scalar(
                select(func.count(m.MaterialCarbonAllocationResult.id)).where(
                    m.MaterialCarbonAllocationResult.data_status == "ready",
                    m.MaterialCarbonAllocationResult.team_id == self.tenant_id,
                    m.MaterialCarbonAllocationResult.run_id.in_([run.id for run in valid_runs]),
                )
            )
            or 0
        )
        return {
            "operationCount": operation_count,
            "runCount": len(valid_runs),
            "readyResultCount": ready_count,
            "totalAllocatedEnergyKwh": float(sum(run.total_energy_kwh for run in valid_runs)),
            "totalAllocatedCo2eKg": float(sum(run.total_co2e_kg for run in valid_runs)),
        }

    async def _paged(
        self, model: type[Any], conditions: list[Any], filters: dict[str, Any], *, sort_default: str
    ) -> dict[str, Any]:
        limit = min(200, max(1, int(filters.get("limit") or 50)))
        offset = max(0, int(filters.get("offset") or 0))
        sort_field = str(filters.get("sort_field") or sort_default)
        sort_order = str(filters.get("sort_order") or "desc").lower()
        column = getattr(model, sort_field, getattr(model, sort_default))
        order_by = column.desc() if sort_order == "desc" else column.asc()
        conditions.append(model.team_id == self.tenant_id)
        total = int(await self._session.scalar(select(func.count(model.id)).where(*conditions)) or 0)
        rows = (
            await self._session.execute(select(model).where(*conditions).order_by(order_by).limit(limit).offset(offset))
        ).scalars()
        items = []
        for row in rows:
            item = model_to_dict(row)
            if model in (m.MaterialCarbonAllocationRun, m.MaterialCarbonAllocationResult):
                run = (
                    row
                    if model == m.MaterialCarbonAllocationRun
                    else await self._session.get(m.MaterialCarbonAllocationRun, row.run_id)
                )
                try:
                    await CalculateMaterialCarbonAllocation(self._session).require_current(run)
                except (MaterialAllocationError, ValueError):
                    item["status" if model == m.MaterialCarbonAllocationRun else "data_status"] = "stale"
            items.append(item)
        return {"items": items, "total": total, "limit": limit, "offset": offset}
