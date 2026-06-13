from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import anyio
import click
from advanced_alchemy.utils.fixtures import open_fixture_async
from advanced_alchemy.utils.text import slugify
from rich import get_console
from sqlalchemy import select
from sqlalchemy.orm import load_only
from structlog import get_logger

from app.config import alchemy
from app.db.models import Role, UserRole
from app.domain.accounts.deps import provide_users_service
from app.domain.accounts.schemas import UserCreate, UserUpdate
from app.domain.accounts.services import RoleService, UserService
from app.domain.carbon.calculation_factor_importer import import_calculation_factor_checklist
from app.domain.carbon.energy_analysis_importer import seed_energy_analysis_data
from app.domain.carbon.factor_importer import import_ncsc_factor_package
from app.domain.carbon.mvp_data_importer import seed_carbon_mvp_data
from app.domain.carbon.production_data_importer import import_wms_production_data
from app.domain.energy.benchmark_importer import seed_warehouse_energy_benchmark_data
from app.lib.deps import create_service_provider, provide_services
from app.lib.settings import get_settings


@click.group(name="users", invoke_without_command=False, help="Manage application users and roles.")
@click.pass_context
def user_management_group(_: dict[str, Any]) -> None:
    """Manage application users."""


@click.group(name="carbon", invoke_without_command=False, help="Manage carbon data assets.")
@click.pass_context
def carbon_management_group(_: dict[str, Any]) -> None:
    """Manage carbon data assets."""


async def load_database_fixtures() -> None:
    """Import/Synchronize Database Fixtures."""
    settings = get_settings()
    logger = get_logger()
    fixtures_path = Path(settings.db.FIXTURE_PATH)
    async with RoleService.new(
        statement=select(Role).options(load_only(Role.id, Role.slug, Role.name, Role.description)),
        config=alchemy,
    ) as service:
        fixture_data = await open_fixture_async(fixtures_path, "role")
        await service.upsert_many(match_fields=["name"], data=fixture_data, auto_commit=True)
        await logger.ainfo("loaded roles")


@user_management_group.command(name="create-user", help="Create a user")
@click.option(
    "--email",
    help="Email of the new user",
    type=click.STRING,
    required=False,
    show_default=False,
)
@click.option(
    "--name",
    help="Full name of the new user",
    type=click.STRING,
    required=False,
    show_default=False,
)
@click.option(
    "--password",
    help="Password",
    type=click.STRING,
    required=False,
    show_default=False,
)
@click.option(
    "--superuser",
    help="Is a superuser",
    type=click.BOOL,
    default=False,
    required=False,
    show_default=False,
    is_flag=True,
)
def create_user(
    email: str | None,
    name: str | None,
    password: str | None,
    superuser: bool | None,
) -> None:
    """Create a user."""
    console = get_console()

    async def _create_user(
        email: str,
        password: str,
        name: str | None = None,
        superuser: bool = False,
    ) -> None:
        obj_in = UserCreate(
            email=email,
            name=name,
            password=password,
            is_superuser=superuser,
        )
        async with provide_services(provide_users_service) as (users_service,):
            user = await users_service.create(data=obj_in.to_dict(), auto_commit=True)
            console.print(f"User created: {user.email}")

    console.rule("Create a new application user.")
    email = email or click.prompt("Email")
    name = name or click.prompt("Full Name", show_default=False)
    password = password or click.prompt("Password", hide_input=True, confirmation_prompt=True)
    superuser = superuser or click.prompt("Create as superuser?", show_default=True, type=click.BOOL)

    anyio.run(_create_user, cast("str", email), cast("str", password), name, cast("bool", superuser))


