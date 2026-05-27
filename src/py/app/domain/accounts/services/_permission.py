from __future__ import annotations

from advanced_alchemy.extensions.litestar import repository, service

from app.db import models as m


class PermissionService(service.SQLAlchemyAsyncRepositoryService[m.Permission]):
    """Handles database operations for permissions."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.Permission]):
        """Permission SQLAlchemy Repository."""

        model_type = m.Permission

    repository_type = Repo
    match_fields = ["code", "name", "module"]
