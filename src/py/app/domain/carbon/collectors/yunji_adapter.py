"""
云集 (Yunji) HTTP API 适配器 (Litestar版)
"""
from __future__ import annotations
import logging
from typing import Any, TYPE_CHECKING

import httpx
from sqlalchemy import select, func

from app.db import models as m
from app.domain.carbon.collectors.base import IDataCollector
from app.lib.settings import get_settings

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
settings = get_settings()


class YunjiAdapter(IDataCollector):
    """云集平台 HTTP 轮询适配器"""

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=settings.carbon.YUNJI_API_HOST,
            headers={"API_KEY": settings.carbon.YUNJI_API_KEY, "Content-Type": "application/json"},
            timeout=30.0,
        )

    async def connect(self) -> bool:
        return True

    async def fetch_data(self, **kwargs) -> Any:
        # 获取需要拉取的电表代码
        codes = kwargs.get("codes")
        if codes is None:
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
            records.append({
                "equipment_id": obj["Address"],
                "zygdn": obj["ZYGDN"],
                "fygdn": obj["FYGDN"],
                "zwgdn": obj["ZWGDN"],
                "fwgdn": obj["FWGDN"],
                "zygdnsz": obj["ZYGDNSZ"],
                "fygdnsz": obj["FYGDNSZ"],
                "zwgdnsz": obj["ZWGDNSZ"],
                "fwgdnsz": obj["FWGDNSZ"],
                "reading_time": obj["ReadingDate"],
                "ammeter_id": obj["AmmeterID"],
                "ammeter_name": obj["AmmeterName"],
                "address": obj["Address"],
                "area_id": obj["AreaID"],
                "area_name": obj["AreaName"],
                "start_time": meta.get("start_time"),
                "end_time": meta.get("end_time"),
                "data_source": 0,
            })
        return records

    async def save(self, db_session: AsyncSession, normalized_list: list[dict]) -> int:
        if not normalized_list:
            return 0
        try:
            # 批量插入
            await db_session.execute(m.AmmeterIndexValue.__table__.insert(), normalized_list)
            await db_session.commit()
            logger.info(f"云集：成功写入 {len(normalized_list)} 条数据")
            return len(normalized_list)
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
