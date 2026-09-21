"""Frozen initial material allocation schema."""

import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None

STATEMENTS = [
    "\nCREATE TABLE dataapp_materialhandlingoperation (\n\tid BIGINT NOT NULL, \n\tsource_system VARCHAR(32) NOT NULL, \n\tsource_record_id VARCHAR(128) NOT NULL, \n\toperation_no VARCHAR(64) NOT NULL, \n\toperation_type VARCHAR(32) NOT NULL, \n\toperation_status VARCHAR(16) NOT NULL, \n\tperiod_start TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tperiod_end TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tmaterial_code VARCHAR(64) NOT NULL, \n\tmaterial_name VARCHAR(128), \n\tmaterial_spec VARCHAR(128), \n\tmaterial_category VARCHAR(64), \n\tbatch_no VARCHAR(64), \n\tquantity NUMERIC(18, 6) NOT NULL, \n\tunit VARCHAR(16) NOT NULL, \n\tweight_kg NUMERIC(18, 6), \n\tequipment_id BIGINT, \n\tequipment_code VARCHAR(64), \n\tequipment_name VARCHAR(128), \n\tequipment_type VARCHAR(32) NOT NULL, \n\tarea_id BIGINT, \n\tarea_code VARCHAR(64), \n\tarea_name VARCHAR(128), \n\tduration_minutes NUMERIC(12, 4) NOT NULL, \n\thandling_distance_m NUMERIC(14, 4), \n\tsource_payload JSON, \n\tdata_quality VARCHAR(24) NOT NULL, \n\tremark TEXT, \n\tteam_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_dataapp_materialhandlingoperation PRIMARY KEY (id), \n\tCONSTRAINT fk_dataapp_materialhandlingoperation_equipment_id_dataa_20ab FOREIGN KEY(equipment_id) REFERENCES dataapp_monitorequipment (id) ON DELETE SET NULL, \n\tCONSTRAINT fk_dataapp_materialhandlingoperation_team_id_team FOREIGN KEY(team_id) REFERENCES team (id) ON DELETE CASCADE, \n\tCONSTRAINT uq_material_handling_operation_team_source UNIQUE (team_id, source_system, source_record_id), \n\tCONSTRAINT fk_dataapp_materialhandlingoperation_area_id_dataapp_mo_7dac FOREIGN KEY(area_id) REFERENCES dataapp_monitorsector (id) ON DELETE SET NULL\n)\n\n",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_area_code ON dataapp_materialhandlingoperation (area_code)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_area_id ON dataapp_materialhandlingoperation (area_id)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_batch_no ON dataapp_materialhandlingoperation (batch_no)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_data_quality ON dataapp_materialhandlingoperation (data_quality)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_equipment_code ON dataapp_materialhandlingoperation (equipment_code)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_equipment_id ON dataapp_materialhandlingoperation (equipment_id)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_equipment_type ON dataapp_materialhandlingoperation (equipment_type)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_material_category ON dataapp_materialhandlingoperation (material_category)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_material_code ON dataapp_materialhandlingoperation (material_code)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_operation_no ON dataapp_materialhandlingoperation (operation_no)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_operation_status ON dataapp_materialhandlingoperation (operation_status)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_operation_type ON dataapp_materialhandlingoperation (operation_type)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_period_end ON dataapp_materialhandlingoperation (period_end)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_period_start ON dataapp_materialhandlingoperation (period_start)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_source_system ON dataapp_materialhandlingoperation (source_system)",
    "CREATE INDEX ix_dataapp_materialhandlingoperation_team_id ON dataapp_materialhandlingoperation (team_id)",
    "CREATE INDEX ix_material_handling_operation_equipment ON dataapp_materialhandlingoperation (team_id, equipment_id, operation_type)",
    "CREATE INDEX ix_material_handling_operation_material ON dataapp_materialhandlingoperation (team_id, material_code, batch_no)",
    "CREATE INDEX ix_material_handling_operation_period ON dataapp_materialhandlingoperation (team_id, period_start, period_end)",
    "\nCREATE TABLE carbon_material_allocation_run (\n\tid BIGINT NOT NULL, \n\trun_code VARCHAR(96) NOT NULL, \n\tperiod_start TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tperiod_end TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tallocation_method VARCHAR(32) NOT NULL, \n\tenergy_granularity VARCHAR(16) NOT NULL, \n\temission_factor NUMERIC(18, 8) NOT NULL, \n\temission_factor_unit VARCHAR(64) NOT NULL, \n\tstatus VARCHAR(24) NOT NULL, \n\tinput_snapshot JSON, \n\tsummary_snapshot JSON, \n\ttotal_energy_kwh NUMERIC(18, 6), \n\ttotal_co2e_kg NUMERIC(18, 6), \n\tstarted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tcompleted_at TIMESTAMP WITHOUT TIME ZONE, \n\tremark TEXT, \n\tteam_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_carbon_material_allocation_run PRIMARY KEY (id), \n\tCONSTRAINT uq_material_allocation_run_team_code UNIQUE (team_id, run_code), \n\tCONSTRAINT fk_carbon_material_allocation_run_team_id_team FOREIGN KEY(team_id) REFERENCES team (id) ON DELETE CASCADE\n)\n\n",
    "CREATE INDEX ix_carbon_material_allocation_run_allocation_method ON carbon_material_allocation_run (allocation_method)",
    "CREATE INDEX ix_carbon_material_allocation_run_period_end ON carbon_material_allocation_run (period_end)",
    "CREATE INDEX ix_carbon_material_allocation_run_period_start ON carbon_material_allocation_run (period_start)",
    "CREATE INDEX ix_carbon_material_allocation_run_run_code ON carbon_material_allocation_run (run_code)",
    "CREATE INDEX ix_carbon_material_allocation_run_status ON carbon_material_allocation_run (status)",
    "CREATE INDEX ix_carbon_material_allocation_run_team_id ON carbon_material_allocation_run (team_id)",
    "CREATE INDEX ix_material_allocation_run_period ON carbon_material_allocation_run (team_id, period_start, period_end, status)",
    "\nCREATE TABLE carbon_material_allocation_result (\n\tid BIGINT NOT NULL, \n\trun_id BIGINT NOT NULL, \n\toperation_id BIGINT NOT NULL, \n\toperation_no VARCHAR(64) NOT NULL, \n\toperation_type VARCHAR(32) NOT NULL, \n\tequipment_id BIGINT, \n\tequipment_code VARCHAR(64), \n\tequipment_name VARCHAR(128), \n\tequipment_type VARCHAR(32) NOT NULL, \n\tarea_id BIGINT, \n\tarea_code VARCHAR(64), \n\tarea_name VARCHAR(128), \n\tmaterial_code VARCHAR(64) NOT NULL, \n\tmaterial_name VARCHAR(128), \n\tmaterial_spec VARCHAR(128), \n\tmaterial_category VARCHAR(64), \n\tbatch_no VARCHAR(64), \n\tsource_energy_kwh NUMERIC(18, 6), \n\tdriver_amount NUMERIC(18, 6), \n\ttotal_driver_amount NUMERIC(18, 6), \n\tallocation_ratio NUMERIC(12, 8), \n\tallocated_energy_kwh NUMERIC(18, 6), \n\temission_factor NUMERIC(18, 8), \n\tallocated_co2e_kg NUMERIC(18, 6), \n\tallocation_method VARCHAR(32) NOT NULL, \n\tenergy_source_snapshot JSON, \n\tproduct_footprint_item_id BIGINT, \n\tdata_status VARCHAR(24) NOT NULL, \n\tremark TEXT, \n\tteam_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_carbon_material_allocation_result PRIMARY KEY (id), \n\tCONSTRAINT fk_carbon_material_allocation_result_product_footprint__d8a0 FOREIGN KEY(product_footprint_item_id) REFERENCES carbon_product_footprint_inventory_item (id) ON DELETE SET NULL, \n\tCONSTRAINT fk_carbon_material_allocation_result_equipment_id_dataa_36ff FOREIGN KEY(equipment_id) REFERENCES dataapp_monitorequipment (id) ON DELETE SET NULL, \n\tCONSTRAINT fk_carbon_material_allocation_result_operation_id_dataa_a8ea FOREIGN KEY(operation_id) REFERENCES dataapp_materialhandlingoperation (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_carbon_material_allocation_result_run_id_carbon_mate_7172 FOREIGN KEY(run_id) REFERENCES carbon_material_allocation_run (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_carbon_material_allocation_result_team_id_team FOREIGN KEY(team_id) REFERENCES team (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_carbon_material_allocation_result_area_id_dataapp_mo_81c9 FOREIGN KEY(area_id) REFERENCES dataapp_monitorsector (id) ON DELETE SET NULL, \n\tCONSTRAINT uq_material_allocation_result_operation UNIQUE (team_id, run_id, operation_id)\n)\n\n",
    "CREATE INDEX ix_carbon_material_allocation_result_allocation_method ON carbon_material_allocation_result (allocation_method)",
    "CREATE INDEX ix_carbon_material_allocation_result_area_code ON carbon_material_allocation_result (area_code)",
    "CREATE INDEX ix_carbon_material_allocation_result_area_id ON carbon_material_allocation_result (area_id)",
    "CREATE INDEX ix_carbon_material_allocation_result_batch_no ON carbon_material_allocation_result (batch_no)",
    "CREATE INDEX ix_carbon_material_allocation_result_data_status ON carbon_material_allocation_result (data_status)",
    "CREATE INDEX ix_carbon_material_allocation_result_equipment_code ON carbon_material_allocation_result (equipment_code)",
    "CREATE INDEX ix_carbon_material_allocation_result_equipment_id ON carbon_material_allocation_result (equipment_id)",
    "CREATE INDEX ix_carbon_material_allocation_result_equipment_type ON carbon_material_allocation_result (equipment_type)",
    "CREATE INDEX ix_carbon_material_allocation_result_material_category ON carbon_material_allocation_result (material_category)",
    "CREATE INDEX ix_carbon_material_allocation_result_material_code ON carbon_material_allocation_result (material_code)",
    "CREATE INDEX ix_carbon_material_allocation_result_operation_id ON carbon_material_allocation_result (operation_id)",
    "CREATE INDEX ix_carbon_material_allocation_result_operation_no ON carbon_material_allocation_result (operation_no)",
    "CREATE INDEX ix_carbon_material_allocation_result_operation_type ON carbon_material_allocation_result (operation_type)",
    "CREATE INDEX ix_carbon_material_allocation_result_product_footprint_item_id ON carbon_material_allocation_result (product_footprint_item_id)",
    "CREATE INDEX ix_carbon_material_allocation_result_run_id ON carbon_material_allocation_result (run_id)",
    "CREATE INDEX ix_carbon_material_allocation_result_team_id ON carbon_material_allocation_result (team_id)",
    "CREATE INDEX ix_material_allocation_result_equipment ON carbon_material_allocation_result (team_id, equipment_id, data_status)",
    "CREATE INDEX ix_material_allocation_result_material ON carbon_material_allocation_result (team_id, material_code, batch_no)",
]
TABLES = ("dataapp_materialhandlingoperation", "carbon_material_allocation_run", "carbon_material_allocation_result")


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(sa.text(statement))
    for table in TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        rule = "current_setting('app.tenant_bypass', true) = 'true' OR team_id::text = nullif(current_setting('app.tenant_id', true), '')"
        op.execute(sa.text(f"CREATE POLICY rls_{table}_tenant_scope ON {table} USING ({rule}) WITH CHECK ({rule})"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
