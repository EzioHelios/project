from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from litestar.exceptions import PermissionDeniedException
from sqlalchemy import select, text

from app.db import models as m
from app.lib.tenancy import DEFAULT_TENANT_ID, TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY, resolve_tenant_context

pytestmark = pytest.mark.anyio


def _scope_for_user(user: SimpleNamespace, team_id: str | None = None) -> dict:
    headers: list[tuple[bytes, bytes]] = []
    if team_id is not None:
        headers.append((b"x-team-id", team_id.encode()))
    return {"user": user, "headers": headers, "path_params": {}}


def test_resolve_tenant_context_defaults_single_team_user() -> None:
    team_id = uuid4()
    user = SimpleNamespace(
        id=uuid4(),
        is_superuser=False,
        roles=[],
        teams=[SimpleNamespace(team_id=team_id)],
    )

    context = resolve_tenant_context(_scope_for_user(user))

    assert context is not None
    assert context.team_id == team_id


def test_resolve_tenant_context_rejects_non_member_team_header() -> None:
    user = SimpleNamespace(
        id=uuid4(),
        is_superuser=False,
        roles=[],
        teams=[SimpleNamespace(team_id=uuid4())],
    )

    with pytest.raises(PermissionDeniedException):
        resolve_tenant_context(_scope_for_user(user, team_id=str(uuid4())))


async def test_tenant_scoped_queries_require_context(session) -> None:
    team_a = m.Team(name="Tenant A", slug="tenant-a")
    team_b = m.Team(name="Tenant B", slug="tenant-b")
    session.add_all([team_a, team_b])
    await session.flush()

    session.info[TENANT_BYPASS_SESSION_KEY] = True
    session.add_all(
        [
            m.MonitorSector(team_id=team_a.id, code="A", name="Tenant A Sector"),
            m.MonitorSector(team_id=team_b.id, code="B", name="Tenant B Sector"),
        ]
    )
    await session.commit()
    session.info.clear()

    rows_without_context = (await session.scalars(select(m.MonitorSector).order_by(m.MonitorSector.code))).all()
    assert rows_without_context == []

    session.info[TENANT_ID_SESSION_KEY] = team_a.id
    rows_for_team_a = (await session.scalars(select(m.MonitorSector).order_by(m.MonitorSector.code))).all()

    assert [row.code for row in rows_for_team_a] == ["A"]


async def test_tenant_scoped_writes_are_auto_assigned(session) -> None:
    team = m.Team(name="Tenant", slug="tenant")
    session.add(team)
    await session.flush()

    session.info[TENANT_ID_SESSION_KEY] = team.id
    sector = m.MonitorSector(code="AUTO", name="Auto Assigned")
    session.add(sector)
    await session.commit()

    assert sector.team_id == team.id


async def test_bypass_writes_fall_back_to_default_tenant(session) -> None:
    session.add(m.Team(id=DEFAULT_TENANT_ID, name="Default Tenant", slug="default-tenant"))
    await session.flush()

    session.info[TENANT_BYPASS_SESSION_KEY] = True
    sector = m.MonitorSector(code="DEFAULT", name="Default Tenant Assigned")
    session.add(sector)
    await session.flush()

    assert sector.team_id == DEFAULT_TENANT_ID


async def test_tenant_scoped_writes_reject_cross_team_changes(session) -> None:
    team_a = m.Team(name="Tenant A", slug="tenant-a")
    team_b = m.Team(name="Tenant B", slug="tenant-b")
    session.add_all([team_a, team_b])
    await session.flush()

    session.info[TENANT_BYPASS_SESSION_KEY] = True
    sector = m.MonitorSector(team_id=team_a.id, code="A", name="Tenant A Sector")
    session.add(sector)
    await session.commit()
    session.info.clear()

    session.info[TENANT_ID_SESSION_KEY] = team_b.id
    sector.name = "Wrong Tenant Update"

    try:
        await session.commit()
    except PermissionDeniedException:
        await session.rollback()
    else:  # pragma: no cover
        msg = "Expected cross-tenant write to be rejected."
        raise AssertionError(msg)


async def test_postgresql_session_settings_follow_tenant_context(session) -> None:
    team_id = uuid4()
    session.info[TENANT_ID_SESSION_KEY] = team_id

    tenant_setting = await session.scalar(text("select current_setting('app.tenant_id', true)"))
    bypass_setting = await session.scalar(text("select current_setting('app.tenant_bypass', true)"))

    assert tenant_setting == str(team_id)
    assert bypass_setting == "false"


async def test_postgresql_session_settings_follow_bypass_context(session) -> None:
    session.info[TENANT_BYPASS_SESSION_KEY] = True

    tenant_setting = await session.scalar(text("select current_setting('app.tenant_id', true)"))
    bypass_setting = await session.scalar(text("select current_setting('app.tenant_bypass', true)"))

    assert tenant_setting == ""
    assert bypass_setting == "true"
