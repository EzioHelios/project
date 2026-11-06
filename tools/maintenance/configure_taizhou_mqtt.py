"""Configure Jiangyan and Taixing addressed-meter MQTT ingestion.

Run inside the application environment. The default mode prints the intended
result and rolls back; pass ``--apply`` to persist idempotent upserts.
"""

# ruff: noqa: C901, RUF001, T201 - idempotent setup workflow and reviewed Chinese master data/audit output.

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.config import alchemy
from app.db import models as m
from app.domain.metering.reading_facts import SZSCADA_TAG_TO_POINT, point_spec
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

OWNER_UNIT = "国网江苏省电力有限公司泰州供电分公司"
BROKER_HOST = "116.63.218.160"
BROKER_PORT = 1883
USERNAME_ENV = "SZSCADA_MQTT_USERNAME"
PASSWORD_ENV = "SZSCADA_MQTT_PASSWORD"  # noqa: S105 - environment-variable name, not a credential.


@dataclass(frozen=True, slots=True)
class MeterConfig:
    address: str
    source_name: str
    equipment_code: str
    equipment_name: str
    sector_code: str
    use_system_code: str
    use_system_name: str
    include_in_scope2: bool
    boundary_type: str = "meter_circuit"
    business_equipment_code: str | None = None
    business_equipment_name: str | None = None


@dataclass(frozen=True, slots=True)
class WarehouseConfig:
    team_id: UUID
    team_name: str
    team_slug: str
    warehouse_code: str
    location: str
    root_sector_code: str
    source_code: str
    source_name: str
    client_id: str
    topic: str
    gateway_key: str
    sectors: tuple[tuple[str, str], ...]
    meters: tuple[MeterConfig, ...]


WAREHOUSES = (
    WarehouseConfig(
        team_id=UUID("00000000-0000-7000-8000-000000000003"),
        team_name="姜堰天目路仓库",
        team_slug="jiangyan-tianmu-warehouse",
        warehouse_code="JY-TML",
        location="泰州市姜堰区天目路",
        root_sector_code="JY-TML",
        source_code="szscada-jy",
        source_name="姜堰天目路仓库 SZSCADA 电表采集",
        client_id="warehouse-carbon-jy-metering",
        topic="szscada/jy",
        gateway_key="3850524f85185900a5e4190e167fc226",
        sectors=(("JY-OFFICE", "办公区域"), ("JY-CHARGE", "充电区域"), ("JY-STORAGE", "仓储区域")),
        meters=(
            MeterConfig(
                "202501020786",
                "办公室",
                "JY-METER-202501020786",
                "办公室电表",
                "JY-OFFICE",
                "SYS-OFFICE",
                "办公及公共系统",
                True,
                business_equipment_code="JY-GRP-OFFICE",
                business_equipment_name="办公及公共设施",
            ),
            MeterConfig(
                "202501020788",
                "充电桩",
                "JY-METER-202501020788",
                "充电桩电表",
                "JY-CHARGE",
                "SYS-CHARGING",
                "车辆及设备充电系统",
                True,
                business_equipment_code="JY-GRP-CHARGING",
                business_equipment_name="充电设施",
            ),
            MeterConfig(
                "202501020787",
                "仓库",
                "JY-METER-202501020787",
                "仓库电表",
                "JY-STORAGE",
                "SYS-STORAGE",
                "仓储设施系统",
                True,
                business_equipment_code="JY-GRP-STORAGE",
                business_equipment_name="仓储设施",
            ),
        ),
    ),
    WarehouseConfig(
        team_id=UUID("00000000-0000-7000-8000-000000000004"),
        team_name="泰兴科能路仓库",
        team_slug="taixing-keneng-warehouse",
        warehouse_code="TX-KNL",
        location="泰兴市科能路",
        root_sector_code="TX-KNL",
        source_code="szscada-tx",
        source_name="泰兴科能路仓库 SZSCADA 电表采集",
        client_id="warehouse-carbon-tx-metering",
        topic="szscada/tx",
        gateway_key="3850524f8518590566e4190e16bc2026",
        sectors=(("TX-OUTDOOR", "室外作业区"), ("TX-CHARGE", "充电区域"), ("TX-INDOOR", "室内作业区")),
        meters=(
            MeterConfig(
                "202502220305",
                "总电表",
                "TX-METER-202502220305",
                "总进线电表",
                "TX-KNL",
                "SYS-SITE-INCOMING",
                "场站购入电力",
                True,
                boundary_type="site_import",
            ),
            MeterConfig(
                "202502220306",
                "室外龙门吊",
                "TX-METER-202502220306",
                "室外龙门吊电表",
                "TX-OUTDOOR",
                "SYS-LIFTING",
                "起重吊装系统",
                False,
                business_equipment_code="TX-GRP-OUTDOOR-LIFTING",
                business_equipment_name="室外龙门吊设备组",
            ),
            MeterConfig(
                "202502220307",
                "充电桩",
                "TX-METER-202502220307",
                "充电桩电表",
                "TX-CHARGE",
                "SYS-CHARGING",
                "车辆及设备充电系统",
                False,
                business_equipment_code="TX-GRP-CHARGING",
                business_equipment_name="充电设施",
            ),
            MeterConfig(
                "202502220308",
                "室内行吊",
                "TX-METER-202502220308",
                "室内行吊电表",
                "TX-INDOOR",
                "SYS-LIFTING",
                "起重吊装系统",
                False,
                business_equipment_code="TX-GRP-INDOOR-LIFTING",
                business_equipment_name="室内行吊设备组",
            ),
        ),
    ),
)


