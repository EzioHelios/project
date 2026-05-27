"""System domain controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypeVar

import structlog
from litestar import Controller, MediaType, get
from litestar.response import Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.domain.system import schemas as s

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.lib.settings import AppSettings

logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])


class SystemController(Controller):
    """System health and configuration."""

    tags = ["System"]
    dependencies = {}

    @get(
        operation_id="SystemHealth",
        name="system:health",
        path="/health",
        summary="Health Check",
        exclude_from_auth=True,
        security=[],  # Public endpoint - no auth required
    )
    async def check_system_health(
        self,
        db_session: AsyncSession,
        settings: AppSettings,
    ) -> Response[s.SystemHealth]:
        """Check database available and returns app config info.

        Args:
            db_session: The database session.
            settings: Application settings.

        Returns:
            The response object.
        """
        db_status: Literal["online", "offline"]
        try:
            await db_session.execute(text("select 1"))
            db_status = "online"
        except SQLAlchemyError:
            db_status = "offline"

        healthy = db_status == "online"
        if healthy:
            await logger.adebug(
                "System Health",
                database_status=db_status,
            )
        else:
            await logger.awarn(
                "System Health Check",
                database_status=db_status,
            )

        return Response(
            content=s.SystemHealth(database_status=db_status, app=settings.NAME),
            status_code=200 if healthy else 500,
            media_type=MediaType.JSON,
        )

    @get(
        operation_id="OAuthConfig",
        name="system:oauth-config",
        path="/api/config/oauth",
        summary="Get OAuth Configuration",
        exclude_from_auth=True,
        security=[],  # Public endpoint - no auth required
    )
    async def get_oauth_config(self, settings: AppSettings) -> s.OAuthConfig:
        """Get OAuth provider configuration for frontend.

        Args:
            settings: Application settings.

        Returns:
            OAuth configuration indicating which providers are enabled.
        """
        return s.OAuthConfig(google_enabled=settings.google_oauth_enabled, github_enabled=settings.github_oauth_enabled)

    @get(
        operation_id="PublicAppConfig",
        name="system:public-config",
        path="/api/config/public",
        summary="Get Public Application Configuration",
        exclude_from_auth=True,
        security=[],
    )
    async def get_public_config(self, settings: AppSettings) -> s.PublicAppConfig:
        """Get public display configuration for frontend."""
        return s.PublicAppConfig(
            display_name=settings.DISPLAY_NAME,
            short_name=settings.SHORT_NAME,
            description=settings.DESCRIPTION,
            auth_mode="cookie-session",
            captcha_provider="altcha-sentinel" if settings.altcha_enabled else None,
            captcha_enabled=settings.altcha_enabled,
            captcha_challenge_url=settings.altcha_challenge_url,
            captcha_site_key=settings.ALTCHA_SENTINEL_API_KEY or None,
        )

    @get(
        operation_id="SystemTasks",
        name="system:tasks",
        path="/api/system/tasks",
        summary="Get configured background tasks",
        exclude_from_auth=True,
        security=[],
    )
    async def get_system_tasks(self, settings: AppSettings) -> dict:
        """Return SAQ task and cron configuration for read-only admin pages."""
        config = settings.saq.get_config()
        queues = []
        for queue in config.queue_configs:
            queue_name = getattr(queue, "name", "background-tasks")
            tasks = [
                {
                    "queue": queue_name,
                    "kind": "task",
                    "name": getattr(task, "__name__", str(task)),
                    "module": getattr(task, "__module__", None),
                    "cron": None,
                    "timeout": None,
                    "ttl": None,
                    "enabled": True,
                }
                for task in (getattr(queue, "tasks", []) or [])
            ]
            scheduled_tasks = [
                {
                    "queue": queue_name,
                    "kind": "cron",
                    "name": getattr(getattr(job, "function", None), "__name__", str(getattr(job, "function", None))),
                    "module": getattr(getattr(job, "function", None), "__module__", None),
                    "cron": getattr(job, "cron", None),
                    "timeout": getattr(job, "timeout", None),
                    "ttl": getattr(job, "ttl", None),
                    "enabled": True,
                }
                for job in (getattr(queue, "scheduled_tasks", []) or [])
            ]
            queues.append(
                {
                    "name": queue_name,
                    "concurrency": getattr(queue, "concurrency", None),
                    "tasks": tasks,
                    "scheduled_tasks": scheduled_tasks,
                }
            )
        return {"code": 200, "msg": "获取成功", "data": queues}
