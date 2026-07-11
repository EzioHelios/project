"""Read-only point monitoring APIs backed by normalized IoT readings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from litestar import Controller, get
from litestar.response import Response
from sqlalchemy import and_, func, or_, select

from app.db import models as m
from app.domain.accounts.guards import requires_authenticated_user
from app.domain.energy.controllers._utils import ok_data

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_SERIES_HOURS = 24
MAX_POINT_LIMIT = 200
MAX_SERIES_LIMIT = 1000


class IotPointMonitoringController(Controller):
    """Expose tenant-scoped monitoring read models for mapped device points."""

    tags = ["IoT Monitoring"]

    @get("/api/iot-monitoring/points", guards=[requires_authenticated_user])
    async def list_points(
        self,
        db_session: AsyncSession,
        keyword: str | None = None,
        equipment_id: int | None = None,
        quality_status: str | None = None,
        source_id: int | None = None,
        subscription_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        """List the latest reading for each mapped point."""
        limited = _safe_limit(limit, MAX_POINT_LIMIT)
        safe_offset = max(offset, 0)
        statement = _latest_points_statement(
            keyword=keyword,
            equipment_id=equipment_id,
            quality_status=quality_status,
            source_id=source_id,
            subscription_id=subscription_id,
        )
        rows = (await db_session.execute(statement)).mappings().all()
        summary = _build_summary(rows)
        page_rows = rows[safe_offset : safe_offset + limited]
        return Response(
            content=ok_data(
                {
                    "items": [_point_row(row) for row in page_rows],
                    "summary": summary,
                    "filter_options": _filter_options(rows),
                    "total": len(rows),
                    "limit": limited,
                    "offset": safe_offset,
                }
            )
        )

    @get("/api/iot-monitoring/point-series", guards=[requires_authenticated_user])
    async def point_series(
        self,
        db_session: AsyncSession,
        binding_id: int,
        source_point_code: str | None = None,
        source_tag: str | None = None,
        mapping_version: str = "v1",
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 500,
    ) -> Response[dict]:
        """Return one point's readings in ascending time order."""
        tag = (source_point_code or source_tag or "").strip()
        version = mapping_version.strip() or "v1"
        if not tag:
            return Response(content={"code": 400, "msg": "source_point_code 为必填"}, status_code=400)
        try:
            start_dt, end_dt = _time_window(start_time, end_time)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)

        limited = _safe_limit(limit, MAX_SERIES_LIMIT)
        statement = (
            select(m.MeterReadingFact)
            .where(
                m.MeterReadingFact.binding_id == binding_id,
                m.MeterReadingFact.source_point_code == tag,
                m.MeterReadingFact.mapping_version == version,
                m.MeterReadingFact.reading_time >= start_dt,
                m.MeterReadingFact.reading_time <= end_dt,
            )
            .order_by(m.MeterReadingFact.reading_time.asc(), m.MeterReadingFact.id.asc())
            .limit(limited)
        )
        rows = (await db_session.scalars(statement)).all()
        return Response(
            content=ok_data(
                {
                    "items": [_series_row(row) for row in rows],
                    "total": len(rows),
                    "limit": limited,
                    "binding_id": binding_id,
                    "source_point_code": tag,
                    "mapping_version": version,
                }
            )
        )


