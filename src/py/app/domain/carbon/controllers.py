"""Carbon domain controllers for data collection, alarms, ledgers, and audit flows."""

import datetime
import re
from collections import defaultdict
from contextlib import suppress
from decimal import Decimal
from typing import Any

from advanced_alchemy.filters import LimitOffset, OrderBy, SearchFilter
from litestar import Controller, Request, delete, get, patch, post
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m
from app.domain.accounts.guards import requires_superuser
from app.domain.admin.deps import provide_audit_log_service
from app.domain.admin.services import AuditLogService
from app.domain.carbon import services
from app.domain.carbon.deps import (
    provide_alarm_event_service,
    provide_api_result_key_mapping_service,
    provide_area_service,
    provide_device_point_service,
    provide_device_service,
    provide_device_type_service,
    provide_employee_commute_service,
    provide_energy_storage_value_service,
    provide_in_money_service,
    provide_monitor_equipment_service,
    provide_monitor_sector_photo_service,
    provide_monitor_sector_service,
    provide_out_money_service,
    provide_vedio_alarm_event_service,
    provide_video_monitor_service,
    provide_warning_rule_service,
)
from app.domain.carbon.validation import (
    CarbonValidationError,
    validate_amount_non_negative,
)
from app.lib.tenancy import session_tenant_id

JSON_BODY = Body()
DEVICE_TYPE_ID_TO_CODE = {
    1: "meter",
    2: "pv_inverter",
    3: "storage_bms",
    4: "charger",
    5: "forklift",
    6: "crane",
    7: "weighbridge",
    8: "automation_equipment",
    9: "camera",
}
DEVICE_TYPE_CODE_TO_ID = {code: identifier for identifier, code in DEVICE_TYPE_ID_TO_CODE.items()}
CATEGORY_TO_DEVICE_TYPE_ID = {
    0: DEVICE_TYPE_CODE_TO_ID["meter"],
    1: DEVICE_TYPE_CODE_TO_ID["pv_inverter"],
    2: DEVICE_TYPE_CODE_TO_ID["camera"],
}
DEVICE_TYPE_ID_TO_CATEGORY = {value: key for key, value in CATEGORY_TO_DEVICE_TYPE_ID.items()}
ROOT_AREA_CODE = "ROOT"
AREA_TYPE_OPTIONS = {"site", "building", "workshop", "warehouse", "zone", "line", "station", "utility", "other"}
DEFAULT_DEVICE_POINT_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "meter": [
        {
            "point_code": "active_power",
            "point_name": "有功功率",
            "unit": "kW",
            "value_type": "float",
            "source_field": "active_power",
            "is_alarm_enabled": True,
        },
        {
            "point_code": "voltage_a",
            "point_name": "A相电压",
            "unit": "V",
            "value_type": "float",
            "source_field": "voltage_a",
        },
        {
            "point_code": "current_a",
            "point_name": "A相电流",
            "unit": "A",
            "value_type": "float",
            "source_field": "current_a",
        },
        {
            "point_code": "total_energy",
            "point_name": "累计电量",
            "unit": "kWh",
            "value_type": "float",
            "source_field": "total_energy",
        },
    ],
    "pv_inverter": [
        {
            "point_code": "power_kw",
            "point_name": "发电功率",
            "unit": "kW",
            "value_type": "float",
            "source_field": "power_kw",
            "is_alarm_enabled": True,
        },
        {
            "point_code": "daily_energy_kwh",
            "point_name": "日发电量",
            "unit": "kWh",
            "value_type": "float",
            "source_field": "daily_energy_kwh",
        },
        {
            "point_code": "cumulative_energy_kwh",
            "point_name": "累计发电量",
            "unit": "kWh",
            "value_type": "float",
            "source_field": "cumulative_energy_kwh",
        },
    ],
    "storage_bms": [
        {
            "point_code": "soc",
            "point_name": "SOC",
            "unit": "%",
            "value_type": "float",
            "source_field": "soc",
            "is_alarm_enabled": True,
        },
        {"point_code": "soh", "point_name": "SOH", "unit": "%", "value_type": "float", "source_field": "soh"},
        {
            "point_code": "charge_power_kw",
            "point_name": "充电功率",
            "unit": "kW",
            "value_type": "float",
            "source_field": "charge_power_kw",
        },
        {
            "point_code": "discharge_power_kw",
            "point_name": "放电功率",
            "unit": "kW",
            "value_type": "float",
            "source_field": "discharge_power_kw",
        },
        {
            "point_code": "temperature_c",
            "point_name": "温度",
            "unit": "℃",
            "value_type": "float",
            "source_field": "temperature_c",
        },
    ],
    "charger": [
        {
            "point_code": "status",
            "point_name": "充电状态",
            "unit": None,
            "value_type": "enum",
            "source_field": "status",
            "is_alarm_enabled": True,
        },
        {
            "point_code": "power_kw",
            "point_name": "充电功率",
            "unit": "kW",
            "value_type": "float",
            "source_field": "power_kw",
        },
        {
            "point_code": "session_energy_kwh",
            "point_name": "本次充电量",
            "unit": "kWh",
            "value_type": "float",
            "source_field": "session_energy_kwh",
        },
        {
            "point_code": "cumulative_energy_kwh",
            "point_name": "累计充电量",
            "unit": "kWh",
            "value_type": "float",
            "source_field": "cumulative_energy_kwh",
        },
    ],
}
DEFAULT_DEVICE_TYPES: tuple[dict[str, Any], ...] = (
    {
        "id": 1,
        "code": "meter",
        "name": "电表",
        "energy_type": "electricity",
        "is_energy_device": True,
        "default_protocol": "http_yunji",
    },
    {
        "id": 2,
        "code": "pv_inverter",
        "name": "光伏逆变器",
        "energy_type": "electricity",
        "is_energy_device": True,
        "default_protocol": "mqtt",
    },
    {
        "id": 3,
        "code": "storage_bms",
        "name": "储能 BMS",
        "energy_type": "electricity",
        "is_energy_device": True,
        "default_protocol": "mqtt",
    },
    {
        "id": 4,
        "code": "charger",
        "name": "充电桩",
        "energy_type": "electricity",
        "is_energy_device": True,
        "default_protocol": "mqtt",
    },
    {"id": 5, "code": "forklift", "name": "叉车", "energy_type": "diesel", "is_special_equipment": True},
    {"id": 6, "code": "crane", "name": "起重设备", "energy_type": "electricity", "is_special_equipment": True},
    {"id": 7, "code": "weighbridge", "name": "地磅", "energy_type": "electricity", "is_special_equipment": True},
    {"id": 8, "code": "automation_equipment", "name": "自动化设备", "energy_type": "electricity"},
    {"id": 9, "code": "camera", "name": "摄像头", "default_protocol": "rtsp"},
)


