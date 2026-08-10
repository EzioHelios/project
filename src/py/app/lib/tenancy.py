"""Tenant scoping helpers for team-owned business data."""

from __future__ import annotations

from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any, ClassVar, cast
from uuid import UUID

from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig
from litestar.datastructures import State  # noqa: TC002 - Litestar resolves reserved dependency types at runtime.
from litestar.exceptions import PermissionDeniedException
from litestar.types import Scope  # noqa: TC002 - Litestar resolves reserved dependency types at runtime.
from sqlalchemy import ForeignKey, event, false, text
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 - Litestar resolves provider return types at runtime.
from sqlalchemy.orm import Mapped, Session, declared_attr, mapped_column, with_loader_criteria

from app.lib import constants

if TYPE_CHECKING:
    from app.db.models import User

TENANT_ID_SESSION_KEY = "tenant_id"
TENANT_BYPASS_SESSION_KEY = "tenant_bypass"
TENANT_EVENT_INSTALLED_KEY = "_app_tenant_events_installed"
TENANT_HEADER_NAME = b"x-team-id"
ACCESS_COOKIE_KEY = "access_token"
DEFAULT_TENANT_ID = UUID("00000000-0000-7000-8000-000000000001")


@dataclass(frozen=True)
class TenantContext:
    """Resolved tenant information for the current request."""

    team_id: UUID
    user_id: UUID
    is_superuser: bool = False


class TeamScopedMixin:
    """Declarative mixin for rows owned by a team tenant."""

    __abstract__ = True
    __tenant_scoped__: ClassVar[bool] = True

    @declared_attr.directive
    def team_id(cls) -> Mapped[UUID]:
        return mapped_column(ForeignKey("team.id", ondelete="CASCADE"), nullable=False, index=True)


def _coerce_uuid(value: object) -> UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _extract_header_team_id(scope: Scope) -> UUID | None:
    for name, value in cast("list[tuple[bytes, bytes]]", scope.get("headers", [])):
        if name.lower() == TENANT_HEADER_NAME:
            return _coerce_uuid(value.decode())
    return None


def _extract_requested_team_id(scope: Scope) -> UUID | None:
    path_params = cast("dict[str, object]", scope.get("path_params") or {})
    return _coerce_uuid(path_params.get("team_id")) or _extract_header_team_id(scope)


def _extract_cookie_value(scope: Scope, key: str) -> str | None:
    cookie = SimpleCookie()
    for name, value in cast("list[tuple[bytes, bytes]]", scope.get("headers", [])):
        if name.lower() == b"cookie":
            raw_cookie = value.decode()
            cookie.load(raw_cookie)
            for part in raw_cookie.split(";"):
                cookie_key, separator, cookie_value = part.strip().partition("=")
                if separator and cookie_key == key and cookie_value:
                    return cookie_value.strip('"')
    morsel = cookie.get(key)
    return morsel.value if morsel is not None else None


def _token_has_superuser_access(scope: Scope) -> bool:
    token = _decode_access_token(scope)
    return bool(token is not None and token.extras.get("is_superuser"))


def _token_user_id(scope: Scope) -> UUID:
    token = _decode_access_token(scope)
    if token is None:
        return DEFAULT_TENANT_ID
    return _coerce_uuid(token.extras.get("user_id")) or DEFAULT_TENANT_ID


def _decode_access_token(scope: Scope) -> Any | None:
    encoded_token = _extract_cookie_value(scope, ACCESS_COOKIE_KEY)
    if not encoded_token:
        return None
    encoded_token = encoded_token.partition(" ")[-1]

    try:
        from litestar.security.jwt import Token

        from app.lib.settings import get_settings

        app_settings = get_settings().app
        token = Token.decode(
            encoded_token=encoded_token,
            secret=app_settings.SECRET_KEY,
            algorithm=app_settings.JWT_ENCRYPTION_ALGORITHM,
        )
    except Exception:  # noqa: BLE001 - invalid or expired auth tokens should not grant tenant bypass.
        return None
    return token


def _user_has_superuser_access(user: User) -> bool:
    if user.is_superuser:
        return True
    return any(assigned_role.role_name == constants.SUPERUSER_ACCESS_ROLE for assigned_role in user.roles)


