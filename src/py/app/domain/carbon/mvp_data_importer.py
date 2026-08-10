from __future__ import annotations

# ruff: noqa: RUF001, S608
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.domain.carbon_accounting.usecases.inventory import CarbonAccountingInventoryUseCase
from app.lib.tenancy import DEFAULT_TENANT_ID, TENANT_BYPASS_SESSION_KEY

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import models as m

SEED_SOURCE = "carbon_mvp_seed"
SEED_MARKER = "[carbon_mvp_seed]"
REPORT_YEAR = 2026
DECEMBER = 12
GRID_FACTOR_KG_PER_KWH = Decimal("0.5827")
STEAM_FACTOR_KG_PER_TON = Decimal("120.0000")


@dataclass(slots=True)
class CarbonMvpSeedResult:
    """Result summary for carbon-management MVP sample data."""

    scope_records: int = 0
    organizations: int = 0
    boundaries: int = 0
    accounting_batches: int = 0
    inventory_items: int = 0
    verification_projects: int = 0
    pcf_studies: int = 0
    suppliers: int = 0
    asset_periods: int = 0
    budget_plans: int = 0


async def seed_carbon_mvp_data(session: AsyncSession) -> CarbonMvpSeedResult:
    """Seed a coherent MVP data set for the carbon-management pages."""

    session.info[TENANT_BYPASS_SESSION_KEY] = True
    await session.execute(text("select set_config('app.tenant_bypass', 'true', true)"))
    await _delete_existing_seed_data(session)
    await _seed_scope_records(session)
    org_id, period_id, boundary_id = await _seed_reporting_boundary(session)
    batch = await _seed_accounting_batch(session, boundary_id)
    template_id, project_id = await _seed_verification(session, org_id, period_id, boundary_id, batch.id)
    product_id, study_id = await _seed_product_footprint(session)
    supplier_task_id = await _seed_supply_chain(session, product_id)
    period_asset_id, account_id, allowance_id, credit_id = await _seed_assets(
        session, boundary_id, batch.id, batch.total_co2e
    )
    plan_id = await _seed_budget(session)
    await session.commit()
    return await _collect_result(
        session,
        batch_id=batch.id,
        project_id=project_id,
        template_id=template_id,
        study_id=study_id,
        supplier_task_id=supplier_task_id,
        asset_period_id=period_asset_id,
        account_id=account_id,
        allowance_id=allowance_id,
        credit_id=credit_id,
        plan_id=plan_id,
    )


async def _delete_existing_seed_data(session: AsyncSession) -> None:
    deletes = [
        "delete from carbon_verification_export_file where team_id = :team_id and job_id in "
        "(select id from carbon_verification_export_job where team_id = :team_id and job_no like 'MVP-%')",
        "delete from carbon_verification_export_job where team_id = :team_id and job_no like 'MVP-%'",
        "delete from carbon_verification_finding where team_id = :team_id and source_name = :source",
        "delete from carbon_verification_attachment where team_id = :team_id and source_name = :source",
        "delete from carbon_verification_project where team_id = :team_id and source_name = :source",
        "delete from carbon_verification_template_version where team_id = :team_id and source_name = :source",
        "delete from carbon_asset_forecast_scenario where team_id = :team_id and source_name = :source",
        "delete from carbon_surrender_record where team_id = :team_id and source_name = :source",
        "delete from carbon_asset_transaction where team_id = :team_id and source_name = :source",
        "delete from carbon_credit_holding where team_id = :team_id and source_name = :source",
        "delete from carbon_quota_allocation where team_id = :team_id and source_name = :source",
        "delete from carbon_asset_account where team_id = :team_id and source_name = :source",
        "delete from carbon_compliance_period where team_id = :team_id and source_name = :source",
        "delete from carbon_supplier_disclosure_release where team_id = :team_id and release_no like 'MVP-%'",
        "delete from carbon_supplier_review_decision where team_id = :team_id and reason like :marker_like",
        "delete from carbon_supplier_evidence where team_id = :team_id and remark like :marker_like",
        "delete from carbon_supplier_carbon_data where team_id = :team_id and remark like :marker_like",
        "delete from carbon_supplier_disclosure_task where team_id = :team_id and source_name = :source",
        "delete from carbon_supplier_site where team_id = :team_id and remark like :marker_like",
        "delete from carbon_supply_chain_supplier where team_id = :team_id and source_name = :source",
        "delete from carbon_product_footprint_result where team_id = :team_id and remark like :marker_like",
        "delete from carbon_product_footprint_allocation_rule where team_id = :team_id and source_name = :source",
        "delete from carbon_product_footprint_inventory_item where team_id = :team_id and remark like :marker_like",
        "delete from carbon_product_lifecycle_stage where team_id = :team_id and study_id in "
        "(select id from carbon_product_footprint_study where team_id = :team_id and source_name = :source)",
        "delete from carbon_product_system_boundary where team_id = :team_id and source_name = :source",
        "delete from carbon_product_footprint_study where team_id = :team_id and source_name = :source",
        "delete from carbon_emission_inventory_item where team_id = :team_id and batch_id in "
        "(select id from carbon_accounting_batch where team_id = :team_id and source_name = :source)",
        "delete from carbon_accounting_batch where team_id = :team_id and source_name = :source",
        "delete from carbon_boundary_facility where team_id = :team_id and source_name = :source",
        "delete from carbon_organization_boundary where team_id = :team_id and source_name = :source",
        "delete from carbon_reporting_period where team_id = :team_id and source_name = :source",
        "delete from carbon_reporting_organization where team_id = :team_id and source_name = :source",
        "delete from dataapp_energycarbonbudgetadjustment where team_id = :team_id and source_name = :source",
        "delete from dataapp_energycarbonbudgetallocation where team_id = :team_id and source_name = :source",
        "delete from dataapp_energycarbonbudgetplan where team_id = :team_id and source_name = :source",
        "delete from dataapp_scope2purchasedenergy where team_id = :team_id and remark like :marker_like",
        "delete from dataapp_scope2electricitybill where team_id = :team_id and remark like :marker_like",
        "delete from dataapp_scope3thirdpartytransport where team_id = :team_id and remark like :marker_like",
        "delete from dataapp_scope3wastedisposal where team_id = :team_id and remark like :marker_like",
        "delete from dataapp_scope1refrigerantleak where team_id = :team_id and remark like :marker_like",
        "delete from dataapp_scope1stationarycombustion where team_id = :team_id and remark like :marker_like",
        "delete from dataapp_scope1mobilecombustion where team_id = :team_id and remark like :marker_like",
        "delete from dataapp_productionproduct where team_id = :team_id and code = 'MVP-PROD-001'",
    ]
    params = {
        "team_id": str(DEFAULT_TENANT_ID),
        "source": SEED_SOURCE,
        "marker_like": f"%{SEED_MARKER}%",
    }
    for statement in deletes:
        await session.execute(text(statement), params)


