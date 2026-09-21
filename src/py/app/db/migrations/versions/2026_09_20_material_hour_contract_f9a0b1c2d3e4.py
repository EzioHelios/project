"""Make handling allocation an explicit hourly contract without deleting history."""

import sqlalchemy as sa
from alembic import op

revision = "f9a0b1c2d3e4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dataapp_materialhandlingoperation", sa.Column("material_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_handling_material",
        "dataapp_materialhandlingoperation",
        "dataapp_productionproduct",
        ["material_id"],
        ["id"],
    )
    op.create_index("ix_handling_material", "dataapp_materialhandlingoperation", ["material_id"])
    op.add_column("dataapp_materialhandlingoperation", sa.Column("active_intervals", sa.JSON(), nullable=True))
    op.add_column("carbon_material_allocation_run", sa.Column("equipment_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_allocation_equipment",
        "carbon_material_allocation_run",
        "dataapp_monitorequipment",
        ["equipment_id"],
        ["id"],
    )
    op.add_column("carbon_material_allocation_run", sa.Column("factor_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_allocation_factor", "carbon_material_allocation_run", "dataapp_emissionfactor", ["factor_id"], ["id"]
    )
    op.add_column("carbon_material_allocation_run", sa.Column("input_hash", sa.String(64), nullable=True))
    op.add_column(
        "carbon_material_allocation_run", sa.Column("revision", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "carbon_material_allocation_run", sa.Column("unallocated_energy_kwh", sa.Numeric(18, 6), nullable=True)
    )
    op.create_unique_constraint(
        "uq_material_allocation_equipment_hour",
        "carbon_material_allocation_run",
        ["team_id", "equipment_id", "period_start"],
    )
    # This transaction is a deliberate schema/data migration, not an application tenant read.
    op.execute("SELECT set_config('app.tenant_bypass', 'true', true)")
    op.execute("UPDATE carbon_material_allocation_run SET status='stale'")
    op.execute("UPDATE carbon_material_allocation_result SET data_status='stale'")
    op.execute(
        "UPDATE carbon_product_footprint_inventory_item SET calc_status='stale_source' WHERE source_type='material_allocation'"
    )
    op.execute("UPDATE dataapp_materialhandlingoperation SET operation_status='draft' WHERE active_intervals IS NULL")
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys("carbon_material_allocation_result"):
        if fk["constrained_columns"] == ["operation_id"]:
            op.drop_constraint(fk["name"], "carbon_material_allocation_result", type_="foreignkey")
    op.create_foreign_key(
        "fk_allocation_operation",
        "carbon_material_allocation_result",
        "dataapp_materialhandlingoperation",
        ["operation_id"],
        ["id"],
    )
    op.create_index(
        "uq_pcf_material_source",
        "carbon_product_footprint_inventory_item",
        ["team_id", "study_id", "source_ref"],
        unique=True,
        postgresql_where=sa.text("source_type = 'material_allocation'"),
    )


def downgrade() -> None:
    op.drop_index("uq_pcf_material_source", table_name="carbon_product_footprint_inventory_item")
    op.drop_constraint("fk_allocation_operation", "carbon_material_allocation_result", type_="foreignkey")
    op.create_foreign_key(
        "fk_allocation_operation",
        "carbon_material_allocation_result",
        "dataapp_materialhandlingoperation",
        ["operation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("uq_material_allocation_equipment_hour", "carbon_material_allocation_run", type_="unique")
    for col in ("unallocated_energy_kwh", "revision", "input_hash", "factor_id", "equipment_id"):
        op.drop_column("carbon_material_allocation_run", col)
    op.drop_column("dataapp_materialhandlingoperation", "active_intervals")
    op.drop_column("dataapp_materialhandlingoperation", "material_id")
