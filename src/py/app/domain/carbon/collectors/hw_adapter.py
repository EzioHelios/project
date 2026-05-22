"""
红外采集 (HW) HTTP API 适配器 (Litestar版)
"""
from __future__ import annotations
import logging
from typing import Any, TYPE_CHECKING
from operator import itemgetter

import httpx
from sqlalchemy import select

from app.db import models as m
from app.domain.carbon.collectors.base import IDataCollector
from app.lib.settings import get_settings

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
settings = get_settings()


class HwAdapter(IDataCollector):
    """红外采集 HTTP 轮询适配器"""

    FIELD_MAPPING = {"3": "zygdn", "4": "fygdn", "5": "zwgdn", "6": "fwgdn"}

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=settings.carbon.HW_API_HOST,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    async def connect(self) -> bool:
        return True

    async def fetch_data(self, **kwargs) -> Any:
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
            return result
        except Exception as e:
            logger.error(f"红外：拉取数据异常: {e}")
            return {"status": 0}

    def normalize(self, raw: Any) -> list[dict]:
        if raw.get("status") != 1:
            logger.error(f"红外：拉取失败，原因：{raw.get('msg')}")
            return []
        meta = raw.get("_meta", {})
        data_list = sorted(raw.get("data", []), key=itemgetter("mid", "fid"))
        rows = []
        for index, obj in enumerate(data_list):
            if index % 4 == 0:
                row = {
                    "zygdn": 0.0, "fygdn": 0.0, "zwgdn": 0.0, "fwgdn": 0.0,
                    "zygdnsz": 0.0, "fygdnsz": 0.0, "zwgdnsz": 0.0, "fwgdnsz": 0.0,
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
                key = self.FIELD_MAPPING[fid]
                val = obj["data"][0] if obj["data"] else 0.0
                row[key] = val
                row[f"{key}sz"] = round(float(val) * float(obj["radio"]), 3)
        return rows

    async def save(self, db_session: AsyncSession, normalized_list: list[dict]) -> int:
        if not normalized_list:
            return 0
        try:
            await db_session.execute(m.AmmeterIndexValue.__table__.insert(), normalized_list)
            await db_session.commit()
            logger.info(f"红外：成功写入 {len(normalized_list)} 条数据")
            return len(normalized_list)
        except Exception as e:
            logger.error(f"红外：保存数据失败: {e}")
            await db_session.rollback()
            return 0

    async def sync_device_status(self, db_session: AsyncSession):
        """同步设备状态"""
        try:
            r = await self.client.get("/Api/Meter", params={"auth": settings.carbon.HW_AUTH_CODE})
            jo = r.json()
            if jo["status"] == 1:
                for obj in jo["data"]:
                    status = 0 if obj["relay_state"] == "1" else 1
                    await db_session.execute(
                        m.MonitorEquipment.__table__.update()
                        .where(
                            (m.MonitorEquipment.external_device_id == obj["address"]) |
                            (m.MonitorEquipment.code == obj["address"])
                        )
                        .values(status=status, trip_state=status)
                    )
                await db_session.commit()
        except Exception as e:
            logger.error(f"红外：同步设备状态异常: {e}")
