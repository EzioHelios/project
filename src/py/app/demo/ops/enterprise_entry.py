"""Replay anonymized enterprise inputs through the existing application services.

The CSV files are the source of truth. Quantities and prices are synthetic demo
assumptions, not customer records. This module never opens its own connection.
"""

from __future__ import annotations

# ruff: noqa: RUF001 - Chinese business labels match the downloadable inputs.
import csv
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select

from app.db import models as m
from app.demo.ops.entry_boundary import ensure_entry_boundary, entry_boundary_readiness
from app.domain.energy.usecases.imports import EnergyDatasetImportUseCase
from app.domain.energy.usecases.interval_facts import _normalize_energy_interval_fact_data
from app.domain.factor_library.schemas import CalculationFactorWriteRequest
from app.domain.factor_library.usecases.factors import CalculationFactorMaintenance
from app.domain.ghg_inventory.usecases.allocations import ReplaceActivityAllocations
from app.domain.ghg_inventory.usecases.calculation import RunInventoryCalculation
from app.domain.ghg_inventory.usecases.maintenance import GhgInventoryMaintenance, _area_within
from app.lib.demo_tenancy import require_demo_tenant
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

SOURCE_SYSTEM = "woheng_enterprise_entry_v1"
SOURCE_NAME = "沃衡工厂月结与维修台账（合成演示数据）"
SAMPLE_ROOT = Path(__file__).resolve().parents[1] / "samples" / "enterprise_entry"
CITY_NAMES = {"TZ": "泰州", "HZ": "湖州"}
ENERGY_TYPES = {
    "购入电力": ("purchased_electricity", "2.1", "kWh"),
    "天然气": ("natural_gas", "1.1", "m3"),
    "柴油": ("diesel", "1.2", "L"),
}


@dataclass(frozen=True, slots=True)
class EntryCase:
    record_code: str
    name: str
    area_code: str
    equipment_code: str | None
    start: date
    end: date
    category: str
    amount: Decimal
    unit: str
    payload: dict[str, Any]
    energy_type: str | None = None
    cost: Decimal | None = None


