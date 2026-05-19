from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.domain.carbon import bigscreen_schemas as bs
from app.domain.carbon import models as m

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


CARBON_ALERT_EVENT_TYPE = 4


def _to_float(value: Decimal | float | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _percent_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 1)


def _safe_text(value: Any, fallback: str = "未配置") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _media_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://", "/")):
        return path
    return f"/media/{path}"


def _month_period(value: str | None) -> str:
    if not value:
        return "未标注"
    return value.replace("-", ".")


async def _sum_first_available(
    session: AsyncSession,
    model: type[Any],
    field_names: tuple[str, ...],
) -> float:
    for field_name in field_names:
        column = getattr(model, field_name, None)
        if column is None:
            continue
        result = await session.execute(select(func.sum(column)))
        return _to_float(result.scalar_one())
    return 0.0


@dataclass(slots=True)
class BigscreenMetaService:
    title: str
    short_name: str
    description: str

    def build(self) -> bs.BigscreenMetaPayload:
        return bs.BigscreenMetaPayload(
            title=f"{self.title} 态势大屏",
            short_name=self.short_name,
            description=self.description,
            default_path="/bigscreen/overview",
            show_weather=False,
            promo_video_url=None,
            nav_items=[
                bs.BigscreenNavItem(label="企业介绍", path="/bigscreen/intro"),
                bs.BigscreenNavItem(label="态势总览", path="/bigscreen/overview"),
                bs.BigscreenNavItem(label="电量监控", path="/bigscreen/power"),
                bs.BigscreenNavItem(label="能碳协同", path="/bigscreen/carbon"),
            ],
        )


@dataclass(slots=True)
class BigscreenIntroService:
    session: AsyncSession
    meta: BigscreenMetaService

    async def build(self) -> bs.BigscreenIntroPayload:
        enterprise = (
            await self.session.execute(select(m.EnterpriseInfo).order_by(m.EnterpriseInfo.id.desc()).limit(1))
        ).scalars().first()
        sectors = (
            await self.session.execute(
                select(m.MonitorSector)
                .options(selectinload(m.MonitorSector.photos))
                .where(m.MonitorSector.is_enable.is_(True))
                .order_by(m.MonitorSector.id.asc())
                .limit(9)
            )
        ).scalars().all()

        photos: list[bs.BigscreenMediaItem] = []
        for sector in sectors:
            photos.extend(
                bs.BigscreenMediaItem(
                    id=f"photo-{photo.id}",
                    title=_safe_text(sector.name, "监测区域"),
                    description=_safe_text(photo.description, _safe_text(sector.description, "现场图像")),
                    image_url=_media_url(photo.path),
                )
                for photo in sector.photos[:2]
            )

        company_gallery = photos[:4]
        project_spotlights = [
            bs.BigscreenMediaItem(
                id=f"sector-{sector.id}",
                title=_safe_text(sector.name, "监测区域"),
                description=_safe_text(sector.description, "区域运行视角"),
                image_url=_media_url(sector.photos[0].path) if sector.photos else None,
            )
            for sector in sectors[:3]
        ]
        success_cases = photos[4:8]

        other_info = enterprise.other_info if enterprise and isinstance(enterprise.other_info, dict) else {}
        hero_description = (
            str(other_info.get("description")).strip()
            if isinstance(other_info.get("description"), str) and str(other_info.get("description")).strip()
            else f"{_safe_text(enterprise.name if enterprise else None, self.meta.title)}以仓储, 能碳, 监测三条主线组织经营现场。首版介绍页优先复用现有主数据与现场图片区, 后续可继续替换为客户定制内容。"
        )

        company_facts = [
            bs.BigscreenInfoItem(label="企业名称", value=_safe_text(enterprise.name if enterprise else None, self.meta.title)),
            bs.BigscreenInfoItem(label="所属单位", value=_safe_text(enterprise.belong_unit if enterprise else None)),
            bs.BigscreenInfoItem(label="行业方向", value=_safe_text(enterprise.industry if enterprise else None)),
            bs.BigscreenInfoItem(label="所在区域", value=_safe_text(enterprise.location if enterprise else None)),
            bs.BigscreenInfoItem(label="员工规模", value=_safe_text(enterprise.people_count if enterprise else None, "0")),
            bs.BigscreenInfoItem(label="仓储面积", value=f"{_to_float(enterprise.store_area if enterprise else None):,.0f} m2"),
            bs.BigscreenInfoItem(label="园区面积", value=f"{_to_float(enterprise.park_area if enterprise else None):,.0f} m2"),
            bs.BigscreenInfoItem(label="统一信用代码", value=_safe_text(enterprise.unify_code if enterprise else None)),
        ]

        return bs.BigscreenIntroPayload(
            hero_title=_safe_text(enterprise.name if enterprise else None, self.meta.title),
            hero_description=hero_description,
            company_gallery=company_gallery,
            project_spotlights=project_spotlights,
            success_cases=success_cases,
            promo_video_url=str(other_info.get("promo_video_url")) if other_info.get("promo_video_url") else None,
            company_facts=company_facts,
        )


