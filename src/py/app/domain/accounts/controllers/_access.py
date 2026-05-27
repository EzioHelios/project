"""User Access Controllers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Any, cast
from uuid import UUID

import msgspec
from advanced_alchemy.utils.text import slugify
from litestar import Controller, Request, Response, delete, get, post
from litestar.di import Provide
from litestar.exceptions import ClientException, NotAuthorizedException, PermissionDeniedException
from litestar.params import Dependency, Parameter
from litestar.security.jwt import OAuth2Login
from litestar.security.jwt import Token as JWTToken
from sqlalchemy.orm import selectinload

from app.db import models as m
from app.domain.admin.deps import provide_audit_log_service
from app.domain.admin.services import AuditLogService
from app.domain.accounts.deps import (
    provide_email_verification_service,
    provide_password_reset_service,
    provide_roles_service,
    provide_users_service,
)
from app.domain.accounts.guards import ACCESS_TOKEN_EXPIRATION, auth, create_access_token
from app.domain.accounts.schemas import (
    AccountLogin,
    AccountRegister,
    ActiveSession,
    ForgotPasswordRequest,
    LoginMfaChallenge,
    PasswordResetComplete,
    PasswordResetSent,
    ResetPasswordRequest,
    ResetTokenValidation,
    User,
)
from app.domain.accounts.security import (
    AltchaSentinelProvider,
    LoginRiskService,
    provide_human_verification_provider,
    provide_login_risk_service,
)
from app.domain.accounts.services import RefreshTokenService
from app.lib.deps import create_service_dependencies
from app.lib.schema import Message
from app.lib.validation import PasswordValidationError, validate_password_strength

if TYPE_CHECKING:
    from advanced_alchemy.filters import FilterTypes
    from advanced_alchemy.service.pagination import OffsetPagination
    from litestar.security.jwt import Token

    from app.domain.accounts.services import (
        PasswordResetService,
        RoleService,
        UserService,
    )
    from app.lib.email import AppEmailService
    from app.lib.settings import AppSettings

logger = logging.getLogger(__name__)

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_MAX_AGE = 7 * 24 * 60 * 60
ACCESS_TOKEN_MAX_AGE = int(ACCESS_TOKEN_EXPIRATION.total_seconds())


async def _parse_login_payload(request: Request[m.User, Token, Any]) -> AccountLogin:
    content_type = request.headers.get("content-type", "")
    raw_payload: dict[str, Any]
    if "application/json" in content_type:
        raw_payload = cast("dict[str, Any]", await request.json())
    else:
        form = await request.form()
        raw_payload = {key: form.get(key) for key in form}

    if "human_verification" in raw_payload and "humanVerification" not in raw_payload:
        raw_payload["humanVerification"] = raw_payload.pop("human_verification")

    if "humanVerification" not in raw_payload:
        provider = raw_payload.pop("human_verification_provider", None) or raw_payload.pop("humanVerificationProvider", None)
        payload = (
            raw_payload.pop("human_verification_payload", None)
            or raw_payload.pop("humanVerificationPayload", None)
            or raw_payload.pop("altcha", None)
        )
        if provider or payload:
            raw_payload["humanVerification"] = {
                "provider": provider or "altcha-sentinel",
                "payload": payload,
            }

    try:
        return msgspec.convert(raw_payload, type=AccountLogin)
    except msgspec.ValidationError as exc:
        raise ClientException(detail=str(exc), status_code=400) from exc


def _client_ip(request: Request[m.User, Token, Any]) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def _set_auth_cookies(
    response: Response[Any],
    *,
    settings: AppSettings,
    access_token: str,
    refresh_token: str | None = None,
) -> Response[Any]:
    response.set_cookie(
        key=auth.key,
        value=auth.format_auth_header(access_token),
        max_age=ACCESS_TOKEN_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    if refresh_token is not None:
        response.set_cookie(
            key=REFRESH_COOKIE_NAME,
            value=refresh_token,
            max_age=REFRESH_TOKEN_MAX_AGE,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite="strict",
            path="/api/access",
        )
    return response


async def _log_auth_event(
    audit_service: AuditLogService,
    request: Request[m.User, Token, Any],
    *,
    action: str,
    actor_id: UUID | None = None,
    actor_email: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    target_label: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Record an authentication or account security audit event."""
    await audit_service.log_action(
        action=action,
        actor_id=actor_id,
        actor_email=actor_email,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        details=details,
        request=request,
    )


