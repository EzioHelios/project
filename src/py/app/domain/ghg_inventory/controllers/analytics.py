"""Organization GHG inventory analysis and internal report APIs."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any, cast

import msgspec
from litestar import Controller, delete, get, patch, post
from litestar.exceptions import ClientException
from litestar.response import Response

from app.db import models as m  # noqa: TC001 - Litestar resolves current_user dependency from this runtime annotation.
from app.domain.accounts.guards import requires_permission
from app.domain.ghg_inventory.infrastructure.result_export import build_result_export_bytes
from app.domain.ghg_inventory.queries.analytics import GhgAnalyticsQueryService
from app.domain.ghg_inventory.queries.result_slice import GhgAnalyticsFilter
from app.domain.ghg_inventory.schemas import (
    GhgAnalyticsBreakdownResponse,
    GhgAnalyticsFlowResponse,
    GhgAnalyticsOverviewResponse,
    GhgAnalyticsTrendResponse,
    GhgComparisonResponse,
    GhgInventoryReadinessResponse,
    GhgInventoryReportActionRequest,
    GhgInventoryReportCreateRequest,
    GhgInventoryReportDeleteResponse,
    GhgInventoryReportListResponse,
    GhgInventoryReportResponse,
    GhgInventoryReportUpdateRequest,
    GhgResultDetailResponse,
    GhgResultListResponse,
    GhgResultSummaryResponse,
)
from app.domain.ghg_inventory.usecases.reports import (
    CreateInventoryReport,
    DeleteInventoryReport,
    ExportInventoryReport,
    TransitionInventoryReport,
    UpdateInventoryReport,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class GhgInventoryAnalyticsController(Controller):
    """Analysis projections for completed organization-inventory calculations."""

    path = "/api/ghg-inventory"
    tags = ["GHG Inventory Analytics"]

    @get(
        "/analytics/overview",
        operation_id="GhgInventoryGetAnalyticsOverview",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def overview(
        self,
        db_session: AsyncSession,
        run_code: str | None = None,
        scope2_method: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        ghg_scope: str | None = None,
        iso_category_code: str | None = None,
        source_code: str | None = None,
        source_mechanism: str | None = None,
        area_id: int | None = None,
        include_descendants: bool = True,
        equipment_id: int | None = None,
        quality_status: str | None = None,
    ) -> GhgAnalyticsOverviewResponse:
        analytics_filter = _analytics_filter(
            run_code=run_code,
            scope2_method=scope2_method or "location",
            date_from=date_from,
            date_to=date_to,
            ghg_scope=ghg_scope,
            iso_category_code=iso_category_code,
            source_code=source_code,
            source_mechanism=source_mechanism,
            area_id=area_id,
            include_descendants=include_descendants,
            equipment_id=equipment_id,
            quality_status=quality_status,
        )
        return msgspec.convert(
            await self._query(
                db_session,
                "overview",
                run_code=run_code,
                scope2_method=scope2_method,
                analytics_filter=analytics_filter,
            ),
            type=GhgAnalyticsOverviewResponse,
        )

    @get(
        "/analytics/trend",
        operation_id="GhgInventoryGetAnalyticsTrend",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def trend(
        self,
        db_session: AsyncSession,
        reporting_org_id: int | None = None,
        scope2_method: str = "location",
        limit: int = 12,
        run_code: str | None = None,
        grain: str = "month",
        date_from: str | None = None,
        date_to: str | None = None,
        ghg_scope: str | None = None,
        iso_category_code: str | None = None,
        source_code: str | None = None,
        source_mechanism: str | None = None,
        area_id: int | None = None,
        include_descendants: bool = True,
        equipment_id: int | None = None,
        quality_status: str | None = None,
    ) -> GhgAnalyticsTrendResponse:
        analytics_filter = _analytics_filter(
            run_code=run_code,
            scope2_method=scope2_method,
            date_from=date_from,
            date_to=date_to,
            ghg_scope=ghg_scope,
            iso_category_code=iso_category_code,
            source_code=source_code,
            source_mechanism=source_mechanism,
            area_id=area_id,
            include_descendants=include_descendants,
            equipment_id=equipment_id,
            quality_status=quality_status,
        )
        return msgspec.convert(
            await self._query(
                db_session,
                "trend",
                reporting_org_id=reporting_org_id,
                scope2_method=scope2_method,
                limit=min(max(limit, 1), 60),
                analytics_filter=analytics_filter,
                grain=grain,
            ),
            type=GhgAnalyticsTrendResponse,
        )

    @get(
        "/analytics/breakdown",
        operation_id="GhgInventoryGetAnalyticsBreakdown",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def breakdown(
        self,
        db_session: AsyncSession,
        run_code: str,
        dimension: str,
        scope2_method: str = "location",
    ) -> GhgAnalyticsBreakdownResponse:
        return msgspec.convert(
            await self._query(
                db_session,
                "breakdown",
                run_code=run_code,
                dimension=dimension,
                scope2_method=scope2_method,
            ),
            type=GhgAnalyticsBreakdownResponse,
        )

    @get(
        "/analytics/flow",
        operation_id="GhgInventoryGetAnalyticsFlow",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def flow(
        self,
        db_session: AsyncSession,
        run_code: str,
        classification: str = "scope",
        scope2_method: str = "location",
        date_from: str | None = None,
        date_to: str | None = None,
        ghg_scope: str | None = None,
        iso_category_code: str | None = None,
        source_code: str | None = None,
        source_mechanism: str | None = None,
        area_id: int | None = None,
        include_descendants: bool = True,
        equipment_id: int | None = None,
        quality_status: str | None = None,
    ) -> GhgAnalyticsFlowResponse:
        analytics_filter = _analytics_filter(
            run_code=run_code,
            scope2_method=scope2_method,
            date_from=date_from,
            date_to=date_to,
            ghg_scope=ghg_scope,
            iso_category_code=iso_category_code,
            source_code=source_code,
            source_mechanism=source_mechanism,
            area_id=area_id,
            include_descendants=include_descendants,
            equipment_id=equipment_id,
            quality_status=quality_status,
        )
        return msgspec.convert(
            await self._query(
                db_session,
                "flow",
                run_code=run_code,
                classification=classification,
                scope2_method=scope2_method,
                analytics_filter=analytics_filter,
            ),
            type=GhgAnalyticsFlowResponse,
        )

    @get(
        "/results",
        operation_id="GhgInventoryListResults",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def results(
        self,
        db_session: AsyncSession,
        run_code: str,
        scope2_method: str = "location",
        ghg_scope: str | None = None,
        iso_category_code: str | None = None,
        source_code: str | None = None,
        quality_status: str | None = None,
        keyword: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        source_mechanism: str | None = None,
        area_id: int | None = None,
        include_descendants: bool = True,
        equipment_id: int | None = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "period_start",
        sort_order: str = "desc",
    ) -> GhgResultListResponse:
        page_size = page_size if page_size in {25, 50, 100} else 25
        offset = (max(page, 1) - 1) * page_size
        analytics_filter = _analytics_filter(
            run_code=run_code,
            scope2_method=scope2_method,
            date_from=date_from,
            date_to=date_to,
            ghg_scope=ghg_scope,
            iso_category_code=iso_category_code,
            source_code=source_code,
            source_mechanism=source_mechanism,
            area_id=area_id,
            include_descendants=include_descendants,
            equipment_id=equipment_id,
            quality_status=quality_status,
            keyword=keyword,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return msgspec.convert(
            await self._query(
                db_session,
                "results",
                run_code=run_code,
                scope2_method=scope2_method,
                ghg_scope=ghg_scope,
                iso_category_code=iso_category_code,
                source_code=source_code,
                quality_status=quality_status,
                keyword=keyword,
                limit=page_size,
                offset=offset,
                analytics_filter=analytics_filter,
            ),
            type=GhgResultListResponse,
        )

    @get(
        "/results/summary",
        operation_id="GhgInventoryGetResultSummary",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def result_summary(
        self,
        db_session: AsyncSession,
        run_code: str,
        scope2_method: str = "location",
        date_from: str | None = None,
        date_to: str | None = None,
        ghg_scope: str | None = None,
        iso_category_code: str | None = None,
        source_code: str | None = None,
        source_mechanism: str | None = None,
        area_id: int | None = None,
        include_descendants: bool = True,
        equipment_id: int | None = None,
        quality_status: str | None = None,
        keyword: str | None = None,
    ) -> GhgResultSummaryResponse:
        analytics_filter = _analytics_filter(**locals())
        return msgspec.convert(
            await self._query(db_session, "results_summary", analytics_filter=analytics_filter),
            type=GhgResultSummaryResponse,
        )

    @get(
        "/analytics/comparison",
        operation_id="GhgInventoryGetAnalyticsComparison",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def comparison(
        self,
        db_session: AsyncSession,
        run_codes: str,
        scope2_method: str = "location",
        date_from: str | None = None,
        date_to: str | None = None,
        ghg_scope: str | None = None,
        iso_category_code: str | None = None,
        source_code: str | None = None,
        source_mechanism: str | None = None,
        area_id: int | None = None,
        include_descendants: bool = True,
        equipment_id: int | None = None,
        quality_status: str | None = None,
    ) -> GhgComparisonResponse:
        codes = [item.strip() for item in run_codes.split(",") if item.strip()]
        analytics_filter = _analytics_filter(**locals())
        return msgspec.convert(
            await self._query(
                db_session,
                "comparison",
                run_codes=codes,
                analytics_filter=analytics_filter,
            ),
            type=GhgComparisonResponse,
        )

    @get(
        "/results/export.xlsx",
        operation_id="GhgInventoryExportResults",
        guards=[requires_permission("carbon.inventory.export")],
    )
    async def export_results(
        self,
        db_session: AsyncSession,
        run_code: str,
        scope2_method: str = "location",
        date_from: str | None = None,
        date_to: str | None = None,
        ghg_scope: str | None = None,
        iso_category_code: str | None = None,
        source_code: str | None = None,
        source_mechanism: str | None = None,
        area_id: int | None = None,
        include_descendants: bool = True,
        equipment_id: int | None = None,
        quality_status: str | None = None,
        keyword: str | None = None,
    ) -> Response[bytes]:
        analytics_filter = _analytics_filter(**locals())
        try:
            content = await build_result_export_bytes(db_session, analytics_filter)
        except ValueError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="organization-ghg-results.xlsx"'},
        )

    @get(
        "/results/{record_code:str}",
        operation_id="GhgInventoryGetResultDetail",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def result_detail(
        self,
        db_session: AsyncSession,
        record_code: str,
        run_code: str,
        scope2_method: str = "location",
    ) -> GhgResultDetailResponse:
        return msgspec.convert(
            await self._query(
                db_session,
                "result_detail",
                run_code=run_code,
                record_code=record_code,
                scope2_method=scope2_method,
            ),
            type=GhgResultDetailResponse,
        )

    @get(
        "/readiness",
        operation_id="GhgInventoryGetReadiness",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def readiness(
        self,
        db_session: AsyncSession,
        inventory_code: str,
        reporting_period_id: int | None = None,
        organization_boundary_id: int | None = None,
    ) -> GhgInventoryReadinessResponse:
        return msgspec.convert(
            await self._query(
                db_session,
                "readiness",
                inventory_code=inventory_code,
                reporting_period_id=reporting_period_id,
                organization_boundary_id=organization_boundary_id,
            ),
            type=GhgInventoryReadinessResponse,
        )

    async def _query(self, db_session: AsyncSession, method: str, **kwargs: Any) -> dict[str, Any]:
        try:
            return cast("dict[str, Any]", await getattr(GhgAnalyticsQueryService(db_session), method)(**kwargs))
        except ValueError as exc:
            status_code = 404 if "不存在" in str(exc) or "没有可用" in str(exc) else 422
            raise ClientException(status_code=status_code, detail=str(exc)) from exc


class GhgInventoryReportController(Controller):
    """Internal inventory report drafting, review and publication."""

    path = "/api/ghg-inventory/reports"
    tags = ["GHG Inventory Reports"]

    @get(operation_id="GhgInventoryListReports", guards=[requires_permission("carbon.inventory.view")])
    async def reports(
        self, db_session: AsyncSession, limit: int = 50, offset: int = 0
    ) -> GhgInventoryReportListResponse:
        payload = await GhgAnalyticsQueryService(db_session).reports(
            limit=min(max(limit, 1), 200), offset=max(offset, 0)
        )
        return msgspec.convert(payload, type=GhgInventoryReportListResponse)

    @post(
        operation_id="GhgInventoryCreateReport",
        guards=[requires_permission("carbon.inventory.report.manage")],
    )
    async def create_report(
        self,
        db_session: AsyncSession,
        data: GhgInventoryReportCreateRequest,
    ) -> GhgInventoryReportResponse:
        try:
            report = await CreateInventoryReport(db_session).execute(
                run_code=data.run_code,
                title=data.title,
                change_summary=data.change_summary,
            )
        except ValueError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        return msgspec.convert(
            await GhgAnalyticsQueryService(db_session).report_payload(report), type=GhgInventoryReportResponse
        )

    @get(
        "/{report_code:str}/{version:int}",
        operation_id="GhgInventoryGetReport",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def report(
        self,
        db_session: AsyncSession,
        report_code: str,
        version: int,
    ) -> GhgInventoryReportResponse:
        try:
            report = await GhgAnalyticsQueryService(db_session).report(report_code=report_code, version=version)
        except ValueError as exc:
            raise ClientException(status_code=404, detail=str(exc)) from exc
        return msgspec.convert(report, type=GhgInventoryReportResponse)

    @get(
        "/{report_code:str}/{version:int}/export",
        operation_id="GhgInventoryExportReport",
        guards=[requires_permission("carbon.inventory.export")],
    )
    async def export_report(
        self,
        db_session: AsyncSession,
        report_code: str,
        version: int,
        file_format: str = "docx",
    ) -> Response[bytes]:
        try:
            exported = await ExportInventoryReport(db_session).execute(
                report_code=report_code,
                version=version,
                file_format=file_format,
            )
        except ValueError as exc:
            status_code = 404 if "不存在" in str(exc) else 422
            raise ClientException(status_code=status_code, detail=str(exc)) from exc
        return Response(
            content=exported.content,
            media_type=exported.content_type,
            headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
        )

    @patch(
        "/{report_code:str}/{version:int}",
        operation_id="GhgInventoryUpdateReport",
        guards=[requires_permission("carbon.inventory.report.manage")],
    )
    async def update_report(
        self,
        db_session: AsyncSession,
        report_code: str,
        version: int,
        data: GhgInventoryReportUpdateRequest,
    ) -> GhgInventoryReportResponse:
        try:
            report = await UpdateInventoryReport(db_session).execute(
                report_code=report_code,
                version=version,
                title=data.title,
                change_summary=data.change_summary,
            )
        except ValueError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        return msgspec.convert(
            await GhgAnalyticsQueryService(db_session).report_payload(report), type=GhgInventoryReportResponse
        )

    @delete(
        "/{report_code:str}/{version:int}",
        operation_id="GhgInventoryDeleteReport",
        guards=[requires_permission("carbon.inventory.report.manage")],
        status_code=200,
    )
    async def delete_report(
        self,
        db_session: AsyncSession,
        current_user: m.User,
        report_code: str,
        version: int,
    ) -> GhgInventoryReportDeleteResponse:
        try:
            result = await DeleteInventoryReport(db_session).execute(
                report_code=report_code,
                version=version,
                actor=current_user.email,
            )
        except ValueError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        return GhgInventoryReportDeleteResponse(
            report_code=cast("str", result["report_code"]),
            version=cast("int", result["version"]),
            deleted=cast("bool", result["deleted"]),
            status=cast("str | None", result["status"]),
        )

    @post(
        "/{report_code:str}/{version:int}/submit",
        operation_id="GhgInventorySubmitReport",
        guards=[requires_permission("carbon.inventory.report.manage")],
    )
    async def submit_report(
        self,
        db_session: AsyncSession,
        current_user: m.User,
        report_code: str,
        version: int,
        data: GhgInventoryReportActionRequest,
    ) -> GhgInventoryReportResponse:
        return await self._transition(db_session, current_user, report_code, version, "submit", data)

    @post(
        "/{report_code:str}/{version:int}/resubmit",
        operation_id="GhgInventoryResubmitReport",
        guards=[requires_permission("carbon.inventory.report.manage")],
    )
    async def resubmit_report(
        self,
        db_session: AsyncSession,
        current_user: m.User,
        report_code: str,
        version: int,
        data: GhgInventoryReportActionRequest,
    ) -> GhgInventoryReportResponse:
        return await self._transition(db_session, current_user, report_code, version, "resubmit", data)

    @post(
        "/{report_code:str}/{version:int}/approve",
        operation_id="GhgInventoryApproveReport",
        guards=[requires_permission("carbon.inventory.report.review")],
    )
    async def approve_report(
        self,
        db_session: AsyncSession,
        current_user: m.User,
        report_code: str,
        version: int,
        data: GhgInventoryReportActionRequest,
    ) -> GhgInventoryReportResponse:
        return await self._transition(db_session, current_user, report_code, version, "approve", data)

    @post(
        "/{report_code:str}/{version:int}/reject",
        operation_id="GhgInventoryRejectReport",
        guards=[requires_permission("carbon.inventory.report.review")],
    )
    async def reject_report(
        self,
        db_session: AsyncSession,
        current_user: m.User,
        report_code: str,
        version: int,
        data: GhgInventoryReportActionRequest,
    ) -> GhgInventoryReportResponse:
        return await self._transition(db_session, current_user, report_code, version, "reject", data)

    @post(
        "/{report_code:str}/{version:int}/publish",
        operation_id="GhgInventoryPublishReport",
        guards=[requires_permission("carbon.inventory.report.publish")],
    )
    async def publish_report(
        self,
        db_session: AsyncSession,
        current_user: m.User,
        report_code: str,
        version: int,
        data: GhgInventoryReportActionRequest,
    ) -> GhgInventoryReportResponse:
        return await self._transition(db_session, current_user, report_code, version, "publish", data)

    @post(
        "/{report_code:str}/{version:int}/archive",
        operation_id="GhgInventoryArchiveReport",
        guards=[requires_permission("carbon.inventory.report.publish")],
    )
    async def archive_report(
        self,
        db_session: AsyncSession,
        current_user: m.User,
        report_code: str,
        version: int,
        data: GhgInventoryReportActionRequest,
    ) -> GhgInventoryReportResponse:
        return await self._transition(db_session, current_user, report_code, version, "archive", data)

    @staticmethod
    async def _transition(
        db_session: AsyncSession,
        current_user: m.User,
        report_code: str,
        version: int,
        action: str,
        data: GhgInventoryReportActionRequest,
    ) -> GhgInventoryReportResponse:
        try:
            report = await TransitionInventoryReport(db_session).execute(
                report_code=report_code,
                version=version,
                action=action,
                actor=current_user.email,
                comment=data.comment,
            )
        except ValueError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        return msgspec.convert(
            await GhgAnalyticsQueryService(db_session).report_payload(report), type=GhgInventoryReportResponse
        )


def _analytics_filter(**values: Any) -> GhgAnalyticsFilter:
    try:
        date_from = date.fromisoformat(values["date_from"]) if values.get("date_from") else None
        date_to = date.fromisoformat(values["date_to"]) if values.get("date_to") else None
    except ValueError as exc:
        raise ClientException(status_code=422, detail="日期格式必须为YYYY-MM-DD") from exc
    return GhgAnalyticsFilter(
        run_code=values.get("run_code"),
        scope2_method=str(values.get("scope2_method") or "location"),
        date_from=date_from,
        date_to=date_to,
        ghg_scope=values.get("ghg_scope"),
        iso_category_code=values.get("iso_category_code"),
        source_code=values.get("source_code"),
        source_mechanism=values.get("source_mechanism"),
        area_id=values.get("area_id"),
        include_descendants=bool(values.get("include_descendants", True)),
        equipment_id=values.get("equipment_id"),
        quality_status=values.get("quality_status"),
        keyword=values.get("keyword"),
        sort_by=str(values.get("sort_by") or "period_start"),
        sort_order=str(values.get("sort_order") or "desc"),
    )