@dataclass(slots=True)
class BigscreenOverviewService:
    session: AsyncSession

    async def build(self) -> bs.BigscreenOverviewPayload:
        monthly_rows = (
            await self.session.execute(
                select(
                    m.Scope2MeterAggregate.billing_month,
                    func.sum(m.Scope2MeterAggregate.total_kwh),
                    func.sum(m.Scope2MeterAggregate.computed_co2e),
                )
                .group_by(m.Scope2MeterAggregate.billing_month)
                .order_by(m.Scope2MeterAggregate.billing_month.asc())
            )
        ).all()

        latest_month = monthly_rows[-1][0] if monthly_rows else None
        latest_energy = _to_float(monthly_rows[-1][1]) if monthly_rows else 0
        prev_energy = _to_float(monthly_rows[-2][1]) if len(monthly_rows) > 1 else 0
        latest_carbon = _to_float(monthly_rows[-1][2]) if monthly_rows else 0
        prev_carbon = _to_float(monthly_rows[-2][2]) if len(monthly_rows) > 1 else 0
        current_year = (latest_month or datetime.now(UTC).strftime("%Y-%m"))[:4]
        year_rows = [row for row in monthly_rows if row[0] and row[0].startswith(current_year)]
        ytd_energy = sum(_to_float(row[1]) for row in year_rows)
        ytd_carbon = sum(_to_float(row[2]) for row in year_rows)

        active_meter_count = int(
            (
                await self.session.execute(
                    select(func.count(func.distinct(m.Scope2MeterAggregate.ammeter_id))).where(
                        m.Scope2MeterAggregate.billing_month == latest_month
                    )
                )
            ).scalar_one()
            or 0
        ) if latest_month else 0
        area_count = int(
            (
                await self.session.execute(
                    select(func.count(m.MonitorSector.id)).where(m.MonitorSector.is_enable.is_(True))
                )
            ).scalar_one()
            or 0
        )

        trend_points = [
            bs.BigscreenTrendPoint(
                period=_month_period(row[0]),
                energy_kwh=_to_float(row[1]),
                carbon_co2e=_to_float(row[2]),
                value=_to_float(row[1]),
            )
            for row in monthly_rows[-12:]
        ]

        by_area_rows = []
        if latest_month:
            by_area_rows = (
                await self.session.execute(
                    select(m.Scope2MeterAggregate.area_name, func.sum(m.Scope2MeterAggregate.total_kwh))
                    .where(m.Scope2MeterAggregate.billing_month == latest_month)
                    .group_by(m.Scope2MeterAggregate.area_name)
                    .order_by(func.sum(m.Scope2MeterAggregate.total_kwh).desc())
                )
            ).all()

        flow_nodes = [bs.BigscreenFlowNode(id="grid", name="外部购电", category="source")]
        flow_links: list[bs.BigscreenFlowLink] = []
        for index, row in enumerate(by_area_rows[:6], start=1):
            node_id = f"area-{index}"
            flow_nodes.append(
                bs.BigscreenFlowNode(id=node_id, name=_safe_text(row[0], f"区域 {index}"), category="area", value=_to_float(row[1]))
            )
            flow_links.append(bs.BigscreenFlowLink(source="grid", target=node_id, value=_to_float(row[1])))

        return bs.BigscreenOverviewPayload(
            energy_kpis=[
                bs.BigscreenMetric(id="month-energy", label="最新账期用电", value=round(latest_energy, 2), unit="kWh", ratio=_percent_change(latest_energy, prev_energy)),
                bs.BigscreenMetric(id="ytd-energy", label="本年累计用电", value=round(ytd_energy, 2), unit="kWh"),
                bs.BigscreenMetric(id="active-meters", label="活跃电表", value=active_meter_count, unit="台"),
            ],
            carbon_kpis=[
                bs.BigscreenMetric(id="month-carbon", label="最新账期碳排", value=round(latest_carbon, 2), unit="kgCO2e", ratio=_percent_change(latest_carbon, prev_carbon)),
                bs.BigscreenMetric(id="ytd-carbon", label="本年累计碳排", value=round(ytd_carbon, 2), unit="kgCO2e"),
                bs.BigscreenMetric(id="area-count", label="在线区域", value=area_count, unit="个"),
            ],
            energy_flow=bs.BigscreenFlowData(title="购电流向", unit="kWh", nodes=flow_nodes, links=flow_links),
            production_trend=trend_points,
            filters={
                "months": [{"label": _month_period(row[0]), "value": row[0]} for row in monthly_rows[-12:]],
                "areas": [{"label": _safe_text(row[0], "未分区"), "value": _safe_text(row[0], "unknown")} for row in by_area_rows[:8]],
            },
        )