def _user_team_ids(user: User) -> set[UUID]:
    return {membership.team_id for membership in user.teams}


def resolve_tenant_context(scope: Scope) -> TenantContext | None:
    """Resolve tenant context from path/header/user membership.

    Non-superusers can use an explicitly requested team only if they are a member.
    If a user belongs to exactly one team, that team is used as the default tenant.
    Superusers bypass tenant filtering unless they explicitly select a team.
    """
    user = cast("User | None", scope.get("user"))
    requested_team_id = _extract_requested_team_id(scope)
    if user is None:
        if _token_has_superuser_access(scope) and requested_team_id is not None:
            return TenantContext(team_id=requested_team_id, user_id=_token_user_id(scope), is_superuser=True)
        return None

    is_superuser = _user_has_superuser_access(user)
    if is_superuser:
        return (
            TenantContext(team_id=requested_team_id, user_id=user.id, is_superuser=True)
            if requested_team_id is not None
            else None
        )

    team_ids = _user_team_ids(user)
    tenant_context: TenantContext | None = None
    if requested_team_id is not None:
        if requested_team_id not in team_ids:
            raise PermissionDeniedException(detail="Insufficient permissions to access team.")
        tenant_context = TenantContext(team_id=requested_team_id, user_id=user.id)
    elif len(team_ids) == 1:
        tenant_context = TenantContext(team_id=next(iter(team_ids)), user_id=user.id)
    return tenant_context


def configure_session_tenant(session: AsyncSession, scope: Scope) -> None:
    """Attach tenant metadata to a request-scoped SQLAlchemy session."""
    try:
        tenant_context = resolve_tenant_context(scope)
    except PermissionDeniedException:
        session.info.pop(TENANT_ID_SESSION_KEY, None)
        session.info.pop(TENANT_BYPASS_SESSION_KEY, None)
        return

    user = cast("User | None", scope.get("user"))
    if tenant_context is None:
        session.info.pop(TENANT_ID_SESSION_KEY, None)
        if (user is not None and _user_has_superuser_access(user)) or (
            user is None and _extract_requested_team_id(scope) is None and _token_has_superuser_access(scope)
        ):
            session.info[TENANT_BYPASS_SESSION_KEY] = True
        else:
            session.info.pop(TENANT_BYPASS_SESSION_KEY, None)
        return

    session.info[TENANT_ID_SESSION_KEY] = tenant_context.team_id
    session.info.pop(TENANT_BYPASS_SESSION_KEY, None)


class TenantAwareSQLAlchemyAsyncConfig(SQLAlchemyAsyncConfig):
    """SQLAlchemy config that carries request tenant metadata on sessions."""

    def provide_session(self, state: State, scope: Scope) -> AsyncSession:
        session = super().provide_session(state, scope)
        configure_session_tenant(session, scope)
        return session


def _is_team_scoped(obj: object) -> bool:
    return bool(getattr(obj.__class__, "__tenant_scoped__", False))


def _tenant_id_for_session(session: Session) -> UUID | None:
    return _coerce_uuid(session.info.get(TENANT_ID_SESSION_KEY))


def session_tenant_id(session: Session | AsyncSession) -> UUID | None:
    """Return the active tenant attached to a sync or async session."""
    return _coerce_uuid(session.info.get(TENANT_ID_SESSION_KEY))


def require_session_tenant_id(session: Session | AsyncSession) -> UUID:
    """Return the active tenant or reject tenant-owned business access."""
    tenant_id = session_tenant_id(session)
    if tenant_id is None:
        msg = "An active team is required for tenant-scoped business data."
        raise PermissionDeniedException(detail=msg)
    return tenant_id


def _iter_team_scoped_model_classes() -> list[type[TeamScopedMixin]]:
    scoped_classes: list[type[TeamScopedMixin]] = []
    pending: list[type[TeamScopedMixin]] = list(TeamScopedMixin.__subclasses__())
    while pending:
        model_cls = pending.pop()
        pending.extend(cast("list[type[TeamScopedMixin]]", model_cls.__subclasses__()))
        if hasattr(model_cls, "__mapper__"):
            scoped_classes.append(model_cls)
    return scoped_classes


def _iter_marked_model_classes(marker: str) -> list[type[TeamScopedMixin]]:
    return [model_cls for model_cls in _iter_team_scoped_model_classes() if getattr(model_cls, marker, False)]