async def _seed_scope_records(session: AsyncSession) -> None:
    months = _months(REPORT_YEAR, 6)
    common = {
        "team_id": str(DEFAULT_TENANT_ID),
        "status": "approved",
        "data_source": "manual",
        "collection_method": "monthly_statement",
        "confidence_level": "medium",
        "data_year_type": "calendar_year",
        "data_year": REPORT_YEAR,
        "approved_at": dt.datetime(REPORT_YEAR, 7, 5, 10, 0, 0, tzinfo=dt.UTC),
        "remark": f"{SEED_MARKER} 当前企业MVP补录数据。",
    }
    for index, month_start in enumerate(months, start=1):
        month_end = _month_end(month_start)
        await session.execute(
            text(
                """
                insert into dataapp_scope1mobilecombustion (
                    team_id, status, data_source, collection_method, confidence_level, data_year_type, data_year,
                    approved_at, record_date, asset_id, asset_name, fuel_type, amount, unit, mileage_km,
                    work_hours, attachment, remark, created_at, updated_at
                )
                values (
                    :team_id, :status, :data_source, :collection_method, :confidence_level, :data_year_type,
                    :data_year, :approved_at, :record_date, :asset_id, :asset_name, 'diesel', :amount,
                    'L', :mileage_km, :work_hours, :attachment, :remark, now(), now()
                )
                """
            ),
            {
                **common,
                "record_date": month_start + dt.timedelta(days=4),
                "asset_id": f"MVP-FORKLIFT-{index:02d}",
                "asset_name": f"仓储叉车 {index}",
                "amount": Decimal("128.0") + Decimal(index * 7),
                "mileage_km": Decimal("420.0") + Decimal(index * 18),
                "work_hours": Decimal("82.0") + Decimal(index * 3),
                "attachment": f"/demo/carbon/scope1/mobile-{REPORT_YEAR}-{index:02d}.pdf",
            },
        )
        await session.execute(
            text(
                """
                insert into dataapp_scope1stationarycombustion (
                    team_id, status, data_source, collection_method, confidence_level, data_year_type, data_year,
                    approved_at, facility_name, period_start, period_end, fuel_type, amount, unit,
                    meter_reading_start, meter_reading_end, attachment, remark, created_at, updated_at
                )
                values (
                    :team_id, :status, :data_source, :collection_method, :confidence_level, :data_year_type,
                    :data_year, :approved_at, '食堂天然气表', :period_start, :period_end, 'natural_gas',
                    :amount, 'm³', :meter_start, :meter_end, :attachment, :remark, now(), now()
                )
                """
            ),
            {
                **common,
                "period_start": month_start,
                "period_end": month_end,
                "amount": Decimal("2150.0") + Decimal(index * 95),
                "meter_start": Decimal(index * 2500),
                "meter_end": Decimal(index * 2500) + Decimal("2150.0") + Decimal(index * 95),
                "attachment": f"/demo/carbon/scope1/gas-{REPORT_YEAR}-{index:02d}.pdf",
            },
        )
        await session.execute(
            text(
                """
                insert into dataapp_scope2electricitybill (
                    team_id, status, data_source, collection_method, confidence_level, data_year_type, data_year,
                    approved_at, account_number, billing_month, total_kwh, peak_kwh, flat_kwh, valley_kwh,
                    amount_cny, attachment, remark, calc_status, factor_source, factor_year, factor_unit,
                    activity_amount, activity_unit, computed_co2e, computation_note, created_at, updated_at
                )
                values (
                    :team_id, :status, :data_source, :collection_method, :confidence_level, :data_year_type,
                    :data_year, :approved_at, 'MVP-ELEC-001', :billing_month, :total_kwh, :peak_kwh,
                    :flat_kwh, :valley_kwh, :amount_cny, :attachment, :remark, 'ready',
                    'NCSC 2026 行业企业排放因子', 2023, 'kgCO2e/kWh', :total_kwh, 'kWh',
                    :computed_co2e, '按江苏区域外购电力因子计算。', now(), now()
                )
                """
            ),
            {
                **common,
                "billing_month": month_start.strftime("%Y-%m"),
                "total_kwh": Decimal("45500.0") + Decimal(index * 1850),
                "peak_kwh": Decimal("14500.0") + Decimal(index * 500),
                "flat_kwh": Decimal("21000.0") + Decimal(index * 900),
                "valley_kwh": Decimal("10000.0") + Decimal(index * 450),
                "amount_cny": Decimal("38200.0") + Decimal(index * 1600),
                "attachment": f"/demo/carbon/scope2/electricity-{REPORT_YEAR}-{index:02d}.pdf",
                "computed_co2e": (Decimal("45500.0") + Decimal(index * 1850)) * GRID_FACTOR_KG_PER_KWH,
            },
        )
        steam_amount = Decimal("72.0") + Decimal(index * 3)
        await session.execute(
            text(
                """
                insert into dataapp_scope2purchasedenergy (
                    team_id, status, data_source, collection_method, confidence_level, data_year_type, data_year,
                    approved_at, energy_type_code, energy_type_name, supplier_name, period_start, period_end,
                    amount, unit, standard_amount, standard_unit, tce_amount, amount_cny, area_id, area_name,
                    facility_name, attachment, remark, calc_status, factor_source, factor_year, factor_unit,
                    activity_amount, activity_unit, computed_co2e, computation_note, standard_code,
                    conversion_factor_source, created_at, updated_at
                )
                values (
                    :team_id, :status, :data_source, :collection_method, :confidence_level, :data_year_type,
                    :data_year, :approved_at, 'purchased_steam', '外购蒸汽', '园区集中供热站',
                    :period_start, :period_end, :amount, 't', :standard_amount, 'kgce', :tce_amount,
                    :amount_cny, 'WH-01', '仓储主库区', '恒温库空调换热站', :attachment, :remark,
                    'ready', '企业示例蒸汽排放因子', 2026, 'kgCO2e/t', :amount, 't',
                    :computed_co2e, '按示例外购蒸汽活动量和企业默认因子计算。', 'GB/T 2589-2020',
                    'GB/T 2589-2020 折标参考系数; 企业MVP假设。', now(), now()
                )
                """
            ),
            {
                **common,
                "period_start": month_start,
                "period_end": month_end,
                "amount": steam_amount,
                "standard_amount": steam_amount * Decimal("128.6"),
                "tce_amount": steam_amount * Decimal("0.1286"),
                "amount_cny": steam_amount * Decimal("245.0"),
                "attachment": f"/demo/carbon/scope2/steam-{REPORT_YEAR}-{index:02d}.pdf",
                "computed_co2e": steam_amount * STEAM_FACTOR_KG_PER_TON,
            },
        )
        await session.execute(
            text(
                """
                insert into dataapp_scope3wastedisposal (
                    team_id, status, data_source, collection_method, confidence_level, data_year_type, data_year,
                    approved_at, date, category, weight_ton, treatment_method, vendor_name, attachment,
                    remark, created_at, updated_at
                )
                values (
                    :team_id, :status, :data_source, :collection_method, :confidence_level, :data_year_type,
                    :data_year, :approved_at, :date, 'waste_municipal_incineration', :weight_ton,
                    'incineration', '苏州绿源固废处置有限公司', :attachment, :remark, now(), now()
                )
                """
            ),
            {
                **common,
                "date": month_start + dt.timedelta(days=18),
                "weight_ton": Decimal("5.2") + Decimal(index) / Decimal(10),
                "attachment": f"/demo/carbon/scope3/waste-{REPORT_YEAR}-{index:02d}.pdf",
            },
        )
        await session.execute(
            text(
                """
                insert into dataapp_scope3thirdpartytransport (
                    team_id, status, data_source, collection_method, confidence_level, data_year_type, data_year,
                    approved_at, waybill_no, origin, destination, vehicle_type, distance_km, load_ton,
                    fuel_amount, attachment, remark, created_at, updated_at
                )
                values (
                    :team_id, :status, :data_source, :collection_method, :confidence_level, :data_year_type,
                    :data_year, :approved_at, :waybill_no, '苏州仓储中心', '上海客户仓',
                    'transport_heavy_truck', :distance_km, :load_ton, null, :attachment,
                    :remark, :created_at, now()
                )
                """
            ),
            {
                **common,
                "waybill_no": f"MVP-TMS-{REPORT_YEAR}{index:02d}",
                "distance_km": Decimal("98.0") + Decimal(index * 2),
                "load_ton": Decimal("18.0") + Decimal(index),
                "attachment": f"/demo/carbon/scope3/transport-{REPORT_YEAR}-{index:02d}.pdf",
                "created_at": month_start + dt.timedelta(days=20),
            },
        )
    await session.execute(
        text(
            """
            insert into dataapp_scope1refrigerantleak (
                team_id, status, data_source, collection_method, confidence_level, data_year_type, data_year,
                approved_at, device_id, device_name, fill_date, refrigerant_type, amount_kg, leak_type,
                attachment, remark, created_at, updated_at
            )
            values (
                :team_id, :status, :data_source, :collection_method, :confidence_level, :data_year_type,
                :data_year, :approved_at, 'MVP-AC-01', '恒温库空调机组', date '2026-04-12',
                'r410a', 6.8000, 'refill', '/demo/carbon/scope1/refrigerant-2026-04.pdf',
                :remark, now(), now()
            )
            """
        ),
        common,
    )