@dataclass(slots=True)
class BigscreenPowerService:
    session: AsyncSession

    async def build(self) -> bs.BigscreenPowerPayload:
        monthly_rows = (
            await self.session.execute(
                select(
                    m.Scope2MeterAggregate.billing_month,
                    func.sum(m.Scope2MeterAggregate.total_kwh),
                    func.sum(m.Scope2MeterAggregate.computed_co2e),
                )
                .group_by(m.Scope2MeterAggregate.billing_month)
                .order_by(m.Scope2MeterAggregate.billing_month.asc())
            )
        ).all()
        latest_month = monthly_rows[-1][0] if monthly_rows else None

        structure_rows = []
        ranking_rows = []
        if latest_month:
            structure_rows = (
                await self.session.execute(
                    select(m.Scope2MeterAggregate.area_name, func.sum(m.Scope2MeterAggregate.total_kwh))
                    .where(m.Scope2MeterAggregate.billing_month == latest_month)
                    .group_by(m.Scope2MeterAggregate.area_name)
                    .order_by(func.sum(m.Scope2MeterAggregate.total_kwh).desc())
                )
            ).all()
            ranking_rows = (
                await self.session.execute(
                    select(m.Scope2MeterAggregate.ammeter_name, func.sum(m.Scope2MeterAggregate.total_kwh))
                    .where(m.Scope2MeterAggregate.billing_month == latest_month)
                    .group_by(m.Scope2MeterAggregate.ammeter_name)
                    .order_by(func.sum(m.Scope2MeterAggregate.total_kwh).desc())
                )
            ).all()

        latest_alerts = (
            await self.session.execute(
                select(m.AlarmEvent)
                .order_by(m.AlarmEvent.event_time.desc().nullslast(), m.AlarmEvent.id.desc())
                .limit(6)
            )
        ).scalars().all()

        device_online = int(
            (
                await self.session.execute(
                    select(func.count(m.MonitorEquipment.id)).where(m.MonitorEquipment.status == 0)
                )
            ).scalar_one()
            or 0
        )
        device_total = int((await self.session.execute(select(func.count(m.MonitorEquipment.id)))).scalar_one() or 0)

        trend_points = [
            bs.BigscreenTrendPoint(
                period=_month_period(row[0]),
                energy_kwh=_to_float(row[1]),
                carbon_co2e=_to_float(row[2]),
                value=_to_float(row[1]),
            )
            for row in monthly_rows[-12:]
        ]

        flow_nodes = [bs.BigscreenFlowNode(id="source", name="总电量", category="source")]
        flow_links: list[bs.BigscreenFlowLink] = []
        for index, row in enumerate(structure_rows[:6], start=1):
            node_id = f"power-area-{index}"
            flow_nodes.append(bs.BigscreenFlowNode(id=node_id, name=_safe_text(row[0], f"区域 {index}"), value=_to_float(row[1]), category="area"))
            flow_links.append(bs.BigscreenFlowLink(source="source", target=node_id, value=_to_float(row[1])))

        return bs.BigscreenPowerPayload(
            alerts=[
                bs.BigscreenAlertItem(
                    id=f"alert-{item.id}",
                    title=_safe_text(item.event_desc, "设备预警"),
                    detail=f"事件类型 {item.event_type}",
                    occurred_at=item.event_time.isoformat() if item.event_time else None,
                    severity="warning" if item.is_handle is False else "info",
                )
                for item in latest_alerts
            ],
            energy_structure=[
                bs.BigscreenDistributionItem(name=_safe_text(row[0], "未分区"), value=round(_to_float(row[1]), 2))
                for row in structure_rows[:8]
            ],
            energy_ranking=[
                bs.BigscreenDistributionItem(name=_safe_text(row[0], "未命名电表"), value=round(_to_float(row[1]), 2))
                for row in ranking_rows[:8]
            ],
            energy_flow=bs.BigscreenFlowData(title="区域用电流图", unit="kWh", nodes=flow_nodes, links=flow_links),
            energy_timeseries=trend_points,
            hero_metrics=[
                bs.BigscreenMetric(id="power-online", label="在线终端", value=device_online, unit="台"),
                bs.BigscreenMetric(id="power-total", label="终端总量", value=device_total, unit="台"),
                bs.BigscreenMetric(id="power-latest", label="最新账期总电量", value=round(_to_float(monthly_rows[-1][1]) if monthly_rows else 0, 2), unit="kWh"),
            ],
        )


