from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.domain.carbon import bigscreen_schemas as bs
from app.domain.carbon import models as m
from app.domain.ghg_inventory import models as ghg
from app.domain.ghg_inventory.domain.catalog import CATEGORY_BY_CODE
from app.domain.ghg_inventory.queries.analytics import GhgAnalyticsQueryService
from app.domain.ghg_inventory.queries.result_slice import GhgAnalyticsFilter

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


CARBON_ALERT_EVENT_TYPE = 4


@dataclass(slots=True)
class BigscreenMetaService:
    title: str
    short_name: str
    description: str

    def build(self) -> bs.BigscreenMetaPayload:
        return bs.BigscreenMetaPayload(
            title=self.title,
            short_name=self.short_name,
            description="",
            default_path="/bigscreen/overview",
            show_weather=False,
            promo_video_url=None,
            nav_items=[
                bs.BigscreenNavItem(label="态势总览", path="/bigscreen/overview"),
                bs.BigscreenNavItem(label="运行监测", path="/bigscreen/monitor"),
                bs.BigscreenNavItem(label="电量监控", path="/bigscreen/power"),
                bs.BigscreenNavItem(label="碳排管理", path="/bigscreen/carbon"),
            ],
        )


@dataclass(slots=True)
class BigscreenIntroService:
    session: AsyncSession
    meta: BigscreenMetaService

    async def build(self) -> bs.BigscreenIntroPayload:
        enterprise = await self.session.scalar(select(m.EnterpriseInfo).order_by(m.EnterpriseInfo.id.desc()).limit(1))
        sectors = (
            await self.session.scalars(
                select(m.MonitorSector)
                .options(selectinload(m.MonitorSector.photos))
                .where(m.MonitorSector.is_enable.is_(True))
                .order_by(m.MonitorSector.id)
            )
        ).all()
        photos = [
            bs.BigscreenMediaItem(
                id=str(photo.id),
                title=sector.name or "区域照片",
                description=photo.description,
                image_url=f"/api/bigscreen/photos/{photo.id}",
            )
            for sector in sectors
            for photo in sector.photos
            if photo.path
        ]
        fields = [
            ("企业名称", "name"),
            ("所属单位", "belong_unit"),
            ("行业", "industry"),
            ("仓库位置", "location"),
            ("员工人数", "people_count"),
            ("仓储面积(m²)", "store_area"),
            ("园区面积(m²)", "park_area"),
            ("统一信用代码", "unify_code"),
        ]
        return bs.BigscreenIntroPayload(
            hero_title=enterprise.name if enterprise else "仓库档案",
            company_gallery=photos,
            profile=(enterprise.other_info or {}).get("public_profile") if enterprise else None,
            company_facts=[
                bs.BigscreenInfoItem(
                    label=label,
                    value=str(getattr(enterprise, field)) if getattr(enterprise, field) is not None else "未填写",
                )
                for label, field in fields
                if getattr(enterprise, field) is not None
                and str(getattr(enterprise, field)).strip()
                and not (isinstance(getattr(enterprise, field), (float, int)) and getattr(enterprise, field) <= 0)
            ]
            if enterprise
            else [],
        )


