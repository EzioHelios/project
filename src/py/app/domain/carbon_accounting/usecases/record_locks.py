from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db import models as m

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CarbonAccountingRecordLockUseCase:
    """Guard Scope activity records that have been captured by locked inventories."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_record_mutable(self, record_type: str, record_id: int) -> None:
        await self.ensure_records_mutable(record_type, [record_id])

    async def ensure_records_mutable(self, record_type: str, record_ids: list[int]) -> None:
        ids = [item for item in record_ids if item is not None]
        if not ids:
            return
        rows = (
            await self._session.execute(
                select(
                    m.CarbonEmissionInventoryItem.record_id,
                    m.CarbonAccountingBatch.id,
                    m.CarbonAccountingBatch.batch_no,
                    m.CarbonAccountingBatch.batch_name,
                )
                .join(m.CarbonAccountingBatch, m.CarbonAccountingBatch.id == m.CarbonEmissionInventoryItem.batch_id)
                .where(
                    m.CarbonEmissionInventoryItem.record_type == record_type,
                    m.CarbonEmissionInventoryItem.record_id.in_(ids),
                    m.CarbonEmissionInventoryItem.included.is_(True),
                    m.CarbonAccountingBatch.status == "locked",
                    m.CarbonAccountingBatch.inventory_status == "locked",
                )
                .order_by(m.CarbonAccountingBatch.id.desc())
            )
        ).all()
        if not rows:
            return
        first = rows[0]
        msg = f"记录已被锁定组织排放清单引用, 不可直接修改或删除; 请通过修订批次处理。锁定批次: {first.batch_no or first.batch_name}"
        raise ValueError(msg)
