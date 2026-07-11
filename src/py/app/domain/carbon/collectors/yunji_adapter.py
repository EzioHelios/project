"""云集 (Yunji) HTTP API 适配器 (Litestar版)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m
from app.domain.carbon.collectors.base import IDataCollector
from app.domain.metering.reading_facts import LEGACY_FIELD_TO_POINT, MeterReadingFactInput, MeterReadingFactWriter
from app.lib.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class YunjiAdapter(IDataCollector):
    """云集平台 HTTP 轮询适配器"""

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=settings.carbon.YUNJI_API_HOST,
            headers={"API_KEY": settings.carbon.YUNJI_API_KEY, "Content-Type": "application/json"},
            timeout=30.0,
            trust_env=False,
        )

    async def connect(self) -> bool:
        return True

    async def fetch_data(self, **kwargs) -> Any:
        # 获取需要拉取的电表代码
        codes = kwargs.get("codes")
        if not codes:
            # 这里原本在 Django 中是同步 ORM，现在改为通过 kwargs 传入或在 Job 中预取
            # 为了保持适配器独立性，我们假设 Job 层会处理好 codes 发现
            return {"IsSuccess": False, "Message": "No codes provided"}

        start_time = kwargs.get("start_time")
        end_time = kwargs.get("end_time")

        payload = {
            "dateType": "mi15",
            "meterAddress": ",".join(codes),
            "startTime": start_time,
            "endTime": end_time,
            "valueType": "SJZ",
        }

        try:
            r = await self.client.post("/WebApi/NH2/ElectricQuantity", json=payload)
            r.raise_for_status()
            result = r.json()
            result["_meta"] = {"start_time": start_time, "end_time": end_time}
            return result
        except Exception as e:
            logger.error(f"云集：拉取数据异常: {e}")
            return {"IsSuccess": False}

    def normalize(self, raw: Any) -> list[dict]:
        if not raw.get("IsSuccess"):
            logger.error(f"云集：拉取失败，消息：{raw.get('Message')}")
            return []
        meta = raw.get("_meta", {})
        records = []
        for obj in raw.get("Data", []):
            readings = []
            for source_field, (point_code, value_kind) in LEGACY_FIELD_TO_POINT.items():
                readings.append(
                    {
                        "source_point_code": source_field,
                        "source_point_name": source_field,
                        "point_code": point_code,
                        "value_kind": value_kind,
                        "raw_value": obj.get(source_field),
                        "normalized_value": obj.get(source_field),
                    }
                )
            records.append({
                "equipment_id": obj["Address"],
                "readings": readings,
                "reading_time": _parse_datetime(obj.get("ReadingDate")),
                "ammeter_id": obj["AmmeterID"],
                "ammeter_name": obj["AmmeterName"],
                "address": obj["Address"],
                "area_id": obj["AreaID"],
                "area_name": obj["AreaName"],
                "start_time": _parse_datetime(meta.get("start_time")),
                "end_time": _parse_datetime(meta.get("end_time")),
                "data_source": 0,
            })
        return records

    async def save(self, db_session: AsyncSession, normalized_list: list[dict]) -> int:
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
            rows: list[dict] = []
            for source_row in normalized_list:
                address = source_row.get("equipment_id")
                equipment = equipment_by_address.get(address)
                if equipment is None:
                    logger.warning("云集：未找到平台设备，跳过电表 address=%s", address)
                    continue
                row = dict(source_row)
                row["equipment_id"] = equipment.id
                row["team_id"] = equipment.team_id
                rows.append(row)

            if not rows:
                return 0
            writer = MeterReadingFactWriter(db_session)
            facts: list[MeterReadingFactInput] = []
            for row in rows:
                reading_time = row.get("reading_time")
                if reading_time is None:
                    continue
                for reading in row.get("readings", []):
                    if reading.get("normalized_value") is None:
                        continue
                    source_record_id = (
                        f"yunji:{row.get('address')}:{reading_time.isoformat()}:"
                        f"{reading['point_code']}:{reading['value_kind']}"
                    )
                    facts.append(
                        MeterReadingFactInput(
                            source_system="yunji",
                            source_record_id=source_record_id,
                            equipment_id=row["equipment_id"],
                            source_point_code=reading["source_point_code"],
                            source_point_name=reading["source_point_name"],
                            point_code=reading["point_code"],
                            raw_value=reading["raw_value"],
                            normalized_value=reading["normalized_value"],
                            value_kind=reading["value_kind"],
                            reading_time=reading_time,
                            mapping_version="yunji_v1",
                        )
                    )
            inserted = await writer.write_many(facts)
            await db_session.commit()
            logger.info("云集：成功写入 %s 条规范读数", inserted)
            return inserted
        except Exception as e:
            logger.error(f"云集：保存数据失败: {e}")
            await db_session.rollback()
            return 0

    async def sync_device_status(self, db_session: AsyncSession):
        """同步设备状态"""
        # 获取开启的云集设备
        stmt = select(func.coalesce(m.MonitorEquipment.external_device_id, m.MonitorEquipment.code)).where(
            m.MonitorEquipment.supplier == "yj",
            m.MonitorEquipment.is_enable == True
        )
        result = await db_session.execute(stmt)
        codes = [r[0] for r in result.fetchall()]

        if not codes: return

        try:
            r = await self.client.post("/WebApi/NH2/AmmeterBasicInfo", json={"meterAddress": ",".join(codes)})
            jo = r.json()
            if jo["IsSuccess"]:
                for obj in jo["Data"]:
                    # 这里简化为逐个更新，实际生产中可考虑批量更新
                    status = 0 if obj["OnlineState"] else 1
                    await db_session.execute(
                        m.MonitorEquipment.__table__.update()
                        .where(
                            (m.MonitorEquipment.external_device_id == obj["Address"]) |
                            (m.MonitorEquipment.code == obj["Address"])
                        )
                        .values(status=status, trip_state=obj["TripState"])
                    )
                await db_session.commit()
        except Exception as e:
            logger.error(f"云集：同步设备状态异常: {e}")


def _parse_datetime(value: object) -> datetime | None:
    """Normalize Yunji's minute-resolution timestamps for SQLAlchemy DateTime columns."""
    if value is None or isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise ValueError(f"云集时间格式无法识别: {value}")
