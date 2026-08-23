"""All configuration via environment.

Take note of the environment variable prefixes required for each
settings class, except `AppSettings`.
"""

from __future__ import annotations

import binascii
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast
from urllib.parse import urlparse

import structlog
from advanced_alchemy.extensions.litestar import AlembicAsyncConfig, AsyncSessionConfig, SQLAlchemyAsyncConfig
from advanced_alchemy.utils.text import slugify
from dotenv import load_dotenv
from litestar.cli._utils import console
from litestar.config.compression import CompressionConfig
from litestar.config.cors import CORSConfig
from litestar.data_extractors import RequestExtractorField, ResponseExtractorField
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException
from litestar.logging.config import LoggingConfig, StructLoggingConfig, default_logger_factory
from litestar.middleware.logging import LoggingMiddlewareConfig
from litestar.plugins.problem_details import ProblemDetailsConfig
from litestar.plugins.structlog import StructlogConfig
from litestar.utils.module_loader import module_to_os_path
from litestar_email import EmailConfig, ResendConfig, SMTPConfig
from litestar_saq import CronJob, QueueConfig, SAQConfig
from litestar_vite import PathConfig, RuntimeConfig, TypeGenConfig, ViteConfig

from app.__metadata__ import __version__ as current_version
from app.utils.env import get_env

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

DEFAULT_MODULE_NAME = "app"
BASE_DIR: Final[Path] = module_to_os_path(DEFAULT_MODULE_NAME)
STATIC_DIR = Path(BASE_DIR / "server" / "static" / "web")


@dataclass
class DatabaseSettings:
    ECHO: bool = field(default_factory=get_env("DATABASE_ECHO", False))
    """Enable SQLAlchemy engine logs."""
    ECHO_POOL: bool = field(default_factory=get_env("DATABASE_ECHO_POOL", False))
    """Enable SQLAlchemy connection pool logs."""
    POOL_DISABLED: bool = field(default_factory=get_env("DATABASE_POOL_DISABLED", False))
    """Disable SQLAlchemy pool configuration."""
    POOL_MAX_OVERFLOW: int = field(default_factory=get_env("DATABASE_MAX_POOL_OVERFLOW", 10))
    """Max overflow for SQLAlchemy connection pool"""
    POOL_SIZE: int = field(default_factory=get_env("DATABASE_POOL_SIZE", 5))
    """Pool size for SQLAlchemy connection pool"""
    POOL_TIMEOUT: int = field(default_factory=get_env("DATABASE_POOL_TIMEOUT", 30))
    """Time in seconds for timing connections out of the connection pool."""
    POOL_RECYCLE: int = field(default_factory=get_env("DATABASE_POOL_RECYCLE", 300))
    """Amount of time to wait before recycling connections."""
    POOL_PRE_PING: bool = field(default_factory=get_env("DATABASE_PRE_POOL_PING", False))
    """Optionally ping database before fetching a session from the connection pool."""
    URL: str = field(default_factory=get_env("DATABASE_URL", "postgresql+psycopg://app:app@localhost:15432/app"))
    """SQLAlchemy Database URL."""
    MIGRATION_CONFIG: str = field(
        default_factory=get_env("DATABASE_MIGRATION_CONFIG", f"{BASE_DIR}/db/migrations/alembic.ini")
    )
    """The path to the `alembic.ini` configuration file."""
    MIGRATION_PATH: str = field(default_factory=get_env("DATABASE_MIGRATION_PATH", f"{BASE_DIR}/db/migrations"))
    """The path to the `alembic` database migrations."""
    MIGRATION_DDL_VERSION_TABLE: str = field(
        default_factory=get_env("DATABASE_MIGRATION_DDL_VERSION_TABLE", "ddl_version")
    )
    """The name to use for the `alembic` versions table name."""
    FIXTURE_PATH: str = field(default_factory=get_env("DATABASE_FIXTURE_PATH", f"{BASE_DIR}/db/fixtures"))
    """The path to JSON fixture files to load into tables."""
    _engine_instance: AsyncEngine | None = None
    """SQLAlchemy engine instance generated from settings."""

    @property
    def engine(self) -> AsyncEngine:
        return self.get_engine()

    def get_engine(self) -> AsyncEngine:
        if self._engine_instance is not None:
            return self._engine_instance
        from app.utils.engine_factory import create_sqlalchemy_engine

        self._engine_instance = create_sqlalchemy_engine(self)
        return self._engine_instance

    def get_config(self) -> SQLAlchemyAsyncConfig:
        """Get SQLAlchemy configuration.

        Returns:
            The SQLAlchemy async configuration.
        """
        from app.lib.tenancy import TenantAwareSQLAlchemyAsyncConfig

        return TenantAwareSQLAlchemyAsyncConfig(
            engine_instance=self.get_engine(),
            before_send_handler="autocommit",
            session_config=AsyncSessionConfig(expire_on_commit=False),
            alembic_config=AlembicAsyncConfig(
                version_table_name=self.MIGRATION_DDL_VERSION_TABLE,
                script_config=self.MIGRATION_CONFIG,
                script_location=self.MIGRATION_PATH,
            ),
        )


