from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, get
from litestar.response import Response
from sqlalchemy import or_, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MeteringTelemetryController(Controller):
    tags = ["Metering"]

    @get("/api/carbon/iot-telemetry")
    async def list_iot_telemetry(
        self,
        db_session: AsyncSession,
        site_id: str | None = None,
        device_id: str | None = None,
        limit: int = 200,
    ) -> Response[dict]:
        filters = []
        model = m.IotTelemetry
        if site_id:
            filters.append(model.site_id == site_id)
        if device_id:
            filters.append(model.device_id == device_id)
        limit_clamped = max(10, min(limit, 1000))
        stmt = select(model).order_by(model.reading_time.desc()).limit(limit_clamped)
        if filters:
            stmt = stmt.where(*filters)
        items = (await db_session.execute(stmt)).scalars().all()
        telemetry_rows = [model_to_dict(item) for item in items]
        device_ids = {row["device_id"] for row in telemetry_rows if row.get("device_id")}
        equipment_map: dict[str, dict[str, Any]] = {}
        if device_ids:
            matched = (
                await db_session.execute(
                    select(
                        m.MonitorEquipment.id,
                        m.MonitorEquipment.code,
                        m.MonitorEquipment.name,
                        m.MonitorEquipment.external_device_id,
                        m.MonitorEquipment.asset_code,
                    ).where(
                        or_(
                            m.MonitorEquipment.external_device_id.in_(device_ids),
                            m.MonitorEquipment.code.in_(device_ids),
                        )
                    )
                )
            ).all()
            for equipment_id, code, name, external_device_id, asset_code in matched:
                for key in {external_device_id, code} - {None}:
                    equipment_map[str(key)] = {
                        "equipment_id": equipment_id,
                        "equipment_code": code,
                        "equipment_name": name,
                        "asset_code": asset_code,
                        "external_device_id": external_device_id or code,
                    }
        for row in telemetry_rows:
            row.update(equipment_map.get(str(row.get("device_id")), {}))
        return Response(content={"code": 200, "data": telemetry_rows})

