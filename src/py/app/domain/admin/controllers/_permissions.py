"""Admin permission management controller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, get, put
from litestar.di import Provide
from litestar.exceptions import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import models as m
from app.domain.accounts.deps import (
    provide_permissions_service,
    provide_role_permissions_service,
    provide_roles_service,
)
from app.domain.accounts.guards import requires_permission
from app.domain.accounts.schemas import Permission, Role, RolePermissionsUpdate
from app.domain.admin.deps import provide_audit_log_service

if TYPE_CHECKING:
    from uuid import UUID

    from litestar import Request
    from litestar.security.jwt import Token

    from app.domain.accounts.services import PermissionService, RolePermissionService, RoleService
    from app.domain.admin.services import AuditLogService


class AdminPermissionsController(Controller):
    """Admin permission and role-permission management."""

    tags = ["Admin"]
    path = "/api/admin"
    guards = [requires_permission("auth.role.manage")]
    dependencies = {
        "permissions_service": Provide(provide_permissions_service),
        "roles_service": Provide(provide_roles_service),
        "role_permissions_service": Provide(provide_role_permissions_service),
        "audit_service": Provide(provide_audit_log_service),
    }

    @get(operation_id="AdminListPermissions", path="/permissions")
    async def list_permissions(self, permissions_service: PermissionService) -> list[Permission]:
        """List all permissions."""
        permissions = await permissions_service.list()
        return [
            permissions_service.to_schema(permission, schema_type=Permission)
            for permission in sorted(permissions, key=lambda item: (item.module, item.code))
        ]

    @get(operation_id="AdminGetRolePermissions", path="/roles/{role_id:uuid}/permissions")
    async def get_role_permissions(
        self,
        roles_service: RoleService,
        role_id: UUID,
    ) -> Role:
        """Get a role with its assigned permissions."""
        role = await roles_service.get(role_id, load=[selectinload(m.Role.permissions)])
        return roles_service.to_schema(role, schema_type=Role)

    @put(operation_id="AdminUpdateRolePermissions", path="/roles/{role_id:uuid}/permissions")
    async def update_role_permissions(
        self,
        request: Request[m.User, Token, Any],
        permissions_service: PermissionService,
        roles_service: RoleService,
        role_permissions_service: RolePermissionService,
        audit_service: AuditLogService,
        role_id: UUID,
        data: RolePermissionsUpdate,
    ) -> Role:
        """Replace a role's permissions."""
        role = await roles_service.get(role_id, load=[selectinload(m.Role.permissions)])
        existing_permissions = await permissions_service.list()
        permissions_by_code = {permission.code: permission for permission in existing_permissions}

        resolved_permissions: list[m.Permission] = []
        missing_codes: list[str] = []
        for code in data.permission_codes:
            permission = permissions_by_code.get(code)
            if permission is None:
                missing_codes.append(code)
                continue
            resolved_permissions.append(permission)
        if missing_codes:
            raise HTTPException(status_code=400, detail=f"Unknown permission codes: {', '.join(sorted(set(missing_codes)))}")

        await roles_service.repository.session.execute(
            m.RolePermission.__table__.delete().where(m.RolePermission.role_id == role.id),
        )
        roles_service.repository.session.add_all(
            [m.RolePermission(role_id=role.id, permission_id=permission.id) for permission in resolved_permissions]
        )
        await roles_service.repository.session.commit()
        updated_role = (
            await roles_service.repository.session.execute(
                select(m.Role)
                .options(selectinload(m.Role.permissions))
                .where(m.Role.id == role_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        await audit_service.log_action(
            action="auth.role.permissions.update",
            actor_id=request.user.id,
            actor_email=request.user.email,
            target_type="role",
            target_id=str(role.id),
            target_label=role.slug,
            details={"permission_codes": [permission.code for permission in resolved_permissions]},
            request=request,
        )
        return roles_service.to_schema(updated_role, schema_type=Role)
