import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import models as m
from app.domain.material_allocation.schemas import HourCalculation, OperationCreate, OperationUpdate
from app.domain.material_allocation.usecases import (
    CalculateMaterialCarbonAllocation,
    MaterialAllocationError,
    MaterialHandlingOperationUseCase,
)
from app.domain.product_footprint.usecases.footprint import ProductFootprintUseCase
from app.domain.product_footprint.usecases.material_import import MaterialResultImportUseCase
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]
START = datetime(2026, 7, 10, 8, tzinfo=UTC)


async def fixture(session):
    team = m.Team(name="Handling", slug="handling-tests")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    area = m.MonitorSector(code="A", name="作业区")
    device = m.MonitorEquipment(code="F", name="叉车", sector=area, is_enable=True)
    product = m.ProductionProduct(code="P", name="物资", default_unit="托", is_enabled=True)
    factor = m.EmissionFactor(
        team_id=team.id,
        scope="2",
        category="electricity",
        sub_category="test",
        unit="kWh",
        factor_value=Decimal("0.5"),
        factor_unit="kgCO2e/kWh",
        year=2026,
        source="test",
        review_status="approved",
        is_active=True,
    )
    session.add_all([area, device, product, factor])
    await session.flush()
    fact = m.EnergyIntervalFact(
        team_id=team.id,
        source_system="test",
        source_record_id="hour",
        equipment_id=device.id,
        energy_type_code="purchased_electricity",
        granularity="hour",
        period_start=START.replace(tzinfo=None),
        period_end=(START + timedelta(hours=1)).replace(tzinfo=None),
        amount=Decimal(6),
        unit="kWh",
        is_current=True,
    )
    session.add(fact)
    use = MaterialHandlingOperationUseCase(session)
    ops = []
    for n, (offset, duration) in enumerate(((0, 10), (20, 20))):
        op = await use.create(
            OperationCreate(
                operation_no=f"T-{n}",
                operation_type="internal_transfer",
                equipment_id=device.id,
                equipment_type="forklift",
                material_id=product.id,
                batch_no="B",
                quantity=1,
                active_intervals=[
                    {"start": START + timedelta(minutes=offset), "end": START + timedelta(minutes=offset + duration)}
                ],
            )
        )
        await use.confirm(op.id)
        ops.append(op)
    command = HourCalculation(
        equipment_id=device.id,
        period_start=START,
        period_end=START + timedelta(hours=1),
        factor_id=factor.id,
        energy_source_system="test",
        assumption="hourly_uniform_intensity_v1",
        applicability_note="explicit test assumption",
    )
    await session.commit()
    return use, ops, command, fact, product, factor


async def test_hour_allocation_conservation_and_idempotency(session):
    _, _, cmd, _, _, _ = await fixture(session)
    calc = CalculateMaterialCarbonAllocation(session)
    run = (await calc.execute(cmd))[0]
    assert run.total_energy_kwh == Decimal(3)
    assert run.unallocated_energy_kwh == Decimal(3)
    assert run.total_co2e_kg == Decimal("1.5")
    first_id, rev = run.id, run.revision
    again = (await calc.execute(cmd))[0]
    assert (again.id, again.revision) == (first_id, rev)
    results = list(
        await session.scalars(
            select(m.MaterialCarbonAllocationResult).order_by(m.MaterialCarbonAllocationResult.operation_id)
        )
    )
    assert [r.allocated_energy_kwh for r in results] == [Decimal(1), Decimal(2)]
    assert await session.scalar(select(func.count(m.ProductFootprintInventoryItem.id))) == 0


async def test_patch_only_changes_explicit_fields(session):
    use, ops, _, _, _, _ = await fixture(session)
    row = ops[0]
    before = (
        row.source_system,
        row.source_record_id,
        row.unit,
        row.duration_minutes,
        row.operation_status,
        row.data_quality,
    )
    await use.update(row.id, OperationUpdate(remark="备注"))
    assert (
        row.source_system,
        row.source_record_id,
        row.unit,
        row.duration_minutes,
        row.operation_status,
        row.data_quality,
    ) == before
    with pytest.raises(ValidationError):
        OperationUpdate.model_validate({"source_system": "vision"})
    with pytest.raises(MaterialAllocationError):
        await use.update(row.id, OperationUpdate(quantity=None))


