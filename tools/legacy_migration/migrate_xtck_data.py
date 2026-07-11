"""
从 Django xtck_deploy 数据库迁移基础数据到 litestar-fullstack 碳管理库。

注意：
- 只在 litestar-fullstack 仓库中新增代码，不修改原仓库。
- 迁移逻辑尽量保持简单清晰，保证可以多次执行（先删后导入）。

环境变量：
- OLD_DB_URL：原 xtck_deploy 的 PostgreSQL 连接串。
- NEW_DB_URL：新 litestar-fullstack 使用的 PostgreSQL 连接串
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "py"))

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.db import models as m


async def _create_engine(url: str) -> AsyncEngine:
    """根据 URL 创建 AsyncEngine。"""
    return create_async_engine(url, future=True)


async def _copy_table(
    src_session: AsyncSession,
    dst_session: AsyncSession,
    src_table,
    dst_model,
    pk_field: str = "id",
) -> None:
    """通用表复制工具：先清空目标表，再批量插入。

    参数：
    - src_table: 原库中的 Table 对象
    - dst_model: 新库中的 ORM 模型
    """
    # 1. 读取源数据
    src_result = await src_session.execute(select(src_table))
    rows: Sequence[dict] = src_result.mappings().all()
    if not rows:
        return

    # 2. 清空目标表
    await dst_session.execute(delete(dst_model))

    # 3. 批量插入
    payload = [dict(row) for row in rows]
    await dst_session.execute(insert(dst_model), payload)


async def migrate_core() -> None:
    """迁移核心表：企业、监控区域、监控终端、电表时序、视频监控等。"""
    old_db_url = os.environ.get("OLD_DB_URL")
    new_db_url = os.environ.get("NEW_DB_URL")
    if not old_db_url or not new_db_url:
        raise RuntimeError("请先设置环境变量 OLD_DB_URL 和 NEW_DB_URL 后再运行迁移脚本。")

    old_engine = await _create_engine(old_db_url)
    new_engine = await _create_engine(new_db_url)

    OldSession = async_sessionmaker(old_engine, expire_on_commit=False)
    NewSession = async_sessionmaker(new_engine, expire_on_commit=False)

    async with OldSession() as old_sess, NewSession() as new_sess:
        # 反射原库表结构
        from sqlalchemy import MetaData

        metadata = MetaData()
        metadata.reflect(bind=old_engine.sync_engine)  # type: ignore[arg-type]

        enterprise_table = metadata.tables.get("dataapp_enterpriseinfo")
        sector_table = metadata.tables.get("dataapp_monitorsector")
        sector_photo_table = metadata.tables.get("dataapp_monitorsectorphoto")
        equipment_table = metadata.tables.get("dataapp_monitorequipment")
        ammeter_table = metadata.tables.get("dataapp_ammeterindexvalue")
        video_table = metadata.tables.get("dataapp_videomonitor")
        emission_factor_table = metadata.tables.get("dataapp_emissionfactor")

        if enterprise_table is not None:
            await _copy_table(old_sess, new_sess, enterprise_table, m.EnterpriseInfo)
        if sector_table is not None:
            await _copy_table(old_sess, new_sess, sector_table, m.MonitorSector)
        if sector_photo_table is not None:
            await _copy_table(old_sess, new_sess, sector_photo_table, m.MonitorSectorPhoto)
        if equipment_table is not None:
            await _copy_table(old_sess, new_sess, equipment_table, m.MonitorEquipment)
        if ammeter_table is not None:
            await _copy_table(old_sess, new_sess, ammeter_table, m.AmmeterIndexValue)
        if video_table is not None:
            await _copy_table(old_sess, new_sess, video_table, m.VideoMonitor)
        if emission_factor_table is not None:
            await _copy_table(old_sess, new_sess, emission_factor_table, m.EmissionFactor)
        await new_sess.commit()

    await old_engine.dispose()
    await new_engine.dispose()


def main() -> None:
    """脚本入口。"""
    asyncio.run(migrate_core())


if __name__ == "__main__":
    main()