def sample_rows(city: str, kind: str) -> list[dict[str, str]]:
    """Read the actual downloadable input; blank values remain distinct from zero."""
    with (SAMPLE_ROOT / f"{CITY_NAMES[city]}基地_{kind}.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_cases(city: str) -> list[EntryCase]:
    """Normalize business inputs, preserving dates, quantities and source references."""
    cases: list[EntryCase] = []
    provenance = {
        "source_name": SOURCE_NAME,
        "standard_code": "DEMO-ASSUMPTION-20261115",
        "confidence_level": "demo",
        "valid_from": "2026-10-01",
    }
    for row in sample_rows(city, "能源月结"):
        energy_type, category, unit = ENERGY_TYPES[row["数据种类"]]
        if row["单位"] != unit:
            msg = f"{row['记录编号']} 单位必须为 {unit}"
            raise ValueError(msg)
        if row["设备编号"] == "GENSET-01":
            category = "1.1"
        payload = {
            **provenance,
            "iso_category_code": category,
            "business_record": row["业务记录"],
            "energy_type_code": energy_type,
            "facility_or_device": row["对象名称"],
            "vehicle_or_machine": row["对象名称"],
            "fuel_or_material": row["数据种类"],
            "energy_type": "electricity",
            "supplier_name": "地区供电公司",
            "meter_point": "GAS-METER-01" if energy_type == "natural_gas" else row["设备编号"],
            "scope2_method": "location" if category == "2.1" else "not_applicable",
        }
        cases.append(
            EntryCase(
                row["记录编号"],
                row["对象名称"],
                row["区域编号"],
                row["设备编号"],
                date.fromisoformat(row["开始日期"]),
                date.fromisoformat(row["结束日期"]),
                category,
                Decimal(row["数量"]),
                unit,
                payload,
                energy_type,
                Decimal(row["费用（元）"]),
            )
        )
    for row in sample_rows(city, "制冷剂维修"):
        # Maintenance top-up is an explicit demo leakage assumption. Recovery is
        # retained in the event but is not turned into a positive emission.
        payload = {
            **provenance,
            "gas_code": row["制冷剂"],
            "facility_or_device": row["设备名称"],
            "charges": row["实际补充量"],
            "recovery": row["实际回收量"],
            "rated_charge_kg": row["额定充注量"],
            "maintenance_record": row["维修内容"],
            "emission_assumption": "维修补充量代表已发生泄漏；回收不计正排放",
        }
        event_date = date.fromisoformat(row["维修日期"])
        cases.append(
            EntryCase(
                row["工单编号"],
                row["设备名称"] + "冷媒维护",
                row["区域编号"],
                row["设备编号"],
                event_date,
                event_date,
                "1.4",
                Decimal(row["实际补充量"]),
                row["单位"],
                payload,
            )
        )
    for row in sample_rows(city, "通勤运输"):
        commute = row["活动名称"] == "员工自驾通勤"
        distance = Decimal(row["单程距离（km）"])
        if commute:
            amount = distance * Decimal(row["出勤天数"]) * Decimal(row["每日单程次数"]) * Decimal(row["人数"])
        else:
            amount = distance * Decimal(row["货物质量（t）"]) * Decimal(row["运输次数"])
        payload = {
            **provenance,
            "transport_direction": "commute" if commute else "upstream",
            "transport_mode": row["运输方式"],
            "distance_km": str(distance),
            "passenger_count": row["人数"],
            "cargo_ton": row["货物质量（t）"],
            "carrier": row["承运商"],
            "work_days": row["出勤天数"],
            "daily_trips": row["每日单程次数"],
            "trips": row["运输次数"],
            "origin": row["起点"],
            "destination": row["终点"],
        }
        cases.append(
            EntryCase(
                row["记录编号"],
                row["活动名称"],
                "OFFICE" if commute else "SORTING",
                None,
                date.fromisoformat(row["开始日期"]),
                date.fromisoformat(row["结束日期"]),
                "3.3" if commute else "3.1",
                amount,
                "人·km" if commute else "t·km",
                payload,
            )
        )
    return cases


def energy_input(case: EntryCase, *, area: m.MonitorSector, equipment: m.MonitorEquipment) -> dict[str, Any]:
    """Build the same dataset command used by the energy input page."""
    return {
        "source_system": SOURCE_SYSTEM,
        "source_record_id": case.record_code,
        "energy_type_code": case.energy_type,
        "equipment_code": equipment.code,
        "equipment_name": equipment.name,
        "area_id": str(area.id),
        "area_name": area.name,
        "granularity": "month",
        "period_start": case.start.isoformat(),
        "period_end": f"{case.end.isoformat()}T23:59:59",
        "amount": str(case.amount),
        "unit": case.unit,
        "cost_cny": str(case.cost),
        "data_quality": "imported",
        "remark": case.payload["business_record"],
    }


async def reject_protected_entry(session: AsyncSession, *, inventory: str) -> None:
    """Fail before any mutation when a partial run already protects its activities."""
    activities = list(
        (
            await session.scalars(select(m.GhgActivityRecord).where(m.GhgActivityRecord.inventory_code == inventory))
        ).all()
    )
    for activity in activities:
        referenced = await session.scalar(
            select(m.GhgCalculationResult.id).where(m.GhgCalculationResult.activity_id == activity.id).limit(1)
        )
        assigned = await session.scalar(
            select(m.GhgParameterAssignment.id).where(m.GhgParameterAssignment.activity_id == activity.id).limit(1)
        )
        if activity.status in {"locked", "archived"} or referenced is not None or assigned is not None:
            msg = f"案例活动 {activity.record_code} 已锁定、归档或被核算引用，保留现有记录供人工处理"
            raise ValueError(msg)


async def configure_energy_sources(
    session: AsyncSession,
    *,
    maintenance: GhgInventoryMaintenance,
    cases: list[EntryCase],
    inventory: str,
    period: m.ReportingPeriod,
    boundary: m.OrganizationBoundary,
    organization: m.ReportingOrganization,
    areas: dict[str, m.MonitorSector],
    equipment: dict[str, m.MonitorEquipment],
) -> None:
    """Configure business emission sources before generation, preserving existing choices."""
    sources = list(
        (
            await session.scalars(
                select(m.GhgEmissionSource).where(
                    m.GhgEmissionSource.inventory_code == inventory,
                    m.GhgEmissionSource.organization_code == organization.code,
                    m.GhgEmissionSource.status == "active",
                )
            )
        ).all()
    )
    for case in cases:
        device = equipment[case.equipment_code]
        area = areas[case.area_code]
        categories = {"2.1"} if case.category == "2.1" else {"1.1", "1.2"}
        matches = [
            source
            for source in sources
            if source.iso_category_code in categories
            and source.reporting_period_id in (None, period.id)
            and (source.valid_from is None or source.valid_from <= case.start)
            and (source.valid_to is None or source.valid_to >= case.end)
            and (
                source.default_equipment_id == device.id
                or (
                    source.default_equipment_id is None
                    and (
                        (
                            source.default_area_id is not None
                            and _area_within(area, source.default_area_id, {item.id: item for item in areas.values()})
                        )
                        or source.facility_code == area.code
                    )
                )
            )
        ]
        if matches:
            continue
        source = await maintenance.create_source(
            {
                "inventory_code": inventory,
                "reporting_period_id": period.id,
                "organization_boundary_id": boundary.id,
                "organization_code": organization.code,
                "facility_code": case.area_code,
                "source_code": f"ENTRY-{case.equipment_code}",
                "source_name": case.name,
                "iso_category_code": case.category,
                "default_area_id": area.id,
                "default_equipment_id": device.id,
                "origin_kind": "internal",
                "source_system": SOURCE_SYSTEM,
                "source_payload": dict(case.payload),
            }
        )
        sources.append(source)


async def maintain_energy_inputs(session: AsyncSession, *, rows: list[dict[str, Any]]) -> None:
    """Update owned, unfrozen inputs with the UI normalization contract; import only missing rows."""
    existing = {
        fact.source_record_id: fact
        for fact in (
            await session.scalars(
                select(m.EnergyIntervalFact).where(m.EnergyIntervalFact.source_system == SOURCE_SYSTEM)
            )
        ).all()
    }
    pending = []
    for row in rows:
        fact = existing.get(row["source_record_id"])
        if fact is None:
            pending.append(row)
            continue
        if not fact.is_current:
            msg = f"{fact.source_record_id} 已停用，保留现有记录供人工处理"
            raise ValueError(msg)
        normalized = await _normalize_energy_interval_fact_data(session, row)
        for field, value in normalized.items():
            setattr(fact, field, value)
        # Retire a previous demo version's carbon-classification hint. Source
        # configuration now determines stationary/mobile combustion, as in UI.
        if "iso_category_code" in (fact.source_snapshot or {}):
            fact.source_snapshot = {
                key: value for key, value in fact.source_snapshot.items() if key != "iso_category_code"
            }
    await session.flush()
    if pending:
        imported = await EnergyDatasetImportUseCase(session).import_rows(
            dataset="energy_interval_facts",
            rows=pending,
            source_name=SOURCE_NAME,
        )
        if imported.errors or imported.imported_count != len(pending):
            msg = f"演示能源导入失败：{imported.errors}"
            raise ValueError(msg)
    await session.commit()


async def seed_enterprise_entry(session: AsyncSession, *, city: str) -> dict[str, Any]:  # noqa: PLR0915
    """Replay one complete month without deriving energy from carbon activities."""
    await require_demo_tenant(session)
    cases = load_cases(city)
    inventory = f"WOHENG-{city}-ENTRY-202610"
    completed = await session.scalar(
        select(m.GhgCalculationRun.id)
        .where(
            m.GhgCalculationRun.inventory_code == inventory,
            m.GhgCalculationRun.status == "completed",
        )
        .limit(1)
    )
    if completed is not None:
        validation = await validate_enterprise_entry(session, city=city)
        if not validation["passed"]:
            msg = f"已核算案例与原表不一致，保留现有记录供人工处理：{validation['errors']}"
            raise ValueError(msg)
        return {**validation, "reused": True}
    await reject_protected_entry(session, inventory=inventory)
    organization = await session.scalar(select(m.ReportingOrganization).order_by(m.ReportingOrganization.id))
    if organization is None:
        msg = "演示工厂缺少报告主体"
        raise ValueError(msg)
    inventory = f"WOHENG-{city}-ENTRY-202610"
    period = await session.scalar(select(m.ReportingPeriod).where(m.ReportingPeriod.code == inventory))
    if period is None:
        period = m.ReportingPeriod(
            reporting_org_id=organization.id,
            code=inventory,
            name=f"{CITY_NAMES[city]}基地2026年10月月结",
            period_type="monthly",
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            status="active",
            source_name=SOURCE_NAME,
            standard_code="DEMO-ASSUMPTION-20261115",
        )
        session.add(period)
    await session.flush()
    areas = {row.code: row for row in (await session.scalars(select(m.MonitorSector))).all()}
    equipment = {row.code: row for row in (await session.scalars(select(m.MonitorEquipment))).all()}
    boundary = await ensure_entry_boundary(session, city=city, period=period, cases=cases)
    energy_cases = [case for case in cases if case.energy_type]
    maintenance = GhgInventoryMaintenance(session)
    await configure_energy_sources(
        session,
        maintenance=maintenance,
        cases=energy_cases,
        inventory=inventory,
        period=period,
        boundary=boundary,
        organization=organization,
        areas=areas,
        equipment=equipment,
    )
    rows = [
        energy_input(case, area=areas[case.area_code], equipment=equipment[case.equipment_code])
        for case in energy_cases
    ]
    await maintain_energy_inputs(session, rows=rows)
    facts = {
        row.source_record_id: row
        for row in (
            await session.scalars(
                select(m.EnergyIntervalFact).where(
                    m.EnergyIntervalFact.source_system == SOURCE_SYSTEM,
                )
            )
        ).all()
    }
    generation = await maintenance.generate_activities(
        inventory_code=inventory,
        reporting_period_id=period.id,
        organization_boundary_id=boundary.id,
        source_types=["energy_electricity", "energy_natural_gas", "energy_diesel"],
    )
    if generation["failedCount"] or generation["skippedCount"]:
        msg = f"演示能源活动生成未完成：{generation['messages']}"
        raise ValueError(msg)
    generated = list(
        (
            await session.scalars(
                select(m.GhgActivityRecord).where(
                    m.GhgActivityRecord.inventory_code == inventory,
                    m.GhgActivityRecord.source_record_type == "energy_interval_fact",
                )
            )
        ).all()
    )
    generated_by_case, link_errors = index_case_activities(list(facts.values()), generated)
    if link_errors:
        raise ValueError("；".join(link_errors))
    for case in cases:
        fact = facts.get(case.record_code)
        generated_activity = generated_by_case.get(case.record_code) if fact else None
        if fact and generated_activity is None:
            msg = f"{case.record_code} 未生成组织碳活动"
            raise ValueError(msg)
        if generated_activity and energy_activity_fact_ids(generated_activity) != {fact.id}:
            msg = f"{case.record_code} 与其他能源事实共同归集，保留生成结果供人工核对"
            raise ValueError(msg)
        if generated_activity and generated_activity.iso_category_code != case.category:
            msg = f"{case.record_code} 的现有排放源分类与案例不一致，保留现有配置供人工处理"
            raise ValueError(msg)
        prior_activity = await session.scalar(
            select(m.GhgActivityRecord).where(
                m.GhgActivityRecord.inventory_code == inventory,
                m.GhgActivityRecord.record_code == case.record_code,
            )
        )
        source_code = (
            generated_activity.source_code
            if generated_activity
            else prior_activity.source_code
            if prior_activity
            else f"ENTRY-{case.equipment_code or case.category.replace('.', '-')}"
        )
        source = await session.scalar(
            select(m.GhgEmissionSource).where(
                m.GhgEmissionSource.inventory_code == inventory,
                m.GhgEmissionSource.source_code == source_code,
            )
        )
        source_payload = {
            "inventory_code": inventory,
            "reporting_period_id": period.id,
            "organization_boundary_id": boundary.id,
            "organization_code": organization.code,
            "facility_code": case.area_code,
            "source_code": source_code,
            "source_name": case.name,
            "iso_category_code": case.category,
            "default_area_id": areas[case.area_code].id,
            "default_equipment_id": equipment[case.equipment_code].id if case.equipment_code else None,
            "origin_kind": "external" if case.category.startswith("3.") else "internal",
            "source_system": SOURCE_SYSTEM,
            "source_payload": case.payload,
        }
        if source is None:
            await maintenance.create_source(source_payload)
        fact = facts.get(case.record_code)
        payload = {
            "inventory_code": inventory,
            "reporting_period_id": period.id,
            "organization_boundary_id": boundary.id,
            "organization_code": organization.code,
            "facility_code": case.area_code,
            "source_code": source_code,
            "record_code": generated_activity.record_code if generated_activity else case.record_code,
            "activity_code": case.energy_type or ("maintenance_event" if case.category == "1.4" else "business_ledger"),
            "activity_name": case.name,
            "iso_category_code": case.category,
            "period_start": fact.period_start.date().isoformat() if fact else case.start.isoformat(),
            "period_end": fact.period_end.date().isoformat() if fact else case.end.isoformat(),
            "activity_amount": str(fact.amount if fact else case.amount),
            "activity_unit": fact.unit if fact else case.unit,
            "data_source_type": "ledger",
            "measurement_method": "能源月结事实" if fact else "维修工单" if case.category == "1.4" else "经营台账",
            "source_system": prior_activity.source_system if prior_activity and not fact else SOURCE_SYSTEM,
            "source_record_type": "energy_interval_fact"
            if fact
            else prior_activity.source_record_type
            if prior_activity
            else "business_ledger",
            "source_record_id": fact.id if fact else prior_activity.source_record_id if prior_activity else None,
            "source_payload": {
                **(dict(generated_activity.source_payload or {}) if generated_activity else {}),
                **(dict(prior_activity.source_payload or {}) if prior_activity else {}),
                **dict(case.payload),
                **({"source_fact_ids": [fact.id]} if fact else {}),
            },
            "parameter_set_code": (generated_activity.parameter_set_code if generated_activity else None)
            or (prior_activity.parameter_set_code if prior_activity else None)
            or f"{case.record_code}-PARAM",
            "status": "approved",
        }
        existing = await session.scalar(
            select(m.GhgActivityRecord).where(
                m.GhgActivityRecord.inventory_code == inventory,
                m.GhgActivityRecord.record_code == payload["record_code"],
            )
        )
        method, _parameters = calculation_parameters(case)
        payload["source_payload"].setdefault("method_code", method)
        if existing is None:
            activity = await maintenance.create_activity(payload)
        else:
            activity = await maintenance.update_activity(payload["record_code"], payload)
        existing_parameter = await session.scalar(
            select(m.GhgParameterValue.id)
            .where(
                m.GhgParameterValue.value_code.startswith(f"{inventory}:{activity.parameter_set_code}:"),
                m.GhgParameterValue.status == "active",
            )
            .limit(1)
        )
        if not activity.source_payload.get("factor_id") and existing_parameter is None:
            await apply_demo_factor(session, activity=activity, case=case)
        if generated_activity is not None:
            continue
        await ReplaceActivityAllocations(session).execute(
            inventory_code=inventory,
            record_code=activity.record_code,
            allocations=[
                {
                    "area_id": areas[case.area_code].id,
                    "equipment_id": equipment[case.equipment_code].id if case.equipment_code else None,
                    "allocation_role": "energy_consumption"
                    if case.category == "2.1"
                    else "responsibility"
                    if case.category.startswith("3.")
                    else "physical_origin",
                    "allocation_ratio": "1",
                    "source_kind": "manual",
                }
            ],
        )
    await session.commit()
    await RunInventoryCalculation(session).execute(
        inventory_code=inventory,
        reporting_period_id=period.id,
        reporting_org_id=organization.id,
        organization_boundary_id=boundary.id,
        reporting_profile_code="CORPORATE_ISO14064_GHGP",
    )
    await session.commit()
    validation = await validate_enterprise_entry(session, city=city)
    if not validation["passed"]:
        msg = f"演示案例语义校验失败：{validation['errors']}"
        raise ValueError(msg)
    return validation


def energy_activity_fact_ids(activity: Any) -> set[int]:
    """Resolve the public generation contract, never demo payload tags or names."""
    if activity.source_record_type != "energy_interval_fact":
        return set()
    payload_ids = (activity.source_payload or {}).get("source_fact_ids")
    if payload_ids is not None and not isinstance(payload_ids, list):
        return set()
    ids = list(payload_ids or [])
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in ids):
        return set()
    if len(ids) != len(set(ids)):
        return set()
    if activity.source_record_id is not None:
        ids.append(activity.source_record_id)
    # IDs are database integer primary keys, not the source's business codes.
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in ids):
        return set()
    return set(ids)