@dataclass(slots=True)
class BigscreenCarbonService:
    session: AsyncSession

    async def build(self) -> bs.BigscreenCarbonPayload:
        scope1_mobile = await _sum_first_available(self.session, m.Scope1MobileCombustion, ("computed_co2e", "amount"))
        scope1_stationary = await _sum_first_available(
            self.session,
            m.Scope1StationaryCombustion,
            ("computed_co2e", "amount"),
        )
        scope1_refrigerant = await _sum_first_available(
            self.session,
            m.Scope1RefrigerantLeak,
            ("computed_co2e", "amount_kg"),
        )
        scope2_meter = await _sum_first_available(self.session, m.Scope2MeterAggregate, ("computed_co2e", "total_kwh"))
        scope2_bill = await _sum_first_available(
            self.session,
            m.Scope2ElectricityBill,
            ("computed_co2e", "total_kwh"),
        )
        scope3_waste = await _sum_first_available(
            self.session,
            m.Scope3WasteDisposal,
            ("computed_co2e", "weight_ton"),
        )
        scope3_transport = await _sum_first_available(
            self.session,
            m.Scope3ThirdPartyTransport,
            ("computed_co2e", "fuel_amount", "load_ton"),
        )

        scope1_total = scope1_mobile + scope1_stationary + scope1_refrigerant
        scope2_total = scope2_meter if scope2_meter > 0 else scope2_bill
        scope3_total = scope3_waste + scope3_transport

        latest_alerts = (
            await self.session.execute(
                select(m.AlarmEvent)
                .where(m.AlarmEvent.event_type == CARBON_ALERT_EVENT_TYPE)
                .order_by(m.AlarmEvent.event_time.desc().nullslast(), m.AlarmEvent.id.desc())
                .limit(6)
            )
        ).scalars().all()

        factor_rows = (
            await self.session.execute(
                select(m.EmissionFactor.year, func.avg(m.EmissionFactor.factor_value))
                .where(m.EmissionFactor.scope == "scope2", m.EmissionFactor.category == "electricity", m.EmissionFactor.is_active.is_(True))
                .group_by(m.EmissionFactor.year)
                .order_by(m.EmissionFactor.year.asc())
            )
        ).all()

        nodes = [
            bs.BigscreenFlowNode(id="root", name="总碳排", value=scope1_total + scope2_total + scope3_total, category="root"),
            bs.BigscreenFlowNode(id="scope1", name="范围1", value=scope1_total, category="scope"),
            bs.BigscreenFlowNode(id="scope2", name="范围2", value=scope2_total, category="scope"),
            bs.BigscreenFlowNode(id="scope3", name="范围3", value=scope3_total, category="scope"),
            bs.BigscreenFlowNode(id="mobile", name="移动源", value=scope1_mobile, category="activity"),
            bs.BigscreenFlowNode(id="stationary", name="固定源", value=scope1_stationary, category="activity"),
            bs.BigscreenFlowNode(id="refrigerant", name="制冷剂", value=scope1_refrigerant, category="activity"),
            bs.BigscreenFlowNode(id="electricity", name="购入电力", value=scope2_total, category="activity"),
            bs.BigscreenFlowNode(id="waste", name="废弃物", value=scope3_waste, category="activity"),
            bs.BigscreenFlowNode(id="transport", name="运输", value=scope3_transport, category="activity"),
        ]
        links = [
            bs.BigscreenFlowLink(source="root", target="scope1", value=scope1_total),
            bs.BigscreenFlowLink(source="root", target="scope2", value=scope2_total),
            bs.BigscreenFlowLink(source="root", target="scope3", value=scope3_total),
            bs.BigscreenFlowLink(source="scope1", target="mobile", value=scope1_mobile),
            bs.BigscreenFlowLink(source="scope1", target="stationary", value=scope1_stationary),
            bs.BigscreenFlowLink(source="scope1", target="refrigerant", value=scope1_refrigerant),
            bs.BigscreenFlowLink(source="scope2", target="electricity", value=scope2_total),
            bs.BigscreenFlowLink(source="scope3", target="waste", value=scope3_waste),
            bs.BigscreenFlowLink(source="scope3", target="transport", value=scope3_transport),
        ]

        commentary: list[str] = []
        if scope2_total > 0:
            commentary.append("范围2 仍然是当前大屏最稳定, 可追踪的主碳源, 适合作为首版经营展示主轴。")
        if scope1_total == 0 and scope3_total == 0:
            commentary.append("范围1与范围3 当前数据覆盖有限, 页面会如实展示为空或低值, 不使用演示值填充。")
        if not factor_rows:
            commentary.append("当前库内没有可直接用于碳价走势的正式数据, 首版图表保留空态。")

        return bs.BigscreenCarbonPayload(
            carbon_compare=[
                bs.BigscreenComparisonItem(name="范围1", current=round(scope1_total, 2), unit="kgCO2e"),
                bs.BigscreenComparisonItem(name="范围2", current=round(scope2_total, 2), unit="kgCO2e"),
                bs.BigscreenComparisonItem(name="范围3", current=round(scope3_total, 2), unit="kgCO2e"),
            ],
            production_share=[
                bs.BigscreenDistributionItem(name="范围1", value=round(scope1_total, 2)),
                bs.BigscreenDistributionItem(name="范围2", value=round(scope2_total, 2)),
                bs.BigscreenDistributionItem(name="范围3", value=round(scope3_total, 2)),
            ],
            carbon_flow=bs.BigscreenFlowData(title="范围级碳流", unit="kgCO2e", nodes=nodes, links=links),
            carbon_alerts=[
                bs.BigscreenAlertItem(
                    id=f"carbon-alert-{item.id}",
                    title=_safe_text(item.event_desc, "碳排异常"),
                    detail=f"事件类型 {item.event_type}",
                    occurred_at=item.event_time.isoformat() if item.event_time else None,
                    severity="warning" if item.is_handle is False else "info",
                )
                for item in latest_alerts
            ],
            carbon_price_trend=[
                bs.BigscreenTrendPoint(period=str(row[0]), carbon_co2e=round(_to_float(row[1]), 4), value=round(_to_float(row[1]), 4))
                for row in factor_rows
            ],
            commentary=commentary,
            hero_metrics=[
                bs.BigscreenMetric(id="carbon-total", label="总碳排", value=round(scope1_total + scope2_total + scope3_total, 2), unit="kgCO2e"),
                bs.BigscreenMetric(id="carbon-scope2", label="范围2占比", value=round(scope2_total, 2), unit="kgCO2e"),
                bs.BigscreenMetric(id="carbon-factors", label="有效电力因子年份", value=len(factor_rows), unit="个"),
            ],
        )