async def _seed_reporting_boundary(session: AsyncSession) -> tuple[int, int, int]:
    org_id = await _insert_returning_id(
        session,
        """
        insert into carbon_reporting_organization (
            team_id, code, name, organization_type, legal_entity_code, control_method, equity_share_pct,
            status, source_name, standard_code, remark, created_at, updated_at
        )
        values (
            :team_id, 'MVP-ORG-2026', '当前企业-组织碳盘查主体', 'enterprise', 'MVP-91320500',
            'operational_control', 100.0000, 'active', :source, 'ISO 14064-1 / GHG Protocol',
            '当前企业MVP组织边界样例。', now(), now()
        )
        returning id
        """,
    )
    period_id = await _insert_returning_id(
        session,
        """
        insert into carbon_reporting_period (
            team_id, reporting_org_id, code, name, period_type, period_start, period_end, base_year,
            status, locked_at, source_name, standard_code, remark, created_at, updated_at
        )
        values (
            :team_id, :org_id, 'MVP-RP-2026', '2026年度组织碳盘查', 'annual',
            date '2026-01-01', date '2026-12-31', 2025, 'locked', now(), :source,
            'ISO 14064-1 / GHG Protocol', '当前企业MVP报告期。', now(), now()
        )
        returning id
        """,
        {"org_id": org_id},
    )
    boundary_id = await _insert_returning_id(
        session,
        """
        insert into carbon_organization_boundary (
            team_id, reporting_org_id, period_id, boundary_no, boundary_name, boundary_type,
            boundary_method, operational_boundary, version, status, published_at, source_name,
            standard_code, confidence_level, remark, created_at, updated_at
        )
        values (
            :team_id, :org_id, :period_id, 'MVP-BOUNDARY-2026-V1', '2026运营控制法组织边界',
            'organization', 'operational_control',
            '{"scope1": true, "scope2": true, "scope3_categories": ["waste", "transport"]}'::json,
            1, 'published', now(), :source, 'ISO 14064-1 / GHG Protocol', 'medium',
            '覆盖园区仓储、办公、公辅和运输协同边界。', now(), now()
        )
        returning id
        """,
        {"org_id": org_id, "period_id": period_id},
    )
    await session.execute(
        text(
            """
            insert into carbon_boundary_facility (
                team_id, boundary_id, facility_type, facility_code, facility_name, facility_role,
                included, valid_from, valid_to, source_name, remark, created_at, updated_at
            )
            values
                (:team_id, :boundary_id, 'area', 'WH-01', '仓储主库区', 'core_operation',
                 true, date '2026-01-01', null, :source, 'MVP边界设施。', now(), now()),
                (:team_id, :boundary_id, 'area', 'OFFICE-01', '办公及公共区域', 'support',
                 true, date '2026-01-01', null, :source, 'MVP边界设施。', now(), now()),
                (:team_id, :boundary_id, 'equipment', 'MVP-AC-01', '恒温库空调机组', 'refrigeration',
                 true, date '2026-01-01', null, :source, 'MVP边界设施。', now(), now())
            """
        ),
        _params({"boundary_id": boundary_id}),
    )
    return org_id, period_id, boundary_id


async def _seed_accounting_batch(session: AsyncSession, boundary_id: int) -> m.CarbonAccountingBatch:
    batch = await CarbonAccountingInventoryUseCase(session).create_batch(
        {
            "boundary_id": boundary_id,
            "batch_no": "MVP-INV-2026",
            "batch_name": "当前企业2026年度组织碳排放清单",
            "status": "draft",
            "standard_code": "ISO 14064-1 / GHG Protocol",
            "source_name": SEED_SOURCE,
            "remark": "当前企业MVP组织碳盘查主样例。",
        }
    )
    batch = await CarbonAccountingInventoryUseCase(session).rebuild_inventory(batch.id)
    return await CarbonAccountingInventoryUseCase(session).lock_batch(batch.id)