def _enforce_flush_tenant(session: Session) -> None:
    tenant_id = _tenant_id_for_session(session)
    bypass = bool(session.info.get(TENANT_BYPASS_SESSION_KEY))
    scoped_objects = [
        obj
        for collection in (session.new, session.dirty, session.deleted)
        for obj in collection
        if _is_team_scoped(obj)
    ]
    if not scoped_objects:
        return

    if tenant_id is None:
        if bypass:
            for obj in scoped_objects:
                if obj in session.new and _coerce_uuid(getattr(obj, "team_id", None)) is None:
                    setattr(obj, "team_id", DEFAULT_TENANT_ID)
            return
        msg = "Tenant-scoped writes require an active team context."
        raise PermissionDeniedException(detail=msg)

    for obj in scoped_objects:
        object_team_id = _coerce_uuid(getattr(obj, "team_id", None))
        if obj in session.new and object_team_id is None:
            setattr(obj, "team_id", tenant_id)
            continue
        if object_team_id != tenant_id:
            msg = "Cannot write tenant-scoped data outside the active team."
            raise PermissionDeniedException(detail=msg)


def install_tenant_events() -> None:
    """Install SQLAlchemy session events once per process."""
    if getattr(Session, TENANT_EVENT_INSTALLED_KEY, False):
        return

    @event.listens_for(Session, "after_begin")
    def _set_postgresql_tenant_settings(session: Session, _transaction: Any, connection: Any) -> None:
        if connection.dialect.name != "postgresql":
            return

        tenant_id = _tenant_id_for_session(session)
        connection.execute(
            text("select set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id) if tenant_id is not None else ""},
        )
        connection.execute(
            text("select set_config('app.tenant_bypass', :tenant_bypass, true)"),
            {"tenant_bypass": "true" if session.info.get(TENANT_BYPASS_SESSION_KEY) else "false"},
        )

    @event.listens_for(Session, "do_orm_execute")
    def _add_tenant_criteria(execute_state: Any) -> None:
        if not execute_state.is_select:
            return
        session = execute_state.session

        revision_scoped_models = _iter_marked_model_classes("__current_revision_scoped__")
        if revision_scoped_models and not execute_state.execution_options.get("include_revision_history"):
            execute_state.statement = execute_state.statement.options(
                *[
                    with_loader_criteria(
                        model_cls,
                        lambda cls: cls.is_current.is_(True),
                        include_aliases=True,
                    )
                    for model_cls in revision_scoped_models
                ]
            )

        formal_record_models = _iter_marked_model_classes("__formal_record_scoped__")
        if formal_record_models and not execute_state.execution_options.get("include_reference_records"):
            execute_state.statement = execute_state.statement.options(
                *[
                    with_loader_criteria(
                        model_cls,
                        lambda cls: cls.record_usage != "reference",
                        include_aliases=True,
                    )
                    for model_cls in formal_record_models
                ]
            )

        if execute_state.execution_options.get("include_all_tenants"):
            return
        if session.info.get(TENANT_BYPASS_SESSION_KEY):
            return

        tenant_id = _tenant_id_for_session(session)
        scoped_model_classes = _iter_team_scoped_model_classes()
        if not scoped_model_classes:
            return
        if tenant_id is None:

            def _deny_tenant_access(_cls: type[TeamScopedMixin]) -> Any:
                return false()

            execute_state.statement = execute_state.statement.options(
                *[
                    with_loader_criteria(model_cls, _deny_tenant_access, include_aliases=True)
                    for model_cls in scoped_model_classes
                ],
            )
            return

        def _match_tenant(cls: type[TeamScopedMixin]) -> Any:
            return cls.team_id == tenant_id

        execute_state.statement = execute_state.statement.options(
            *[
                with_loader_criteria(model_cls, _match_tenant, include_aliases=True)
                for model_cls in scoped_model_classes
            ],
        )

    @event.listens_for(Session, "before_flush")
    def _validate_tenant_writes(session: Session, _flush_context: Any, _instances: Any) -> None:
        _enforce_flush_tenant(session)

    setattr(Session, TENANT_EVENT_INSTALLED_KEY, True)


install_tenant_events()