@dataclass
class ViteSettings:
    """Vite build tool configurations."""

    DEV_MODE: bool = field(default_factory=get_env("VITE_DEV_MODE", False))
    """Start `vite` development server."""
    BUNDLE_DIR: Path = field(default_factory=get_env("VITE_BUNDLE_DIR", STATIC_DIR))
    """Bundle directory for built assets."""
    ASSET_URL: str = field(default_factory=get_env("ASSET_URL", "/static/web/"))
    """Base URL for assets."""
    TRUSTED_PROXIES: str | None = field(default_factory=get_env("LITESTAR_TRUSTED_PROXIES", None))
    """Trust X-Forwarded-* headers from these proxies. Use "*" to trust all."""

    def get_config(self, base_dir: Path = BASE_DIR.parent.parent) -> ViteConfig:
        """Get Vite configuration.

        Args:
            base_dir: Base directory for resolving paths.

        Returns:
            The Vite configuration.
        """
        js_home = base_dir / "js" / "web"
        return ViteConfig(
            mode="spa",
            dev_mode=self.DEV_MODE,
            runtime=RuntimeConfig(executor="bun", trusted_proxies=self.TRUSTED_PROXIES),
            paths=PathConfig(
                root=js_home,
                bundle_dir=self.BUNDLE_DIR,
                asset_url=self.ASSET_URL,
            ),
            types=TypeGenConfig(output=Path("src/lib/generated")),
        )


@dataclass
class ServerSettings:
    """Server configurations."""

    APP_LOC: str = "dma.asgi:create_app"
    """Path to app executable or factory."""
    HOST: str = field(default_factory=get_env("LITESTAR_HOST", "0.0.0.0"))  # noqa: S104
    """Server network host."""
    PORT: int = field(default_factory=get_env("LITESTAR_PORT", 8000))
    """Server port."""
    KEEPALIVE: int = field(default_factory=get_env("LITESTAR_KEEPALIVE", 65))
    """Seconds to hold connections open (65 is > AWS lb idle timeout)."""
    RELOAD: bool = field(default_factory=get_env("LITESTAR_RELOAD", False))
    """Turn on hot reloading."""
    RELOAD_DIRS: list[str] = field(default_factory=get_env("LITESTAR_RELOAD_DIRS", [f"{BASE_DIR}"]))
    """Directories to watch for reloading."""