async def _seed_verification(
    session: AsyncSession,
    org_id: int,
    period_id: int,
    boundary_id: int,
    batch_id: int,
) -> tuple[int, int]:
    template_id = await _insert_returning_id(
        session,
        """
        insert into carbon_verification_template_version (
            team_id, template_code, template_name, version, template_format, template_path,
            applicable_industry, applicable_scope, standard_name, standard_code, source_name,
            status, is_default, effective_from, confidence_level, remark, created_at, updated_at
        )
        values (
            :team_id, 'MVP-GENERAL-ORG-GHG', '工业企业组织碳盘查报告模板', 'v1.0',
            'docx', 'docs/评价方案/templates/工业企业温室气体排放盘查报告与核查材料包通用模板.docx',
            '工业企业通用', '组织碳盘查/核查材料包', 'ISO 14064-1 / GHG Protocol',
            'ISO 14064-1', :source, 'active', true, date '2026-01-01', 'medium',
            '当前企业MVP核查报告通用模板记录。', now(), now()
        )
        returning id
        """,
    )
    project_id = await _insert_returning_id(
        session,
        """
        insert into carbon_verification_project (
            team_id, project_no, project_name, project_type, reporting_org_id, period_id, boundary_id,
            accounting_batch_id, template_version_id, status, verification_year, planned_start,
            planned_end, started_at, completed_at, lead_reviewer, responsible_person, verifier_org,
            readiness_status, conclusion, scope_description, finding_summary, source_name,
            standard_code, confidence_level, remark, created_at, updated_at
        )
        values (
            :team_id, 'MVP-VER-2026', '当前企业2026年度组织碳核查支撑', 'organization_inventory',
            :org_id, :period_id, :boundary_id, :batch_id, :template_id, 'completed', 2026,
            date '2026-07-01', date '2026-07-15', timestamp '2026-07-01 09:00:00',
            timestamp '2026-07-12 17:30:00', '内部核查负责人', '能碳管理员',
            '内部核查组', 'ready', '材料齐备，盘查清单可用于首版报告导出。',
            '覆盖范围1、范围2及首版纳入的范围3废弃物和外购运输。'::text,
            '{"open": 0, "closed": 2, "medium": 1, "low": 1}'::json,
            :source, 'ISO 14064-1', 'medium', '当前企业MVP核查项目。', now(), now()
        )
        returning id
        """,
        {
            "org_id": org_id,
            "period_id": period_id,
            "boundary_id": boundary_id,
            "batch_id": batch_id,
            "template_id": template_id,
        },
    )
    await session.execute(
        text(
            """
            insert into carbon_verification_attachment (
                team_id, attachment_no, project_id, material_group, attachment_type, title,
                source_object_type, source_object_id, source_object_label, source_scope, source_period,
                file_name, file_path, content_type, file_size_bytes, sha256, version_no, status,
                uploaded_by, uploaded_at, reviewed_by, reviewed_at, source_name, standard_code,
                confidence_level, ocr_payload, remark, created_at, updated_at
            )
            values
                (
                    :team_id, 'MVP-ATT-001', :project_id, 'activity_data', 'supporting_document',
                    '2026年1-6月外购电力账单汇总', 'Scope2ElectricityBill', null, '外购电力账单',
                    '范围2', '2026-H1', 'electricity-bills-2026-h1.pdf',
                    '/demo/carbon/materials/electricity-bills-2026-h1.pdf', 'application/pdf',
                    524288, 'mvp-electricity-bills', 1, 'ready', '能碳管理员',
                    timestamp '2026-07-02 10:00:00', '内部核查负责人',
                    timestamp '2026-07-03 10:00:00', :source, 'ISO 14064-1', 'medium',
                    '{"pages": 6}'::json, 'MVP材料包附件。', now(), now()
                ),
                (
                    :team_id, 'MVP-ATT-002', :project_id, 'calculation', 'working_paper',
                    '组织碳排放清单计算底稿', 'CarbonAccountingBatch', :batch_id, 'MVP-INV-2026',
                    null, '2026', 'inventory-working-paper.xlsx',
                    '/demo/carbon/materials/inventory-working-paper.xlsx',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    393216, 'mvp-working-paper', 1, 'ready', '能碳管理员',
                    timestamp '2026-07-02 11:00:00', '内部核查负责人',
                    timestamp '2026-07-03 11:00:00', :source, 'ISO 14064-1', 'medium',
                    '{"sheets": 4}'::json, 'MVP材料包附件。', now(), now()
                )
            """
        ),
        _params({"project_id": project_id, "batch_id": batch_id}),
    )
    await session.execute(
        text(
            """
            insert into carbon_verification_finding (
                team_id, finding_no, project_id, issue_type, finding_type, severity, title,
                description, action_required, record_type, record_id, scope, display_name, period,
                status, owner, due_date, correction_comment, correction_evidence, reviewer, reviewed_at,
                closed_at, source_name, standard_code, source_payload, remark, created_at, updated_at
            )
            values
                (
                    :team_id, 'MVP-FIND-001', :project_id, 'evidence_traceability', 'data_quality',
                    'medium', '补充蒸汽结算单附件', '外购蒸汽记录已有活动量，需补齐供应商结算单。',
                    '上传蒸汽结算单并关联到范围2外购能源记录。', 'Scope2PurchasedEnergy', null,
                    '范围2', '外购蒸汽', '2026-03', 'closed', '能碳管理员', date '2026-07-08',
                    '已补充2026年3月蒸汽结算单。', '/demo/carbon/materials/steam-2026-03.pdf',
                    '内部核查负责人', timestamp '2026-07-08 15:00:00',
                    timestamp '2026-07-08 15:10:00', :source, 'ISO 14064-1',
                    '{"evidence": "steam bill"}'::json, 'MVP核查发现。', now(), now()
                ),
                (
                    :team_id, 'MVP-FIND-002', :project_id, 'calculation_review', 'method_check',
                    'low', '确认外购运输吨公里口径', '抽查运输记录的距离与载重口径。',
                    '保留TMS运单导出和承运商确认记录。', 'Scope3ThirdPartyTransport', null,
                    '范围3', '外购运输', '2026-05', 'closed', '物流主管', date '2026-07-09',
                    '已补充TMS运单导出。', '/demo/carbon/materials/tms-2026-05.xlsx',
                    '内部核查负责人', timestamp '2026-07-09 14:00:00',
                    timestamp '2026-07-09 14:20:00', :source, 'ISO 14064-1',
                    '{"evidence": "tms export"}'::json, 'MVP核查发现。', now(), now()
                )
            """
        ),
        _params({"project_id": project_id}),
    )
    job_id = await _insert_returning_id(
        session,
        """
        insert into carbon_verification_export_job (
            team_id, job_no, project_id, export_type, report_year, scope_filter, status_filter,
            status, template_name, template_path, standard_name, standard_code, file_path,
            file_sha256, file_size_bytes, manifest_payload, requested_by, completed_at,
            created_at, updated_at
        )
        values (
            :team_id, 'MVP-EXPORT-2026', :project_id, 'material_package', 2026, null,
            'approved', 'completed', '工业企业组织碳盘查报告模板',
            'docs/评价方案/templates/工业企业温室气体排放盘查报告与核查材料包通用模板.docx',
            'ISO 14064-1 / GHG Protocol', 'ISO 14064-1',
            '/demo/carbon/exports/org-ghg-material-package-2026.zip',
            'mvp-export-package', 2097152,
            '{"files": 3, "report": "org-ghg-report-2026.docx"}'::json,
            '能碳管理员', timestamp '2026-07-12 18:00:00', now(), now()
        )
        returning id
        """,
        {"project_id": project_id},
    )
    await session.execute(
        text(
            """
            insert into carbon_verification_export_file (
                team_id, job_id, file_type, path, source_name, content_type, size_bytes,
                sha256, created_at, updated_at
            )
            values
                (:team_id, :job_id, 'report_docx',
                 '/demo/carbon/exports/org-ghg-report-2026.docx', :source,
                 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                 786432, 'mvp-report-docx', now(), now()),
                (:team_id, :job_id, 'inventory_xlsx',
                 '/demo/carbon/exports/inventory-working-paper-2026.xlsx', :source,
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                 393216, 'mvp-inventory-xlsx', now(), now())
            """
        ),
        _params({"job_id": job_id}),
    )
    return template_id, project_id


