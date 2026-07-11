from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from litestar import Controller, get
from litestar.response import Response
from sqlalchemy import String, and_, func, or_, select, text

from app.db import models as m
from app.domain.accounts.guards import requires_authenticated_user
from app.domain.energy.controllers._utils import ok_data
from app.domain.production_denominator.controllers._utils import paged_payload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_POINT_CODE = "forward_active_total"
DEFAULT_VALUE_KIND = "register_index"
DEFAULT_TIMEOUT_SECONDS = 600
MAX_LIMIT = 200
MAX_SERIES_LIMIT = 1000


class MeteringReadingController(Controller):
    tags = ["Metering"]

    @get("/api/metering/readings", guards=[requires_authenticated_user])
    async def list_readings(
        self,
        db_session: AsyncSession,
        keyword: str | None = None,
        search: str | None = None,
        area_id: str | None = None,
        equipment_id: int | None = None,
        point_code: str | None = None,
        value_kind: str | None = None,
        quality_status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        limited = _limit(limit)
        safe_offset = max(offset, 0)
        statement = _reading_rows_statement(
            keyword=search or keyword,
            area_id=area_id,
            equipment_id=equipment_id,
            point_code=point_code,
            value_kind=value_kind,
            quality_status=quality_status,
        )
        total = await db_session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
        rows = (
            await db_session.execute(
                statement.order_by(m.MeterReadingFact.reading_time.desc(), m.MeterReadingFact.id.desc())
                .limit(limited)
                .offset(safe_offset)
            )
        ).mappings().all()
        return Response(content=paged_payload([_reading_row(row) for row in rows], total or 0, limited, safe_offset))

    @get("/api/metering/readings/latest", guards=[requires_authenticated_user])
    async def latest_readings(
        self,
        db_session: AsyncSession,
        keyword: str | None = None,
        area_id: str | None = None,
        equipment_id: int | None = None,
        point_code: str | None = None,
        value_kind: str | None = None,
        quality_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[dict]:
        limited = _limit(limit)
        safe_offset = max(offset, 0)
        reading = m.MeterReadingFact
        latest = _latest_ids_subquery()
        statement = _reading_rows_statement(
            keyword=keyword,
            area_id=area_id,
            equipment_id=equipment_id,
            point_code=point_code,
            value_kind=value_kind,
            quality_status=quality_status,
        ).join(latest, and_(latest.c.reading_id == reading.id, latest.c.row_number == 1))
        rows = (await db_session.execute(statement.order_by(reading.reading_time.desc(), reading.id.desc()))).mappings().all()
        summary = _latest_summary(rows)
        page_rows = rows[safe_offset : safe_offset + limited]
        return Response(
            content=ok_data(
                {
                    "items": [_reading_row(row) for row in page_rows],
                    "summary": summary,
                    "total": len(rows),
                    "limit": limited,
                    "offset": safe_offset,
                }
            )
        )

    @get("/api/metering/readings/series", guards=[requires_authenticated_user])
    async def reading_series(
        self,
        db_session: AsyncSession,
        equipment_id: int,
        point_code: str = DEFAULT_POINT_CODE,
        value_kind: str = DEFAULT_VALUE_KIND,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 500,
    ) -> Response[dict]:
        start_dt, end_dt = _time_window(start_time, end_time)
        limited = max(1, min(limit, MAX_SERIES_LIMIT))
        rows = (
            await db_session.scalars(
                select(m.MeterReadingFact)
                .where(
                    m.MeterReadingFact.equipment_id == equipment_id,
                    m.MeterReadingFact.point_code == point_code,
                    m.MeterReadingFact.value_kind == value_kind,
                    m.MeterReadingFact.reading_time >= start_dt,
                    m.MeterReadingFact.reading_time <= end_dt,
                )
                .order_by(m.MeterReadingFact.reading_time.asc(), m.MeterReadingFact.id.asc())
                .limit(limited)
            )
        ).all()
        return Response(
            content=ok_data(
                {
                    "items": [_series_row(row) for row in rows],
                    "total": len(rows),
                    "limit": limited,
                    "equipment_id": equipment_id,
                    "point_code": point_code,
                    "value_kind": value_kind,
                }
            )
        )

    @get("/api/metering/energy/summary", guards=[requires_authenticated_user])
    async def energy_summary(
        self,
        db_session: AsyncSession,
        period: str = "day",
        start_time: str | None = None,
        end_time: str | None = None,
        area_id: str | None = None,
        equipment_id: int | None = None,
        point_code: str = DEFAULT_POINT_CODE,
    ) -> Response[dict]:
        start_dt, end_dt = _time_window(start_time, end_time) if start_time or end_time else _period_window(period)
        rows = await _consumption_rows(
            db_session,
            start_dt=start_dt,
            end_dt=end_dt,
            point_code=point_code,
            granularity=None,
            area_id=area_id,
            equipment_id=equipment_id,
        )
        total_kwh = sum(_float(row.get("total_kwh")) for row in rows)
        sample_count = sum(int(row.get("sample_count") or 0) for row in rows)
        invalid_count = sum(1 for row in rows if str(row.get("calc_status")) != "ready")
        return Response(
            content=ok_data(
                {
                    "period": period,
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat(),
                    "point_code": point_code,
                    "total_kwh": total_kwh,
                    "meter_count": len(rows),
                    "sample_count": sample_count,
                    "invalid_meter_count": invalid_count,
                    "calc_status": "ready" if rows and invalid_count == 0 else "partial" if rows else "empty",
                }
            )
        )

    @get("/api/metering/energy/trend", guards=[requires_authenticated_user])
    async def energy_trend(
        self,
        db_session: AsyncSession,
        granularity: str = "day",
        start_time: str | None = None,
        end_time: str | None = None,
        area_id: str | None = None,
        equipment_id: int | None = None,
        point_code: str = DEFAULT_POINT_CODE,
    ) -> Response[dict]:
        start_dt, end_dt = _time_window(start_time, end_time, default_hours=24 * 30)
        safe_granularity = granularity if granularity in {"hour", "day", "month"} else "day"
        rows = await _consumption_rows(
            db_session,
            start_dt=start_dt,
            end_dt=end_dt,
            point_code=point_code,
            granularity=safe_granularity,
            area_id=area_id,
            equipment_id=equipment_id,
        )
        items: dict[str, dict[str, Any]] = {}
        for row in rows:
            period_key = str(row["period_key"])
            item = items.setdefault(period_key, {"period": period_key, "total_kwh": 0.0, "sample_count": 0})
            item["total_kwh"] += _float(row.get("total_kwh"))
            item["sample_count"] += int(row.get("sample_count") or 0)
        return Response(content=ok_data({"items": list(items.values()), "granularity": safe_granularity}))

    @get("/api/metering/energy/ranking", guards=[requires_authenticated_user])
    async def energy_ranking(
        self,
        db_session: AsyncSession,
        group_by: str = "equipment",
        period: str = "day",
        start_time: str | None = None,
        end_time: str | None = None,
        area_id: str | None = None,
        limit: int = 20,
        point_code: str = DEFAULT_POINT_CODE,
    ) -> Response[dict]:
        start_dt, end_dt = _time_window(start_time, end_time) if start_time or end_time else _period_window(period)
        rows = await _consumption_rows(
            db_session,
            start_dt=start_dt,
            end_dt=end_dt,
            point_code=point_code,
            granularity=None,
            area_id=area_id,
            equipment_id=None,
        )
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = str(row["area_id"] if group_by == "area" else row["equipment_id"])
            label = row["area_name"] if group_by == "area" else row["equipment_name"]
            item = grouped.setdefault(key, {"id": key, "name": label or key, "total_kwh": 0.0, "sample_count": 0})
            item["total_kwh"] += _float(row.get("total_kwh"))
            item["sample_count"] += int(row.get("sample_count") or 0)
        items = sorted(grouped.values(), key=lambda row: row["total_kwh"], reverse=True)[: _limit(limit)]
        return Response(content=ok_data({"items": items, "group_by": group_by, "period": period}))

    @get("/api/metering/quality/summary", guards=[requires_authenticated_user])
    async def quality_summary(self, db_session: AsyncSession) -> Response[dict]:
        reading = m.MeterReadingFact
        latest = _latest_ids_subquery()
        rows = (
            await db_session.execute(_latest_meter_rows_statement().join(latest, and_(latest.c.reading_id == reading.id, latest.c.row_number == 1)))
        ).mappings().all()
        return Response(content=ok_data(_latest_summary(rows)))


def _reading_rows_statement(
    *,
    keyword: str | None = None,
    area_id: str | None = None,
    equipment_id: int | None = None,
    point_code: str | None = None,
    value_kind: str | None = None,
    quality_status: str | None = None,
) -> Any:
    reading = m.MeterReadingFact
    statement = _latest_meter_rows_statement()
    conditions = []
    if area_id:
        conditions.append(func.cast(m.MonitorEquipment.sector_id, String) == area_id)
    if equipment_id is not None:
        conditions.append(reading.equipment_id == equipment_id)
    if point_code:
        conditions.append(reading.point_code == point_code)
    if value_kind:
        conditions.append(reading.value_kind == value_kind)
    if quality_status:
        conditions.append(reading.quality_status == quality_status)
    term = (keyword or "").strip()
    if term:
        pattern = f"%{term}%"
        conditions.append(
            or_(
                m.MonitorEquipment.code.ilike(pattern),
                m.MonitorEquipment.name.ilike(pattern),
                m.MonitorSector.name.ilike(pattern),
                reading.point_code.ilike(pattern),
                reading.point_name.ilike(pattern),
                reading.source_point_code.ilike(pattern),
                reading.source_point_name.ilike(pattern),
            )
        )
    if conditions:
        statement = statement.where(*conditions)
    return statement


def _latest_meter_rows_statement() -> Any:
    reading = m.MeterReadingFact
    return (
        select(
            reading.id,
            reading.reading_time,
            reading.equipment_id,
            m.MonitorEquipment.code.label("equipment_code"),
            m.MonitorEquipment.name.label("equipment_name"),
            m.MonitorEquipment.external_device_id.label("external_device_id"),
            m.MonitorSector.id.label("area_id"),
            m.MonitorSector.name.label("area_name"),
            reading.point_code,
            reading.point_name,
            reading.energy_direction,
            reading.energy_kind,
            reading.tou_period,
            reading.value_kind,
            reading.normalized_value,
            reading.raw_value,
            reading.unit,
            reading.quality_status,
            reading.source_system,
            reading.source_record_id,
            reading.source_point_code,
            reading.source_point_name,
            reading.source_message_id,
            m.MqttSubscription.expected_interval_seconds,
        )
        .join(m.MonitorEquipment, m.MonitorEquipment.id == reading.equipment_id)
        .outerjoin(m.MonitorSector, m.MonitorSector.id == m.MonitorEquipment.sector_id)
        .outerjoin(m.MqttDeviceBinding, m.MqttDeviceBinding.id == reading.binding_id)
        .outerjoin(m.MqttSubscription, m.MqttSubscription.id == m.MqttDeviceBinding.subscription_id)
    )


def _latest_ids_subquery() -> Any:
    reading = m.MeterReadingFact
    return (
        select(
            reading.id.label("reading_id"),
            func.row_number()
            .over(
                partition_by=(reading.equipment_id, reading.point_code, reading.value_kind),
                order_by=(reading.reading_time.desc(), reading.id.desc()),
            )
            .label("row_number"),
        ).subquery()
    )


async def _consumption_rows(
    db_session: AsyncSession,
    *,
    start_dt: datetime,
    end_dt: datetime,
    point_code: str,
    granularity: str | None,
    area_id: str | None,
    equipment_id: int | None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "start_time": start_dt,
        "end_time": end_dt,
        "point_code": point_code,
        "value_kind": DEFAULT_VALUE_KIND,
        "granularity": granularity,
        "area_id": area_id,
        "equipment_id": equipment_id,
    }
    sql = text(
        """
        with ordered as (
            select
                fact.team_id,
                fact.equipment_id,
                equipment.code as equipment_code,
                equipment.name as equipment_name,
                sector.id::text as area_id,
                sector.name as area_name,
                case
                    when cast(:granularity as text) is null then null::timestamp
                    else date_trunc(cast(:granularity as text), fact.reading_time)
                end as period_bucket,
                fact.reading_time,
                fact.normalized_value,
                first_value(fact.normalized_value) over (
                    partition by fact.team_id, fact.equipment_id, case
                        when cast(:granularity as text) is null then null::timestamp
                        else date_trunc(cast(:granularity as text), fact.reading_time)
                    end
                    order by fact.reading_time asc, fact.id asc
                ) as start_value,
                first_value(fact.normalized_value) over (
                    partition by fact.team_id, fact.equipment_id, case
                        when cast(:granularity as text) is null then null::timestamp
                        else date_trunc(cast(:granularity as text), fact.reading_time)
                    end
                    order by fact.reading_time desc, fact.id desc
                ) as end_value,
                count(*) over (
                    partition by fact.team_id, fact.equipment_id, case
                        when cast(:granularity as text) is null then null::timestamp
                        else date_trunc(cast(:granularity as text), fact.reading_time)
                    end
                ) as sample_count
            from metering_meter_reading_fact fact
            join dataapp_monitorequipment equipment on equipment.id = fact.equipment_id
            left join dataapp_monitorsector sector on sector.id = equipment.sector_id
            where
                fact.reading_time >= :start_time
                and fact.reading_time < :end_time
                and fact.point_code = :point_code
                and fact.value_kind = :value_kind
                and fact.normalized_value is not null
                and (cast(:area_id as text) is null or equipment.sector_id::text = cast(:area_id as text))
                and (cast(:equipment_id as integer) is null or fact.equipment_id = cast(:equipment_id as integer))
        ),
        deduped as (
            select distinct on (team_id, equipment_id, period_bucket)
                team_id,
                equipment_id,
                equipment_code,
                equipment_name,
                area_id,
                area_name,
                period_bucket,
                start_value,
                end_value,
                sample_count
            from ordered
            order by team_id, equipment_id, period_bucket, reading_time desc
        )
        select
            coalesce(to_char(period_bucket, 'YYYY-MM-DD HH24:MI:SS'), 'total') as period_key,
            equipment_id,
            max(equipment_code) as equipment_code,
            max(equipment_name) as equipment_name,
            max(area_id) as area_id,
            coalesce(max(area_name), '未分区') as area_name,
            min(start_value) as start_index,
            max(end_value) as end_index,
            greatest(max(end_value) - min(start_value), 0) as total_kwh,
            sum(sample_count)::int as sample_count,
            case when count(*) > 0 and min(sample_count) >= 2 then 'ready' else 'insufficient_data' end as calc_status
        from deduped
        group by period_key, equipment_id
        order by period_key asc, total_kwh desc nulls last
        """
    )
    return [dict(row) for row in (await db_session.execute(sql, params)).mappings().all()]


def _reading_row(row: Any) -> dict[str, Any]:
    data = dict(row)
    data["reading_time"] = _iso(data.get("reading_time"))
    for key in ("normalized_value",):
        data[key] = _float(data.get(key)) if data.get(key) is not None else None
    return data


def _series_row(row: m.MeterReadingFact) -> dict[str, Any]:
    return {
        "id": row.id,
        "reading_time": _iso(row.reading_time),
        "normalized_value": _float(row.normalized_value) if row.normalized_value is not None else None,
        "raw_value": row.raw_value,
        "quality_status": row.quality_status,
        "unit": row.unit,
        "source_system": row.source_system,
        "source_record_id": row.source_record_id,
        "source_point_code": row.source_point_code,
        "source_message_id": row.source_message_id,
    }


def _latest_summary(rows: list[Any]) -> dict[str, Any]:
    now = datetime.now(UTC).replace(tzinfo=None)
    latest_time = max((row["reading_time"] for row in rows if row["reading_time"] is not None), default=None)
    valid_count = sum(1 for row in rows if row["quality_status"] == "valid")
    invalid_count = sum(1 for row in rows if row["quality_status"] == "invalid")
    timeout_count = 0
    for row in rows:
        reading_time = row["reading_time"]
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


def _period_window(period: str) -> tuple[datetime, datetime]:
    now = datetime.now(UTC).replace(tzinfo=None)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return start, now
    if period == "month":
        return today.replace(day=1), now
    if period == "year":
        return today.replace(month=1, day=1), now
    return today, now


def _time_window(start_time: str | None, end_time: str | None, *, default_hours: int = 24) -> tuple[datetime, datetime]:
    end_dt = _parse_datetime(end_time) if end_time else datetime.now(UTC).replace(tzinfo=None)
    start_dt = _parse_datetime(start_time) if start_time else end_dt - timedelta(hours=default_hours)
    return start_dt, end_dt


def _parse_datetime(value: str | None) -> datetime:
    if value is None:
        msg = "时间不能为空"
        raise ValueError(msg)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _limit(value: int) -> int:
    return max(1, min(value or 1, MAX_LIMIT))


def _float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None