def _latest_points_statement(
    *,
    keyword: str | None,
    equipment_id: int | None,
    quality_status: str | None,
    source_id: int | None,
    subscription_id: int | None,
) -> Any:
    reading = m.MeterReadingFact
    latest = (
        select(
            reading.id.label("reading_id"),
            func.row_number()
            .over(
                partition_by=(reading.binding_id, reading.source_point_code, reading.mapping_version),
                order_by=(reading.reading_time.desc(), reading.id.desc()),
            )
            .label("row_number"),
        )
        .subquery()
    )
    statement = (
        select(
            reading.id.label("reading_id"),
            reading.binding_id,
            reading.equipment_id,
            reading.source_message_id,
            reading.source_point_code,
            reading.source_point_name,
            reading.point_code,
            reading.point_name,
            reading.energy_direction,
            reading.energy_kind,
            reading.tou_period,
            reading.value_kind,
            reading.raw_value,
            reading.normalized_value,
            reading.unit,
            reading.quality_status,
            reading.source_type,
            reading.reading_time,
            reading.mapping_version,
            m.MqttDeviceBinding.gateway_key,
            m.MqttDeviceBinding.meter_key,
            m.MqttDeviceBinding.external_device_id,
            m.MqttDeviceBinding.temporary_address,
            m.MqttDeviceBinding.identity_status,
            m.MqttSubscription.id.label("subscription_id"),
            m.MqttSubscription.topic_filter,
            m.MqttSubscription.expected_interval_seconds,
            m.MqttDataSource.id.label("source_id"),
            m.MqttDataSource.code.label("source_code"),
            m.MqttDataSource.name.label("source_name_label"),
            m.MonitorEquipment.code.label("equipment_code"),
            m.MonitorEquipment.name.label("equipment_name"),
            m.MonitorSector.id.label("sector_id"),
            m.MonitorSector.name.label("sector_name"),
            m.DevicePoint.id.label("device_point_id"),
            m.DevicePoint.point_name.label("device_point_name"),
            m.DevicePoint.unit.label("device_point_unit"),
            m.MqttPointMapping.point_code.label("mapped_point_code"),
            m.MqttPointMapping.unit.label("mapped_unit"),
        )
        .join(latest, and_(latest.c.reading_id == reading.id, latest.c.row_number == 1))
        .join(m.MqttDeviceBinding, m.MqttDeviceBinding.id == reading.binding_id)
        .join(m.MqttSubscription, m.MqttSubscription.id == m.MqttDeviceBinding.subscription_id)
        .join(m.MqttDataSource, m.MqttDataSource.id == m.MqttSubscription.source_id)
        .join(m.MonitorEquipment, m.MonitorEquipment.id == reading.equipment_id)
        .outerjoin(m.MonitorSector, m.MonitorSector.id == m.MonitorEquipment.sector_id)
        .outerjoin(
            m.MqttPointMapping,
            and_(
                m.MqttPointMapping.binding_id == reading.binding_id,
                m.MqttPointMapping.source_tag == reading.source_point_code,
                m.MqttPointMapping.mapping_version == reading.mapping_version,
            ),
        )
        .outerjoin(
            m.DevicePoint,
            and_(m.DevicePoint.device_id == reading.equipment_id, m.DevicePoint.point_code == reading.point_code),
        )
        .order_by(reading.reading_time.desc(), reading.id.desc())
    )
    conditions = []
    if equipment_id is not None:
        conditions.append(reading.equipment_id == equipment_id)
    if quality_status:
        conditions.append(reading.quality_status == quality_status)
    if source_id is not None:
        conditions.append(m.MqttDataSource.id == source_id)
    if subscription_id is not None:
        conditions.append(m.MqttSubscription.id == subscription_id)
    term = (keyword or "").strip()
    if term:
        pattern = f"%{term}%"
        conditions.append(
            or_(
                m.MonitorEquipment.name.ilike(pattern),
                m.MonitorEquipment.code.ilike(pattern),
                m.MonitorSector.name.ilike(pattern),
                m.DevicePoint.point_name.ilike(pattern),
                reading.point_name.ilike(pattern),
                reading.point_code.ilike(pattern),
                reading.source_point_name.ilike(pattern),
                reading.source_point_code.ilike(pattern),
                m.MqttDeviceBinding.external_device_id.ilike(pattern),
                m.MqttDeviceBinding.temporary_address.ilike(pattern),
            )
        )
    if conditions:
        statement = statement.where(*conditions)
    return statement


def _build_summary(rows: list[Any]) -> dict[str, Any]:
    now = datetime.now(UTC).replace(tzinfo=None)
    latest_time = max((_row_datetime(row, "reading_time") for row in rows), default=None)
    valid_count = sum(1 for row in rows if row["quality_status"] == "valid")
    invalid_count = sum(1 for row in rows if row["quality_status"] == "invalid")
    timeout_count = 0
    for row in rows:
        reading_time = _row_datetime(row, "reading_time")
        if reading_time is None:
            continue
        interval = int(row["expected_interval_seconds"] or 0)
        timeout_seconds = interval * 2 if interval > 0 else DEFAULT_TIMEOUT_SECONDS
        if reading_time < now - timedelta(seconds=timeout_seconds):
            timeout_count += 1
    return {
        "total_points": len(rows),
        "valid_points": valid_count,
        "invalid_points": invalid_count,
        "timeout_points": timeout_count,
        "latest_reading_time": _iso(latest_time),
    }


