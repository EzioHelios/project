"""碳管理后台定时任务 (SAQ Jobs)。"""

from __future__ import annotations

# ruff: noqa: B007, BLE001, DTZ005, DTZ007, DTZ011, F841, G004, N806, PLR0915, PLR2004, RUF001, RUF003, S311, S608, SIM102, TRY301, TRY400
import datetime
import logging
import random
from typing import TYPE_CHECKING

from sqlalchemy import func, select, text

from app.config import alchemy
from app.db import models as m
from app.domain.carbon.collectors.hw_adapter import HwAdapter
from app.domain.carbon.collectors.yunji_adapter import YunjiAdapter
from app.lib.settings import get_settings
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
    """按每表游标续拉全部已启用的云集电表。"""
    settings = get_settings().carbon
    now = datetime.datetime.now()
    configured_start = datetime.datetime.strptime(settings.YUNJI_PULL_START_TIME, "%Y-%m-%d %H:%M:%S")
    overlap = datetime.timedelta(minutes=settings.YUNJI_PULL_OVERLAP_MINUTES)
    max_window = datetime.timedelta(hours=settings.YUNJI_PULL_MAX_WINDOW_HOURS)
    async with alchemy.get_session() as session:
        session.info[TENANT_BYPASS_SESSION_KEY] = True
        equipment_rows = (
            await session.scalars(
                select(m.MonitorEquipment).where(
                    m.MonitorEquipment.supplier == "yj",
                    m.MonitorEquipment.is_enable.is_(True),
                )
            )
        ).all()

        if not equipment_rows:
            logger.warning("云集：无已启用电表，跳过拉取")
            return

        adapter = YunjiAdapter()
        try:
            for equipment in equipment_rows:
                code = equipment.external_device_id or equipment.code
                equipment_id = equipment.id
                team_id = equipment.team_id
                cursor = await session.scalar(
                    select(m.MeteringAcquisitionCursor).where(
                        m.MeteringAcquisitionCursor.team_id == team_id,
                        m.MeteringAcquisitionCursor.source_system == "yunji",
                        m.MeteringAcquisitionCursor.equipment_id == equipment_id,
                    )
                )
                if cursor is None:
                    latest_fact_time = await session.scalar(
                        select(func.max(m.MeterReadingFact.reading_time)).where(
                            m.MeterReadingFact.team_id == team_id,
                            m.MeterReadingFact.source_system == "yunji",
                            m.MeterReadingFact.equipment_id == equipment_id,
                        )
                    )
                    cursor = m.MeteringAcquisitionCursor(
                        team_id=team_id,
                        source_system="yunji",
                        equipment_id=equipment_id,
                        last_success_time=latest_fact_time,
                        status="ready",
                    )
                    session.add(cursor)

                start_time = max(
                    configured_start,
                    (cursor.last_success_time - overlap) if cursor.last_success_time else configured_start,
                )
                end_time = min(now, start_time + max_window)
                if end_time <= start_time:
                    continue

                cursor.last_attempt_time = now
                cursor.status = "pulling"
                cursor.error_detail = None
                await session.flush()
                try:
                    raw = await adapter.fetch_data(
                        codes=[code],
                        start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
                        end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                    if not raw.get("IsSuccess"):
                        msg = str(raw.get("Message") or "Yunji API returned an unsuccessful response")
                        raise RuntimeError(msg)
                    normalized_rows = adapter.normalize(raw)
                    for row in normalized_rows:
                        row["team_id"] = team_id
                    inserted = await adapter.save(
                        session,
                        normalized_rows,
                        auto_commit=False,
                        raise_on_error=True,
                    )
                    cursor.last_success_time = end_time
                    cursor.source_watermark = end_time.isoformat()
                    cursor.status = "ready"
                    cursor.cursor_metadata = {"last_inserted_facts": inserted, "window_start": start_time.isoformat()}
                    await session.commit()
                except Exception as exc:
                    await session.rollback()
                    failed_cursor = await session.scalar(
                        select(m.MeteringAcquisitionCursor).where(
                            m.MeteringAcquisitionCursor.team_id == team_id,
                            m.MeteringAcquisitionCursor.source_system == "yunji",
                            m.MeteringAcquisitionCursor.equipment_id == equipment_id,
                        )
                    )
                    if failed_cursor is None:
                        failed_cursor = m.MeteringAcquisitionCursor(
                            team_id=team_id,
                            source_system="yunji",
                            equipment_id=equipment_id,
                        )
                        session.add(failed_cursor)
                    failed_cursor.last_attempt_time = now
                    failed_cursor.status = "failed"
                    failed_cursor.error_detail = str(exc)[:4000]
                    await session.commit()
                    logger.exception("云集：电表 %s 拉取失败", code)
        finally:
            await adapter.client.aclose()


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
        yesterday = datetime.date.today() - datetime.timedelta(days=1)

        for wr in wrs:
            if not wr.table_name:
                continue

            # 构建查询（由于 table_name 是动态的，继续使用 text）
            field_names = list(wr.range_val.keys()) if wr.range_val else []
            if not field_names:
                continue

            if wr.event_type == 1:  # 设备故障
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
                                    event = m.AlarmEvent(
                                        rule_id=wr.id,
                                        event_desc=desc,
                                        event_type=1,
                                        equipment_id=r[2],
                                        sector_id=r[3],
                                        event_time=datetime.datetime.now(),
                                    )
                                    session.add(event)
                                elif wr.event_type == 2:  # 用电异常
                                    desc = f"【用电】{wr.name}，当前值 {val} 不在范围 {limit}"
                                    event = m.AlarmEvent(
                                        rule_id=wr.id,
                                        event_desc=desc,
                                        event_type=2,
                                        sector_id=wr.sector_id,
                                        event_time=datetime.datetime.now(),
                                    )
                                    session.add(event)
                                    # 同时触发碳排放预警
                                    desc2 = f"【碳排放】{wr.name}关联碳排放异常，当前值 {round(val * YD_CPFL_PFYZ, 2)}"
                                    event2 = m.AlarmEvent(
                                        rule_id=wr.id,
                                        event_desc=desc2,
                                        event_type=4,
                                        sector_id=wr.sector_id,
                                        event_time=datetime.datetime.now(),
                                    )
                                    session.add(event2)
                                elif wr.event_type == 3:  # 发电异常
                                    desc = f"【发电】{wr.name}，当前值 {val} 异常"
                                    event = m.AlarmEvent(
                                        rule_id=wr.id,
                                        event_desc=desc,
                                        event_type=3,
                                        sector_id=wr.sector_id,
                                        event_time=datetime.datetime.now(),
                                    )
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
        if not vms:
            return

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
