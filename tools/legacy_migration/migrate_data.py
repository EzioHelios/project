import datetime
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "py"))

from app.lib.settings import get_settings

# Use settings for target database
settings = get_settings()
target_ds = settings.db.URL.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")

# Legacy database URL from environment
source_ds = os.environ["OLD_DB_URL"]

# Map of Target Table -> Source Table
TABLES_MAP = {
    "dataapp_enterpriseinfo": "dataapp_enterpriseinfo",
    "dataapp_monitorsector": "dataapp_monitorsector",
    "dataapp_monitorsectorphoto": "dataapp_monitorsectorphoto",
    "dataapp_monitorequipment": "dataapp_monitorequipment",
    "dataapp_ammeterindexvalue": "dataapp_ammeterindexvalue",
    "dataapp_videomonitor": "dataapp_videomonitor",
    "dataapp_apiresultkeymapping": "dataapp_apiresultkeymapping",
    "dataapp_warningrule": "dataapp_warningrule",
    "dataapp_alarmevent": "dataapp_alarmevent",
    "dataapp_vedioalarmevent": "dataapp_vedioalarmevent",
    "dataapp_energystoragevalue": "dataapp_energystoragevalue",
    "dataapp_scope1mobilecombustion": "dataapp_scope1mobilecombustion",
    "dataapp_scope1stationarycombustion": "dataapp_scope1stationarycombustion",
    "dataapp_scope1refrigerantleak": "dataapp_scope1refrigerantleak",
    "dataapp_scope2electricitybill": "dataapp_scope2electricitybill",
    "dataapp_scope3wastedisposal": "dataapp_scope3wastedisposal",
    "dataapp_scope3thirdpartytransport": "dataapp_scope3thirdpartytransport",
    "dataapp_emissionfactor": "dataapp_emissionfactor",
    "dataapp_carbonauditlog": "dataapp_carbonauditlog",
    "dataapp_employeecommute": "dataapp_employeecommute",
    "dataapp_inmoney": "dataapp_inmoney",
    "dataapp_outmoney": "dataapp_outmoney",
}

def migrate():
    try:
        print(f"Connecting to source: {source_ds}")
        print(f"Connecting to target: {target_ds}")

        s_conn = psycopg.connect(source_ds)
        t_conn = psycopg.connect(target_ds)

        s_cur = s_conn.cursor()
        t_cur = t_conn.cursor()

        # 1. Migrate Users
        print("Migrating users first...")
        s_cur.execute(
            "SELECT id, username, email, is_active, is_superuser, date_joined FROM auth_user"
        )
        users = s_cur.fetchall()
        user_id_map = {}

        for u_id, username, email, is_active, is_superuser, joined_at in users:
            new_id = uuid4()
            user_id_map[u_id] = new_id
            now = datetime.datetime.now(datetime.UTC)
            # Check if user already exists
            t_cur.execute("SELECT id FROM user_account WHERE username = %s", (username,))
            if t_cur.fetchone():
                print(f"  User {username} already exists, skipping.")
                continue

            t_cur.execute(
                """INSERT INTO user_account 
                (id, username, email, is_active, is_superuser, is_verified, joined_at, 
                 login_count, failed_reset_attempts, is_two_factor_enabled, 
                 created_at, updated_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    new_id, username, email, is_active, is_superuser, True,
                    joined_at.date(), 0, 0, False, now, now
                )
            )

        print("Migrated users.")

        # 2. Migrate Carbon Tables
        t_cur.execute("SET session_replication_role = 'replica'")

        for target_table, source_table in TABLES_MAP.items():
            print(f"Migrating table: {source_table} -> {target_table}")

            # Get columns for source
            s_cur.execute(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_name = '{source_table}' ORDER BY ordinal_position"
            )
            s_cols = [r[0] for r in s_cur.fetchall()]

            # Get columns for target
            t_cur.execute(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_name = '{target_table}' ORDER BY ordinal_position"
            )
            t_cols = [r[0] for r in t_cur.fetchall()]

            if not s_cols:
                print(f"  Source table {source_table} not found, skipping.")
                continue

            s_cur.execute(f"SELECT * FROM {source_table}")
            rows = s_cur.fetchall()

            if not rows:
                print(f"  Empty table {source_table}, skipping.")
                continue

            # Identify columns that exist in both
            common_cols = [col for col in s_cols if col in t_cols]

            placeholders = ", ".join(["%s"] * len(common_cols))
            col_names = ", ".join(common_cols)
            insert_query = f"INSERT INTO {target_table} ({col_names}) VALUES ({placeholders})"

            # Clear target table first (optional, but safer for re-runs)
            t_cur.execute(f"TRUNCATE TABLE {target_table} CASCADE")

            for row in rows:
                row_dict = dict(zip(s_cols, row))

                # Special mapping for audit logs operator_id (UUID mapping)
                if target_table == "dataapp_carbonauditlog":
                    legacy_op_id = row_dict.get("operator_id")
                    if legacy_op_id in user_id_map:
                        row_dict["operator_id"] = user_id_map[legacy_op_id]
                    else:
                        row_dict["operator_id"] = None

                # Extract values for the common columns
                vals = []
                for col in common_cols:
                    val = row_dict[col]
                    if isinstance(val, dict):
                        val = json.dumps(val)
                    vals.append(val)
                t_cur.execute(insert_query, vals)

            print(f"  Migrated {len(rows)} rows.")

        # Re-enable triggers
        t_cur.execute("SET session_replication_role = 'origin'")

        # 3. Reset sequences
        print("Resetting sequences...")
        for table in TABLES_MAP:
             t_cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}' AND column_name = 'id'")
             res = t_cur.fetchone()
             if res and res[1] in ("bigint", "integer"):
                 t_cur.execute(f"SELECT pg_get_serial_sequence('{table}', 'id')")
                 seq_res = t_cur.fetchone()
                 if seq_res and seq_res[0]:
                     seq = seq_res[0]
                     t_cur.execute(
                         f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}), 1))"
                     )

        t_conn.commit()
        print("Migration completed successfully!")

    except Exception as e:
        print(f"Migration failed: {e}")
        if "t_conn" in locals():
            t_conn.rollback()
    finally:
        if "s_conn" in locals(): s_conn.close()
        if "t_conn" in locals(): t_conn.close()

if __name__ == "__main__":
    migrate()
