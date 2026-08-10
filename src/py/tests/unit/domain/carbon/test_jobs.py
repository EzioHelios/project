from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import select

from app.db import models as m
from app.domain.carbon import jobs
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class _Client:
    async def aclose(self) -> None:
        return None


class _Adapter:
    responses: list[dict[str, Any]] = []
    calls: list[str] = []

    def __init__(self) -> None:
        self.client = _Client()

    async def fetch_data(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs["codes"][0])
        return self.responses.pop(0)

    def normalize(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def save(self, *_args: Any, **_kwargs: Any) -> int:
        return 0


async def _prepare_job(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    responses: list[dict[str, Any]],
) -> UUID:
    session.info[TENANT_BYPASS_SESSION_KEY] = True
    team = m.Team(name="云集采集租户", slug="yunji-job-tenant")
    session.add(team)
    await session.flush()
    meters = [
        m.MonitorEquipment(
            team_id=team.id,
            code=f"YJ-JOB-{number}",
            external_device_id=f"YJ-JOB-{number}",
            name=f"云集电表{number}",
            supplier="yj",
            is_enable=True,
        )
        for number in (1, 2)
    ]
    session.add_all(meters)
    await session.commit()

    @asynccontextmanager
    async def get_session() -> AsyncIterator[AsyncSession]:
        yield session

    _Adapter.responses = list(responses)
    _Adapter.calls = []
    monkeypatch.setattr(jobs.alchemy, "get_session", get_session)
    monkeypatch.setattr(jobs, "YunjiAdapter", _Adapter)
    return team.id


@pytest.mark.anyio
async def test_pull_yunji_data_continues_after_one_meter_rolls_back(session, monkeypatch) -> None:
    team_id = await _prepare_job(
        session,
        monkeypatch,
        [
            {"IsSuccess": False, "Message": "temporary upstream error"},
            {"IsSuccess": True, "Data": []},
        ],
    )

    await jobs.pull_yunji_data({})

    assert _Adapter.calls == ["YJ-JOB-1", "YJ-JOB-2"]
    cursors = (
        await session.scalars(
            select(m.MeteringAcquisitionCursor)
            .where(m.MeteringAcquisitionCursor.team_id == team_id)
            .order_by(m.MeteringAcquisitionCursor.equipment_id)
        )
    ).all()
    assert [cursor.status for cursor in cursors] == ["failed", "ready"]


@pytest.mark.anyio
async def test_pull_yunji_data_stops_remaining_requests_when_rate_limited(session, monkeypatch) -> None:
    await _prepare_job(
        session,
        monkeypatch,
        [
            {"IsSuccess": False, "Message": "429 Too Many Requests"},
            {"IsSuccess": True, "Data": []},
        ],
    )

    await jobs.pull_yunji_data({})

    assert _Adapter.calls == ["YJ-JOB-1"]