def index_case_activities(facts: list[Any], activities: list[Any]) -> tuple[dict[str, Any], list[str]]:
    """Join single-fact cases by typed FK; business-ledger cases retain their record code."""
    fact_codes = {row.id: row.source_record_id for row in facts}
    indexed: dict[str, Any] = {}
    errors: list[str] = []
    for activity in activities:
        if activity.source_record_type == "energy_interval_fact":
            ids = energy_activity_fact_ids(activity)
            if len(ids) != 1 or not ids <= fact_codes.keys():
                errors.append(f"{activity.record_code} 未关联唯一案例能源事实，需核对月度归集来源集合")
                continue
            code = fact_codes[next(iter(ids))]
        else:
            code = activity.record_code
        if code in indexed:
            errors.append(f"{code} 存在重复的案例活动关联")
            continue
        indexed[code] = activity
    return indexed, errors


def compare_cases(cases: list[EntryCase], facts: list[Any], activities: list[Any]) -> list[str]:
    """Check values and provenance, including duplicate records and missing zeroes."""
    errors: list[str] = []
    fact_map = {row.source_record_id: row for row in facts}
    activity_map, link_errors = index_case_activities(facts, activities)
    errors.extend(link_errors)
    if len(fact_map) != len(facts) or len(activity_map) != len(activities):
        errors.append("存在重复的案例事实或活动")
    expected_fact_codes = {case.record_code for case in cases if case.energy_type}
    if set(fact_map) != expected_fact_codes:
        errors.append("能源事实范围与原始输入不一致")
    if set(activity_map) != {case.record_code for case in cases}:
        errors.append("活动范围与原始输入不一致")
    for case in cases:
        activity = activity_map.get(case.record_code)
        if activity is None:
            errors.append(f"{case.record_code} 缺少活动")
            continue
        if (
            activity.activity_amount,
            activity.activity_unit,
            activity.period_start,
            activity.period_end,
            activity.iso_category_code,
            activity.facility_code,
        ) != (
            case.amount,
            case.unit,
            case.start,
            case.end,
            case.category,
            case.area_code,
        ):
            errors.append(f"{case.record_code} 活动数量、单位、期间或分类不一致")
        if case.energy_type:
            fact = fact_map.get(case.record_code)
            if fact is None:
                errors.append(f"{case.record_code} 缺少能源事实")
                continue
            if (
                fact.amount,
                fact.unit,
                fact.energy_type_code,
                fact.equipment_code,
                fact.cost_cny,
                fact.period_start.date(),
                fact.period_end.date(),
            ) != (
                case.amount,
                case.unit,
                case.energy_type,
                case.equipment_code,
                case.cost,
                case.start,
                case.end,
            ):
                errors.append(f"{case.record_code} 能源数量、费用、设备或期间不一致")
            if energy_activity_fact_ids(activity) != {fact.id}:
                errors.append(f"{case.record_code} 活动未关联能源事实")
        elif case.category == "1.4":
            for key in ("gas_code", "charges", "recovery", "rated_charge_kg"):
                if activity.source_payload.get(key) != case.payload[key]:
                    errors.append(f"{case.record_code} 制冷剂事件字段 {key} 不一致")  # noqa: PERF401
    return errors


