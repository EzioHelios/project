"""碳管理后台定时任务 (SAQ Jobs)。
"""
from __future__ import annotations

import datetime
import logging
import random
from typing import TYPE_CHECKING

from sqlalchemy import func, select, text

from app.config import alchemy
from app.db import models as m
from app.domain.carbon.collectors.hw_adapter import HwAdapter
from app.domain.carbon.collectors.yunji_adapter import YunjiAdapter
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY

if TYPE_CHECKING:
    from saq.types import Context

logger = logging.getLogger(__name__)


async def sync_yunji_status(_: Context) -> None:
    """定时同步云集平台电表设备状态。"""
    async with alchemy.get_session() as session:
        session.info[TENANT_BYPASS_SESSION_KEY] = True
        adapter = YunjiAdapter()
        await adapter.sync_device_status(session)


async def pull_yunji_data(_: Context) -> None:
    """定时拉取云集平台电量数值。"""
    async with alchemy.get_session() as session:
        session.info[TENANT_BYPASS_SESSION_KEY] = True
        # 获取需要拉取的电表代码
        stmt = select(func.coalesce(m.MonitorEquipment.external_device_id, m.MonitorEquipment.code)).where(
            m.MonitorEquipment.supplier == "yj",
            m.MonitorEquipment.status == 0
        )
        result = await session.execute(stmt)
        codes = [r[0] for r in result.fetchall()]

        if not codes:
            logger.warning("云集：无在线电表，跳过拉取")
            return

        # 随机抽取 10 台
        sample_codes = random.sample(codes, min(10, len(codes)))

        # 计算拉取时间范围（逻辑参考原 Django tasks.py）
        # 这里简化处理，实际中建议记录上次同步位置
        start_time = (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        adapter = YunjiAdapter()
        await adapter.fetch_and_save(session, codes=sample_codes, start_time=start_time, end_time=end_time)


async def sync_hw_status(_: Context) -> None:
    """定时同步红外平台电表设备状态。"""
    async with alchemy.get_session() as session:
        adapter = HwAdapter()
        await adapter.sync_device_status(session)


async def pull_hw_data(_: Context) -> None:
    """定时拉取红外采集电量数值。"""
    async with alchemy.get_session() as session:
        # 逻辑：拉取过去 24 小时的数据（参考 Django HW_PULL_INTERVAL=24h）
        start_time = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        adapter = HwAdapter()
        await adapter.fetch_and_save(session, start_time=start_time, end_time=end_time)


async def execute_day_alarm_scan(_: Context) -> None:
    """执行用电/发电/碳排放预警扫描。"""
    YD_CPFL_PFYZ = 0.5810
    async with alchemy.get_session() as session:
        # 1. 获取所有预警规则
        stmt = select(m.WarningRule)
        result = await session.execute(stmt)
        wrs = result.scalars().all()

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        yesterday = (datetime.date.today() - datetime.timedelta(days=1))

        for wr in wrs:
            if not wr.table_name: continue

            # 构建查询（由于 table_name 是动态的，继续使用 text）
            field_names = list(wr.range_val.keys()) if wr.range_val else []
            if not field_names: continue

            if wr.event_type == 1: # 设备故障
                sql = f"select {','.join(field_names)},code,id,sector_id from {wr.table_name} "
            elif wr.sector_id:
              # 假设 table_name 视图中有 area_id 字段
              sql = f"select {','.join(field_names)} from {wr.table_name} where day='{yesterday}' and area_id='{wr.sector_id}'"
            else:
              sql = f"select {','.join(field_names)} from {wr.table_name} where day='{yesterday}'"

            try:
                r_set = await session.execute(text(sql))
                rows = r_set.fetchall()

                for r in rows:
                    for i, (field, limit) in enumerate(wr.range_val.items()):
                        val = float(r[i]) if r[i] is not None else 0.0
                        if isinstance(limit, (list, tuple)) and len(limit) == 2:
                            if not (limit[0] <= val <= limit[1]):
                                # 触发预警
                                if wr.event_type == 1:
                                    desc = f"【故障】设备{r[1]} {wr.name} 异常"
                                    event = m.AlarmEvent(rule_id=wr.id, event_desc=desc, event_type=1, equipment_id=r[2], sector_id=r[3], event_time=datetime.datetime.now())
                                    session.add(event)
                                elif wr.event_type == 2: # 用电异常
                                    desc = f"【用电】{wr.name}，当前值 {val} 不在范围 {limit}"
                                    event = m.AlarmEvent(rule_id=wr.id, event_desc=desc, event_type=2, sector_id=wr.sector_id, event_time=datetime.datetime.now())
                                    session.add(event)
                                    # 同时触发碳排放预警
                                    desc2 = f"【碳排放】{wr.name}关联碳排放异常，当前值 {round(val * YD_CPFL_PFYZ, 2)}"
                                    event2 = m.AlarmEvent(rule_id=wr.id, event_desc=desc2, event_type=4, sector_id=wr.sector_id, event_time=datetime.datetime.now())
                                    session.add(event2)
                                elif wr.event_type == 3: # 发电异常
                                    desc = f"【发电】{wr.name}，当前值 {val} 异常"
                                    event = m.AlarmEvent(rule_id=wr.id, event_desc=desc, event_type=3, sector_id=wr.sector_id, event_time=datetime.datetime.now())
                                    session.add(event)
            except Exception as e:
                logger.error(f"预警扫描异常 (Rule: {wr.name}): {e}")

        await session.commit()


async def execute_video_alarm_scan(_: Context) -> None:
    """模拟视频监控预警。"""
    async with alchemy.get_session() as session:
        # 随机从前 90 个视频监控中选 1-2 个产生事件
        stmt = select(m.VideoMonitor).limit(90)
        result = await session.execute(stmt)
        vms = result.scalars().all()
        if not vms: return

        selected = random.sample(vms, min(len(vms), random.randint(1, 2)))
        event_types = {1: "未佩戴安全帽", 2: "烟火", 3: "异常跌倒"}

        for vm in selected:
            et = random.randint(1, 3)
            event = m.VedioAlarmEvent(
                event_type=et,
                event_desc=f"{vm.location} 监控到 {event_types[et]} 行为",
                event_time=datetime.datetime.now(),
                equipment_id=vm.id,
                is_handle=False,
            )
            session.add(event)
        await session.commit()