async def _seed_product_footprint(session: AsyncSession) -> tuple[int, int]:
    product_id = await _insert_returning_id(
        session,
        """
        insert into dataapp_productionproduct (
            team_id, code, name, spec, category, output_kind, default_unit, standard_unit,
            is_enabled, remark, created_at, updated_at
        )
        values (
            :team_id, 'MVP-PROD-001', '智能仓储控制柜', 'SC-42U', '电气设备',
            'product', '台', '台', true, 'MVP产品碳足迹样例。', now(), now()
        )
        returning id
        """,
    )
    study_id = await _insert_returning_id(
        session,
        """
        insert into carbon_product_footprint_study (
            team_id, study_code, study_name, product_id, product_code, product_name, product_spec,
            product_category, standard_code, standard_name, pcr_code, functional_unit, declared_unit,
            period_start, period_end, boundary_type, status, result_status, source_name,
            confidence_level, remark, created_at, updated_at
        )
        values (
            :team_id, 'MVP-PCF-2026-001', '智能仓储控制柜产品碳足迹研究',
            :product_id, 'MVP-PROD-001', '智能仓储控制柜', 'SC-42U', '电气设备',
            'ISO 14067', '温室气体 产品碳足迹量化要求和指南', null,
            '1台智能仓储控制柜', '1台', date '2026-01-01', date '2026-06-30',
            'cradle_to_gate', 'completed', 'calculated', :source, 'medium',
            '当前企业MVP产品碳足迹样例。', now(), now()
        )
        returning id
        """,
        {"product_id": product_id},
    )
    await session.execute(
        text(
            """
            insert into carbon_product_system_boundary (
                team_id, study_id, boundary_type, included_stages, excluded_stages, cutoff_rule,
                geography, technology_scope, temporal_scope, assumption, standard_code, source_name,
                created_at, updated_at
            )
            values (
                :team_id, :study_id, 'cradle_to_gate',
                '["raw_material", "manufacturing", "packaging"]'::json,
                '["use_phase", "end_of_life"]'::json,
                '单项质量或排放贡献小于1%的辅料暂按截断处理，总截断比例不超过5%。',
                '中国华东', '企业当前量产工艺', '2026年1-6月',
                'MVP阶段采用企业内部补录与供应商审核PCF数据。', 'ISO 14067', :source,
                now(), now()
            )
            """
        ),
        _params({"study_id": study_id}),
    )
    stage_rows = [
        ("raw_material", "原材料取得", 1),
        ("manufacturing", "生产制造", 2),
        ("packaging", "包装入库", 3),
    ]
    stage_ids: dict[str, int] = {}
    for code, name, sequence in stage_rows:
        stage_ids[code] = await _insert_returning_id(
            session,
            """
            insert into carbon_product_lifecycle_stage (
                team_id, study_id, stage_code, stage_name, sequence, included,
                description, created_at, updated_at
            )
            values (
                :team_id, :study_id, :code, :name, :sequence, true,
                'MVP产品碳足迹阶段。', now(), now()
            )
            returning id
            """,
            {"study_id": study_id, "code": code, "name": name, "sequence": sequence},
        )
    items = [
        (
            "MVP-PCF-IT-001",
            "raw_material",
            "supplier_pcf",
            "钣金壳体供应商PCF",
            None,
            None,
            None,
            None,
            Decimal("58.2000"),
        ),
        (
            "MVP-PCF-IT-002",
            "raw_material",
            "material",
            "铜排与线束",
            Decimal("18.5"),
            "kg",
            Decimal("3.2000"),
            "kgCO2e/kg",
            None,
        ),
        (
            "MVP-PCF-IT-003",
            "manufacturing",
            "energy",
            "装配测试用电",
            Decimal("86.0"),
            "kWh",
            GRID_FACTOR_KG_PER_KWH,
            "kgCO2e/kWh",
            None,
        ),
        (
            "MVP-PCF-IT-004",
            "packaging",
            "material",
            "纸箱与托盘包装",
            Decimal("9.6"),
            "kg",
            Decimal("1.4500"),
            "kgCO2e/kg",
            None,
        ),
    ]
    total = Decimal(0)
    for item_no, stage_code, activity_type, name, amount, unit, factor, factor_unit, supplier_pcf in items:
        computed = supplier_pcf if supplier_pcf is not None else (amount or Decimal(0)) * (factor or Decimal(0))
        total += computed
        await session.execute(
            text(
                """
                insert into carbon_product_footprint_inventory_item (
                    team_id, study_id, stage_id, item_no, activity_type, item_name, activity_amount,
                    activity_unit, factor_value, factor_unit, factor_source, supplier_pcf_value,
                    supplier_pcf_unit, supplier_name, allocation_ratio, computed_co2e, calc_status,
                    data_quality, source_type, source_ref, evidence_path, included, remark,
                    created_at, updated_at
                )
                values (
                    :team_id, :study_id, :stage_id, :item_no, :activity_type, :item_name,
                    :activity_amount, :activity_unit, :factor_value, :factor_unit, :factor_source,
                    :supplier_pcf_value, :supplier_pcf_unit, :supplier_name, 1.000000,
                    :computed_co2e, 'calculated', 'medium', 'manual', :source_ref,
                    :evidence_path, true, :remark, now(), now()
                )
                """
            ),
            _params(
                {
                    "study_id": study_id,
                    "stage_id": stage_ids[stage_code],
                    "item_no": item_no,
                    "activity_type": activity_type,
                    "item_name": name,
                    "activity_amount": amount,
                    "activity_unit": unit,
                    "factor_value": factor,
                    "factor_unit": factor_unit,
                    "factor_source": "企业MVP因子/供应商审核PCF",
                    "supplier_pcf_value": supplier_pcf,
                    "supplier_pcf_unit": "kgCO2e/台" if supplier_pcf is not None else None,
                    "supplier_name": "苏州精密钣金有限公司" if supplier_pcf is not None else None,
                    "computed_co2e": computed,
                    "source_ref": "MVP-PCF-2026-H1",
                    "evidence_path": f"/demo/carbon/pcf/{item_no}.pdf",
                    "remark": f"{SEED_MARKER} PCF清单项。",
                }
            ),
        )
    await session.execute(
        text(
            """
            insert into carbon_product_footprint_allocation_rule (
                team_id, study_id, process_code, process_name, allocation_method, basis, ratio,
                source_name, remark, created_at, updated_at
            )
            values (
                :team_id, :study_id, 'assembly-line-a', 'A线装配测试',
                'physical', '按台数分配', 1.000000, :source, 'MVP分配规则。', now(), now()
            )
            """
        ),
        _params({"study_id": study_id}),
    )
    await session.execute(
        text(
            """
            insert into carbon_product_footprint_result (
                team_id, study_id, result_version, total_co2e, unit, footprint_per_declared_unit,
                result_status, calculated_at, inventory_count, missing_factor_count, stage_payload,
                result_payload, report_status, remark, created_at, updated_at
            )
            values (
                :team_id, :study_id, 1, :total, 'kgCO2e', :total, 'calculated', now(),
                4, 0,
                '[{"stage": "raw_material", "co2e": 117.4}, {"stage": "manufacturing", "co2e": 50.1122},
                  {"stage": "packaging", "co2e": 13.92}]'::json,
                '{"declared_unit": "1台", "boundary": "cradle_to_gate"}'::json,
                'draft', :remark, now(), now()
            )
            """
        ),
        _params({"study_id": study_id, "total": total, "remark": f"{SEED_MARKER} PCF计算结果。"}),
    )
    return product_id, study_id