@dataclass(slots=True)
class BigscreenCarbonService:
    session: AsyncSession

    async def build(self) -> bs.BigscreenCarbonPayload:
        sample_runs = (
            select(ghg.GhgCalculationResult.run_id)
            .join(ghg.GhgActivityRecord, ghg.GhgActivityRecord.id == ghg.GhgCalculationResult.activity_id)
            .where(ghg.GhgActivityRecord.source_system.like("demo%"))
        )
        run = await self.session.scalar(
            select(ghg.GhgCalculationRun)
            .join(ghg.GhgInventoryReport, ghg.GhgInventoryReport.run_id == ghg.GhgCalculationRun.id)
            .where(
                ghg.GhgInventoryReport.status == "published",
                ghg.GhgCalculationRun.status == "completed",
                ghg.GhgCalculationRun.id.not_in(sample_runs),
            )
            .order_by(ghg.GhgInventoryReport.published_at.desc().nullslast(), ghg.GhgInventoryReport.id.desc())
            .limit(1)
        )
        if run is None:
            run = await self.session.scalar(
                select(ghg.GhgCalculationRun)
                .where(ghg.GhgCalculationRun.status == "completed", ghg.GhgCalculationRun.id.not_in(sample_runs))
                .order_by(ghg.GhgCalculationRun.completed_at.desc().nullslast(), ghg.GhgCalculationRun.id.desc())
                .limit(1)
            )
        scopes, areas, facts, sources, activity_counts, factors = [], [], [], [], [], []
        flow = bs.BigscreenFlowData(title="组织碳流", unit="kgCO2e")
        total = None
        if run:
            result = ghg.GhgCalculationResult
            conditions = [
                result.run_id == run.id,
                result.result_kind == "emission",
                or_(result.ghg_scope != "scope2", result.scope2_method == run.default_scope2_method),
            ]
            rows = (
                await self.session.execute(
                    select(result.ghg_scope, func.sum(result.co2e_kg)).where(*conditions).group_by(result.ghg_scope)
                )
            ).all()
            scopes = [
                bs.BigscreenDistributionItem(
                    name={"scope1": "范围一", "scope2": "范围二", "scope3": "范围三"}.get(scope, scope),
                    value=float(value),
                )
                for scope, value in rows
            ]
            total = sum(item.value for item in scopes) if scopes else None
            activity = ghg.GhgActivityRecord
            start, end, count = (
                await self.session.execute(
                    select(
                        func.min(activity.period_start),
                        func.max(activity.period_end),
                        func.count(func.distinct(activity.id)),
                    )
                    .join(result, result.activity_id == activity.id)
                    .where(*conditions)
                )
            ).one()
            facts = [
                bs.BigscreenInfoItem(label="数据期间", value=f"{start} 至 {end}" if start else "暂无"),
                bs.BigscreenInfoItem(
                    label="核算完成", value=str(run.completed_at.date()) if run.completed_at else "未记录"
                ),
                bs.BigscreenInfoItem(
                    label="范围二方法", value="地点法" if run.default_scope2_method == "location" else "市场法"
                ),
                bs.BigscreenInfoItem(label="活动记录", value=f"{count} 条"),
            ]
            graph = await GhgAnalyticsQueryService(self.session).flow(
                run_code=run.run_code,
                classification="iso_category",
                scope2_method=run.default_scope2_method,
                analytics_filter=GhgAnalyticsFilter(run_code=run.run_code, scope2_method=run.default_scope2_method),
            )
            flow = bs.BigscreenFlowData(title="组织碳流", unit="kgCO2e", nodes=graph["nodes"], links=graph["links"])
            total = float(graph["totalCo2EKg"])
            areas = [
                bs.BigscreenDistributionItem(name=node.name, value=node.value or 0)
                for node in flow.nodes
                if node.category == "resource"
            ]
            sources = [
                bs.BigscreenDistributionItem(name=node.name, value=node.value or 0)
                for node in flow.nodes
                if node.category == "source"
            ]
            rows = (
                await self.session.execute(
                    select(result.iso_category_code, func.count(func.distinct(result.activity_id)))
                    .where(*conditions)
                    .group_by(result.iso_category_code)
                )
            ).all()
            activity_counts = [
                bs.BigscreenDistributionItem(name=CATEGORY_BY_CODE[code].name, value=count) for code, count in rows
            ]
            assignment = ghg.GhgParameterAssignment
            rows = (
                await self.session.execute(
                    select(assignment.source_name, assignment.value, assignment.unit)
                    .where(
                        assignment.run_id == run.id,
                        assignment.activity_id.in_(select(result.activity_id).where(*conditions)),
                        assignment.parameter_role == "emission_factor",
                    )
                    .distinct()
                    .order_by(assignment.source_name, assignment.value, assignment.unit)
                )
            ).all()
            factors = [
                bs.BigscreenInfoItem(label=name, value=f"{value.normalize():f} {unit}") for name, value, unit in rows
            ]
        return bs.BigscreenCarbonPayload(
            hero_metrics=[
                bs.BigscreenMetric(id="carbon", label="核算排放量", value=total, unit="kgCO2e"),
                bs.BigscreenMetric(
                    id="allocated",
                    label="已归集排放量",
                    value=sum(
                        node.value or 0
                        for node in flow.nodes
                        if node.category == "resource" and node.id != "resource:unallocated"
                    )
                    if flow.nodes
                    else None,
                    unit="kgCO2e",
                ),
            ],
            period_facts=facts,
            scope_distribution=scopes,
            area_ranking=areas,
            flow=flow,
            source_ranking=sources,
            activity_distribution=activity_counts,
            factors=factors,
        )