@user_management_group.command(name="promote-to-superuser", help="Promotes a user to application superuser")
@click.option(
    "--email",
    help="Email of the user",
    type=click.STRING,
    required=False,
    show_default=False,
)
def promote_to_superuser(email: str) -> None:
    """Promote to Superuser.

    Args:
        email (str): The email address of the user to promote.
    """
    console = get_console()

    async def _promote_to_superuser(email: str) -> None:
        async with UserService.new(config=alchemy) as users_service:
            user = await users_service.get_one_or_none(email=email)
            if user:
                console.print(f"Promoting user: %{user.email}")
                user_in = UserUpdate(
                    email=user.email,
                    is_superuser=True,
                )
                user = await users_service.update(
                    item_id=user.id,
                    data=user_in.to_dict(),
                    auto_commit=True,
                )
                console.print(f"Upgraded {email} to superuser")
            else:
                console.print(f"User not found: {email}")

    console.rule("Promote user to superuser.")
    anyio.run(_promote_to_superuser, email)


@user_management_group.command(name="create-roles", help="Create pre-configured application roles and assign to users.")
def create_default_roles() -> None:
    """Create the default Roles for the system"""
    provide_roles_service = create_service_provider(RoleService)
    console = get_console()

    async def _create_default_roles() -> None:
        await load_database_fixtures()
        async with provide_services(provide_users_service, provide_roles_service) as (users_service, roles_service):
            default_role = await roles_service.get_one_or_none(slug=slugify(users_service.default_role))
            if default_role:
                all_active_users = await users_service.list(is_active=True)
                for user in all_active_users:
                    if any(r.role_id == default_role.id for r in user.roles):
                        console.print("User %s already has default role", user.email)
                    else:
                        user.roles.append(UserRole(role_id=default_role.id))
                        console.print("Assigned %s default role", user.email)
                        await users_service.update(item_id=user.id, data=user, auto_commit=True)

    console.rule("Creating default roles.")
    anyio.run(_create_default_roles)


@user_management_group.command(name="seed-admin", help="Create a default admin account (admin@example.com / admin123).")
def seed_admin() -> None:
    """Create a default admin account if it does not already exist."""
    console = get_console()

    async def _seed_admin() -> None:
        await load_database_fixtures()
        async with provide_services(provide_users_service) as (users_service,):
            existing = await users_service.get_one_or_none(email="admin@example.com")
            if existing:
                console.print("[yellow]Admin account already exists: admin@example.com[/yellow]")
                return
            user = await users_service.create(
                data={
                    "email": "admin@example.com",
                    "name": "Admin",
                    "password": "admin123",
                    "is_superuser": True,
                    "is_active": True,
                    "is_verified": True,
                },
                auto_commit=True,
            )
            console.print(f"[green]Admin account created: {user.email} (password: admin123)[/green]")

    console.rule("Seeding default admin account.")
    anyio.run(_seed_admin)


@carbon_management_group.command(name="import-ncsc-factors", help="Import an NCSC official factor package.")
@click.argument("package_dir", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
def import_ncsc_factors(package_dir: Path) -> None:
    """Import NCSC factor package into the source-neutral factor asset library."""
    console = get_console()

    async def _import() -> None:
        async with alchemy.get_session() as session:
            result = await import_ncsc_factor_package(session, package_dir)
        console.print(
            "[green]Imported factor package[/green] "
            f"snapshot={result.snapshot_id} source={result.source_system} "
            f"checksum={'ok' if result.checksum_verified else 'failed'} "
            f"libraries={result.libraries} categories={result.categories} "
            f"records={result.raw_records} candidates={result.projection_candidates}"
        )

    console.rule("Import NCSC official factor package.")
    anyio.run(_import)


@carbon_management_group.command(
    name="import-calculation-factor-checklist",
    help="Import a reusable calculation-factor checklist CSV into the calculation factor library.",
)
@click.argument("csv_path", type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path))
def import_calculation_factor_checklist_command(csv_path: Path) -> None:
    """Import a reusable calculation-factor checklist CSV."""
    console = get_console()

    async def _import() -> None:
        async with alchemy.get_session() as session:
            result = await import_calculation_factor_checklist(session, csv_path)
        console.print(
            "[green]Imported calculation factor checklist[/green] "
            f"imported={result.imported} updated={result.updated} "
            f"skipped_pending={result.skipped_pending} skipped_invalid={result.skipped_invalid} "
            f"resolved_raw_records={result.resolved_raw_records}"
        )

    console.rule("Import calculation factor checklist.")
    anyio.run(_import)


