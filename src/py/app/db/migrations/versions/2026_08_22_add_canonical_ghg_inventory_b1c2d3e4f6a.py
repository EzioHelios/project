"""add canonical organization GHG inventory and migrate legacy activities

Revision ID: b1c2d3e4f6a
Revises: f9e8d7c6b5a4
Create Date: 2026-08-22
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.domain.ghg_inventory import models
from app.domain.ghg_inventory.domain.catalog import CATEGORIES, METHODS, REPORTING_PROFILES

revision = "b1c2d3e4f6a"
down_revision = "f9e8d7c6b5a4"
branch_labels = None
depends_on = None

TABLES = (
    models.GhgReportingProfile.__table__,
    models.GhgCalculationMethodDefinition.__table__,
    models.GhgMethodParameterDefinition.__table__,
    models.GhgParameterValue.__table__,
    models.GhgActivityRecord.__table__,
    models.GhgEvidenceFile.__table__,
    models.GhgEvidenceLink.__table__,
    models.GhgCalculationRun.__table__,
    models.GhgParameterAssignment.__table__,
    models.GhgCalculationResult.__table__,
    models.GhgImportBatch.__table__,
    models.GhgImportIssue.__table__,
)

TENANT_TABLES = tuple(table.name for table in TABLES if "team_id" in table.c)

PERMISSIONS = (
    ("carbon.inventory.view", "查看温室气体盘查", "查看规范化活动、参数、证据和核算结果"),
    ("carbon.inventory.import", "导入温室气体活动", "下载分类模板、预检并导入盘查数据"),
    ("carbon.inventory.calculate", "执行温室气体核算", "按已发布方法和报告配置生成核算快照"),
    ("carbon.evidence.manage", "管理温室气体证据", "维护盘查证据文件及关联"),
)


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


def _seed_catalog() -> None:
    bind = op.get_bind()
    profile_table = models.GhgReportingProfile.__table__
    method_table = models.GhgCalculationMethodDefinition.__table__
    parameter_table = models.GhgMethodParameterDefinition.__table__
    for profile in REPORTING_PROFILES:
        bind.execute(
            profile_table.insert().values(
                code=profile["code"],
                name=profile["name"],
                version=profile["version"],
                standard_code=profile["standardCode"],
                standard_version=profile["version"],
                effective_from=date(2026, 7, 1),
                boundary_rules={"classification": "ISO_14064_1_SIX_CATEGORIES", "ghgpMapping": True},
                output_mappings=[],
                status="published",
            )
        )
    category_map = {category.code: category for category in CATEGORIES}
    for method in METHODS:
        applicable_categories = [
            category.code for category in category_map.values() if method.code in category.default_methods
        ]
        method_id = bind.execute(
            method_table.insert()
            .values(
                code=method.code,
                version="2026.1",
                name=method.name,
                formula_family=method.family,
                formula_variant="default",
                formula_expression={"kind": "whitelisted", "handler": method.code},
                human_formula=method.formula,
                standard_code="方法配置基于 ISO 14064-1 / GHG Protocol / 适用国内指南",
                applicable_categories=applicable_categories,
                applicable_gases=["CO2", "CH4", "N2O", "HFC", "PFC", "SF6", "NF3", "CO2e"],
                source_priority=[
                    "measured",
                    "supplier",
                    "authority_published",
                    "national_default",
                    "library",
                    "custom_approved",
                ],
                effective_from=date(2026, 7, 1),
                status="published" if method.executable else "defined",
            )
            .returning(method_table.c.id)
        ).scalar_one()
        for sort_order, parameter in enumerate(method.parameters, 1):
            bind.execute(
                parameter_table.insert().values(
                    method_id=method_id,
                    parameter_code=parameter["code"],
                    parameter_name=parameter["name"],
                    parameter_role=parameter["role"],
                    value_type="decimal",
                    unit_dimension=parameter["role"],
                    allowed_units=parameter["units"],
                    allowed_source_modes=parameter["sourceModes"],
                    required=parameter["required"],
                    sort_order=sort_order,
                )
            )


def _insert_permissions() -> None:
    bind = op.get_bind()
    permission = sa.table(
        "permission",
        sa.column("id"),
        sa.column("code"),
        sa.column("name"),
        sa.column("description"),
        sa.column("module"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    role = sa.table("role", sa.column("id"), sa.column("name"))
    role_permission = sa.table(
        "role_permission",
        sa.column("id"),
        sa.column("role_id"),
        sa.column("permission_id"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    for code, name, description in PERMISSIONS:
        permission_id = uuid4()
        bind.execute(
            permission.insert().values(
                id=permission_id,
                code=code,
                name=name,
                description=description,
                module="carbon_inventory",
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
            )
        )
        if code == "carbon.inventory.view":
            role_id = bind.scalar(sa.select(role.c.id).where(role.c.name == "User"))
            if role_id is not None:
                bind.execute(
                    role_permission.insert().values(
                        id=uuid4(),
                        role_id=role_id,
                        permission_id=permission_id,
                        created_at=sa.func.now(),
                        updated_at=sa.func.now(),
                    )
                )


def _migrate_legacy_activities() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    statements = (
        """
        insert into ghg_activity_record (
            id, team_id, record_code, inventory_code, organization_code, facility_code, source_code,
            activity_code, activity_name, period_start, period_end, iso_category_code, ghg_scope,
            source_mechanism, value_chain_position, boundary_status, activity_amount, activity_unit,
            data_source_type, measurement_method, quality_status, source_payload, remarks, status,
            source_system, source_record_type, source_record_id, created_at, updated_at
        )
        select (select coalesce(max(id), 0) from ghg_activity_record) + row_number() over (),
            team_id, coalesce(source_record_no, 'LEGACY-MOBILE-' || id),
            'LEGACY-' || coalesce(data_year, extract(year from record_date)::int),
            'LEGACY-ORG', 'LEGACY-FACILITY', coalesce(asset_id, 'MOBILE-' || id),
            coalesce(asset_id, 'MOBILE-' || id), coalesce(asset_name, '移动燃烧'), record_date, record_date,
            '1.2', 'scope1', 'mobile', 'own', 'included', amount, unit, data_source,
            collection_method, 'warning', jsonb_build_object('fuel_or_material', fuel_type, 'mileage_km', mileage_km, 'work_hours', work_hours),
            remark, case when status = 'approved' then 'approved' else 'draft' end,
            'legacy_migration', 'Scope1MobileCombustion', id, created_at, updated_at
        from dataapp_scope1mobilecombustion
        on conflict (team_id, inventory_code, record_code) do nothing
        """,
        """
        insert into ghg_activity_record (
            id, team_id, record_code, inventory_code, organization_code, facility_code, source_code,
            activity_code, activity_name, period_start, period_end, iso_category_code, ghg_scope,
            source_mechanism, value_chain_position, boundary_status, activity_amount, activity_unit,
            data_source_type, measurement_method, quality_status, source_payload, remarks, status,
            source_system, source_record_type, source_record_id, created_at, updated_at
        )
        select (select coalesce(max(id), 0) from ghg_activity_record) + row_number() over (),
            team_id, coalesce(source_record_no, 'LEGACY-STATIONARY-' || id),
            'LEGACY-' || coalesce(data_year, extract(year from period_start)::int),
            'LEGACY-ORG', 'LEGACY-FACILITY', 'STATIONARY-' || id, 'STATIONARY-' || id,
            facility_name, period_start, period_end, '1.1', 'scope1', 'stationary', 'own', 'included',
            amount, unit, data_source, collection_method, 'warning',
            jsonb_build_object('facility_or_device', facility_name, 'fuel_or_material', fuel_type),
            remark, case when status = 'approved' then 'approved' else 'draft' end,
            'legacy_migration', 'Scope1StationaryCombustion', id, created_at, updated_at
        from dataapp_scope1stationarycombustion
        on conflict (team_id, inventory_code, record_code) do nothing
        """,
        """
        insert into ghg_activity_record (
            id, team_id, record_code, inventory_code, organization_code, facility_code, source_code,
            activity_code, activity_name, period_start, period_end, iso_category_code, ghg_scope,
            source_mechanism, value_chain_position, boundary_status, activity_amount, activity_unit,
            data_source_type, measurement_method, quality_status, source_payload, remarks, status,
            source_system, source_record_type, source_record_id, created_at, updated_at
        )
        select (select coalesce(max(id), 0) from ghg_activity_record) + row_number() over (),
            team_id, coalesce(source_record_no, 'LEGACY-FUGITIVE-' || id),
            'LEGACY-' || coalesce(data_year, extract(year from fill_date)::int),
            'LEGACY-ORG', 'LEGACY-FACILITY', coalesce(device_id, 'FUGITIVE-' || id),
            coalesce(device_id, 'FUGITIVE-' || id), coalesce(device_name, '逸散排放'), fill_date, fill_date,
            '1.4', 'scope1', 'fugitive', 'own', 'included', amount_kg, 'kg', data_source,
            collection_method, 'warning', jsonb_build_object('gas_code', refrigerant_type, 'leak_type', leak_type),
            remark, case when status = 'approved' then 'approved' else 'draft' end,
            'legacy_migration', 'Scope1RefrigerantLeak', id, created_at, updated_at
        from dataapp_scope1refrigerantleak
        on conflict (team_id, inventory_code, record_code) do nothing
        """,
        """
        insert into ghg_activity_record (
            id, team_id, record_code, inventory_code, organization_code, facility_code, source_code,
            activity_code, activity_name, period_start, period_end, iso_category_code, ghg_scope,
            source_mechanism, value_chain_position, boundary_status, activity_amount, activity_unit,
            data_source_type, measurement_method, quality_status, source_payload, remarks, status,
            source_system, source_record_type, source_record_id, created_at, updated_at
        )
        select (select coalesce(max(id), 0) from ghg_activity_record) + row_number() over (),
            team_id, coalesce(source_record_no, 'LEGACY-ELECTRICITY-' || id),
            'LEGACY-' || left(billing_month, 4), 'LEGACY-ORG', 'LEGACY-FACILITY', account_number,
            account_number || '-' || billing_month, '购入电力', to_date(billing_month || '-01', 'YYYY-MM-DD'),
            (to_date(billing_month || '-01', 'YYYY-MM-DD') + interval '1 month - 1 day')::date,
            '2.1', 'scope2', 'energy', 'upstream', 'included', total_kwh, 'kWh', data_source,
            collection_method, case when calc_status = 'ready' then 'warning' else 'failed' end,
            jsonb_build_object('energy_type', 'electricity', 'meter_point', account_number, 'scope2_method', 'location'),
            remark, case when status = 'approved' then 'approved' else 'draft' end,
            'legacy_migration', 'Scope2ElectricityBill', id, created_at, updated_at
        from dataapp_scope2electricitybill
        on conflict (team_id, inventory_code, record_code) do nothing
        """,
        """
        insert into ghg_activity_record (
            id, team_id, record_code, inventory_code, organization_code, facility_code, source_code,
            activity_code, activity_name, period_start, period_end, iso_category_code, ghg_scope,
            source_mechanism, value_chain_position, boundary_status, activity_amount, activity_unit,
            data_source_type, measurement_method, quality_status, source_payload, remarks, status,
            source_system, source_record_type, source_record_id, created_at, updated_at
        )
        select (select coalesce(max(id), 0) from ghg_activity_record) + row_number() over (),
            team_id, coalesce(source_record_no, 'LEGACY-PURCHASED-' || id),
            'LEGACY-' || coalesce(data_year, extract(year from period_start)::int), 'LEGACY-ORG',
            coalesce(area_id, 'LEGACY-FACILITY'), 'PURCHASED-' || id, 'PURCHASED-' || id,
            coalesce(energy_type_name, energy_type_code), period_start, period_end, '2.2', 'scope2',
            'energy', 'upstream', 'included', amount, unit, data_source, collection_method,
            case when calc_status = 'ready' then 'warning' else 'failed' end,
            jsonb_build_object('energy_type', energy_type_code, 'supplier_name', supplier_name, 'scope2_method', 'not_applicable'),
            remark, case when status = 'approved' then 'approved' else 'draft' end,
            'legacy_migration', 'Scope2PurchasedEnergy', id, created_at, updated_at
        from dataapp_scope2purchasedenergy
        on conflict (team_id, inventory_code, record_code) do nothing
        """,
        """
        insert into ghg_activity_record (
            id, team_id, record_code, inventory_code, organization_code, facility_code, source_code,
            activity_code, activity_name, period_start, period_end, iso_category_code, ghg_scope,
            scope3_category, source_mechanism, value_chain_position, boundary_status, activity_amount,
            activity_unit, data_source_type, measurement_method, quality_status, source_payload,
            remarks, status, source_system, source_record_type, source_record_id, created_at, updated_at
        )
        select (select coalesce(max(id), 0) from ghg_activity_record) + row_number() over (),
            team_id, coalesce(source_record_no, 'LEGACY-WASTE-' || id),
            'LEGACY-' || coalesce(data_year, extract(year from date)::int), 'LEGACY-ORG', 'LEGACY-FACILITY',
            'WASTE-' || id, 'WASTE-' || id, category, date, date, '4.4', 'scope3', 5, 'value_chain',
            'upstream', 'included', weight_ton, 't', data_source, collection_method, 'warning',
            jsonb_build_object('waste_type', category, 'treatment_method', treatment_method, 'treatment_vendor', vendor_name),
            remark, case when status = 'approved' then 'approved' else 'draft' end,
            'legacy_migration', 'Scope3WasteDisposal', id, created_at, updated_at
        from dataapp_scope3wastedisposal
        on conflict (team_id, inventory_code, record_code) do nothing
        """,
        """
        insert into ghg_activity_record (
            id, team_id, record_code, inventory_code, organization_code, facility_code, source_code,
            activity_code, activity_name, period_start, period_end, iso_category_code, ghg_scope,
            scope3_category, source_mechanism, value_chain_position, boundary_status, activity_amount,
            activity_unit, data_source_type, measurement_method, quality_status, source_payload,
            remarks, status, source_system, source_record_type, source_record_id, created_at, updated_at
        )
        select (select coalesce(max(id), 0) from ghg_activity_record) + row_number() over (),
            team_id, coalesce(source_record_no, 'LEGACY-TRANSPORT-' || id),
            'LEGACY-' || coalesce(data_year, extract(year from created_at)::int), 'LEGACY-ORG', 'LEGACY-FACILITY',
            waybill_no, waybill_no, '第三方运输 ' || waybill_no, created_at::date, created_at::date,
            '3.1', 'scope3', 4, 'transport', 'upstream', 'included', distance_km * load_ton, 'tkm',
            data_source, collection_method, 'warning', jsonb_build_object('transport_mode', vehicle_type, 'origin', origin, 'destination', destination, 'distance_km', distance_km, 'cargo_ton', load_ton),
            remark, case when status = 'approved' then 'approved' else 'draft' end,
            'legacy_migration', 'Scope3ThirdPartyTransport', id, created_at, updated_at
        from dataapp_scope3thirdpartytransport
        on conflict (team_id, inventory_code, record_code) do nothing
        """,
    )
    for statement in statements:
        op.execute(sa.text(statement))
    op.execute(
        sa.text(
            "select setval('ghg_activity_record_id_seq', "
            "greatest((select coalesce(max(id), 0) from ghg_activity_record) + 1, 1), false)"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=False)
    for table_name in TENANT_TABLES:
        _enable_tenant_rls(table_name)
    _seed_catalog()
    _insert_permissions()
    _migrate_legacy_activities()


def downgrade() -> None:
    bind = op.get_bind()
    permission_codes = [code for code, _, _ in PERMISSIONS]
    permission = sa.table("permission", sa.column("id"), sa.column("code"))
    role_permission = sa.table("role_permission", sa.column("permission_id"))
    permission_ids = sa.select(permission.c.id).where(permission.c.code.in_(permission_codes))
    bind.execute(sa.delete(role_permission).where(role_permission.c.permission_id.in_(permission_ids)))
    bind.execute(sa.delete(permission).where(permission.c.code.in_(permission_codes)))
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
