"""Owned, repeatable handling examples using the production commands."""

# ruff: noqa: RUF001
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.db import models as m
from app.domain.material_allocation.policies import fingerprint
from app.domain.material_allocation.schemas import HourCalculation, OperationCreate
from app.domain.material_allocation.usecases import CalculateMaterialCarbonAllocation, MaterialHandlingOperationUseCase
from app.lib.tenancy import require_session_tenant_id


async def seed_material_handling(session: Any, tenant_slug: str, city_code: str) -> None:
    team = require_session_tenant_id(session)
    area = await session.scalar(
        select(m.MonitorSector).where(m.MonitorSector.team_id == team, m.MonitorSector.code == "AUTO_WH")
    )
    if area is None:
        msg = "请先生成自动化仓储区域"
        raise ValueError(msg)

    async def owned(model: type[Any], key: str, values: dict) -> Any:
        registry = await session.scalar(
            select(m.DemoManifest).where(
                m.DemoManifest.namespace == "woheng",
                m.DemoManifest.package_key == "woheng-showcase",
                m.DemoManifest.object_type == model.__tablename__,
                m.DemoManifest.object_key == key,
            )
        )
        row = await session.get(model, int(registry.object_id)) if registry else None
        if row:
            current = {k: getattr(row, k) for k in values}
            if fingerprint(current) != registry.details["hash"]:
                msg = f"演示对象已被修改，保留原数据: {key}"
                raise ValueError(msg)
            return row
        if registry:
            msg = f"演示对象已被删除，请先处理清单: {key}"
            raise ValueError(msg)
        row = model(team_id=team, **values)
        session.add(row)
        await session.flush()
        session.add(
            m.DemoManifest(
                namespace="woheng",
                package_key="woheng-showcase",
                profile="full",
                module_key="material-handling",
                object_type=model.__tablename__,
                object_key=key,
                object_id=str(row.id),
                team_id=team,
                details={"hash": fingerprint({k: getattr(row, k) for k in values})},
            )
        )
        return row

    factor = await owned(
        m.EmissionFactor,
        f"{tenant_slug}:handling-factor",
        {
            "scope": "2",
            "category": "electricity",
            "sub_category": "handling-demo",
            "unit": "kWh",
            "factor_value": Decimal("0.5"),
            "factor_unit": "kgCO2e/kWh",
            "year": 2026,
            "source": "沃衡物资作业演示假设",
            "is_active": True,
            "review_status": "approved",
            "projection_status": "manual",
        },
    )
    await owned(
        m.ProductionProduct,
        f"{tenant_slug}:vision-material",
        {
            "code": "VISION-WHEEL-RIM",
            "name": "轮毂物资（演示任务）",
            "default_unit": "托",
            "is_enabled": True,
        },
    )
    usecase = MaterialHandlingOperationUseCase(session)
    for index, (code, name, kind) in enumerate(
        (
            ("FORKLIFT-EV-01", "电动叉车一号", "forklift"),
            ("ROTARY-CRANE-01", "物资旋转吊一号", "rotary_crane"),
            ("BRIDGE-CRANE-01", "库内行吊一号", "bridge_crane"),
            ("STACKER-01", "自动堆垛机一号", "stacker"),
        )
    ):
        device = await session.scalar(
            select(m.MonitorEquipment).where(m.MonitorEquipment.team_id == team, m.MonitorEquipment.code == code)
        )
        if device is None:
            device = await owned(
                m.MonitorEquipment,
                f"{tenant_slug}:handling-device:{code}",
                {
                    "code": code,
                    "name": name,
                    "sector_id": area.id,
                    "is_enable": True,
                    "energy_type": "purchased_electricity",
                },
            )
        start = datetime(2026, 7, 10, 8 + index, tzinfo=UTC)
        await owned(
            m.EnergyIntervalFact,
            f"{tenant_slug}:handling-hour:{code}",
            {
                "source_system": "woheng-material-hour",
                "source_record_id": f"{tenant_slug}:{code}:20260710",
                "equipment_id": device.id,
                "equipment_code": device.code,
                "equipment_name": device.name,
                "area_id": area.code,
                "area_name": area.name,
                "energy_type_code": "purchased_electricity",
                "granularity": "hour",
                "period_start": start.replace(tzinfo=None),
                "period_end": (start + timedelta(hours=1)).replace(tzinfo=None),
                "amount": Decimal(6 if city_code == "TZ" else 9),
                "unit": "kWh",
                "data_quality": "simulated",
                "is_current": True,
                "revision_no": 1,
                "source_snapshot": {"assumption": "hourly_uniform_intensity_v1", "source": "沃衡演示假设"},
            },
        )
        for n, (offset, minutes) in enumerate(((0, 10), (20, 20))):
            material = await owned(
                m.ProductionProduct,
                f"{tenant_slug}:handling-material:{index}:{n}",
                {
                    "code": f"WH-MH-{index}-{n}",
                    "name": f"{name}作业物资{n + 1}",
                    "default_unit": "托",
                    "is_enabled": True,
                },
            )
            study = await owned(
                m.ProductFootprintStudy,
                f"{tenant_slug}:handling-study:{index}:{n}",
                {
                    "product_id": material.id,
                    "product_code": material.code,
                    "product_name": material.name,
                    "study_code": f"WH-MH-{index}-{n}",
                    "study_name": f"{material.name}仓储阶段研究",
                    "boundary_type": "gate_to_gate",
                    "period_start": date(2026, 7, 1),
                    "period_end": date(2026, 7, 31),
                },
            )
            await owned(
                m.ProductSystemBoundary,
                f"{tenant_slug}:handling-boundary:{index}:{n}",
                {
                    "study_id": study.id,
                    "boundary_type": "gate_to_gate",
                },
            )
            await owned(
                m.ProductLifeCycleStage,
                f"{tenant_slug}:handling-stage:{index}:{n}",
                {
                    "study_id": study.id,
                    "stage_code": "storage",
                    "stage_name": "仓储作业",
                    "included": True,
                },
            )
            command = OperationCreate(
                operation_no=f"WH-{city_code}-MH-{index}-{n}",
                operation_type="internal_transfer",
                equipment_id=device.id,
                equipment_type=kind,
                material_id=material.id,
                batch_no="20260710",
                quantity=1,
                active_intervals=[
                    {"start": start + timedelta(minutes=offset), "end": start + timedelta(minutes=offset + minutes)}
                ],
            )
            key = f"{tenant_slug}:handling-operation:{index}:{n}"
            op = await usecase.receive(
                command,
                source_system="woheng-showcase",
                source_record_id=key,
                data_quality="simulated",
                source_payload={"assumption": "controlled_demo"},
            )
            registry = await session.scalar(
                select(m.DemoManifest).where(
                    m.DemoManifest.namespace == "woheng",
                    m.DemoManifest.object_type == "dataapp_materialhandlingoperation",
                    m.DemoManifest.object_key == key,
                )
            )
            if registry and op.operation_status != "confirmed":
                msg = f"演示作业状态已变更，保留人工修改: {key}"
                raise ValueError(msg)
            if registry is None:
                await usecase.confirm(op.id)
                session.add(
                    m.DemoManifest(
                        namespace="woheng",
                        package_key="woheng-showcase",
                        profile="full",
                        module_key="material-handling",
                        object_type="dataapp_materialhandlingoperation",
                        object_key=key,
                        object_id=str(op.id),
                        team_id=team,
                        details={"source_key": key},
                    )
                )
        runs = await CalculateMaterialCarbonAllocation(session).execute(
            HourCalculation(
                equipment_id=device.id,
                period_start=start,
                period_end=start + timedelta(hours=1),
                energy_source_system="woheng-material-hour",
                factor_id=factor.id,
                assumption="hourly_uniform_intensity_v1",
                applicability_note="沃衡模拟小时电量，演示按有效时段估算并保留未归属量",
            )
        )
        for run in runs:
            for obj in [
                run,
                *list(
                    await session.scalars(
                        select(m.MaterialCarbonAllocationResult).where(
                            m.MaterialCarbonAllocationResult.run_id == run.id
                        )
                    )
                ),
            ]:
                key = f"{tenant_slug}:{obj.__tablename__}:{obj.id}"
                if not await session.scalar(
                    select(m.DemoManifest.id).where(
                        m.DemoManifest.namespace == "woheng",
                        m.DemoManifest.object_key == key,
                        m.DemoManifest.object_type == obj.__tablename__,
                    )
                ):
                    session.add(
                        m.DemoManifest(
                            namespace="woheng",
                            package_key="woheng-showcase",
                            profile="full",
                            module_key="material-handling",
                            object_type=obj.__tablename__,
                            object_key=key,
                            object_id=str(obj.id),
                            team_id=team,
                            details={"source": "hourly-command"},
                        )
                    )
    await session.flush()
