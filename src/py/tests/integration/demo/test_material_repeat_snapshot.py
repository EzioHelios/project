"""Persisted numeric scale must not invalidate an unchanged material allocation."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import models as m
from app.domain.material_allocation.usecases import CalculateMaterialCarbonAllocation
from app.lib.tenancy import TENANT_ID_SESSION_KEY
from tests.integration.material_allocation.test_allocation_usecase import fixture as build_fixture

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def frozen_rows(session):
    return [
        list((await session.execute(select(*model.__table__.c).order_by(model.id))).all())
        for model in (m.MaterialCarbonAllocationRun, m.MaterialCarbonAllocationResult)
    ]


@pytest.mark.parametrize("changed_input", ["energy", "factor", "quantity"])
async def test_material_repeat_across_sessions_preserves_snapshots_and_detects_real_changes(session, changed_input):
    # Keep newly created objects alive so their in-memory Decimal scale differs
    # from the Numeric columns read by the next request/session.
    _use, operations, command, fact, _product, factor = await build_fixture(session)
    first = (await CalculateMaterialCarbonAllocation(session).execute(command))[0]
    first_id, revision = first.id, first.revision
    fact_id, factor_id, operation_id = fact.id, factor.id, operations[0].id
    assert first.input_snapshot is not None
    assert first.input_snapshot["factor"]["value"] == "0.5"
    await session.commit()
    before = await frozen_rows(session)
    tenant_id = session.info[TENANT_ID_SESSION_KEY]
    await session.commit()
    factory = async_sessionmaker(session.bind, expire_on_commit=False)
    async with factory() as reloaded:
        reloaded.info[TENANT_ID_SESSION_KEY] = tenant_id
        persisted_factor = await reloaded.get(m.EmissionFactor, factor_id)
        assert persisted_factor is not None
        assert str(persisted_factor.factor_value) == "0.50000000"
        calc = CalculateMaterialCarbonAllocation(reloaded)
        repeated = (await calc.execute(command))[0]
        assert (repeated.id, repeated.revision) == (first_id, revision)
        await calc.require_current(repeated)
        await reloaded.commit()
        assert await frozen_rows(reloaded) == before
        if changed_input == "energy":
            row = await reloaded.get(m.EnergyIntervalFact, fact_id)
            assert row is not None
            row.amount += Decimal(6)
        elif changed_input == "factor":
            persisted_factor.factor_value += Decimal("0.1")
        else:
            row = await reloaded.get(m.MaterialHandlingOperation, operation_id)
            assert row is not None
            row.quantity += Decimal(1)
        await reloaded.flush()
        changed = (await calc.execute(command))[0]
        assert (changed.id, changed.revision) == (first_id, revision + 1)
        assert changed.total_co2e_kg == Decimal({"energy": "3", "factor": "1.8", "quantity": "1.5"}[changed_input])
        await reloaded.commit()
