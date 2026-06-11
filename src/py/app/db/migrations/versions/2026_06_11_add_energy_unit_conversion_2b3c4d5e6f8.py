"""add energy unit conversion dictionary

Revision ID: 2b3c4d5e6f8
Revises: 1a2b3c4d5e7
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2b3c4d5e6f8"
down_revision = "1a2b3c4d5e7"
branch_labels = None
depends_on = None


ENERGY_UNIT_CONVERSIONS: tuple[dict[str, object], ...] = (
    {
        "energy_type_code": "diesel",
        "from_unit": "L",
        "to_unit": "kg",
        "multiply_factor": 0.84,
        "standard_code": "enterprise_default",
        "conversion_factor_source": "默认柴油密度参数,用于 L 到 kg 换算; 企业应优先维护实测密度或供应商密度. GB/T 2589-2020 折标系数适用单位为 kg.",
        "is_default": True,
        "remark": "体积到质量换算不是 GB/T 2589 折标系数,后续可按批次密度覆盖.",
    },
    {
        "energy_type_code": "diesel",
        "from_unit": "t",
        "to_unit": "kg",
        "multiply_factor": 1000,
        "standard_code": "SI",
        "conversion_factor_source": "公制质量单位换算.",
        "is_default": True,
        "remark": None,
    },
    {
        "energy_type_code": "gasoline",
        "from_unit": "L",
        "to_unit": "kg",
        "multiply_factor": 0.74,
        "standard_code": "enterprise_default",
        "conversion_factor_source": "默认汽油密度参数,用于 L 到 kg 换算; 企业应优先维护实测密度或供应商密度. GB/T 2589-2020 折标系数适用单位为 kg.",
        "is_default": True,
        "remark": "体积到质量换算不是 GB/T 2589 折标系数,后续可按批次密度覆盖.",
    },
    {
        "energy_type_code": "gasoline",
        "from_unit": "t",
        "to_unit": "kg",
        "multiply_factor": 1000,
        "standard_code": "SI",
        "conversion_factor_source": "公制质量单位换算.",
        "is_default": True,
        "remark": None,
    },
    {
        "energy_type_code": "fuel_oil",
        "from_unit": "t",
        "to_unit": "kg",
        "multiply_factor": 1000,
        "standard_code": "SI",
        "conversion_factor_source": "公制质量单位换算.",
        "is_default": True,
        "remark": None,
    },
    {
        "energy_type_code": "coal",
        "from_unit": "kg",
        "to_unit": "t",
        "multiply_factor": 0.001,
        "standard_code": "SI",
        "conversion_factor_source": "公制质量单位换算.",
        "is_default": True,
        "remark": None,
    },
    {
        "energy_type_code": "purchased_electricity",
        "from_unit": "MWh",
        "to_unit": "kWh",
        "multiply_factor": 1000,
        "standard_code": "SI",
        "conversion_factor_source": "电量单位换算,1 MWh = 1000 kWh.",
        "is_default": True,
        "remark": None,
    },
    {
        "energy_type_code": "purchased_heat",
        "from_unit": "MWh",
        "to_unit": "GJ",
        "multiply_factor": 3.6,
        "standard_code": "SI",
        "conversion_factor_source": "热量单位换算,1 MWh = 3.6 GJ.",
        "is_default": True,
        "remark": None,
    },
    {
        "energy_type_code": "purchased_heat",
        "from_unit": "Gcal",
        "to_unit": "GJ",
        "multiply_factor": 4.1868,
        "standard_code": "SI",
        "conversion_factor_source": "热量单位换算,1 Gcal = 4.1868 GJ.",
        "is_default": True,
        "remark": None,
    },
    {
        "energy_type_code": "purchased_steam",
        "from_unit": "MWh",
        "to_unit": "GJ",
        "multiply_factor": 3.6,
        "standard_code": "SI",
        "conversion_factor_source": "热量单位换算,1 MWh = 3.6 GJ.",
        "is_default": True,
        "remark": "蒸汽按热量计费时可用; 按吨计费时应按焓值另行维护 t 到 GJ 换算.",
    },
    {
        "energy_type_code": "purchased_steam",
        "from_unit": "Gcal",
        "to_unit": "GJ",
        "multiply_factor": 4.1868,
        "standard_code": "SI",
        "conversion_factor_source": "热量单位换算,1 Gcal = 4.1868 GJ.",
        "is_default": True,
        "remark": "蒸汽按热量计费时可用; 按吨计费时应按焓值另行维护 t 到 GJ 换算.",
    },
    {
        "energy_type_code": "purchased_cooling",
        "from_unit": "MWh",
        "to_unit": "GJ",
        "multiply_factor": 3.6,
        "standard_code": "SI",
        "conversion_factor_source": "冷量单位换算,1 MWh = 3.6 GJ.",
        "is_default": True,
        "remark": None,
    },
    {
        "energy_type_code": "purchased_cooling",
        "from_unit": "Gcal",
        "to_unit": "GJ",
        "multiply_factor": 4.1868,
        "standard_code": "SI",
        "conversion_factor_source": "冷量单位换算,1 Gcal = 4.1868 GJ.",
        "is_default": True,
        "remark": None,
    },
)


def _id_type() -> sa.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _create_energy_consumption_view() -> None:
    op.execute(sa.text("drop view if exists energy_consumption_fact_v"))
    op.execute(
        sa.text(
            """
            create or replace view energy_consumption_fact_v as
            with typed as (
                select
                    code,
                    name,
                    category,
                    default_scope,
                    original_unit as factor_unit,
                    standard_unit,
                    standard_factor,
                    standard_code,
                    conversion_factor_source as standard_factor_source
                from dataapp_energytype
                where is_enabled = true
            ),
            raw_facts as (
                select
                    mobile.team_id,
                    'Scope1MobileCombustion'::text as source_record_type,
                    mobile.id as source_record_id,
                    'scope1'::text as scope,
                    'mobile_combustion'::text as emission_category,
                    mobile.fuel_type::text as raw_energy_type_code,
                    mobile.amount::numeric as original_amount,
                    mobile.unit::text as original_unit,
                    mobile.record_date as period_start,
                    mobile.record_date as period_end,
                    null::text as area_id,
                    null::text as area_name,
                    coalesce(mobile.asset_name, mobile.asset_id, mobile.fuel_type)::text as facility_or_device_name,
                    mobile.status::text as status,
                    null::numeric as co2e_amount,
                    null::text as record_standard_code,
                    null::text as record_conversion_factor_source,
                    null::text as emission_factor_source
                from dataapp_scope1mobilecombustion mobile
                union all
                select
                    stationary.team_id,
                    'Scope1StationaryCombustion'::text as source_record_type,
                    stationary.id as source_record_id,
                    'scope1'::text as scope,
                    'stationary_combustion'::text as emission_category,
                    stationary.fuel_type::text as raw_energy_type_code,
                    stationary.amount::numeric as original_amount,
                    stationary.unit::text as original_unit,
                    stationary.period_start as period_start,
                    stationary.period_end as period_end,
                    null::text as area_id,
                    null::text as area_name,
                    coalesce(stationary.facility_name, stationary.fuel_type)::text as facility_or_device_name,
                    stationary.status::text as status,
                    null::numeric as co2e_amount,
                    null::text as record_standard_code,
                    null::text as record_conversion_factor_source,
                    null::text as emission_factor_source
                from dataapp_scope1stationarycombustion stationary
                union all
                select
                    bill.team_id,
                    'Scope2ElectricityBill'::text as source_record_type,
                    bill.id as source_record_id,
                    'scope2'::text as scope,
                    'purchased_electricity'::text as emission_category,
                    'purchased_electricity'::text as raw_energy_type_code,
                    bill.total_kwh::numeric as original_amount,
                    'kWh'::text as original_unit,
                    to_date(bill.billing_month || '-01', 'YYYY-MM-DD') as period_start,
                    (to_date(bill.billing_month || '-01', 'YYYY-MM-DD') + interval '1 month - 1 day')::date as period_end,
                    null::text as area_id,
                    null::text as area_name,
                    bill.account_number::text as facility_or_device_name,
                    bill.status::text as status,
                    bill.computed_co2e::numeric as co2e_amount,
                    null::text as record_standard_code,
                    null::text as record_conversion_factor_source,
                    bill.factor_source::text as emission_factor_source
                from dataapp_scope2electricitybill bill
                union all
                select
                    meter.team_id,
                    'Scope2MeterAggregate'::text as source_record_type,
                    meter.id as source_record_id,
                    'scope2'::text as scope,
                    'purchased_electricity'::text as emission_category,
                    'purchased_electricity'::text as raw_energy_type_code,
                    meter.total_kwh::numeric as original_amount,
                    'kWh'::text as original_unit,
                    to_date(meter.billing_month || '-01', 'YYYY-MM-DD') as period_start,
                    (to_date(meter.billing_month || '-01', 'YYYY-MM-DD') + interval '1 month - 1 day')::date as period_end,
                    meter.area_id::text as area_id,
                    meter.area_name::text as area_name,
                    coalesce(meter.ammeter_name, meter.ammeter_id)::text as facility_or_device_name,
                    meter.status::text as status,
                    meter.computed_co2e::numeric as co2e_amount,
                    null::text as record_standard_code,
                    null::text as record_conversion_factor_source,
                    meter.factor_source::text as emission_factor_source
                from dataapp_scope2meteraggregate meter
                union all
                select
                    purchased.team_id,
                    'Scope2PurchasedEnergy'::text as source_record_type,
                    purchased.id as source_record_id,
                    'scope2'::text as scope,
                    purchased.energy_type_code::text as emission_category,
                    purchased.energy_type_code::text as raw_energy_type_code,
                    purchased.amount::numeric as original_amount,
                    purchased.unit::text as original_unit,
                    purchased.period_start as period_start,
                    purchased.period_end as period_end,
                    purchased.area_id::text as area_id,
                    purchased.area_name::text as area_name,
                    coalesce(purchased.facility_name, purchased.supplier_name, purchased.energy_type_name, purchased.energy_type_code)::text as facility_or_device_name,
                    purchased.status::text as status,
                    purchased.computed_co2e::numeric as co2e_amount,
                    purchased.standard_code::text as record_standard_code,
                    purchased.conversion_factor_source::text as record_conversion_factor_source,
                    purchased.factor_source::text as emission_factor_source
                from dataapp_scope2purchasedenergy purchased
            ),
            normalized as (
                select
                    raw_facts.*,
                    coalesce(typed.code, raw_facts.raw_energy_type_code)::text as energy_type_code,
                    coalesce(typed.name, raw_facts.raw_energy_type_code)::text as energy_type_name,
                    typed.factor_unit::text as factor_unit,
                    typed.standard_unit::text as standard_unit,
                    typed.standard_factor::numeric as standard_factor,
                    coalesce(raw_facts.record_standard_code, typed.standard_code, 'GB/T 2589-2020')::text as standard_code,
                    typed.standard_factor_source::text as standard_factor_source,
                    conversion.multiply_factor::numeric as dictionary_conversion_factor,
                    conversion.conversion_factor_source::text as dictionary_conversion_source,
                    case
                        when raw_facts.original_amount is null or typed.factor_unit is null then null
                        when lower(replace(replace(trim(coalesce(raw_facts.original_unit, '')), '³', '3'), ' ', '')) =
                             lower(replace(replace(trim(coalesce(typed.factor_unit, '')), '³', '3'), ' ', ''))
                            then raw_facts.original_amount
                        when conversion.multiply_factor is not null
                            then raw_facts.original_amount * conversion.multiply_factor
                        else null
                    end as factor_amount,
                    case
                        when raw_facts.original_amount is null or typed.factor_unit is null then null
                        when lower(replace(replace(trim(coalesce(raw_facts.original_unit, '')), '³', '3'), ' ', '')) =
                             lower(replace(replace(trim(coalesce(typed.factor_unit, '')), '³', '3'), ' ', ''))
                            then 1::numeric
                        else conversion.multiply_factor
                    end as unit_conversion_factor,
                    case
                        when raw_facts.original_amount is null or typed.factor_unit is null then null
                        when lower(replace(replace(trim(coalesce(raw_facts.original_unit, '')), '³', '3'), ' ', '')) =
                             lower(replace(replace(trim(coalesce(typed.factor_unit, '')), '³', '3'), ' ', ''))
                            then '原始单位与折标基准单位一致'::text
                        else conversion.conversion_factor_source::text
                    end as unit_conversion_source
                from raw_facts
                left join typed on typed.code = raw_facts.raw_energy_type_code and typed.default_scope = raw_facts.scope
                left join dataapp_energyunitconversion conversion on
                    conversion.energy_type_code = raw_facts.raw_energy_type_code
                    and conversion.is_enabled = true
                    and lower(replace(replace(trim(coalesce(conversion.from_unit, '')), '³', '3'), ' ', '')) =
                        lower(replace(replace(trim(coalesce(raw_facts.original_unit, '')), '³', '3'), ' ', ''))
                    and lower(replace(replace(trim(coalesce(conversion.to_unit, '')), '³', '3'), ' ', '')) =
                        lower(replace(replace(trim(coalesce(typed.factor_unit, '')), '³', '3'), ' ', ''))
            )
            select
                team_id,
                source_record_type,
                source_record_id,
                scope,
                emission_category,
                energy_type_code,
                energy_type_name,
                original_amount,
                original_unit,
                factor_amount,
                factor_unit,
                unit_conversion_factor,
                unit_conversion_source,
                case when standard_factor is null or factor_amount is null then null else factor_amount * standard_factor end as standard_amount,
                standard_unit,
                case when standard_factor is null or factor_amount is null then null else (factor_amount * standard_factor) / 1000 end as tce_amount,
                co2e_amount,
                period_start,
                period_end,
                area_id,
                area_name,
                facility_or_device_name,
                status,
                standard_code,
                concat_ws('; ', unit_conversion_source, record_conversion_factor_source, standard_factor_source)::text as conversion_factor_source,
                emission_factor_source
            from normalized
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "dataapp_energyunitconversion",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("energy_type_code", sa.String(length=32), nullable=False),
        sa.Column("from_unit", sa.String(length=16), nullable=False),
        sa.Column("to_unit", sa.String(length=16), nullable=False),
        sa.Column("multiply_factor", sa.Numeric(precision=18, scale=10), nullable=False),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("conversion_factor_source", sa.String(length=255), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_energyunitconversion")),
        sa.UniqueConstraint("energy_type_code", "from_unit", "to_unit", name="uq_energy_unit_conversion_type_units"),
    )
    op.create_index(op.f("ix_dataapp_energyunitconversion_energy_type_code"), "dataapp_energyunitconversion", ["energy_type_code"])
    op.create_index(op.f("ix_dataapp_energyunitconversion_is_default"), "dataapp_energyunitconversion", ["is_default"])
    op.create_index(op.f("ix_dataapp_energyunitconversion_is_enabled"), "dataapp_energyunitconversion", ["is_enabled"])
    op.create_index("ix_energy_unit_conversion_type_enabled", "dataapp_energyunitconversion", ["energy_type_code", "is_enabled"])
    op.bulk_insert(
        sa.table("dataapp_energyunitconversion", *[sa.column(key) for key in ENERGY_UNIT_CONVERSIONS[0]]),
        list(ENERGY_UNIT_CONVERSIONS),
    )
    op.alter_column("dataapp_energyunitconversion", "is_default", server_default=None)
    op.alter_column("dataapp_energyunitconversion", "is_enabled", server_default=None)
    _create_energy_consumption_view()


def downgrade() -> None:
    op.execute(sa.text("drop view if exists energy_consumption_fact_v"))
    op.drop_index("ix_energy_unit_conversion_type_enabled", table_name="dataapp_energyunitconversion")
    op.drop_index(op.f("ix_dataapp_energyunitconversion_is_enabled"), table_name="dataapp_energyunitconversion")
    op.drop_index(op.f("ix_dataapp_energyunitconversion_is_default"), table_name="dataapp_energyunitconversion")
    op.drop_index(op.f("ix_dataapp_energyunitconversion_energy_type_code"), table_name="dataapp_energyunitconversion")
    op.drop_table("dataapp_energyunitconversion")
