"""Exercise real import, generation, factor selection and calculation in isolated PostgreSQL."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import models as m
from app.demo.ops.enterprise_entry import SOURCE_SYSTEM, load_cases, seed_enterprise_entry, validate_enterprise_entry
from app.demo.showcase.builder import AREAS, EQUIPMENT
from app.domain.energy.usecases.energy_types import ensure_standard_energy_types
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.mark.parametrize(("city", "slug"), [("TZ", "taizhou"), ("HZ", "huzhou")])
async def test_import_to_result_is_repeatable_and_preserves_unrelated_equipment(session, city, slug, monkeypatch):  # noqa: PLR0915
    team = m.Team(name=f"沃衡{city}工厂", slug=f"woheng-{slug}-production-base", is_active=True)
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    org = m.ReportingOrganization(code=f"WOHENG-{city}-ORG", name=f"沃衡{city}工厂")
    session.add(org)
    areas = {}
    for spec in AREAS:
        row = m.MonitorSector(team_id=team.id, code=spec.code, name=spec.name, level=0, path=f"/{spec.code}")
        session.add(row)
        await session.flush()
        areas[spec.code] = row
    for spec in EQUIPMENT:
        session.add(
            m.MonitorEquipment(team_id=team.id, code=spec.code, name=spec.name, sector_id=areas[spec.area_code].id)
        )
    session.add(
        m.MonitorEquipment(team_id=team.id, code="901", name="SZSCADA临时电表901", sector_id=areas["ENERGY"].id)
    )
    session.add(
        m.GhgReportingProfile(
            code="CORPORATE_ISO14064_GHGP",
            name="测试核算方案",
            version="1",
            standard_code="DEMO",
            standard_version="1",
            effective_from=date(2026, 1, 1),
            status="published",
        )
    )
    for code, parameter in [
        ("F02_EF", "EMISSION_FACTOR"),
        ("F08_PURCHASED_ENERGY", "ENERGY_FACTOR"),
        ("F09_TRANSPORT_ACTIVITY", "TRANSPORT_FACTOR"),
    ]:
        method = m.GhgCalculationMethodDefinition(
            code=code,
            name=code,
            version="1",
            formula_family="TEST",
            formula_expression={},
            human_formula="活动量乘以参数",
            standard_code="DEMO",
            applicable_categories=[],
            effective_from=date(2026, 1, 1),
            status="published",
        )
        session.add(method)
        await session.flush()
        session.add(
            m.GhgMethodParameterDefinition(
                method_id=method.id,
                parameter_code=parameter,
                parameter_name=parameter,
                parameter_role="emission_factor",
                allowed_units=[],
                required=True,
            )
        )
    await session.commit()
    await ensure_standard_energy_types(session, apply=True)
    import base64

    from app.demo.ops.enterprise_entry import CITY_NAMES, SAMPLE_ROOT
    from app.demo.ops.entry_samples import CATEGORY_NAMES, sample_context
    from app.domain.ghg_inventory.usecases.import_workbook import CommitCategoryWorkbook, PreviewCategoryWorkbook

    for category, label in CATEGORY_NAMES.items():
        context = sample_context(city, category)
        path = SAMPLE_ROOT / f"{CITY_NAMES[city]}基地_{label}.xlsx"
        batch = await PreviewCategoryWorkbook(session).execute(
            {
                **context,
                "file_name": path.name,
                "workbook_base64": base64.b64encode(path.read_bytes()).decode(),
            }
        )
        assert batch.error_count == 0, batch.preview_snapshot
        committed = await CommitCategoryWorkbook(session).execute(
            batch.batch_code,
            acknowledge_warnings=True,
            warning_acknowledgement="录入活动后选择企业因子并核算",
        )
        assert committed.status == "committed"
    imported_ids = set((await session.scalars(select(m.GhgActivityRecord.id))).all())
    assert len(imported_ids) == 4
    from app.domain.ghg_inventory.usecases.maintenance import GhgInventoryMaintenance

    forklift = await session.scalar(select(m.MonitorEquipment).where(m.MonitorEquipment.code == "FORKLIFT-FLEET-01"))
    configured_source = await GhgInventoryMaintenance(session).create_source(
        {
            "inventory_code": f"WOHENG-{city}-ENTRY-202610",
            "organization_code": org.code,
            "facility_code": "CHARGING",
            "source_code": "USER-FORKLIFT",
            "source_name": "人工配置的厂内柴油叉车",
            "iso_category_code": "1.2",
            "default_equipment_id": forklift.id,
            "default_area_id": areas["CHARGING"].id,
            "source_system": "manual_entry",
            "source_payload": {"user_note": "保留用户维护内容"},
        }
    )
    from app.demo.ops.enterprise_entry import energy_input, sample_rows
    from app.domain.energy.usecases.imports import EnergyDatasetImportUseCase

    # Exercise the actual Chinese download through the same mapping as the UI.
    chinese_rows = [
        {
            "area_name": row["区域"],
            "equipment_name": row["设备"],
            "energy_type_name": row["能源种类"],
            "amount": row["能源用量"],
            "unit": row["单位"],
            "cost_cny": row["费用"],
            "remark": row["备注"],
            "period_start": "2026-10-01",
            "period_end": "2026-10-31T23:59:59",
            "granularity": "month",
        }
        for row in sample_rows(city, "能源导入")
    ]
    preview = await EnergyDatasetImportUseCase(session).import_rows(
        dataset="energy_interval_facts",
        rows=chinese_rows,
        source_name="企业中文模板",
        preview=True,
    )
    assert not preview.errors, preview.errors
    assert len(preview.records) == 4
    # Resume a partial install using the existing record ID, with explicit update.
    gas_case = next(case for case in load_cases(city) if case.energy_type == "natural_gas")
    boiler = await session.scalar(select(m.MonitorEquipment).where(m.MonitorEquipment.code == "BOILER-01"))
    partial = energy_input(gas_case, area=areas["UTILITY"], equipment=boiler)
    partial["amount"] = "1"
    imported = await EnergyDatasetImportUseCase(session).import_rows(
        dataset="energy_interval_facts",
        rows=[partial],
        source_name="部分安装",
    )
    existing_fact_id = imported.imported_ids[0]
    first = await seed_enterprise_entry(session, city=city)
    restored = await session.get(m.EnergyIntervalFact, existing_fact_id)
    assert restored.amount == gas_case.amount

    await session.refresh(configured_source)
    assert configured_source.source_name == "人工配置的厂内柴油叉车"
    assert configured_source.source_payload == {"user_note": "保留用户维护内容"}
    energy_facts = list((await session.scalars(select(m.EnergyIntervalFact))).all())
    assert all("iso_category_code" not in (fact.source_snapshot or {}) for fact in energy_facts)
    assert all(fact.equipment_id is not None for fact in energy_facts)

    assert first["passed"], first
    inventory = f"WOHENG-{city}-ENTRY-202610"
    activities = list(
        (
            await session.scalars(select(m.GhgActivityRecord).where(m.GhgActivityRecord.inventory_code == inventory))
        ).all()
    )
    forklift_activity = next(row for row in activities if row.source_code == "USER-FORKLIFT")
    assert forklift_activity.source_code == "USER-FORKLIFT"
    assert forklift_activity.iso_category_code == "1.2"
    original_ids = {row.id for row in activities}
    assert imported_ids <= original_ids
    assert all(
        row.source_record_type == "ghg_import_batch" and row.source_record_id
        for row in activities
        if row.id in imported_ids
    )
    assert len(list((await session.scalars(select(m.GhgEmissionSource))).all())) == 7
    second = await seed_enterprise_entry(session, city=city)
    assert second["passed"], second
    assert (
        set(
            (
                await session.scalars(
                    select(m.GhgActivityRecord.id).where(m.GhgActivityRecord.inventory_code == inventory)
                )
            ).all()
        )
        == original_ids
    )
    assert (
        len(
            list(
                (
                    await session.scalars(
                        select(m.EnergyIntervalFact).where(m.EnergyIntervalFact.source_system == SOURCE_SYSTEM)
                    )
                ).all()
            )
        )
        == 4
    )
    assert (
        await session.scalar(select(m.MonitorEquipment.name).where(m.MonitorEquipment.code == "901"))
        == "SZSCADA临时电表901"
    )
    assert (await validate_enterprise_entry(session, city=city))["passed"]
    run = await session.scalar(
        select(m.GhgCalculationRun)
        .where(m.GhgCalculationRun.inventory_code == inventory)
        .order_by(m.GhgCalculationRun.id.desc())
    )
    results = list(
        (await session.scalars(select(m.GhgCalculationResult).where(m.GhgCalculationResult.run_id == run.id))).all()
    )
    assert len(results) == len(load_cases(city))
    refrigerant = next(row for row in results if row.gas_code == "R32" and row.gas_mass_kg > 0)
    assert refrigerant.gas_mass_kg == Decimal("2.4" if city == "TZ" else "1.8")
    assert refrigerant.co2e_kg == refrigerant.gas_mass_kg * 675
    for activity in activities:
        assert activity.source_payload["factor_id"]
    # Repeat the real UI generation/apply-factor/calculation workflow, without
    # any demo input_record tags, and retain original activity IDs.
    boundary_id = first["boundary"]["boundary_id"]
    regenerated = await GhgInventoryMaintenance(session).generate_activities(
        inventory_code=inventory,
        reporting_period_id=run.reporting_period_id,
        organization_boundary_id=boundary_id,
        source_types=["energy_electricity", "energy_natural_gas", "energy_diesel"],
    )
    assert regenerated["failedCount"] == regenerated["skippedCount"] == 0
    energy_activities = [row for row in activities if row.source_record_type == "energy_interval_fact"]
    assert len(energy_activities) == 4
    assert all("input_record" not in row.source_payload for row in energy_activities)
    assert original_ids == {row.id for row in activities}
    from app.domain.factor_library.usecases.factors import CalculationFactorMaintenance
    from app.domain.ghg_inventory.usecases.calculation import RunInventoryCalculation

    for activity in activities:
        if activity.iso_category_code == "1.4":
            await CalculationFactorMaintenance(session).apply_activity_factor(
                inventory_code=inventory,
                record_code=activity.record_code,
                factor_id=activity.source_payload["factor_id"],
                parameter_code="GWP",
            )
    ui_run = await RunInventoryCalculation(session).execute(
        inventory_code=inventory,
        reporting_profile_code="CORPORATE_ISO14064_GHGP",
        reporting_period_id=run.reporting_period_id,
        reporting_org_id=org.id,
        organization_boundary_id=boundary_id,
    )
    assert ui_run.status == "completed"
    assert (await validate_enterprise_entry(session, city=city))["passed"]
    assert (await seed_enterprise_entry(session, city=city))["reused"]
    assert all("input_record" not in row.source_payload for row in energy_activities)

    from app.demo.ops.entry_boundary import repair_entry_boundary_links
    from app.domain.ghg_inventory.usecases.calculation import RunInventoryCalculation

    # The same boundary selected by the UI is published for this exact month.
    boundary_id = first["boundary"]["boundary_id"]
    boundary = await session.get(m.OrganizationBoundary, boundary_id)
    assert boundary.status == "published"
    assert boundary.period_id == run.reporting_period_id
    assert run.organization_boundary_id == boundary_id
    assert first["boundary"]["ui_readiness"]["readyForCalculation"]
    assert first["boundary"]["ui_readiness"]["activityCount"] == 8
    assert all(row.organization_boundary_id == boundary_id for row in activities)
    period = await session.get(m.ReportingPeriod, run.reporting_period_id)
    period.period_start = date(2026, 1, 1)
    await session.flush()
    assert not (await validate_enterprise_entry(session, city=city))["passed"]
    period.period_start = date(2026, 10, 1)
    boundary.status = "draft"
    await session.flush()
    assert not (await validate_enterprise_entry(session, city=city))["passed"]
    boundary.status = "published"
    # Simulate the previous released demo with results but missing boundary links.
    for activity in activities:
        activity.organization_boundary_id = None
    run.organization_boundary_id = None
    await session.commit()
    original_org = activities[0].organization_code
    activities[0].organization_code = "OTHER-ORG"
    await session.flush()
    with pytest.raises(ValueError, match="报告主体"):
        await repair_entry_boundary_links(session, city=city)
    assert all(row.organization_boundary_id is None for row in activities)
    activities[0].organization_code = original_org
    await session.flush()
    old_results = [(row.id, row.co2e_kg, dict(row.formula_snapshot)) for row in results]
    old_ids = {row.id for row in activities}
    assert not (await validate_enterprise_entry(session, city=city))["passed"]
    repaired = await repair_entry_boundary_links(session, city=city)
    assert repaired["ready"] and repaired["activity_links_updated"] == 8
    assert (await repair_entry_boundary_links(session, city=city))["activity_links_updated"] == 0
    assert run.organization_boundary_id is None
    assert old_ids == {row.id for row in activities}
    assert [(row.id, row.co2e_kg, dict(row.formula_snapshot)) for row in results] == old_results
    rerun = await RunInventoryCalculation(session).execute(
        inventory_code=inventory,
        reporting_profile_code="CORPORATE_ISO14064_GHGP",
        reporting_period_id=period.id,
        reporting_org_id=org.id,
        organization_boundary_id=boundary.id,
    )
    assert rerun.status == "completed" and rerun.organization_boundary_id == boundary.id
    assert rerun.id != run.id
    rerun_results = list(
        (
            await session.scalars(
                select(m.GhgCalculationResult).where(
                    m.GhgCalculationResult.run_id == rerun.id,
                )
            )
        ).all()
    )
    assert len(rerun_results) == 8
    assert sum(row.co2e_kg for row in rerun_results) == sum(row.co2e_kg for row in results)
    assert [(row.id, row.co2e_kg, dict(row.formula_snapshot)) for row in results] == old_results
    # A partial/failed run with existing results must be protected before any writes.
    run.status = "failed"
    rerun.status = "failed"
    ui_run.status = "failed"
    await session.commit()
    before = [(row.id, dict(row.source_payload), row.activity_amount) for row in activities]
    with pytest.raises(ValueError, match="被核算引用"):
        await seed_enterprise_entry(session, city=city)
    assert [(row.id, dict(row.source_payload), row.activity_amount) for row in activities] == before
    run.status = "completed"
    rerun.status = "completed"
    ui_run.status = "completed"
    await session.commit()
    fact = await session.scalar(select(m.EnergyIntervalFact).where(m.EnergyIntervalFact.source_system == SOURCE_SYSTEM))
    fact.amount += 1
    await session.flush()
    assert not (await validate_enterprise_entry(session, city=city))["passed"]
    fact.amount -= 1
    await session.commit()

    # Full install checks both tenants before writes. This fixture supplies the
    # actual October case; historical showcase volume is irrelevant to this check.
    from unittest.mock import AsyncMock

    from app.demo.ops.contracts import DemoExecutionContext
    from app.demo.ops.woheng import WohengShowcasePackage

    package = WohengShowcasePackage(session)
    monkeypatch.setattr(package, "_has_base_showcase_dataset", lambda _counts: True)
    history_models = (m.GhgCalculationRun, m.GhgCalculationResult, m.GhgParameterAssignment)

    async def history_snapshot():
        return [
            list((await session.execute(select(*model.__table__.c).order_by(model.id))).all())
            for model in history_models
        ]

    history_before = await history_snapshot()
    for _ in range(2):
        await package._assert_install_targets_safe()
        assert (await seed_enterprise_entry(session, city=city))["reused"]
        assert await history_snapshot() == history_before
    dictionary = AsyncMock()
    monkeypatch.setattr("app.demo.ops.woheng.ensure_standard_energy_types", dictionary)
    period = await session.scalar(select(m.ReportingPeriod).where(m.ReportingPeriod.code == inventory))
    period.status = "locked"
    await session.commit()
    with pytest.raises(ValueError, match="已锁定或归档"):
        await package._install(DemoExecutionContext("woheng-showcase", "woheng", apply=True))
    dictionary.assert_not_awaited()
    assert await history_snapshot() == history_before
    period = await session.scalar(select(m.ReportingPeriod).where(m.ReportingPeriod.code == inventory))
    period.status = "open"
    activity = await session.scalar(select(m.GhgActivityRecord).where(m.GhgActivityRecord.inventory_code == inventory))
    activity.status = "locked"
    locked_id = activity.id
    await session.commit()
    with pytest.raises(ValueError, match="既有案例已修改或锁定"):
        await package._install(DemoExecutionContext("woheng-showcase", "woheng", apply=True))
    dictionary.assert_not_awaited()
    assert (
        await session.scalar(select(m.GhgActivityRecord.status).where(m.GhgActivityRecord.id == locked_id)) == "locked"
    )
    assert await history_snapshot() == history_before


async def test_owned_energy_cleanup_leaves_external_sources_and_tenants_untouched(session):
    from datetime import datetime

    from app.demo.ops.enterprise_entry import repair_owned_energy_snapshots

    team = m.Team(name="沃衡清理测试", slug="woheng-taizhou-production-base", is_active=True)
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    area = m.MonitorSector(team_id=team.id, code="COLD_WH", name="涂装车间", path="/COLD_WH", level=0)
    session.add(area)
    await session.flush()
    device = m.MonitorEquipment(team_id=team.id, code="CHILLER-01", name="动力站制冷机组一号", sector_id=area.id)
    session.add(device)
    await session.flush()
    for source, code, energy in [
        ("demo_ghg_activity_daily", "OLD-REF", "refrigerant"),
        ("manual_entry", "USER-REF", "refrigerant"),
        ("demo_showcase", "OWNED-ELEC", "purchased_electricity"),
        ("meter_projection", "USER-ELEC", "purchased_electricity"),
    ]:
        session.add(
            m.EnergyIntervalFact(
                team_id=team.id,
                source_system=source,
                source_record_id=code,
                energy_type_code=energy,
                equipment_id=device.id,
                equipment_code=device.code,
                equipment_name="冷链制冷机组一号",
                area_id=str(area.id),
                area_name="冷链仓库",
                granularity="month",
                period_start=datetime(2026, 8, 1),  # noqa: DTZ001 - database uses local naive intervals
                period_end=datetime(2026, 8, 31, 23, 59, 59),  # noqa: DTZ001
                amount=Decimal(10),
                unit="kg" if energy == "refrigerant" else "kWh",
                is_current=True,
                revision_no=1,
            )
        )
    await session.commit()
    await repair_owned_energy_snapshots(session)
    rows = {row.source_record_id: row for row in (await session.scalars(select(m.EnergyIntervalFact))).all()}
    assert "OLD-REF" not in rows
    assert rows["USER-REF"].amount == 10
    assert rows["OWNED-ELEC"].equipment_name == "动力站制冷机组一号"
    assert rows["OWNED-ELEC"].area_name == "涂装车间"
    assert rows["USER-ELEC"].equipment_name == "冷链制冷机组一号"