async def _seed_supply_chain(session: AsyncSession, product_id: int) -> int:
    supplier_id = await _insert_returning_id(
        session,
        """
        insert into carbon_supply_chain_supplier (
            team_id, supplier_code, name, industry, supplier_type, contact_name, contact_email,
            country_region, status, risk_level, source_name, standard_code, remark, created_at, updated_at
        )
        values (
            :team_id, 'MVP-SUP-001', '苏州精密钣金有限公司', '金属制品', 'tier1',
            '张工', 'supplier-carbon@example.com', '中国江苏', 'active', 'medium',
            :source, 'ISO 14067', '当前企业MVP供应商。', now(), now()
        )
        returning id
        """,
    )
    await session.execute(
        text(
            """
            insert into carbon_supplier_site (
                team_id, supplier_id, site_code, site_name, country_region, address,
                facility_scope, status, remark, created_at, updated_at
            )
            values (
                :team_id, :supplier_id, 'MVP-SITE-001', '苏州钣金一厂', '中国江苏',
                '苏州市工业园区示例路88号', '壳体制造', 'active', :remark, now(), now()
            )
            """
        ),
        _params({"supplier_id": supplier_id, "remark": f"{SEED_MARKER} 供应商站点。"}),
    )
    task_id = await _insert_returning_id(
        session,
        """
        insert into carbon_supplier_disclosure_task (
            team_id, task_no, task_name, supplier_id, task_type, product_id, product_code,
            product_name, period_start, period_end, due_date, status, submitted_at, approved_at,
            requested_by, standard_code, source_name, confidence_level, remark, created_at, updated_at
        )
        values (
            :team_id, 'MVP-SCT-2026-001', '智能仓储控制柜钣金壳体PCF披露',
            :supplier_id, 'pcf', :product_id, 'MVP-PROD-001', '智能仓储控制柜',
            date '2026-01-01', date '2026-06-30', date '2026-07-05', 'approved',
            timestamp '2026-07-01 10:30:00', timestamp '2026-07-03 16:00:00',
            '采购经理', 'ISO 14067', :source, 'medium', '当前企业MVP供应链任务。',
            now(), now()
        )
        returning id
        """,
        {"supplier_id": supplier_id, "product_id": product_id},
    )
    await session.execute(
        text(
            """
            insert into carbon_supplier_carbon_data (
                team_id, task_id, supplier_id, data_no, data_type, scope_category, product_id,
                product_code, product_name, material_code, material_name, activity_amount,
                activity_unit, pcf_value, pcf_unit, co2e_amount, factor_source, boundary_type,
                data_quality, verified, validity_start, validity_end, source_type, source_ref,
                status, published_to_scope3, published_to_pcf, remark, created_at, updated_at
            )
            values (
                :team_id, :task_id, :supplier_id, 'MVP-SCD-001', 'pcf', 'purchased_goods',
                :product_id, 'MVP-PROD-001', '智能仓储控制柜', 'MVP-SHELL-001', '钣金壳体',
                1.000000, '套', 58.200000, 'kgCO2e/套', 58.200000,
                '供应商审核PCF声明', 'cradle_to_gate', 'supplier_reported', true,
                date '2026-01-01', date '2026-12-31', 'supplier_portal_snapshot',
                'MVP-SCT-2026-001', 'approved', false, true, :remark, now(), now()
            )
            """
        ),
        _params(
            {
                "task_id": task_id,
                "supplier_id": supplier_id,
                "product_id": product_id,
                "remark": f"{SEED_MARKER} 供应商PCF数据。",
            }
        ),
    )
    await session.execute(
        text(
            """
            insert into carbon_supplier_evidence (
                team_id, task_id, evidence_no, evidence_type, file_name, file_path, file_sha256,
                file_size_bytes, review_status, submitted_by, reviewed_at, remark, created_at, updated_at
            )
            values (
                :team_id, :task_id, 'MVP-SCE-001', 'pcf_statement', 'supplier-pcf-statement.pdf',
                '/demo/carbon/supply-chain/supplier-pcf-statement.pdf', 'mvp-supplier-pcf',
                262144, 'approved', '张工', timestamp '2026-07-03 15:30:00',
                :remark, now(), now()
            )
            """
        ),
        _params({"task_id": task_id, "remark": f"{SEED_MARKER} 供应商证据。"}),
    )
    await session.execute(
        text(
            """
            insert into carbon_supplier_review_decision (
                team_id, task_id, decision, reason, reviewed_by, decided_at, created_at, updated_at
            )
            values (
                :team_id, :task_id, 'approved', :reason, '采购经理',
                timestamp '2026-07-03 16:00:00', now(), now()
            )
            """
        ),
        _params({"task_id": task_id, "reason": f"{SEED_MARKER} 数据与证据一致，允许用于PCF。"}),
    )
    await session.execute(
        text(
            """
            insert into carbon_supplier_disclosure_release (
                team_id, release_no, task_id, release_type, recipient_name, status, released_at,
                payload, remark, created_at, updated_at
            )
            values (
                :team_id, 'MVP-REL-2026-001', :task_id, 'internal_pcf_reference',
                '产品碳足迹研究', 'released', timestamp '2026-07-04 09:00:00',
                '{"pcf_value": 58.2, "unit": "kgCO2e/套"}'::json,
                'MVP供应商披露发布。', now(), now()
            )
            """
        ),
        _params({"task_id": task_id}),
    )
    return task_id


