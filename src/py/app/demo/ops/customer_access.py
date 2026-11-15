"""Provision the customer role using ordinary RBAC and tenant memberships."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, or_, select

from app.db import models as m
from app.domain.accounts.business_permissions import CUSTOMER_DEMO_PERMISSIONS, CUSTOMER_DEMO_ROLE
from app.lib.crypt import get_password_hash
from app.lib.validation import validate_email, validate_password_strength, validate_username

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

TENANT_SLUGS = frozenset({"woheng-taizhou-production-base", "woheng-huzhou-production-base"})


async def provision_customer_access(
    session: AsyncSession,
    *,
    username: str,
    email: str,
    password: str | None,
    apply: bool = False,
) -> dict:
    """Create one limited account, never adopt or reset an unrelated existing user."""
    username = validate_username(username)
    email = validate_email(email)
    teams = list((await session.scalars(select(m.Team).where(m.Team.slug.in_(TENANT_SLUGS)))).all())
    if {team.slug for team in teams} != TENANT_SLUGS:
        message = "沃衡两个基地尚未初始化"
        raise ValueError(message)
    permissions = list(
        (await session.scalars(select(m.Permission).where(m.Permission.code.in_(CUSTOMER_DEMO_PERMISSIONS)))).all()
    )
    missing = CUSTOMER_DEMO_PERMISSIONS - {p.code for p in permissions}
    if missing:
        message = f"缺少业务权限, 请先升级数据库: {sorted(missing)}"
        raise ValueError(message)
    role = await session.scalar(select(m.Role).where(m.Role.slug == CUSTOMER_DEMO_ROLE))
    users = list(
        (await session.scalars(select(m.User).where(or_(m.User.username == username, m.User.email == email)))).all()
    )
    user = users[0] if users else None
    if user:
        assigned = set((await session.scalars(select(m.UserRole.role_id).where(m.UserRole.user_id == user.id))).all())
        if (
            len(users) != 1
            or user.username != username
            or user.email != email
            or user.is_superuser
            or not role
            or assigned != {role.id}
        ):
            message = "账号已存在且不属于客户演示角色; 未修改现有账号"
            raise ValueError(message)
        memberships = list((await session.scalars(select(m.TeamMember).where(m.TeamMember.user_id == user.id))).all())
        if {x.team_id for x in memberships} != {x.id for x in teams} or any(
            x.is_owner or x.role != m.TeamRoles.MEMBER for x in memberships
        ):
            message = "已有客户账号的租户权限与目标不符; 请先人工核查"
            raise ValueError(message)
    result = {
        "username": username,
        "role": CUSTOMER_DEMO_ROLE,
        "tenants": sorted(TENANT_SLUGS),
        "permission_count": len(permissions),
        "created": user is None,
        "applied": apply,
    }
    if not apply:
        return result
    if user is None:
        if not password:
            message = "新账号需要通过环境变量提供密码"
            raise ValueError(message)
        validate_password_strength(password)
    if role is None:
        role = m.Role(slug=CUSTOMER_DEMO_ROLE, name="能碳客户演示", description="十二项能碳功能及配套数据维护")
        session.add(role)
        await session.flush()
    await session.execute(delete(m.RolePermission).where(m.RolePermission.role_id == role.id))
    session.add_all(m.RolePermission(role_id=role.id, permission_id=p.id) for p in permissions)
    if user is None:
        user = m.User(
            username=username,
            email=email,
            name="客户演示",
            is_active=True,
            is_verified=True,
            is_superuser=False,
            hashed_password=await get_password_hash(password),
        )
        session.add(user)
        await session.flush()
        session.add(m.UserRole(user_id=user.id, role_id=role.id))
        session.add_all(
            m.TeamMember(user_id=user.id, team_id=t.id, role=m.TeamRoles.MEMBER, is_owner=False) for t in teams
        )
    await session.commit()
    return result
