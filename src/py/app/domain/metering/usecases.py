from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select

from app.db import models as m


def _utc_now_naive() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class AlarmHandlingUseCase:
    def __init__(self, db_session: Any) -> None:
        self._db_session = db_session

    async def update_alarm_event(self, record_id: int, payload: dict[str, Any]) -> m.AlarmEvent | None:
        obj = await self._db_session.get(m.AlarmEvent, record_id)
        if obj is None:
            return None
        for field, value in payload.items():
            setattr(obj, field, value)
        if obj.status == "resolved":
            obj.is_handle = True
            obj.resolved_at = obj.resolved_at or _utc_now_naive()
        elif obj.status:
            obj.is_handle = obj.status != "open"
        await self._db_session.commit()
        return obj

    async def handle_alarm_event(self, record_id: int) -> m.AlarmEvent | None:
        obj = await self._db_session.get(m.AlarmEvent, record_id)
        if obj is None:
            return None
        obj.status = "resolved"
        obj.resolved_at = _utc_now_naive()
        obj.is_handle = True
        await self._db_session.commit()
        return obj

    async def handle_alarm_events_batch(self, ids: list[int]) -> list[m.AlarmEvent]:
        stmt = select(m.AlarmEvent).where(m.AlarmEvent.is_handle.is_(False))
        if ids:
            stmt = stmt.where(m.AlarmEvent.id.in_(ids))
        items = (await self._db_session.execute(stmt)).scalars().all()
        for item in items:
            item.status = "resolved"
            item.resolved_at = item.resolved_at or _utc_now_naive()
            item.is_handle = True
        await self._db_session.commit()
        return list(items)

    async def handle_video_alarm_event(self, record_id: int) -> m.VedioAlarmEvent | None:
        obj = await self._db_session.get(m.VedioAlarmEvent, record_id)
        if obj is None:
            return None
        obj.is_handle = True
        await self._db_session.commit()
        return obj

    async def handle_video_alarm_events_batch(self, ids: list[int]) -> list[m.VedioAlarmEvent]:
        stmt = select(m.VedioAlarmEvent).where(m.VedioAlarmEvent.is_handle.is_(False))
        if ids:
            stmt = stmt.where(m.VedioAlarmEvent.id.in_(ids))
        items = (await self._db_session.execute(stmt)).scalars().all()
        for item in items:
            item.is_handle = True
        await self._db_session.commit()
        return list(items)