async def validate_enterprise_entry(session: AsyncSession, *, city: str) -> dict[str, Any]:
    """Read-only semantic acceptance of the dedicated input cases."""
    facts = list(
        (
            await session.scalars(
                select(m.EnergyIntervalFact).where(
                    m.EnergyIntervalFact.source_system == SOURCE_SYSTEM,
                    m.EnergyIntervalFact.is_current.is_(True),
                )
            )
        ).all()
    )
    activities = list(
        (
            await session.scalars(
                select(m.GhgActivityRecord).where(
                    m.GhgActivityRecord.inventory_code == f"WOHENG-{city}-ENTRY-202610",
                    m.GhgActivityRecord.status == "approved",
                )
            )
        ).all()
    )
    cases = load_cases(city)
    errors = compare_cases(cases, facts, activities)
    boundary_validation = await entry_boundary_readiness(session, city=city, cases=cases, activities=activities)
    errors.extend(boundary_validation["errors"])
    # Repeat installation must still notice other monthly sources. Never scope
    # the production generator to our source_system to conceal a real overlap.
    existing_monthly = list(
        (
            await session.scalars(
                select(m.EnergyIntervalFact).where(
                    m.EnergyIntervalFact.is_current.is_(True),
                    m.EnergyIntervalFact.granularity == "month",
                    m.EnergyIntervalFact.period_start >= datetime.combine(date(2026, 10, 1), time.min),
                    m.EnergyIntervalFact.period_end <= datetime.combine(date(2026, 10, 31), time.max),
                    m.EnergyIntervalFact.equipment_code.in_(
                        [case.equipment_code for case in cases if case.energy_type]
                    ),
                )
            )
        ).all()
    )
    own_ids = {fact.id for fact in facts}
    if any(row.id not in own_ids for row in existing_monthly):
        errors.append("案例设备本月存在其他来源的月度能源事实，请先核对重叠记录")
    run = await session.scalar(
        select(m.GhgCalculationRun)
        .where(
            m.GhgCalculationRun.inventory_code == f"WOHENG-{city}-ENTRY-202610",
        )
        .order_by(m.GhgCalculationRun.id.desc())
    )
    if run is None or run.status != "completed":
        errors.append("案例缺少已完成的核算结果")
    else:
        from app.domain.ghg_inventory.domain.calculation import calculate

        results = {
            row.activity_id: row
            for row in (
                await session.scalars(
                    select(m.GhgCalculationResult).where(
                        m.GhgCalculationResult.run_id == run.id,
                    )
                )
            ).all()
        }
        by_input, _link_errors = index_case_activities(facts, activities)
        for case in cases:
            activity = by_input.get(case.record_code)
            result = results.get(activity.id) if activity else None
            method, params = calculation_parameters(case)
            expected = calculate(
                method,
                case.amount,
                {key: value for key, (value, _) in params.items()},
                {**case.payload, "gas_code": case.payload.get("gas_code", "CO2e")},
            )
            if result is None or abs(result.co2e_kg - expected.co2e_kg) > Decimal("0.00000001"):
                errors.append(f"{case.record_code} 核算结果与案例输入及因子不一致")
            elif case.category == "1.4" and (result.gas_code, result.gas_mass_kg, result.gwp_value) != (
                case.payload["gas_code"],
                case.amount,
                expected.gwp_value,
            ):
                errors.append(f"{case.record_code} 制冷剂气体、质量或GWP不一致")
    return {
        "passed": not errors,
        "errors": errors,
        "source_name": SOURCE_NAME,
        "energy_fact_count": len(facts),
        "activity_count": len(activities),
        "boundary": boundary_validation,
    }


