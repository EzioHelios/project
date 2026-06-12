from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, Request, get, patch, post
from litestar.params import Body
from litestar.response import Response

from app.db import models as m
from app.domain.accounts.guards import requires_superuser
from app.domain.admin.deps import provide_audit_log_service
from app.domain.admin.services import AuditLogService  # noqa: TC001
from app.domain.carbon import services  # noqa: TC001
from app.domain.carbon.controllers import (
    _coerce_datetime_fields,
    _coerce_float_fields,
    _coerce_int_fields,
    _list_page,
    _payload_without_none,
)
from app.domain.carbon.deps import provide_alarm_event_service, provide_vedio_alarm_event_service
from app.domain.metering.usecases import AlarmHandlingUseCase
from app.domain.production_denominator.controllers._utils import log_admin_data_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


ADMIN_BODY = Body()
ADMIN_OPTIONAL_BODY = Body(default={})


class MeteringAlarmController(Controller):
    tags = ["Metering"]
    dependencies = {
        "alarm_event_service": provide_alarm_event_service,
        "vedio_alarm_event_service": provide_vedio_alarm_event_service,
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
        await log_admin_data_event(
            security_audit_service,
            request,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
            details=details,
        )

    @get("/api/data/alarm-events")
    async def list_alarm_events(
        self,
        alarm_event_service: services.AlarmEventService,
        keyword: str | None = None,
        search: str | None = None,
        event_type: int | None = None,
        is_handle: bool | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "event_time",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if event_type is not None:
            conditions.append(m.AlarmEvent.event_type == event_type)
        if is_handle is not None:
            conditions.append(m.AlarmEvent.is_handle == is_handle)
        if status:
            conditions.append(m.AlarmEvent.status == status)
        page = await _list_page(
            alarm_event_service,
            m.AlarmEvent,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["event_desc", "alarm_code", "alarm_name", "point_code", "status"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @patch("/api/data/alarm-events/{record_id:int}", guards=[requires_superuser])
    async def update_alarm_event(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        _coerce_datetime_fields(data, ["event_time", "resolved_at"])
        _coerce_int_fields(data, ["event_type", "sector_id", "equipment_id"])
        _coerce_float_fields(data, ["current_value", "threshold_value"])
        payload = _payload_without_none(data)
        obj = await AlarmHandlingUseCase(db_session).update_alarm_event(record_id, payload)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.alarm-event.update",
            target_type="AlarmEvent",
            target_id=obj.id,
            target_label=obj.alarm_name,
            details={"updated_fields": sorted(payload.keys()), "status": obj.status},
        )
        return Response(content={"code": 200, "msg": "更新成功"})

    @post("/api/data/alarm-events/{record_id:int}/handle", guards=[requires_superuser])
    async def handle_alarm_event(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await AlarmHandlingUseCase(db_session).handle_alarm_event(record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.alarm-event.handle",
            target_type="AlarmEvent",
            target_id=obj.id,
            target_label=obj.alarm_name,
            details={"status": obj.status},
        )
        return Response(content={"code": 200, "msg": "已处理"})

    @post("/api/data/alarm-events/handle-batch", guards=[requires_superuser])
    async def handle_alarm_events_batch(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_OPTIONAL_BODY,
    ) -> Response[dict]:
        ids = data.get("ids") or []
        items = await AlarmHandlingUseCase(db_session).handle_alarm_events_batch(ids)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.alarm-event.batch-handle",
            target_type="AlarmEvent",
            details={"count": len(items), "ids": ids},
        )
        return Response(content={"code": 200, "msg": "已批量处理", "data": {"count": len(items)}})

    @get("/api/data/video-alarm-events")
    async def list_video_alarm_events(
        self,
        vedio_alarm_event_service: services.VedioAlarmEventService,
        keyword: str | None = None,
        search: str | None = None,
        event_type: int | None = None,
        is_handle: bool | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "event_time",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if event_type is not None:
            conditions.append(m.VedioAlarmEvent.event_type == event_type)
        if is_handle is not None:
            conditions.append(m.VedioAlarmEvent.is_handle == is_handle)
        page = await _list_page(
            vedio_alarm_event_service,
            m.VedioAlarmEvent,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["event_desc"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/data/video-alarm-events/{record_id:int}/handle", guards=[requires_superuser])
    async def handle_video_alarm_event(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await AlarmHandlingUseCase(db_session).handle_video_alarm_event(record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.handle",
            target_type="VedioAlarmEvent",
            target_id=obj.id,
            details={"is_handle": obj.is_handle},
        )
        return Response(content={"code": 200, "msg": "已处理"})

    @post("/api/data/video-alarm-events/handle-batch", guards=[requires_superuser])
    async def handle_video_alarm_events_batch(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_OPTIONAL_BODY,
    ) -> Response[dict]:
        ids = data.get("ids") or []
        items = await AlarmHandlingUseCase(db_session).handle_video_alarm_events_batch(ids)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.video-alarm-event.batch-handle",
            target_type="VedioAlarmEvent",
            details={"count": len(items), "ids": ids},
        )
        return Response(content={"code": 200, "msg": "已批量处理", "data": {"count": len(items)}})

