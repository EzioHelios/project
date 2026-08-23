"""Legacy URL adapters for equipment monitoring and operational alarms.

Organization-carbon analytics were retired from this bounded context. Carbon
inventory, quality, evidence and factor usage are owned by ``ghg_inventory``
and ``carbon_verification``. This controller deliberately exposes only the two
operational work surfaces that still use the historical URL prefix.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from dateutil.relativedelta import relativedelta
from litestar import Controller, get
from litestar.response import Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement

HIGH_RISK_UNHANDLED_ALERT_COUNT = 3


class EnergyOperationsCompatibilityController(Controller):
    """Serve monitoring and alarm pages without depending on carbon facts."""

    tags = ["Energy Operations"]

    async def _monitor_area_summary(self, db_session: AsyncSession) -> list[dict[str, Any]]:
        sectors = list(
            (
                await db_session.execute(
                    select(m.MonitorSector)
                    .options(selectinload(m.MonitorSector.photos))
                    .order_by(m.MonitorSector.id.asc())
                )
            )
            .scalars()
            .all()
        )
        equipment_counts = {sector.id: {"total": 0, "online": 0, "fault": 0} for sector in sectors}
        equipment_rows = (
            await db_session.execute(select(m.MonitorEquipment.sector_id, m.MonitorEquipment.status))
        ).all()
        for sector_id, status in equipment_rows:
            if sector_id not in equipment_counts:
                continue
            equipment_counts[sector_id]["total"] += 1
            equipment_counts[sector_id]["online" if status == 0 else "fault"] += 1

        alert_rows = (
            await db_session.execute(
                select(
                    m.AlarmEvent.sector_id,
                    func.count(m.AlarmEvent.id),
                    func.sum(case((m.AlarmEvent.is_handle.is_(False), 1), else_=0)),
                ).group_by(m.AlarmEvent.sector_id)
            )
        ).all()
        alert_map = {
            sector_id: {"total": int(total or 0), "unhandled": int(unhandled or 0)}
            for sector_id, total, unhandled in alert_rows
        }
        video_rows = (
            await db_session.execute(
                select(
                    m.VideoMonitor.f_area,
                    func.count(m.VideoMonitor.id),
                    func.sum(case((m.VideoMonitor.status == 0, 1), else_=0)),
                ).group_by(m.VideoMonitor.f_area)
            )
        ).all()
        video_map = {
            str(area or ""): {"total": int(total or 0), "online": int(online or 0)}
            for area, total, online in video_rows
        }

        items: list[dict[str, Any]] = []
        for sector in sectors:
            equipment = equipment_counts.get(sector.id, {"total": 0, "online": 0, "fault": 0})
            alerts = alert_map.get(sector.id, {"total": 0, "unhandled": 0})
            videos = video_map.get(str(sector.name or ""), {"total": 0, "online": 0})
            total_objects = max(equipment["total"] + videos["total"], 1)
            online_objects = equipment["online"] + videos["online"]
            items.append(
                {
                    "id": sector.id,
                    "name": sector.name or f"区域{sector.id}",
                    "area_id": sector.area_id,
                    "description": sector.description,
                    "equipment_total": equipment["total"],
                    "equipment_online": equipment["online"],
                    "equipment_fault": equipment["fault"],
                    "video_total": videos["total"],
                    "video_online": videos["online"],
                    "alert_total": alerts["total"],
                    "alert_unhandled": alerts["unhandled"],
                    "health_ratio": round((online_objects / total_objects) * 100, 1),
                    "status": "高风险"
                    if alerts["unhandled"] > HIGH_RISK_UNHANDLED_ALERT_COUNT or equipment["fault"] > 0
                    else "稳定",
                    "photo_count": len(sector.photos or []),
                }
            )
        return items

    async def _alerts(self, db_session: AsyncSession) -> list[dict[str, Any]]:
        area_names = {
            sector_id: sector_name or f"区域{sector_id}"
            for sector_id, sector_name in (
                await db_session.execute(select(m.MonitorSector.id, m.MonitorSector.name))
            ).all()
        }
        equipment_names = {
            equipment_id: equipment_name or equipment_code
            for equipment_id, equipment_name, equipment_code in (
                await db_session.execute(
                    select(m.MonitorEquipment.id, m.MonitorEquipment.name, m.MonitorEquipment.code)
                )
            ).all()
        }
        video_names = {
            video_id: location or f"视频点位{video_id}"
            for video_id, location in (
                await db_session.execute(select(m.VideoMonitor.id, m.VideoMonitor.location))
            ).all()
        }

        items: list[dict[str, Any]] = []
        alarm_rows = list(
            (
                await db_session.execute(
                    select(m.AlarmEvent).order_by(
                        m.AlarmEvent.event_time.desc().nullslast(),
                        m.AlarmEvent.id.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        severity_map = {1: "high", 2: "medium", 3: "medium", 4: "high"}
        type_map = {1: "设备告警", 2: "用能告警", 3: "发电告警", 4: "碳告警"}
        items.extend(
            [
                {
                    "id": f"alarm:{row.id}",
                    "source": "alarm",
                    "record_id": row.id,
                    "alert_type": type_map.get(row.event_type, "业务告警"),
                    "severity": severity_map.get(row.event_type, "medium"),
                    "title": row.event_desc or type_map.get(row.event_type, "业务告警"),
                    "area_name": area_names.get(row.sector_id, "未分区"),
                    "object_name": equipment_names.get(
                        row.equipment_id,
                        f"设备{row.equipment_id}" if row.equipment_id else "未关联对象",
                    ),
                    "status": "已处理" if row.is_handle else "待处理",
                    "occurred_at": row.event_time.isoformat() if row.event_time else None,
                    "description": row.event_desc,
                }
                for row in alarm_rows
            ]
        )

        video_rows = list(
            (
                await db_session.execute(
                    select(m.VedioAlarmEvent).order_by(
                        m.VedioAlarmEvent.event_time.desc().nullslast(),
                        m.VedioAlarmEvent.id.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        video_type_map = {1: "未佩戴安全帽", 2: "烟火", 3: "火点", 4: "区域入侵"}
        video_severity_map = {1: "medium", 2: "high", 3: "high", 4: "medium"}
        items.extend(
            [
                {
                    "id": f"video:{row.id}",
                    "source": "video",
                    "record_id": row.id,
                    "alert_type": "视频告警",
                    "severity": video_severity_map.get(row.event_type, "medium"),
                    "title": video_type_map.get(row.event_type, "视频告警"),
                    "area_name": "视频监控",
                    "object_name": video_names.get(
                        row.equipment_id,
                        f"视频{row.equipment_id}" if row.equipment_id else "未关联视频",
                    ),
                    "status": "已处理" if row.is_handle else "待处理",
                    "occurred_at": row.event_time.isoformat() if row.event_time else None,
                    "description": row.event_desc,
                }
                for row in video_rows
            ]
        )
        items.sort(key=lambda item: str(item.get("occurred_at") or ""), reverse=True)
        return items

    @staticmethod
    def _alert_facets(items: list[dict[str, Any]]) -> dict[str, Any]:
        dimensions: dict[str, dict[str, int]] = {
            "by_source": defaultdict(int),
            "by_severity": defaultdict(int),
            "by_status": defaultdict(int),
            "by_area": defaultdict(int),
        }
        for item in items:
            dimensions["by_source"][str(item["source"])] += 1
            dimensions["by_severity"][str(item["severity"])] += 1
            dimensions["by_status"][str(item["status"])] += 1
            dimensions["by_area"][str(item.get("area_name") or "未分区")] += 1
        return {
            key: [
                {"name": name, "value": value}
                for name, value in sorted(values.items(), key=lambda pair: pair[1], reverse=True)
            ][:10]
            for key, values in dimensions.items()
        }

    @staticmethod
    def _alert_trend(items: list[dict[str, Any]], months: int) -> list[dict[str, Any]]:
        current_month = datetime.datetime.now(tz=datetime.UTC).date().replace(day=1)
        labels = [
            (current_month - relativedelta(months=offset)).strftime("%Y-%m")
            for offset in range(max(1, months) - 1, -1, -1)
        ]
        counts: dict[str, dict[str, str | int]] = {
            label: {"period": label, "alerts_count": 0, "handled_count": 0} for label in labels
        }
        for item in items:
            month_key = str(item.get("occurred_at") or "")[:7]
            if month_key not in counts:
                continue
            counts[month_key]["alerts_count"] = int(counts[month_key]["alerts_count"]) + 1
            if item.get("status") == "已处理":
                counts[month_key]["handled_count"] = int(counts[month_key]["handled_count"]) + 1
        return list(counts.values())

    @get("/api/energy-carbon/monitor/areas", operation_id="EnergyOperationsListMonitorAreas")
    async def list_monitor_areas(self, db_session: AsyncSession) -> Response[dict[str, Any]]:
        return Response(
            content={"code": 200, "msg": "获取成功", "data": {"items": await self._monitor_area_summary(db_session)}}
        )

    @get("/api/energy-carbon/monitor/devices", operation_id="EnergyOperationsListMonitorDevices")
    async def list_monitor_devices(
        self,
        db_session: AsyncSession,
        sector_id: int | None = None,
        status: int | None = None,
        category: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict[str, Any]]:
        filters: list[ColumnElement[bool]] = []
        if sector_id is not None:
            filters.append(m.MonitorEquipment.sector_id == sector_id)
        if status is not None:
            filters.append(m.MonitorEquipment.status == status)
        if category is not None:
            filters.append(m.MonitorEquipment.category == category)
        stmt = (
            select(m.MonitorEquipment)
            .options(selectinload(m.MonitorEquipment.sector))
            .where(*filters)
            .order_by(m.MonitorEquipment.sort_index.asc().nullslast(), m.MonitorEquipment.id.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = list((await db_session.execute(stmt)).scalars().all())
        items: list[dict[str, Any]] = []
        for row in rows:
            alert_count = int(
                await db_session.scalar(
                    select(func.count(m.AlarmEvent.id)).where(
                        m.AlarmEvent.equipment_id == row.id,
                        m.AlarmEvent.is_handle.is_(False),
                    )
                )
                or 0
            )
            items.append(
                {
                    "id": row.id,
                    "name": row.name or row.code,
                    "code": row.code,
                    "category": row.category,
                    "sector_id": row.sector_id,
                    "sector_name": row.sector.name if row.sector else None,
                    "status": row.status,
                    "trip_state": row.trip_state,
                    "location": row.location,
                    "protocol": row.protocol,
                    "alert_unhandled": alert_count,
                }
            )
        total = int(await db_session.scalar(select(func.count()).select_from(m.MonitorEquipment).where(*filters)) or 0)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {"items": items, "total": total, "limit": limit, "offset": offset},
            }
        )

    @get(
        "/api/energy-carbon/monitor/devices/{device_id:int}",
        operation_id="EnergyOperationsGetMonitorDevice",
    )
    async def get_monitor_device_detail(self, db_session: AsyncSession, device_id: int) -> Response[dict[str, Any]]:
        device = (
            await db_session.execute(
                select(m.MonitorEquipment)
                .options(selectinload(m.MonitorEquipment.sector))
                .where(m.MonitorEquipment.id == device_id)
            )
        ).scalar_one_or_none()
        if device is None:
            return Response(content={"code": 404, "msg": "设备不存在"}, status_code=404)
        meter_samples = list(
            (
                await db_session.execute(
                    select(m.MeterReadingFact)
                    .where(m.MeterReadingFact.equipment_id == device_id)
                    .order_by(m.MeterReadingFact.reading_time.desc().nullslast(), m.MeterReadingFact.id.desc())
                    .limit(12)
                )
            )
            .scalars()
            .all()
        )
        alarms = list(
            (
                await db_session.execute(
                    select(m.AlarmEvent)
                    .where(m.AlarmEvent.equipment_id == device_id)
                    .order_by(m.AlarmEvent.event_time.desc().nullslast())
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "device": {
                        "id": device.id,
                        "name": device.name or device.code,
                        "code": device.code,
                        "category": device.category,
                        "status": device.status,
                        "trip_state": device.trip_state,
                        "sector_name": device.sector.name if device.sector else None,
                        "location": device.location,
                        "protocol": device.protocol,
                        "install_time": device.install_time.isoformat() if device.install_time else None,
                    },
                    "meter_samples": [model_to_dict(item) for item in meter_samples],
                    "alerts": [model_to_dict(item) for item in alarms],
                },
            }
        )

    @get(
        "/api/energy-carbon/monitor/devices/{device_id:int}/timeseries",
        operation_id="EnergyOperationsGetMonitorDeviceTimeseries",
    )
    async def get_monitor_device_timeseries(self, db_session: AsyncSession, device_id: int) -> Response[dict[str, Any]]:
        samples = list(
            (
                await db_session.execute(
                    select(m.MeterReadingFact)
                    .where(
                        m.MeterReadingFact.equipment_id == device_id,
                        m.MeterReadingFact.point_code == "forward_active_total",
                        m.MeterReadingFact.value_kind == "register_index",
                    )
                    .order_by(m.MeterReadingFact.reading_time.asc().nullslast(), m.MeterReadingFact.id.asc())
                    .limit(48)
                )
            )
            .scalars()
            .all()
        )
        series = [
            {
                "period": item.reading_time.strftime("%m-%d %H:%M") if item.reading_time else f"样本{index + 1}",
                "energy_kwh": float(item.normalized_value or 0),
                "carbon_co2e": 0.0,
            }
            for index, item in enumerate(samples)
        ]
        return Response(content={"code": 200, "msg": "获取成功", "data": {"series": series}})

    @get(
        "/api/energy-carbon/monitor/devices/{device_id:int}/alerts",
        operation_id="EnergyOperationsGetMonitorDeviceAlerts",
    )
    async def get_monitor_device_alerts(self, db_session: AsyncSession, device_id: int) -> Response[dict[str, Any]]:
        alarms = list(
            (
                await db_session.execute(
                    select(m.AlarmEvent)
                    .where(m.AlarmEvent.equipment_id == device_id)
                    .order_by(m.AlarmEvent.event_time.desc().nullslast())
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )
        return Response(
            content={"code": 200, "msg": "获取成功", "data": {"items": [model_to_dict(item) for item in alarms]}}
        )

    @get(
        "/api/energy-carbon/monitor/devices/{device_id:int}/videos",
        operation_id="EnergyOperationsGetMonitorDeviceVideos",
    )
    async def get_monitor_device_videos(self, db_session: AsyncSession, device_id: int) -> Response[dict[str, Any]]:
        device = await db_session.scalar(select(m.MonitorEquipment).where(m.MonitorEquipment.id == device_id))
        if device is None or device.sector_id is None:
            return Response(content={"code": 200, "msg": "获取成功", "data": {"items": []}})
        sector_name = await db_session.scalar(
            select(m.MonitorSector.name).where(m.MonitorSector.id == device.sector_id)
        )
        if not sector_name:
            return Response(content={"code": 200, "msg": "获取成功", "data": {"items": []}})
        videos = list(
            (await db_session.execute(select(m.VideoMonitor).where(m.VideoMonitor.f_area == sector_name).limit(8)))
            .scalars()
            .all()
        )
        return Response(
            content={"code": 200, "msg": "获取成功", "data": {"items": [model_to_dict(item) for item in videos]}}
        )

    @get("/api/energy-carbon/alerts", operation_id="EnergyOperationsListAlerts")
    async def list_alerts(
        self,
        db_session: AsyncSession,
        source: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict[str, Any]]:
        items = await self._alerts(db_session)
        if source and source != "all":
            items = [item for item in items if item["source"] == source]
        if status and status != "all":
            items = [item for item in items if item["status"] == status]
        if severity and severity != "all":
            items = [item for item in items if item["severity"] == severity]
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "items": items[offset : offset + limit],
                    "total": len(items),
                    "limit": limit,
                    "offset": offset,
                },
            }
        )

    @get("/api/energy-carbon/alerts/summary", operation_id="EnergyOperationsGetAlertSummary")
    async def get_alert_summary(self, db_session: AsyncSession) -> Response[dict[str, Any]]:
        items = await self._alerts(db_session)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "total": len(items),
                    "unhandled": sum(1 for item in items if item["status"] == "待处理"),
                    "high_risk": sum(1 for item in items if item["severity"] == "high"),
                    "today_added": sum(
                        1
                        for item in items
                        if str(item.get("occurred_at") or "").startswith(
                            datetime.datetime.now(tz=datetime.UTC).date().isoformat()
                        )
                    ),
                    "avg_handle_hours": None,
                    **self._alert_facets(items),
                },
            }
        )

    @get("/api/energy-carbon/alerts/facets", operation_id="EnergyOperationsGetAlertFacets")
    async def get_alert_facets(self, db_session: AsyncSession) -> Response[dict[str, Any]]:
        items = await self._alerts(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": self._alert_facets(items)})

    @get("/api/energy-carbon/alerts/trend", operation_id="EnergyOperationsGetAlertTrend")
    async def get_alert_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict[str, Any]]:
        items = await self._alerts(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"series": self._alert_trend(items, months)}})

    @get("/api/energy-carbon/alerts/{alert_id:str}", operation_id="EnergyOperationsGetAlert")
    async def get_alert(self, db_session: AsyncSession, alert_id: str) -> Response[dict[str, Any]]:
        match = next((item for item in await self._alerts(db_session) if item["id"] == alert_id), None)
        if match is None:
            return Response(content={"code": 404, "msg": "告警不存在"}, status_code=404)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    **match,
                    "history": [
                        {"label": "发生", "value": match.get("occurred_at")},
                        {"label": "当前状态", "value": match.get("status")},
                        {"label": "风险等级", "value": match.get("severity")},
                    ],
                },
            }
        )

    @get(
        "/api/energy-carbon/alerts/{alert_id:str}/history",
        operation_id="EnergyOperationsGetAlertHistory",
    )
    async def get_alert_history(self, db_session: AsyncSession, alert_id: str) -> Response[dict[str, Any]]:
        match = next((item for item in await self._alerts(db_session) if item["id"] == alert_id), None)
        if match is None:
            return Response(content={"code": 404, "msg": "告警不存在"}, status_code=404)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {"items": [{"stage": "发现", "time": match.get("occurred_at"), "status": match.get("status")}]},
            }
        )