@carbon_management_group.command(
    name="import-wms-production-data",
    help="Generate product, product price and product batch quantity samples from WMS records.",
)
@click.option("--limit", type=click.INT, default=None, help="Limit inbound and outbound source rows for sampling.")
@click.option("--dry-run", is_flag=True, default=False, help="Build the data in memory and roll back without writing.")
def import_wms_production_data_command(limit: int | None, dry_run: bool) -> None:
    """Generate product denominator samples from inbound and outbound WMS data."""
    console = get_console()

    async def _import() -> None:
        async with alchemy.get_session() as session:
            result = await import_wms_production_data(session, limit=limit, dry_run=dry_run)
        console.print(
            "[green]Generated WMS production data[/green] "
            f"dry_run={dry_run} products={result.products_upserted} "
            f"prices_inserted={result.prices_inserted} prices_deleted={result.prices_deleted} "
            f"output_facts={result.output_facts_upserted} "
            f"skipped_missing_code={result.skipped_missing_code} "
            f"skipped_missing_date={result.skipped_missing_date} "
            f"skipped_missing_quantity={result.skipped_missing_quantity}"
        )

    console.rule("Generate WMS production data samples.")
    anyio.run(_import)


@carbon_management_group.command(
    name="seed-carbon-mvp-data",
    help="Generate a coherent MVP data set for carbon accounting, verification, PCF, supply chain, assets, and budget.",
)
def seed_carbon_mvp_data_command() -> None:
    """Generate carbon-management MVP sample data."""
    console = get_console()

    async def _seed() -> None:
        async with alchemy.get_session() as session:
            result = await seed_carbon_mvp_data(session)
        console.print(
            "[green]Seeded carbon MVP data[/green] "
            f"scope_records={result.scope_records} organizations={result.organizations} "
            f"boundaries={result.boundaries} accounting_batches={result.accounting_batches} "
            f"inventory_items={result.inventory_items} verification_projects={result.verification_projects} "
            f"pcf_studies={result.pcf_studies} suppliers={result.suppliers} "
            f"asset_periods={result.asset_periods} budget_plans={result.budget_plans}"
        )

    console.rule("Seed carbon-management MVP data.")
    anyio.run(_seed)


@carbon_management_group.command(
    name="seed-energy-analysis-data",
    help="Generate energy analysis systems, tariff, interval facts and workload samples.",
)
def seed_energy_analysis_data_command() -> None:
    """Generate reusable energy analysis sample data from existing meter readings."""
    console = get_console()

    async def _seed() -> None:
        async with alchemy.get_session() as session:
            result = await seed_energy_analysis_data(session)
        console.print(
            "[green]Seeded energy analysis data[/green] "
            f"use_systems={result.use_systems} bindings={result.use_system_bindings} "
            f"tariff_plans={result.tariff_plans} tariff_segments={result.tariff_segments} "
            f"hourly_facts={result.hourly_facts} daily_facts={result.daily_facts} "
            f"workload_facts={result.workload_facts}"
        )

    console.rule("Seed energy analysis data.")
    anyio.run(_seed)


@carbon_management_group.command(
    name="seed-energy-benchmark-data",
    help="Generate a warehouse scenario industry benchmark library sample.",
)
def seed_energy_benchmark_data_command() -> None:
    """Generate warehouse scenario benchmark library sample data."""
    console = get_console()

    async def _seed() -> None:
        async with alchemy.get_session() as session:
            result = await seed_warehouse_energy_benchmark_data(session)
        console.print(
            "[green]Seeded energy benchmark data[/green] "
            f"profiles_deleted={result.profiles_deleted} "
            f"profiles_inserted={result.profiles_inserted} "
            f"items_inserted={result.items_inserted}"
        )

    console.rule("Seed energy benchmark data.")
    anyio.run(_seed)
