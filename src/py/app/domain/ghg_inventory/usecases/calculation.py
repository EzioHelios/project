"""Versioned organization-inventory calculation use case."""

from __future__ import annotations

# ruff: noqa: RUF001 - Chinese business messages are intentional.
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import func, select

from app.domain.carbon.models import OrganizationBoundary, ReportingPeriod
from app.domain.ghg_inventory.domain.calculation import calculate
from app.domain.ghg_inventory.models import (
    GhgActivityAllocation,
    GhgActivityRecord,
    GhgCalculationMethodDefinition,
    GhgCalculationResult,
    GhgCalculationRun,
    GhgEvidenceLink,
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

    async def execute(  # noqa: C901, PLR0915 - one transaction freezes and calculates the complete inventory
        self,
        *,
        inventory_code: str,
        reporting_profile_code: str,
        reporting_period_id: int | None,
        reporting_org_id: int | None = None,
        organization_boundary_id: int | None = None,
        default_scope2_method: str = "location",
    ) -> GhgCalculationRun:
        require_session_tenant_id(self.session)
        if default_scope2_method not in {"location", "market"}:
            msg = "Scope 2口径只能选择地点法或市场法"
            raise ValueError(msg)
        profile = await self.session.scalar(
            select(GhgReportingProfile)
            .where(GhgReportingProfile.code == reporting_profile_code, GhgReportingProfile.status == "published")
            .order_by(GhgReportingProfile.effective_from.desc())
        )
        if profile is None:
            msg = "报告配置不存在或尚未发布"
            raise ValueError(msg)
        period = None
        if reporting_period_id is not None:
            period = await self.session.scalar(select(ReportingPeriod).where(ReportingPeriod.id == reporting_period_id))
            if period is None:
                msg = "报告期间不存在"
                raise ValueError(msg)
            if reporting_org_id is not None and period.reporting_org_id != reporting_org_id:
                msg = "报告期间不属于所选报告组织"
                raise ValueError(msg)
            reporting_org_id = period.reporting_org_id
        boundary = None
        if organization_boundary_id is not None:
            boundary = await self.session.scalar(
                select(OrganizationBoundary).where(OrganizationBoundary.id == organization_boundary_id)
            )
            if boundary is None:
                msg = "组织边界不存在"
                raise ValueError(msg)
            if boundary.status != "published":
                msg = "组织边界尚未发布"
                raise ValueError(msg)
            if reporting_org_id is not None and boundary.reporting_org_id != reporting_org_id:
                msg = "组织边界不属于所选报告组织"
                raise ValueError(msg)
            if reporting_period_id is not None and boundary.period_id != reporting_period_id:
                msg = "组织边界不属于所选报告期间"
                raise ValueError(msg)
            reporting_org_id = boundary.reporting_org_id
            reporting_period_id = boundary.period_id
        activity_filters = [
            GhgActivityRecord.inventory_code == inventory_code,
            GhgActivityRecord.boundary_status == "included",
            GhgActivityRecord.status == "approved",
        ]
        if reporting_period_id is not None:
            activity_filters.append(GhgActivityRecord.reporting_period_id == reporting_period_id)
        if organization_boundary_id is not None:
            activity_filters.append(GhgActivityRecord.organization_boundary_id == organization_boundary_id)
        activities = list((await self.session.execute(select(GhgActivityRecord).where(*activity_filters))).scalars())
        if not activities:
            msg = "盘查任务没有可计算的已批准活动数据"
            raise ValueError(msg)
        period_ids = {item.reporting_period_id for item in activities if item.reporting_period_id is not None}
        boundary_ids = {
            item.organization_boundary_id for item in activities if item.organization_boundary_id is not None
        }
        organization_codes = {item.organization_code for item in activities}
        if reporting_period_id is None and len(period_ids) > 1:
            msg = "盘查任务包含多个报告期间，请明确选择报告期间"
            raise ValueError(msg)
        if organization_boundary_id is None and len(boundary_ids) > 1:
            msg = "盘查任务包含多个组织边界，请明确选择边界版本"
            raise ValueError(msg)
        reporting_period_id = reporting_period_id or next(iter(period_ids), None)
        organization_boundary_id = organization_boundary_id or next(iter(boundary_ids), None)
        if reporting_org_id is None and reporting_period_id is not None:
            period = await self.session.scalar(select(ReportingPeriod).where(ReportingPeriod.id == reporting_period_id))
            reporting_org_id = period.reporting_org_id if period else None
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
            reporting_org_id=reporting_org_id,
            reporting_period_id=reporting_period_id,
            organization_boundary_id=organization_boundary_id,
            default_scope2_method=default_scope2_method,
            status="running",
            input_snapshot={
                "reportingProfile": {
                    "code": profile.code,
                    "version": profile.version,
                    "standardCode": profile.standard_code,
                    "standardVersion": profile.standard_version,
                },
                "context": {
                    "reportingOrgId": reporting_org_id,
                    "reportingPeriodId": reporting_period_id,
                    "organizationBoundaryId": organization_boundary_id,
                    "organizationCodes": sorted(organization_codes),
                    "defaultScope2Method": default_scope2_method,
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

        calculated_results: list[GhgCalculationResult] = []
        failures: list[dict[str, str]] = []
        for activity in activities:
            try:
                result = await self._calculate_activity(run, activity)
            except ValueError as exc:
                failures.append({"recordCode": activity.record_code, "reason": str(exc)})
                continue
            calculated_results.append(result)

        if failures:
            run.status = "failed"
            run.input_snapshot = {**run.input_snapshot, "failures": failures}
            run.completed_at = datetime.now().astimezone()
            await self.session.commit()
            msg = f"{len(failures)} 条活动记录缺少有效方法或参数"
            raise ValueError(msg)
        evidence_record_count = int(
            await self.session.scalar(
                select(func.count(func.distinct(GhgEvidenceLink.record_code))).where(
                    GhgEvidenceLink.record_type == "activity",
                    GhgEvidenceLink.record_code.in_([item.record_code for item in activities]),
                )
            )
            or 0
        )
        summary = _build_summary(calculated_results, default_scope2_method=default_scope2_method)
        quality_counts = {
            status: sum(1 for activity in activities if activity.quality_status == status)
            for status in ("pass", "warning", "failed")
        }
        run.summary_snapshot = summary
        run.quality_snapshot = {
            "activityCount": len(activities),
            "allocationCoveragePct": "100.00",
            "evidenceRecordCount": evidence_record_count,
            "evidenceCoveragePct": str(
                (Decimal(evidence_record_count) / Decimal(len(activities)) * Decimal(100)).quantize(Decimal("0.01"))
            ),
            "qualityCounts": quality_counts,
        }
        run.total_co2e_kg = Decimal(str(summary["defaultTotalCo2eKg"]))
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


def _build_summary(
    results: list[GhgCalculationResult],
    *,
    default_scope2_method: str,
) -> dict[str, Any]:
    direct_and_value_chain = [result for result in results if result.ghg_scope != "scope2"]
    scope2_common = [
        result for result in results if result.ghg_scope == "scope2" and result.scope2_method == "not_applicable"
    ]
    scope2_location = [
        result for result in results if result.ghg_scope == "scope2" and result.scope2_method == "location"
    ]
    scope2_market = [result for result in results if result.ghg_scope == "scope2" and result.scope2_method == "market"]
    has_scope2 = any(result.ghg_scope == "scope2" for result in results)
    location_available = not has_scope2 or bool(scope2_location or scope2_common)
    market_available = not has_scope2 or bool(scope2_market or scope2_common)
    base_total = sum((result.co2e_kg for result in direct_and_value_chain), Decimal(0))
    location_total = base_total + sum((result.co2e_kg for result in scope2_common + scope2_location), Decimal(0))
    market_total = base_total + sum((result.co2e_kg for result in scope2_common + scope2_market), Decimal(0))
    selected_results = [
        result
        for result in results
        if result.ghg_scope != "scope2" or result.scope2_method in {"not_applicable", default_scope2_method}
    ]
    scope_totals: dict[str, Decimal] = {}
    iso_totals: dict[str, Decimal] = {}
    for result in selected_results:
        scope_totals[result.ghg_scope] = scope_totals.get(result.ghg_scope, Decimal(0)) + result.co2e_kg
        iso_totals[result.iso_category_code] = iso_totals.get(result.iso_category_code, Decimal(0)) + result.co2e_kg
    default_total = location_total if default_scope2_method == "location" else market_total
    return {
        "defaultScope2Method": default_scope2_method,
        "defaultTotalCo2eKg": str(default_total),
        "totalLocationCo2eKg": str(location_total) if location_available else None,
        "totalMarketCo2eKg": str(market_total) if market_available else None,
        "scope2LocationAvailable": location_available,
        "scope2MarketAvailable": market_available,
        "scopeTotals": {key: str(value) for key, value in sorted(scope_totals.items())},
        "isoCategoryTotals": {key: str(value) for key, value in sorted(iso_totals.items())},
    }