def calculation_parameters(case: EntryCase) -> tuple[str, dict[str, tuple[Decimal, str]]]:
    """Synthetic demonstration factors, explicitly labelled as assumptions."""
    if case.category == "1.4":
        return "F02_EF", {
            "EMISSION_FACTOR": (Decimal(1), "kg/kg"),
            "GWP": (Decimal(2088 if case.payload.get("gas_code") == "R410A" else 675), "kgCO2e/kg"),
        }
    if case.energy_type == "purchased_electricity":
        return "F08_PURCHASED_ENERGY", {"ENERGY_FACTOR": (Decimal("0.5827"), "kgCO2e/kWh")}
    if case.energy_type:
        factor = Decimal("2.162") if case.energy_type == "natural_gas" else Decimal("2.676")
        return "F02_EF", {"EMISSION_FACTOR": (factor, f"kgCO2e/{case.unit}")}
    factor = Decimal("0.135") if case.category == "3.3" else Decimal("0.09")
    return "F09_TRANSPORT_ACTIVITY", {"TRANSPORT_FACTOR": (factor, f"kgCO2e/{case.unit}")}


async def upgrade_refrigerant_events(session: AsyncSession) -> None:
    """Archive only package-owned synthetic monthly refrigerant rows; retain audit history."""
    from app.demo.showcase.builder import REFRIGERANT_EVENTS

    await require_demo_tenant(session)
    rows = list(
        (
            await session.scalars(
                select(m.GhgActivityRecord).where(
                    m.GhgActivityRecord.activity_code == "C14-REFRIGERANT",
                    m.GhgActivityRecord.record_code.like("WOHENG-%-C14-REFRIGERANT"),
                )
            )
        ).all()
    )
    device = await session.scalar(select(m.MonitorEquipment).where(m.MonitorEquipment.code == "CHILLER-01"))
    if any(row.status == "locked" for row in rows):
        msg = "本包历史冷媒记录已锁定，不自动改写"
        raise ValueError(msg)
    for row in rows:
        if row.status == "archived":
            continue
        event = REFRIGERANT_EVENTS.get((row.period_start.year, row.period_start.month))
        if event is None:
            row.status = "archived"
            row.remarks = "原月度模拟记录已归档；该月没有制冷剂维修事件。"
            continue
        # Keep the legacy parameter values and frozen assignments intact. The
        # explicit maintenance model gets its own reusable parameter set.
        row.parameter_set_code = f"{row.record_code}-MAINT-V1"
        row.period_start = row.period_end = event[0]
        row.activity_amount = event[1]
        row.activity_name = "动力站制冷机组一号冷媒补充"
        row.measurement_method = "维修工单实际补充量"
        row.data_source_type = "ledger"
        row.status = "approved"
        row.source_payload = {
            **dict(row.source_payload or {}),
            "method_code": "F02_EF",
            "gas_code": "R410A",
            "facility_or_device": device.name if device else "动力站制冷机组一号",
            "charges": str(event[1]),
            "recovery": "0",
            "opening_stock": "0",
            "purchases": "0",
            "closing_stock": "0",
            "transfers": "0",
            "source_name": SOURCE_NAME,
            "standard_code": "DEMO-ASSUMPTION-20261115",
            "confidence_level": "demo",
            "maintenance_record": f"制冷机组查漏与补充工单 WX-{event[0]:%Y%m%d}",
            "emission_assumption": "本次维修补充量作为已发生泄漏量；非设备额定充注量",
        }
        area = await session.get(m.MonitorSector, device.sector_id) if device else None
        if area is not None:
            row.facility_code = area.code
            await session.flush()
            await ReplaceActivityAllocations(session).execute(
                inventory_code=row.inventory_code,
                record_code=row.record_code,
                allocations=[
                    {
                        "area_id": area.id,
                        "equipment_id": device.id,
                        "allocation_role": "physical_origin",
                        "allocation_ratio": "1",
                        "source_kind": "manual",
                    }
                ],
                commit=False,
            )
        event_case = EntryCase(
            row.record_code,
            row.activity_name,
            row.facility_code,
            "CHILLER-01",
            event[0],
            event[0],
            "1.4",
            event[1],
            "kg",
            row.source_payload,
        )
        await apply_demo_factor(session, activity=row, case=event_case)
    await session.commit()