async def test_hour_boundary_and_overlap_are_rejected(session):
    use, ops, cmd, _, _, _ = await fixture(session)
    calc = CalculateMaterialCarbonAllocation(session)
    with pytest.raises(MaterialAllocationError, match="整小时"):
        await calc.execute(cmd.model_copy(update={"period_start": START + timedelta(minutes=30)}))
    await use.update(
        ops[1].id, OperationUpdate(active_intervals=[{"start": START, "end": START + timedelta(minutes=20)}])
    )
    await use.confirm(ops[1].id)
    with pytest.raises(MaterialAllocationError, match="重叠"):
        await calc.execute(cmd)


async def test_zero_factor_missing_energy_and_duplicate_source(session):
    _, _, cmd, fact, _, factor = await fixture(session)
    factor.factor_value = 0
    run = (await CalculateMaterialCarbonAllocation(session).execute(cmd))[0]
    assert run.total_co2e_kg == 0
    with pytest.raises(MaterialAllocationError, match="唯一完整"):
        await CalculateMaterialCarbonAllocation(session).execute(
            cmd.model_copy(update={"energy_source_system": "missing"})
        )
    session.add(
        m.EnergyIntervalFact(
            team_id=fact.team_id,
            source_system="test",
            source_record_id="duplicate",
            equipment_id=fact.equipment_id,
            energy_type_code="purchased_electricity",
            granularity="hour",
            period_start=fact.period_start,
            period_end=fact.period_end,
            amount=1,
            unit="kWh",
            is_current=True,
        )
    )
    await session.flush()
    with pytest.raises(MaterialAllocationError, match="唯一完整"):
        await CalculateMaterialCarbonAllocation(session).execute(cmd)


async def test_pcf_reference_idempotency_and_staleness(session):
    use, ops, cmd, fact, product, _ = await fixture(session)
    calc = CalculateMaterialCarbonAllocation(session)
    run = (await calc.execute(cmd))[0]
    result = await session.scalar(
        select(m.MaterialCarbonAllocationResult).where(m.MaterialCarbonAllocationResult.operation_id == ops[0].id)
    )
    study = m.ProductFootprintStudy(
        product_id=product.id,
        product_code=product.code,
        study_code="S",
        study_name="研究",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
    )
    session.add(study)
    await session.flush()
    stage = m.ProductLifeCycleStage(study_id=study.id, stage_code="storage", stage_name="仓储", included=True)
    session.add(stage)
    await session.flush()
    importer = MaterialResultImportUseCase(session)
    item = await importer.import_result(study.id, result.id, stage.id)
    assert (await importer.import_result(study.id, result.id, stage.id)).id == item.id
    assert item.activity_type == "energy"
    with pytest.raises(ValueError, match="派生清单"):
        await ProductFootprintUseCase(session).update_inventory_item(item.id, {"activity_amount": 999})
    with pytest.raises(MaterialAllocationError, match="不可删除"):
        await use.delete(ops[0].id)
    fact.amount = 12
    await session.flush()
    with pytest.raises(MaterialAllocationError, match="变更"):
        await importer.validate_study(study.id)
    assert (await calc.execute(cmd))[0].id == run.id
    with pytest.raises(MaterialAllocationError, match="同步"):
        await importer.validate_study(study.id)
    await importer.import_result(study.id, result.id, stage.id)
    assert item.activity_amount == 2
    await importer.validate_study(study.id)
    await use.withdraw(ops[0].id)
    with pytest.raises(MaterialAllocationError):
        await importer.validate_study(study.id)


async def test_cross_tenant_operation_and_factor_rejected(session):
    _, ops, cmd, _, _, _ = await fixture(session)
    other = m.Team(name="Other", slug="other-handling")
    session.add(other)
    await session.commit()
    session.info[TENANT_ID_SESSION_KEY] = other.id
    with pytest.raises(MaterialAllocationError):
        await MaterialHandlingOperationUseCase(session).get(ops[0].id)
    with pytest.raises(MaterialAllocationError):
        await CalculateMaterialCarbonAllocation(session).execute(cmd)


