from __future__ import annotations

from uuid import UUID  # noqa: TC003

from advanced_alchemy.extensions.litestar import repository, service

from app.db import models as m


class RolePermissionService(service.SQLAlchemyAsyncRepositoryService[m.RolePermission]):
    """Handles role permission assignments."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.RolePermission]):
        """RolePermission SQLAlchemy Repository."""

        model_type = m.RolePermission

    repository_type = Repo

    async def sync_role_permissions(self, role_id: UUID, permission_ids: list[UUID]) -> list[m.RolePermission]:
        """Replace all permissions for a role."""
        existing = await self.list(m.RolePermission.role_id == role_id)
        if existing:
            await self.delete_many([item.id for item in existing])
        if permission_ids:
            self.repository.session.add_all(
                [m.RolePermission(role_id=role_id, permission_id=permission_id) for permission_id in permission_ids]
            )
        await self.repository.session.commit()
        if not permission_ids:
            return []
        return await self.list(m.RolePermission.role_id == role_id)
