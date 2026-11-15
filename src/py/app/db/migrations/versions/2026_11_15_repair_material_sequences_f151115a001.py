"""Restore the three ID sequences omitted by the frozen f7a8b9c0d1e2 DDL.

The models already use these explicit sequences. Preserve existing rows and
sequence progress; do not replace the models with identity columns.
"""

import sqlalchemy as sa
from alembic import op

revision = "f151115a001"
down_revision = "e061106a001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Repair only the material handling/allocation tables, within the DDL transaction."""
    op.execute(
        sa.text("""
DO $repair$
DECLARE
    table_name text;
    sequence_name text;
    table_oid regclass;
    sequence_oid regclass;
    owner_oid oid;
    identity_kind text;
    default_expression text;
    maximum_id bigint;
    sequence_last bigint;
    sequence_called boolean;
    previous_bypass text := current_setting('app.tenant_bypass', true);
BEGIN
    -- This schema migration must inspect all tenants when choosing the next ID.
    PERFORM set_config('app.tenant_bypass', 'true', true);
    FOREACH table_name IN ARRAY ARRAY[
        'dataapp_materialhandlingoperation',
        'carbon_material_allocation_run',
        'carbon_material_allocation_result'
    ] LOOP
        table_oid := format('public.%I', table_name)::regclass;
        sequence_name := table_name || '_id_seq';
        EXECUTE format('LOCK TABLE public.%I IN SHARE ROW EXCLUSIVE MODE', table_name);
        SELECT a.attidentity, pg_get_expr(d.adbin, d.adrelid)
          INTO identity_kind, default_expression
          FROM pg_attribute a
          LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
         WHERE a.attrelid = table_oid AND a.attname = 'id';
        IF identity_kind IS DISTINCT FROM '' THEN
            RAISE EXCEPTION 'Unexpected identity or missing id column on %', table_name;
        END IF;
        IF default_expression IS NOT NULL AND default_expression NOT IN (
            format('nextval(%L::regclass)', sequence_name),
            format('nextval(%L::regclass)', 'public.' || sequence_name)
        ) THEN
            RAISE EXCEPTION 'Unexpected id default on %: %', table_name, default_expression;
        END IF;
        EXECUTE format('SELECT max(id) FROM public.%I', table_name) INTO maximum_id;
        sequence_oid := to_regclass(format('public.%I', sequence_name));
        IF sequence_oid IS NULL THEN
            EXECUTE format('CREATE SEQUENCE public.%I AS bigint START WITH %s',
                sequence_name, greatest(coalesce(maximum_id, 0) + 1, 1));
            sequence_oid := to_regclass(format('public.%I', sequence_name));
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_sequence WHERE seqrelid = sequence_oid AND seqincrement = 1 AND NOT seqcycle
        ) THEN
            RAISE EXCEPTION 'Unexpected sequence definition for %', sequence_name;
        END IF;
        SELECT refobjid INTO owner_oid FROM pg_depend
         WHERE classid = 'pg_class'::regclass AND objid = sequence_oid
           AND refclassid = 'pg_class'::regclass AND deptype IN ('a', 'i');
        IF owner_oid IS NOT NULL AND owner_oid <> table_oid THEN
            RAISE EXCEPTION 'Sequence % belongs to another table', sequence_name;
        END IF;
        EXECUTE format('SELECT last_value, is_called FROM public.%I', sequence_name)
           INTO sequence_last, sequence_called;
        IF maximum_id IS NOT NULL AND
           sequence_last + (CASE WHEN sequence_called THEN 1 ELSE 0 END) <= maximum_id THEN
            -- Transactional RESTART only moves this table's generator forward.
            EXECUTE format('ALTER SEQUENCE public.%I RESTART WITH %s', sequence_name, maximum_id + 1);
        END IF;
        EXECUTE format('ALTER SEQUENCE public.%I OWNED BY public.%I.id', sequence_name, table_name);
        EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET DEFAULT nextval(%L::regclass)',
            table_name, 'public.' || sequence_name);
    END LOOP;
    PERFORM set_config('app.tenant_bypass', coalesce(previous_bypass, ''), true);
END;
$repair$;
""")
    )


def downgrade() -> None:
    """Keep ID generators: older models need them too, and they may predate this repair."""