async def apply_demo_factor(session: AsyncSession, *, activity: m.GhgActivityRecord, case: EntryCase) -> None:
    """Select a reusable tenant factor through the same service as the business UI."""
    _method, parameters = calculation_parameters(case)
    parameter_code = "GWP" if case.category == "1.4" else next(iter(parameters))
    value, unit = parameters[parameter_code]
    category = (
        "refrigerant"
        if case.category == "1.4"
        else "electricity"
        if case.category == "2.1"
        else "fuel"
        if case.energy_type
        else "transport"
    )
    sub_category = case.payload.get("gas_code") or case.energy_type or case.payload["transport_mode"]
    team_id = require_session_tenant_id(session)
    factor = await session.scalar(
        select(m.EmissionFactor).where(
            m.EmissionFactor.team_id == team_id,
            m.EmissionFactor.scope == activity.ghg_scope,
            m.EmissionFactor.category == category,
            m.EmissionFactor.sub_category == str(sub_category).lower(),
            m.EmissionFactor.unit == case.unit,
            m.EmissionFactor.year == case.start.year,
        )
    )
    # Prefer an already approved applicable shared factor when it matches the
    # documented case basis; never silently swap units or gas identities.
    if factor is None:
        factor = await session.scalar(
            select(m.EmissionFactor)
            .where(
                m.EmissionFactor.team_id.is_(None),
                m.EmissionFactor.scope == activity.ghg_scope,
                m.EmissionFactor.category == category,
                m.EmissionFactor.sub_category == str(sub_category).lower(),
                m.EmissionFactor.unit == case.unit,
                m.EmissionFactor.factor_unit == unit,
                m.EmissionFactor.factor_value == value,
                m.EmissionFactor.year <= case.start.year,
                m.EmissionFactor.review_status == "approved",
                m.EmissionFactor.is_active.is_(True),
            )
            .order_by(m.EmissionFactor.year.desc(), m.EmissionFactor.id.desc())
        )
    service = CalculationFactorMaintenance(session)
    if factor is None:
        created = await service.create_factor(
            CalculationFactorWriteRequest(
                scope=activity.ghg_scope,
                category=category,
                sub_category=str(sub_category),
                unit=case.unit,
                factor_value=value,
                factor_unit=unit,
                year=case.start.year,
                source=f"沃衡{case.name}演示假设",
                source_system="enterprise",
                source_snapshot_id="DEMO-ASSUMPTION-20261115",
                note="合成案例参数，可在企业因子库维护；不代表客户生产实绩或官方认证因子。",
            )
        )
        factor_id = created.id
    else:
        factor_id = factor.id
    await service.apply_activity_factor(
        inventory_code=activity.inventory_code,
        record_code=activity.record_code,
        factor_id=factor_id,
        parameter_code=parameter_code,
    )


