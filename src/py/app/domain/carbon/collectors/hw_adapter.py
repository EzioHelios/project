"""Infrared-meter HTTP acquisition adapter."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from operator import itemgetter
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import select

from app.db import models as m
from app.domain.carbon.collectors.base import IDataCollector
from app.domain.metering.reading_facts import (
    VALUE_KIND_LEGACY_QUANTITY,
    VALUE_KIND_REGISTER_INDEX,
    MeterReadingFactInput,
    MeterReadingFactWriter,
)
from app.lib.settings import get_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
settings = get_settings()


class HwAdapter(IDataCollector):
    """Poll infrared meters and persist canonical metering facts."""

    FIELD_MAPPING = {
        "3": "forward_active_total",
        "4": "reverse_active_total",
        "5": "forward_reactive_total",
        "6": "reverse_reactive_total",
    }

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            base_url=settings.carbon.HW_API_HOST,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    async def connect(self) -> bool:
        return True

    async def fetch_data(self, **kwargs: Any) -> Any:
        start_time = kwargs.get("start_time")
        end_time = kwargs.get("end_time")

        params = {
            "auth": settings.carbon.HW_AUTH_CODE,
            "functionids": "3,4,5,6",
            "start_time": start_time,
            "end_time": end_time,
        }

        try:
            r = await self.client.get("/Api/DataRequest", params=params)
            r.raise_for_status()
            result = r.json()
            result["_meta"] = {"start_time": start_time, "end_time": end_time}
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            logger.exception("红外采集拉取数据异常")
            return {"status": 0}
        else:
            return result

    def normalize(self, raw: Any) -> list[dict[str, Any]]:
        if raw.get("status") != 1:
            logger.error("红外采集拉取失败, 原因: %s", raw.get("msg"))
            return []
        meta = raw.get("_meta", {})
        data_list = sorted(raw.get("data", []), key=itemgetter("mid", "fid"))
        rows = []
        for index, obj in enumerate(data_list):
            if index % 4 == 0:
                row = {
                    "readings": [],
                    "ammeter_id": obj["cid"],
                    "ammeter_name": obj["cid"],
                    "address": obj["address"],
                    "equipment_id": obj["address"],
                    "start_time": meta.get("start_time"),
                    "end_time": meta.get("end_time"),
                    "radio": obj["radio"],
                    "data_source": 1,
                }
                rows.append(row)
            else:
                row = rows[-1]

            fid = str(obj["fid"])
            if fid in self.FIELD_MAPPING:
                point_code = self.FIELD_MAPPING[fid]
                val = obj["data"][0] if obj["data"] else 0.0
                scaled = round(float(val) * float(obj["radio"]), 3)
                row["readings"].extend(
                    [
                        {
                            "source_point_code": f"fid_{fid}",
                            "source_point_name": f"红外功能号 {fid}",
                            "point_code": point_code,
                            "value_kind": VALUE_KIND_LEGACY_QUANTITY,
                            "raw_value": val,
                            "normalized_value": val,
                        },
                        {
                            "source_point_code": f"fid_{fid}_scaled",
                            "source_point_name": f"红外功能号 {fid} 倍率换算值",
                            "point_code": point_code,
                            "value_kind": VALUE_KIND_REGISTER_INDEX,
                            "raw_value": val,
                            "normalized_value": scaled,
                        },
                    ]
                )
        return rows

    async def save(self, db_session: AsyncSession, normalized_list: list[dict[str, Any]]) -> int:
        if not normalized_list:
            return 0
        try:
            addresses = {row["equipment_id"] for row in normalized_list if row.get("equipment_id")}
            equipment_rows = (
                await db_session.scalars(
                    select(m.MonitorEquipment).where(
                        (m.MonitorEquipment.external_device_id.in_(addresses))
                        | (m.MonitorEquipment.code.in_(addresses))
                    )
                )
            ).all()
            equipment_by_address = {
                address: equipment
                for equipment in equipment_rows
                for address in (equipment.external_device_id, equipment.code)
                if address
            }
            facts: list[MeterReadingFactInput] = []
            for row in normalized_list:
                address = row.get("equipment_id")
                equipment = equipment_by_address.get(address)
                if equipment is None:
                    logger.warning("红外采集未找到平台设备, 跳过电表 address=%s", address)
                    continue
                reading_time = _parse_datetime(row.get("end_time") or row.get("start_time"))
                if reading_time is None:
                    continue
                for reading in row.get("readings", []):
                    source_record_id = (
                        f"hw:{address}:{reading_time.isoformat()}:{reading['point_code']}:{reading['value_kind']}"
                    )
                    facts.append(
                        MeterReadingFactInput(
                            source_system="infrared_hw",
                            source_record_id=source_record_id,
                            equipment_id=equipment.id,
                            source_point_code=reading["source_point_code"],
                            source_point_name=reading["source_point_name"],
                            point_code=reading["point_code"],
                            raw_value=reading["raw_value"],
                            normalized_value=reading["normalized_value"],
                            value_kind=reading["value_kind"],
                            reading_time=reading_time,
                            mapping_version="hw_v1",
                        )
                    )
            inserted = await MeterReadingFactWriter(db_session).write_many(facts)
            await db_session.commit()
            logger.info("红外采集成功写入 %s 条规范读数", inserted)
        except (ValueError, TypeError, KeyError, ArithmeticError):
            logger.exception("红外采集保存数据失败")
            await db_session.rollback()
            return 0
        else:
            return inserted

    async def sync_device_status(self, db_session: AsyncSession) -> None:
        """Synchronize meter availability and relay status."""
        try:
            r = await self.client.get("/Api/Meter", params={"auth": settings.carbon.HW_AUTH_CODE})
            jo = r.json()
            if jo["status"] == 1:
                for obj in jo["data"]:
                    status = 0 if obj["relay_state"] == "1" else 1
                    await db_session.execute(
                        m.MonitorEquipment.__table__.update()
                        .where(
                            (m.MonitorEquipment.external_device_id == obj["address"])
                            | (m.MonitorEquipment.code == obj["address"])
                        )
                        .values(status=status, trip_state=status)
                    )
                await db_session.commit()
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            logger.exception("红外采集同步设备状态异常")


def _parse_datetime(value: object) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    msg = f"红外时间格式无法识别: {value}"
    raise ValueError(msg)
