"""Organization GHG inventory analytics read models."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import func, select

from app.domain.carbon.models import (
    EnergyCarbonBudgetAllocation,
    MonitorEquipment,
    MonitorSector,
    OrganizationBoundary,
    ReportingOrganization,
    ReportingPeriod,
)
from app.domain.energy_budget.domain.policies import execution_rate_pct, execution_status
from app.domain.energy_budget.queries.budget import EnergyBudgetQuery, EnergyBudgetQueryService
from app.domain.ghg_inventory.domain.catalog import CATEGORY_BY_CODE
from app.domain.ghg_inventory.models import (
    GhgActivityAllocation,
    GhgActivityRecord,
    GhgCalculationMethodDefinition,
    GhgCalculationResult,
    GhgCalculationRun,
    GhgEmissionSource,
    GhgEvidenceFile,
    GhgEvidenceLink,
    GhgInventoryReport,
    GhgInventoryReportReview,
    GhgMethodParameterDefinition,
    GhgParameterAssignment,
    GhgParameterValue,
    GhgReportingProfile,
)
from app.domain.ghg_inventory.queries.result_slice import (
    GhgAnalyticsFilter,
    GhgAttributedResultRow,
    GhgResultSliceQuery,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement


SCOPE_LABELS = {"scope1": "Scope 1", "scope2": "Scope 2", "scope3": "Scope 3"}
ISO_GROUP_LABELS = {
    "1": "直接温室气体排放",
    "2": "输入能源间接排放",
    "3": "运输间接排放",
    "4": "使用产品间接排放",
    "5": "与组织产品使用相关的间接排放",
    "6": "其他间接排放",
}
SOURCE_DISPLAY_LABELS = {"waste_municipal_incineration": "生活垃圾焚烧"}
SOURCE_PERIOD_SUFFIX = re.compile(r"(?:\s+|[-_])(?:20\d{4}|\d{1,2})$")
MIN_COMPARISON_RUNS = 2
MAX_COMPARISON_RUNS = 3
DECEMBER = 12
ResultRow = tuple[
    GhgCalculationResult,
    GhgActivityRecord,
    GhgCalculationMethodDefinition,
    GhgEmissionSource | None,
]


class GhgAnalyticsQueryService:
    """Build consistent analysis projections from one frozen calculation run."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def calculation_runs(
        self,
        *,
        inventory_code: str | None,
        reporting_org_id: int | None,
        reporting_period_id: int | None,
        organization_boundary_id: int | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        filters: list[ColumnElement[bool]] = []
        if inventory_code:
            filters.append(GhgCalculationRun.inventory_code == inventory_code)
        if reporting_org_id is not None:
            filters.append(GhgCalculationRun.reporting_org_id == reporting_org_id)
        if reporting_period_id is not None:
            filters.append(GhgCalculationRun.reporting_period_id == reporting_period_id)
        if organization_boundary_id is not None:
            filters.append(GhgCalculationRun.organization_boundary_id == organization_boundary_id)
        if status:
            filters.append(GhgCalculationRun.status == status)
        total = int(await self.session.scalar(select(func.count()).select_from(GhgCalculationRun).where(*filters)) or 0)
        rows = list(
            (
                await self.session.execute(
                    select(
                        GhgCalculationRun,
                        GhgReportingProfile,
                        ReportingOrganization,
                        ReportingPeriod,
                        OrganizationBoundary,
                    )
                    .join(GhgReportingProfile, GhgReportingProfile.id == GhgCalculationRun.reporting_profile_id)
                    .outerjoin(ReportingOrganization, ReportingOrganization.id == GhgCalculationRun.reporting_org_id)
                    .outerjoin(ReportingPeriod, ReportingPeriod.id == GhgCalculationRun.reporting_period_id)
                    .outerjoin(
                        OrganizationBoundary, OrganizationBoundary.id == GhgCalculationRun.organization_boundary_id
                    )
                    .where(*filters)
                    .order_by(GhgCalculationRun.started_at.desc(), GhgCalculationRun.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return {
            "items": [self._run_list_item(*row) for row in rows],
            "total": total,
        }

    async def overview(
        self,
        *,
        run_code: str | None,
        scope2_method: str | None,
        analytics_filter: GhgAnalyticsFilter | None = None,
    ) -> dict[str, Any]:
        if analytics_filter is not None:
            return await self._overview_from_filter(analytics_filter)
        run = await self._resolve_run(run_code)
        method = scope2_method or run.default_scope2_method
        self._validate_scope2_method(method)
        context = await self._run_context(run)
        rows = await self._result_rows(run.id)
        selected = [row for row in rows if self._result_selected(row[0], method)]
        activity_ids = {activity.id for _, activity, _, _ in selected}
        evidence_by_record = await self._evidence_counts({activity.record_code for _, activity, _, _ in selected})
        allocations = await self._allocations(activity_ids)
        allocation_by_activity: dict[int, list[GhgActivityAllocation]] = defaultdict(list)
        for allocation_item in allocations:
            allocation_by_activity[allocation_item.activity_id].append(allocation_item)

        total, available = self._method_total(run, method)
        denominator = total if total is not None else sum((result.co2e_kg for result, _, _, _ in selected), Decimal(0))
        scope = self._group_result_rows(
            selected, lambda result, _activity, _source: result.ghg_scope, SCOPE_LABELS, evidence_by_record
        )
        iso = self._group_result_rows(
            selected,
            lambda result, _activity, _source: result.iso_category_code.split(".", 1)[0],
            ISO_GROUP_LABELS,
            evidence_by_record,
        )
        source_labels = {
            self._flow_source_identity(result, activity, source)[0]: self._flow_source_identity(
                result, activity, source
            )[1]
            for result, activity, _, source in selected
        }
        sources = self._group_result_rows(
            selected,
            lambda result, activity, source: self._flow_source_identity(result, activity, source)[0],
            source_labels,
            evidence_by_record,
        )
        area_rows = self._group_allocated_rows(
            selected, allocation_by_activity, dimension="area", evidence_by_record=evidence_by_record
        )
        equipment_rows = self._group_allocated_rows(
            selected,
            allocation_by_activity,
            dimension="equipment",
            evidence_by_record=evidence_by_record,
        )
        quality = dict(run.quality_snapshot or {})
        allocation_sums: dict[int, Decimal] = defaultdict(Decimal)
        for allocation in allocations:
            allocation_sums[allocation.activity_id] += allocation.allocation_ratio
        dynamically_allocated = sum(
            1
            for activity_id in activity_ids
            if abs(allocation_sums.get(activity_id, Decimal(0)) - Decimal(1)) <= Decimal("0.000001")
        )
        dynamically_evidenced = sum(1 for record_code in evidence_by_record if evidence_by_record[record_code] > 0)
        allocation_coverage = quality.get("allocationCoveragePct")
        if allocation_coverage is None:
            allocation_coverage = self._coverage(dynamically_allocated, len(activity_ids))
        evidence_coverage = quality.get("evidenceCoveragePct")
        if evidence_coverage is None:
            evidence_coverage = self._coverage(dynamically_evidenced, len(activity_ids))
        result_quality_status = "pass"
        if any(result.quality_status == "failed" for result, *_rest in selected):
            result_quality_status = "failed"
        elif any(result.quality_status != "pass" for result, *_rest in selected):
            result_quality_status = "warning"
        return {
            "runCode": run.run_code,
            "inventoryCode": run.inventory_code,
            "status": run.status,
            **context,
            "scope2Method": method,
            "scope2Available": available,
            "totalCo2EKg": str(total) if total is not None else None,
            "activityCount": len(activity_ids),
            "dataCompletenessPct": "100.00" if run.status == "completed" else "0.00",
            "allocationCoveragePct": str(allocation_coverage),
            "evidenceCoveragePct": str(evidence_coverage),
            "qualityStatus": result_quality_status,
            "scopeBreakdown": self._finalize_breakdown(scope, denominator),
            "isoBreakdown": self._finalize_breakdown(iso, denominator),
            "sourceRanking": self._finalize_breakdown(sources, denominator)[:10],
            "areaRanking": self._finalize_breakdown(area_rows, denominator)[:10],
            "equipmentRanking": self._finalize_breakdown(equipment_rows, denominator)[:10],
            "completedAt": run.completed_at.isoformat() if run.completed_at else None,
        }

    async def _overview_from_filter(self, query: GhgAnalyticsFilter) -> dict[str, Any]:
        result_slice = await GhgResultSliceQuery(self.session).execute(query)
        run = result_slice.run
        rows = result_slice.rows
        context = await self._run_context(run)
        activity_ids = {row.activity.id for row in rows}
        record_codes = {row.activity.record_code for row in rows}
        evidence_by_record = await self._evidence_counts(record_codes)
        allocations = await self._allocations(activity_ids)
        total_value = sum((row.attributed_co2e_kg for row in rows), Decimal(0))
        _method_total, scope2_available = self._method_total(run, query.scope2_method)
        if query.ghg_scope != "scope2" and not any(row.result.ghg_scope == "scope2" for row in rows):
            scope2_available = True
        denominator = total_value
        scope = self._group_attributed_rows(
            rows,
            lambda row: row.result.ghg_scope,
            SCOPE_LABELS,
            evidence_by_record,
        )
        iso = self._group_attributed_rows(
            rows,
            lambda row: row.result.iso_category_code.split(".", 1)[0],
            ISO_GROUP_LABELS,
            evidence_by_record,
        )
        source_labels = {
            self._flow_source_identity(row.result, row.activity, row.source)[0]: self._flow_source_identity(
                row.result,
                row.activity,
                row.source,
            )[1]
            for row in rows
        }
        sources = self._group_attributed_rows(
            rows,
            lambda row: self._flow_source_identity(row.result, row.activity, row.source)[0],
            source_labels,
            evidence_by_record,
        )
        area_rows = await self._resource_breakdown(
            rows, allocations, query=query, dimension="area", evidence_by_record=evidence_by_record
        )
        equipment_rows = await self._resource_breakdown(
            rows,
            allocations,
            query=query,
            dimension="equipment",
            evidence_by_record=evidence_by_record,
        )
        allocated_ids = {item.activity_id for item in allocations}
        allocation_coverage = self._coverage(len(activity_ids & allocated_ids), len(activity_ids))
        evidence_coverage = self._coverage(
            sum(1 for code in record_codes if evidence_by_record.get(code, 0) > 0),
            len(record_codes),
        )
        quality_status = "pass"
        if any(row.result.quality_status == "failed" for row in rows):
            quality_status = "failed"
        elif any(row.result.quality_status != "pass" for row in rows):
            quality_status = "warning"
        budget = await self._budget_target(query, run, total_value if scope2_available else None)
        return {
            "runCode": run.run_code,
            "inventoryCode": run.inventory_code,
            "status": run.status,
            **context,
            "scope2Method": query.scope2_method,
            "scope2Available": scope2_available,
            "totalCo2EKg": str(total_value) if scope2_available else None,
            "activityCount": len(activity_ids),
            "resultCount": len(rows),
            "dataCompletenessPct": "100.00" if run.status == "completed" else "0.00",
            "allocationCoveragePct": allocation_coverage,
            "evidenceCoveragePct": evidence_coverage,
            "qualityStatus": quality_status,
            "scopeBreakdown": self._finalize_breakdown(scope, denominator),
            "isoBreakdown": self._finalize_breakdown(iso, denominator),
            "sourceRanking": self._finalize_breakdown(sources, denominator)[:10],
            "areaRanking": self._finalize_breakdown(area_rows, denominator)[:10],
            "equipmentRanking": self._finalize_breakdown(equipment_rows, denominator)[:10],
            "budgetTarget": budget,
            "completedAt": run.completed_at.isoformat() if run.completed_at else None,
        }

    async def results_summary(self, *, analytics_filter: GhgAnalyticsFilter) -> dict[str, Any]:
        overview = await self._overview_from_filter(analytics_filter)
        result_slice = await GhgResultSliceQuery(self.session).execute(analytics_filter)
        record_codes = {row.activity.record_code for row in result_slice.rows}
        evidence = await self._evidence_counts(record_codes)
        allocations = await self._allocations({row.activity.id for row in result_slice.rows})
        allocated_ids = {row.activity_id for row in allocations}
        missing_evidence = sum(1 for code in record_codes if evidence.get(code, 0) == 0)
        unallocated = sum(1 for row in result_slice.rows if row.activity.id not in allocated_ids)
        return {
            "runCode": result_slice.run.run_code,
            "scope2Method": analytics_filter.scope2_method,
            "totalCo2EKg": overview["totalCo2EKg"],
            "activityCount": overview["activityCount"],
            "resultCount": result_slice.total,
            "missingEvidenceCount": missing_evidence,
            "unallocatedCount": unallocated,
            "scopeBreakdown": overview["scopeBreakdown"],
            "isoBreakdown": overview["isoBreakdown"],
            "sourceBreakdown": overview["sourceRanking"],
            "areaBreakdown": overview["areaRanking"],
            "equipmentBreakdown": overview["equipmentRanking"],
        }

    async def comparison(
        self,
        *,
        run_codes: list[str],
        analytics_filter: GhgAnalyticsFilter,
    ) -> dict[str, Any]:
        if len(run_codes) < MIN_COMPARISON_RUNS or len(run_codes) > MAX_COMPARISON_RUNS:
            msg = "运行比较必须选择2至3个核算运行"
            raise ValueError(msg)
        items: list[dict[str, Any]] = []
        for code in run_codes:
            item = await self._overview_from_filter(replace(analytics_filter, run_code=code))
            items.append(
                {
                    "runCode": code,
                    "reportingPeriodName": item["reportingPeriodName"],
                    "organizationBoundaryName": item["organizationBoundaryName"],
                    "boundaryVersion": await self._boundary_version(item["organizationBoundaryId"]),
                    "totalCo2EKg": item["totalCo2EKg"],
                    "scopeBreakdown": item["scopeBreakdown"],
                    "isoBreakdown": item["isoBreakdown"],
                    "areaBreakdown": item["areaRanking"],
                    "equipmentBreakdown": item["equipmentRanking"],
                }
            )
        deltas: list[dict[str, Any]] = []
        for previous, current in pairwise(items):
            previous_total = Decimal(str(previous["totalCo2EKg"] or 0))
            current_total = Decimal(str(current["totalCo2EKg"] or 0))
            change = current_total - previous_total
            change_pct = change / previous_total * Decimal(100) if previous_total else None
            deltas.append(
                {
                    "fromRunCode": previous["runCode"],
                    "toRunCode": current["runCode"],
                    "changeCo2EKg": str(change),
                    "changePct": str(change_pct.quantize(Decimal("0.01"))) if change_pct is not None else None,
                }
            )
        return {"scope2Method": analytics_filter.scope2_method, "items": items, "deltas": deltas}

    async def _trend_from_filter(self, query: GhgAnalyticsFilter, *, grain: str) -> dict[str, Any]:
        if grain not in {"month", "quarter", "year"}:
            msg = "趋势粒度只能选择月、季或年"
            raise ValueError(msg)
        result_slice = await GhgResultSliceQuery(self.session).execute(query)
        buckets: dict[str, dict[str, Decimal]] = {}
        excluded_count = 0
        excluded_value = Decimal(0)
        included_value = Decimal(0)
        for row in result_slice.rows:
            bucket = self._period_bucket(row.activity.period_start, row.activity.period_end, grain)
            if bucket is None:
                excluded_count += 1
                excluded_value += row.attributed_co2e_kg
                continue
            values = buckets.setdefault(bucket, {"scope1": Decimal(0), "scope2": Decimal(0), "scope3": Decimal(0)})
            values[row.result.ghg_scope] += row.attributed_co2e_kg
            included_value += row.attributed_co2e_kg
        total_for_coverage = included_value + excluded_value
        coverage = included_value / total_for_coverage * Decimal(100) if total_for_coverage else Decimal(100)
        items = [
            {
                "runCode": result_slice.run.run_code,
                "periodId": None,
                "periodName": bucket,
                "periodStart": None,
                "periodEnd": None,
                "totalCo2EKg": str(sum(values.values(), Decimal(0))),
                "scope1Co2EKg": str(values["scope1"]),
                "scope2Co2EKg": str(values["scope2"]),
                "scope3Co2EKg": str(values["scope3"]),
                "scope2Method": query.scope2_method,
                "boundaryVersion": await self._boundary_version(result_slice.run.organization_boundary_id),
            }
            for bucket, values in sorted(buckets.items())
        ]
        current_total = sum((row.attributed_co2e_kg for row in result_slice.rows), Decimal(0))
        previous_total = await self._comparable_total(result_slice.run, query, mode="previous")
        year_ago_total = await self._comparable_total(result_slice.run, query, mode="year_ago")
        return {
            "items": items,
            "total": len(items),
            "grain": grain,
            "currentTotalCo2EKg": str(current_total),
            **self._change_payload("previous", current_total, previous_total),
            **self._change_payload("yearOnYear", current_total, year_ago_total),
            "trendCoveragePct": str(coverage.quantize(Decimal("0.01"))),
            "excludedCrossPeriodCount": excluded_count,
            "excludedCrossPeriodCo2EKg": str(excluded_value),
        }

    async def trend(
        self,
        *,
        reporting_org_id: int | None,
        scope2_method: str,
        limit: int,
        analytics_filter: GhgAnalyticsFilter | None = None,
        grain: str = "month",
    ) -> dict[str, Any]:
        if analytics_filter is not None:
            return await self._trend_from_filter(analytics_filter, grain=grain)
        self._validate_scope2_method(scope2_method)
        filters: list[ColumnElement[bool]] = [GhgCalculationRun.status == "completed"]
        if reporting_org_id is not None:
            filters.append(GhgCalculationRun.reporting_org_id == reporting_org_id)
        rows = list(
            (
                await self.session.execute(
                    select(GhgCalculationRun, ReportingPeriod, OrganizationBoundary)
                    .outerjoin(ReportingPeriod, ReportingPeriod.id == GhgCalculationRun.reporting_period_id)
                    .outerjoin(
                        OrganizationBoundary, OrganizationBoundary.id == GhgCalculationRun.organization_boundary_id
                    )
                    .where(*filters)
                    .order_by(ReportingPeriod.period_start.desc().nullslast(), GhgCalculationRun.completed_at.desc())
                )
            ).all()
        )
        latest_by_period: dict[
            int | None, tuple[GhgCalculationRun, ReportingPeriod | None, OrganizationBoundary | None]
        ] = {}
        for row in rows:
            run, period, _boundary = row
            key = period.id if period else run.reporting_period_id
            latest_by_period.setdefault(key, (run, period, _boundary))
        selected_rows = list(latest_by_period.values())[:limit]
        selected_rows.reverse()
        items: list[dict[str, Any]] = []
        for run, period, boundary in selected_rows:
            summary = dict(run.summary_snapshot or {})
            total, _available = self._method_total(run, scope2_method)
            scope_totals = cast("dict[str, Any]", summary.get("scopeTotals") or {})
            if not scope_totals:
                fallback_rows = await self._result_rows(run.id)
                selected_results = [
                    result for result, *_rest in fallback_rows if self._result_selected(result, scope2_method)
                ]
                scope_totals = {
                    scope: str(
                        sum((result.co2e_kg for result in selected_results if result.ghg_scope == scope), Decimal(0))
                    )
                    for scope in ("scope1", "scope2", "scope3")
                }
            scope2_value = self._scope2_total(summary, scope2_method)
            if not summary and total is not None:
                scope2_value = Decimal(str(scope_totals.get("scope2") or 0))
            items.append(
                {
                    "runCode": run.run_code,
                    "periodId": period.id if period else run.reporting_period_id,
                    "periodName": period.name if period else run.inventory_code,
                    "periodStart": period.period_start.isoformat() if period else None,
                    "periodEnd": period.period_end.isoformat() if period else None,
                    "totalCo2EKg": str(total) if total is not None else None,
                    "scope1Co2EKg": str(scope_totals.get("scope1") or "0"),
                    "scope2Co2EKg": str(scope2_value) if scope2_value is not None else None,
                    "scope3Co2EKg": str(scope_totals.get("scope3") or "0"),
                    "scope2Method": scope2_method,
                    "boundaryVersion": boundary.version if boundary else None,
                }
            )
        return {"items": items, "total": len(items)}

    async def breakdown(self, *, run_code: str, dimension: str, scope2_method: str) -> dict[str, Any]:
        overview = await self.overview(run_code=run_code, scope2_method=scope2_method)
        mapping = {
            "scope": "scopeBreakdown",
            "iso_category": "isoBreakdown",
            "source": "sourceRanking",
            "area": "areaRanking",
            "equipment": "equipmentRanking",
        }
        key = mapping.get(dimension)
        if key is None:
            msg = "不支持的分析维度"
            raise ValueError(msg)
        return {"runCode": run_code, "dimension": dimension, "items": overview[key]}

    async def flow(  # noqa: PLR0915 - path construction is kept in one read-model transaction
        self,
        *,
        run_code: str,
        classification: str,
        scope2_method: str,
        analytics_filter: GhgAnalyticsFilter | None = None,
    ) -> dict[str, Any]:
        if analytics_filter is not None:
            return await self._flow_from_filter(analytics_filter, classification=classification)
        if classification not in {"scope", "iso_category"}:
            msg = "分析维度只能选择GHG Protocol排放范围或ISO 14064-1六类别"
            raise ValueError(msg)
        self._validate_scope2_method(scope2_method)
        run = await self._resolve_run(run_code)
        rows = [row for row in await self._result_rows(run.id) if self._result_selected(row[0], scope2_method)]
        allocations = await self._allocations({activity.id for _, activity, _, _ in rows})
        allocation_by_activity: dict[int, list[GhgActivityAllocation]] = defaultdict(list)
        for allocation in allocations:
            allocation_by_activity[allocation.activity_id].append(allocation)
        evidence_by_record = await self._evidence_counts({activity.record_code for _, activity, _, _ in rows})
        context = await self._run_context(run)
        root_id = f"boundary:{run.organization_boundary_id or run.inventory_code}"
        root_name = context.get("organizationBoundaryName") or run.inventory_code
        node_meta: dict[str, dict[str, Any]] = {
            root_id: {"name": root_name, "category": "boundary", "records": set(), "evidence": set()}
        }
        link_values: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        path_values: dict[tuple[str, ...], Decimal] = defaultdict(Decimal)
        path_records: dict[tuple[str, ...], set[str]] = defaultdict(set)
        for result, activity, _method, source in rows:
            allocation_rows: Sequence[GhgActivityAllocation | None] = allocation_by_activity.get(activity.id) or [None]
            for allocation_row in allocation_rows:
                value = result.co2e_kg * (allocation_row.allocation_ratio if allocation_row else Decimal(1))
                if classification == "scope":
                    class_code = result.ghg_scope
                    class_name = SCOPE_LABELS.get(class_code, class_code)
                else:
                    class_code = result.iso_category_code.split(".", 1)[0]
                    class_name = ISO_GROUP_LABELS.get(class_code, class_code)
                class_id = f"class:{classification}:{class_code}"
                category_id = f"category:{result.iso_category_code}"
                category_name = CATEGORY_BY_CODE[result.iso_category_code].name
                source_id, source_name, _source_drilldown = self._flow_source_identity(result, activity, source)
                if allocation_row is None:
                    resource_id = "resource:unallocated"
                    resource_name = "未分配"
                elif allocation_row.equipment_code_snapshot:
                    resource_id = f"equipment:{allocation_row.equipment_code_snapshot}"
                    resource_name = allocation_row.equipment_name_snapshot or allocation_row.equipment_code_snapshot
                else:
                    resource_id = f"area:{allocation_row.area_code_snapshot}"
                    resource_name = allocation_row.area_name_snapshot
                path = (root_id, class_id, category_id, source_id, resource_id)
                names = (root_name, class_name, category_name, source_name, resource_name)
                categories = ("boundary", "classification", "category", "source", "resource")
                for node_id, node_name, node_category in zip(path, names, categories, strict=True):
                    meta = node_meta.setdefault(
                        node_id,
                        {"name": node_name, "category": node_category, "records": set(), "evidence": set()},
                    )
                    meta["records"].add(activity.record_code)
                    if evidence_by_record.get(activity.record_code, 0):
                        meta["evidence"].add(activity.record_code)
                for source_node, target_node in pairwise(path):
                    link_values[(source_node, target_node)] += value
                path_values[path] += value
                path_records[path].add(activity.record_code)
        node_values: dict[str, Decimal] = defaultdict(Decimal)
        for (source_node, _target_node), value in link_values.items():
            node_values[source_node] += value
        for (_source_node, target_node), value in link_values.items():
            if target_node.startswith(("resource:", "area:", "equipment:")):
                node_values[target_node] += value
        total, _available = self._method_total(run, scope2_method)
        nodes: list[dict[str, Any]] = []
        for node_id, meta in node_meta.items():
            records = meta["records"]
            evidence = meta["evidence"]
            coverage = Decimal(100) if not records else Decimal(len(evidence)) / Decimal(len(records)) * Decimal(100)
            nodes.append(
                {
                    "id": node_id,
                    "name": meta["name"],
                    "value": str(node_values.get(node_id, total or Decimal(0))),
                    "category": meta["category"],
                    "recordCount": len(records),
                    "evidenceCoveragePct": str(coverage.quantize(Decimal("0.01"))),
                }
            )
        links = [
            {"source": source, "target": target, "value": str(value)}
            for (source, target), value in sorted(link_values.items())
        ]
        top_paths = [
            {
                "path": [str(node_meta[node_id]["name"]) for node_id in path],
                "value": str(value),
                "recordCount": len(path_records[path]),
            }
            for path, value in sorted(path_values.items(), key=lambda item: item[1], reverse=True)[:10]
        ]
        return {
            "runCode": run.run_code,
            "classification": classification,
            "scope2Method": scope2_method,
            "totalCo2EKg": str(total) if total is not None else None,
            "nodes": nodes,
            "links": links,
            "topPaths": top_paths,
        }

    async def _flow_from_filter(  # noqa: PLR0915
        self,
        query: GhgAnalyticsFilter,
        *,
        classification: str,
    ) -> dict[str, Any]:
        if classification not in {"scope", "iso_category"}:
            msg = "分析维度只能选择GHG Protocol排放范围或ISO 14064-1六类别"
            raise ValueError(msg)
        result_slice = await GhgResultSliceQuery(self.session).execute(query)
        rows = result_slice.rows
        run = result_slice.run
        context = await self._run_context(run)
        allocations = await self._allocations({row.activity.id for row in rows})
        allocations_by_activity: dict[int, list[GhgActivityAllocation]] = defaultdict(list)
        for allocation in allocations:
            allocations_by_activity[allocation.activity_id].append(allocation)
        area_ids = (
            await GhgResultSliceQuery(self.session).area_ids(
                query.area_id, include_descendants=query.include_descendants
            )
            if query.area_id is not None
            else None
        )
        root_id = f"boundary:{run.organization_boundary_id or run.inventory_code}"
        root_name = context.get("organizationBoundaryName") or run.inventory_code
        node_meta: dict[str, dict[str, Any]] = {
            root_id: {
                "name": root_name,
                "category": "boundary",
                "records": set(),
                "drilldown": {},
            }
        }
        link_values: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        path_values: dict[tuple[str, ...], Decimal] = defaultdict(Decimal)
        path_records: dict[tuple[str, ...], set[str]] = defaultdict(set)
        path_drilldown: dict[tuple[str, ...], dict[str, Any]] = {}
        for row in rows:
            result, activity = row.result, row.activity
            matching_allocations = [
                item
                for item in allocations_by_activity.get(activity.id, [])
                if (area_ids is None or item.area_id in area_ids)
                and (query.equipment_id is None or item.equipment_id == query.equipment_id)
            ]
            allocation_rows = self._flow_allocation_distribution(
                matching_allocations,
                target_ratio=row.attribution_ratio,
            )
            for allocation_row, ratio in allocation_rows:
                value = result.co2e_kg * ratio
                if classification == "scope":
                    class_code = result.ghg_scope
                    class_name = SCOPE_LABELS.get(class_code, class_code)
                    class_drilldown = {"ghgScope": class_code}
                else:
                    class_code = result.iso_category_code.split(".", 1)[0]
                    class_name = ISO_GROUP_LABELS.get(class_code, class_code)
                    class_drilldown = {"isoCategoryCode": class_code}
                class_id = f"class:{classification}:{class_code}"
                category_id = f"category:{result.iso_category_code}"
                category_name = CATEGORY_BY_CODE[result.iso_category_code].name
                source_id, source_name, source_drilldown = self._flow_source_identity(
                    result,
                    activity,
                    row.source,
                )
                if allocation_row is None:
                    resource_id = "resource:unallocated"
                    resource_name = "未归集"
                    resource_drilldown: dict[str, Any] = {}
                elif allocation_row.equipment_id is not None:
                    resource_id = f"equipment:{allocation_row.equipment_id}"
                    resource_name = (
                        allocation_row.equipment_name_snapshot or allocation_row.equipment_code_snapshot or "设备"
                    )
                    resource_drilldown = {"areaId": allocation_row.area_id, "equipmentId": allocation_row.equipment_id}
                else:
                    resource_id = f"area:{allocation_row.area_id}"
                    resource_name = allocation_row.area_name_snapshot
                    resource_drilldown = {"areaId": allocation_row.area_id}
                path = (root_id, class_id, category_id, source_id, resource_id)
                definitions: tuple[tuple[str, str, str, dict[str, Any]], ...] = (
                    (root_id, str(root_name), "boundary", {}),
                    (class_id, class_name, "classification", class_drilldown),
                    (category_id, category_name, "category", {"isoCategoryCode": result.iso_category_code}),
                    (source_id, str(source_name), "source", source_drilldown),
                    (resource_id, resource_name, "resource", resource_drilldown),
                )
                for node_id, node_name, node_category, drilldown in definitions:
                    meta = node_meta.setdefault(
                        node_id,
                        {"name": node_name, "category": node_category, "records": set(), "drilldown": drilldown},
                    )
                    meta["records"].add(activity.record_code)
                for source_node, target_node in pairwise(path):
                    link_values[(source_node, target_node)] += value
                path_values[path] += value
                path_records[path].add(activity.record_code)
                path_drilldown[path] = {
                    **class_drilldown,
                    "isoCategoryCode": result.iso_category_code,
                    **source_drilldown,
                    **resource_drilldown,
                }
        node_values: dict[str, Decimal] = defaultdict(Decimal)
        for (source_node, _target), value in link_values.items():
            node_values[source_node] += value
        for (_source, target_node), value in link_values.items():
            if target_node.startswith(("resource:", "area:", "equipment:")):
                node_values[target_node] += value
        total = sum((row.attributed_co2e_kg for row in rows), Decimal(0))
        evidence_counts = await self._evidence_counts({row.activity.record_code for row in rows})
        nodes = [
            {
                "id": node_id,
                "name": meta["name"],
                "value": str(node_values.get(node_id, total if node_id == root_id else Decimal(0))),
                "category": meta["category"],
                "recordCount": len(meta["records"]),
                "evidenceCoveragePct": self._coverage(
                    sum(1 for record_code in meta["records"] if evidence_counts.get(record_code, 0) > 0),
                    len(meta["records"]),
                ),
                "drilldown": meta["drilldown"],
            }
            for node_id, meta in node_meta.items()
        ]
        links = [
            {"source": source, "target": target, "value": str(value)}
            for (source, target), value in sorted(link_values.items())
        ]
        top_paths = [
            {
                "path": [str(node_meta[node_id]["name"]) for node_id in path],
                "value": str(value),
                "recordCount": len(path_records[path]),
                "drilldown": path_drilldown[path],
            }
            for path, value in sorted(path_values.items(), key=lambda item: item[1], reverse=True)[:10]
        ]
        return {
            "runCode": run.run_code,
            "classification": classification,
            "scope2Method": query.scope2_method,
            "totalCo2EKg": str(total),
            "nodes": nodes,
            "links": links,
            "topPaths": top_paths,
        }

    @staticmethod
    def _flow_allocation_distribution(
        allocations: list[GhgActivityAllocation],
        *,
        target_ratio: Decimal,
    ) -> list[tuple[GhgActivityAllocation | None, Decimal]]:
        """Distribute exactly the selected attribution across resource nodes.

        Partial allocation is completed with an explicit unallocated path. If
        imported allocation ratios exceed the selected attribution, resource
        shares are normalized so the Sankey remains conservative while the
        underlying data-quality issue remains visible in allocation coverage.
        """
        if not allocations:
            return [(None, target_ratio)] if target_ratio > 0 else []
        allocated_ratio = sum((item.allocation_ratio for item in allocations), Decimal(0))
        if allocated_ratio <= 0:
            return [(None, target_ratio)] if target_ratio > 0 else []
        if allocated_ratio > target_ratio:
            scale = target_ratio / allocated_ratio
            return [(item, item.allocation_ratio * scale) for item in allocations]
        rows: list[tuple[GhgActivityAllocation | None, Decimal]] = [
            (item, item.allocation_ratio) for item in allocations
        ]
        residual = target_ratio - allocated_ratio
        if residual > 0:
            rows.append((None, residual))
        return rows

    @staticmethod
    def _flow_source_identity(
        result: GhgCalculationResult,
        activity: GhgActivityRecord,
        source: GhgEmissionSource | None,
    ) -> tuple[str, str, dict[str, str]]:
        """Return a stable business source bucket instead of a monthly activity-record bucket."""
        raw_source_name = (source.source_name if source is not None else activity.activity_name).strip()
        source_name = SOURCE_DISPLAY_LABELS.get(raw_source_name, raw_source_name)
        if result.iso_category_code == "3.1":
            payload = dict(activity.source_payload or {})
            origin = str(payload.get("origin") or "").strip()
            destination = str(payload.get("destination") or "").strip()
            transport_mode = str(payload.get("transport_mode") or payload.get("vehicle_type") or "").strip()
            route_key = (
                f"{transport_mode}|{origin}|{destination}"
                if any((transport_mode, origin, destination))
                else source_name.casefold()
            )
            route_name = " → ".join(item for item in (origin, destination) if item)
            display_name = f"第三方物流运输 · {route_name}" if route_name else "第三方物流运输"
            return (
                f"source:{result.iso_category_code}:transport:{route_key}",
                display_name,
                {"keyword": "第三方运输"},
            )
        normalized_name = SOURCE_PERIOD_SUFFIX.sub("", source_name).strip()
        normalized_keyword = SOURCE_PERIOD_SUFFIX.sub("", raw_source_name).strip()
        return (
            f"source:{result.iso_category_code}:{normalized_name.casefold()}",
            normalized_name,
            {"keyword": normalized_keyword},
        )

    async def results(
        self,
        *,
        run_code: str,
        scope2_method: str,
        ghg_scope: str | None,
        iso_category_code: str | None,
        source_code: str | None,
        quality_status: str | None,
        keyword: str | None,
        limit: int,
        offset: int,
        analytics_filter: GhgAnalyticsFilter | None = None,
    ) -> dict[str, Any]:
        if analytics_filter is not None:
            result_slice = await GhgResultSliceQuery(self.session).execute(
                analytics_filter,
                limit=limit,
                offset=offset,
            )
            return {
                "items": await self.attributed_result_items(result_slice.rows),
                "total": result_slice.total,
                "limit": limit,
                "offset": offset,
            }
        self._validate_scope2_method(scope2_method)
        run = await self._resolve_run(run_code)
        rows = [row for row in await self._result_rows(run.id) if self._result_selected(row[0], scope2_method)]
        if ghg_scope:
            rows = [row for row in rows if row[0].ghg_scope == ghg_scope]
        if iso_category_code:
            rows = [row for row in rows if row[0].iso_category_code == iso_category_code]
        if source_code:
            rows = [row for row in rows if row[1].source_code == source_code]
        if quality_status:
            rows = [row for row in rows if row[0].quality_status == quality_status]
        if keyword:
            normalized = keyword.strip().lower()
            rows = [
                row
                for row in rows
                if normalized in row[1].record_code.lower()
                or normalized in row[1].activity_name.lower()
                or normalized in row[1].source_code.lower()
            ]
        total = len(rows)
        page = rows[offset : offset + limit]
        items = await self._result_items(page)
        return {"items": items, "total": total}

    async def result_detail(self, *, run_code: str, record_code: str, scope2_method: str) -> dict[str, Any]:
        self._validate_scope2_method(scope2_method)
        run = await self._resolve_run(run_code)
        rows = [
            row
            for row in await self._result_rows(run.id)
            if row[1].record_code == record_code and self._result_selected(row[0], scope2_method)
        ]
        if not rows:
            msg = "核算结果不存在"
            raise ValueError(msg)
        items = await self._result_items(rows)
        result, activity, _method, _source = rows[0]
        assignments = list(
            (
                await self.session.scalars(
                    select(GhgParameterAssignment)
                    .where(GhgParameterAssignment.run_id == run.id, GhgParameterAssignment.activity_id == activity.id)
                    .order_by(GhgParameterAssignment.parameter_code)
                )
            ).all()
        )
        allocations = await self._allocations({activity.id})
        evidence_rows = list(
            (
                await self.session.execute(
                    select(GhgEvidenceLink, GhgEvidenceFile)
                    .join(GhgEvidenceFile, GhgEvidenceFile.id == GhgEvidenceLink.evidence_id)
                    .where(GhgEvidenceLink.record_type == "activity", GhgEvidenceLink.record_code == record_code)
                )
            ).all()
        )
        return {
            "result": items[0],
            "activityDetails": {
                "periodStart": activity.period_start.isoformat(),
                "periodEnd": activity.period_end.isoformat(),
                "dataSourceType": activity.data_source_type,
                "measurementMethod": activity.measurement_method,
                "sourcePayload": activity.source_payload,
                "remarks": activity.remarks,
            },
            "formulaSnapshot": result.formula_snapshot,
            "assignments": [
                {
                    "parameterCode": item.parameter_code,
                    "parameterRole": item.parameter_role,
                    "value": str(item.value),
                    "unit": item.unit,
                    "sourceMode": item.source_mode,
                    "sourceName": item.source_name,
                    "sourceVersion": item.source_version,
                    "standardCode": item.standard_code,
                    "clauseReference": item.clause_reference,
                    "tableReference": item.table_reference,
                    "selectionRule": item.selection_rule,
                }
                for item in assignments
            ],
            "allocations": [
                {
                    "allocationCode": item.allocation_code,
                    "areaCode": item.area_code_snapshot,
                    "areaName": item.area_name_snapshot,
                    "areaPath": item.area_path_snapshot,
                    "equipmentCode": item.equipment_code_snapshot,
                    "equipmentName": item.equipment_name_snapshot,
                    "allocationRole": item.allocation_role,
                    "allocationRatio": str(item.allocation_ratio),
                    "sourceKind": item.source_kind,
                }
                for item in allocations
            ],
            "evidence": [
                {
                    "evidenceCode": evidence.evidence_code,
                    "fileName": evidence.file_name,
                    "documentType": evidence.document_type,
                    "issuer": evidence.issuer,
                    "periodStart": evidence.period_start.isoformat() if evidence.period_start else None,
                    "periodEnd": evidence.period_end.isoformat() if evidence.period_end else None,
                    "verificationStatus": evidence.verification_status,
                    "evidenceRole": link.evidence_role,
                    "reviewStatus": link.review_status,
                    "pageOrCellReference": link.page_or_cell_reference,
                }
                for link, evidence in evidence_rows
            ],
        }

    async def readiness(
        self,
        *,
        inventory_code: str,
        reporting_period_id: int | None,
        organization_boundary_id: int | None,
    ) -> dict[str, Any]:
        filters = [GhgActivityRecord.inventory_code == inventory_code, GhgActivityRecord.boundary_status == "included"]
        if reporting_period_id is not None:
            filters.append(GhgActivityRecord.reporting_period_id == reporting_period_id)
        if organization_boundary_id is not None:
            filters.append(GhgActivityRecord.organization_boundary_id == organization_boundary_id)
        activities = list((await self.session.scalars(select(GhgActivityRecord).where(*filters))).all())
        activity_ids = {item.id for item in activities}
        allocations = await self._allocations(activity_ids)
        allocation_sums: dict[int, Decimal] = defaultdict(Decimal)
        for allocation in allocations:
            allocation_sums[allocation.activity_id] += allocation.allocation_ratio
        evidence_counts = await self._evidence_counts({item.record_code for item in activities})
        complete_allocations = sum(
            1
            for item in activities
            if abs(allocation_sums.get(item.id, Decimal(0)) - Decimal(1)) <= Decimal("0.000001")
        )
        approved = sum(1 for item in activities if item.status == "approved")
        quality_valid = sum(1 for item in activities if item.quality_status != "failed")
        evidence_complete = sum(1 for item in activities if evidence_counts.get(item.record_code, 0) > 0)
        parameter_complete = await self._parameter_complete_count(activities)
        boundary_valid = 0
        if organization_boundary_id is not None:
            boundary = await self.session.scalar(
                select(OrganizationBoundary).where(OrganizationBoundary.id == organization_boundary_id)
            )
            boundary_valid = 1 if boundary and boundary.status == "published" else 0
        checks = [
            self._readiness_check("boundary", "组织边界", boundary_valid, 1),
            self._readiness_check("approval", "活动数据审批", approved, len(activities)),
            self._readiness_check("allocation", "区域设备归集", complete_allocations, len(activities)),
            self._readiness_check("parameters", "方法参数与因子", parameter_complete, len(activities)),
            self._readiness_check("quality", "数据质量", quality_valid, len(activities)),
            self._readiness_check("evidence", "证据文件", evidence_complete, len(activities), blocking=False),
        ]
        blocking = [check["name"] for check in checks if check["blockingCount"] > 0]
        latest_run = await self.session.scalar(
            select(GhgCalculationRun)
            .where(
                GhgCalculationRun.inventory_code == inventory_code,
                *(
                    [GhgCalculationRun.reporting_period_id == reporting_period_id]
                    if reporting_period_id is not None
                    else []
                ),
                *(
                    [GhgCalculationRun.organization_boundary_id == organization_boundary_id]
                    if organization_boundary_id is not None
                    else []
                ),
            )
            .order_by(GhgCalculationRun.started_at.desc())
            .limit(1)
        )
        return {
            "inventoryCode": inventory_code,
            "reportingPeriodId": reporting_period_id,
            "organizationBoundaryId": organization_boundary_id,
            "readyForCalculation": bool(activities) and not blocking,
            "activityCount": len(activities),
            "checks": checks,
            "blockingIssues": [f"{name}尚未完成" for name in blocking],
            "latestRunCode": latest_run.run_code if latest_run else None,
            "latestRunStatus": latest_run.status if latest_run else None,
        }

    async def reports(self, *, limit: int, offset: int) -> dict[str, Any]:
        total = int(await self.session.scalar(select(func.count()).select_from(GhgInventoryReport)) or 0)
        rows = list(
            (
                await self.session.scalars(
                    select(GhgInventoryReport)
                    .order_by(GhgInventoryReport.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return {"items": [await self.report_payload(row) for row in rows], "total": total}

    async def report_payload(self, report: GhgInventoryReport) -> dict[str, Any]:
        run = await self.session.get(GhgCalculationRun, report.run_id)
        profile = await self.session.get(GhgReportingProfile, report.reporting_profile_id)
        reviews = list(
            (
                await self.session.scalars(
                    select(GhgInventoryReportReview)
                    .where(GhgInventoryReportReview.report_id == report.id)
                    .order_by(GhgInventoryReportReview.acted_at)
                )
            ).all()
        )
        return {
            "id": report.id,
            "reportCode": report.report_code,
            "version": report.version,
            "title": report.title,
            "inventoryCode": report.inventory_code,
            "runCode": run.run_code if run else "",
            "reportingOrgId": report.reporting_org_id,
            "reportingPeriodId": report.reporting_period_id,
            "organizationBoundaryId": report.organization_boundary_id,
            "reportingProfileCode": profile.code if profile else "",
            "status": report.status,
            "metricsSnapshot": report.metrics_snapshot,
            "evidenceSnapshot": report.evidence_snapshot,
            "changeSummary": report.change_summary,
            "submittedBy": report.submitted_by,
            "submittedAt": report.submitted_at.isoformat() if report.submitted_at else None,
            "approvedBy": report.approved_by,
            "approvedAt": report.approved_at.isoformat() if report.approved_at else None,
            "publishedAt": report.published_at.isoformat() if report.published_at else None,
            "reviews": [
                {
                    "action": item.action,
                    "fromStatus": item.from_status,
                    "toStatus": item.to_status,
                    "actor": item.actor,
                    "comment": item.comment,
                    "actedAt": item.acted_at.isoformat(),
                }
                for item in reviews
            ],
        }

    async def _resolve_run(self, run_code: str | None) -> GhgCalculationRun:
        query = select(GhgCalculationRun)
        if run_code:
            query = query.where(GhgCalculationRun.run_code == run_code)
        else:
            query = query.where(GhgCalculationRun.status == "completed").order_by(
                GhgCalculationRun.completed_at.desc(), GhgCalculationRun.id.desc()
            )
        run = await self.session.scalar(query.limit(1))
        if run is None:
            msg = "没有可用的组织温室气体核算运行"
            raise ValueError(msg)
        return run

    async def _run_context(self, run: GhgCalculationRun) -> dict[str, Any]:
        profile = await self.session.get(GhgReportingProfile, run.reporting_profile_id)
        organization = (
            await self.session.get(ReportingOrganization, run.reporting_org_id) if run.reporting_org_id else None
        )
        period = await self.session.get(ReportingPeriod, run.reporting_period_id) if run.reporting_period_id else None
        boundary = (
            await self.session.get(OrganizationBoundary, run.organization_boundary_id)
            if run.organization_boundary_id
            else None
        )
        return {
            "reportingOrgId": run.reporting_org_id,
            "reportingOrgName": organization.name if organization else None,
            "reportingPeriodId": run.reporting_period_id,
            "reportingPeriodName": period.name if period else None,
            "organizationBoundaryId": run.organization_boundary_id,
            "organizationBoundaryName": boundary.boundary_name if boundary else None,
            "reportingProfileCode": profile.code if profile else "",
            "reportingProfileName": profile.name if profile else "",
        }

    async def _result_rows(self, run_id: int) -> list[ResultRow]:
        rows = await self.session.execute(
            select(
                GhgCalculationResult,
                GhgActivityRecord,
                GhgCalculationMethodDefinition,
                GhgEmissionSource,
            )
            .join(GhgActivityRecord, GhgActivityRecord.id == GhgCalculationResult.activity_id)
            .join(
                GhgCalculationMethodDefinition,
                GhgCalculationMethodDefinition.id == GhgCalculationResult.method_id,
            )
            .outerjoin(GhgEmissionSource, GhgEmissionSource.id == GhgActivityRecord.emission_source_id)
            .where(GhgCalculationResult.run_id == run_id)
            .order_by(GhgActivityRecord.record_code)
        )
        return [cast("ResultRow", tuple(row)) for row in rows.all()]

    async def _result_items(self, rows: list[ResultRow]) -> list[dict[str, Any]]:
        activity_ids = {activity.id for _, activity, _, _ in rows}
        allocations = await self._allocations(activity_ids)
        allocation_by_activity: dict[int, list[GhgActivityAllocation]] = defaultdict(list)
        for allocation in allocations:
            allocation_by_activity[allocation.activity_id].append(allocation)
        evidence_by_record = await self._evidence_counts({activity.record_code for _, activity, _, _ in rows})
        return [
            {
                "recordCode": activity.record_code,
                "activityName": activity.activity_name,
                "inventoryCode": activity.inventory_code,
                "organizationCode": activity.organization_code,
                "facilityCode": activity.facility_code,
                "sourceCode": activity.source_code,
                "sourceName": self._flow_source_identity(result, activity, source)[1],
                "sourceMechanism": activity.source_mechanism,
                "periodStart": activity.period_start.isoformat(),
                "periodEnd": activity.period_end.isoformat(),
                "isoCategoryCode": result.iso_category_code,
                "isoCategoryName": CATEGORY_BY_CODE[result.iso_category_code].name,
                "ghgScope": result.ghg_scope,
                "activityAmount": str(activity.activity_amount),
                "activityUnit": activity.activity_unit,
                "methodCode": method.code,
                "methodName": method.name,
                "gasCode": result.gas_code,
                "co2eKg": str(result.co2e_kg),
                "calculatedCo2EKg": str(result.co2e_kg),
                "attributedCo2EKg": str(result.co2e_kg),
                "attributionRatio": "1",
                "scope2Method": result.scope2_method,
                "qualityStatus": result.quality_status,
                "evidenceCount": evidence_by_record.get(activity.record_code, 0),
                "allocationStatus": "complete" if allocation_by_activity.get(activity.id) else "unallocated",
                "areaNames": sorted({item.area_name_snapshot for item in allocation_by_activity.get(activity.id, [])}),
                "equipmentNames": sorted(
                    {
                        item.equipment_name_snapshot
                        for item in allocation_by_activity.get(activity.id, [])
                        if item.equipment_name_snapshot
                    }
                ),
            }
            for result, activity, method, source in rows
        ]

    async def attributed_result_items(self, rows: list[GhgAttributedResultRow]) -> list[dict[str, Any]]:
        activity_ids = {row.activity.id for row in rows}
        allocations = await self._allocations(activity_ids)
        allocation_by_activity: dict[int, list[GhgActivityAllocation]] = defaultdict(list)
        for allocation in allocations:
            allocation_by_activity[allocation.activity_id].append(allocation)
        evidence_by_record = await self._evidence_counts({row.activity.record_code for row in rows})
        return [
            {
                "recordCode": row.activity.record_code,
                "activityName": row.activity.activity_name,
                "inventoryCode": row.activity.inventory_code,
                "organizationCode": row.activity.organization_code,
                "facilityCode": row.activity.facility_code,
                "sourceCode": row.activity.source_code,
                "sourceName": self._flow_source_identity(row.result, row.activity, row.source)[1],
                "sourceMechanism": row.activity.source_mechanism,
                "periodStart": row.activity.period_start.isoformat(),
                "periodEnd": row.activity.period_end.isoformat(),
                "isoCategoryCode": row.result.iso_category_code,
                "isoCategoryName": CATEGORY_BY_CODE[row.result.iso_category_code].name,
                "ghgScope": row.result.ghg_scope,
                "activityAmount": str(row.activity.activity_amount),
                "activityUnit": row.activity.activity_unit,
                "methodCode": row.method.code,
                "methodName": row.method.name,
                "gasCode": row.result.gas_code,
                "co2eKg": str(row.attributed_co2e_kg),
                "calculatedCo2EKg": str(row.result.co2e_kg),
                "attributedCo2EKg": str(row.attributed_co2e_kg),
                "attributionRatio": str(row.attribution_ratio),
                "scope2Method": row.result.scope2_method,
                "qualityStatus": row.result.quality_status,
                "evidenceCount": evidence_by_record.get(row.activity.record_code, 0),
                "allocationStatus": "complete" if allocation_by_activity.get(row.activity.id) else "unallocated",
                "areaNames": sorted(
                    {item.area_name_snapshot for item in allocation_by_activity.get(row.activity.id, [])}
                ),
                "equipmentNames": sorted(
                    {
                        item.equipment_name_snapshot
                        for item in allocation_by_activity.get(row.activity.id, [])
                        if item.equipment_name_snapshot
                    }
                ),
            }
            for row in rows
        ]

    async def _allocations(self, activity_ids: set[int]) -> list[GhgActivityAllocation]:
        if not activity_ids:
            return []
        return list(
            (
                await self.session.scalars(
                    select(GhgActivityAllocation).where(GhgActivityAllocation.activity_id.in_(activity_ids))
                )
            ).all()
        )

    async def _evidence_counts(self, record_codes: set[str]) -> dict[str, int]:
        if not record_codes:
            return {}
        rows = (
            await self.session.execute(
                select(GhgEvidenceLink.record_code, func.count(GhgEvidenceLink.id))
                .where(GhgEvidenceLink.record_type == "activity", GhgEvidenceLink.record_code.in_(record_codes))
                .group_by(GhgEvidenceLink.record_code)
            )
        ).tuples()
        return {record_code: int(count) for record_code, count in rows.all()}

    async def _parameter_complete_count(self, activities: list[GhgActivityRecord]) -> int:
        complete = 0
        for activity in activities:
            method_code = str(activity.source_payload.get("method_code") or "")
            method = await self.session.scalar(
                select(GhgCalculationMethodDefinition).where(
                    GhgCalculationMethodDefinition.code == method_code,
                    GhgCalculationMethodDefinition.status == "published",
                )
            )
            if method is None or not activity.parameter_set_code:
                continue
            required = set(
                (
                    await self.session.scalars(
                        select(GhgMethodParameterDefinition.parameter_code).where(
                            GhgMethodParameterDefinition.method_id == method.id,
                            GhgMethodParameterDefinition.required.is_(True),
                        )
                    )
                ).all()
            )
            prefix = f"{activity.inventory_code}:{activity.parameter_set_code}:"
            available = set(
                (
                    await self.session.scalars(
                        select(GhgParameterValue.parameter_code).where(
                            GhgParameterValue.value_code.startswith(prefix),
                            GhgParameterValue.status == "active",
                            GhgParameterValue.approval_status == "approved",
                        )
                    )
                ).all()
            )
            if required <= available:
                complete += 1
        return complete

    async def _resource_breakdown(
        self,
        rows: list[GhgAttributedResultRow],
        allocations: list[GhgActivityAllocation],
        *,
        query: GhgAnalyticsFilter,
        dimension: str,
        evidence_by_record: dict[str, int],
    ) -> dict[str, dict[str, Any]]:
        area_ids = (
            await GhgResultSliceQuery(self.session).area_ids(
                query.area_id, include_descendants=query.include_descendants
            )
            if query.area_id is not None
            else None
        )
        by_activity: dict[int, list[GhgActivityAllocation]] = defaultdict(list)
        for allocation in allocations:
            if area_ids is not None and allocation.area_id not in area_ids:
                continue
            if query.equipment_id is not None and allocation.equipment_id != query.equipment_id:
                continue
            by_activity[allocation.activity_id].append(allocation)
        groups: dict[str, dict[str, Any]] = {}
        for row in rows:
            for allocation in by_activity.get(row.activity.id, []):
                if dimension == "equipment":
                    if allocation.equipment_id is None:
                        continue
                    code = str(allocation.equipment_id)
                    name = allocation.equipment_name_snapshot or allocation.equipment_code_snapshot or code
                else:
                    code = str(allocation.area_id)
                    name = allocation.area_name_snapshot
                item = groups.setdefault(
                    code,
                    {
                        "code": code,
                        "name": name,
                        "value": Decimal(0),
                        "records": set(),
                        "warnings": set(),
                        "evidence": set(),
                    },
                )
                item["value"] += row.result.co2e_kg * allocation.allocation_ratio
                item["records"].add(row.activity.record_code)
                if row.result.quality_status != "pass":
                    item["warnings"].add(row.activity.record_code)
                if evidence_by_record.get(row.activity.record_code, 0):
                    item["evidence"].add(row.activity.record_code)
        return groups

    async def _budget_target(
        self,
        query: GhgAnalyticsFilter,
        run: GhgCalculationRun,
        actual_co2e_kg: Decimal | None,
    ) -> dict[str, Any] | None:
        context = await self._run_context(run)
        period = await self.session.get(ReportingPeriod, run.reporting_period_id) if run.reporting_period_id else None
        start = query.date_from or (period.period_start if period else None)
        end = query.date_to or (period.period_end if period else None)
        if start is None or end is None:
            return None
        target_scope = "enterprise"
        target_code: str | None = None
        if query.equipment_id is not None:
            equipment = await self.session.get(MonitorEquipment, query.equipment_id)
            if equipment is None:
                return None
            target_scope = "device"
            target_code = equipment.code
        elif query.area_id is not None:
            area = await self.session.get(MonitorSector, query.area_id)
            if area is None:
                return None
            target_scope = "area"
            target_code = area.code
        plan = await EnergyBudgetQueryService(self.session).selected_plan(
            EnergyBudgetQuery(
                budget_year=start.year,
                target_scope=target_scope,
                target_code=target_code,
            )
        )
        if plan is None or plan.carbon_budget_co2e is None:
            return None
        allocations = list(
            (
                await self.session.scalars(
                    select(EnergyCarbonBudgetAllocation)
                    .where(
                        EnergyCarbonBudgetAllocation.plan_id == plan.id,
                        EnergyCarbonBudgetAllocation.period_month >= start.replace(day=1),
                        EnergyCarbonBudgetAllocation.period_month <= end,
                    )
                    .order_by(EnergyCarbonBudgetAllocation.period_month)
                )
            ).all()
        )
        budget_tonnes: Decimal | None = None
        if allocations:
            expected_months = self._month_starts(start, end)
            allocation_months = {item.period_month for item in allocations if item.carbon_budget_co2e is not None}
            if expected_months <= allocation_months:
                budget_tonnes = sum(
                    (item.carbon_budget_co2e or Decimal(0) for item in allocations),
                    Decimal(0),
                )
        elif start <= plan.period_start and end >= plan.period_end:
            budget_tonnes = plan.carbon_budget_co2e
        if budget_tonnes is None:
            return None
        actual_tonnes = actual_co2e_kg / Decimal(1000) if actual_co2e_kg is not None else None
        variance = actual_tonnes - budget_tonnes if actual_tonnes is not None else None
        rate = execution_rate_pct(actual_tonnes, budget_tonnes) if actual_tonnes is not None else None
        status = execution_status(rate, budget_tonnes > 0, actual_tonnes is not None)
        return {
            "planId": plan.id,
            "planName": plan.name,
            "targetScope": plan.target_scope,
            "targetCode": plan.target_code,
            "budgetCo2ETonnes": str(budget_tonnes),
            "actualCo2ETonnes": str(actual_tonnes) if actual_tonnes is not None else None,
            "varianceCo2ETonnes": str(variance) if variance is not None else None,
            "executionRatePct": str(rate) if rate is not None else None,
            "status": status,
            "reportingPeriodName": context.get("reportingPeriodName"),
        }

    async def _comparable_total(
        self,
        run: GhgCalculationRun,
        query: GhgAnalyticsFilter,
        *,
        mode: str,
    ) -> Decimal | None:
        period = await self.session.get(ReportingPeriod, run.reporting_period_id) if run.reporting_period_id else None
        if period is None:
            return None
        selected_start = query.date_from or period.period_start
        selected_end = query.date_to or period.period_end
        if mode == "previous":
            span = selected_end - selected_start
            target_end = selected_start - timedelta(days=1)
            target_start = target_end - span
        else:
            try:
                target_start = selected_start.replace(year=selected_start.year - 1)
                target_end = selected_end.replace(year=selected_end.year - 1)
            except ValueError:
                target_start = selected_start.replace(year=selected_start.year - 1, day=28)
                target_end = selected_end.replace(year=selected_end.year - 1, day=28)
        candidate_period = await self.session.scalar(
            select(ReportingPeriod)
            .where(
                ReportingPeriod.reporting_org_id == run.reporting_org_id,
                ReportingPeriod.period_start <= target_start,
                ReportingPeriod.period_end >= target_end,
            )
            .order_by(ReportingPeriod.period_start.desc())
            .limit(1)
        )
        if candidate_period is None:
            return None
        candidate = await self.session.scalar(
            select(GhgCalculationRun)
            .where(
                GhgCalculationRun.reporting_org_id == run.reporting_org_id,
                GhgCalculationRun.reporting_profile_id == run.reporting_profile_id,
                GhgCalculationRun.reporting_period_id == candidate_period.id,
                GhgCalculationRun.status == "completed",
            )
            .order_by(GhgCalculationRun.completed_at.desc(), GhgCalculationRun.id.desc())
            .limit(1)
        )
        if candidate is None:
            return None
        candidate_slice = await GhgResultSliceQuery(self.session).execute(
            replace(
                query,
                run_code=candidate.run_code,
                date_from=target_start,
                date_to=target_end,
            )
        )
        return sum((row.attributed_co2e_kg for row in candidate_slice.rows), Decimal(0))

    async def _boundary_version(self, boundary_id: int | None) -> int | None:
        boundary = await self.session.get(OrganizationBoundary, boundary_id) if boundary_id else None
        return boundary.version if boundary else None

    @staticmethod
    def _period_bucket(period_start: date, period_end: date, grain: str) -> str | None:
        if grain == "month":
            if (period_start.year, period_start.month) != (period_end.year, period_end.month):
                return None
            return period_start.strftime("%Y-%m")
        if grain == "quarter":
            start_quarter = (period_start.month - 1) // 3 + 1
            end_quarter = (period_end.month - 1) // 3 + 1
            if period_start.year != period_end.year or start_quarter != end_quarter:
                return None
            return f"{period_start.year}-Q{start_quarter}"
        if period_start.year != period_end.year:
            return None
        return str(period_start.year)

    @staticmethod
    def _month_starts(period_start: date, period_end: date) -> set[date]:
        current = period_start.replace(day=1)
        end = period_end.replace(day=1)
        output: set[date] = set()
        while current <= end:
            output.add(current)
            current = date(
                current.year + (1 if current.month == DECEMBER else 0),
                1 if current.month == DECEMBER else current.month + 1,
                1,
            )
        return output

    @staticmethod
    def _change_payload(prefix: str, current: Decimal, previous: Decimal | None) -> dict[str, Any]:
        if previous is None:
            return {
                f"{prefix}TotalCo2EKg": None,
                f"{prefix}ChangeCo2EKg": None,
                f"{prefix}ChangePct": None,
            }
        change = current - previous
        change_pct = change / previous * Decimal(100) if previous else None
        return {
            f"{prefix}TotalCo2EKg": str(previous),
            f"{prefix}ChangeCo2EKg": str(change),
            f"{prefix}ChangePct": str(change_pct.quantize(Decimal("0.01"))) if change_pct is not None else None,
        }

    @staticmethod
    def _group_attributed_rows(
        rows: list[GhgAttributedResultRow],
        key_fn: Callable[[GhgAttributedResultRow], str],
        labels: dict[str, str],
        evidence_by_record: dict[str, int],
    ) -> dict[str, dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for row in rows:
            code = str(key_fn(row))
            item = groups.setdefault(
                code,
                {
                    "code": code,
                    "name": labels.get(code, code),
                    "value": Decimal(0),
                    "records": set(),
                    "warnings": set(),
                    "evidence": set(),
                },
            )
            item["value"] += row.attributed_co2e_kg
            item["records"].add(row.activity.record_code)
            if row.result.quality_status != "pass":
                item["warnings"].add(row.activity.record_code)
            if evidence_by_record.get(row.activity.record_code, 0):
                item["evidence"].add(row.activity.record_code)
        return groups

    @staticmethod
    def _validate_scope2_method(method: str) -> None:
        if method not in {"location", "market"}:
            msg = "Scope 2口径只能选择地点法或市场法"
            raise ValueError(msg)

    @staticmethod
    def _result_selected(result: GhgCalculationResult, method: str) -> bool:
        return result.ghg_scope != "scope2" or result.scope2_method in {"not_applicable", method}

    @staticmethod
    def _method_total(run: GhgCalculationRun, method: str) -> tuple[Decimal | None, bool]:
        summary = dict(run.summary_snapshot or {})
        value_key = "totalLocationCo2eKg" if method == "location" else "totalMarketCo2eKg"
        available_key = "scope2LocationAvailable" if method == "location" else "scope2MarketAvailable"
        available = bool(summary.get(available_key, method == run.default_scope2_method))
        value = summary.get(value_key)
        if value is None and method == run.default_scope2_method and run.total_co2e_kg is not None:
            value = run.total_co2e_kg
            available = True
        return (Decimal(str(value)) if value is not None and available else None, available)

    @staticmethod
    def _scope2_total(summary: dict[str, Any], method: str) -> Decimal | None:
        total_key = "totalLocationCo2eKg" if method == "location" else "totalMarketCo2eKg"
        total = summary.get(total_key)
        scope_totals = cast("dict[str, Any]", summary.get("scopeTotals") or {})
        scope1 = Decimal(str(scope_totals.get("scope1") or 0))
        scope3 = Decimal(str(scope_totals.get("scope3") or 0))
        return Decimal(str(total)) - scope1 - scope3 if total is not None else None

    @staticmethod
    def _quality_status(run: GhgCalculationRun) -> str:
        counts = cast("dict[str, Any]", (run.quality_snapshot or {}).get("qualityCounts") or {})
        if int(counts.get("failed") or 0) > 0:
            return "failed"
        if int(counts.get("warning") or 0) > 0:
            return "warning"
        return "pass"

    @staticmethod
    def _group_result_rows(
        rows: list[ResultRow],
        key_fn: Callable[[GhgCalculationResult, GhgActivityRecord, GhgEmissionSource | None], str],
        labels: dict[str, str],
        evidence_by_record: dict[str, int],
    ) -> dict[str, dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for result, activity, _method, source in rows:
            code = str(key_fn(result, activity, source))
            item = groups.setdefault(
                code,
                {
                    "code": code,
                    "name": labels.get(code, code),
                    "value": Decimal(0),
                    "records": set(),
                    "warnings": set(),
                    "evidence": set(),
                },
            )
            item["value"] += result.co2e_kg
            item["records"].add(activity.record_code)
            if result.quality_status != "pass":
                item["warnings"].add(activity.record_code)
            if evidence_by_record.get(activity.record_code, 0):
                item["evidence"].add(activity.record_code)
        return groups

    @staticmethod
    def _group_allocated_rows(
        rows: list[ResultRow],
        allocation_by_activity: dict[int, list[GhgActivityAllocation]],
        *,
        dimension: str,
        evidence_by_record: dict[str, int],
    ) -> dict[str, dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for result, activity, _method, _source in rows:
            for allocation in allocation_by_activity.get(activity.id, []):
                if dimension == "equipment":
                    if not allocation.equipment_code_snapshot:
                        continue
                    code = allocation.equipment_code_snapshot
                    name = allocation.equipment_name_snapshot or code
                else:
                    code = allocation.area_code_snapshot
                    name = allocation.area_name_snapshot
                item = groups.setdefault(
                    code,
                    {
                        "code": code,
                        "name": name,
                        "value": Decimal(0),
                        "records": set(),
                        "warnings": set(),
                        "evidence": set(),
                    },
                )
                item["value"] += result.co2e_kg * allocation.allocation_ratio
                item["records"].add(activity.record_code)
                if result.quality_status != "pass":
                    item["warnings"].add(activity.record_code)
                if evidence_by_record.get(activity.record_code, 0):
                    item["evidence"].add(activity.record_code)
        return groups

    @staticmethod
    def _finalize_breakdown(groups: dict[str, dict[str, Any]], total: Decimal) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for item in groups.values():
            records = item["records"]
            evidence = item["evidence"]
            percentage = item["value"] / total * Decimal(100) if total else Decimal(0)
            coverage = Decimal(len(evidence)) / Decimal(len(records)) * Decimal(100) if records else Decimal(100)
            output.append(
                {
                    "code": item["code"],
                    "name": item["name"],
                    "valueCo2EKg": str(item["value"]),
                    "percentage": str(percentage.quantize(Decimal("0.01"))),
                    "recordCount": len(records),
                    "warningCount": len(item["warnings"]),
                    "evidenceCoveragePct": str(coverage.quantize(Decimal("0.01"))),
                }
            )
        return sorted(output, key=lambda item: Decimal(item["valueCo2EKg"]), reverse=True)

    @staticmethod
    def _readiness_check(code: str, name: str, complete: int, total: int, *, blocking: bool = True) -> dict[str, Any]:
        coverage = (
            Decimal(100)
            if total == 0 and code == "evidence"
            else (Decimal(complete) / Decimal(total) * Decimal(100) if total else Decimal(0))
        )
        missing = max(total - complete, 0)
        return {
            "code": code,
            "name": name,
            "status": "pass" if missing == 0 else ("warning" if not blocking else "failed"),
            "completedCount": complete,
            "totalCount": total,
            "coveragePct": str(coverage.quantize(Decimal("0.01"))),
            "blockingCount": missing if blocking else 0,
        }

    @staticmethod
    def _coverage(complete: int, total: int) -> str:
        value = Decimal(complete) / Decimal(total) * Decimal(100) if total else Decimal(0)
        return str(value.quantize(Decimal("0.01")))

    @staticmethod
    def _run_list_item(
        run: GhgCalculationRun,
        profile: GhgReportingProfile,
        organization: ReportingOrganization | None,
        period: ReportingPeriod | None,
        boundary: OrganizationBoundary | None,
    ) -> dict[str, Any]:
        return {
            "runCode": run.run_code,
            "inventoryCode": run.inventory_code,
            "status": run.status,
            "reportingOrgId": run.reporting_org_id,
            "reportingOrgName": organization.name if organization else None,
            "reportingPeriodId": run.reporting_period_id,
            "reportingPeriodName": period.name if period else None,
            "organizationBoundaryId": run.organization_boundary_id,
            "organizationBoundaryName": boundary.boundary_name if boundary else None,
            "reportingProfileCode": profile.code,
            "reportingProfileName": profile.name,
            "defaultScope2Method": run.default_scope2_method,
            "totalCo2EKg": str(run.total_co2e_kg) if run.total_co2e_kg is not None else None,
            "qualityStatus": GhgAnalyticsQueryService._quality_status(run),
            "startedAt": run.started_at.isoformat(),
            "completedAt": run.completed_at.isoformat() if run.completed_at else None,
        }
