"""Exercise actual SQL cleanup against legacy rows in an isolated PostgreSQL fixture."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from app.db import models as m
from app.domain.metering.projection_cleanup import CleanupBlockedError, ProjectionCleanup
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = pytest.mark.anyio


async def test_cleanup_preserves_current_ids_values_and_other_tenants(session):
    team = m.Team(name="Cleanup A", slug="cleanup-a")
    other = m.Team(name="Cleanup B", slug="cleanup-b")
    session.add_all([team, other])
    await session.commit()
    team_id, other_id = team.id, other.id
    # Only this test database relaxes the new guards to model the pre-migration schema.
    await session.execute(
        text(
            "ALTER TABLE dataapp_energyintervalfact DROP CONSTRAINT ck_dataapp_energyintervalfact_ck_energy_interval_current_only"
        )
    )
    await session.execute(
        text("ALTER TABLE dataapp_energyintervalfact DROP CONSTRAINT uq_energy_interval_team_source_record")
    )
    await session.commit()
    try:
        for tenant in (team_id, other_id):
            session.info[TENANT_ID_SESSION_KEY] = tenant
            await session.execute(
                text("""
                INSERT INTO dataapp_energyintervalfact
                (id, team_id, source_system, source_record_id, energy_type_code, granularity,
                 period_start, period_end, amount, unit, data_quality, revision_no, is_current, created_at, updated_at)
                SELECT nextval('dataapp_energyintervalfact_id_seq'), CAST(:team AS uuid), 'meter_projection', 'key:' || k, 'electricity', 'hour',
                       timestamp '2026-10-01', timestamp '2026-10-01 01:00:00', r, 'kWh', 'measured',
                       r, r=20 AND k<=100, now(), now()
                FROM generate_series(1,101) k CROSS JOIN generate_series(1,20) r
            """),
                {"team": str(tenant)},
            )
            await session.commit()
        session.info[TENANT_ID_SESSION_KEY] = team_id
        ids = (await session.scalars(select(m.EnergyIntervalFact.id))).all()
        cleaner = ProjectionCleanup(session, month="2026-10", batch_size=73)
        report = await cleaner.execute()
        assert report["dry_run"]
        assert not report["blocked"]
        assert report["tables"][0]["total"] == 2020
        assert report["tables"][0]["obsolete"] == 1920
        with pytest.raises(CleanupBlockedError, match="paused writers"):
            await cleaner.execute(apply=True)
        with pytest.raises(CleanupBlockedError, match="explicit backup waiver"):
            await cleaner.execute(apply=True, writers_paused=True)
        result = await cleaner.execute(apply=True, writers_paused=True, backup_waived=True)
        assert result["backup_waived"]
        assert result["deleted"]["dataapp_energyintervalfact"] == 1920
        assert sorted((await session.scalars(select(m.EnergyIntervalFact.id))).all()) == sorted(ids)
        assert await session.scalar(select(func.sum(m.EnergyIntervalFact.amount))) == Decimal(2000)
        assert await session.scalar(select(func.max(m.EnergyIntervalFact.revision_no))) == 20
        again = await cleaner.execute(apply=True, writers_paused=True, backup_verified=True)
        assert not any(again["deleted"].values())
        session.info[TENANT_ID_SESSION_KEY] = other_id
        other_report = await ProjectionCleanup(session).execute()
        assert other_report["tables"][0]["obsolete"] == 1920
        # Leave a valid current-only schema for subsequent tests.
        await ProjectionCleanup(session).execute(apply=True, writers_paused=True, backup_verified=True)
    finally:
        await session.rollback()
        await session.execute(
            text("DELETE FROM dataapp_energyintervalfact WHERE team_id IN (:a,:b)"), {"a": team_id, "b": other_id}
        )
        await session.execute(
            text(
                "ALTER TABLE dataapp_energyintervalfact ADD CONSTRAINT uq_energy_interval_team_source_record UNIQUE(team_id,source_system,source_record_id)"
            )
        )
        await session.execute(
            text(
                "ALTER TABLE dataapp_energyintervalfact ADD CONSTRAINT ck_dataapp_energyintervalfact_ck_energy_interval_current_only CHECK(is_current AND revision_no>=1 AND supersedes_id IS NULL)"
            )
        )
        await session.commit()


async def test_schema_migration_refuses_dirty_data_and_accepts_cleaned_data(session):  # noqa: PLR0915 - full migration rehearsal
    from importlib import import_module

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = import_module("app.db.migrations.versions.2026_10_26_current_only_projections_c0261026a001")

    async def run_migration(name):
        conn = await session.connection()

        def execute(sync_conn):
            context = MigrationContext.configure(sync_conn, opts={"target_metadata": m.EnergyIntervalFact.metadata})
            with Operations.context(context):
                getattr(migration, name)()

        await conn.run_sync(execute)

    team = m.Team(name="Migration preview", slug="projection-migration-preview")
    session.add(team)
    await session.commit()
    team_id = team.id
    session.info[TENANT_ID_SESSION_KEY] = team_id
    await run_migration("downgrade")
    await session.commit()
    await session.execute(
        text("""
        INSERT INTO dataapp_energyintervalfact
        (id, team_id, source_system, source_record_id, energy_type_code, granularity,
         period_start, period_end, amount, unit, data_quality, revision_no, is_current, created_at, updated_at)
        SELECT nextval('dataapp_energyintervalfact_id_seq'), CAST(:team AS uuid), 'meter_projection', 'migrate-key',
               'electricity', 'hour', timestamp '2026-10-01', timestamp '2026-10-01 01:00:00', 5,
               'kWh', 'measured', r, r=2, now(), now() FROM generate_series(1,2) r
    """),
        {"team": str(team_id)},
    )
    await session.commit()
    try:
        with pytest.raises(RuntimeError, match="audited projection cleanup"):
            await run_migration("upgrade")
        await session.rollback()
        # A real external FK must block deletion, even if it specifies ON DELETE SET NULL.
        await session.execute(
            text(
                "CREATE TABLE projection_cleanup_reference (fact_id bigint REFERENCES dataapp_energyintervalfact(id) ON DELETE SET NULL)"
            )
        )
        await session.execute(
            text(
                "INSERT INTO projection_cleanup_reference SELECT id FROM dataapp_energyintervalfact WHERE team_id=:team AND NOT is_current"
            ),
            {"team": team_id},
        )
        await session.commit()
        cleaner = ProjectionCleanup(session)
        report = await cleaner.execute()
        assert report["blocked"]
        assert report["tables"][0]["references"][0]["table"] == "projection_cleanup_reference"
        with pytest.raises(CleanupBlockedError, match="unresolved references"):
            await cleaner.execute(apply=True, writers_paused=True, backup_verified=True)
        await session.rollback()
        await session.execute(text("DROP TABLE projection_cleanup_reference"))
        await session.commit()
        from datetime import date

        obsolete_id = await session.scalar(
            text("SELECT id FROM dataapp_energyintervalfact WHERE team_id=:team AND NOT is_current"), {"team": team_id}
        )
        unrelated = m.GhgActivityRecord(
            record_code="UNRELATED",
            inventory_code="INV",
            organization_code="ORG",
            facility_code="FAC",
            source_code="FUEL",
            activity_code="UNRELATED",
            activity_name="Unrelated numeric ID",
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            iso_category_code="1.1",
            ghg_scope="scope1",
            source_mechanism="stationary_combustion",
            value_chain_position="internal",
            boundary_status="included",
            activity_amount=Decimal(5),
            activity_unit="kg",
            data_source_type="measured",
            measurement_method="invoice",
            quality_status="pass",
            status="draft",
            source_system="legacy_migration",
            source_record_type="Scope1StationaryCombustion",
            source_record_id=obsolete_id,
            source_payload={},
        )
        session.add(unrelated)
        await session.commit()
        assert not (await cleaner.execute())["blocked"]
        activity = m.GhgActivityRecord(
            record_code="REF",
            inventory_code="INV",
            organization_code="ORG",
            facility_code="FAC",
            source_code="ELEC",
            activity_code="REF",
            activity_name="Reference preview",
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            iso_category_code="2.1",
            ghg_scope="scope2",
            source_mechanism="purchased_energy",
            value_chain_position="internal",
            boundary_status="included",
            activity_amount=Decimal(5),
            activity_unit="kWh",
            data_source_type="measured",
            measurement_method="meter",
            quality_status="pass",
            status="draft",
            source_system="energy_fact",
            source_record_type="meter_month",
            source_record_id=obsolete_id,
            source_payload={"fact_ids": [obsolete_id]},
        )
        session.add(activity)
        await session.commit()
        activity_id = activity.id
        report = await cleaner.execute()
        assert report["blocked"]
        assert report["tables"][0]["references"][0]["column"] == "source_payload.fact_ids"
        await session.execute(
            text("DELETE FROM ghg_activity_record WHERE team_id=:team AND id=:id"), {"team": team_id, "id": activity_id}
        )
        await session.commit()
        await cleaner.execute(apply=True, writers_paused=True, backup_verified=True)
        await run_migration("upgrade")
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(m.EnergyIntervalFact)) == 1
        assert await session.scalar(select(m.EnergyIntervalFact.revision_no)) == 2
    except BaseException:
        await session.rollback()
        await session.execute(text("DROP TABLE IF EXISTS projection_cleanup_reference"))
        await session.execute(text("DELETE FROM dataapp_energyintervalfact WHERE team_id=:team"), {"team": team_id})
        await session.commit()
        await run_migration("upgrade")
        await session.commit()
        raise