async def _ensure_team(config: WarehouseConfig) -> UUID:
    async with alchemy.get_session() as session:
        session.info[TENANT_BYPASS_SESSION_KEY] = True
        team = await session.scalar(select(m.Team).where(m.Team.slug == config.team_slug))
        if team is None:
            team = m.Team(id=config.team_id, name=config.team_name, slug=config.team_slug, is_active=True)
            session.add(team)
        else:
            team.name = config.team_name
            team.is_active = True
        await session.commit()
        return team.id


async def _configure_warehouse(config: WarehouseConfig, team_id: UUID, *, apply: bool) -> dict[str, object]:
    async with alchemy.get_session() as session:
        session.info[TENANT_ID_SESSION_KEY] = team_id
        enterprise = await session.scalar(select(m.EnterpriseInfo).order_by(m.EnterpriseInfo.id).limit(1))
        if enterprise is None:
            enterprise = m.EnterpriseInfo()
            session.add(enterprise)
        enterprise.name = config.team_name
        enterprise.belong_unit = OWNER_UNIT
        enterprise.location = config.location
        enterprise.other_info = {
            **(enterprise.other_info or {}),
            "bigscreen": {
                "overview_focus": "sampling",
                "monitor_focus": "sampling",
                "carbon_focus": "inventory",
            },
        }

        sectors: dict[str, m.MonitorSector] = {}
        root = await session.scalar(select(m.MonitorSector).where(m.MonitorSector.code == config.root_sector_code))
        if root is None:
            root = m.MonitorSector(code=config.root_sector_code)
            session.add(root)
            await session.flush()
        root.name = config.team_name
        root.area_type = "site"
        root.path = f"/{config.root_sector_code}"
        root.level = 0
        root.sort_index = 0
        root.location_desc = config.location
        root.is_enable = True
        sectors[root.code] = root
        for sort_index, (code, name) in enumerate(config.sectors, start=1):
            sector = await session.scalar(select(m.MonitorSector).where(m.MonitorSector.code == code))
            if sector is None:
                sector = m.MonitorSector(code=code)
                session.add(sector)
            sector.name = name
            sector.parent_id = root.id
            sector.area_type = "functional"
            sector.path = f"/{config.root_sector_code}/{code}"
            sector.level = 1
            sector.sort_index = sort_index
            sector.is_enable = True
            sectors[code] = sector
        await session.flush()
        if config.team_slug == "taixing-keneng-warehouse":
            obsolete_incoming = await session.scalar(
                select(m.MonitorSector).where(m.MonitorSector.code == "TX-INCOMING")
            )
            if obsolete_incoming is not None:
                obsolete_incoming.is_enable = False
                obsolete_incoming.remark = "电气总进线不是物理区域；总表已归到仓库根节点。"

        source = await session.scalar(select(m.MqttDataSource).where(m.MqttDataSource.code == config.source_code))
        if source is None:
            source = m.MqttDataSource(code=config.source_code)
            session.add(source)
        source.name = config.source_name
        source.broker_host = BROKER_HOST
        source.broker_port = BROKER_PORT
        source.username_env = USERNAME_ENV
        source.password_env = PASSWORD_ENV
        source.client_id = config.client_id
        source.tls_enabled = False
        source.enabled = True
        await session.flush()

        subscription = await session.scalar(
            select(m.MqttSubscription).where(
                m.MqttSubscription.source_id == source.id,
                m.MqttSubscription.topic_filter == config.topic,
            )
        )
        if subscription is None:
            subscription = m.MqttSubscription(source_id=source.id, topic_filter=config.topic)
            session.add(subscription)
        subscription.parser_code = "szscada_metering_v2"
        subscription.contract_version = "v2"
        subscription.qos = 1
        subscription.expected_interval_seconds = 300
        subscription.enabled = True
        await session.flush()

        equipment_rows: list[m.MonitorEquipment] = []
        binding_rows: list[m.MqttDeviceBinding] = []
        boundary_rows: list[m.MeasurementBoundary] = []
        system_binding_rows: list[m.EnergyUseSystemBinding] = []
        for sort_index, meter in enumerate(config.meters, start=1):
            sector = sectors[meter.sector_code]
            equipment = await session.scalar(
                select(m.MonitorEquipment).where(m.MonitorEquipment.code == meter.equipment_code)
            )
            if equipment is None:
                equipment = m.MonitorEquipment(code=meter.equipment_code)
                session.add(equipment)
            equipment.name = meter.equipment_name
            equipment.external_device_id = meter.address
            equipment.asset_code = meter.address
            equipment.sector_id = sector.id
            equipment.category = 0
            equipment.owner_unit = OWNER_UNIT
            equipment.warehouse_name = config.team_name
            equipment.warehouse_code = config.warehouse_code
            equipment.energy_type = "purchased_electricity"
            equipment.data_acquisition_method = "mqtt"
            equipment.protocol = "mqtt"
            equipment.supplier = "szscada"
            equipment.status = 0
            equipment.location = sector.name
            equipment.sort_index = sort_index
            equipment.is_enable = True
            await session.flush()
            equipment_rows.append(equipment)

            use_system = await session.scalar(
                select(m.EnergyUseSystem).where(m.EnergyUseSystem.code == meter.use_system_code)
            )
            if use_system is None:
                use_system = m.EnergyUseSystem(code=meter.use_system_code, name=meter.use_system_name)
                session.add(use_system)
            use_system.name = meter.use_system_name
            use_system.system_type = "electricity_end_use"
            use_system.is_enabled = True
            await session.flush()

            system_binding = await session.scalar(
                select(m.EnergyUseSystemBinding).where(
                    m.EnergyUseSystemBinding.system_code == meter.use_system_code,
                    m.EnergyUseSystemBinding.equipment_id == equipment.id,
                )
            )
            if system_binding is None:
                system_binding = m.EnergyUseSystemBinding(
                    system_code=meter.use_system_code,
                    equipment_id=equipment.id,
                )
                session.add(system_binding)
            system_binding.equipment_code = equipment.code
            system_binding.equipment_name = equipment.name
            system_binding.sector_id = sector.id
            system_binding.area_id = sector.code
            system_binding.area_name = sector.name
            system_binding.confidence_level = "confirmed" if config.team_slug.startswith("taixing") else "medium"
            system_binding.is_primary = True
            system_binding.remark = "依据现场网关设备名称建立；设备用途和覆盖范围应随现场验收更新。"
            system_binding_rows.append(system_binding)

            business_equipment = None
            if meter.business_equipment_code and meter.business_equipment_name:
                business_equipment = await session.scalar(
                    select(m.MonitorEquipment).where(m.MonitorEquipment.code == meter.business_equipment_code)
                )
                if business_equipment is None:
                    business_equipment = m.MonitorEquipment(code=meter.business_equipment_code)
                    session.add(business_equipment)
                business_equipment.name = meter.business_equipment_name
                business_equipment.sector_id = sector.id
                business_equipment.owner_unit = OWNER_UNIT
                business_equipment.warehouse_name = config.team_name
                business_equipment.warehouse_code = config.warehouse_code
                business_equipment.energy_type = "electricity"
                business_equipment.location = sector.name
                business_equipment.sort_index = 100 + sort_index
                business_equipment.is_enable = True
                await session.flush()

            boundary_code = f"MB-{config.warehouse_code}-{meter.address}"
            boundary = await session.scalar(
                select(m.MeasurementBoundary).where(m.MeasurementBoundary.code == boundary_code)
            )
            if boundary is None:
                boundary = m.MeasurementBoundary(code=boundary_code, name=f"{meter.equipment_name}计量边界")
                session.add(boundary)
            boundary.name = f"{meter.equipment_name}计量边界"
            boundary.boundary_type = meter.boundary_type
            boundary.meter_equipment_id = equipment.id
            boundary.sector_id = sector.id
            boundary.use_system_code = meter.use_system_code
            boundary.energy_direction = "import"
            boundary.include_in_scope2 = meter.include_in_scope2
            boundary.status = "active"
            boundary.mapping_version = "taizhou-metering-v1"
            boundary.source_name = "SZSCADA addressed-meter configuration"
            boundary.confidence_level = "confirmed" if config.team_slug.startswith("taixing") else "medium"
            boundary.remark = (
                "场站总进线用于仓库总电量和范围二核算。"
                if meter.boundary_type == "site_import"
                else "分项回路用于区域和设备用电分配，不与场站总表重复计入范围二。"
                if not meter.include_in_scope2
                else "当前未配置场站总表，按已知互斥回路合计；需使用电费单核对覆盖范围。"
            )
            await session.flush()
            boundary_rows.append(boundary)

            member_code = business_equipment.code if business_equipment is not None else sector.code
            boundary_member = await session.scalar(
                select(m.MeasurementBoundaryMember).where(
                    m.MeasurementBoundaryMember.boundary_id == boundary.id,
                    m.MeasurementBoundaryMember.member_code == member_code,
                )
            )
            if boundary_member is None:
                boundary_member = m.MeasurementBoundaryMember(
                    boundary_id=boundary.id,
                    member_code=member_code,
                )
                session.add(boundary_member)
            boundary_member.member_type = "equipment_group" if business_equipment is not None else "sector"
            boundary_member.sector_id = sector.id
            boundary_member.equipment_id = business_equipment.id if business_equipment is not None else None
            boundary_member.member_role = "covered"
            boundary_member.allocation_weight = Decimal(1)
            boundary_member.confirmation_status = "confirmed"
            boundary_member.source_name = "现场网关设备清单"

            binding = await session.scalar(
                select(m.MqttDeviceBinding).where(
                    m.MqttDeviceBinding.subscription_id == subscription.id,
                    m.MqttDeviceBinding.gateway_key == config.gateway_key,
                    m.MqttDeviceBinding.meter_key == meter.address,
                )
            )
            if binding is None:
                binding = m.MqttDeviceBinding(
                    subscription_id=subscription.id,
                    gateway_key=config.gateway_key,
                    meter_key=meter.address,
                )
                session.add(binding)
            binding.selector_name_pattern = f"^{meter.source_name}$"
            binding.equipment_id = equipment.id
            binding.external_device_id = meter.address
            binding.temporary_address = meter.address
            binding.identity_status = "confirmed"
            binding.scaling_mode = "upstream_scaled"
            binding.multiplier = Decimal(1)
            await session.flush()
            binding_rows.append(binding)

            for source_tag, point_code in SZSCADA_TAG_TO_POINT.items():
                spec = point_spec(point_code)
                mapping = await session.scalar(
                    select(m.MqttPointMapping).where(
                        m.MqttPointMapping.binding_id == binding.id,
                        m.MqttPointMapping.source_tag == source_tag,
                        m.MqttPointMapping.mapping_version == "v2",
                    )
                )
                if mapping is None:
                    mapping = m.MqttPointMapping(
                        binding_id=binding.id,
                        source_tag=source_tag,
                        mapping_version="v2",
                    )
                    session.add(mapping)
                mapping.source_name_suffix = spec.point_name
                mapping.point_code = spec.point_code
                mapping.point_name = spec.point_name
                mapping.unit = spec.unit
                mapping.multiplier = Decimal(1)
                mapping.enabled = True

                device_point = await session.scalar(
                    select(m.DevicePoint).where(
                        m.DevicePoint.device_id == equipment.id,
                        m.DevicePoint.point_code == spec.point_code,
                    )
                )
                if device_point is None:
                    device_point = m.DevicePoint(device_id=equipment.id, point_code=spec.point_code)
                    session.add(device_point)
                device_point.point_name = spec.point_name
                device_point.unit = spec.unit
                device_point.value_type = "float"
                device_point.source_field = source_tag
                device_point.sampling_interval_seconds = 300
                device_point.is_enabled = True
                device_point.is_alarm_enabled = False

        await session.flush()
        summary = {
            "team_id": str(team_id),
            "team_name": config.team_name,
            "topic": config.topic,
            "gateway_key": config.gateway_key,
            "source_id": source.id,
            "subscription_id": subscription.id,
            "equipment_ids": [row.id for row in equipment_rows],
            "binding_ids": [row.id for row in binding_rows],
            "meter_count": len(equipment_rows),
            "mapping_count": len(binding_rows) * len(SZSCADA_TAG_TO_POINT),
            "boundary_count": len(boundary_rows),
            "system_binding_count": len(system_binding_rows),
        }
        if apply:
            await session.commit()
        else:
            await session.rollback()
        return summary


async def main(*, apply: bool) -> None:
    results = []
    for config in WAREHOUSES:
        if apply:
            team_id = await _ensure_team(config)
        else:
            async with alchemy.get_session() as session:
                session.info[TENANT_BYPASS_SESSION_KEY] = True
                existing = await session.scalar(select(m.Team).where(m.Team.slug == config.team_slug))
                if existing is None:
                    results.append(
                        {
                            "team_id": str(config.team_id),
                            "team_name": config.team_name,
                            "topic": config.topic,
                            "gateway_key": config.gateway_key,
                            "source_id": None,
                            "subscription_id": None,
                            "equipment_ids": [],
                            "binding_ids": [],
                            "meter_count": len(config.meters),
                            "mapping_count": len(config.meters) * len(SZSCADA_TAG_TO_POINT),
                        }
                    )
                    continue
                team_id = existing.id
        results.append(await _configure_warehouse(config, team_id, apply=apply))
    print(json.dumps({"apply": apply, "warehouses": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(apply=parser.parse_args().apply))
