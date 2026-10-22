"""Template reads must not require, or grant, inventory write permissions."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from litestar.exceptions import PermissionDeniedException

from app.domain.ghg_inventory.controllers.inventory import GhgInventoryController


def _connection(permission_codes: tuple[str, ...]) -> Mock:
    role = SimpleNamespace(
        role_name="inventory_reader",
        permissions=[SimpleNamespace(code=code) for code in permission_codes],
    )
    return Mock(user=SimpleNamespace(is_superuser=False, roles=[role]))


@pytest.mark.parametrize("permission", ["carbon.inventory.view", "carbon.inventory.import"])
def test_template_download_accepts_read_or_import_permission(permission: str) -> None:
    handler = GhgInventoryController.template
    for guard in handler.guards:
        guard(_connection((permission,)), handler)


def test_template_download_denies_unrelated_permissions() -> None:
    handler = GhgInventoryController.template
    with pytest.raises(PermissionDeniedException):
        for guard in handler.guards:
            guard(_connection(("carbon.inventory.export",)), handler)


@pytest.mark.parametrize("handler_name", ["preview", "commit"])
def test_template_reader_cannot_import_inventory(handler_name: str) -> None:
    handler = getattr(GhgInventoryController, handler_name)
    with pytest.raises(PermissionDeniedException):
        for guard in handler.guards:
            guard(_connection(("carbon.inventory.view",)), handler)
