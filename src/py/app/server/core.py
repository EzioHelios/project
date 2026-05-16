# pylint: disable=[invalid-name,import-outside-toplevel]
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, TypeVar
from uuid import UUID

from advanced_alchemy.exceptions import DuplicateKeyError, RepositoryError
from httpx_oauth.oauth2 import OAuth2Token
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.plugins import ScalarRenderPlugin
from litestar.params import Body
from litestar.plugins import CLIPluginProtocol, InitPluginProtocol
from litestar.security.jwt import OAuth2Login, Token
from litestar_email import EmailService

from app import config
from app.__metadata__ import __version__
from app.db import models as m
from app.domain.accounts.guards import auth, provide_user
from app.lib.email import AppEmailService
from app.lib.exceptions import (
    ApplicationClientError,
    ApplicationError,
    exception_to_http_response,
)
from app.lib.settings import AppSettings, get_settings, provide_app_settings
from app.lib.validation import ValidationError
from app.server import plugins

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from click import Group
    from litestar.config.app import AppConfig
    from litestar.datastructures import State


T = TypeVar("T")


class ApplicationCore(InitPluginProtocol, CLIPluginProtocol):
    """Application core configuration plugin.

    This class is responsible for configuring the main Litestar application with our routes, guards, and various plugins

    """

    __slots__ = ("app_slug",)
    app_slug: str

    def on_cli_init(self, cli: Group) -> None:
        from app.cli.commands import carbon_management_group, user_management_group

        settings = get_settings()
        self.app_slug = settings.app.slug
        cli.add_command(carbon_management_group)
        cli.add_command(user_management_group)

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Configure application for use with SQLAlchemy.

        Args:
            app_config: The :class:`AppConfig <litestar.config.app.AppConfig>` instance.

        Returns:
            The configured app config.
        """
        settings = get_settings()
        self.app_slug = settings.app.slug
        app_config.debug = settings.app.DEBUG
        app_config.openapi_config = OpenAPIConfig(
            title=settings.app.NAME,
            version=__version__,
            components=[auth.openapi_components],
            security=[auth.security_requirement],
            render_plugins=[ScalarRenderPlugin(version="latest")],
        )
        app_config = auth.on_app_init(app_config)
        app_config.cors_config = config.cors


        app_config.plugins.extend(
            [
                plugins.structlog,
                # plugins.granian,
                plugins.alchemy,
                plugins.vite,
                # plugins.get_saq_plugin(),
                plugins.problem_details,
                # plugins.oauth2_provider,
                plugins.email,
                plugins.domain,
            ],
        )

        app_config.signature_namespace.update(
            {
                "Token": Token,
                "OAuth2Login": OAuth2Login,
                "RequestEncodingType": RequestEncodingType,
                "Body": Body,
                "m": m,
                "UUID": UUID,
                "datetime": datetime,
                "OAuth2Token": OAuth2Token,
                "AppSettings": AppSettings,
                "User": m.User,
                "AppEmailService": AppEmailService,
                "EmailService": EmailService,
            },
        )
        app_config.exception_handlers = {
            ApplicationError: exception_to_http_response,
            ApplicationClientError: exception_to_http_response,
            ValidationError: exception_to_http_response,
            RepositoryError: exception_to_http_response,
            DuplicateKeyError: exception_to_http_response,
        }
        app_config.dependencies.update(
            {
                "current_user": Provide(provide_user, sync_to_thread=False),
                "settings": Provide(provide_app_settings, sync_to_thread=False),
                "app_mailer": Provide(get_mailer_dependency),
            }
        )

        return app_config


async def get_mailer_dependency(state: State) -> AsyncGenerator[AppEmailService, None]:
    """Provide the app email service.

    在未启用 email 插件时，`state` 上不存在 ``mailer``，如果仍然强制访问
    将导致 AttributeError 并让诸如 ``/api/access/signup`` 这类依赖邮件的接口 500。

    这里做一个安全兜底：
    - 若检测到 `state.mailer` 存在，则正常使用真实的 EmailService。
    - 若不存在，则返回一个“空实现”的 mailer，只记录日志，不真正发邮件，
      这样注册 / 重置密码等流程依然可以走通，只是不会发送邮件。

    Args:
        state: Litestar application state.

    Yields:
        AppEmailService 实例（真实或空实现）。
    """

    # 优先尝试真实 mailer（需要在 plugins 里启用 plugins.email）
    try:
        email_config = state.mailer  # type: ignore[attr-defined]
    except AttributeError:
        # 构造一个空实现的 mailer，满足 AppEmailService 的最小依赖接口
        class _NoopMailer:
            async def send_message(self, message: object) -> int:  # pragma: no cover - 简单兜底
                # 这里不抛异常，只返回 0 表示“未真正发送”，避免影响主流程
                return 0

        yield AppEmailService(mailer=_NoopMailer())  # type: ignore[arg-type]
        return

    async with email_config.provide_service() as mailer:
        yield AppEmailService(mailer=mailer)
