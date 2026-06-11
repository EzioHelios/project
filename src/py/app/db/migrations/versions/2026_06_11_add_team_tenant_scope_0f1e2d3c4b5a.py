"""add team tenant scope

Revision ID: 0f1e2d3c4b5a
Revises: c1d2e3f4a5b6
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID
from alembic import op

revision = "0f1e2d3c4b5a"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]

DEFAULT_TENANT_ID = "00000000-0000-7000-8000-000000000001"
DEFAULT_TENANT_SLUG = "default-tenant"

TENANT_TABLES = (
    "dataapp_enterpriseinfo",
    "dataapp_employeecommute",
    "dataapp_monitorsector",
    "dataapp_monitorsectorphoto",
    "dataapp_inmoney",
    "dataapp_outmoney",
    "dataapp_monitorequipment",
    "dataapp_devicepoint",
    "dataapp_ammeterindexvalue",
    "dataapp_videomonitor",
    "dataapp_warningrule",
    "dataapp_alarmevent",
    "dataapp_vedioalarmevent",
    "dataapp_energystoragevalue",
    "dataapp_scope1mobilecombustion",
    "dataapp_scope1stationarycombustion",
    "dataapp_scope1refrigerantleak",
    "dataapp_scope2electricitybill",
    "dataapp_scope2meteraggregate",
    "dataapp_scope3wastedisposal",
    "dataapp_scope3thirdpartytransport",
    "dataapp_iottelemetry",
    "dataapp_carbonauditlog",
)


def _team_id_column() -> sa.Column:
    return sa.Column("team_id", sa.GUID(length=16), nullable=True)


def _add_team_column(table_name: str) -> None:
    op.add_column(table_name, _team_id_column())
    op.execute(
        sa.text(
            f"update {table_name} set team_id = cast(:team_id as uuid) where team_id is null"  # noqa: S608
        ).bindparams(
            team_id=DEFAULT_TENANT_ID,
        )
    )
    op.alter_column(table_name, "team_id", nullable=False)
    op.create_foreign_key(
        f"fk_{table_name}_team_id_team",
        table_name,
        "team",
        ["team_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f(f"ix_{table_name}_team_id"), table_name, ["team_id"])


def _drop_team_column(table_name: str) -> None:
    op.drop_index(op.f(f"ix_{table_name}_team_id"), table_name=table_name)
    op.drop_constraint(f"fk_{table_name}_team_id_team", table_name, type_="foreignkey")
    op.drop_column(table_name, "team_id")


def _tenant_policy_name(table_name: str) -> str:
    return f"rls_{table_name}_tenant_scope"


def _enable_tenant_rls(table_name: str) -> None:
    policy_name = _tenant_policy_name(table_name)
    op.execute(sa.text(f"alter table {table_name} enable row level security"))
    op.execute(sa.text(f"alter table {table_name} force row level security"))
    op.execute(
        sa.text(
            f"""
            create policy {policy_name} on {table_name}
            using (
                current_setting('app.tenant_bypass', true) = 'true'
                or team_id::text = nullif(current_setting('app.tenant_id', true), '')
            )
            with check (
                current_setting('app.tenant_bypass', true) = 'true'
                or team_id::text = nullif(current_setting('app.tenant_id', true), '')
            )
            """
        )
    )


def _disable_tenant_rls(table_name: str) -> None:
    policy_name = _tenant_policy_name(table_name)
    op.execute(sa.text(f"drop policy if exists {policy_name} on {table_name}"))
    op.execute(sa.text(f"alter table {table_name} no force row level security"))
    op.execute(sa.text(f"alter table {table_name} disable row level security"))


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            insert into team (id, name, description, is_active, slug, sa_orm_sentinel, created_at, updated_at)
            values (
                cast(:team_id as uuid),
                'Default Tenant',
                'Default team used to own data created before tenant isolation.',
                true,
                :slug,
                null,
                current_timestamp,
                current_timestamp
            )
            on conflict (slug) do nothing
            """
        ).bindparams(team_id=DEFAULT_TENANT_ID, slug=DEFAULT_TENANT_SLUG)
    )

    for table_name in TENANT_TABLES:
        _add_team_column(table_name)

    op.drop_constraint(op.f("uq_dataapp_monitorsector_code"), "dataapp_monitorsector", type_="unique")
    op.create_unique_constraint(
        "uq_dataapp_monitorsector_team_code",
        "dataapp_monitorsector",
        ["team_id", "code"],
    )
    op.drop_index(op.f("ix_dataapp_monitorequipment_code"), table_name="dataapp_monitorequipment")
    op.create_index(op.f("ix_dataapp_monitorequipment_code"), "dataapp_monitorequipment", ["code"])
    op.create_unique_constraint(
        "uq_dataapp_monitorequipment_team_code",
        "dataapp_monitorequipment",
        ["team_id", "code"],
    )
    op.drop_constraint("uq_scope2_meter_aggregate_meter_month", "dataapp_scope2meteraggregate", type_="unique")
    op.create_unique_constraint(
        "uq_scope2_meter_aggregate_team_meter_month",
        "dataapp_scope2meteraggregate",
        ["team_id", "ammeter_id", "billing_month"],
    )
    op.drop_index("ix_scope2_meter_aggregate_month_area", table_name="dataapp_scope2meteraggregate")
    op.create_index(
        "ix_scope2_meter_aggregate_team_month_area",
        "dataapp_scope2meteraggregate",
        ["team_id", "billing_month", "area_id"],
    )

    for table_name in TENANT_TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TENANT_TABLES):
        _disable_tenant_rls(table_name)

    op.drop_index("ix_scope2_meter_aggregate_team_month_area", table_name="dataapp_scope2meteraggregate")
    op.create_index(
        "ix_scope2_meter_aggregate_month_area",
        "dataapp_scope2meteraggregate",
        ["billing_month", "area_id"],
    )
    op.drop_constraint(
        "uq_scope2_meter_aggregate_team_meter_month",
        "dataapp_scope2meteraggregate",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_scope2_meter_aggregate_meter_month",
        "dataapp_scope2meteraggregate",
        ["ammeter_id", "billing_month"],
    )
    op.drop_constraint("uq_dataapp_monitorequipment_team_code", "dataapp_monitorequipment", type_="unique")
    op.drop_index(op.f("ix_dataapp_monitorequipment_code"), table_name="dataapp_monitorequipment")
    op.create_index(op.f("ix_dataapp_monitorequipment_code"), "dataapp_monitorequipment", ["code"], unique=True)
    op.drop_constraint("uq_dataapp_monitorsector_team_code", "dataapp_monitorsector", type_="unique")
    op.create_unique_constraint(op.f("uq_dataapp_monitorsector_code"), "dataapp_monitorsector", ["code"])

    for table_name in reversed(TENANT_TABLES):
        _drop_team_column(table_name)

    op.execute(sa.text("delete from team where slug = :slug").bindparams(slug=DEFAULT_TENANT_SLUG))
