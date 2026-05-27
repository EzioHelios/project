"""Admin domain controllers."""

from app.domain.admin.controllers._audit import AuditController
from app.domain.admin.controllers._dashboard import DashboardController
from app.domain.admin.controllers._permissions import AdminPermissionsController
from app.domain.admin.controllers._teams import AdminTeamsController
from app.domain.admin.controllers._users import AdminUsersController

__all__ = (
    "AdminPermissionsController",
    "AdminTeamsController",
    "AdminUsersController",
    "AuditController",
    "DashboardController",
)
