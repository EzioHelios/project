"""Comprehensive tests for account domain guards."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from litestar.exceptions import PermissionDeniedException
from litestar.security.jwt import Token

from app.domain.accounts.guards import (
    create_access_token,
    current_user_from_token,
    has_permission,
    provide_user,
    requires_active_user,
    requires_permission,
    requires_superuser,
    requires_verified_user,
)
from app.lib import constants
from app.lib.settings import get_settings
from tests.factories import UserFactory

pytestmark = [pytest.mark.anyio, pytest.mark.unit, pytest.mark.auth, pytest.mark.security]

settings = get_settings()


def test_provide_user_returns_request_user() -> None:
    """Test that provide_user returns the user from the request."""
    user = UserFactory.build()
    mock_request = Mock()
    mock_request.user = user

    result = provide_user(mock_request)

    assert result is user
    assert result.email == user.email


def test_provide_user_with_different_user_types() -> None:
    """Test provide_user with different user configurations."""
    # Superuser
    superuser = UserFactory.build(is_superuser=True)
    mock_request = Mock()
    mock_request.user = superuser

    result = provide_user(mock_request)
    assert result.is_superuser is True

    # Inactive user
    inactive_user = UserFactory.build(is_active=False)
    mock_request.user = inactive_user

    result = provide_user(mock_request)
    assert result.is_active is False


def test_active_user_passes() -> None:
    """Test that active user passes the guard."""
    user = UserFactory.build(is_active=True)
    mock_connection = Mock()
    mock_connection.user = user
    mock_handler = Mock()

    # Should not raise
    requires_active_user(mock_connection, mock_handler)


def test_inactive_user_raises_permission_denied() -> None:
    """Test that inactive user raises PermissionDeniedException."""
    user = UserFactory.build(is_active=False)
    mock_connection = Mock()
    mock_connection.user = user
    mock_handler = Mock()

    with pytest.raises(PermissionDeniedException) as exc_info:
        requires_active_user(mock_connection, mock_handler)

    assert "Inactive account" in str(exc_info.value)


def test_verified_user_passes() -> None:
    """Test that verified user passes the guard."""
    user = UserFactory.build(is_verified=True)
    mock_connection = Mock()
    mock_connection.user = user
    mock_handler = Mock()

    # Should not raise
    requires_verified_user(mock_connection, mock_handler)


def test_unverified_user_raises_permission_denied() -> None:
    """Test that unverified user raises PermissionDeniedException."""
    user = UserFactory.build(is_verified=False)
    mock_connection = Mock()
    mock_connection.user = user
    mock_handler = Mock()

    with pytest.raises(PermissionDeniedException) as exc_info:
        requires_verified_user(mock_connection, mock_handler)

    assert "not verified" in str(exc_info.value)


def test_superuser_flag_passes() -> None:
    """Test that user with is_superuser=True passes."""
    user = UserFactory.build(is_superuser=True)
    mock_connection = Mock()
    mock_connection.user = user
    mock_handler = Mock()

    # Should not raise
    requires_superuser(mock_connection, mock_handler)


def test_superuser_role_passes() -> None:
    """Test that user with superuser role passes."""
    # Use a fully mocked user object to avoid SQLAlchemy relationship issues
    mock_role = Mock()
    mock_role.role_name = constants.SUPERUSER_ACCESS_ROLE

    mock_user = Mock()
    mock_user.is_superuser = False
    mock_user.roles = [mock_role]

    mock_connection = Mock()
    mock_connection.user = mock_user
    mock_handler = Mock()

    # Should not raise
    requires_superuser(mock_connection, mock_handler)


def test_non_superuser_raises_permission_denied() -> None:
    """Test that non-superuser raises PermissionDeniedException."""
    mock_user = Mock()
    mock_user.is_superuser = False
    mock_user.roles = []  # No roles

    mock_connection = Mock()
    mock_connection.user = mock_user
    mock_handler = Mock()

    with pytest.raises(PermissionDeniedException) as exc_info:
        requires_superuser(mock_connection, mock_handler)

    assert "Insufficient privileges" in str(exc_info.value)


def test_user_with_non_superuser_role_raises() -> None:
    """Test that user with different role raises PermissionDeniedException."""
    mock_role = Mock()
    mock_role.role_name = "regular_user"

    mock_user = Mock()
    mock_user.is_superuser = False
    mock_user.roles = [mock_role]

    mock_connection = Mock()
    mock_connection.user = mock_user
    mock_handler = Mock()

    with pytest.raises(PermissionDeniedException) as exc_info:
        requires_superuser(mock_connection, mock_handler)

    assert "Insufficient privileges" in str(exc_info.value)


def test_requires_permission_passes_with_granted_permission() -> None:
    """Test that a user with matching permission passes the guard."""
    mock_permission = Mock()
    mock_permission.code = "auth.role.manage"
    mock_role = Mock()
    mock_role.role_name = "role_manager"
    mock_role.permissions = [mock_permission]

    mock_user = Mock()
    mock_user.is_superuser = False
    mock_user.roles = [mock_role]

    mock_connection = Mock()
    mock_connection.user = mock_user
    mock_handler = Mock()

    requires_permission("auth.role.manage")(mock_connection, mock_handler)


def test_requires_permission_denies_without_grant() -> None:
    """Test that a user without permission is denied."""
    mock_role = Mock()
    mock_role.role_name = "role_manager"
    mock_role.permissions = []

    mock_user = Mock()
    mock_user.is_superuser = False
    mock_user.roles = [mock_role]

    mock_connection = Mock()
    mock_connection.user = mock_user
    mock_handler = Mock()

    with pytest.raises(PermissionDeniedException):
        requires_permission("auth.role.manage")(mock_connection, mock_handler)


def test_has_permission_checks_user_roles() -> None:
    """Test permission lookup across user roles."""
    mock_permission = Mock()
    mock_permission.code = "admin.audit.view"
    mock_role = Mock()
    mock_role.role_name = "auditor"
    mock_role.permissions = [mock_permission]

    user = Mock()
    user.is_superuser = False
    user.roles = [mock_role]

    assert has_permission(user, "admin.audit.view") is True
    assert has_permission(user, "auth.role.manage") is False


def test_create_basic_token() -> None:
    """Test creating a basic access token."""
    user_id = str(uuid4())
    email = "test@example.com"

    token_str = create_access_token(user_id=user_id, email=email)

    assert token_str is not None
    assert isinstance(token_str, str)
    assert len(token_str) > 0


def test_token_decodes_correctly() -> None:
    """Test that created token can be decoded."""
    user_id = str(uuid4())
    email = "test@example.com"

    token_str = create_access_token(
        user_id=user_id,
        email=email,
        is_superuser=True,
        is_verified=True,
    )

    # Decode the token
    token = Token.decode(
        encoded_token=token_str,
        secret=settings.app.SECRET_KEY,
        algorithm=settings.app.JWT_ENCRYPTION_ALGORITHM,
    )

    assert token.sub == email
    assert token.extras["user_id"] == user_id
    assert token.extras["is_superuser"] is True
    assert token.extras["is_verified"] is True


def test_token_expiration() -> None:
    """Test that token has correct expiration."""
    user_id = str(uuid4())
    email = "test@example.com"

    before_creation = datetime.now(UTC)
    token_str = create_access_token(user_id=user_id, email=email)
    after_creation = datetime.now(UTC)

    token = Token.decode(
        encoded_token=token_str,
        secret=settings.app.SECRET_KEY,
        algorithm=settings.app.JWT_ENCRYPTION_ALGORITHM,
    )

    # Token should expire in approximately 15 minutes
    expected_min = before_creation + timedelta(minutes=14)
    expected_max = after_creation + timedelta(minutes=16)

    assert expected_min <= token.exp <= expected_max


def test_token_with_password_auth_method() -> None:
    """Test token with password authentication method."""
    user_id = str(uuid4())
    email = "test@example.com"

    token_str = create_access_token(
        user_id=user_id,
        email=email,
        auth_method="password",
    )

    token = Token.decode(
        encoded_token=token_str,
        secret=settings.app.SECRET_KEY,
        algorithm=settings.app.JWT_ENCRYPTION_ALGORITHM,
    )

    assert token.extras["auth_method"] == "password"
    assert token.extras["amr"] == ["pwd"]


def test_token_with_oauth_auth_method() -> None:
    """Test token with OAuth authentication method."""
    user_id = str(uuid4())
    email = "test@example.com"

    token_str = create_access_token(
        user_id=user_id,
        email=email,
        auth_method="google",
    )

    token = Token.decode(
        encoded_token=token_str,
        secret=settings.app.SECRET_KEY,
        algorithm=settings.app.JWT_ENCRYPTION_ALGORITHM,
    )

    assert token.extras["auth_method"] == "google"
    assert token.extras["amr"] == ["google"]


def test_token_with_custom_amr() -> None:
    """Test token with custom AMR (authentication methods reference)."""
    user_id = str(uuid4())
    email = "test@example.com"

    token_str = create_access_token(
        user_id=user_id,
        email=email,
        auth_method="password",
        amr=["pwd", "mfa", "otp"],
    )

    token = Token.decode(
        encoded_token=token_str,
        secret=settings.app.SECRET_KEY,
        algorithm=settings.app.JWT_ENCRYPTION_ALGORITHM,
    )

    assert token.extras["amr"] == ["pwd", "mfa", "otp"]


def test_token_has_unique_jti() -> None:
    """Test that each token has a unique JTI."""
    user_id = str(uuid4())
    email = "test@example.com"

    tokens = []
    for _ in range(5):
        token_str = create_access_token(user_id=user_id, email=email)
        token = Token.decode(
            encoded_token=token_str,
            secret=settings.app.SECRET_KEY,
            algorithm=settings.app.JWT_ENCRYPTION_ALGORITHM,
        )
        tokens.append(token.jti)

    # All JTIs should be unique
    assert len(set(tokens)) == len(tokens)


def test_token_default_values() -> None:
    """Test token with default parameter values."""
    user_id = str(uuid4())
    email = "test@example.com"

    token_str = create_access_token(user_id=user_id, email=email)

    token = Token.decode(
        encoded_token=token_str,
        secret=settings.app.SECRET_KEY,
        algorithm=settings.app.JWT_ENCRYPTION_ALGORITHM,
    )

    assert token.extras["is_superuser"] is False
    assert token.extras["is_verified"] is False
    assert token.extras["auth_method"] == "password"


def test_active_verified_superuser_passes_all() -> None:
    """Test that active, verified superuser passes all guards."""
    user = UserFactory.build(is_active=True, is_verified=True, is_superuser=True)
    mock_connection = Mock()
    mock_connection.user = user
    mock_handler = Mock()

    # All guards should pass
    requires_active_user(mock_connection, mock_handler)
    requires_verified_user(mock_connection, mock_handler)
    requires_superuser(mock_connection, mock_handler)


def test_active_verified_non_superuser_fails_superuser_guard() -> None:
    """Test that active, verified non-superuser fails superuser guard."""
    # Use Mock user to avoid SQLAlchemy relationship issues
    mock_user = Mock()
    mock_user.is_active = True
    mock_user.is_verified = True
    mock_user.is_superuser = False
    mock_user.roles = []

    mock_connection = Mock()
    mock_connection.user = mock_user
    mock_handler = Mock()

    # First two guards should pass
    requires_active_user(mock_connection, mock_handler)
    requires_verified_user(mock_connection, mock_handler)

    # Superuser guard should fail
    with pytest.raises(PermissionDeniedException):
        requires_superuser(mock_connection, mock_handler)


def test_inactive_user_fails_early() -> None:
    """Test that inactive user fails at first guard."""
    user = UserFactory.build(is_active=False, is_verified=True, is_superuser=True)
    mock_connection = Mock()
    mock_connection.user = user
    mock_handler = Mock()

    # Should fail at active user guard
    with pytest.raises(PermissionDeniedException):
        requires_active_user(mock_connection, mock_handler)


def test_token_contains_no_password() -> None:
    """Verify token does not contain password information."""
    user_id = str(uuid4())
    email = "test@example.com"

    token_str = create_access_token(user_id=user_id, email=email)

    # Token should not contain "password" in any form
    assert "password" not in token_str.lower()


def test_different_users_get_different_tokens() -> None:
    """Test that different users get different tokens."""
    user1_id = str(uuid4())
    user2_id = str(uuid4())

    token1 = create_access_token(user_id=user1_id, email="user1@example.com")
    token2 = create_access_token(user_id=user2_id, email="user2@example.com")

    assert token1 != token2


def test_same_user_different_times_get_different_tokens() -> None:
    """Test that same user gets different tokens at different times."""
    user_id = str(uuid4())
    email = "test@example.com"

    token1 = create_access_token(user_id=user_id, email=email)
    token2 = create_access_token(user_id=user_id, email=email)

    # Tokens should differ due to unique JTI and potentially different timestamps
    assert token1 != token2


async def test_current_user_from_token_uses_standalone_service_session() -> None:
    """Auth user lookup must not create or reuse the request-scoped business session."""
    user = Mock()
    user.is_active = True
    token = Token(sub="test@example.com", exp=datetime.now(UTC) + timedelta(minutes=15), jti="test-jti")
    service = Mock()
    service.get_one_or_none = AsyncMock(return_value=user)

    @asynccontextmanager
    async def fake_provide_services(
        *_providers: object,
        session: object | None = None,
        connection: object | None = None,
    ):
        assert session is None
        assert connection is None
        yield (service,)

    from app.domain.accounts import guards as guards_module

    original_provider = guards_module.provide_services
    guards_module.provide_services = fake_provide_services
    try:
        result = await current_user_from_token(token, Mock())
    finally:
        guards_module.provide_services = original_provider

    assert result is user
    service.get_one_or_none.assert_called_once_with(email="test@example.com")
