
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "py"))

from sqlalchemy import MetaData, create_engine, delete, insert, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Fix for Windows asyncio loop policy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

VIEWS_FILE = Path(__file__).parent / "recreate_views.sql"

from app.db import models as m


async def _copy_table(
    old_conn,
    dst_session,
    src_name: str,
    dst_model,
    metadata: MetaData,
    chunk_size: int = 50000
) -> None:
    src_table = metadata.tables.get(src_name)
    if src_table is None:
        print(f"Skipping {src_name}: table not found in source database.")
        return

    print(f"Migrating {src_name} -> {dst_model.__tablename__}...")

    # Clear target table
    await dst_session.execute(delete(dst_model))
    await dst_session.commit()

    # Determine total count
    total_count = old_conn.execute(text(f"SELECT count(*) FROM {src_name}")).scalar()
    if total_count == 0:
        print(f"  - No data in {src_name}.")
        return

    print(f"  - Total rows to migrate: {total_count}")

    # Check if 'id' exists for faster paging
    has_id = "id" in src_table.columns

    # Process in chunks
    offset = 0
    last_id = 0

    while offset < total_count:
        if has_id:
            stmt = select(src_table).where(src_table.c.id > last_id).order_by(src_table.c.id).limit(chunk_size)
        else:
            stmt = select(src_table).offset(offset).limit(chunk_size)

        src_result = old_conn.execute(stmt)
        rows = src_result.mappings().all()

        if not rows:
            break

        payload = [dict(row) for row in rows]
        await dst_session.execute(insert(dst_model), payload)
        await dst_session.commit()

        if has_id:
            last_id = rows[-1]["id"]

        offset += len(rows)
        print(f"  - Migrated {offset}/{total_count} rows...")

    print(f"  - Successfully migrated {total_count} rows.")

async def migrate_all() -> None:
    old_db_url_sync = os.environ["OLD_DB_URL"]
    new_db_url_async = os.environ["NEW_DB_URL"]

    print(f"Source DB (Sync): {old_db_url_sync}")
    print(f"Target DB (Async): {new_db_url_async}")

    old_engine = create_engine(old_db_url_sync)
    new_engine = create_async_engine(new_db_url_async)
    NewSession = async_sessionmaker(new_engine, expire_on_commit=False)

    metadata = MetaData()
    print("Reflecting source database schema...")
    with old_engine.connect() as old_conn:
        metadata.reflect(bind=old_conn)

        # Mapping (Source Table -> Target Model)
        # Ordered by dependency if possible, but SET session_replication_role = 'replica' handles FKs.
        mapping = [
            ("dataapp_enterpriseinfo", m.EnterpriseInfo),
            ("dataapp_monitorsector", m.MonitorSector),
            ("dataapp_monitorsectorphoto", m.MonitorSectorPhoto),
            ("dataapp_monitorequipment", m.MonitorEquipment),
            ("dataapp_ammeterindexvalue", m.AmmeterIndexValue),
            ("dataapp_videomonitor", m.VideoMonitor),
            ("dataapp_apiresultkeymapping", m.ApiResultKeyMapping),
            ("dataapp_inmoney", m.InMoney),
            ("dataapp_outmoney", m.OutMoney),
            ("dataapp_employeecommute", m.EmployeeCommute),
            ("dataapp_warningrule", m.WarningRule),
            ("dataapp_alarmevent", m.AlarmEvent),
            ("dataapp_vedioalarmevent", m.VedioAlarmEvent),
            ("dataapp_energystoragevalue", m.EnergyStorageValue),
            ("dataapp_auditlog", m.CarbonAuditLog),
            ("dataapp_emissionfactor", m.EmissionFactor),
            ("dataapp_scope1mobilecombustion", m.Scope1MobileCombustion),
            ("dataapp_scope1stationarycombustion", m.Scope1StationaryCombustion),
            ("dataapp_scope1refrigerantleak", m.Scope1RefrigerantLeak),
            ("dataapp_scope2electricitybill", m.Scope2ElectricityBill),
            ("dataapp_scope3wastedisposal", m.Scope3WasteDisposal),
            ("dataapp_scope3thirdpartytransport", m.Scope3ThirdPartyTransport),
        ]

        async with NewSession() as new_sess:
            # Set replication role to bypass FK checks
            await new_sess.execute(text("SET session_replication_role = 'replica';"))
            await new_sess.commit()

            for src_name, dst_model in mapping:
                try:
                    await _copy_table(old_conn, new_sess, src_name, dst_model, metadata)
                except Exception as e:
                    print(f"Error migrating {src_name}: {e}")
                    await new_sess.rollback()

            # Restore replication role
            await new_sess.execute(text("SET session_replication_role = 'origin';"))
            await new_sess.commit()
            print("Data migration complete.")

            # Recreate views
            print("Recreating views...")
            if VIEWS_FILE.exists():
                with open(VIEWS_FILE, encoding="utf-8") as f:
                    content = f.read()
                    content = content.replace("public.", "")
                    statements = [s.strip() for s in content.split(";") if s.strip()]
                    for stmt in statements:
                        try:
                            await new_sess.execute(text(stmt))
                            await new_sess.commit()
                        except Exception as e:
                            err_msg = str(e).split("\n")[0]
                            print(f"Error creating view: {err_msg[:120]}...")
                            await new_sess.rollback()
                print("Views recreated.")

    await new_engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_all())
