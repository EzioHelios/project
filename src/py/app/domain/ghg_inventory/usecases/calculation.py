"""Versioned organization-inventory calculation use case."""

from __future__ import annotations

# ruff: noqa: RUF001 - Chinese business messages are intentional.
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from app.domain.ghg_inventory.domain.calculation import calculate
from app.domain.ghg_inventory.models import (
    GhgActivityAllocation,
    GhgActivityRecord,
    GhgCalculationMethodDefinition,
    GhgCalculationResult,
    GhgCalculationRun,
    GhgMethodParameterDefinition,
    GhgParameterAssignment,
    GhgParameterValue,
    GhgReportingProfile,
)
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RunInventoryCalculation:
    """Resolve each parameter independently, freeze assignments, then calculate."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self,
        *,
        inventory_code: str,
        reporting_profile_code: str,
        reporting_period_id: int | None,
    ) -> GhgCalculationRun:
        require_session_tenant_id(self.session)
        profile = await self.session.scalar(
            select(GhgReportingProfile)
            .where(GhgReportingProfile.code == reporting_profile_code, GhgReportingProfile.status == "published")
            .order_by(GhgReportingProfile.effective_from.desc())
        )
        if profile is None:
            msg = "报告配置不存在或尚未发布"
            raise ValueError(msg)
        activities = list(
            (
                await self.session.execute(
                    select(GhgActivityRecord).where(
                        GhgActivityRecord.inventory_code == inventory_code,
                        GhgActivityRecord.boundary_status == "included",
                        GhgActivityRecord.status == "approved",
                    )
                )
            ).scalars()
        )
        if not activities:
            msg = "盘查任务没有可计算的已批准活动数据"
            raise ValueError(msg)
        activity_ids = [activity.id for activity in activities]
        allocations = list(
            (
                await self.session.scalars(
                    select(GhgActivityAllocation).where(GhgActivityAllocation.activity_id.in_(activity_ids))
                )
            ).all()
        )
        allocations_by_activity: dict[int, list[GhgActivityAllocation]] = {}
        for allocation in allocations:
            allocations_by_activity.setdefault(allocation.activity_id, []).append(allocation)
        incomplete = [
            activity.record_code
            for activity in activities
            if abs(
                sum(
                    (item.allocation_ratio for item in allocations_by_activity.get(activity.id, [])),
                    Decimal(0),
                )
                - Decimal(1)
            )
            > Decimal("0.000001")
        ]
        if incomplete:
            msg = f"{len(incomplete)} 条活动尚未完成100%区域归集"
            raise ValueError(msg)

        run = GhgCalculationRun(
            run_code=f"CALC-{uuid4().hex[:16].upper()}",
            inventory_code=inventory_code,
            reporting_profile_id=profile.id,
            reporting_period_id=reporting_period_id,
            status="running",
            input_snapshot={
                "reportingProfile": {
                    "code": profile.code,
                    "version": profile.version,
                    "standardCode": profile.standard_code,
                    "standardVersion": profile.standard_version,
                },
                "activityCount": len(activities),
                "allocationCount": len(allocations),
                "allocations": [
                    {
                        "recordCode": activity.record_code,
                        "items": [
                            {
                                "allocationCode": item.allocation_code,
                                "areaId": item.area_id,
                                "areaCode": item.area_code_snapshot,
                                "areaPath": item.area_path_snapshot,
                                "equipmentId": item.equipment_id,
                                "equipmentCode": item.equipment_code_snapshot,
                                "role": item.allocation_role,
                                "ratio": str(item.allocation_ratio),
                            }
                            for item in allocations_by_activity.get(activity.id, [])
                        ],
                    }
                    for activity in activities
                ],
            },
            started_at=datetime.now().astimezone(),
        )
        self.session.add(run)
        await self.session.flush()

        total = Decimal(0)
        failures: list[dict[str, str]] = []
        for activity in activities:
            try:
                result = await self._calculate_activity(run, activity)
            except ValueError as exc:
                failures.append({"recordCode": activity.record_code, "reason": str(exc)})
                continue
            total += result.co2e_kg

        if failures:
            run.status = "failed"
            run.input_snapshot = {**run.input_snapshot, "failures": failures}
            run.completed_at = datetime.now().astimezone()
            await self.session.commit()
            msg = f"{len(failures)} 条活动记录缺少有效方法或参数"
            raise ValueError(msg)
        run.total_co2e_kg = total
        run.status = "completed"
        run.completed_at = datetime.now().astimezone()
        await self.session.commit()
        return run

    async def _calculate_activity(
        self,
        run: GhgCalculationRun,
        activity: GhgActivityRecord,
    ) -> GhgCalculationResult:
        method_code = str(activity.source_payload.get("method_code") or "")
        if not method_code:
            msg = f"活动 {activity.record_code} 未冻结计算方法"
            raise ValueError(msg)
        method = await self.session.scalar(
            select(GhgCalculationMethodDefinition).where(
                GhgCalculationMethodDefinition.code == method_code,
                GhgCalculationMethodDefinition.status == "published",
            )
        )
        if method is None:
            msg = f"活动 {activity.record_code} 没有已发布计算方法"
            raise ValueError(msg)

        prefix = f"{activity.inventory_code}:{activity.parameter_set_code}:"
        parameter_rows = list(
            (
                await self.session.execute(
                    select(GhgParameterValue).where(
                        GhgParameterValue.value_code.startswith(prefix),
                        GhgParameterValue.status == "active",
                        GhgParameterValue.approval_status == "approved",
                    )
                )
            ).scalars()
        )
        parameters = {row.parameter_code: row.value for row in parameter_rows}
        required = set(
            (
                await self.session.execute(
                    select(GhgMethodParameterDefinition.parameter_code).where(
                        GhgMethodParameterDefinition.method_id == method.id,
                        GhgMethodParameterDefinition.required.is_(True),
                    )
                )
            ).scalars()
        )
        missing = required - parameters.keys()
        if missing:
            msg = f"活动 {activity.record_code} 缺少参数：{', '.join(sorted(missing))}"
            raise ValueError(msg)

        for row in parameter_rows:
            self.session.add(
                GhgParameterAssignment(
                    run_id=run.id,
                    activity_id=activity.id,
                    method_id=method.id,
                    parameter_value_id=row.id,
                    parameter_code=row.parameter_code,
                    parameter_role=row.parameter_role,
                    value=row.value,
                    unit=row.unit,
                    source_mode=row.source_mode,
                    source_name=row.source_name,
                    source_version=row.source_version,
                    standard_code=row.standard_code,
                    clause_reference=row.clause_reference,
                    table_reference=row.table_reference,
                    selection_rule="工作簿显式参数集，经方法必填项与来源校验后采用",
                    snapshot={
                        "valueCode": row.value_code,
                        "validFrom": row.valid_from.isoformat() if row.valid_from else None,
                        "validTo": row.valid_to.isoformat() if row.valid_to else None,
                        "referenceYear": row.reference_year,
                        "geography": row.geography,
                        "technology": row.technology,
                        "fuelOrMaterial": row.fuel_or_material,
                        "qualityGrade": row.quality_grade,
                        "evidenceCode": row.evidence_code,
                    },
                )
            )
        output = calculate(method.code, activity.activity_amount, parameters, activity.source_payload)
        formula_snapshot: dict[str, Any] = {
            "methodCode": method.code,
            "methodVersion": method.version,
            "methodName": method.name,
            "standardCode": method.standard_code,
            "clauseReference": method.clause_reference,
            "humanFormula": method.human_formula,
            "activity": {"value": str(activity.activity_amount), "unit": activity.activity_unit},
            "parameters": [
                {
                    "code": row.parameter_code,
                    "value": str(row.value),
                    "unit": row.unit,
                    "sourceMode": row.source_mode,
                    "sourceName": row.source_name,
                    "sourceVersion": row.source_version,
                }
                for row in parameter_rows
            ],
            "result": {"gasMassKg": str(output.gas_mass_kg), "co2eKg": str(output.co2e_kg)},
        }
        result = GhgCalculationResult(
            run_id=run.id,
            activity_id=activity.id,
            method_id=method.id,
            iso_category_code=activity.iso_category_code,
            ghg_scope=activity.ghg_scope,
            gas_code=output.gas_code,
            gas_mass_kg=output.gas_mass_kg,
            gwp_value=output.gwp_value,
            gwp_version="reporting-profile",
            co2e_kg=output.co2e_kg,
            scope2_method=output.scope2_method,
            result_kind=output.result_kind,
            formula_snapshot=formula_snapshot,
            quality_status=activity.quality_status,
        )
        self.session.add(result)
        return result