async def repair_owned_energy_snapshots(session: AsyncSession) -> None:
    """Remove owned non-energy projections and refresh owned object snapshots only."""
    from app.demo.showcase.builder import EQUIPMENT

    await require_demo_tenant(session)
    owned_sources = (
        "demo_ghg_activity_monthly",
        "demo_ghg_activity_daily",
        "demo_showcase",
        "scope2_meter_monthly",
        "woheng-material-hour",
        SOURCE_SYSTEM,
    )
    await session.execute(
        delete(m.EnergyIntervalFact).where(
            m.EnergyIntervalFact.source_system.in_(owned_sources),
            m.EnergyIntervalFact.energy_type_code == "refrigerant",
        )
    )
    devices = {
        row.code: row
        for row in (
            await session.scalars(
                select(m.MonitorEquipment).where(
                    m.MonitorEquipment.code.in_([spec.code for spec in EQUIPMENT]),
                )
            )
        ).all()
    }
    areas = {row.id: row for row in (await session.scalars(select(m.MonitorSector))).all()}
    facts = list(
        (
            await session.scalars(
                select(m.EnergyIntervalFact).where(
                    m.EnergyIntervalFact.source_system.in_(
                        (*owned_sources, "meter_hourly", "meter_daily", "meter_monthly")
                    ),
                    m.EnergyIntervalFact.equipment_code.in_(devices),
                )
            )
        ).all()
    )
    for fact in facts:
        device = devices[fact.equipment_code]
        fact.equipment_name = device.name
        area = areas.get(device.sector_id)
        if area:
            fact.area_id = str(area.id)
            fact.area_name = area.name
    await session.commit()