@dataclass
class SaqSettings:
    """SAQ (Simple Async Queue) configuration using Redis as broker."""

    REDIS_URL: str = field(default_factory=get_env("SAQ_REDIS_URL", "redis://localhost:16379/0"))
    """Redis URL for SAQ broker."""
    PROCESSES: int = field(default_factory=get_env("SAQ_PROCESSES", 1))
    """The number of worker processes to start.

    Default is set to 1.
    """
    CONCURRENCY: int = field(default_factory=get_env("SAQ_CONCURRENCY", 10))
    """The number of concurrent jobs allowed to execute per worker process.

    Default is set to 10.
    """
    WEB_ENABLED: bool = field(default_factory=get_env("SAQ_WEB_ENABLED", True))
    """If true, the worker admin UI is hosted on worker startup."""
    USE_SERVER_LIFESPAN: bool = field(default_factory=get_env("SAQ_USE_SERVER_LIFESPAN", True))
    """Auto start and stop `saq` processes when starting the Litestar application."""
    MQTT_INGEST_CONCURRENCY: int = field(default_factory=get_env("MQTT_INGEST_CONCURRENCY", 1))
    """Dedicated MQTT queue concurrency. Keep this at one for a single subscription runner."""

    def get_config(self) -> SAQConfig:
        """Get SAQ configuration.

        Returns:
            The SAQ configuration.
        """
        from app.domain.accounts import jobs as account_jobs
        from app.domain.carbon import jobs as carbon_jobs
        from app.domain.carbon_verification import jobs as carbon_verification_jobs
        from app.domain.decarbonization import jobs as decarbonization_jobs
        from app.domain.iot_ingestion import infrastructure as iot_infrastructure
        from app.domain.iot_ingestion import jobs as iot_jobs
        from app.domain.microgrid import jobs as microgrid_jobs
        from app.domain.system import jobs as system_jobs
        from app.lib.worker import after_process, before_process, on_shutdown, on_startup

        return SAQConfig(
            web_enabled=self.WEB_ENABLED,
            worker_processes=self.PROCESSES,
            use_server_lifespan=self.USE_SERVER_LIFESPAN,
            queue_configs=[
                QueueConfig(
                    name="background-tasks",
                    dsn=self.REDIS_URL,
                    tasks=[
                        system_jobs.cleanup_auth_tokens,
                        account_jobs.refresh_oauth_tokens,
                        carbon_jobs.sync_yunji_status,
                        carbon_jobs.pull_yunji_data,
                        carbon_jobs.sync_hw_status,
                        carbon_jobs.pull_hw_data,
                        carbon_verification_jobs.run_carbon_verification_export,
                        decarbonization_jobs.refresh_reduction_project_risks,
                        microgrid_jobs.run_microgrid_forecast_cycle,
                        microgrid_jobs.run_microgrid_optimization_cycle,
                        microgrid_jobs.refresh_microgrid_load_models,
                        microgrid_jobs.project_microgrid_meter_history,
                    ],
                    scheduled_tasks=[
                        CronJob(
                            function=system_jobs.cleanup_auth_tokens,
                            cron="0 * * * *",
                            timeout=600,
                            ttl=1800,
                        ),
                        CronJob(
                            function=account_jobs.refresh_oauth_tokens,
                            cron="*/15 * * * *",
                            timeout=600,
                            ttl=1800,
                        ),
                        # Carbon Jobs - Status Sync (Hourly)
                        CronJob(
                            function=carbon_jobs.sync_yunji_status,
                            cron="0 * * * *",
                            timeout=300,
                        ),
                        CronJob(
                            function=carbon_jobs.sync_hw_status,
                            cron="0 * * * *",
                            timeout=300,
                        ),
                        # Carbon Jobs - Data Pulling (Every 15 mins for Yunji, Daily for HW)
                        CronJob(
                            function=carbon_jobs.pull_yunji_data,
                            cron="*/15 * * * *",
                            timeout=600,
                        ),
                        CronJob(
                            function=carbon_jobs.pull_hw_data,
                            cron="0 1 * * *",  # 每天凌晨1点拉取红外
                            timeout=1200,
                        ),
                        CronJob(
                            function=decarbonization_jobs.refresh_reduction_project_risks,
                            cron="15 3 * * *",
                            timeout=600,
                        ),
                        CronJob(
                            function=microgrid_jobs.run_microgrid_forecast_cycle,
                            cron="*/15 * * * *",
                            timeout=600,
                        ),
                        CronJob(
                            function=microgrid_jobs.run_microgrid_optimization_cycle,
                            cron="2-59/15 * * * *",
                            timeout=300,
                        ),
                        CronJob(
                            function=microgrid_jobs.refresh_microgrid_load_models,
                            cron="30 2 * * *",
                            timeout=900,
                        ),
                        CronJob(
                            function=microgrid_jobs.project_microgrid_meter_history,
                            cron="7 * * * *",
                            timeout=900,
                        ),
                    ],
                    concurrency=self.CONCURRENCY,
                    startup=on_startup,
                    shutdown=on_shutdown,
                    before_process=before_process,
                    after_process=after_process,
                ),
                QueueConfig(
                    name="mqtt-ingest",
                    dsn=self.REDIS_URL,
                    tasks=[
                        ("iot.ingest_mqtt_message", iot_jobs.ingest_mqtt_message),
                        ("iot.retry_pending_mqtt_messages", iot_jobs.retry_pending_mqtt_messages),
                    ],
                    scheduled_tasks=[
                        CronJob(
                            function=iot_jobs.retry_pending_mqtt_messages,
                            cron="*/1 * * * *",
                            timeout=300,
                        ),
                    ],
                    concurrency=self.MQTT_INGEST_CONCURRENCY,
                    startup=[on_startup, iot_infrastructure.on_mqtt_ingest_startup],
                    shutdown=[iot_infrastructure.on_mqtt_ingest_shutdown, on_shutdown],
                    before_process=before_process,
                    after_process=after_process,
                    separate_process=True,
                ),
            ],
        )