def _audit_request_details(request: Request[Any, Any, Any]) -> tuple[str | None, str | None]:
    forwarded_for = request.headers.get("x-forwarded-for")
    ip_address = (
        forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host if request.client else None
    )
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


async def _log_security_audit(
    audit_service: AuditLogService,
    request: Request[Any, Any, Any],
    *,
    action: str,
    target_type: str,
    target_id: str | None = None,
    target_label: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    ip_address, user_agent = _audit_request_details(request)
    await audit_service.log_action(
        action=action,
        actor_id=request.user.id,
        actor_email=request.user.email,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _parse_vedio_event_time(date_string: str | None) -> datetime.datetime | None:
    """解析回调中的日期时间字符串, 如 2023-08-31T17:02:15.080+08:00。"""
    if not date_string:
        return None
    try:
        from dateutil import parser as dateutil_parser

        return dateutil_parser.parse(date_string)
    except (ValueError, OverflowError):
        try:
            return datetime.datetime.fromisoformat(date_string)
        except (ValueError, OverflowError):
            return None


class CarbonEventController(Controller):
    tags = ["CarbonEvent"]
    signature_types = [Response]
    dependencies = {
        "alarm_event_service": provide_alarm_event_service,
        "vedio_alarm_event_service": provide_vedio_alarm_event_service,
        "video_monitor_service": provide_video_monitor_service,
        "security_audit_service": provide_audit_log_service,
    }

    @post(path="/api/zjyj/handleEvents", guards=[requires_superuser])
    async def handle_events_zjyj(
        self,
        request: Request[Any, Any, Any],
        alarm_event_service: services.AlarmEventService,
        security_audit_service: AuditLogService,
        data: dict,
    ) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await alarm_event_service.update_many([{"id": record_id, "is_handle": True} for record_id in ids])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.alarm-event.batch-handle",
            target_type="alarm_event",
            details={"batch_size": len(ids), "query_scope": "zjyj"},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleEvents", guards=[requires_superuser])
    async def handle_events(
        self,
        request: Request[Any, Any, Any],
        alarm_event_service: services.AlarmEventService,
        security_audit_service: AuditLogService,
        data: dict,
    ) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await alarm_event_service.update_many([{"id": record_id, "is_handle": True} for record_id in ids])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.alarm-event.batch-handle",
            target_type="alarm_event",
            details={"batch_size": len(ids)},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/zjyj/handleAllEvents", guards=[requires_superuser])
    async def handle_all_events_zjyj(
        self,
        request: Request[Any, Any, Any],
        alarm_event_service: services.AlarmEventService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        unhandled = await alarm_event_service.list(m.AlarmEvent.is_handle.is_(False))
        if unhandled:
            await alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.alarm-event.handle-all",
            target_type="alarm_event",
            details={"batch_size": len(unhandled), "query_scope": "zjyj"},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleAllEvents", guards=[requires_superuser])
    async def handle_all_events(
        self,
        request: Request[Any, Any, Any],
        alarm_event_service: services.AlarmEventService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        unhandled = await alarm_event_service.list(m.AlarmEvent.is_handle.is_(False))
        if unhandled:
            await alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.alarm-event.handle-all",
            target_type="alarm_event",
            details={"batch_size": len(unhandled)},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/zjyj/handleVideoEvents", guards=[requires_superuser])
    async def handle_video_events_zjyj(
        self,
        request: Request[Any, Any, Any],
        vedio_alarm_event_service: services.VedioAlarmEventService,
        security_audit_service: AuditLogService,
        data: dict,
    ) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await vedio_alarm_event_service.update_many([{"id": record_id, "is_handle": True} for record_id in ids])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.batch-handle",
            target_type="video_alarm_event",
            details={"batch_size": len(ids), "query_scope": "zjyj"},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleVideoEvents", guards=[requires_superuser])
    async def handle_video_events(
        self,
        request: Request[Any, Any, Any],
        vedio_alarm_event_service: services.VedioAlarmEventService,
        security_audit_service: AuditLogService,
        data: dict,
    ) -> Response[dict]:
        ids = data.get("ids", [])
        if ids:
            await vedio_alarm_event_service.update_many([{"id": record_id, "is_handle": True} for record_id in ids])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.batch-handle",
            target_type="video_alarm_event",
            details={"batch_size": len(ids)},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/zjyj/handleAllVideoEvents", guards=[requires_superuser])
    async def handle_all_video_events_zjyj(
        self,
        request: Request[Any, Any, Any],
        vedio_alarm_event_service: services.VedioAlarmEventService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        unhandled = await vedio_alarm_event_service.list(m.VedioAlarmEvent.is_handle.is_(False))
        if unhandled:
            await vedio_alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.handle-all",
            target_type="video_alarm_event",
            details={"batch_size": len(unhandled), "query_scope": "zjyj"},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/handleAllVideoEvents", guards=[requires_superuser])
    async def handle_all_video_events(
        self,
        request: Request[Any, Any, Any],
        vedio_alarm_event_service: services.VedioAlarmEventService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        unhandled = await vedio_alarm_event_service.list(m.VedioAlarmEvent.is_handle.is_(False))
        if unhandled:
            await vedio_alarm_event_service.update_many([{"id": e.id, "is_handle": True} for e in unhandled])
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.handle-all",
            target_type="video_alarm_event",
            details={"batch_size": len(unhandled)},
        )
        return Response(content={"code": 200, "msg": "处理成功"})

    @post(path="/api/pullVedioAlarmEvent", guards=[requires_superuser])
    async def pull_vedio_alarm_event(
        self,
        request: Request[Any, Any, Any],
        data: dict,
        video_monitor_service: services.VideoMonitorService,
        security_audit_service: AuditLogService,
        db_session: AsyncSession,
    ) -> Response[dict]:
        """接收摄像头报警回调, 创建 VedioAlarmEvent。"""
        json_data = data.get("json") or data
        rets: list[m.VedioAlarmEvent] = []
        all_vms = await video_monitor_service.list()
        ip_to_vm: dict[str, Any] = {str(v.ip_address): v for v in all_vms if getattr(v, "ip_address", None)}

        def vm_by_ip(ip: str | None) -> Any:
            return ip_to_vm.get(ip or "") if ip else None

        def make_event(
            event_type: int, event_desc: str, event_time: datetime.datetime | None, ip_addr: str | None
        ) -> m.VedioAlarmEvent:
            vm = vm_by_ip(ip_addr)
            return m.VedioAlarmEvent(
                event_type=event_type,
                event_desc=event_desc,
                event_time=event_time or datetime.datetime.now(datetime.UTC),
                equipment_id=vm.id if vm else None,
                is_handle=False,
            )

        if "params" in json_data and "events" in json_data["params"]:
            for evt in json_data["params"]["events"]:
                evt_data = evt.get("data") or {}
                if evt_data.get("eventType") == "AIOPResultData":
                    event_desc = f"{evt_data.get('channelName', '')} 监控到 【未带安全帽】 事件"
                    event_time = _parse_vedio_event_time(evt_data.get("dateTime"))
                    created = make_event(1, event_desc, event_time, evt_data.get("ipAddress"))
                    db_session.add(created)
                    await db_session.flush()
                    rets.append(created)
                elif evt_data.get("eventType") == "fielddetection":
                    event_desc = f"{evt_data.get('channelName', '')} 监控到 【区域入侵】 事件"
                    event_time = _parse_vedio_event_time(evt_data.get("dateTime"))
                    created = make_event(4, event_desc, event_time, evt_data.get("ipAddress"))
                    db_session.add(created)
                    await db_session.flush()
                    rets.append(created)
        if "eventType" in json_data:
            if json_data["eventType"] == "fireDetection":
                ip_addr = json_data.get("ipAddress")
                vms = [v for v in all_vms if getattr(v, "ip_address", None) == ip_addr]
                loc = vms[0].location if vms else json_data.get("eventDescription", "")
                event_desc = f"{loc} 监控到 【火点】 事件"
                event_time = _parse_vedio_event_time(json_data.get("dateTime"))
                created = make_event(3, event_desc, event_time, ip_addr)
                db_session.add(created)
                await db_session.flush()
                rets.append(created)
            elif json_data["eventType"] == "smokeAndFireDetection":
                ip_addr = json_data.get("ipAddress")
                vms = [v for v in all_vms if getattr(v, "ip_address", None) == ip_addr]
                loc = vms[0].location if vms else json_data.get("eventDescription", "")
                event_desc = f"{loc} 监控到 【烟火】 事件"
                event_time = _parse_vedio_event_time(json_data.get("dateTime"))
                created = make_event(2, event_desc, event_time, ip_addr)
                db_session.add(created)
                await db_session.flush()
                rets.append(created)

        def _serialize(e: m.VedioAlarmEvent) -> dict:
            return {
                "id": e.id,
                "event_type": e.event_type,
                "event_desc": e.event_desc,
                "event_time": e.event_time.isoformat() if e.event_time else None,
                "equipment_id": e.equipment_id,
                "is_handle": e.is_handle,
                "add_time": e.add_time.isoformat() if getattr(e, "add_time", None) else None,
            }

        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.pull",
            target_type="video_alarm_event",
            details={"batch_size": len(rets)},
        )
        return Response(
            content={
                "code": 200,
                "msg": "拉取报警事件成功",
                "data": {"totalCount": len(rets), "alarmEvents": [_serialize(r) for r in rets]},
            }
        )


def model_to_dict(obj: Any) -> dict:
    """将 ORM 对象转为可 JSON 序列化的字典。"""
    if not obj:
        return {}
    import uuid
    from decimal import Decimal

    result = {}
    for c in obj.__table__.columns:
        if c.info.get("private"):
            continue
        val = getattr(obj, c.name)
        # 处理不可直接 JSON 序列化的类型
        if isinstance(val, (datetime.date, datetime.datetime)):
            val = val.isoformat()
        elif isinstance(val, Decimal):
            val = float(val)
        elif isinstance(val, uuid.UUID):
            val = str(val)
        result[c.name] = val
    return result


def _area_label(area: m.MonitorSector | None) -> str | None:
    if area is None:
        return None
    return area.name or area.code


def _serialize_area(
    area: m.MonitorSector,
    *,
    equipment_count: int = 0,
    child_count: int = 0,
    include_parent: bool = False,
) -> dict[str, Any]:
    data = model_to_dict(area)
    data["is_enabled"] = bool(area.is_enable is not False)
    data["remark"] = area.remark or area.description
    data["child_count"] = child_count
    data["equipment_count"] = equipment_count
    if include_parent and area.parent is not None:
        data["parent"] = {"id": area.parent.id, "code": area.parent.code, "name": _area_label(area.parent)}
    return data


def _serialize_device_type(device_type: m.DeviceType, *, child_count: int = 0) -> dict[str, Any]:
    data = model_to_dict(device_type)
    data["child_count"] = child_count
    return data


def _serialize_device(
    device: m.MonitorEquipment,
    *,
    area: m.MonitorSector | None = None,
    device_type: m.DeviceType | None = None,
    parent_device: m.MonitorEquipment | None = None,
    child_device_count: int = 0,
    point_count: int = 0,
) -> dict[str, Any]:
    data = model_to_dict(device)
    resolved_area = area
    resolved_type = device_type
    resolved_parent = parent_device
    data["area_id"] = device.sector_id
    data["area_name"] = _area_label(resolved_area)
    data["is_enabled"] = bool(device.is_enable is not False)
    data["location_desc"] = device.location
    data["owner_department"] = device.owner_unit
    data["parent_device"] = (
        {
            "id": resolved_parent.id,
            "code": resolved_parent.code,
            "name": resolved_parent.name or resolved_parent.code,
        }
        if resolved_parent is not None
        else None
    )
    data["device_type"] = (
        {
            "id": resolved_type.id,
            "code": resolved_type.code,
            "name": resolved_type.name,
        }
        if resolved_type is not None
        else None
    )
    data["area"] = (
        {"id": resolved_area.id, "code": resolved_area.code, "name": _area_label(resolved_area)}
        if resolved_area is not None
        else None
    )
    data["child_device_count"] = child_device_count
    data["point_count"] = point_count
    return data


def _build_tree(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {node["id"]: {**node, "children": []} for node in nodes}
    roots: list[dict[str, Any]] = []
    for node in by_id.values():
        parent_id = node.get("parent_id")
        if parent_id in by_id:
            by_id[parent_id]["children"].append(node)
        else:
            roots.append(node)
    for node in by_id.values():
        node["children"].sort(
            key=lambda item: (item.get("sort_index") or 0, item.get("name") or item.get("code") or "")
        )
    roots.sort(key=lambda item: (item.get("sort_index") or 0, item.get("name") or item.get("code") or ""))
    return roots


async def _ensure_root_area(db_session: AsyncSession) -> m.MonitorSector:
    root = await db_session.scalar(select(m.MonitorSector).where(m.MonitorSector.code == ROOT_AREA_CODE))
    if root is not None:
        return root
    tenant_id = session_tenant_id(db_session)
    root = m.MonitorSector(
        code=ROOT_AREA_CODE,
        name="区域主数据",
        area_type="site",
        path=None,
        level=0,
        sort_index=0,
        description="系统根节点",
        remark="系统自动创建的根区域",
        is_enable=False,
    )
    if tenant_id is not None:
        root.team_id = tenant_id
    db_session.add(root)
    await db_session.flush()
    root.path = f"/{root.id}"
    await db_session.commit()
    await db_session.refresh(root)
    return root


async def _rebuild_area_path(db_session: AsyncSession, area: m.MonitorSector) -> None:
    if area.parent_id is None:
        area.path = f"/{area.id}"
        area.level = 0
        return
    parent = await db_session.get(m.MonitorSector, area.parent_id)
    if parent is None:
        area.parent_id = None
        area.path = f"/{area.id}"
        area.level = 0
        return
    parent_path = parent.path or f"/{parent.id}"
    parent_level = parent.level or 0
    area.path = f"{parent_path}/{area.id}"
    area.level = parent_level + 1


async def _update_area_descendant_paths(db_session: AsyncSession, area: m.MonitorSector) -> None:
    descendants = (
        (
            await db_session.execute(
                select(m.MonitorSector)
                .where(m.MonitorSector.parent_id == area.id)
                .order_by(m.MonitorSector.sort_index.asc(), m.MonitorSector.id.asc())
            )
        )
        .scalars()
        .all()
    )
    for child in descendants:
        await _rebuild_area_path(db_session, child)
        await _update_area_descendant_paths(db_session, child)


async def _is_descendant_area(db_session: AsyncSession, area_id: int, candidate_parent_id: int) -> bool:
    area = await db_session.get(m.MonitorSector, area_id)
    parent = await db_session.get(m.MonitorSector, candidate_parent_id)
    if area is None or parent is None:
        return False
    area_path = area.path or f"/{area.id}"
    parent_path = parent.path or f"/{parent.id}"
    return parent_path.startswith(f"{area_path}/")


async def _get_area_subtree_ids(db_session: AsyncSession, area_id: int) -> list[int]:
    area = await db_session.get(m.MonitorSector, area_id)
    if area is None:
        return []
    path = area.path or f"/{area.id}"
    rows = (
        (await db_session.execute(select(m.MonitorSector.id).where(m.MonitorSector.path.like(f"{path}%"))))
        .scalars()
        .all()
    )
    return [int(item) for item in rows]


async def _get_device_type_subtree_ids(db_session: AsyncSession, device_type_id: int) -> list[int]:
    rows = (
        await db_session.execute(select(m.DeviceType.id, m.DeviceType.parent_id).order_by(m.DeviceType.id.asc()))
    ).all()
    children_by_parent: dict[int | None, list[int]] = defaultdict(list)
    for identifier, parent_id in rows:
        children_by_parent[parent_id].append(identifier)
    queue = [device_type_id]
    seen: set[int] = set()
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        queue.extend(children_by_parent.get(current, []))
    return sorted(seen)


async def _is_descendant_device(db_session: AsyncSession, device_id: int, parent_device_id: int) -> bool:
    current_parent_id = parent_device_id
    seen: set[int] = set()
    while current_parent_id is not None and current_parent_id not in seen:
        if current_parent_id == device_id:
            return True
        seen.add(current_parent_id)
        current_parent_id = await db_session.scalar(
            select(m.MonitorEquipment.parent_device_id).where(m.MonitorEquipment.id == current_parent_id)
        )
    return False


_FACTOR_UNIT_PATTERN = re.compile(
    r"(tC/TJ|TJ/万t|10⁴t|万t|tCO2|tCO₂|tC|kg|CH4|CH₄|CO2|CO₂|N2O|N₂O|%|m3|m³|Gg)", re.IGNORECASE
)


def _looks_like_factor_unit(value: str) -> bool:
    return bool(_FACTOR_UNIT_PATTERN.search(value.strip()))


def _augment_raw_factor_record_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Add display-oriented fields for matrix-style official raw factor records."""
    if data.get("library_code") != "G04":
        data["display_factor_name"] = data.get("factor_name")
        data["display_factor_unit_raw"] = data.get("factor_unit_raw")
        return data

    raw_payload = data.get("raw_payload") if isinstance(data.get("raw_payload"), dict) else {}
    row_cells = raw_payload.get("rowCells") if isinstance(raw_payload, dict) else []
    row_cells = row_cells if isinstance(row_cells, list) else []
    header = raw_payload.get("header") if isinstance(raw_payload, dict) else {}
    header_value = str(header.get("value") or "").strip() if isinstance(header, dict) else ""
    factor_value = str(data.get("factor_value_raw") or "").strip()

    unit = data.get("factor_unit_raw")
    dimensions: list[str] = []
    for cell in row_cells:
        if not isinstance(cell, dict):
            continue
        value = str(cell.get("value") or "").strip()
        value_en = str(cell.get("valueEn") or "").strip()
        for candidate in (value, value_en):
            if candidate and not unit and _looks_like_factor_unit(candidate):
                unit = candidate
        if not value or value == factor_value or _looks_like_factor_unit(value):
            continue
        if value not in dimensions:
            dimensions.append(value)

    if header_value and header_value not in dimensions:
        dimensions.append(header_value)

    if dimensions:
        data["display_factor_name"] = " - ".join(dimensions)
        data["matrix_dimensions"] = dimensions
    else:
        data["display_factor_name"] = re.sub(r"\s*-\s*纵\d+\s*", " - ", str(data.get("factor_name") or "")).strip(" -")
        data["matrix_dimensions"] = []
    data["display_factor_unit_raw"] = unit
    return data


def _payload_without_none(data: dict[str, Any]) -> dict[str, Any]:
    """Drop client-side empty values before writing simple admin records."""
    return {k: v for k, v in data.items() if v is not None}


def _coerce_datetime_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        val = data.get(field)
        if isinstance(val, str) and val:
            with suppress(ValueError):
                data[field] = datetime.datetime.fromisoformat(val)
            if isinstance(data.get(field), str):
                with suppress(ValueError):
                    data[field] = datetime.datetime.combine(datetime.date.fromisoformat(val), datetime.time.min)


def _coerce_int_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        val = data.get(field)
        if isinstance(val, str) and val.strip():
            with suppress(ValueError):
                data[field] = int(val)


def _coerce_float_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        val = data.get(field)
        if isinstance(val, str) and val.strip():
            with suppress(ValueError):
                data[field] = float(val)


def _coerce_decimal_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        val = data.get(field)
        if val in (None, ""):
            continue
        with suppress(ValueError, TypeError):
            data[field] = val if isinstance(val, Decimal) else Decimal(str(val))


def _strip_string_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        val = data.get(field)
        if isinstance(val, str):
            data[field] = val.strip() or None


def _sync_monitor_equipment_type_fields(data: dict[str, Any]) -> None:
    device_type_id = data.get("device_type_id")
    category = data.get("category")
    if isinstance(device_type_id, str) and device_type_id.strip():
        try:
            device_type_id = data["device_type_id"] = int(device_type_id)
        except ValueError:
            device_type_id = None
    if isinstance(category, str) and category.strip():
        try:
            category = data["category"] = int(category)
        except ValueError:
            category = None

    if device_type_id is not None and "category" not in data:
        mapped_category = DEVICE_TYPE_ID_TO_CATEGORY.get(device_type_id)
        if mapped_category is not None:
            data["category"] = mapped_category
    elif category is not None and "device_type_id" not in data:
        mapped_device_type_id = CATEGORY_TO_DEVICE_TYPE_ID.get(category)
        if mapped_device_type_id is not None:
            data["device_type_id"] = mapped_device_type_id


def _sync_monitor_equipment_identifier_fields(data: dict[str, Any]) -> None:
    asset_code = data.get("asset_code")
    external_device_id = data.get("external_device_id")
    code = data.get("code")

    if isinstance(asset_code, str):
        asset_code = asset_code.strip() or None
        data["asset_code"] = asset_code
    if isinstance(external_device_id, str):
        external_device_id = external_device_id.strip() or None
        data["external_device_id"] = external_device_id
    if isinstance(code, str):
        code = code.strip() or None
        data["code"] = code

    if not external_device_id and code:
        data["external_device_id"] = code


def _normalize_area_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data)
    if "is_enabled" in payload and "is_enable" not in payload:
        payload["is_enable"] = payload.pop("is_enabled")
    else:
        payload.pop("is_enabled", None)
    if "remark" in payload and "description" not in payload:
        payload["description"] = payload["remark"]
    payload["remark"] = payload.get("remark") or payload.get("description")
    if "area_type" in payload and isinstance(payload["area_type"], str):
        area_type = payload["area_type"].strip().lower()
        payload["area_type"] = area_type if area_type in AREA_TYPE_OPTIONS else "other"
    _coerce_int_fields(payload, ["parent_id", "level", "sort_index", "area_id"])
    return payload


def _normalize_device_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data)
    if "area_id" in payload and "sector_id" not in payload:
        payload["sector_id"] = payload["area_id"]
    payload.pop("area_id", None)
    if "location_desc" in payload and "location" not in payload:
        payload["location"] = payload["location_desc"]
    payload.pop("location_desc", None)
    if "owner_department" in payload and "owner_unit" not in payload:
        payload["owner_unit"] = payload["owner_department"]
    payload.pop("owner_department", None)
    if "is_enabled" in payload and "is_enable" not in payload:
        payload["is_enable"] = payload["is_enabled"]
    payload.pop("is_enabled", None)
    _coerce_datetime_fields(payload, ["install_time", "last_inspection_at", "inspection_due_at"])
    _coerce_int_fields(payload, ["sector_id", "device_type_id", "category", "sort_index", "parent_device_id"])
    _coerce_float_fields(payload, ["rated_power_kw"])
    _sync_monitor_equipment_type_fields(payload)
    _sync_monitor_equipment_identifier_fields(payload)
    return payload


async def _ensure_default_device_points(db_session: AsyncSession, equipment: m.MonitorEquipment) -> None:
    device_type_id = equipment.device_type_id
    if device_type_id is None:
        return
    device_type_code = DEVICE_TYPE_ID_TO_CODE.get(device_type_id)
    if not device_type_code:
        return
    templates = DEFAULT_DEVICE_POINT_TEMPLATES.get(device_type_code)
    if not templates:
        return

    existing_codes = {
        row[0]
        for row in (
            await db_session.execute(select(m.DevicePoint.point_code).where(m.DevicePoint.device_id == equipment.id))
        ).all()
    }
    for template in templates:
        if template["point_code"] in existing_codes:
            continue
        db_session.add(
            m.DevicePoint(
                device_id=equipment.id,
                point_code=template["point_code"],
                point_name=template["point_name"],
                unit=template["unit"],
                value_type=template["value_type"],
                source_field=template["source_field"],
                sampling_interval_seconds=300,
                is_enabled=True,
                is_alarm_enabled=template.get("is_alarm_enabled", False),
            )
        )


async def _ensure_default_device_types(db_session: AsyncSession) -> None:
    existing_rows = (await db_session.execute(select(m.DeviceType.id, m.DeviceType.code))).all()
    existing_codes = {code for _identifier, code in existing_rows}
    existing_ids = {int(identifier) for identifier, _code in existing_rows}
    missing = [item for item in DEFAULT_DEVICE_TYPES if item["code"] not in existing_codes]
    if not missing:
        return
    next_id = max(existing_ids, default=0) + 1
    for item in missing:
        payload = dict(item)
        payload_id = int(payload["id"])
        if payload_id in existing_ids:
            payload["id"] = next_id
            next_id += 1
        existing_ids.add(int(payload["id"]))
        db_session.add(m.DeviceType(**payload))
    await db_session.commit()


def _matches_keyword(row: dict[str, Any], keyword: str | None, fields: list[str]) -> bool:
    if not keyword:
        return True
    needle = keyword.strip().lower()
    if not needle:
        return True
    return any(needle in str(row.get(field) or "").lower() for field in fields)


def _slice_rows(rows: list[dict[str, Any]], limit: int = 200, offset: int = 0) -> dict[str, Any]:
    limit_clamped = max(10, min(limit, 1000))
    offset_clamped = max(0, offset)
    return {
        "items": rows[offset_clamped : offset_clamped + limit_clamped],
        "total": len(rows),
        "limit": limit_clamped,
        "offset": offset_clamped,
    }


def _paged_payload(items: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": limit, "offset": offset, "code": 200, "data": items}


def _jsonable_mapping(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (datetime.date, datetime.datetime)):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


def _build_list_filters(
    model: Any,
    *,
    limit: int,
    offset: int,
    search: str | None,
    keyword: str | None,
    search_fields: list[str] | None,
    sort_field: str,
    sort_order: str,
) -> tuple[list[Any], int, int]:
    limit_clamped = max(1, min(limit, 100))
    offset_clamped = max(0, offset)
    filters: list[Any] = [LimitOffset(limit_clamped, offset_clamped)]
    order = "asc" if sort_order == "asc" else "desc"
    if sort_field and hasattr(model, sort_field):
        filters.append(OrderBy(getattr(model, sort_field), order))
    search_value = (search or keyword or "").strip()
    if search_value and search_fields:
        filters.append(SearchFilter(field_name=set(search_fields), value=search_value, ignore_case=True))
    return filters, limit_clamped, offset_clamped


async def _list_page(
    service: Any,
    model: Any,
    *,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
    keyword: str | None = None,
    search_fields: list[str] | None = None,
    sort_field: str = "id",
    sort_order: str = "desc",
    conditions: list[Any] | None = None,
) -> dict[str, Any]:
    filters, limit_clamped, offset_clamped = _build_list_filters(
        model,
        limit=limit,
        offset=offset,
        search=search,
        keyword=keyword,
        search_fields=search_fields,
        sort_field=sort_field,
        sort_order=sort_order,
    )
    rows, total = await service.list_and_count(*(conditions or []), *filters)
    return _paged_payload([model_to_dict(row) for row in rows], total, limit_clamped, offset_clamped)


async def _list_rows(
    service: Any,
    model: Any,
    *,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
    keyword: str | None = None,
    search_fields: list[str] | None = None,
    sort_field: str = "id",
    sort_order: str = "desc",
    conditions: list[Any] | None = None,
) -> list[Any]:
    filters, _, _ = _build_list_filters(
        model,
        limit=limit,
        offset=offset,
        search=search,
        keyword=keyword,
        search_fields=search_fields,
        sort_field=sort_field,
        sort_order=sort_order,
    )
    return await service.list(*(conditions or []), *filters)


class CarbonCRUDController(Controller):
    """Operational finance and employee-commute master data."""

    tags = ["Operational Data"]
    signature_types = [Response]
    dependencies = {
        "employee_commute_service": provide_employee_commute_service,
        "area_service": provide_area_service,
        "device_service": provide_device_service,
        "monitor_sector_service": provide_monitor_sector_service,
        "monitor_sector_photo_service": provide_monitor_sector_photo_service,
        "monitor_equipment_service": provide_monitor_equipment_service,
        "device_type_service": provide_device_type_service,
        "device_point_service": provide_device_point_service,
        "video_monitor_service": provide_video_monitor_service,
        "warning_rule_service": provide_warning_rule_service,
        "alarm_event_service": provide_alarm_event_service,
        "vedio_alarm_event_service": provide_vedio_alarm_event_service,
        "api_result_key_mapping_service": provide_api_result_key_mapping_service,
        "energy_storage_value_service": provide_energy_storage_value_service,
        "in_money_service": provide_in_money_service,
        "out_money_service": provide_out_money_service,
        "security_audit_service": provide_audit_log_service,
    }

    async def _log_admin_data_event(
        self,
        security_audit_service: AuditLogService,
        request: Request[Any, Any, Any],
        *,
        action: str,
        target_type: str,
        target_id: int | str | None = None,
        target_label: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        payload = dict(details or {})
        payload.setdefault("target_type", target_type)
        if target_id is not None:
            payload.setdefault("target_id", target_id)
        await _log_security_audit(
            security_audit_service,
            request,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            target_label=target_label,
            details=payload,
        )

    @get("/api/data/in-money")
    async def list_in_money(
        self,
        in_money_service: services.InMoneyService,
        keyword: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "add_time",
        sort_order: str = "desc",
    ) -> Response[dict]:
        page = await _list_page(
            in_money_service,
            m.InMoney,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["rkdbh", "gysmc", "gysbm", "wlbh", "wlms", "ckmc"],
            sort_field=sort_field,
            sort_order=sort_order,
        )
        return Response(content=page)

    @get("/api/data/out-money")
    async def list_out_money(
        self,
        out_money_service: services.OutMoneyService,
        keyword: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "add_time",
        sort_order: str = "desc",
    ) -> Response[dict]:
        page = await _list_page(
            out_money_service,
            m.OutMoney,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["ckdbh", "xmmc", "wlbm", "wlms", "gysmc", "ckdd"],
            sort_field=sort_field,
            sort_order=sort_order,
        )
        return Response(content=page)

    # Employee commute master data.
    @get("/api/data/employee-commute")
    async def list_employee_commute(
        self,
        employee_commute_service: services.EmployeeCommuteService,
        keyword: str | None = None,
        search: str | None = None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        """List employee commute records."""
        conditions = [m.EmployeeCommute.category == category] if category else []
        page = await _list_page(
            employee_commute_service,
            m.EmployeeCommute,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["name", "category"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/data/employee-commute", guards=[requires_superuser])
    async def create_employee_commute(
        self,
        request: Request[Any, Any, Any],
        employee_commute_service: services.EmployeeCommuteService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = JSON_BODY,
    ) -> Response[dict]:
        """新增员工通勤记录。"""
        # mileage / unit_consumption 若传入则要求非负
        try:
            if "mileage" in data and data["mileage"] is not None:
                validate_amount_non_negative(data["mileage"], "里程")
            if "unit_consumption" in data and data["unit_consumption"] is not None:
                validate_amount_non_negative(data["unit_consumption"], "单位油耗")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)

        payload = {k: v for k, v in data.items() if v is not None}
        obj = await employee_commute_service.create(payload, auto_commit=True)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.employee-commute.create",
            target_type="EmployeeCommute",
            target_id=obj.id,
            target_label=obj.name,
            details={"category": obj.category},
        )
        return Response(content={"code": 200, "data": model_to_dict(obj), "msg": "创建成功"})

    @patch("/api/data/employee-commute/{record_id:int}", guards=[requires_superuser])
    async def update_employee_commute(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        employee_commute_service: services.EmployeeCommuteService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = JSON_BODY,
    ) -> Response[dict]:
        """更新员工通勤记录。"""
        obj = await employee_commute_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)

        try:
            if "mileage" in data and data["mileage"] is not None:
                validate_amount_non_negative(data["mileage"], "里程")
            if "unit_consumption" in data and data["unit_consumption"] is not None:
                validate_amount_non_negative(data["unit_consumption"], "单位油耗")
        except CarbonValidationError as e:
            return Response(content={"code": 400, "msg": str(e)}, status_code=400)

        await employee_commute_service.update(item_id=record_id, data=data, auto_commit=True)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.employee-commute.update",
            target_type="EmployeeCommute",
            target_id=record_id,
            target_label=obj.name,
            details={"updated_fields": sorted(data.keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/employee-commute/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_employee_commute(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        employee_commute_service: services.EmployeeCommuteService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        """删除员工通勤记录。"""
        obj = await employee_commute_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await employee_commute_service.delete(record_id, auto_commit=True)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.employee-commute.delete",
            target_type="EmployeeCommute",
            target_id=record_id,
            target_label=obj.name,
            details={"category": obj.category},
        )
        return Response(content={"code": 200, "msg": "已删除"})