async def _seed_assets(
    session: AsyncSession,
    boundary_id: int,
    batch_id: int,
    total_co2e: Decimal | None,
) -> tuple[int, int, int, int]:
    total_t = (total_co2e or Decimal(0)) / Decimal(1000)
    period_id = await _insert_returning_id(
        session,
        """
        insert into carbon_compliance_period (
            team_id, period_code, period_name, market, period_start, period_end, surrender_due_date,
            boundary_id, accounting_batch_id, status, risk_threshold_yellow, risk_threshold_orange,
            risk_threshold_red, source_name, standard_code, confidence_level, remark, created_at, updated_at
        )
        values (
            :team_id, 'MVP-CP-2026', '2026年度碳资产履约周期', 'national',
            date '2026-01-01', date '2026-12-31', date '2027-06-30', :boundary_id, :batch_id,
            'open', 0.0300, 0.0800, 0.1500, :source, '企业MVP假设', 'medium',
            '当前企业MVP碳资产周期。', now(), now()
        )
        returning id
        """,
        {"boundary_id": boundary_id, "batch_id": batch_id},
    )
    account_id = await _insert_returning_id(
        session,
        """
        insert into carbon_asset_account (
            team_id, account_code, account_name, asset_type, market, currency, status,
            registry_account_no, owner_name, source_name, standard_code, remark, created_at, updated_at
        )
        values (
            :team_id, 'MVP-CEA-ACCOUNT', '当前企业碳配额账户', 'allowance', 'national',
            'CNY', 'active', 'MVP-REG-001', '当前企业', :source, '企业MVP假设',
            '当前企业MVP资产账户。', now(), now()
        )
        returning id
        """,
    )
    allowance_id = await _insert_returning_id(
        session,
        """
        insert into carbon_quota_allocation (
            team_id, period_id, account_id, allocation_no, quota_type, allocated_amount,
            adjustment_amount, used_amount, frozen_amount, unit, valid_from, valid_to,
            source_name, standard_code, remark, created_at, updated_at
        )
        values (
            :team_id, :period_id, :account_id, 'MVP-ALLOW-2026', 'CEA', :allocated,
            0, :used, 0, 'tCO2e', date '2026-01-01', date '2026-12-31',
            :source, '企业MVP假设', '当前企业MVP配额台账。', now(), now()
        )
        returning id
        """,
        {
            "period_id": period_id,
            "account_id": account_id,
            "allocated": total_t + Decimal("120.0"),
            "used": total_t * Decimal("0.35"),
        },
    )
    credit_id = await _insert_returning_id(
        session,
        """
        insert into carbon_credit_holding (
            team_id, account_id, holding_no, credit_type, project_code, project_name, registry,
            vintage_year, quantity, used_quantity, frozen_quantity, unit, market_price, currency,
            valid_from, valid_to, status, source_name, standard_code, remark, created_at, updated_at
        )
        values (
            :team_id, :account_id, 'MVP-CCER-2026', 'CCER', 'MVP-CCER-PV-01',
            '分布式光伏减排项目', 'CCER登记簿', 2025, 80.000000, 0, 0,
            'tCO2e', 62.000000, 'CNY', date '2026-01-01', date '2028-12-31',
            'active', :source, '企业MVP假设', '当前企业MVP CCER持仓。', now(), now()
        )
        returning id
        """,
        {"account_id": account_id},
    )
    await session.execute(
        text(
            """
            insert into carbon_asset_transaction (
                team_id, account_id, transaction_no, asset_type, transaction_type, amount,
                unit_price, currency, fee_rate, tax_rate, trade_date, counterparty, status,
                scenario_payload, source_name, remark, created_at, updated_at
            )
            values (
                :team_id, :account_id, 'MVP-TXN-2026-001', 'allowance', 'buy',
                50.000000, 68.000000, 'CNY', 0.001000, 0.000000, date '2026-07-20',
                '模拟交易对手方', 'simulated',
                '{"purpose": "risk_buffer"}'::json, :source, '当前企业MVP模拟交易。', now(), now()
            )
            """
        ),
        _params({"account_id": account_id}),
    )
    await session.execute(
        text(
            """
            insert into carbon_surrender_record (
                team_id, period_id, account_id, surrender_no, asset_type, quota_allocation_id,
                credit_holding_id, amount, unit, status, surrendered_at, purpose, source_name,
                remark, created_at, updated_at
            )
            values (
                :team_id, :period_id, :account_id, 'MVP-SUR-2026-001', 'allowance',
                :allowance_id, null, :amount, 'tCO2e', 'completed',
                timestamp '2026-07-25 10:00:00', 'interim_compliance', :source,
                '当前企业MVP清缴记录。', now(), now()
            )
            """
        ),
        _params(
            {
                "period_id": period_id,
                "account_id": account_id,
                "allowance_id": allowance_id,
                "amount": total_t * Decimal("0.20"),
            }
        ),
    )
    await session.execute(
        text(
            """
            insert into carbon_asset_forecast_scenario (
                team_id, period_id, scenario_code, scenario_name, base_year, forecast_start,
                forecast_end, emission_growth_rate, planned_reduction, planned_allowance_purchase,
                planned_credit_purchase, planned_surrender, allowance_price, credit_price, currency,
                status, source_name, confidence_level, remark, created_at, updated_at
            )
            values (
                :team_id, :period_id, 'MVP-ASSET-BASELINE-2026', '2026履约基准预测',
                2026, date '2026-07-01', date '2026-12-31', 0.030000, 25.000000,
                50.000000, 20.000000, :planned_surrender, 68.000000, 62.000000,
                'CNY', 'active', :source, 'medium', '当前企业MVP履约预测。',
                now(), now()
            )
            """
        ),
        _params({"period_id": period_id, "planned_surrender": total_t}),
    )
    return period_id, account_id, allowance_id, credit_id