class AccessController(Controller):
    """User login and registration."""

    tags = ["Access"]
    dependencies = create_service_dependencies(
        RefreshTokenService,
        key="refresh_token_service",
        load=[selectinload(m.RefreshToken.user)],
        error_messages={
            "duplicate_key": "Refresh token already exists.",
            "integrity": "Refresh token operation failed.",
        },
        filters={
            "pagination_type": "limit_offset",
            "pagination_size": 25,
            "created_at": True,
            "sort_field": "created_at",
            "sort_order": "desc",
        },
    ) | {
        "users_service": Provide(provide_users_service),
        "roles_service": Provide(provide_roles_service),
        "verification_service": Provide(provide_email_verification_service),
        "password_reset_service": Provide(provide_password_reset_service),
        "audit_service": Provide(provide_audit_log_service),
        "login_risk_service": Provide(provide_login_risk_service, sync_to_thread=False),
        "human_verification_provider": Provide(provide_human_verification_provider, sync_to_thread=False),
    }

    @post(operation_id="AccountLogin", path="/api/access/login", exclude_from_auth=True, security=[])
    async def login(  # noqa: D417
        self,
        request: Request[m.User, Token, Any],
        users_service: UserService,
        refresh_token_service: RefreshTokenService,
        audit_service: AuditLogService,
        login_risk_service: LoginRiskService,
        human_verification_provider: AltchaSentinelProvider | None,
        settings: AppSettings,
    ) -> Response[OAuth2Login] | Response[LoginMfaChallenge]:
        """Authenticate a user.

        If MFA is enabled, returns a response indicating MFA is required
        with a challenge token in a cookie. Otherwise, returns full OAuth2 tokens.

        Args:
            request: The HTTP request
            users_service: User Service
            refresh_token_service: Refresh Token Service
            settings: Application settings

        Returns:
            OAuth2 Login Response with refresh token cookie, or MFA challenge
        """
        data = await _parse_login_payload(request)
        client_ip = _client_ip(request)
        requires_human_verification = human_verification_provider is not None and await login_risk_service.requires_human_verification(
            data.username, client_ip
        )

        if requires_human_verification:
            if not data.human_verification:
                raise ClientException(detail="human_verification_required", status_code=400)
            if data.human_verification.provider != "altcha-sentinel":
                raise ClientException(detail="Unsupported human verification provider", status_code=400)
            verification = await human_verification_provider.verify(
                data.human_verification.payload,
                request_origin=str(request.base_url),
            )
            if not verification.verified:
                await login_risk_service.record_failure(data.username, client_ip)
                await _log_auth_event(
                    audit_service,
                    request,
                    action="auth.login.failed",
                    actor_email=data.username,
                    target_type="user",
                    target_label=data.username,
                    details={"reason": verification.reason or "human_verification_failed"},
                )
                raise ClientException(detail="human_verification_failed", status_code=403)

        try:
            user = await users_service.authenticate(data.username, data.password)
        except PermissionDeniedException:
            failure_count = await login_risk_service.record_failure(data.username, client_ip)
            await _log_auth_event(
                audit_service,
                request,
                action="auth.login.failed",
                actor_email=data.username,
                target_type="user",
                target_label=data.username,
                details={"reason": "invalid_credentials", "failure_count": failure_count},
            )
            if human_verification_provider is not None and failure_count >= settings.LOGIN_RISK_THRESHOLD:
                raise ClientException(detail="human_verification_required", status_code=400) from None
            raise

        await login_risk_service.clear_failures(data.username, client_ip)

        if user.is_two_factor_enabled and user.totp_secret:
            mfa_challenge_token = JWTToken(
                sub=user.email,
                exp=datetime.now(UTC) + timedelta(minutes=5),
                aud="mfa_verification",
                extras={
                    "type": "mfa_challenge",
                    "user_id": str(user.id),
                },
            )
            encoded_challenge = mfa_challenge_token.encode(
                secret=settings.SECRET_KEY,
                algorithm=settings.JWT_ENCRYPTION_ALGORITHM,
            )

            response = Response(
                LoginMfaChallenge(
                    mfa_required=True,
                    message="MFA verification required",
                ),
                status_code=200,
            )
            response.set_cookie(
                key="mfa_challenge",
                value=encoded_challenge,
                max_age=300,
                httponly=True,
                secure=settings.COOKIE_SECURE,
                samesite="lax",
                path="/api/mfa",
            )
            return response

        device_info = request.headers.get("user-agent", "")[:255] if request.headers.get("user-agent") else None

        raw_refresh_token, _ = await refresh_token_service.create_refresh_token(
            user_id=user.id,
            device_info=device_info,
        )

        access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            is_superuser=users_service.is_superuser(user),
            is_verified=user.is_verified,
            auth_method="password",
            amr=["pwd"],
        )
        response = Response(
            OAuth2Login(
                access_token=access_token,
                token_type="Bearer",  # noqa: S106
                refresh_token=raw_refresh_token,
                expires_in=ACCESS_TOKEN_MAX_AGE,
            ),
            status_code=201,
        )
        await _log_auth_event(
            audit_service,
            request,
            action="auth.login.success",
            actor_id=user.id,
            actor_email=user.email,
            target_type="user",
            target_id=str(user.id),
            target_label=user.email,
            details={"auth_method": "password"},
        )
        return _set_auth_cookies(response, settings=settings, access_token=access_token, refresh_token=raw_refresh_token)

    @post(operation_id="AccountLogout", path="/api/access/logout", exclude_from_auth=True, security=[])
    async def logout(
        self,
        request: Request[m.User, Token, Any],
        refresh_token_service: RefreshTokenService,
        users_service: UserService,
        audit_service: AuditLogService,
    ) -> Response[Message]:
        """Account Logout.

        Revokes the current refresh token family and clears cookies.

        Args:
            request: Request
            refresh_token_service: Refresh Token Service

        Returns:
            Logout Response
        """
        if raw_refresh_token := request.cookies.get(REFRESH_COOKIE_NAME):
            token_hash = refresh_token_service.hash_token(raw_refresh_token)
            if refresh_token := await refresh_token_service.get_one_or_none(token_hash=token_hash):
                await refresh_token_service.revoke_token_family(refresh_token.family_id)
                user = await users_service.get_one_or_none(id=refresh_token.user_id)
                if user is not None:
                    await _log_auth_event(
                        audit_service,
                        request,
                        action="auth.logout",
                        actor_id=user.id,
                        actor_email=user.email,
                        target_type="session_family",
                        target_id=str(refresh_token.family_id),
                        target_label=user.email,
                    )

        request.cookies.pop(auth.key, None)
        request.clear_session()
        response = Response(Message(message="OK"), status_code=200)
        response.delete_cookie(auth.key, path="/")
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/access")
        response.delete_cookie("mfa_challenge", path="/api/mfa")
        return response

    @post(operation_id="TokenRefresh", path="/api/access/refresh", exclude_from_auth=True, security=[])
    async def refresh_token(
        self,
        request: Request[m.User, Token, Any],
        refresh_token_service: RefreshTokenService,
        users_service: UserService,
        audit_service: AuditLogService,
        settings: AppSettings,
    ) -> Response[OAuth2Login]:
        """Refresh access token using refresh token.

        Implements token rotation - the old refresh token is revoked
        and a new one is issued.

        Args:
            request: Request with refresh token cookie
            refresh_token_service: Refresh Token Service
            users_service: User Service
            settings: Application settings

        Returns:
            New access token with rotated refresh token cookie

        Raises:
            NotAuthorizedException: If refresh token is invalid or expired
        """
        if not (raw_refresh_token := request.cookies.get(REFRESH_COOKIE_NAME)):
            raise NotAuthorizedException(detail="No refresh token provided")

        device_info = request.headers.get("user-agent", "")[:255] if request.headers.get("user-agent") else None

        new_raw_token, new_token_model = await refresh_token_service.rotate_refresh_token(
            raw_token=raw_refresh_token,
            device_info=device_info,
        )

        user = await users_service.get(new_token_model.user_id)
        access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            is_superuser=users_service.is_superuser(user),
            is_verified=user.is_verified,
            auth_method="refresh",
            amr=["refresh"],
        )
        response = Response(
            OAuth2Login(
                access_token=access_token,
                token_type="Bearer",  # noqa: S106
                refresh_token=new_raw_token,
                expires_in=ACCESS_TOKEN_MAX_AGE,
            ),
            status_code=201,
        )
        await _log_auth_event(
            audit_service,
            request,
            action="auth.refresh.success",
            actor_id=user.id,
            actor_email=user.email,
            target_type="session",
            target_id=str(new_token_model.id),
            target_label=user.email,
            details={"auth_method": "refresh"},
        )
        return _set_auth_cookies(response, settings=settings, access_token=access_token, refresh_token=new_raw_token)

    @get(operation_id="GetActiveSessions", path="/api/access/sessions")
    async def get_sessions(
        self,
        request: Request[m.User, Token, Any],
        refresh_token_service: RefreshTokenService,
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)],
    ) -> OffsetPagination[ActiveSession]:
        """Get all active sessions for the current user.

        Args:
            request: Request with authenticated user
            refresh_token_service: Refresh Token Service
            filters: Filter and pagination parameters

        Returns:
            Paginated active sessions
        """
        current_token_hash = None
        if raw_refresh_token := request.cookies.get(REFRESH_COOKIE_NAME):
            current_token_hash = refresh_token_service.hash_token(raw_refresh_token)
        active_tokens, total = await refresh_token_service.list_and_count(
            *filters,
            m.RefreshToken.user_id == request.user.id,
            m.RefreshToken.revoked_at.is_(None),
            m.RefreshToken.expires_at > datetime.now(UTC),
        )

        items = [
            {
                "id": token.id,
                "device_info": token.device_info,
                "created_at": token.created_at,
                "expires_at": token.expires_at,
                "is_current": token.token_hash == current_token_hash,
            }
            for token in active_tokens
        ]
        return refresh_token_service.to_schema(items, total, filters, schema_type=ActiveSession)

    @delete(operation_id="RevokeSession", path="/api/access/sessions/{session_id:uuid}", status_code=200)
    async def revoke_session(
        self,
        request: Request[m.User, Token, Any],
        refresh_token_service: RefreshTokenService,
        audit_service: AuditLogService,
        session_id: UUID,
    ) -> Message:
        """Revoke a specific session.

        Args:
            request: Request with authenticated user
            refresh_token_service: Refresh Token Service
            session_id: ID of the session to revoke

        Returns:
            Success message

        Raises:
            ClientException: If session not found or does not belong to user
        """
        token = await refresh_token_service.get_one_or_none(id=session_id)
        if not token or token.user_id != request.user.id:
            raise ClientException(detail="Session not found", status_code=404)
        await refresh_token_service.revoke_token_family(token.family_id)
        await _log_auth_event(
            audit_service,
            request,
            action="auth.session.revoke",
            actor_id=request.user.id,
            actor_email=request.user.email,
            target_type="session",
            target_id=str(token.id),
            target_label=token.device_info,
        )
        return Message(message="Session revoked successfully")

    @delete(operation_id="RevokeAllSessions", path="/api/access/sessions", status_code=200)
    async def revoke_all_sessions(
        self,
        request: Request[m.User, Token, Any],
        refresh_token_service: RefreshTokenService,
        audit_service: AuditLogService,
    ) -> Message:
        """Revoke all sessions except the current one.

        Args:
            request: Request with authenticated user
            refresh_token_service: Refresh Token Service

        Returns:
            Success message
        """

        current_token_hash = None
        if raw_refresh_token := request.cookies.get(REFRESH_COOKIE_NAME):
            current_token_hash = refresh_token_service.hash_token(raw_refresh_token)
        active_tokens = await refresh_token_service.get_active_sessions(request.user.id)
        revoked_count = 0
        for token in active_tokens:
            if token.token_hash != current_token_hash:
                revoked_count += await refresh_token_service.revoke_token_family(token.family_id)
        await _log_auth_event(
            audit_service,
            request,
            action="auth.session.revoke_all",
            actor_id=request.user.id,
            actor_email=request.user.email,
            target_type="user",
            target_id=str(request.user.id),
            target_label=request.user.email,
            details={"revoked_count": revoked_count},
        )
        return Message(message=f"Revoked {revoked_count} session(s)")

    @post(operation_id="AccountRegister", path="/api/access/signup")
    async def signup(
        self,
        request: Request[m.User, Token, Any],
        users_service: UserService,
        roles_service: RoleService,
        data: AccountRegister,
        app_mailer: AppEmailService,
    ) -> User:
        """User Signup.

        Args:
            request: Request
            users_service: User Service
            roles_service: Role Service
            data: Account Register Data
            app_mailer: Email service for sending notifications

        Returns:
            User
        """
        user_data = data.to_dict()

        role_obj = await roles_service.get_one_or_none(slug=slugify(users_service.default_role))

        if role_obj is not None:
            user_data.update({"role_id": role_obj.id})

        user = await users_service.create(user_data)
        request.app.emit(event_id="user_created", user_id=user.id, mailer=app_mailer)
        return users_service.to_schema(user, schema_type=User)

    @post(operation_id="ForgotPassword", path="/api/access/forgot-password", exclude_from_auth=True, security=[])
    async def forgot_password(
        self,
        users_service: UserService,
        password_reset_service: PasswordResetService,
        app_mailer: AppEmailService,
        request: Request[m.User, Token, Any],
        audit_service: AuditLogService,
        data: ForgotPasswordRequest,
    ) -> PasswordResetSent:
        """Initiate password reset flow.

        Args:
            data: Forgot password request data
            request: HTTP request object
            users_service: User service
            password_reset_service: Password reset service
            app_mailer: Email service for sending notifications

        Returns:
            Response indicating reset email status
        """
        user = await users_service.get_one_or_none(email=data.email)
        if user is None or not user.is_active:
            return PasswordResetSent(
                message="If the email exists, a password reset link has been sent", expires_in_minutes=60
            )
        if await password_reset_service.check_rate_limit(user.id):
            return PasswordResetSent(
                message="Too many password reset requests. Please try again later", expires_in_minutes=60
            )
        request.app.emit(event_id="password_reset_requested", user_id=user.id, mailer=app_mailer)
        await _log_auth_event(
            audit_service,
            request,
            action="auth.password.reset.requested",
            actor_id=user.id,
            actor_email=user.email,
            target_type="user",
            target_id=str(user.id),
            target_label=user.email,
        )
        return PasswordResetSent(
            message="If the email exists, a password reset link has been sent", expires_in_minutes=60
        )

    @get(operation_id="ValidateResetToken", path="/api/access/reset-password", exclude_from_auth=True, security=[])
    async def validate_reset_token(
        self,
        token: Annotated[str, Parameter(query="token", min_length=32, max_length=255)],
        password_reset_service: PasswordResetService,
    ) -> ResetTokenValidation:
        """Validate a password reset token.

        Args:
            token: Reset token from URL parameter
            password_reset_service: Password reset service

        Returns:
            Token validation response
        """
        try:
            reset_token = await password_reset_service.validate_reset_token(token)
            if reset_token:
                return ResetTokenValidation(
                    valid=True, user_id=reset_token.user_id, expires_at=reset_token.expires_at.isoformat()
                )
        except ClientException:
            logger.warning("Failed to validate reset token", exc_info=True)

        return ResetTokenValidation(valid=False)

    @post(operation_id="ResetPassword", path="/api/access/reset-password", exclude_from_auth=True, security=[])
    async def reset_password_with_token(
        self,
        data: ResetPasswordRequest,
        users_service: UserService,
        password_reset_service: PasswordResetService,
        request: Request[m.User, Token, Any],
        app_mailer: AppEmailService,
        audit_service: AuditLogService,
    ) -> PasswordResetComplete:
        """Complete password reset with token.

        Args:
            data: Password reset request data
            users_service: User service
            password_reset_service: Password reset service
            request: HTTP request object
            app_mailer: Email service for sending notifications

        Returns:
            Password reset confirmation

        Raises:
            ClientException: If token is invalid or passwords do not match
        """

        if data.password != data.password_confirm:
            raise ClientException(detail="Passwords do not match", status_code=400)

        try:
            validate_password_strength(data.password)
        except PasswordValidationError as e:
            raise ClientException(detail=str(e), status_code=400) from e
        reset_token = await password_reset_service.use_reset_token(data.token)
        user = await users_service.reset_password_with_token(user_id=reset_token.user_id, new_password=data.password)
        request.app.emit(event_id="password_reset_completed", user_id=user.id, mailer=app_mailer)
        await _log_auth_event(
            audit_service,
            request,
            action="auth.password.reset.completed",
            actor_id=user.id,
            actor_email=user.email,
            target_type="user",
            target_id=str(user.id),
            target_label=user.email,
        )
        return PasswordResetComplete(message="Password has been successfully reset", user_id=user.id)