@dataclass
class CarbonSettings:
    """Carbon management specific settings for external APIs."""

    YUNJI_API_KEY: str = field(default_factory=get_env("YUNJI_API_KEY", "94A26B674E5442809FD4DD9B51F83723"))
    YUNJI_API_HOST: str = field(default_factory=get_env("YUNJI_API_HOST", "http://nhapi.yunjichaobiao.com/"))
    YUNJI_PULL_START_TIME: str = field(default_factory=get_env("YUNJI_PULL_START_TIME", "2023-03-22 00:00:00"))
    YUNJI_PULL_OVERLAP_MINUTES: int = field(default_factory=get_env("YUNJI_PULL_OVERLAP_MINUTES", 15, int))
    YUNJI_PULL_MAX_WINDOW_HOURS: int = field(default_factory=get_env("YUNJI_PULL_MAX_WINDOW_HOURS", 24, int))

    HW_AUTH_CODE: str = field(default_factory=get_env("HW_AUTH_CODE", "d7770f50ad09ab821246c3da105fd4b9"))
    HW_API_HOST: str = field(default_factory=get_env("HW_API_HOST", "http://api1.tqdianbiao.com/"))
    HW_PULL_START_TIME: str = field(default_factory=get_env("HW_PULL_START_TIME", "2023-03-23 00:00:00"))


@dataclass
class EmailSettings:
    """Email configuration.

    Set EMAIL_BACKEND to:
    - "console" (default) - prints emails to stdout (development)
    - "memory" - stores in memory (testing)
    - "smtp" - sends via SMTP server
    - "resend" - sends via Resend API (production)
    """

    BACKEND: str = field(default_factory=get_env("EMAIL_BACKEND", "console"))
    """Email backend: console, memory, smtp, resend."""
    FROM_EMAIL: str = field(default_factory=get_env("EMAIL_FROM_ADDRESS", "noreply@localhost"))
    """Default from email address."""
    FROM_NAME: str = field(default_factory=get_env("EMAIL_FROM_NAME", "Litestar App"))
    """Default from name."""
    # SMTP settings (only used when BACKEND="smtp")
    SMTP_HOST: str = field(default_factory=get_env("EMAIL_SMTP_HOST", "localhost"))
    """SMTP server hostname."""
    SMTP_PORT: int = field(default_factory=get_env("EMAIL_SMTP_PORT", 587, int))
    """SMTP server port."""
    SMTP_USER: str = field(default_factory=get_env("EMAIL_SMTP_USER", ""))
    """SMTP username."""
    SMTP_PASSWORD: str = field(default_factory=get_env("EMAIL_SMTP_PASSWORD", ""))
    """SMTP password."""
    USE_TLS: bool = field(default_factory=get_env("EMAIL_USE_TLS", True))
    """Use TLS for SMTP connection."""
    USE_SSL: bool = field(default_factory=get_env("EMAIL_USE_SSL", False))
    """Use SSL for SMTP connection."""
    TIMEOUT: int = field(default_factory=get_env("EMAIL_TIMEOUT", 30, int))
    """SMTP connection timeout in seconds."""
    # Resend settings (only used when BACKEND="resend")
    RESEND_API_KEY: str = field(default_factory=get_env("RESEND_API_KEY", ""))
    """Resend API key for production email sending."""

    def get_config(self) -> EmailConfig:
        """Return EmailConfig for the litestar-email plugin.

        As of litestar-email v0.3.0, the backend parameter accepts either
        a string ("console", "memory") or a config object (SMTPConfig,
        ResendConfig).

        Returns:
            The email configuration.
        """
        backend: str | SMTPConfig | ResendConfig = self.BACKEND
        if self.BACKEND == "smtp":
            backend = SMTPConfig(
                host=self.SMTP_HOST,
                port=self.SMTP_PORT,
                username=self.SMTP_USER,
                password=self.SMTP_PASSWORD,
                use_tls=self.USE_TLS,
                use_ssl=self.USE_SSL,
                timeout=self.TIMEOUT,
            )
        elif self.BACKEND == "resend":
            backend = ResendConfig(api_key=self.RESEND_API_KEY)
        return EmailConfig(
            backend=backend,
            from_email=self.FROM_EMAIL,
            from_name=self.FROM_NAME,
        )


