"""Synthetic data cannot be written through customer or unscoped entry points."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from litestar.exceptions import PermissionDeniedException

from app.demo.ops.material_handling import seed_material_handling
from app.demo.ops.woheng import TENANTS
from app.demo.showcase import ShowcaseDemoBuilder
from app.domain.carbon.energy_analysis_importer import seed_energy_analysis_data
from app.domain.energy.benchmark_importer import seed_warehouse_energy_benchmark_data
from app.domain.ghg_inventory.usecases.tenant_dataset import CompleteWarehouseTenantInventory
from app.domain.microgrid.usecases.operations import BootstrapXiangtaiDemo
from app.lib.demo_tenancy import CUSTOMER_TENANT_IDS, WOHENG_TENANT_SLUGS, require_demo_tenant
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.unit, pytest.mark.anyio]


def session_for(slug, *, team_id=None, active=True, bypass=False):
    team_id = team_id or uuid4()
    return SimpleNamespace(
        info={TENANT_ID_SESSION_KEY: team_id, TENANT_BYPASS_SESSION_KEY: bypass},
        no_autoflush=nullcontext(),
        get=AsyncMock(return_value=SimpleNamespace(id=team_id, slug=slug, is_active=active)),
        execute=AsyncMock(),
        scalar=AsyncMock(),
    )


@pytest.mark.parametrize("slug", sorted(WOHENG_TENANT_SLUGS))
async def test_only_registered_woheng_tenants_are_accepted(slug):
    assert {tenant.slug for tenant in TENANTS} == WOHENG_TENANT_SLUGS
    session = session_for(slug)
    assert await require_demo_tenant(session) == session.info[TENANT_ID_SESSION_KEY]


@pytest.mark.parametrize("slug", ["xiangtai", "anfang", "customer", "woheng-other", "industrial-showcase"])
async def test_customer_and_unregistered_tenants_are_rejected(slug):
    with pytest.raises(PermissionDeniedException):
        await require_demo_tenant(session_for(slug))


@pytest.mark.parametrize("team_id", list(CUSTOMER_TENANT_IDS))
async def test_renaming_customer_to_demo_slug_does_not_allow_writes(team_id):
    with pytest.raises(PermissionDeniedException):
        await require_demo_tenant(session_for("woheng-taizhou-production-base", team_id=team_id))


async def test_missing_tenant_and_bypass_are_rejected_before_database_access():
    for info in ({}, {TENANT_ID_SESSION_KEY: uuid4(), TENANT_BYPASS_SESSION_KEY: True}):
        session = SimpleNamespace(info=info, get=AsyncMock())
        with pytest.raises(PermissionDeniedException):
            await require_demo_tenant(session)
        session.get.assert_not_awaited()


async def test_missing_or_inactive_demo_tenant_is_rejected():
    session = session_for("woheng-taizhou-production-base", active=False)
    with pytest.raises(PermissionDeniedException):
        await require_demo_tenant(session)
    session.get.return_value = None
    with pytest.raises(PermissionDeniedException):
        await require_demo_tenant(session)


@pytest.mark.parametrize("entry", ["showcase", "energy", "benchmark", "inventory", "microgrid", "handling"])
async def test_each_generator_rejects_customer_before_business_queries(entry):
    session = session_for("xiangtai")
    commands = {
        "showcase": lambda: ShowcaseDemoBuilder(session).execute(),
        "energy": lambda: seed_energy_analysis_data(session),
        "benchmark": lambda: seed_warehouse_energy_benchmark_data(session),
        "inventory": lambda: CompleteWarehouseTenantInventory(session).execute(),
        "microgrid": lambda: BootstrapXiangtaiDemo(session).execute(),
        "handling": lambda: seed_material_handling(session, "xiangtai", "TZ"),
    }
    with pytest.raises(PermissionDeniedException):
        await commands[entry]()
    session.execute.assert_not_awaited()
    session.scalar.assert_not_awaited()
