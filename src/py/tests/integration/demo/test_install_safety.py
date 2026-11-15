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


@pytest.mark.parametrize("initial_context", ["none", "other_tenant", "bypass"])
async def test_install_guard_binds_postgres_context_before_each_tenant_read(session, monkeypatch, initial_context):
    from sqlalchemy import text

    from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY

    teams = [m.Team(slug=spec.slug, name=spec.name, is_active=True) for spec in TENANTS]
    session.add_all(teams)
    await session.commit()
    expected_ids = [str(team.id) for team in teams]
    if initial_context == "other_tenant":
        session.info[TENANT_ID_SESSION_KEY] = teams[1].id
    elif initial_context == "bypass":
        session.info[TENANT_BYPASS_SESSION_KEY] = True
    # Begin a transaction before the guard, as CLI/session setup can do.
    await session.execute(text("SELECT 1"))
    package = WohengShowcasePackage(session)
    original_counts = package._tenant_counts
    observed = []

    async def checked_counts():
        tenant_id, bypass = (
            await session.execute(
                text("SELECT current_setting('app.tenant_id', true), current_setting('app.tenant_bypass', true)")
            )
        ).one()
        assert tenant_id == expected_ids[len(observed)]
        assert tenant_id == str(session.info[TENANT_ID_SESSION_KEY])
        assert bypass == "false"
        observed.append(tenant_id)
        return await original_counts()

    monkeypatch.setattr(package, "_tenant_counts", checked_counts)
    await package._assert_install_targets_safe()
    assert observed == expected_ids


async def test_demo_role_repairs_verification_grants_without_changing_other_roles(session):
    role = m.Role(slug="woheng-demo-operator", name="沃衡演示运营员")
    other = m.Role(slug="unrelated-viewer", name="其他查看者")
    permission = m.Permission(code="carbon.verification.view", name="查看核查", module="carbon")
    session.add_all([role, other, permission])
    await session.flush()
    session.add(m.RolePermission(role_id=role.id, permission_id=permission.id))
    await session.commit()
    package = WohengShowcasePackage(session)
    for _ in range(2):
        await package._ensure_demo_role_permissions(role)
        await session.commit()
    codes = list(
        (
            await session.scalars(
                select(m.Permission.code)
                .join(m.RolePermission, m.RolePermission.permission_id == m.Permission.id)
                .where(m.RolePermission.role_id == role.id)
            )
        ).all()
    )
    assert len(codes) == len(set(codes))
    assert {
        "carbon.verification.view",
        "carbon.verification.manage",
        "carbon.verification.export",
        "carbon.verification.evidence.manage",
    } <= set(codes)
    assert "system.tasks.view" not in codes
    assert "energy.dictionary.manage" not in codes
    assert not list((await session.scalars(select(m.RolePermission).where(m.RolePermission.role_id == other.id))).all())