@dataclass
class AppSettings:
    """Application configuration"""

    NAME: str = field(default_factory=lambda: "Litestar Fullstack Template")
    """Application name."""
    DISPLAY_NAME: str = field(default_factory=get_env("APP_DISPLAY_NAME", "碳数据收集与管理系统"))
    """User-facing application display name."""
    SHORT_NAME: str = field(default_factory=get_env("APP_SHORT_NAME", "CD"))
    """Short user-facing application name."""
    DESCRIPTION: str = field(
        default_factory=get_env("APP_DESCRIPTION", "支持 Scope 1/2/3 碳排放数据的采集、审核与统计分析。")
    )
    """User-facing application description."""
    BRAND_MARK_URL: str = field(default_factory=get_env("APP_BRAND_MARK_URL", ""))
    """Optional user-facing brand mark URL."""
    FAVICON_URL: str = field(default_factory=get_env("APP_FAVICON_URL", ""))
    """Optional user-facing favicon URL."""
    VERSION: str = field(default=f"v{current_version}")
    """Current application"""
    CONTACT_NAME: str = field(default="Admin")
    """Application contact name"""
    CONTACT_EMAIL: str = field(default="admin@localhost")
    """Application contact email"""
    URL: str = field(default_factory=get_env("APP_URL", "http://localhost:8000"))
    """The frontend base URL"""
    DEBUG: bool = field(default_factory=get_env("LITESTAR_DEBUG", False))
    """Run `Litestar` with `debug=True`."""
    SECRET_KEY: str = field(
        default_factory=get_env("SECRET_KEY", binascii.hexlify(os.urandom(32)).decode(encoding="utf-8")),
    )
    """Application secret key."""
    JWT_ENCRYPTION_ALGORITHM: str = "HS256"
    """JWT Algorithm to use"""
    ALLOWED_CORS_ORIGINS: list[str] | str = field(default_factory=get_env("ALLOWED_CORS_ORIGINS", ["*"], list[str]))
    """Allowed CORS Origins"""
    COOKIE_SECURE: bool = field(default_factory=get_env("COOKIE_SECURE", False))
    """Use secure cookies (set to True in production with HTTPS)"""
    STATIC_DIR: Path = field(default_factory=get_env("STATIC_DIR", STATIC_DIR))
    """Default URL where static assets are located."""
    STATIC_URL: str = field(default_factory=get_env("STATIC_URL", "/static/web/"))
    """URL Location for Static assets."""
    BASE_URL: str | None = None
    """Fully qualified path to optional use for URL generation."""
    DEV_MODE: bool = field(default_factory=get_env("VITE_DEV_MODE", False))
    """Toggle dev mode flag.  This can be used enable extra processes during development."""
    ENABLE_INSTRUMENTATION: bool = False
    """Enable OpenTelemetry instrumentation"""
    ENVIRONMENT: str = field(default_factory=get_env("APP_ENV", "development"))
    """Runtime environment, e.g. development / staging / production."""
    GOOGLE_OAUTH2_CLIENT_ID: str = field(default_factory=get_env("GOOGLE_OAUTH2_CLIENT_ID", ""))
    """Google Client ID"""
    GOOGLE_OAUTH2_CLIENT_SECRET: str = field(default_factory=get_env("GOOGLE_OAUTH2_CLIENT_SECRET", ""))
    """Google Client Secret"""
    GITHUB_OAUTH2_CLIENT_ID: str = field(default_factory=get_env("GITHUB_OAUTH2_CLIENT_ID", ""))
    """GitHub Client ID"""
    GITHUB_OAUTH2_CLIENT_SECRET: str = field(default_factory=get_env("GITHUB_OAUTH2_CLIENT_SECRET", ""))
    """GitHub Client Secret"""
    ENV_SECRETS: str = field(default_factory=get_env("ENV_SECRETS", "runtime-secrets"))
    """Path to environment secrets."""
    ALTCHA_SENTINEL_URL: str = field(default_factory=get_env("ALTCHA_SENTINEL_URL", ""))
    """Public base URL for the ALTCHA Sentinel service."""
    ALTCHA_SENTINEL_INTERNAL_URL: str = field(default_factory=get_env("ALTCHA_SENTINEL_INTERNAL_URL", ""))
    """Internal base URL used by the backend to verify Sentinel payloads."""
    ALTCHA_SENTINEL_API_KEY: str = field(default_factory=get_env("ALTCHA_SENTINEL_API_KEY", ""))
    """Public/restricted ALTCHA Sentinel API key used for challenges."""
    ALTCHA_SENTINEL_VERIFY_PATH: str = field(
        default_factory=get_env("ALTCHA_SENTINEL_VERIFY_PATH", "/v1/verify/signature")
    )
    """HTTP path used by the application to verify ALTCHA Sentinel payloads."""
    LOGIN_RISK_THRESHOLD: int = field(default_factory=get_env("LOGIN_RISK_THRESHOLD", 5, int))
    """Failed login attempts allowed before human verification is required."""
    LOGIN_RISK_WINDOW_SECONDS: int = field(default_factory=get_env("LOGIN_RISK_WINDOW_SECONDS", 900, int))
    """Rolling window used to track failed login attempts."""
    LOGIN_RISK_BLOCK_SECONDS: int = field(default_factory=get_env("LOGIN_RISK_BLOCK_SECONDS", 3600, int))
    """Temporary block duration for requests that continue failing after the threshold."""
    HSTS_MAX_AGE: int = field(default_factory=get_env("HSTS_MAX_AGE", 31536000, int))
    """Strict-Transport-Security max-age value for HTTPS production deployments."""

    @property
    def google_oauth_enabled(self) -> bool:
        """Check if Google OAuth is configured.

        Returns:
            True if Google OAuth credentials are set.
        """
        return bool(self.GOOGLE_OAUTH2_CLIENT_ID and self.GOOGLE_OAUTH2_CLIENT_SECRET)

    @property
    def github_oauth_enabled(self) -> bool:
        """Check if GitHub OAuth is configured.

        Returns:
            True if GitHub OAuth credentials are set.
        """
        return bool(self.GITHUB_OAUTH2_CLIENT_ID and self.GITHUB_OAUTH2_CLIENT_SECRET)

    @property
    def slug(self) -> str:
        """Return a slugified name.

        Returns:
            `self.NAME`, all lowercase and hyphens instead of spaces.
        """
        return slugify(self.NAME)

    @property
    def is_production(self) -> bool:
        """Return whether runtime environment should enforce production-safe settings."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def altcha_enabled(self) -> bool:
        """Return whether ALTCHA Sentinel is configured for browser verification."""
        return bool(self.ALTCHA_SENTINEL_URL and self.ALTCHA_SENTINEL_API_KEY)

    @property
    def altcha_challenge_url(self) -> str | None:
        """Return the challenge URL consumed directly by the ALTCHA widget."""
        if not self.altcha_enabled:
            return None
        base_url = self.ALTCHA_SENTINEL_URL.rstrip("/")
        return f"{base_url}/v1/challenge?apiKey={self.ALTCHA_SENTINEL_API_KEY}"

    @property
    def altcha_verify_url(self) -> str | None:
        """Return the Sentinel endpoint used to verify the signed ALTCHA payload."""
        base_url = self.ALTCHA_SENTINEL_INTERNAL_URL or self.ALTCHA_SENTINEL_URL
        if not base_url:
            return None
        return f"{base_url.rstrip('/')}{self.ALTCHA_SENTINEL_VERIFY_PATH}"

    def get_compression_config(self) -> CompressionConfig:
        return CompressionConfig(backend="gzip")

    def get_cors_config(self) -> CORSConfig:
        return CORSConfig(allow_origins=cast("list[str]", self.ALLOWED_CORS_ORIGINS), allow_credentials=True)

    def get_problem_details_config(self) -> ProblemDetailsConfig:
        return ProblemDetailsConfig(enable_for_all_http_exceptions=True)

    def __post_init__(self) -> None:
        # Check if the ALLOWED_CORS_ORIGINS is a string.
        if isinstance(self.ALLOWED_CORS_ORIGINS, str):
            # Check if the string starts with "[" and ends with "]", indicating a list.
            if self.ALLOWED_CORS_ORIGINS.startswith("[") and self.ALLOWED_CORS_ORIGINS.endswith("]"):
                try:
                    # Safely evaluate the string as a Python list.
                    self.ALLOWED_CORS_ORIGINS = json.loads(self.ALLOWED_CORS_ORIGINS)  # pyright: ignore[reportConstantRedefinition]
                except (SyntaxError, ValueError):
                    # Handle potential errors if the string is not a valid Python literal.
                    msg = "ALLOWED_CORS_ORIGINS is not a valid list representation."
                    raise ValueError(msg) from None
            else:
                # Split the string by commas into a list if it is not meant to be a list representation.
                self.ALLOWED_CORS_ORIGINS = [host.strip() for host in self.ALLOWED_CORS_ORIGINS.split(",")]  # pyright: ignore[reportConstantRedefinition]

        if self.ALTCHA_SENTINEL_URL:
            parsed = urlparse(self.ALTCHA_SENTINEL_URL)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                msg = "ALTCHA_SENTINEL_URL must be an absolute http(s) URL."
                raise ValueError(msg)

        if self.is_production:
            if cast("list[str]", self.ALLOWED_CORS_ORIGINS) == ["*"]:
                msg = "ALLOWED_CORS_ORIGINS cannot be wildcard in production."
                raise ValueError(msg)
            if not self.COOKIE_SECURE:
                msg = "COOKIE_SECURE must be enabled in production."
                raise ValueError(msg)
            if not self.SECRET_KEY or self.SECRET_KEY in {"change-me", "development-secret-key"}:
                msg = "SECRET_KEY must be rotated away from development defaults in production."
                raise ValueError(msg)
            if not self.altcha_enabled:
                msg = "ALTCHA Sentinel must be configured in production."
                raise ValueError(msg)


@dataclass
class LogSettings:
    """Logger configuration"""

    # https://stackoverflow.com/a/1845097/6560549
    EXCLUDE_PATHS: str = r"\A(?!x)x"
    """Regex to exclude paths from logging."""
    INCLUDE_COMPRESSED_BODY: bool = False
    """Include 'body' of compressed responses in log output."""
    LEVEL: int = field(default_factory=get_env("LOG_LEVEL", 30))
    """Stdlib log levels.

    Only emit logs at this level, or higher.
    """
    OBFUSCATE_COOKIES: set[str] = field(default_factory=lambda: {"session", "XSRF-TOKEN"})
    """Request cookie keys to obfuscate."""
    OBFUSCATE_HEADERS: set[str] = field(default_factory=lambda: {"Authorization", "X-API-KEY", "X-XSRF-TOKEN"})
    """Request header keys to obfuscate."""
    REQUEST_FIELDS: list[RequestExtractorField] = field(
        default_factory=get_env(
            "LOG_REQUEST_FIELDS",
            [
                "path",
                "method",
                "query",
                "path_params",
            ],
            list[RequestExtractorField],
        ),
    )
    """Attributes of the [Request][litestar.connection.request.Request] to be
    logged."""
    RESPONSE_FIELDS: list[ResponseExtractorField] = field(
        default_factory=get_env(
            "LOG_RESPONSE_FIELDS",
            ["status_code"],
            type_hint=list[ResponseExtractorField],
        )
    )
    """Attributes of the [Response][litestar.response.Response] to be
    logged."""
    SAQ_LEVEL: int = field(default_factory=get_env("SAQ_LOG_LEVEL", 50))
    """Level to log SAQ logs."""
    SQLALCHEMY_LEVEL: int = field(default_factory=get_env("SQLALCHEMY_LOG_LEVEL", 30))
    """Level to log SQLAlchemy logs."""
    ASGI_ACCESS_LEVEL: int = field(default_factory=get_env("ASGI_ACCESS_LOG_LEVEL", 30))
    """Level to log uvicorn access logs."""
    ASGI_ERROR_LEVEL: int = field(default_factory=get_env("ASGI_ERROR_LOG_LEVEL", 30))
    """Level to log uvicorn error logs."""

    def get_structlog_config(self) -> StructlogConfig:
        from app.lib import log as log_conf

        return StructlogConfig(
            enable_middleware_logging=False,
            structlog_logging_config=StructLoggingConfig(
                log_exceptions="always",
                processors=log_conf.structlog_processors(as_json=not log_conf.is_tty()),
                logger_factory=default_logger_factory(as_json=not log_conf.is_tty()),
                disable_stack_trace={404, 401, 403, NotAuthorizedException, PermissionDeniedException},
                standard_lib_logging_config=LoggingConfig(
                    log_exceptions="always",
                    disable_stack_trace={404, 401, 403, NotAuthorizedException, PermissionDeniedException},
                    root={"level": logging.getLevelName(self.LEVEL), "handlers": ["queue_listener"]},
                    formatters={
                        "standard": {
                            "()": structlog.stdlib.ProcessorFormatter,
                            "processors": log_conf.stdlib_logger_processors(as_json=not log_conf.is_tty()),
                        },
                    },
                    loggers={
                        "saq": {
                            "propagate": False,
                            "level": self.SAQ_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                        "sqlalchemy.engine": {
                            "propagate": False,
                            "level": self.SQLALCHEMY_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                        "sqlalchemy.pool": {
                            "propagate": False,
                            "level": self.SQLALCHEMY_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                        "opentelemetry.sdk.metrics._internal": {
                            "propagate": False,
                            "level": 40,
                            "handlers": ["queue_listener"],
                        },
                        "httpx": {
                            "propagate": False,
                            "level": max(self.LEVEL, logging.WARNING),
                            "handlers": ["queue_listener"],
                        },
                        "httpcore": {
                            "propagate": False,
                            "level": max(self.LEVEL, logging.WARNING),
                            "handlers": ["queue_listener"],
                        },
                        "_granian": {
                            "propagate": False,
                            "level": self.ASGI_ERROR_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                        "granian.server": {
                            "propagate": False,
                            "level": self.ASGI_ERROR_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                        "granian.access": {
                            "propagate": False,
                            "level": self.ASGI_ACCESS_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                    },
                ),
            ),
            middleware_logging_config=LoggingMiddlewareConfig(
                request_log_fields=self.REQUEST_FIELDS,
                response_log_fields=self.RESPONSE_FIELDS,
            ),
        )


@dataclass
class Settings:
    app: AppSettings = field(default_factory=AppSettings)
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    vite: ViteSettings = field(default_factory=ViteSettings)
    server: ServerSettings = field(default_factory=ServerSettings)
    saq: SaqSettings = field(default_factory=SaqSettings)
    log: LogSettings = field(default_factory=LogSettings)
    email: EmailSettings = field(default_factory=EmailSettings)
    carbon: CarbonSettings = field(default_factory=CarbonSettings)

    @classmethod
    @lru_cache(maxsize=1, typed=True)
    def from_env(cls, dotenv_filename: str = ".env") -> Settings:
        logger = structlog.get_logger()
        _secret_id = os.environ.get("ENV_SECRETS", None)  # use this to load secrets in a container
        env_file = Path(f"{os.curdir}/{dotenv_filename}")
        env_file_exists = env_file.is_file()
        if env_file_exists:
            console.print(f"[yellow]Loading environment configuration from {dotenv_filename}[/]")
            load_dotenv(env_file, override=False)  # Env vars take precedence over .env file
        try:
            db: DatabaseSettings = DatabaseSettings()
            server: ServerSettings = ServerSettings()
            saq: SaqSettings = SaqSettings()
            vite: ViteSettings = ViteSettings()
            app: AppSettings = AppSettings()
            log: LogSettings = LogSettings()
            carbon: CarbonSettings = CarbonSettings()
        except Exception as e:  # noqa: BLE001
            logger.fatal("Could not load settings. %s", e)
            sys.exit(1)
        return Settings(app=app, db=db, vite=vite, server=server, saq=saq, log=log, carbon=carbon)


def get_settings(dotenv_filename: str = ".env") -> Settings:
    return Settings.from_env(dotenv_filename)


def provide_app_settings() -> AppSettings:
    """Return application settings for dependency injection.

    Returns:
        The application settings instance.
    """
    return get_settings().app
