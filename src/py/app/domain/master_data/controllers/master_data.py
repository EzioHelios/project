# ruff: noqa: RUF001
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, Request, delete, get, patch, post
from litestar.exceptions import ClientException
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import selectinload

from app.db import models as m
from app.domain.accounts.guards import requires_superuser
from app.domain.admin.deps import provide_audit_log_service
from app.domain.admin.services import AuditLogService  # noqa: TC001
from app.domain.carbon import services  # noqa: TC001
from app.domain.carbon.controllers import (
    ROOT_AREA_CODE,
    _area_label,
    _build_tree,
    _coerce_float_fields,
    _coerce_int_fields,
    _ensure_default_device_points,
    _ensure_default_device_types,
    _ensure_root_area,
    _get_area_subtree_ids,
    _get_device_type_subtree_ids,
    _is_descendant_area,
    _is_descendant_device,
    _list_page,
    _normalize_area_payload,
    _normalize_device_payload,
    _payload_without_none,
    _rebuild_area_path,
    _serialize_area,
    _serialize_device,
    _serialize_device_type,
    _update_area_descendant_paths,
    model_to_dict,
)
from app.domain.carbon.deps import (
    provide_api_result_key_mapping_service,
    provide_area_service,
    provide_device_point_service,
    provide_device_service,
    provide_device_type_service,
    provide_video_monitor_service,
    provide_warning_rule_service,
)
from app.domain.production_denominator.controllers._utils import log_admin_data_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


ADMIN_BODY = Body()

VISION_PRIVATE_FIELDS = {"recognition_config", "recognition_state", "recognition_preview"}


def _camera_payload(data: dict[str, Any]) -> dict[str, Any]:
    if VISION_PRIVATE_FIELDS.intersection(data):
        raise ClientException(detail="请通过识别配置维护识别参数")
    return _payload_without_none(data)


