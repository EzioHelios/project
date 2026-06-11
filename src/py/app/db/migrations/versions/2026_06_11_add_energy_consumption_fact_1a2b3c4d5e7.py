"""add energy consumption fact view

Revision ID: 1a2b3c4d5e7
Revises: 0f1e2d3c4b5a
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "1a2b3c4d5e7"
down_revision = "0f1e2d3c4b5a"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]


ENERGY_TYPES: tuple[dict[str, object], ...] = (
    {
        "code": "diesel",
        "name": "柴油",
        "category": "fuel",
        "default_scope": "scope1",
        "original_unit": "kg",
        "standard_unit": "kgce",
        "standard_factor": 1.4571,
        "standard_code": "GB/T 2589-2020",
        "conversion_factor_source": "GB/T 2589-2020 综合能耗计算通则,折标准煤参考系数.",
    },
    {
        "code": "gasoline",
        "name": "汽油",
        "category": "fuel",
        "default_scope": "scope1",
        "original_unit": "kg",
        "standard_unit": "kgce",
        "standard_factor": 1.4714,
        "standard_code": "GB/T 2589-2020",
        "conversion_factor_source": "GB/T 2589-2020 综合能耗计算通则,折标准煤参考系数.",
    },
    {
        "code": "natural_gas",
        "name": "天然气",
        "category": "fuel",
        "default_scope": "scope1",
        "original_unit": "m3",
        "standard_unit": "kgce",
        "standard_factor": 1.2143,
        "standard_code": "GB/T 2589-2020",
        "conversion_factor_source": "GB/T 2589-2020 综合能耗计算通则,折标准煤参考系数.",
    },
    {
        "code": "coal",
        "name": "原煤",
        "category": "fuel",
        "default_scope": "scope1",
        "original_unit": "t",
        "standard_unit": "kgce",
        "standard_factor": 714.3,
        "standard_code": "GB/T 2589-2020",
        "conversion_factor_source": "GB/T 2589-2020 综合能耗计算通则,折标准煤参考系数.",
    },
    {
        "code": "fuel_oil",
        "name": "燃料油",
        "category": "fuel",
        "default_scope": "scope1",
        "original_unit": "kg",
        "standard_unit": "kgce",
        "standard_factor": 1.4286,
        "standard_code": "GB/T 2589-2020",
        "conversion_factor_source": "GB/T 2589-2020 综合能耗计算通则,折标准煤参考系数.",
    },
    {
        "code": "purchased_electricity",
        "name": "外购电力",
        "category": "purchased_energy",
        "default_scope": "scope2",
        "original_unit": "kWh",
        "standard_unit": "kgce",
        "standard_factor": 0.1229,
        "standard_code": "GB/T 2589-2020",
        "conversion_factor_source": "GB/T 2589-2020 综合能耗计算通则,电力折标准煤参考系数.",
    },
    {
        "code": "purchased_heat",
        "name": "外购热力",
        "category": "purchased_energy",
        "default_scope": "scope2",
        "original_unit": "GJ",
        "standard_unit": "kgce",
        "standard_factor": 34.12,
        "standard_code": "GB/T 2589-2020",
        "conversion_factor_source": "GB/T 2589-2020 综合能耗计算通则,热量折标准煤参考口径.",
    },
    {
        "code": "purchased_steam",
        "name": "外购蒸汽",
        "category": "purchased_energy",
        "default_scope": "scope2",
        "original_unit": "GJ",
        "standard_unit": "kgce",
        "standard_factor": 34.12,
        "standard_code": "GB/T 2589-2020",
        "conversion_factor_source": "GB/T 2589-2020 综合能耗计算通则,蒸汽按热量折标准煤参考口径.",
    },
    {
        "code": "purchased_cooling",
        "name": "外购冷量",
        "category": "purchased_energy",
        "default_scope": "scope2",
        "original_unit": "GJ",
        "standard_unit": "kgce",
        "standard_factor": 34.12,
        "standard_code": "GB/T 2589-2020",
        "conversion_factor_source": "GB/T 2589-2020 综合能耗计算通则,冷量按热量折标准煤参考口径.",
    },
)


def _id_type() -> sa.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


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


def _create_energy_consumption_view() -> None:
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
                    original_unit,
                    standard_unit,
                    standard_factor,
                    standard_code,
                    conversion_factor_source
                from dataapp_energytype
                where is_enabled = true
            )
            select
                mobile.team_id,
                'Scope1MobileCombustion'::text as source_record_type,
                mobile.id as source_record_id,
                'scope1'::text as scope,
                'mobile_combustion'::text as emission_category,
                coalesce(energy.code, mobile.fuel_type)::text as energy_type_code,
                coalesce(energy.name, mobile.fuel_type)::text as energy_type_name,
                mobile.amount::numeric as original_amount,
                mobile.unit::text as original_unit,
                case when energy.standard_factor is null then null else mobile.amount * energy.standard_factor end as standard_amount,
                energy.standard_unit::text as standard_unit,
                case when energy.standard_factor is null then null else (mobile.amount * energy.standard_factor) / 1000 end as tce_amount,
                null::numeric as co2e_amount,
                mobile.record_date as period_start,
                mobile.record_date as period_end,
                null::text as area_id,
                null::text as area_name,
                coalesce(mobile.asset_name, mobile.asset_id, mobile.fuel_type)::text as facility_or_device_name,
                mobile.status::text as status,
                coalesce(energy.standard_code, 'GB/T 2589-2020')::text as standard_code,
                energy.conversion_factor_source::text as conversion_factor_source,
                null::text as emission_factor_source
            from dataapp_scope1mobilecombustion mobile
            left join typed energy on energy.code = mobile.fuel_type and energy.default_scope = 'scope1'
            union all
            select
                stationary.team_id,
                'Scope1StationaryCombustion'::text as source_record_type,
                stationary.id as source_record_id,
                'scope1'::text as scope,
                'stationary_combustion'::text as emission_category,
                coalesce(energy.code, stationary.fuel_type)::text as energy_type_code,
                coalesce(energy.name, stationary.fuel_type)::text as energy_type_name,
                stationary.amount::numeric as original_amount,
                stationary.unit::text as original_unit,
                case when energy.standard_factor is null then null else stationary.amount * energy.standard_factor end as standard_amount,
                energy.standard_unit::text as standard_unit,
                case when energy.standard_factor is null then null else (stationary.amount * energy.standard_factor) / 1000 end as tce_amount,
                null::numeric as co2e_amount,
                stationary.period_start as period_start,
                stationary.period_end as period_end,
                null::text as area_id,
                null::text as area_name,
                coalesce(stationary.facility_name, stationary.fuel_type)::text as facility_or_device_name,
                stationary.status::text as status,
                coalesce(energy.standard_code, 'GB/T 2589-2020')::text as standard_code,
                energy.conversion_factor_source::text as conversion_factor_source,
                null::text as emission_factor_source
            from dataapp_scope1stationarycombustion stationary
            left join typed energy on energy.code = stationary.fuel_type and energy.default_scope = 'scope1'
            union all
            select
                bill.team_id,
                'Scope2ElectricityBill'::text as source_record_type,
                bill.id as source_record_id,
                'scope2'::text as scope,
                'purchased_electricity'::text as emission_category,
                energy.code::text as energy_type_code,
                energy.name::text as energy_type_name,
                bill.total_kwh::numeric as original_amount,
                'kWh'::text as original_unit,
                case when energy.standard_factor is null then null else bill.total_kwh * energy.standard_factor end as standard_amount,
                energy.standard_unit::text as standard_unit,
                case when energy.standard_factor is null then null else (bill.total_kwh * energy.standard_factor) / 1000 end as tce_amount,
                bill.computed_co2e::numeric as co2e_amount,
                to_date(bill.billing_month || '-01', 'YYYY-MM-DD') as period_start,
                (to_date(bill.billing_month || '-01', 'YYYY-MM-DD') + interval '1 month - 1 day')::date as period_end,
                null::text as area_id,
                null::text as area_name,
                bill.account_number::text as facility_or_device_name,
                bill.status::text as status,
                coalesce(energy.standard_code, 'GB/T 2589-2020')::text as standard_code,
                energy.conversion_factor_source::text as conversion_factor_source,
                bill.factor_source::text as emission_factor_source
            from dataapp_scope2electricitybill bill
            left join typed energy on energy.code = 'purchased_electricity'
            union all
            select
                meter.team_id,
                'Scope2MeterAggregate'::text as source_record_type,
                meter.id as source_record_id,
                'scope2'::text as scope,
                'purchased_electricity'::text as emission_category,
                energy.code::text as energy_type_code,
                energy.name::text as energy_type_name,
                meter.total_kwh::numeric as original_amount,
                'kWh'::text as original_unit,
                case when energy.standard_factor is null then null else meter.total_kwh * energy.standard_factor end as standard_amount,
                energy.standard_unit::text as standard_unit,
                case when energy.standard_factor is null then null else (meter.total_kwh * energy.standard_factor) / 1000 end as tce_amount,
                meter.computed_co2e::numeric as co2e_amount,
                to_date(meter.billing_month || '-01', 'YYYY-MM-DD') as period_start,
                (to_date(meter.billing_month || '-01', 'YYYY-MM-DD') + interval '1 month - 1 day')::date as period_end,
                meter.area_id::text as area_id,
                meter.area_name::text as area_name,
                coalesce(meter.ammeter_name, meter.ammeter_id)::text as facility_or_device_name,
                meter.status::text as status,
                coalesce(energy.standard_code, 'GB/T 2589-2020')::text as standard_code,
                energy.conversion_factor_source::text as conversion_factor_source,
                meter.factor_source::text as emission_factor_source
            from dataapp_scope2meteraggregate meter
            left join typed energy on energy.code = 'purchased_electricity'
            union all
            select
                purchased.team_id,
                'Scope2PurchasedEnergy'::text as source_record_type,
                purchased.id as source_record_id,
                'scope2'::text as scope,
                purchased.energy_type_code::text as emission_category,
                coalesce(energy.code, purchased.energy_type_code)::text as energy_type_code,
                coalesce(energy.name, purchased.energy_type_name, purchased.energy_type_code)::text as energy_type_name,
                purchased.amount::numeric as original_amount,
                purchased.unit::text as original_unit,
                coalesce(
                    purchased.standard_amount,
                    case when energy.standard_factor is null then null else purchased.amount * energy.standard_factor end
                ) as standard_amount,
                coalesce(purchased.standard_unit, energy.standard_unit)::text as standard_unit,
                coalesce(
                    purchased.tce_amount,
                    case when energy.standard_factor is null then null else (purchased.amount * energy.standard_factor) / 1000 end
                ) as tce_amount,
                purchased.computed_co2e::numeric as co2e_amount,
                purchased.period_start as period_start,
                purchased.period_end as period_end,
                purchased.area_id::text as area_id,
                purchased.area_name::text as area_name,
                coalesce(purchased.facility_name, purchased.supplier_name, purchased.energy_type_name, purchased.energy_type_code)::text as facility_or_device_name,
                purchased.status::text as status,
                coalesce(purchased.standard_code, energy.standard_code, 'GB/T 2589-2020')::text as standard_code,
                coalesce(purchased.conversion_factor_source, energy.conversion_factor_source)::text as conversion_factor_source,
                purchased.factor_source::text as emission_factor_source
            from dataapp_scope2purchasedenergy purchased
            left join typed energy on energy.code = purchased.energy_type_code and energy.default_scope = 'scope2'
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "dataapp_energytype",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("default_scope", sa.String(length=16), nullable=False),
        sa.Column("original_unit", sa.String(length=16), nullable=True),
        sa.Column("standard_unit", sa.String(length=16), nullable=True, server_default="kgce"),
        sa.Column("standard_factor", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("conversion_factor_source", sa.String(length=255), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_energytype")),
        sa.UniqueConstraint("code", name="uq_dataapp_energytype_code"),
    )
    op.create_index(op.f("ix_dataapp_energytype_code"), "dataapp_energytype", ["code"])
    op.create_index("ix_dataapp_energytype_category_scope", "dataapp_energytype", ["category", "default_scope"])
    op.create_index(op.f("ix_dataapp_energytype_category"), "dataapp_energytype", ["category"])
    op.create_index(op.f("ix_dataapp_energytype_default_scope"), "dataapp_energytype", ["default_scope"])
    op.create_index(op.f("ix_dataapp_energytype_is_enabled"), "dataapp_energytype", ["is_enabled"])

    op.bulk_insert(sa.table("dataapp_energytype", *[sa.column(key) for key in ENERGY_TYPES[0]]), list(ENERGY_TYPES))
    op.alter_column("dataapp_energytype", "standard_unit", server_default=None)
    op.alter_column("dataapp_energytype", "is_enabled", server_default=None)

    op.create_table(
        "dataapp_scope2purchasedenergy",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("energy_type_code", sa.String(length=32), nullable=False),
        sa.Column("energy_type_name", sa.String(length=64), nullable=True),
        sa.Column("supplier_name", sa.String(length=128), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("standard_amount", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("standard_unit", sa.String(length=16), nullable=True),
        sa.Column("tce_amount", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("amount_cny", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("area_id", sa.String(length=20), nullable=True),
        sa.Column("area_name", sa.String(length=50), nullable=True),
        sa.Column("facility_name", sa.String(length=128), nullable=True),
        sa.Column("attachment", sa.String(length=255), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("calc_status", sa.String(length=24), nullable=False, server_default="ready"),
        sa.Column("factor_source", sa.String(length=128), nullable=True),
        sa.Column("factor_year", sa.Integer(), nullable=True),
        sa.Column("factor_unit", sa.String(length=32), nullable=True),
        sa.Column("activity_amount", sa.Numeric(precision=16, scale=4), nullable=True),
        sa.Column("activity_unit", sa.String(length=16), nullable=True),
        sa.Column("computed_co2e", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("computation_note", sa.Text(), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("conversion_factor_source", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("creator_id", sa.GUID(length=16), nullable=True),
        sa.Column("approver_id", sa.GUID(length=16), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("data_source", sa.String(length=20), nullable=False, server_default="metered"),
        sa.Column("collection_method", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("confidence_level", sa.String(length=10), nullable=False, server_default="high"),
        sa.Column("data_year_type", sa.String(length=20), nullable=False, server_default="actual"),
        sa.Column("data_year", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.GUID(length=16), nullable=False),
        sa.Column("created_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approver_id"], ["user_account.id"], name=op.f("fk_dataapp_scope2purchasedenergy_approver_id_user_account"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["creator_id"], ["user_account.id"], name=op.f("fk_dataapp_scope2purchasedenergy_creator_id_user_account"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], name="fk_dataapp_scope2purchasedenergy_team_id_team", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_scope2purchasedenergy")),
    )
    op.create_index(op.f("ix_dataapp_scope2purchasedenergy_energy_type_code"), "dataapp_scope2purchasedenergy", ["energy_type_code"])
    op.create_index(op.f("ix_dataapp_scope2purchasedenergy_area_id"), "dataapp_scope2purchasedenergy", ["area_id"])
    op.create_index(op.f("ix_dataapp_scope2purchasedenergy_calc_status"), "dataapp_scope2purchasedenergy", ["calc_status"])
    op.create_index(op.f("ix_dataapp_scope2purchasedenergy_status"), "dataapp_scope2purchasedenergy", ["status"])
    op.create_index(op.f("ix_dataapp_scope2purchasedenergy_creator_id"), "dataapp_scope2purchasedenergy", ["creator_id"])
    op.create_index(op.f("ix_dataapp_scope2purchasedenergy_approver_id"), "dataapp_scope2purchasedenergy", ["approver_id"])
    op.create_index(op.f("ix_dataapp_scope2purchasedenergy_team_id"), "dataapp_scope2purchasedenergy", ["team_id"])
    op.create_index("ix_scope2_purchased_energy_team_period", "dataapp_scope2purchasedenergy", ["team_id", "period_start", "period_end"])
    op.create_index("ix_scope2_purchased_energy_team_type", "dataapp_scope2purchasedenergy", ["team_id", "energy_type_code"])
    op.alter_column("dataapp_scope2purchasedenergy", "calc_status", server_default=None)
    op.alter_column("dataapp_scope2purchasedenergy", "status", server_default=None)
    op.alter_column("dataapp_scope2purchasedenergy", "data_source", server_default=None)
    op.alter_column("dataapp_scope2purchasedenergy", "collection_method", server_default=None)
    op.alter_column("dataapp_scope2purchasedenergy", "confidence_level", server_default=None)
    op.alter_column("dataapp_scope2purchasedenergy", "data_year_type", server_default=None)

    _enable_tenant_rls("dataapp_scope2purchasedenergy")
    _create_energy_consumption_view()


def downgrade() -> None:
    op.execute(sa.text("drop view if exists energy_consumption_fact_v"))
    _disable_tenant_rls("dataapp_scope2purchasedenergy")
    op.drop_index("ix_scope2_purchased_energy_team_type", table_name="dataapp_scope2purchasedenergy")
    op.drop_index("ix_scope2_purchased_energy_team_period", table_name="dataapp_scope2purchasedenergy")
    op.drop_index(op.f("ix_dataapp_scope2purchasedenergy_team_id"), table_name="dataapp_scope2purchasedenergy")
    op.drop_index(op.f("ix_dataapp_scope2purchasedenergy_approver_id"), table_name="dataapp_scope2purchasedenergy")
    op.drop_index(op.f("ix_dataapp_scope2purchasedenergy_creator_id"), table_name="dataapp_scope2purchasedenergy")
    op.drop_index(op.f("ix_dataapp_scope2purchasedenergy_status"), table_name="dataapp_scope2purchasedenergy")
    op.drop_index(op.f("ix_dataapp_scope2purchasedenergy_calc_status"), table_name="dataapp_scope2purchasedenergy")
    op.drop_index(op.f("ix_dataapp_scope2purchasedenergy_area_id"), table_name="dataapp_scope2purchasedenergy")
    op.drop_index(op.f("ix_dataapp_scope2purchasedenergy_energy_type_code"), table_name="dataapp_scope2purchasedenergy")
    op.drop_table("dataapp_scope2purchasedenergy")
    op.drop_index(op.f("ix_dataapp_energytype_is_enabled"), table_name="dataapp_energytype")
    op.drop_index(op.f("ix_dataapp_energytype_default_scope"), table_name="dataapp_energytype")
    op.drop_index(op.f("ix_dataapp_energytype_category"), table_name="dataapp_energytype")
    op.drop_index("ix_dataapp_energytype_category_scope", table_name="dataapp_energytype")
    op.drop_index(op.f("ix_dataapp_energytype_code"), table_name="dataapp_energytype")
    op.drop_table("dataapp_energytype")