def _filter_options(rows: list[Any]) -> dict[str, list[dict[str, Any]]]:
    sources: dict[int, dict[str, Any]] = {}
    subscriptions: dict[int, dict[str, Any]] = {}
    equipment: dict[int, dict[str, Any]] = {}
    for row in rows:
        sources[row["source_id"]] = {
            "id": row["source_id"],
            "code": row["source_code"],
            "name": row["source_name_label"],
        }
        subscriptions[row["subscription_id"]] = {
            "id": row["subscription_id"],
            "topic_filter": row["topic_filter"],
            "source_id": row["source_id"],
        }
        equipment[row["equipment_id"]] = {
            "id": row["equipment_id"],
            "code": row["equipment_code"],
            "name": row["equipment_name"] or row["equipment_code"],
        }
    return {
        "sources": sorted(sources.values(), key=lambda item: str(item["code"] or item["name"])),
        "subscriptions": sorted(subscriptions.values(), key=lambda item: str(item["topic_filter"])),
        "equipment": sorted(equipment.values(), key=lambda item: str(item["name"] or item["code"])),
    }


def _point_row(row: Any) -> dict[str, Any]:
    point_name = row["device_point_name"] or row["point_name"] or row["mapped_point_code"] or row["source_point_name"] or row["point_code"]
    unit = row["device_point_unit"] or row["mapped_unit"] or row["unit"]
    return {
        "selection_key": f"{row['binding_id']}:{row['source_point_code']}:{row['mapping_version']}",
        "binding_id": row["binding_id"],
        "equipment_id": row["equipment_id"],
        "equipment_code": row["equipment_code"],
        "equipment_name": row["equipment_name"] or row["equipment_code"],
        "sector_id": row["sector_id"],
        "sector_name": row["sector_name"],
        "point_code": row["point_code"],
        "point_name": point_name,
        "energy_direction": row["energy_direction"],
        "energy_kind": row["energy_kind"],
        "tou_period": row["tou_period"],
        "value_kind": row["value_kind"],
        "unit": unit,
        "latest_value": _decimal_to_float(row["normalized_value"]),
        "raw_value": row["raw_value"],
        "latest_reading_time": _iso(row["reading_time"]),
        "quality_status": row["quality_status"],
        "source_type": row["source_type"],
        "source_message_id": row["source_message_id"],
        "gateway_key": row["gateway_key"],
        "meter_key": row["meter_key"],
        "external_device_id": row["external_device_id"],
        "temporary_address": row["temporary_address"],
        "identity_status": row["identity_status"],
        "source_id": row["source_id"],
        "source_code": row["source_code"],
        "source_name": row["source_name_label"],
        "subscription_id": row["subscription_id"],
        "topic_filter": row["topic_filter"],
        "source_point_code": row["source_point_code"],
        "source_tag": row["source_point_code"],
        "source_point_name": row["source_point_name"],
        "mapping_version": row["mapping_version"],
    }


def _series_row(row: m.MeterReadingFact) -> dict[str, Any]:
    return {
        "id": row.id,
        "reading_time": _iso(row.reading_time),
        "normalized_value": _decimal_to_float(row.normalized_value),
        "raw_value": row.raw_value,
        "quality_status": row.quality_status,
        "unit": row.unit,
        "source_message_id": row.source_message_id,
    }


def _safe_limit(value: int, max_value: int) -> int:
    return max(1, min(int(value or 1), max_value))


def _time_window(start_time: str | None, end_time: str | None) -> tuple[datetime, datetime]:
    end_dt = _parse_datetime(end_time) if end_time else datetime.now(UTC).replace(tzinfo=None)
    start_dt = _parse_datetime(start_time) if start_time else end_dt - timedelta(hours=DEFAULT_SERIES_HOURS)
    if start_dt > end_dt:
        msg = "start_time 不能晚于 end_time"
        raise ValueError(msg)
    return start_dt, end_dt


def _parse_datetime(value: str | None) -> datetime:
    if value is None:
        msg = "时间不能为空"
        raise ValueError(msg)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        msg = "时间格式必须为 ISO 8601"
        raise ValueError(msg) from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _row_datetime(row: Any, key: str) -> datetime | None:
    value = row[key]
    return value if isinstance(value, datetime) else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
