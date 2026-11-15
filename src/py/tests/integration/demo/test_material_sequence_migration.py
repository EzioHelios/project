"""Run the historical frozen DDL and its repair, rather than create_all for target tables."""

from datetime import datetime
from importlib import import_module
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import insert, select, text
from sqlalchemy.exc import DBAPIError

from app.db import models as m

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
LEGACY = import_module("app.db.migrations.versions.2026_09_20_add_material_handling_allocation_f7a8b9c0d1e2")
HOURLY = import_module("app.db.migrations.versions.2026_09_20_material_hour_contract_f9a0b1c2d3e4")
REPAIR = import_module("app.db.migrations.versions.2026_11_15_repair_material_sequences_f151115a001")
MODELS = (m.MaterialHandlingOperation, m.MaterialCarbonAllocationRun, m.MaterialCarbonAllocationResult)


def recreate_from_migrations(connection):
    for model in reversed(MODELS):
        connection.execute(text(f'DROP TABLE "{model.__tablename__}" CASCADE'))
        connection.execute(text(f'DROP SEQUENCE IF EXISTS "{model.__tablename__}_id_seq"'))
    connection.execute(text("DROP INDEX IF EXISTS uq_pcf_material_source"))
    with Operations.context(MigrationContext.configure(connection)):
        LEGACY.upgrade()
        HOURLY.upgrade()


def upgrade(connection):
    with Operations.context(MigrationContext.configure(connection)):
        REPAIR.upgrade()


async def insert_triplet(connection, team_id, suffix, explicit_id=None):
    common = {"team_id": team_id, **({"id": explicit_id} if explicit_id is not None else {})}
    start = datetime.fromisoformat("2026-07-10T08:00:00")
    end = datetime.fromisoformat("2026-07-10T09:00:00")
    operation = await connection.scalar(
        insert(m.MaterialHandlingOperation.__table__)
        .values(
            **common,
            source_system="migration_test",
            source_record_id=suffix,
            operation_no=suffix,
            operation_type="internal_transfer",
            period_start=start,
            period_end=end,
            material_code="M",
            quantity=1,
            unit="pcs",
            equipment_type="forklift",
            duration_minutes=60,
        )
        .returning(m.MaterialHandlingOperation.id)
    )
    run = await connection.scalar(
        insert(m.MaterialCarbonAllocationRun.__table__)
        .values(**common, run_code=suffix, period_start=start, period_end=end, emission_factor=1)
        .returning(m.MaterialCarbonAllocationRun.id)
    )
    result = await connection.scalar(
        insert(m.MaterialCarbonAllocationResult.__table__)
        .values(
            **common,
            run_id=run,
            operation_id=operation,
            operation_no=suffix,
            operation_type="internal_transfer",
            equipment_type="forklift",
            material_code="M",
            allocation_method="duration_minutes",
        )
        .returning(m.MaterialCarbonAllocationResult.id)
    )
    return [operation, run, result]


async def sequence_states(connection):
    return [
        (await connection.execute(text(f'SELECT last_value,is_called FROM "{model.__tablename__}_id_seq"'))).one()
        for model in MODELS
    ]


async def rows_snapshot(connection):
    return [list((await connection.execute(select(*model.__table__.c).order_by(model.id))).all()) for model in MODELS]


@pytest.mark.parametrize("state", ["missing_empty", "missing_high_ids", "existing_ahead", "existing_behind"])
async def test_material_sequence_repair_preserves_rows_and_progress(engine, db_schema, state):
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.run_sync(recreate_from_migrations)
            team_id = uuid4()
            await connection.execute(insert(m.Team.__table__).values(id=team_id, slug="sequence-test", name="Test"))
            for model in MODELS:
                assert (
                    await connection.scalar(
                        text("SELECT pg_get_serial_sequence(:table,'id')"), {"table": model.__tablename__}
                    )
                    is None
                )
            if state != "missing_empty":
                assert await insert_triplet(connection, team_id, "historical", 100000) == [100000] * 3
            if state.startswith("existing_"):
                start = 200000 if state == "existing_ahead" else 1
                for model in MODELS:
                    await connection.execute(
                        text(f'CREATE SEQUENCE "{model.__tablename__}_id_seq" AS bigint START WITH {start}')
                    )
            before = await rows_snapshot(connection)
            await connection.execute(text("SELECT set_config('app.tenant_bypass','false',true)"))
            await connection.run_sync(upgrade)
            assert await connection.scalar(text("SELECT current_setting('app.tenant_bypass')")) == "false"
            assert await rows_snapshot(connection) == before
            for model in MODELS:
                assert (
                    await connection.scalar(
                        text("SELECT pg_get_serial_sequence(:table,'id')"), {"table": model.__tablename__}
                    )
                    == f"public.{model.__tablename__}_id_seq"
                )
                assert (
                    await connection.execute(
                        text(
                            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=CAST(:table AS regclass)"
                        ),
                        {"table": model.__tablename__},
                    )
                ).one() == (True, True)
            expected = 1 if state == "missing_empty" else 200000 if state == "existing_ahead" else 100001
            assert await insert_triplet(connection, team_id, "first") == [expected] * 3
            progress = await sequence_states(connection)
            rows = await rows_snapshot(connection)
            await connection.run_sync(upgrade)
            assert await sequence_states(connection) == progress
            assert await rows_snapshot(connection) == rows
            assert await insert_triplet(connection, team_id, "second") == [expected + 1] * 3
        finally:
            await transaction.rollback()


async def test_material_sequence_repair_rejects_conflicting_default_without_changes(engine, db_schema):
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.run_sync(recreate_from_migrations)
            await connection.execute(
                text("ALTER TABLE dataapp_materialhandlingoperation ALTER COLUMN id SET DEFAULT 123")
            )
            async with connection.begin_nested() as savepoint:
                with pytest.raises(DBAPIError, match="Unexpected id default"):
                    await connection.run_sync(upgrade)
                await savepoint.rollback()
            assert (
                await connection.scalar(
                    text(
                        "SELECT column_default FROM information_schema.columns WHERE table_name='dataapp_materialhandlingoperation' AND column_name='id'"
                    )
                )
                == "123"
            )
            for model in MODELS:
                assert (
                    await connection.scalar(text("SELECT to_regclass(:seq)"), {"seq": f"{model.__tablename__}_id_seq"})
                    is None
                )
                assert await connection.scalar(text(f'SELECT count(*) FROM "{model.__tablename__}"')) == 0
        finally:
            await transaction.rollback()