class MasterDataController(Controller):
    tags = ["Master Data"]
    dependencies = {
        "area_service": provide_area_service,
        "device_service": provide_device_service,
        "device_type_service": provide_device_type_service,
        "device_point_service": provide_device_point_service,
        "warning_rule_service": provide_warning_rule_service,
        "video_monitor_service": provide_video_monitor_service,
        "api_result_key_mapping_service": provide_api_result_key_mapping_service,
        "security_audit_service": provide_audit_log_service,
    }

    @get("/api/master-data/enterprise-profile")
    async def get_enterprise_profile(self, db_session: AsyncSession) -> Response[dict]:
        row = await db_session.scalar(select(m.EnterpriseInfo).order_by(m.EnterpriseInfo.id.desc()).limit(1))
        return Response(content={"code": 200, "msg": "获取成功", "data": model_to_dict(row) if row else {}})

    @get("/api/master-data/import-workbooks/template", guards=[requires_superuser])
    async def download_master_data_import_template(self) -> Response[bytes]:
        from app.domain.master_data.import_workbook import build_master_data_template_bytes

        return Response(
            content=build_master_data_template_bytes(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="energy-metering-master-data-template.xlsx"'},
        )

    @post("/api/master-data/import-workbooks/preview", guards=[requires_superuser], status_code=200)
    async def preview_master_data_import_workbook(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        from app.domain.master_data.import_workbook import preview_master_data_workbook

        workbook_base64 = str(data.get("workbook_base64") or "")
        if not workbook_base64:
            raise ClientException(detail="缺少 workbook_base64", status_code=400)
        try:
            preview = await preview_master_data_workbook(db_session, workbook_base64)
        except ValueError as exc:
            raise ClientException(detail=str(exc), status_code=400) from exc
        return Response(content={"code": 200, "msg": "预览成功", "data": preview})

    @post("/api/master-data/import-workbooks/import", guards=[requires_superuser])
    async def import_master_data_import_workbook(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        from app.domain.master_data.import_workbook import import_master_data_workbook

        workbook_base64 = str(data.get("workbook_base64") or "")
        if not workbook_base64:
            raise ClientException(detail="缺少 workbook_base64", status_code=400)
        try:
            result = await import_master_data_workbook(db_session, workbook_base64)
        except ValueError as exc:
            raise ClientException(detail=str(exc), status_code=400) from exc
        return Response(content={"code": 200, "msg": "导入成功", "data": result})

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

    @get("/api/master-data/areas/tree")
    async def list_master_data_area_tree(
        self,
        db_session: AsyncSession,
        area_service: services.AreaService,
        include_disabled: bool = True,
    ) -> Response[dict]:
        root = await _ensure_root_area(db_session)
        conditions = []
        if not include_disabled:
            conditions.append(m.MonitorSector.is_enable.is_(True))
        rows = (
            (
                await db_session.execute(
                    select(m.MonitorSector)
                    .where(*(conditions or [text("1=1")]))
                    .order_by(m.MonitorSector.level.asc(), m.MonitorSector.sort_index.asc(), m.MonitorSector.id.asc())
                )
            )
            .scalars()
            .all()
        )
        sector_ids = [row.id for row in rows]
        child_counts = dict(
            (
                await db_session.execute(
                    select(m.MonitorSector.parent_id, func.count(m.MonitorSector.id))
                    .where(m.MonitorSector.parent_id.is_not(None))
                    .group_by(m.MonitorSector.parent_id)
                )
            ).all()
        )
        equipment_counts = {}
        if sector_ids:
            equipment_counts = dict(
                (
                    await db_session.execute(
                        select(m.MonitorEquipment.sector_id, func.count(m.MonitorEquipment.id))
                        .where(m.MonitorEquipment.sector_id.in_(sector_ids))
                        .group_by(m.MonitorEquipment.sector_id)
                    )
                ).all()
            )
        items = [
            _serialize_area(
                row,
                equipment_count=int(equipment_counts.get(row.id, 0)),
                child_count=int(child_counts.get(row.id, 0)),
            )
            for row in rows
        ]
        tree = _build_tree(items)
        selected_root = next((node for node in tree if node["id"] == root.id), None)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": tree, "root": selected_root}})

    @get("/api/master-data/areas")
    async def list_master_data_areas(
        self,
        db_session: AsyncSession,
        area_service: services.AreaService,
        keyword: str | None = None,
        search: str | None = None,
        parent_id: int | None = None,
        area_type: str | None = None,
        is_enabled: bool | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "sort_index",
        sort_order: str = "asc",
    ) -> Response[dict]:
        conditions = []
        if parent_id is not None:
            conditions.append(m.MonitorSector.parent_id == parent_id)
        if area_type:
            conditions.append(m.MonitorSector.area_type == area_type.strip().lower())
        if is_enabled is not None:
            conditions.append(m.MonitorSector.is_enable.is_(is_enabled))
        page = await _list_page(
            area_service,
            m.MonitorSector,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["code", "name", "description", "manager_name", "owner_department", "location_desc"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        area_ids = [row["id"] for row in page["items"] if row.get("id") is not None]
        child_counts = {}
        equipment_counts = {}
        if area_ids:
            child_counts = dict(
                (
                    await db_session.execute(
                        select(m.MonitorSector.parent_id, func.count(m.MonitorSector.id))
                        .where(m.MonitorSector.parent_id.in_(area_ids))
                        .group_by(m.MonitorSector.parent_id)
                    )
                ).all()
            )
            equipment_counts = dict(
                (
                    await db_session.execute(
                        select(m.MonitorEquipment.sector_id, func.count(m.MonitorEquipment.id))
                        .where(m.MonitorEquipment.sector_id.in_(area_ids))
                        .group_by(m.MonitorEquipment.sector_id)
                    )
                ).all()
            )
        for row in page["items"]:
            row["is_enabled"] = row.get("is_enable", True)
            row["remark"] = row.get("remark") or row.get("description")
            row["child_count"] = int(child_counts.get(row.get("id"), 0))
            row["equipment_count"] = int(equipment_counts.get(row.get("id"), 0))
        return Response(content=page)

    @get("/api/master-data/areas/{area_id:int}/summary")
    async def get_master_data_area_summary(self, db_session: AsyncSession, area_id: int) -> Response[dict]:
        area = (
            await db_session.execute(
                select(m.MonitorSector)
                .where(m.MonitorSector.id == area_id)
                .options(selectinload(m.MonitorSector.parent), selectinload(m.MonitorSector.children))
            )
        ).scalar_one_or_none()
        if area is None:
            return Response(content={"code": 404, "msg": "区域不存在"}, status_code=404)
        child_ids = [child.id for child in area.children]
        device_rows = (
            (
                await db_session.execute(
                    select(m.MonitorEquipment)
                    .where(m.MonitorEquipment.sector_id == area.id)
                    .options(
                        selectinload(m.MonitorEquipment.device_type),
                        selectinload(m.MonitorEquipment.parent_device),
                        selectinload(m.MonitorEquipment.sector),
                        selectinload(m.MonitorEquipment.child_devices),
                        selectinload(m.MonitorEquipment.device_points),
                    )
                )
            )
            .scalars()
            .all()
        )
        online_count = sum(1 for item in device_rows if item.status == 0)
        child_device_counts = {}
        child_area_counts = {}
        if child_ids:
            child_device_counts = dict(
                (
                    await db_session.execute(
                        select(m.MonitorEquipment.sector_id, func.count(m.MonitorEquipment.id))
                        .where(m.MonitorEquipment.sector_id.in_(child_ids))
                        .group_by(m.MonitorEquipment.sector_id)
                    )
                ).all()
            )
            child_area_counts = dict(
                (
                    await db_session.execute(
                        select(m.MonitorSector.parent_id, func.count(m.MonitorSector.id))
                        .where(m.MonitorSector.parent_id.in_(child_ids))
                        .group_by(m.MonitorSector.parent_id)
                    )
                ).all()
            )
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "area": _serialize_area(
                        area, equipment_count=len(device_rows), child_count=len(area.children), include_parent=True
                    ),
                    "children": [
                        _serialize_area(
                            child,
                            equipment_count=int(child_device_counts.get(child.id, 0)),
                            child_count=int(child_area_counts.get(child.id, 0)),
                        )
                        for child in sorted(area.children, key=lambda item: ((item.sort_index or 0), item.id))
                    ],
                    "devices": [
                        _serialize_device(
                            item, child_device_count=len(item.child_devices), point_count=len(item.device_points)
                        )
                        for item in device_rows
                    ],
                    "stats": {
                        "device_total": len(device_rows),
                        "device_online": online_count,
                        "device_fault": len(device_rows) - online_count,
                        "child_area_total": len(area.children),
                    },
                },
            }
        )

    @post("/api/master-data/areas", guards=[requires_superuser])
    async def create_master_data_area(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        root = await _ensure_root_area(db_session)
        payload = _payload_without_none(_normalize_area_payload(data))
        if payload.get("code") != ROOT_AREA_CODE and payload.get("parent_id") is None:
            payload["parent_id"] = root.id
        obj = m.MonitorSector(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await _rebuild_area_path(db_session, obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="master-data.area.create",
            target_type="Area",
            target_id=obj.id,
            target_label=obj.name,
            details={"code": obj.code, "parent_id": obj.parent_id},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": _serialize_area(obj)})

    @patch("/api/master-data/areas/{area_id:int}", guards=[requires_superuser])
    async def update_master_data_area(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        area_id: int,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        root = await _ensure_root_area(db_session)
        obj = await db_session.get(m.MonitorSector, area_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "区域不存在"}, status_code=404)
        payload = _payload_without_none(_normalize_area_payload(data))
        next_parent_id = payload.get("parent_id", obj.parent_id)
        if obj.code == ROOT_AREA_CODE:
            next_parent_id = None
        elif next_parent_id is None:
            next_parent_id = root.id
        if next_parent_id == obj.id:
            return Response(content={"code": 400, "msg": "区域不能挂到自身下"}, status_code=400)
        if next_parent_id is not None and await _is_descendant_area(db_session, obj.id, next_parent_id):
            return Response(content={"code": 400, "msg": "区域不能挂到自己的子区域下"}, status_code=400)
        payload["parent_id"] = next_parent_id
        for field, value in payload.items():
            setattr(obj, field, value)
        await _rebuild_area_path(db_session, obj)
        await _update_area_descendant_paths(db_session, obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="master-data.area.update",
            target_type="Area",
            target_id=obj.id,
            target_label=obj.name,
            details={"updated_fields": sorted(payload.keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功", "data": _serialize_area(obj)})

    @delete("/api/master-data/areas/{area_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_master_data_area(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        area_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await db_session.get(m.MonitorSector, area_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "区域不存在"}, status_code=404)
        if obj.code == ROOT_AREA_CODE:
            return Response(content={"code": 400, "msg": "系统根区域不可删除"}, status_code=400)
        child_count = int(
            (
                await db_session.execute(
                    select(func.count(m.MonitorSector.id)).where(m.MonitorSector.parent_id == area_id)
                )
            ).scalar_one()
            or 0
        )
        if child_count > 0:
            return Response(content={"code": 400, "msg": "区域下仍有子区域，禁止删除"}, status_code=400)
        device_count = int(
            (
                await db_session.execute(
                    select(func.count(m.MonitorEquipment.id)).where(m.MonitorEquipment.sector_id == area_id)
                )
            ).scalar_one()
            or 0
        )
        if device_count > 0:
            return Response(content={"code": 400, "msg": "区域下仍有设备，禁止删除"}, status_code=400)
        label = obj.name
        await db_session.delete(obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="master-data.area.delete",
            target_type="Area",
            target_id=area_id,
            target_label=label,
            details={"code": obj.code},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/master-data/device-types/tree")
    async def list_master_data_device_type_tree(
        self,
        db_session: AsyncSession,
        device_type_service: services.DeviceTypeService,
        include_disabled: bool = True,
    ) -> Response[dict]:
        await _ensure_default_device_types(db_session)
        conditions = []
        if not include_disabled:
            conditions.append(m.DeviceType.is_enabled.is_(True))
        rows = (
            (
                await db_session.execute(
                    select(m.DeviceType).where(*(conditions or [text("1=1")])).order_by(m.DeviceType.id.asc())
                )
            )
            .scalars()
            .all()
        )
        child_counts = dict(
            (
                await db_session.execute(
                    select(m.DeviceType.parent_id, func.count(m.DeviceType.id))
                    .where(m.DeviceType.parent_id.is_not(None))
                    .group_by(m.DeviceType.parent_id)
                )
            ).all()
        )
        items = [_serialize_device_type(row, child_count=int(child_counts.get(row.id, 0))) for row in rows]
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": _build_tree(items)}})

    @get("/api/master-data/devices")
    async def list_master_data_devices(
        self,
        db_session: AsyncSession,
        device_service: services.DeviceService,
        keyword: str | None = None,
        search: str | None = None,
        area_id: int | None = None,
        device_type_id: int | None = None,
        status: int | None = None,
        is_enabled: bool | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "sort_index",
        sort_order: str = "asc",
    ) -> Response[dict]:
        conditions = []
        if area_id is not None:
            area_ids = await _get_area_subtree_ids(db_session, area_id)
            if area_ids:
                conditions.append(m.MonitorEquipment.sector_id.in_(area_ids))
        if device_type_id is not None:
            device_type_ids = await _get_device_type_subtree_ids(db_session, device_type_id)
            conditions.append(m.MonitorEquipment.device_type_id.in_(device_type_ids))
        if status is not None:
            conditions.append(m.MonitorEquipment.status == status)
        if is_enabled is not None:
            conditions.append(m.MonitorEquipment.is_enable.is_(is_enabled))
        page = await _list_page(
            device_service,
            m.MonitorEquipment,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=[
                "code",
                "name",
                "external_device_id",
                "asset_code",
                "model",
                "manufacturer",
                "owner_unit",
                "maintainer_name",
                "location",
            ],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        device_ids = [row["id"] for row in page["items"] if row.get("id") is not None]
        area_ids = [row["sector_id"] for row in page["items"] if row.get("sector_id") is not None]
        device_type_ids = [row["device_type_id"] for row in page["items"] if row.get("device_type_id") is not None]
        parent_ids = [row["parent_device_id"] for row in page["items"] if row.get("parent_device_id") is not None]
        area_map = (
            {
                row.id: row
                for row in (await db_session.execute(select(m.MonitorSector).where(m.MonitorSector.id.in_(area_ids))))
                .scalars()
                .all()
            }
            if area_ids
            else {}
        )
        type_map = (
            {
                row.id: row
                for row in (await db_session.execute(select(m.DeviceType).where(m.DeviceType.id.in_(device_type_ids))))
                .scalars()
                .all()
            }
            if device_type_ids
            else {}
        )
        parent_map = (
            {
                row.id: row
                for row in (
                    await db_session.execute(select(m.MonitorEquipment).where(m.MonitorEquipment.id.in_(parent_ids)))
                )
                .scalars()
                .all()
            }
            if parent_ids
            else {}
        )
        point_counts = {}
        child_counts = {}
        if device_ids:
            point_counts = dict(
                (
                    await db_session.execute(
                        select(m.DevicePoint.device_id, func.count(m.DevicePoint.id))
                        .where(m.DevicePoint.device_id.in_(device_ids))
                        .group_by(m.DevicePoint.device_id)
                    )
                ).all()
            )
            child_counts = dict(
                (
                    await db_session.execute(
                        select(m.MonitorEquipment.parent_device_id, func.count(m.MonitorEquipment.id))
                        .where(m.MonitorEquipment.parent_device_id.in_(device_ids))
                        .group_by(m.MonitorEquipment.parent_device_id)
                    )
                ).all()
            )
        for row in page["items"]:
            area = area_map.get(row.get("sector_id"))
            device_type = type_map.get(row.get("device_type_id"))
            parent_device = parent_map.get(row.get("parent_device_id"))
            row["area_id"] = row.get("sector_id")
            row["area_name"] = _area_label(area)
            row["device_type"] = (
                {"id": device_type.id, "code": device_type.code, "name": device_type.name}
                if device_type is not None
                else None
            )
            row["parent_device"] = (
                {"id": parent_device.id, "code": parent_device.code, "name": parent_device.name or parent_device.code}
                if parent_device is not None
                else None
            )
            row["is_enabled"] = row.get("is_enable", True)
            row["location_desc"] = row.get("location")
            row["owner_department"] = row.get("owner_unit")
            row["child_device_count"] = int(child_counts.get(row.get("id"), 0))
            row["point_count"] = int(point_counts.get(row.get("id"), 0))
        return Response(content=page)

    @get("/api/master-data/devices/{device_id:int}")
    async def get_master_data_device_detail(self, db_session: AsyncSession, device_id: int) -> Response[dict]:
        device = (
            await db_session.execute(
                select(m.MonitorEquipment)
                .where(m.MonitorEquipment.id == device_id)
                .options(
                    selectinload(m.MonitorEquipment.sector),
                    selectinload(m.MonitorEquipment.device_type),
                    selectinload(m.MonitorEquipment.parent_device),
                    selectinload(m.MonitorEquipment.child_devices),
                    selectinload(m.MonitorEquipment.device_points),
                )
            )
        ).scalar_one_or_none()
        if device is None:
            return Response(content={"code": 404, "msg": "设备不存在"}, status_code=404)
        child_devices = [
            _serialize_device(child, area=child.sector, device_type=child.device_type, parent_device=device)
            for child in sorted(device.child_devices, key=lambda item: ((item.sort_index or 0), item.id))
        ]
        point_rows = [model_to_dict(item) for item in sorted(device.device_points, key=lambda item: item.id)]
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "device": _serialize_device(
                        device,
                        area=device.sector,
                        device_type=device.device_type,
                        parent_device=device.parent_device,
                        child_device_count=len(device.child_devices),
                        point_count=len(device.device_points),
                    ),
                    "children": child_devices,
                    "points": point_rows,
                },
            }
        )

    @post("/api/master-data/devices", guards=[requires_superuser])
    async def create_master_data_device(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        await _ensure_default_device_types(db_session)
        payload = _payload_without_none(_normalize_device_payload(data))
        if payload.get("sector_id") is None:
            return Response(content={"code": 400, "msg": "area_id 为必填"}, status_code=400)
        if payload.get("device_type_id") is None:
            return Response(content={"code": 400, "msg": "device_type_id 为必填"}, status_code=400)
        obj = m.MonitorEquipment(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await _ensure_default_device_points(db_session, obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="master-data.device.create",
            target_type="Device",
            target_id=obj.id,
            target_label=obj.name,
            details={"code": obj.code, "area_id": obj.sector_id, "device_type_id": obj.device_type_id},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": _serialize_device(obj)})

    @patch("/api/master-data/devices/{device_id:int}", guards=[requires_superuser])
    async def update_master_data_device(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        device_id: int,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        await _ensure_default_device_types(db_session)
        obj = await db_session.get(m.MonitorEquipment, device_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "设备不存在"}, status_code=404)
        payload = _payload_without_none(_normalize_device_payload(data))
        next_parent_id = payload.get("parent_device_id", obj.parent_device_id)
        if next_parent_id == obj.id:
            return Response(content={"code": 400, "msg": "设备不能挂到自身下"}, status_code=400)
        if next_parent_id is not None and await _is_descendant_device(db_session, obj.id, next_parent_id):
            return Response(content={"code": 400, "msg": "设备不能挂到自己的子设备下"}, status_code=400)
        for field, value in payload.items():
            setattr(obj, field, value)
        if obj.sector_id is None:
            return Response(content={"code": 400, "msg": "area_id 为必填"}, status_code=400)
        if obj.device_type_id is None:
            return Response(content={"code": 400, "msg": "device_type_id 为必填"}, status_code=400)
        await _ensure_default_device_points(db_session, obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="master-data.device.update",
            target_type="Device",
            target_id=obj.id,
            target_label=obj.name,
            details={"updated_fields": sorted(payload.keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功", "data": _serialize_device(obj)})

    @delete("/api/master-data/devices/{device_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_master_data_device(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        device_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await db_session.get(m.MonitorEquipment, device_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "设备不存在"}, status_code=404)
        child_count = int(
            (
                await db_session.execute(
                    select(func.count(m.MonitorEquipment.id)).where(m.MonitorEquipment.parent_device_id == device_id)
                )
            ).scalar_one()
            or 0
        )
        if child_count > 0:
            return Response(content={"code": 400, "msg": "设备下仍有子设备，禁止删除"}, status_code=400)
        label = obj.name
        await db_session.delete(obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="master-data.device.delete",
            target_type="Device",
            target_id=device_id,
            target_label=label,
            details={"code": obj.code},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/master-data/device-points")
    async def list_master_data_device_points(
        self,
        db_session: AsyncSession,
        device_point_service: services.DevicePointService,
        keyword: str | None = None,
        search: str | None = None,
        device_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "asc",
    ) -> Response[dict]:
        conditions = []
        if device_id is not None:
            conditions.append(m.DevicePoint.device_id == device_id)
        page = await _list_page(
            device_point_service,
            m.DevicePoint,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["point_code", "point_name", "source_field", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        device_ids = [row["device_id"] for row in page["items"] if row.get("device_id") is not None]
        device_map = (
            {
                row.id: row
                for row in (
                    await db_session.execute(select(m.MonitorEquipment).where(m.MonitorEquipment.id.in_(device_ids)))
                )
                .scalars()
                .all()
            }
            if device_ids
            else {}
        )
        for row in page["items"]:
            device = device_map.get(row.get("device_id"))
            row["device"] = (
                {"id": device.id, "code": device.code, "name": device.name or device.code}
                if device is not None
                else None
            )
        return Response(content=page)

    @post("/api/master-data/device-points", guards=[requires_superuser])
    async def create_master_data_device_point(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        _coerce_int_fields(data, ["device_id", "sampling_interval_seconds"])
        _coerce_float_fields(data, ["upper_limit", "lower_limit"])
        payload = _payload_without_none(data)
        if payload.get("device_id") is None:
            return Response(content={"code": 400, "msg": "device_id 为必填"}, status_code=400)
        exists = await db_session.scalar(
            select(m.DevicePoint.id).where(
                m.DevicePoint.device_id == payload.get("device_id"),
                m.DevicePoint.point_code == payload.get("point_code"),
            )
        )
        if exists is not None:
            return Response(content={"code": 400, "msg": "同一设备下测点编码不能重复"}, status_code=400)
        obj = m.DevicePoint(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="master-data.device-point.create",
            target_type="DevicePoint",
            target_id=obj.id,
            target_label=obj.point_name,
            details={"device_id": obj.device_id, "point_code": obj.point_code},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/master-data/device-points/{record_id:int}", guards=[requires_superuser])
    async def update_master_data_device_point(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = await db_session.get(m.DevicePoint, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "测点不存在"}, status_code=404)
        _coerce_int_fields(data, ["device_id", "sampling_interval_seconds"])
        _coerce_float_fields(data, ["upper_limit", "lower_limit"])
        payload = _payload_without_none(data)
        next_device_id = payload.get("device_id", obj.device_id)
        next_point_code = payload.get("point_code", obj.point_code)
        exists = await db_session.scalar(
            select(m.DevicePoint.id).where(
                m.DevicePoint.device_id == next_device_id,
                m.DevicePoint.point_code == next_point_code,
                m.DevicePoint.id != obj.id,
            )
        )
        if exists is not None:
            return Response(content={"code": 400, "msg": "同一设备下测点编码不能重复"}, status_code=400)
        for field, value in payload.items():
            setattr(obj, field, value)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="master-data.device-point.update",
            target_type="DevicePoint",
            target_id=obj.id,
            target_label=obj.point_name,
            details={"updated_fields": sorted(payload.keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功", "data": model_to_dict(obj)})

    @delete("/api/master-data/device-points/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_master_data_device_point(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await db_session.get(m.DevicePoint, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "测点不存在"}, status_code=404)
        await db_session.delete(obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="master-data.device-point.delete",
            target_type="DevicePoint",
            target_id=record_id,
            target_label=obj.point_name,
            details={"device_id": obj.device_id, "point_code": obj.point_code},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    # ---------- 数据管理: 区域 / 终端 / 视频 / 规则配置 ----------
    @get("/api/data/monitor-sectors")
    async def list_monitor_sectors(
        self,
        db_session: AsyncSession,
        monitor_sector_service: services.MonitorSectorService,
        keyword: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        page = await _list_page(
            monitor_sector_service,
            m.MonitorSector,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["code", "name", "area", "description"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=[m.MonitorSector.code != ROOT_AREA_CODE],
        )
        sector_ids = [row["id"] for row in page["items"] if row.get("id") is not None]
        if sector_ids:
            photos = (
                (
                    await db_session.execute(
                        select(m.MonitorSectorPhoto)
                        .where(m.MonitorSectorPhoto.sector_id.in_(sector_ids))
                        .order_by(m.MonitorSectorPhoto.id.desc())
                    )
                )
                .scalars()
                .all()
            )
            photos_by_sector: dict[int, list[dict[str, Any]]] = {}
            for photo in photos:
                if photo.sector_id is not None:
                    photos_by_sector.setdefault(photo.sector_id, []).append(model_to_dict(photo))
            equipment_counts = dict(
                (
                    await db_session.execute(
                        select(m.MonitorEquipment.sector_id, func.count())
                        .where(m.MonitorEquipment.sector_id.in_(sector_ids))
                        .group_by(m.MonitorEquipment.sector_id)
                    )
                ).all()
            )
            for row in page["items"]:
                sector_id = row.get("id")
                row["photos"] = photos_by_sector.get(sector_id, [])
                row["equipment_count"] = equipment_counts.get(sector_id, 0)
        return Response(content=page)

    @post("/api/data/monitor-sectors", guards=[requires_superuser])
    async def create_monitor_sector(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        root = await _ensure_root_area(db_session)
        payload = _payload_without_none(_normalize_area_payload(data))
        if payload.get("code") != ROOT_AREA_CODE and payload.get("parent_id") is None:
            payload["parent_id"] = root.id
        obj = m.MonitorSector(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await _rebuild_area_path(db_session, obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.monitor-sector.create",
            target_type="MonitorSector",
            target_id=obj.id,
            target_label=obj.name,
            details={"code": obj.code},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/monitor-sectors/{record_id:int}", guards=[requires_superuser])
    async def update_monitor_sector(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        root = await _ensure_root_area(db_session)
        obj = await db_session.get(m.MonitorSector, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        payload = _payload_without_none(_normalize_area_payload(data))
        next_parent_id = payload.get("parent_id", obj.parent_id)
        if obj.code == ROOT_AREA_CODE:
            next_parent_id = None
        elif next_parent_id is None:
            next_parent_id = root.id
        if next_parent_id == obj.id:
            return Response(content={"code": 400, "msg": "区域不能挂到自身下"}, status_code=400)
        if next_parent_id is not None and await _is_descendant_area(db_session, obj.id, next_parent_id):
            return Response(content={"code": 400, "msg": "区域不能挂到自己的子区域下"}, status_code=400)
        payload["parent_id"] = next_parent_id
        for field, value in payload.items():
            setattr(obj, field, value)
        await _rebuild_area_path(db_session, obj)
        await _update_area_descendant_paths(db_session, obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.monitor-sector.update",
            target_type="MonitorSector",
            target_id=obj.id,
            target_label=obj.name,
            details={"updated_fields": sorted(payload.keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/monitor-sectors/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_monitor_sector(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await db_session.get(m.MonitorSector, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if obj.code == ROOT_AREA_CODE:
            return Response(content={"code": 400, "msg": "系统根区域不可删除"}, status_code=400)
        child_count = int(
            (
                await db_session.execute(
                    select(func.count(m.MonitorSector.id)).where(m.MonitorSector.parent_id == record_id)
                )
            ).scalar_one()
            or 0
        )
        if child_count > 0:
            return Response(content={"code": 400, "msg": "区域下仍有子区域，禁止删除"}, status_code=400)
        device_count = int(
            (
                await db_session.execute(
                    select(func.count(m.MonitorEquipment.id)).where(m.MonitorEquipment.sector_id == record_id)
                )
            ).scalar_one()
            or 0
        )
        if device_count > 0:
            return Response(content={"code": 400, "msg": "区域下仍有设备，禁止删除"}, status_code=400)
        sector_name = obj.name
        sector_code = obj.code
        await db_session.delete(obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.monitor-sector.delete",
            target_type="MonitorSector",
            target_id=record_id,
            target_label=sector_name,
            details={"code": sector_code},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/data/monitor-sector-photos", guards=[requires_superuser])
    async def create_monitor_sector_photo(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = m.MonitorSectorPhoto(**_payload_without_none(data))
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.monitor-sector-photo.create",
            target_type="MonitorSectorPhoto",
            target_id=obj.id,
            details={"sector_id": obj.sector_id, "url": obj.url},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @delete("/api/data/monitor-sector-photos/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_monitor_sector_photo(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await db_session.get(m.MonitorSectorPhoto, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        details = {"sector_id": obj.sector_id, "url": obj.url}
        await db_session.delete(obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.monitor-sector-photo.delete",
            target_type="MonitorSectorPhoto",
            target_id=record_id,
            details=details,
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/device-types")
    async def list_device_types(
        self,
        db_session: AsyncSession,
        device_type_service: services.DeviceTypeService,
        keyword: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "asc",
    ) -> Response[dict]:
        await _ensure_default_device_types(db_session)
        page = await _list_page(
            device_type_service,
            m.DeviceType,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["code", "name", "parent_code", "energy_type", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
        )
        return Response(content=page)

    @post("/api/data/device-types", guards=[requires_superuser])
    async def create_device_type(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        await _ensure_default_device_types(db_session)
        obj = m.DeviceType(**_payload_without_none(data))
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.device-type.create",
            target_type="DeviceType",
            target_id=obj.id,
            target_label=obj.name,
            details={"code": obj.code},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/device-types/{record_id:int}", guards=[requires_superuser])
    async def update_device_type(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = await db_session.get(m.DeviceType, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        for field, value in _payload_without_none(data).items():
            setattr(obj, field, value)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.device-type.update",
            target_type="DeviceType",
            target_id=obj.id,
            target_label=obj.name,
            details={"updated_fields": sorted(_payload_without_none(data).keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/device-types/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_device_type(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await db_session.get(m.DeviceType, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        label = obj.name
        code = obj.code
        await db_session.delete(obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.device-type.delete",
            target_type="DeviceType",
            target_id=record_id,
            target_label=label,
            details={"code": code},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/monitor-equipments")
    async def list_monitor_equipments(
        self,
        db_session: AsyncSession,
        monitor_equipment_service: services.MonitorEquipmentService,
        keyword: str | None = None,
        search: str | None = None,
        sector_id: int | None = None,
        category: int | None = None,
        device_type_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if sector_id:
            conditions.append(m.MonitorEquipment.sector_id == sector_id)
        if category is not None:
            conditions.append(m.MonitorEquipment.category == category)
        if device_type_id is not None:
            conditions.append(m.MonitorEquipment.device_type_id == device_type_id)
        page = await _list_page(
            monitor_equipment_service,
            m.MonitorEquipment,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=[
                "code",
                "name",
                "external_device_id",
                "supplier",
                "location",
                "asset_code",
                "model",
                "manufacturer",
                "warehouse_name",
                "warehouse_code",
            ],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        sector_ids = [row["sector_id"] for row in page["items"] if row.get("sector_id") is not None]
        device_type_ids = [row["device_type_id"] for row in page["items"] if row.get("device_type_id") is not None]
        if sector_ids:
            sectors = (
                await db_session.execute(
                    select(m.MonitorSector.id, m.MonitorSector.name).where(m.MonitorSector.id.in_(sector_ids))
                )
            ).all()
            sector_names = dict(sectors)
            for row in page["items"]:
                row["sector_name"] = sector_names.get(row.get("sector_id"))
        if device_type_ids:
            device_types = (
                await db_session.execute(
                    select(m.DeviceType.id, m.DeviceType.code, m.DeviceType.name).where(
                        m.DeviceType.id.in_(device_type_ids)
                    )
                )
            ).all()
            device_type_map = {
                identifier: {"device_type_code": code, "device_type_name": name}
                for identifier, code, name in device_types
            }
            for row in page["items"]:
                row.update(device_type_map.get(row.get("device_type_id"), {}))
        for row in page["items"]:
            if not row.get("external_device_id") and row.get("code"):
                row["external_device_id"] = row["code"]
        return Response(content=page)

    @post("/api/data/monitor-equipments", guards=[requires_superuser])
    async def create_monitor_equipment(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        await _ensure_default_device_types(db_session)
        payload = _payload_without_none(_normalize_device_payload(data))
        obj = m.MonitorEquipment(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await _ensure_default_device_points(db_session, obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.monitor-equipment.create",
            target_type="MonitorEquipment",
            target_id=obj.id,
            target_label=obj.name,
            details={"code": obj.code, "sector_id": obj.sector_id, "device_type_id": obj.device_type_id},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/monitor-equipments/{record_id:int}", guards=[requires_superuser])
    async def update_monitor_equipment(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        await _ensure_default_device_types(db_session)
        obj = await db_session.get(m.MonitorEquipment, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        payload = _payload_without_none(_normalize_device_payload(data))
        next_parent_id = payload.get("parent_device_id", obj.parent_device_id)
        if next_parent_id == obj.id:
            return Response(content={"code": 400, "msg": "设备不能挂到自身下"}, status_code=400)
        if next_parent_id is not None and await _is_descendant_device(db_session, obj.id, next_parent_id):
            return Response(content={"code": 400, "msg": "设备不能挂到自己的子设备下"}, status_code=400)
        for field, value in payload.items():
            setattr(obj, field, value)
        await _ensure_default_device_points(db_session, obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.monitor-equipment.update",
            target_type="MonitorEquipment",
            target_id=obj.id,
            target_label=obj.name,
            details={"updated_fields": sorted(payload.keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/monitor-equipments/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_monitor_equipment(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await db_session.get(m.MonitorEquipment, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        child_count = int(
            (
                await db_session.execute(
                    select(func.count(m.MonitorEquipment.id)).where(m.MonitorEquipment.parent_device_id == record_id)
                )
            ).scalar_one()
            or 0
        )
        if child_count > 0:
            return Response(content={"code": 400, "msg": "设备下仍有子设备，禁止删除"}, status_code=400)
        details = {"code": obj.code, "sector_id": obj.sector_id, "device_type_id": obj.device_type_id}
        await db_session.delete(obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.monitor-equipment.delete",
            target_type="MonitorEquipment",
            target_id=record_id,
            target_label=obj.name,
            details=details,
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/device-points")
    async def list_device_points(
        self,
        db_session: AsyncSession,
        device_point_service: services.DevicePointService,
        keyword: str | None = None,
        search: str | None = None,
        device_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if device_id is not None:
            conditions.append(m.DevicePoint.device_id == device_id)
        page = await _list_page(
            device_point_service,
            m.DevicePoint,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["point_code", "point_name", "unit", "value_type", "source_field", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        device_ids = [row["device_id"] for row in page["items"] if row.get("device_id") is not None]
        if device_ids:
            devices = (
                await db_session.execute(
                    select(m.MonitorEquipment.id, m.MonitorEquipment.code, m.MonitorEquipment.name).where(
                        m.MonitorEquipment.id.in_(device_ids)
                    )
                )
            ).all()
            device_map = {identifier: {"device_code": code, "device_name": name} for identifier, code, name in devices}
            for row in page["items"]:
                row.update(device_map.get(row.get("device_id"), {}))
        return Response(content=page)

    @post("/api/data/device-points", guards=[requires_superuser])
    async def create_device_point(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        _coerce_int_fields(data, ["device_id", "sampling_interval_seconds"])
        _coerce_float_fields(data, ["upper_limit", "lower_limit"])
        payload = _payload_without_none(data)
        exists = await db_session.scalar(
            select(m.DevicePoint.id).where(
                m.DevicePoint.device_id == payload.get("device_id"),
                m.DevicePoint.point_code == payload.get("point_code"),
            )
        )
        if exists is not None:
            return Response(content={"code": 400, "msg": "同一设备下测点编码不能重复"}, status_code=400)
        obj = m.DevicePoint(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.device-point.create",
            target_type="DevicePoint",
            target_id=obj.id,
            target_label=obj.point_name,
            details={"device_id": obj.device_id, "point_code": obj.point_code},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/device-points/{record_id:int}", guards=[requires_superuser])
    async def update_device_point(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = await db_session.get(m.DevicePoint, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        _coerce_int_fields(data, ["device_id", "sampling_interval_seconds"])
        _coerce_float_fields(data, ["upper_limit", "lower_limit"])
        payload = _payload_without_none(data)
        next_device_id = payload.get("device_id", obj.device_id)
        next_point_code = payload.get("point_code", obj.point_code)
        exists = await db_session.scalar(
            select(m.DevicePoint.id).where(
                m.DevicePoint.device_id == next_device_id,
                m.DevicePoint.point_code == next_point_code,
                m.DevicePoint.id != obj.id,
            )
        )
        if exists is not None:
            return Response(content={"code": 400, "msg": "同一设备下测点编码不能重复"}, status_code=400)
        for field, value in payload.items():
            setattr(obj, field, value)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.device-point.update",
            target_type="DevicePoint",
            target_id=obj.id,
            target_label=obj.point_name,
            details={
                "updated_fields": sorted(payload.keys()),
                "device_id": obj.device_id,
                "point_code": obj.point_code,
            },
        )
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/device-points/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_device_point(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await db_session.get(m.DevicePoint, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        details = {"device_id": obj.device_id, "point_code": obj.point_code}
        await db_session.delete(obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.device-point.delete",
            target_type="DevicePoint",
            target_id=record_id,
            target_label=obj.point_name,
            details=details,
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/video-monitors")
    async def list_video_monitors(
        self,
        video_monitor_service: services.VideoMonitorService,
        keyword: str | None = None,
        search: str | None = None,
        status: int | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if status is not None:
            conditions.append(m.VideoMonitor.status == status)
        page = await _list_page(
            video_monitor_service,
            m.VideoMonitor,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["location", "f_area", "ip_address", "brand", "b_model"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/data/video-monitors", guards=[requires_superuser])
    async def create_video_monitor(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = m.VideoMonitor(**_camera_payload(data))
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.video-monitor.create",
            target_type="VideoMonitor",
            target_id=obj.id,
            target_label=obj.location,
            details={"f_area": obj.f_area, "ip_address": obj.ip_address},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/video-monitors/{record_id:int}", guards=[requires_superuser])
    async def update_video_monitor(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = await db_session.get(m.VideoMonitor, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        for field, value in _camera_payload(data).items():
            setattr(obj, field, value)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.video-monitor.update",
            target_type="VideoMonitor",
            target_id=obj.id,
            target_label=obj.location,
            details={"updated_fields": sorted(_payload_without_none(data).keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/video-monitors/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_video_monitor(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await db_session.get(m.VideoMonitor, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        if await db_session.scalar(select(m.VisionObservation.id).where(m.VisionObservation.camera_id == record_id).limit(1)):
            raise ClientException(detail="摄像头已有识别记录，请停用并保留历史记录")
        details = {"f_area": obj.f_area, "ip_address": obj.ip_address}
        await db_session.delete(obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.video-monitor.delete",
            target_type="VideoMonitor",
            target_id=record_id,
            target_label=obj.location,
            details=details,
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/warning-rules")
    async def list_warning_rules(
        self,
        warning_rule_service: services.WarningRuleService,
        keyword: str | None = None,
        search: str | None = None,
        event_type: int | None = None,
        equipment_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if event_type is not None:
            conditions.append(m.WarningRule.event_type == event_type)
        if equipment_id is not None:
            conditions.append(m.WarningRule.equipment_id == equipment_id)
        page = await _list_page(
            warning_rule_service,
            m.WarningRule,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["name", "description", "table_name", "alarm_code", "alarm_name", "point_code"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/data/warning-rules", guards=[requires_superuser])
    async def create_warning_rule(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        _coerce_int_fields(data, ["event_type", "sector_id", "equipment_id"])
        obj = m.WarningRule(**_payload_without_none(data))
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.warning-rule.create",
            target_type="WarningRule",
            target_id=obj.id,
            target_label=obj.name,
            details={"alarm_code": obj.alarm_code, "equipment_id": obj.equipment_id},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/warning-rules/{record_id:int}", guards=[requires_superuser])
    async def update_warning_rule(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = await db_session.get(m.WarningRule, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        _coerce_int_fields(data, ["event_type", "sector_id", "equipment_id"])
        for field, value in _payload_without_none(data).items():
            setattr(obj, field, value)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.warning-rule.update",
            target_type="WarningRule",
            target_id=obj.id,
            target_label=obj.name,
            details={"updated_fields": sorted(_payload_without_none(data).keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/warning-rules/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_warning_rule(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await db_session.get(m.WarningRule, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        details = {"alarm_code": obj.alarm_code, "equipment_id": obj.equipment_id}
        await db_session.delete(obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.warning-rule.delete",
            target_type="WarningRule",
            target_id=record_id,
            target_label=obj.name,
            details=details,
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/api-result-key-mappings")
    async def list_api_result_key_mappings(
        self,
        api_result_key_mapping_service: services.ApiResultKeyMappingService,
        keyword: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        page = await _list_page(
            api_result_key_mapping_service,
            m.ApiResultKeyMapping,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["key_name", "cn_name"],
            sort_field=sort_field,
            sort_order=sort_order,
        )
        return Response(content=page)

    @post("/api/data/api-result-key-mappings", guards=[requires_superuser])
    async def create_api_result_key_mapping(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = m.ApiResultKeyMapping(**_payload_without_none(data))
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.api-result-key-mapping.create",
            target_type="ApiResultKeyMapping",
            target_id=obj.id,
            target_label=obj.key_name,
            details={"cn_name": obj.cn_name},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/data/api-result-key-mappings/{record_id:int}", guards=[requires_superuser])
    async def update_api_result_key_mapping(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = await db_session.get(m.ApiResultKeyMapping, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        for field, value in _payload_without_none(data).items():
            setattr(obj, field, value)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.api-result-key-mapping.update",
            target_type="ApiResultKeyMapping",
            target_id=obj.id,
            target_label=obj.key_name,
            details={"updated_fields": sorted(_payload_without_none(data).keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功"})

    @delete("/api/data/api-result-key-mappings/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_api_result_key_mapping(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        record_id: int,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await db_session.get(m.ApiResultKeyMapping, record_id)
        if obj is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        details = {"cn_name": obj.cn_name}
        await db_session.delete(obj)
        await db_session.commit()
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.api-result-key-mapping.delete",
            target_type="ApiResultKeyMapping",
            target_id=record_id,
            target_label=obj.key_name,
            details=details,
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/data/energy-storage")
    async def get_energy_storage_setting(self, db_session: AsyncSession) -> Response[dict]:
        obj = (
            (await db_session.execute(select(m.EnergyStorageValue).order_by(m.EnergyStorageValue.id.desc()).limit(1)))
            .scalars()
            .first()
        )
        return Response(content={"code": 200, "msg": "获取成功", "data": model_to_dict(obj) if obj else None})

    @post("/api/data/energy-storage", guards=[requires_superuser])
    async def save_energy_storage_setting(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = (
            (await db_session.execute(select(m.EnergyStorageValue).order_by(m.EnergyStorageValue.id.desc()).limit(1)))
            .scalars()
            .first()
        )
        if obj is None:
            obj = m.EnergyStorageValue(**_payload_without_none(data))
            db_session.add(obj)
        else:
            for field, value in _payload_without_none(data).items():
                setattr(obj, field, value)
        await db_session.commit()
        await db_session.refresh(obj)
        await self._log_admin_data_event(
            security_audit_service,
            request,
            action="carbon.energy-storage.save",
            target_type="EnergyStorageValue",
            target_id=obj.id,
            details={"updated_fields": sorted(_payload_without_none(data).keys())},
        )
        return Response(content={"code": 200, "msg": "保存成功", "data": model_to_dict(obj)})

    # ---------- 数据管理: 事件处理 / 流水只读 ----------