async def _seed_budget(session: AsyncSession) -> int:
    plan_id = await _insert_returning_id(
        session,
        """
        insert into dataapp_energycarbonbudgetplan (
            team_id, code, name, budget_year, period_type, period_start, period_end,
            target_scope, target_code, target_name, energy_budget_tce, carbon_budget_co2e,
            denominator_plan, denominator_unit, energy_intensity_budget, carbon_intensity_budget,
            status, source_name, standard_code, confidence_level, remark, created_at, updated_at
        )
        values (
            :team_id, 'MVP-ECB-2026', '当前企业2026年度能碳预算', 2026, 'annual',
            date '2026-01-01', date '2026-12-31', 'enterprise', null, '当前企业',
            82.000000, 360000.000000, 12000.000000, '台',
            0.006833, 30.000000, 'active', :source, 'GB/T 2589-2020 / 企业MVP假设',
            'medium', '当前企业MVP能碳预算。', now(), now()
        )
        returning id
        """,
    )
    weights = [
        Decimal("0.076"),
        Decimal("0.072"),
        Decimal("0.078"),
        Decimal("0.080"),
        Decimal("0.083"),
        Decimal("0.088"),
        Decimal("0.092"),
        Decimal("0.091"),
        Decimal("0.086"),
        Decimal("0.084"),
        Decimal("0.082"),
        Decimal("0.088"),
    ]
    for index, weight in enumerate(weights, start=1):
        month = dt.date(REPORT_YEAR, index, 1)
        energy_budget = Decimal("82.0") * weight
        carbon_budget = Decimal("360000.0") * weight
        denominator = Decimal("12000.0") * weight
        await session.execute(
            text(
                """
                insert into dataapp_energycarbonbudgetallocation (
                    team_id, plan_id, period_month, target_scope, target_code, target_name,
                    energy_budget_tce, carbon_budget_co2e, denominator_budget, denominator_unit,
                    energy_intensity_budget, carbon_intensity_budget, status, source_name,
                    standard_code, confidence_level, remark, created_at, updated_at
                )
                values (
                    :team_id, :plan_id, :period_month, 'enterprise', null, '当前企业',
                    :energy_budget, :carbon_budget, :denominator, '台',
                    :energy_intensity, :carbon_intensity, 'active', :source,
                    'GB/T 2589-2020 / 企业MVP假设', 'medium', '当前企业MVP月度预算。',
                    now(), now()
                )
                """
            ),
            _params(
                {
                    "plan_id": plan_id,
                    "period_month": month,
                    "energy_budget": energy_budget,
                    "carbon_budget": carbon_budget,
                    "denominator": denominator,
                    "energy_intensity": energy_budget / denominator,
                    "carbon_intensity": carbon_budget / denominator,
                }
            ),
        )
    await session.execute(
        text(
            """
            insert into dataapp_energycarbonbudgetadjustment (
                team_id, plan_id, allocation_id, adjustment_no, adjustment_type, effective_month,
                original_energy_budget_tce, original_carbon_budget_co2e, adjusted_energy_budget_tce,
                adjusted_carbon_budget_co2e, reason, status, requested_by, approved_by, approved_at,
                source_name, standard_code, confidence_level, remark, created_at, updated_at
            )
            select
                :team_id, :plan_id, a.id, 'MVP-ECB-ADJ-2026-06', 'reforecast', date '2026-06-01',
                a.energy_budget_tce, a.carbon_budget_co2e, a.energy_budget_tce + 0.600000,
                a.carbon_budget_co2e + 2400.000000,
                '6月恒温库负荷上升，调整月度预算。', 'approved', '能碳管理员',
                '运营负责人', timestamp '2026-06-20 16:00:00', :source,
                '企业MVP假设', 'medium', '当前企业MVP预算调整。', now(), now()
            from dataapp_energycarbonbudgetallocation a
            where a.plan_id = :plan_id and a.period_month = date '2026-06-01'
            """
        ),
        _params({"plan_id": plan_id}),
    )
    return plan_id


async def _collect_result(session: AsyncSession, **ids: int) -> CarbonMvpSeedResult:
    scope_records = 0
    for table_name in (
        "dataapp_scope1mobilecombustion",
        "dataapp_scope1stationarycombustion",
        "dataapp_scope1refrigerantleak",
        "dataapp_scope2electricitybill",
        "dataapp_scope2purchasedenergy",
        "dataapp_scope3wastedisposal",
        "dataapp_scope3thirdpartytransport",
    ):
        scope_records += int(
            await session.scalar(
                text(f"select count(*) from {table_name} where team_id = :team_id and remark like :marker_like"),
                {"team_id": str(DEFAULT_TENANT_ID), "marker_like": f"%{SEED_MARKER}%"},
            )
            or 0
        )
    inventory_items = int(
        await session.scalar(
            text(
                "select count(*) from carbon_emission_inventory_item where team_id = :team_id and batch_id = :batch_id"
            ),
            {"team_id": str(DEFAULT_TENANT_ID), "batch_id": ids["batch_id"]},
        )
        or 0
    )
    return CarbonMvpSeedResult(
        scope_records=scope_records,
        organizations=1,
        boundaries=1,
        accounting_batches=1,
        inventory_items=inventory_items,
        verification_projects=1 if ids.get("project_id") else 0,
        pcf_studies=1 if ids.get("study_id") else 0,
        suppliers=1 if ids.get("supplier_task_id") else 0,
        asset_periods=1 if ids.get("asset_period_id") else 0,
        budget_plans=1 if ids.get("plan_id") else 0,
    )


async def _insert_returning_id(session: AsyncSession, statement: str, extra: dict[str, Any] | None = None) -> int:
    return int((await session.execute(text(statement), _params(extra))).scalar_one())


def _params(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"team_id": str(DEFAULT_TENANT_ID), "source": SEED_SOURCE}
    if extra:
        params.update(extra)
    return params


def _months(year: int, count: int) -> list[dt.date]:
    return [dt.date(year, month, 1) for month in range(1, count + 1)]


def _month_end(month_start: dt.date) -> dt.date:
    if month_start.month == DECEMBER:
        return dt.date(month_start.year, DECEMBER, 31)
    return dt.date(month_start.year, month_start.month + 1, 1) - dt.timedelta(days=1)
