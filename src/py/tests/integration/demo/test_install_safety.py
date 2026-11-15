"""Regression checks for the single full install entry in isolated PostgreSQL."""

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from litestar.exceptions import PermissionDeniedException
from sqlalchemy import select

from app.db import models as m
from app.demo.ops.contracts import DemoExecutionContext
from app.demo.ops.woheng import TENANTS, WohengShowcasePackage
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def user_snapshot(session):
    return list((await session.execute(select(*m.User.__table__.c).order_by(m.User.id))).all())


async def test_full_install_identity_preserves_existing_accounts_and_memberships(session):
    customer = m.Team(slug="customer", name="Customer", is_active=True)
    teams = [m.Team(slug=spec.slug, name=spec.name, is_active=True) for spec in TENANTS]
    users = [
        m.User(
            email=email,
            username=username,
            name="Existing identity",
            hashed_password="existing-password-hash",
            is_superuser=email == "admin@example.com",
            is_active=False,
            is_verified=False,
            is_two_factor_enabled=True,
            totp_secret="existing-totp-secret",
            backup_codes=["existing-backup-hash"],
        )
        for email, username in [
            ("admin@example.com", "admin"),
            ("taizhou@customer.example", "taizhou"),
            ("codex.e2e@local.test", "codex_e2e"),
            ("woheng.mobile@local.test", "woheng_mobile"),
        ]
    ]
    session.add_all([customer, *teams, *users])
    await session.flush()
    memberships = [m.TeamMember(team_id=customer.id, user_id=user.id, role="MEMBER") for user in users]
    session.add_all(memberships)
    await session.commit()
    before = await user_snapshot(session)
    member_before = list((await session.execute(select(*m.TeamMember.__table__.c))).all())
    package = WohengShowcasePackage(session)
    for _ in range(2):
        await package._ensure_standard_accounts()
        await package._ensure_standard_account_memberships()
    assert await user_snapshot(session) == before
    assert (
        list(
            (await session.execute(select(*m.TeamMember.__table__.c).where(m.TeamMember.team_id == customer.id))).all()
        )
        == member_before
    )
    assert not list(
        (await session.scalars(select(m.UserRole).where(m.UserRole.user_id.in_([u.id for u in users[:2]])))).all()
    )
    assert (
        len(
            list(
                (
                    await session.scalars(select(m.TeamMember).where(m.TeamMember.team_id.in_([t.id for t in teams])))
                ).all()
            )
        )
        == 4
    )
    assert not list(
        (
            await session.scalars(
                select(m.TeamMember).where(m.TeamMember.user_id == users[0].id, m.TeamMember.team_id != customer.id)
            )
        ).all()
    )


async def test_new_demo_username_does_not_displace_customer(session):
    user = m.User(email="customer@example.com", username="codex_e2e", hashed_password="unchanged")
    session.add(user)
    await session.commit()
    package = WohengShowcasePackage(session)
    created = await package._ensure_standard_accounts()
    assert user.username == "codex_e2e"
    assert created["codex.e2e@local.test"].username is None
    assert created["codex.e2e@local.test"].is_superuser is False
    assert await session.scalar(select(m.User.id).where(m.User.email == "admin@example.com")) is None


@pytest.mark.parametrize("protected_id", [1, 2])
async def test_full_install_rejects_customer_before_global_writes(session, monkeypatch, protected_id):
    team = m.Team(
        id=UUID(f"00000000-0000-7000-8000-{protected_id:012d}"),
        slug=TENANTS[0].slug,
        name="Customer must not be renamed",
        is_active=True,
    )
    session.add(team)
    await session.commit()
    package = WohengShowcasePackage(session)
    dictionary = AsyncMock()
    accounts = AsyncMock()
    monkeypatch.setattr("app.demo.ops.woheng.ensure_standard_energy_types", dictionary)
    monkeypatch.setattr(package, "_ensure_standard_accounts", accounts)
    with pytest.raises(PermissionDeniedException):
        await package._install(DemoExecutionContext("woheng-showcase", "woheng", apply=True))
    dictionary.assert_not_awaited()
    accounts.assert_not_awaited()
    assert (
        await session.scalar(select(m.Team.name).where(m.Team.slug == TENANTS[0].slug))
        == "Customer must not be renamed"
    )


async def test_full_install_refuses_partial_base_before_writes(session, monkeypatch):
    team = m.Team(slug=TENANTS[0].slug, name=TENANTS[0].name, is_active=True)
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    session.add(m.MonitorSector(team_id=team.id, code="ROOT", name="Existing", level=0, path="/ROOT"))
    await session.flush()
    area = await session.scalar(select(m.MonitorSector))
    session.add(m.MonitorEquipment(team_id=team.id, code="901", name="Keep", sector_id=area.id))
    await session.commit()
    package = WohengShowcasePackage(session)
    dictionary = AsyncMock()
    monkeypatch.setattr("app.demo.ops.woheng.ensure_standard_energy_types", dictionary)
    with pytest.raises(ValueError, match="既有基础数据不完整"):
        await package._install(DemoExecutionContext("woheng-showcase", "woheng", apply=True))
    dictionary.assert_not_awaited()
    assert await session.scalar(select(m.MonitorEquipment.name)) == "Keep"