async def test_demo_repeat_install_preserves_objects_and_user_changes(session):
    from app.demo.ops.material_handling import seed_material_handling

    team = m.Team(name="Demo Handling", slug="woheng-taizhou-production-base", is_active=True)
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    session.add(m.MonitorSector(code="AUTO_WH", name="仓储区"))
    await session.flush()
    await seed_material_handling(session, team.slug, "TZ")
    await session.commit()
    models = (
        m.MaterialHandlingOperation,
        m.MaterialCarbonAllocationRun,
        m.MaterialCarbonAllocationResult,
        m.ProductFootprintStudy,
        m.DemoManifest,
    )
    before = [await session.scalar(select(func.count(model.id))) for model in models]
    await seed_material_handling(session, team.slug, "TZ")
    await session.commit()
    assert [await session.scalar(select(func.count(model.id))) for model in models] == before
    assert await session.scalar(select(func.count(m.ProductFootprintInventoryItem.id))) == 0
    fact = await session.scalar(select(m.EnergyIntervalFact))
    fact.amount += 1
    await session.flush()
    with pytest.raises(ValueError, match="已被修改"):
        await seed_material_handling(session, team.slug, "TZ")


async def test_empty_hour_keeps_all_energy_unallocated(session):
    use, ops, cmd, _, _, _ = await fixture(session)
    for op in ops:
        await use.withdraw(op.id)
    run = (await CalculateMaterialCarbonAllocation(session).execute(cmd))[0]
    assert run.total_energy_kwh == 0
    assert run.unallocated_energy_kwh == 6
    assert run.total_co2e_kg == 0


async def test_equivalent_interval_patch_preserves_confirmation(session):
    use, ops, _, _, _, _ = await fixture(session)
    await use.update(
        ops[0].id,
        OperationUpdate(
            active_intervals=[
                {
                    "start": "2026-07-10T16:00:00+08:00",
                    "end": "2026-07-10T16:10:00+08:00",
                }
            ],
            remark="修订备注",
        ),
    )
    assert ops[0].operation_status == "confirmed"


async def test_vision_business_revision_requires_reason(session):
    use, ops, _, _, _, _ = await fixture(session)
    row = ops[0]
    row.source_system = "vision"
    await session.flush()
    with pytest.raises(MaterialAllocationError, match="修正原因"):
        await use.update(row.id, OperationUpdate(quantity=2))
    await use.update(row.id, OperationUpdate(quantity=2, remark="核实物资数量"))
    assert row.quantity == 2
    assert row.operation_status == "draft"
    assert row.source_system == "vision"


async def test_confirmation_refreshes_master_data_snapshot(session):
    use, ops, _, _, _, _ = await fixture(session)
    area = m.MonitorSector(code="B", name="新作业区")
    session.add(area)
    await session.flush()
    device = await session.get(m.MonitorEquipment, ops[0].equipment_id)
    device.sector_id = area.id
    await session.flush()
    await use.confirm(ops[0].id)
    assert ops[0].area_id == area.id
    assert ops[0].area_name == area.name


async def test_concurrent_hour_calculation_has_one_current_result(session):
    _, _, cmd, _, _, _ = await fixture(session)
    tenant_id = session.info[TENANT_ID_SESSION_KEY]
    factory = async_sessionmaker(session.bind, expire_on_commit=False)

    async def calculate():
        async with factory() as other:
            other.info[TENANT_ID_SESSION_KEY] = tenant_id
            run = (await CalculateMaterialCarbonAllocation(other).execute(cmd))[0]
            await other.commit()
            return run.id, run.revision

    first, second = await asyncio.gather(calculate(), calculate())
    assert first == second
    assert await session.scalar(select(func.count(m.MaterialCarbonAllocationRun.id))) == 1
    assert await session.scalar(select(func.count(m.MaterialCarbonAllocationResult.id))) == 2


async def test_write_permission_is_required_for_non_superuser(session, authenticated_client, test_user):
    _, ops, _, _, _, _ = await fixture(session)
    tenant_id = session.info[TENANT_ID_SESSION_KEY]
    session.add(m.TeamMember(team_id=tenant_id, user_id=test_user.id, role=m.TeamRoles.MEMBER, is_owner=False))
    await session.commit()
    headers = {"X-Team-Id": str(tenant_id)}
    path = f"/api/material-allocation/operations/{ops[0].id}"
    denied = await authenticated_client.patch(path, json={"remark": "permission test"}, headers=headers)
    assert denied.status_code == 403
    permission = m.Permission(
        code="material_operations:write", name="Maintain operations", module="material_allocation"
    )
    role = m.Role(name="Material Operator", slug="material-operator")
    session.add_all([role, permission])
    await session.flush()
    session.add(m.RolePermission(role_id=role.id, permission_id=permission.id))
    session.add(m.UserRole(user_id=test_user.id, role_id=role.id))
    await session.commit()
    allowed = await authenticated_client.patch(path, json={"remark": "permission test"}, headers=headers)
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data"]["remark"] == "permission test"
