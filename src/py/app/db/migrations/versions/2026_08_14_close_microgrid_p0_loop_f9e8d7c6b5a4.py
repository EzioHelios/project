"""close the microgrid P0 strategy and audit loop

Revision ID: f9e8d7c6b5a4
Revises: a0b1c2d3e4f5
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f9e8d7c6b5a4"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None

BINDING_TABLE = "microgrid_asset_meter_binding"


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    return constraint_name in {
        foreign_key["name"] for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
    }


def _add_column_if_missing(table_name: str, column: sa.Column[object]) -> None:
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _enable_tenant_rls(table_name: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    policy_name = f"rls_{table_name}_tenant_scope"
    op.execute(sa.text(f"alter table {table_name} enable row level security"))
    op.execute(sa.text(f"alter table {table_name} force row level security"))
    op.execute(sa.text(f"drop policy if exists {policy_name} on {table_name}"))
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


def upgrade() -> None:
    if not _table_exists(BINDING_TABLE):
        op.create_table(
            BINDING_TABLE,
            sa.Column("site_id", sa.BigInteger(), nullable=False),
            sa.Column("asset_id", sa.BigInteger(), nullable=False),
            sa.Column("equipment_id", sa.BigInteger(), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("point_code", sa.String(length=64), nullable=False, server_default="forward_active_total"),
            sa.Column("direction", sa.String(length=16), nullable=False, server_default="import"),
            sa.Column("sign", sa.Numeric(8, 4), nullable=False, server_default="1"),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source_kind", sa.String(length=32), nullable=False, server_default="manual_configuration"),
            sa.Column("source_name", sa.String(length=128), nullable=False, server_default="管理员手工绑定"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("team_id", sa.Uuid(), nullable=False),
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["site_id"], ["microgrid_site.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["microgrid_asset.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["equipment_id"], ["dataapp_monitorequipment.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "team_id",
                "site_id",
                "asset_id",
                "equipment_id",
                "point_code",
                "direction",
                name="uq_microgrid_binding_resource_meter",
            ),
        )
    _create_index_if_missing("ix_microgrid_asset_meter_binding_site_id", BINDING_TABLE, ["site_id"])
    _create_index_if_missing("ix_microgrid_asset_meter_binding_asset_id", BINDING_TABLE, ["asset_id"])
    _create_index_if_missing("ix_microgrid_asset_meter_binding_equipment_id", BINDING_TABLE, ["equipment_id"])
    _create_index_if_missing(
        "ix_microgrid_binding_site_role",
        BINDING_TABLE,
        ["team_id", "site_id", "role", "enabled"],
    )
    _create_index_if_missing("ix_microgrid_asset_meter_binding_team_id", BINDING_TABLE, ["team_id"])
    _enable_tenant_rls(BINDING_TABLE)

    _add_column_if_missing("microgrid_scenario", sa.Column("tariff_plan_id", sa.BigInteger(), nullable=True))
    _add_column_if_missing(
        "microgrid_scenario",
        sa.Column("grid_emission_factor_id", sa.BigInteger(), nullable=True),
    )
    _add_column_if_missing(
        "microgrid_scenario",
        sa.Column("based_on_scenario_id", sa.BigInteger(), nullable=True),
    )
    _add_column_if_missing(
        "microgrid_scenario",
        sa.Column("change_summary", sa.String(length=255), nullable=True),
    )
    if not _foreign_key_exists("microgrid_scenario", "fk_microgrid_scenario_tariff_plan_id"):
        op.create_foreign_key(
            "fk_microgrid_scenario_tariff_plan_id",
            "microgrid_scenario",
            "dataapp_energytariffplan",
            ["tariff_plan_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _foreign_key_exists("microgrid_scenario", "fk_microgrid_scenario_grid_emission_factor_id"):
        op.create_foreign_key(
            "fk_microgrid_scenario_grid_emission_factor_id",
            "microgrid_scenario",
            "dataapp_emissionfactor",
            ["grid_emission_factor_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _foreign_key_exists("microgrid_scenario", "fk_microgrid_scenario_based_on_scenario_id"):
        op.create_foreign_key(
            "fk_microgrid_scenario_based_on_scenario_id",
            "microgrid_scenario",
            "microgrid_scenario",
            ["based_on_scenario_id"],
            ["id"],
            ondelete="SET NULL",
        )
    for column in ("tariff_plan_id", "grid_emission_factor_id", "based_on_scenario_id"):
        _create_index_if_missing(f"ix_microgrid_scenario_{column}", "microgrid_scenario", [column])

    _add_column_if_missing(
        "microgrid_forecast_run",
        sa.Column("quality_status", sa.String(length=16), nullable=False, server_default="warning"),
    )
    _add_column_if_missing(
        "microgrid_forecast_run",
        sa.Column("quality_checks", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    _add_column_if_missing(
        "microgrid_forecast_run",
        sa.Column("history_source_kind", sa.String(length=32), nullable=False, server_default="simulated"),
    )
    _add_column_if_missing(
        "microgrid_forecast_run",
        sa.Column("history_coverage_pct", sa.Numeric(7, 4), nullable=True),
    )
    _create_index_if_missing(
        "ix_microgrid_forecast_run_quality_status",
        "microgrid_forecast_run",
        ["quality_status"],
    )
    _create_index_if_missing(
        "ix_microgrid_forecast_run_history_source_kind",
        "microgrid_forecast_run",
        ["history_source_kind"],
    )

    _add_column_if_missing(
        "microgrid_optimization_run",
        sa.Column("purpose", sa.String(length=16), nullable=False, server_default="operational"),
    )
    _add_column_if_missing(
        "microgrid_optimization_run",
        sa.Column("baseline_peak_kw", sa.Numeric(18, 6), nullable=True),
    )
    _add_column_if_missing(
        "microgrid_optimization_run",
        sa.Column("optimized_peak_kw", sa.Numeric(18, 6), nullable=True),
    )
    _add_column_if_missing(
        "microgrid_optimization_run",
        sa.Column("peak_change_kw", sa.Numeric(18, 6), nullable=True),
    )
    _create_index_if_missing(
        "ix_microgrid_optimization_run_purpose",
        "microgrid_optimization_run",
        ["purpose"],
    )


def downgrade() -> None:
    op.drop_index("ix_microgrid_optimization_run_purpose", table_name="microgrid_optimization_run")
    for column in ("peak_change_kw", "optimized_peak_kw", "baseline_peak_kw", "purpose"):
        op.drop_column("microgrid_optimization_run", column)

    op.drop_index("ix_microgrid_forecast_run_history_source_kind", table_name="microgrid_forecast_run")
    op.drop_index("ix_microgrid_forecast_run_quality_status", table_name="microgrid_forecast_run")
    for column in ("history_coverage_pct", "history_source_kind", "quality_checks", "quality_status"):
        op.drop_column("microgrid_forecast_run", column)

    for column in ("based_on_scenario_id", "grid_emission_factor_id", "tariff_plan_id"):
        op.drop_index(f"ix_microgrid_scenario_{column}", table_name="microgrid_scenario")
    op.drop_constraint("fk_microgrid_scenario_based_on_scenario_id", "microgrid_scenario", type_="foreignkey")
    op.drop_constraint("fk_microgrid_scenario_grid_emission_factor_id", "microgrid_scenario", type_="foreignkey")
    op.drop_constraint("fk_microgrid_scenario_tariff_plan_id", "microgrid_scenario", type_="foreignkey")
    for column in ("change_summary", "based_on_scenario_id", "grid_emission_factor_id", "tariff_plan_id"):
        op.drop_column("microgrid_scenario", column)
    op.drop_table(BINDING_TABLE)
