# ruff: noqa: ARG001
import asyncio
import sys
from typing import TYPE_CHECKING, Literal, cast

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from advanced_alchemy.base import metadata_registry
from alembic import context
from alembic.autogenerate import rewriter
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncEngine, async_engine_from_config
from sqlalchemy.sql.schema import SchemaItem

import app.db.models  # noqa: F401  # Register every model with the metadata registry.

if TYPE_CHECKING:
    from advanced_alchemy.alembic.commands import AlembicCommandConfig
    from sqlalchemy.engine import Connection

__all__ = ("do_run_migrations", "run_migrations_offline", "run_migrations_online")


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config: "AlembicCommandConfig" = context.config  # type: ignore
if not hasattr(config, "db_url"):
    try:
        from app.lib.settings import get_settings
        settings = get_settings()
        config.db_url = settings.db.URL
    except Exception:  # noqa: BLE001 - Alembic may run before application settings are importable.
        import os
        config.db_url = os.getenv("DATABASE_URL")
writer = rewriter.Rewriter()

# These tables are retained as read-only historical archives. They have no ORM
# model and no application route, so Alembic must not interpret them as pending
# destructive drops. ``ddl_version`` remains the only active migration ledger.
UNMANAGED_ARCHIVE_TABLES = {"alembic_version", "dataapp_ammeterindexvalue"}


def include_object(
    obj: SchemaItem,
    name: str | None,
    type_: Literal[
        "schema",
        "table",
        "column",
        "index",
        "unique_constraint",
        "foreign_key_constraint",
    ],
    reflected: bool,
    compare_to: SchemaItem | None,
) -> bool:
    """Excludes the SAQ tables, indexes, and other objects from being included in autogeneration

    Args:
        obj: The object to include.
        name: The name of the object.
        type_: The type of the object.
        reflected: Whether the object is reflected.
        compare_to: The object to compare to.

    Returns:
        Whether the object should be included.
    """
    return not (
        (name is not None and name.startswith("saq_"))
        or (
            type_ == "table"
            and name in {"task_queue", "task_queue_stats", "task_queue_ddl_version", *UNMANAGED_ARCHIVE_TABLES}
        )
        or (name is not None and name == "task_queue_lock_key_seq")
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    bind_key = getattr(config, "bind_key", None)
    context.configure(
        url=config.db_url,
        target_metadata=metadata_registry.get(bind_key),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=getattr(config, "compare_type", True),
        version_table=getattr(config, "version_table_name", "alembic_version"),
        version_table_pk=getattr(config, "version_table_pk", False),
        user_module_prefix=getattr(config, "user_module_prefix", "sa."),
        render_as_batch=getattr(config, "render_as_batch", True),
        process_revision_directives=writer,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: "Connection") -> None:
    """Run migrations."""
    bind_key = getattr(config, "bind_key", None)
    context.configure(
        connection=connection,
        target_metadata=metadata_registry.get(bind_key),
        compare_type=getattr(config, "compare_type", True),
        version_table=getattr(config, "version_table_name", "alembic_version"),
        version_table_pk=getattr(config, "version_table_pk", False),
        user_module_prefix=getattr(config, "user_module_prefix", "sa."),
        render_as_batch=getattr(config, "render_as_batch", True),
        process_revision_directives=writer,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a
    connection with the context.

    Raises:
        RuntimeError: If the engine cannot be created from the config.
    """
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = config.db_url

    connectable = cast(
        "AsyncEngine",
        (getattr(config, "engine", None))
        or async_engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            future=True,
        ),
    )
    if connectable is None:  # pyright: ignore[reportUnnecessaryComparison]
        msg = "Could not get engine from config.  Please ensure your `alembic.ini` according to the official Alembic documentation."
        raise RuntimeError(
            msg,
        )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
