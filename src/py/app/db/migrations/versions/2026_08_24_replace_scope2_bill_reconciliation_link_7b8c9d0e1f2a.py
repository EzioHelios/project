"""Replace the legacy Scope 2 bill link with the canonical GHG activity link.

Revision ID: 7b8c9d0e1f2a
Revises: 6a7b8c9d0e1f
Create Date: 2026-08-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "7b8c9d0e1f2a"
down_revision = "6a7b8c9d0e1f"
branch_labels = None
depends_on = None


def _replace_energy_consumption_views() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        sa.text(
            """
            create or replace view energy_consumption_fact_all_v with (security_invoker = true) as
            with typed as (
                select code, name, default_scope, original_unit as factor_unit,
                       standard_unit, standard_factor, standard_code,
                       conversion_factor_source as standard_factor_source
                  from dataapp_energytype
                 where is_enabled = true
            ),
            canonical as (
                select activity.team_id,
                       'GhgActivityRecord'::text as source_record_type,
                       activity.id as source_record_id,
                       activity.ghg_scope::text as scope,
                       activity.iso_category_code::text as emission_category,
                       coalesce(
                           activity.source_payload ->> 'energy_type_code',
                           activity.source_payload ->> 'fuel_type',
                           case when activity.ghg_scope = 'scope2' and activity.source_mechanism = 'purchased_energy'
                                then 'purchased_electricity' end,
                           activity.activity_code
                       )::text as raw_energy_type_code,
                       activity.activity_amount::numeric as original_amount,
                       activity.activity_unit::text as original_unit,
                       activity.period_start,
                       activity.period_end,
                       allocation.area_id::text as area_id,
                       allocation.area_name_snapshot::text as area_name,
                       coalesce(allocation.equipment_name_snapshot, activity.activity_name)::text as facility_or_device_name,
                       activity.status::text as status,
                       null::numeric as co2e_amount,
                       (activity.source_payload ->> 'standard_code')::text as record_standard_code,
                       (activity.source_payload ->> 'conversion_factor_source')::text as record_conversion_factor_source,
                       (activity.source_payload ->> 'factor_source')::text as emission_factor_source
                  from ghg_activity_record activity
                  left join lateral (
                      select item.area_id, item.area_name_snapshot, item.equipment_name_snapshot
                        from ghg_activity_allocation item
                       where item.activity_id = activity.id
                         and item.team_id = activity.team_id
                         and item.status = 'active'
                       order by case when item.allocation_role = 'responsibility' then 0 else 1 end,
                                item.allocation_ratio desc,
                                item.id
                       limit 1
                  ) allocation on true
                 where activity.status = 'approved'
                   and activity.boundary_status = 'included'
                   and activity.ghg_scope in ('scope1', 'scope2')
            ),
            normalized as (
                select canonical.*,
                       coalesce(typed.code, canonical.raw_energy_type_code)::text as energy_type_code,
                       coalesce(typed.name, canonical.raw_energy_type_code)::text as energy_type_name,
                       typed.factor_unit::text as factor_unit,
                       typed.standard_unit::text as standard_unit,
                       typed.standard_factor::numeric as standard_factor,
                       coalesce(canonical.record_standard_code, typed.standard_code, 'GB/T 2589-2020')::text as standard_code,
                       typed.standard_factor_source::text as standard_factor_source,
                       conversion.multiply_factor::numeric as dictionary_conversion_factor,
                       conversion.conversion_factor_source::text as dictionary_conversion_source,
                       case
                           when canonical.original_amount is null or typed.factor_unit is null then null
                           when lower(replace(replace(trim(coalesce(canonical.original_unit, '')), '³', '3'), ' ', '')) =
                                lower(replace(replace(trim(coalesce(typed.factor_unit, '')), '³', '3'), ' ', ''))
                               then canonical.original_amount
                           when conversion.multiply_factor is not null
                               then canonical.original_amount * conversion.multiply_factor
                           else null
                       end as factor_amount,
                       case
                           when canonical.original_amount is null or typed.factor_unit is null then null
                           when lower(replace(replace(trim(coalesce(canonical.original_unit, '')), '³', '3'), ' ', '')) =
                                lower(replace(replace(trim(coalesce(typed.factor_unit, '')), '³', '3'), ' ', ''))
                               then 1::numeric
                           else conversion.multiply_factor
                       end as unit_conversion_factor,
                       case
                           when canonical.original_amount is null or typed.factor_unit is null then null
                           when lower(replace(replace(trim(coalesce(canonical.original_unit, '')), '³', '3'), ' ', '')) =
                                lower(replace(replace(trim(coalesce(typed.factor_unit, '')), '³', '3'), ' ', ''))
                               then '原始单位与折标基准单位一致'::text
                           else conversion.conversion_factor_source::text
                       end as unit_conversion_source
                  from canonical
                  left join typed
                    on typed.code = canonical.raw_energy_type_code
                   and typed.default_scope = canonical.scope
                  left join dataapp_energyunitconversion conversion
                    on conversion.energy_type_code = canonical.raw_energy_type_code
                   and conversion.is_enabled = true
                   and lower(replace(replace(trim(coalesce(conversion.from_unit, '')), '³', '3'), ' ', '')) =
                       lower(replace(replace(trim(coalesce(canonical.original_unit, '')), '³', '3'), ' ', ''))
                   and lower(replace(replace(trim(coalesce(conversion.to_unit, '')), '³', '3'), ' ', '')) =
                       lower(replace(replace(trim(coalesce(typed.factor_unit, '')), '³', '3'), ' ', ''))
            )
            select team_id, source_record_type, source_record_id, scope, emission_category,
                   energy_type_code, energy_type_name, original_amount, original_unit,
                   factor_amount, factor_unit, unit_conversion_factor, unit_conversion_source,
                   case when standard_factor is null or factor_amount is null then null
                        else factor_amount * standard_factor end as standard_amount,
                   standard_unit,
                   case when standard_factor is null or factor_amount is null then null
                        else (factor_amount * standard_factor) / 1000 end as tce_amount,
                   co2e_amount, period_start, period_end, area_id, area_name,
                   facility_or_device_name, status, standard_code,
                   concat_ws('; ', unit_conversion_source, record_conversion_factor_source, standard_factor_source)::text
                       as conversion_factor_source,
                   emission_factor_source
              from normalized
            """
        )
    )
    op.execute(
        sa.text(
            """
            create or replace view energy_consumption_fact_v with (security_invoker = true) as
            select *
              from energy_consumption_fact_all_v
             where source_record_type = 'GhgActivityRecord'
            """
        )
    )


def upgrade() -> None:
    op.add_column(
        "metering_scope2_electricity_reconciliation",
        sa.Column("activity_record_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_scope2_reconciliation_activity",
        "metering_scope2_electricity_reconciliation",
        ["activity_record_id"],
    )
    op.create_foreign_key(
        "fk_metering_scope2_reconciliation_activity_record",
        "metering_scope2_electricity_reconciliation",
        "ghg_activity_record",
        ["activity_record_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        sa.text(
            """
            update metering_scope2_electricity_reconciliation r
               set activity_record_id = a.id
              from ghg_activity_record a
             where r.electricity_bill_id is not null
               and a.team_id = r.team_id
               and a.source_record_type = 'Scope2ElectricityBill'
               and a.source_record_id = r.electricity_bill_id
            """
        )
    )
    op.execute(
        sa.text(
            "alter table metering_scope2_electricity_reconciliation "
            "drop constraint if exists fk_metering_scope2_electricity_reconciliation_electrici_978a"
        )
    )
    op.execute(sa.text("drop index if exists ix_metering_scope2_electricity_reconciliation_electrici_9e1f"))
    op.drop_column("metering_scope2_electricity_reconciliation", "electricity_bill_id")
    _replace_energy_consumption_views()
    op.execute(sa.text("alter table carbon_verification_project drop constraint if exists fk_cv_project_batch"))
    op.execute(
        sa.text(
            "alter table carbon_verification_project drop constraint if exists "
            "fk_carbon_verification_project_accounting_batch_id_carbon_accounting_batch"
        )
    )
    op.execute(sa.text("drop index if exists ix_carbon_verification_project_batch"))
    op.execute(sa.text("drop index if exists ix_carbon_verification_project_accounting_batch_id"))
    op.execute(sa.text("alter table carbon_verification_project drop column if exists accounting_batch_id"))
    op.execute(
        sa.text(
            "alter table carbon_compliance_cycle drop constraint if exists "
            "fk_carbon_compliance_cycle_accounting_batch_id_carbon_accounting_batch"
        )
    )
    op.execute(sa.text("drop index if exists ix_carbon_compliance_cycle_accounting_batch_id"))
    op.execute(sa.text("alter table carbon_compliance_cycle drop column if exists accounting_batch_id"))
    for table_name in (
        "carbon_emission_inventory_item",
        "carbon_accounting_batch",
        "dataapp_scope1mobilecombustion",
        "dataapp_scope1stationarycombustion",
        "dataapp_scope1refrigerantleak",
        "dataapp_scope2electricitybill",
        "dataapp_scope2purchasedenergy",
        "dataapp_scope3wastedisposal",
        "dataapp_scope3thirdpartytransport",
    ):
        op.execute(sa.text(f"drop table if exists {table_name}"))


def downgrade() -> None:
    message = "The retired Scope-table and accounting-batch model is intentionally not restorable."
    raise RuntimeError(message)
