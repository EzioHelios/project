"""Exercise the actual customer role through the authenticated HTTP application."""

from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import undefer

from app.db import models as m
from app.demo.ops.customer_access import TENANT_SLUGS, provision_customer_access
from app.domain.accounts.business_permissions import CUSTOMER_DEMO_PERMISSIONS, CUSTOMER_DEMO_ROLE
from app.domain.accounts.guards import create_access_token

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def customer(session, client):
    teams = [m.Team(name=slug, slug=slug) for slug in sorted(TENANT_SLUGS)]
    session.add_all(teams)
    session.add_all(m.Permission(code=code, name=code, module="test") for code in CUSTOMER_DEMO_PERMISSIONS)
    await session.commit()
    args = {"username": "customer-demo", "email": "customer@example.com", "password": "Example123!Customer"}
    plan = await provision_customer_access(session, **args)
    assert plan["applied"] is False
    assert await session.scalar(select(func.count()).select_from(m.User)) == 0
    await provision_customer_access(session, **args, apply=True)
    user = await session.scalar(
        select(m.User).options(undefer(m.User.hashed_password)).where(m.User.username == args["username"])
    )
    before = user.hashed_password
    await provision_customer_access(session, **{**args, "password": "Different123!Password"}, apply=True)
    await session.refresh(user, attribute_names=["hashed_password"])
    assert user.hashed_password == before
    assert not user.is_superuser
    assert await session.scalar(select(func.count()).select_from(m.UserRole).where(m.UserRole.user_id == user.id)) == 1
    assert (
        await session.scalar(select(func.count()).select_from(m.TeamMember).where(m.TeamMember.user_id == user.id)) == 2
    )
    token = create_access_token(
        user_id=str(user.id), email=user.email, is_superuser=False, is_verified=True, auth_method="password"
    )
    return user, teams, {"Authorization": f"Bearer {token}", "X-Team-Id": str(teams[0].id)}


async def test_effective_role_and_tenant_scope(customer, client):
    _user, teams, headers = customer
    response = await client.get("/api/me/permissions", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"permissions": sorted(CUSTOMER_DEMO_PERMISSIONS), "isSuperuser": False}
    for team in teams:
        response = await client.get("/api/energy/interval-facts", headers={**headers, "X-Team-Id": str(team.id)})
        assert response.status_code == 200, response.text
    response = await client.get("/api/energy/interval-facts", headers={**headers, "X-Team-Id": str(uuid4())})
    assert response.status_code == 403


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/teams"),
        ("GET", "/api/system/tasks"),
        ("GET", "/api/energy-carbon/monitor/devices"),
        ("GET", "/api/energy-carbon/alerts"),
        ("GET", "/api/mobile/work-orders"),
        ("POST", "/api/teams"),
    ],
)
async def test_excluded_api_denied(customer, client, method, path):
    response = await client.request(method, path, headers=customer[2], json={} if method == "POST" else None)
    assert response.status_code == 403, response.text


async def test_provision_refuses_adopting_existing_user(customer, session):
    user, _, _ = customer
    original_hash = user.hashed_password
    role = await session.scalar(select(m.Role).where(m.Role.slug == CUSTOMER_DEMO_ROLE))
    extra = m.Role(name="Extra", slug="extra")
    session.add(extra)
    await session.flush()
    session.add(m.UserRole(user_id=user.id, role_id=extra.id))
    await session.commit()
    with pytest.raises(ValueError, match="未修改现有账号"):
        await provision_customer_access(session, username=user.username, email=user.email, password=None, apply=True)
    assert user.hashed_password == original_hash
    assert role is not None


async def test_review_cannot_be_written_through_project_crud(customer, client):
    for method, endpoint in [
        ("POST", "/api/carbon/verification/projects"),
        ("PATCH", "/api/carbon/verification/projects/1"),
    ]:
        response = await client.request(method, endpoint, headers=customer[2], json={"conclusion_status": "approved"})
        assert response.status_code == 403


async def test_read_permission_does_not_authorize_writes(customer, client, session):
    role = await session.scalar(select(m.Role).where(m.Role.slug == CUSTOMER_DEMO_ROLE))
    permission = await session.scalar(select(m.Permission).where(m.Permission.code == "energy.consumption.manage"))
    await session.execute(
        delete(m.RolePermission).where(
            m.RolePermission.role_id == role.id, m.RolePermission.permission_id == permission.id
        )
    )
    await session.commit()
    assert (await client.get("/api/energy/interval-facts", headers=customer[2])).status_code == 200
    assert (await client.post("/api/energy/interval-facts", headers=customer[2], json={})).status_code == 403
    assert (await client.post("/api/energy/imports/datasets", headers=customer[2], json={})).status_code == 403
