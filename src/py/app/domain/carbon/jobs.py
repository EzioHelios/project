"""碳管理后台定时任务 (SAQ Jobs)。"""

from __future__ import annotations

# ruff: noqa: DTZ005, DTZ007, PLR0915, RUF001, RUF003, TRY301
import datetime
import logging
from typing import TYPE_CHECKING

from sqlalchemy import func, select

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
            await session.execute(
                select(
                    func.coalesce(m.MonitorEquipment.external_device_id, m.MonitorEquipment.code),
                    m.MonitorEquipment.id,
                    m.MonitorEquipment.team_id,
                )
                .where(
                    m.MonitorEquipment.supplier == "yj",
                    m.MonitorEquipment.is_enable.is_(True),
                )
                .order_by(m.MonitorEquipment.id)
            )
        ).all()

        if not equipment_rows:
            logger.warning("云集：无已启用电表，跳过拉取")
            return

        adapter = YunjiAdapter()
        try:
            for code, equipment_id, team_id in equipment_rows:
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
                    if "429" in str(exc):
                        logger.warning("云集：接口限流，停止本轮剩余电表拉取")
                        break
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
