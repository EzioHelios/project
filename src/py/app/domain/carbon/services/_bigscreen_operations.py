"""Warehouse presentation queries over existing tenant-owned business facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, true

from app.db import models as m
from app.domain.carbon.services._bigscreen_ledger import ledger_overview
from app.domain.energy.queries.flow import EnergyFlowQuery, EnergyFlowQueryService
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


MAX_WINDOW_DAYS = 366
MAX_HOURLY_DAYS = 31
MAX_EVENT_PAGE_SIZE = 50


def resolve_window(start: date | None, end: date | None, latest: datetime | None) -> tuple[date, date]:
    """Use the latest available month unless a period was explicitly selected."""
    end = end or (latest.date() if latest else datetime.now(UTC).date())
    start = start or end.replace(day=1)
    if start > end or (end - start).days > MAX_WINDOW_DAYS:
        msg = "请选择起止顺序正确且不超过一年的期间"
        raise ValueError(msg)
    return start, end


def trend_points(rows: Any, start: date, end: date, grain: str) -> list[dict[str, Any]]:
    """Keep absent intervals as gaps, not zero readings."""
    if not rows:
        return []
    values = {moment.replace(tzinfo=None): float(value) for moment, value in rows}
    current = datetime.combine(start.replace(day=1) if grain == "month" else start, datetime.min.time())
    stop = datetime.combine(end + timedelta(days=1), datetime.min.time())
    points = []
    while current < stop:
        points.append({"period": current.isoformat(), "value": values.get(current)})
        if grain == "month":
            current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        else:
            current += timedelta(hours=1) if grain == "hour" else timedelta(days=1)
    return points


def descendant_codes(rows: Any, selected: str) -> list[str]:
    """Expand configured hierarchy by IDs, not by similar names."""
    found = {item_id for item_id, code, _, _ in rows if code == selected}
    while True:
        children = {item_id for item_id, _, parent_id, _ in rows if parent_id in found}
        if children <= found:
            return [code for item_id, code, _, _ in rows if item_id in found]
        found |= children


def energy_filters() -> list[Any]:
    fact = m.EnergyIntervalFact
    return [
        fact.is_current.is_(True),
        fact.energy_type_code.in_(["electricity", "purchased_electricity"]),
        fact.unit == "kWh",
        fact.source_system.in_(["meter_projection", "meter_daily", "meter_hourly"]),
        fact.equipment_id.in_(select(m.MonitorEquipment.id).where(m.MonitorEquipment.category == 0)),
        fact.data_quality != "simulated",
        ~fact.source_system.like("demo%"),
    ]


@dataclass
class BigscreenOperationsService:
    session: AsyncSession

    async def energy_calendar(self, end: date, area_codes: list[str] | None = None) -> list[dict[str, Any]]:
        fact = m.EnergyIntervalFact
        conditions = [
            *energy_filters(),
            fact.granularity == "day",
            fact.period_start >= datetime.combine(end.replace(month=1, day=1), datetime.min.time()),
            fact.period_start < datetime.combine(end + timedelta(days=1), datetime.min.time()),
        ]
        if area_codes is not None:
            conditions.append(fact.area_id.in_(area_codes))
        bucket = func.date_trunc("day", fact.period_start)
        rows = (
            await self.session.execute(select(bucket, func.sum(fact.amount)).where(*conditions).group_by(bucket))
        ).all()
        result = []
        for key, label, since in [
            ("day", "当日已记录", end),
            ("month", "当月已记录", end.replace(day=1)),
            ("year", "当年已记录", end.replace(month=1, day=1)),
        ]:
            eligible = [(moment, amount) for moment, amount in rows if moment.date() >= since]
            result.append(
                {
                    "id": key,
                    "label": label,
                    "value": float(sum(amount for _, amount in eligible)) if eligible else None,
                    "unit": "kWh",
                    "start": since.isoformat(),
                    "end": end.isoformat(),
                    "recorded_days": len(eligible),
                    "calendar_days": (end - since).days + 1,
                }
            )
        return result

    async def build(
        self, *, start: date | None = None, end: date | None = None, grain: str = "day", area: str | None = None
    ) -> dict[str, Any]:
        if grain not in {"hour", "day", "month"}:
            msg = "不支持的时间粒度"
            raise ValueError(msg)
        fact = m.EnergyIntervalFact
        first, latest = (
            await self.session.execute(
                select(func.min(fact.period_start), func.max(fact.period_start)).where(
                    *energy_filters(), fact.granularity == "day"
                )
            )
        ).one()
        start, end = resolve_window(start, end, latest)
        area_rows = (
            await self.session.execute(
                select(m.MonitorSector.id, m.MonitorSector.code, m.MonitorSector.parent_id, m.MonitorSector.name)
                .where(m.MonitorSector.is_enable.is_(True))
                .order_by(m.MonitorSector.sort_index, m.MonitorSector.id)
            )
        ).all()
        if grain == "hour" and (end - start).days >= MAX_HOURLY_DAYS:
            msg = "小时趋势请选择不超过31天的期间"
            raise ValueError(msg)
        conditions = [
            *energy_filters(),
            fact.granularity == ("hour" if grain == "hour" else "day"),
            fact.period_start >= datetime.combine(start, datetime.min.time()),
            fact.period_start < datetime.combine(end + timedelta(days=1), datetime.min.time()),
        ]
        if area:
            conditions.append(fact.area_id.in_(descendant_codes(area_rows, area)))
        calendar = await self.energy_calendar(end, descendant_codes(area_rows, area) if area else None)
        flow = await EnergyFlowQueryService(self.session).graph(
            EnergyFlowQuery(
                period_start=start.isoformat(),
                period_end=end.isoformat(),
                granularity="hour" if grain == "hour" else "day",
                energy_type_code="electricity",
                metered_only=True,
                area_codes=tuple(descendant_codes(area_rows, area)) if area else None,
            )
        )
        count, total, covered_devices, covered_areas, observed = (
            await self.session.execute(
                select(
                    func.count(),
                    func.sum(fact.amount),
                    func.count(func.distinct(fact.equipment_id)),
                    func.count(func.distinct(fact.area_id)),
                    func.max(fact.created_at),
                ).where(*conditions)
            )
        ).one()
        bucket = func.date_trunc(grain, fact.period_start)
        series = (
            await self.session.execute(
                select(bucket, func.sum(fact.amount)).where(*conditions).group_by(bucket).order_by(bucket)
            )
        ).all()
        areas = [(code, name) for _, code, _, name in area_rows]
        by_area = (
            await self.session.execute(
                select(fact.area_id, fact.area_name, func.sum(fact.amount))
                .where(*conditions)
                .group_by(fact.area_id, fact.area_name)
                .order_by(func.sum(fact.amount).desc())
            )
        ).all()
        by_device = (
            await self.session.execute(
                select(fact.equipment_id, fact.equipment_name, func.sum(fact.amount))
                .where(*conditions)
                .group_by(fact.equipment_id, fact.equipment_name)
                .order_by(func.sum(fact.amount).desc())
            )
        ).all()
        equipment = (
            await self.session.scalars(select(m.MonitorEquipment).where(m.MonitorEquipment.is_enable.is_(True)))
        ).all()
        tenant_id = require_session_tenant_id(self.session)
        meter = m.MonitorEquipment.__table__
        reading_fact = m.MeterReadingFact.__table__
        # Seek the newest eligible row per device instead of sorting its entire history.
        latest_reading = (
            select(reading_fact.c.reading_time, reading_fact.c.normalized_value, reading_fact.c.unit)
            .where(
                reading_fact.c.team_id == tenant_id,
                reading_fact.c.equipment_id == meter.c.id,
                reading_fact.c.quality_status == "valid",
                reading_fact.c.point_code == "forward_active_total",
                reading_fact.c.value_kind == "register_index",
                ~reading_fact.c.source_system.like("demo%"),
            )
            .order_by(reading_fact.c.reading_time.desc(), reading_fact.c.id.desc())
            .limit(1)
            .lateral("latest_reading")
        )
        readings = {
            row.equipment_id: row
            for row in (
                await self.session.execute(
                    select(
                        meter.c.id.label("equipment_id"),
                        latest_reading.c.reading_time,
                        latest_reading.c.normalized_value,
                        latest_reading.c.unit,
                    )
                    .select_from(meter.join(latest_reading, true()))
                    .where(meter.c.team_id == tenant_id, meter.c.is_enable.is_(True))
                )
            ).all()
        }
        area_names = {item_id: name for item_id, _, _, name in area_rows}
        devices = []
        for device in equipment:
            reading = readings.get(device.id)
            devices.append(
                {
                    "id": str(device.id),
                    "name": device.name or device.code,
                    "category": device.category,
                    "status": device.status,
                    "area": area_names.get(device.sector_id),
                    "area_id": str(device.sector_id) if device.sector_id else None,
                    "last_reading": reading.reading_time.isoformat() if reading else None,
                    "register_value": float(reading.normalized_value)
                    if reading and reading.normalized_value is not None
                    else None,
                    "register_unit": reading.unit if reading else None,
                }
            )
        enterprise = await self.session.scalar(select(m.EnterpriseInfo).order_by(m.EnterpriseInfo.id.desc()).limit(1))
        fields = [
            ("所属单位", "belong_unit", ""),
            ("仓储面积", "store_area", " m²"),
            ("园区面积", "park_area", " m²"),
            ("绿化面积", "green_area", " m²"),
            ("员工人数", "people_count", " 人"),
            ("仓库位置", "location", ""),
        ]
        company = []
        if enterprise:
            for label, field, unit in fields:
                value = getattr(enterprise, field)
                if (
                    value is None
                    or (isinstance(value, (float, int)) and value <= 0)
                    or (isinstance(value, str) and not value.strip())
                ):
                    continue
                company.append(
                    {
                        "label": label,
                        "value": f"{value:g}{unit}"
                        if isinstance(value, (float, int))
                        else str(value)
                        if value is not None
                        else "未填写",
                    }
                )
        commute_power = (
            await self.session.execute(
                select(m.EmployeeCommute.car_power_type, func.count()).group_by(m.EmployeeCommute.car_power_type)
            )
        ).all()
        ledger = await ledger_overview(self.session)
        alarms = await self.alerts()
        safety = await self.alerts(video=True)
        carbon_alarms = await self.alerts(event_types=[4])
        power_alarms = await self.alerts(event_types=[2, 3])
        business = []
        for model, label, amount in [(m.InMoney, "入库单据", m.InMoney.shje), (m.OutMoney, "出库单据", m.OutMoney.je)]:
            quantity, valid, amount_total = (
                await self.session.execute(
                    select(func.count(), func.count(amount), func.sum(amount)).select_from(model)
                )
            ).one()
            business.append({"label": label, "value": quantity, "unit": "条", "detail": f"含金额 {valid} 条"})
            business.append(
                {
                    "label": label.replace("单据", "金额"),
                    "value": float(amount_total) / 10000 if valid else None,
                    "unit": "万元",
                    "detail": f"历史台账合计, 含金额 {valid}/{quantity} 条",
                }
            )
        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "grain": grain,
            "available_start": first.date().isoformat() if first else None,
            "available_end": latest.date().isoformat() if latest else None,
            "observed_at": observed.isoformat() if observed else None,
            "areas": [{"value": code, "label": name or code} for code, name in areas],
            "energy_kpis": [
                {"id": "energy", "label": "电表电量合计", "value": float(total) if count else None, "unit": "kWh"},
                {"id": "meters", "label": "有数据电表", "value": covered_devices, "unit": "台"},
                {"id": "areas", "label": "覆盖区域", "value": covered_areas, "unit": "个"},
            ],
            "energy_calendar": calendar,
            "energy_flow": flow,
            "profile": (enterprise.other_info or {}).get("public_profile") if enterprise else None,
            "presentation": (enterprise.other_info or {}).get("bigscreen", {}) if enterprise else {},
            "ledger": ledger,
            "commute_power": [
                {"name": {0: "柴油", 1: "汽油", 2: "电力"}.get(kind, "未登记"), "value": quantity}
                for kind, quantity in commute_power
            ],
            "trend": trend_points(series, start, end, grain),
            "area_ranking": [
                {"id": code, "name": name or "未归集", "value": float(value)} for code, name, value in by_area
            ],
            "equipment_ranking": [
                {"id": str(code), "name": name or "未命名设备", "value": float(value)}
                for code, name, value in by_device
            ],
            "company_name": enterprise.name if enterprise else None,
            "company_facts": company,
            "devices": devices,
            "alarms": alarms,
            "safety": safety,
            "carbon_alarms": carbon_alarms,
            "power_alarms": power_alarms,
            "business": business,
        }

    async def alerts(
        self,
        *,
        video: bool = False,
        event_types: list[int] | None = None,
        start: date | None = None,
        end: date | None = None,
        status: str | None = None,
        area: str | None = None,
        page: int = 1,
        page_size: int = 8,
    ) -> dict[str, Any]:
        if page < 1 or not 1 <= page_size <= MAX_EVENT_PAGE_SIZE:
            msg = "分页范围无效"
            raise ValueError(msg)
        if start and end and start > end:
            msg = "开始日期不能晚于结束日期"
            raise ValueError(msg)
        if status not in {None, "pending", "handled", "unknown"}:
            msg = "处理状态无效"
            raise ValueError(msg)
        model = m.VedioAlarmEvent if video else m.AlarmEvent
        conditions = [model.event_type.in_(event_types)] if event_types else []
        if start:
            conditions.append(model.event_time >= start)
        if end:
            conditions.append(model.event_time < end + timedelta(days=1))
        if status:
            conditions.append(model.is_handle.is_({"pending": False, "handled": True, "unknown": None}[status]))
        labels = (
            {1: "安全帽", 2: "烟火", 3: "火点", 4: "区域入侵"}
            if video
            else {1: "设备故障", 2: "用电异常", 3: "发电异常", 4: "碳排异常"}
        )
        if video:
            region = func.coalesce(func.nullif(m.VideoMonitor.f_area, ""), "未分区")
            device_name = m.VideoMonitor.location
            joins = [
                (m.VideoMonitor, (m.VideoMonitor.id == model.equipment_id) & (m.VideoMonitor.team_id == model.team_id))
            ]
        else:
            region = func.coalesce(m.MonitorSector.name, "未关联区域")
            device_name = m.MonitorEquipment.name
            joins = [
                (m.MonitorSector, (m.MonitorSector.id == model.sector_id) & (m.MonitorSector.team_id == model.team_id)),
                (
                    m.MonitorEquipment,
                    (m.MonitorEquipment.id == model.equipment_id) & (m.MonitorEquipment.team_id == model.team_id),
                ),
            ]
        if area:
            conditions.append(region == area)
        base = select(model.id).select_from(model)
        for target, condition in joins:
            base = base.outerjoin(target, condition)
        base = base.where(*conditions)
        rows = (
            await self.session.execute(
                base.with_only_columns(
                    model.event_type,
                    func.count(),
                    func.min(model.event_time),
                    func.max(model.event_time),
                ).group_by(model.event_type)
            )
        ).all()
        region_stmt = base.with_only_columns(region, func.count())
        recent_stmt = base.with_only_columns(model, region, device_name)
        regions = (await self.session.execute(region_stmt.group_by(region).order_by(func.count().desc()))).all()
        recent = (
            await self.session.execute(
                recent_stmt.order_by(model.event_time.desc().nullslast(), model.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        states = (
            await self.session.execute(base.with_only_columns(model.is_handle, func.count()).group_by(model.is_handle))
        ).all()
        levels = {"info": "提示", "warning": "预警", "critical": "严重"}
        return {
            "page": page,
            "page_size": page_size,
            "total": sum(row[1] for row in rows),
            "start": min((row[2] for row in rows if row[2]), default=None),
            "end": max((row[3] for row in rows if row[3]), default=None),
            "distribution": [
                {"id": str(kind), "name": labels.get(kind, "其他"), "value": count} for kind, count, _, _ in rows
            ],
            "region_distribution": [{"name": name, "value": count} for name, count in regions],
            "status_distribution": [
                {"name": "已处理" if handled else "未处理" if handled is False else "未记录", "value": count}
                for handled, count in states
            ],
            "recent": [
                {
                    "id": str(item.id),
                    "title": item.event_desc or labels.get(item.event_type, "其他"),
                    "type": labels.get(item.event_type, "其他"),
                    "time": item.event_time,
                    "status": "已处理" if item.is_handle else "未处理" if item.is_handle is False else "未记录",
                    "area": region_name,
                    "device": device or "未关联设备",
                    "level": None if video else levels.get(item.alarm_level, "未记录"),
                    "handle_note": None if video else item.handle_note,
                }
                for item, region_name, device in recent
            ],
        }
