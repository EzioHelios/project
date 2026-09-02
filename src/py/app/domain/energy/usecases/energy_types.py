"""Standard energy type initialization and cleanup workflows."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.db import models as m
from app.db.models import Team
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class EnergyTypeSpec:
    code: str
    name: str
    category: str
    default_scope: str
    original_unit: str | None
    standard_unit: str | None
    standard_factor: Decimal | None
    standard_code: str
    conversion_factor_source: str
    remark: str | None = None


@dataclass(frozen=True, slots=True)
class EnergyUnitConversionSpec:
    energy_type_code: str
    from_unit: str
    to_unit: str
    multiply_factor: Decimal
    standard_code: str
    conversion_factor_source: str
    remark: str | None = None


@dataclass(frozen=True, slots=True)
class EnergyTypeInitResult:
    applied: bool
    energy_types_created: int
    energy_types_updated: int
    energy_types_unchanged: int
    conversions_created: int
    conversions_updated: int
    conversions_unchanged: int


@dataclass(frozen=True, slots=True)
class EnergyTypeIssue:
    table_name: str
    team_slug: str
    team_name: str
    field_name: str
    observed_code: str
    row_count: int
    issue_type: str
    suggested_code: str | None = None


@dataclass(frozen=True, slots=True)
class EnergyTypeDiagnosticResult:
    team_slug: str | None
    issues: tuple[EnergyTypeIssue, ...]
    known_energy_type_count: int

    @property
    def issue_count(self) -> int:
        return len(self.issues)


@dataclass(frozen=True, slots=True)
class EnergyTypeRepairResult:
    applied: bool
    initialized: EnergyTypeInitResult
    interval_facts_updated: int = 0
    device_types_updated: int = 0
    equipment_updated: int = 0
    ghg_activities_updated: int = 0
    remaining_issues: EnergyTypeDiagnosticResult | None = None


STANDARD_ENERGY_TYPES: tuple[EnergyTypeSpec, ...] = (
    EnergyTypeSpec(
        code="purchased_electricity",
        name="外购电力",
        category="purchased_energy",
        default_scope="scope2",
        original_unit="kWh",
        standard_unit="kgce",
        standard_factor=Decimal("0.1229"),
        standard_code="GB/T 2589-2020",
        conversion_factor_source="GB/T 2589-2020 综合能耗计算通则,电力折标准煤参考系数.",
    ),
    EnergyTypeSpec(
        code="natural_gas",
        name="天然气",
        category="fuel",
        default_scope="scope1",
        original_unit="m3",
        standard_unit="kgce",
        standard_factor=Decimal("1.2143"),
        standard_code="GB/T 2589-2020",
        conversion_factor_source="GB/T 2589-2020 综合能耗计算通则,折标准煤参考系数.",
    ),
    EnergyTypeSpec(
        code="diesel",
        name="柴油",
        category="fuel",
        default_scope="scope1",
        original_unit="kg",
        standard_unit="kgce",
        standard_factor=Decimal("1.4571"),
        standard_code="GB/T 2589-2020",
        conversion_factor_source="GB/T 2589-2020 综合能耗计算通则,折标准煤参考系数.",
    ),
    EnergyTypeSpec(
        code="gasoline",
        name="汽油",
        category="fuel",
        default_scope="scope1",
        original_unit="kg",
        standard_unit="kgce",
        standard_factor=Decimal("1.4714"),
        standard_code="GB/T 2589-2020",
        conversion_factor_source="GB/T 2589-2020 综合能耗计算通则,折标准煤参考系数.",
    ),
    EnergyTypeSpec(
        code="fuel_oil",
        name="燃料油",
        category="fuel",
        default_scope="scope1",
        original_unit="kg",
        standard_unit="kgce",
        standard_factor=Decimal("1.4286"),
        standard_code="GB/T 2589-2020",
        conversion_factor_source="GB/T 2589-2020 综合能耗计算通则,折标准煤参考系数.",
    ),
    EnergyTypeSpec(
        code="coal",
        name="原煤",
        category="fuel",
        default_scope="scope1",
        original_unit="t",
        standard_unit="kgce",
        standard_factor=Decimal("714.3"),
        standard_code="GB/T 2589-2020",
        conversion_factor_source="GB/T 2589-2020 综合能耗计算通则,折标准煤参考系数.",
    ),
    EnergyTypeSpec(
        code="purchased_heat",
        name="外购热力",
        category="purchased_energy",
        default_scope="scope2",
        original_unit="GJ",
        standard_unit="kgce",
        standard_factor=Decimal("34.12"),
        standard_code="GB/T 2589-2020",
        conversion_factor_source="GB/T 2589-2020 综合能耗计算通则,热量折标准煤参考口径.",
    ),
    EnergyTypeSpec(
        code="purchased_steam",
        name="外购蒸汽",
        category="purchased_energy",
        default_scope="scope2",
        original_unit="GJ",
        standard_unit="kgce",
        standard_factor=Decimal("34.12"),
        standard_code="GB/T 2589-2020",
        conversion_factor_source="GB/T 2589-2020 综合能耗计算通则,蒸汽按热量折标准煤参考口径.",
    ),
    EnergyTypeSpec(
        code="purchased_cooling",
        name="外购冷量",
        category="purchased_energy",
        default_scope="scope2",
        original_unit="GJ",
        standard_unit="kgce",
        standard_factor=Decimal("34.12"),
        standard_code="GB/T 2589-2020",
        conversion_factor_source="GB/T 2589-2020 综合能耗计算通则,冷量按热量折标准煤参考口径.",
    ),
    EnergyTypeSpec(
        code="refrigerant",
        name="制冷剂",
        category="non_energy_medium",
        default_scope="scope1",
        original_unit="kg",
        standard_unit=None,
        standard_factor=None,
        standard_code="ISO 14064-1",
        conversion_factor_source="非能源排放介质,用于组织碳核算分类与活动数据归集.",
        remark="不参与综合能耗折标准煤计算.",
    ),
)

STANDARD_UNIT_CONVERSIONS: tuple[EnergyUnitConversionSpec, ...] = (
    EnergyUnitConversionSpec(
        "diesel",
        "L",
        "kg",
        Decimal("0.84"),
        "enterprise_default",
        "默认柴油密度参数,用于 L 到 kg 换算; 企业应优先维护实测密度或供应商密度.",
    ),
    EnergyUnitConversionSpec("diesel", "t", "kg", Decimal(1000), "SI", "公制质量单位换算."),
    EnergyUnitConversionSpec(
        "gasoline",
        "L",
        "kg",
        Decimal("0.74"),
        "enterprise_default",
        "默认汽油密度参数,用于 L 到 kg 换算; 企业应优先维护实测密度或供应商密度.",
    ),
    EnergyUnitConversionSpec("gasoline", "t", "kg", Decimal(1000), "SI", "公制质量单位换算."),
    EnergyUnitConversionSpec("fuel_oil", "t", "kg", Decimal(1000), "SI", "公制质量单位换算."),
    EnergyUnitConversionSpec("coal", "kg", "t", Decimal("0.001"), "SI", "公制质量单位换算."),
    EnergyUnitConversionSpec("purchased_electricity", "MWh", "kWh", Decimal(1000), "SI", "电量单位换算."),
    EnergyUnitConversionSpec("purchased_heat", "MWh", "GJ", Decimal("3.6"), "SI", "热量单位换算."),
    EnergyUnitConversionSpec("purchased_heat", "Gcal", "GJ", Decimal("4.1868"), "SI", "热量单位换算."),
    EnergyUnitConversionSpec("purchased_steam", "MWh", "GJ", Decimal("3.6"), "SI", "热量单位换算."),
    EnergyUnitConversionSpec("purchased_steam", "Gcal", "GJ", Decimal("4.1868"), "SI", "热量单位换算."),
    EnergyUnitConversionSpec(
        "purchased_steam",
        "t",
        "GJ",
        Decimal("2.8"),
        "enterprise_default",
        "默认蒸汽热焓参数,用于 t 到 GJ 换算; 企业应优先维护供应商结算热值.",
    ),
    EnergyUnitConversionSpec("purchased_cooling", "MWh", "GJ", Decimal("3.6"), "SI", "冷量单位换算."),
    EnergyUnitConversionSpec("purchased_cooling", "Gcal", "GJ", Decimal("4.1868"), "SI", "冷量单位换算."),
)

CANONICAL_ENERGY_CODE_BY_ALIAS: dict[str, str] = {
    "electricity": "purchased_electricity",
    "grid_electricity": "purchased_electricity",
    "power": "purchased_electricity",
    "电力": "purchased_electricity",
    "购电": "purchased_electricity",
    "外购电力": "purchased_electricity",
    "c21-electricity": "purchased_electricity",
    "natural_gas": "natural_gas",
    "gas": "natural_gas",
    "天然气": "natural_gas",
    "c11-gas": "natural_gas",
    "diesel": "diesel",
    "柴油": "diesel",
    "c12-diesel": "diesel",
    "purchased_steam": "purchased_steam",
    "steam": "purchased_steam",
    "蒸汽": "purchased_steam",
    "外购蒸汽": "purchased_steam",
    "c22-steam": "purchased_steam",
    "refrigerant": "refrigerant",
    "制冷剂": "refrigerant",
    "c14-refrigerant": "refrigerant",
}


def normalize_energy_code_key(value: str | None) -> str:
    """Normalize an inbound code for deterministic matching."""
    return (value or "").strip().lower()


def canonicalize_energy_type_code(value: str | None) -> str | None:
    """Return the platform standard energy type code for a known inbound value."""
    if not value:
        return None
    normalized = normalize_energy_code_key(value)
    return CANONICAL_ENERGY_CODE_BY_ALIAS.get(normalized, normalized)


async def ensure_standard_energy_types(session: AsyncSession, *, apply: bool) -> EnergyTypeInitResult:
    """Create or update the global standard energy type and unit conversion dictionaries."""
    type_codes = [item.code for item in STANDARD_ENERGY_TYPES]
    conversion_keys = [(item.energy_type_code, item.from_unit, item.to_unit) for item in STANDARD_UNIT_CONVERSIONS]
    existing_types = {
        item.code: item for item in (await session.scalars(select(m.EnergyType).where(m.EnergyType.code.in_(type_codes)))).all()
    }
    existing_conversions = {
        (item.energy_type_code, item.from_unit, item.to_unit): item
        for item in (
            await session.scalars(
                select(m.EnergyUnitConversion).where(
                    m.EnergyUnitConversion.energy_type_code.in_([key[0] for key in conversion_keys])
                )
            )
        ).all()
    }

    created = updated = unchanged = 0
    for spec in STANDARD_ENERGY_TYPES:
        row = existing_types.get(spec.code)
        if row is None:
            created += 1
            if apply:
                row = m.EnergyType(code=spec.code)
                session.add(row)
        elif _energy_type_needs_update(row, spec):
            updated += 1
        else:
            unchanged += 1
        if apply and row is not None:
            _apply_energy_type_spec(row, spec)

    conversions_created = conversions_updated = conversions_unchanged = 0
    for spec in STANDARD_UNIT_CONVERSIONS:
        row = existing_conversions.get((spec.energy_type_code, spec.from_unit, spec.to_unit))
        if row is None:
            conversions_created += 1
            if apply:
                row = m.EnergyUnitConversion(
                    energy_type_code=spec.energy_type_code,
                    from_unit=spec.from_unit,
                    to_unit=spec.to_unit,
                )
                session.add(row)
        elif _conversion_needs_update(row, spec):
            conversions_updated += 1
        else:
            conversions_unchanged += 1
        if apply and row is not None:
            _apply_conversion_spec(row, spec)

    if apply:
        await session.commit()

    return EnergyTypeInitResult(
        applied=apply,
        energy_types_created=created,
        energy_types_updated=updated,
        energy_types_unchanged=unchanged,
        conversions_created=conversions_created,
        conversions_updated=conversions_updated,
        conversions_unchanged=conversions_unchanged,
    )


async def diagnose_energy_type_data(session: AsyncSession, *, team_slug: str | None = None) -> EnergyTypeDiagnosticResult:
    """Report tenant rows that do not use standard energy type codes."""
    previous_bypass = session.info.get(TENANT_BYPASS_SESSION_KEY)
    session.info[TENANT_BYPASS_SESSION_KEY] = True
    try:
        teams = await _teams_by_id(session)
        requested_team_id = await _resolve_team_id(session, team_slug)
        known_codes = {item.code for item in (await session.scalars(select(m.EnergyType))).all()}
        known_codes.update(item.code for item in STANDARD_ENERGY_TYPES)

        issues: list[EnergyTypeIssue] = []
        await _collect_interval_fact_issues(session, issues, teams, known_codes, requested_team_id)
        if requested_team_id is None:
            await _collect_device_type_issues(session, issues, known_codes)
        await _collect_equipment_issues(session, issues, teams, known_codes, requested_team_id)
        await _collect_ghg_activity_issues(session, issues, teams, known_codes, requested_team_id)
        return EnergyTypeDiagnosticResult(
            team_slug=None if team_slug in {None, "all"} else team_slug,
            issues=tuple(issues),
            known_energy_type_count=len(known_codes),
        )
    finally:
        if previous_bypass is None:
            session.info.pop(TENANT_BYPASS_SESSION_KEY, None)
        else:
            session.info[TENANT_BYPASS_SESSION_KEY] = previous_bypass


async def repair_energy_type_data(session: AsyncSession, *, team_slug: str | None = None, apply: bool) -> EnergyTypeRepairResult:
    """Normalize existing tenant data to the standard energy type dictionary."""
    initialized = await ensure_standard_energy_types(session, apply=apply)
    if not apply:
        return EnergyTypeRepairResult(applied=False, initialized=initialized)

    previous_bypass = session.info.get(TENANT_BYPASS_SESSION_KEY)
    session.info[TENANT_BYPASS_SESSION_KEY] = True
    try:
        requested_team_id = await _resolve_team_id(session, team_slug)
        interval_count = await _repair_interval_facts(session, requested_team_id)
        device_type_count = await _repair_device_types(session) if requested_team_id is None else 0
        equipment_count = await _repair_equipment(session, requested_team_id)
        activity_count = await _repair_ghg_activities(session, requested_team_id)
        await session.commit()
        remaining = await diagnose_energy_type_data(session, team_slug=team_slug)
        return EnergyTypeRepairResult(
            applied=True,
            initialized=initialized,
            interval_facts_updated=interval_count,
            device_types_updated=device_type_count,
            equipment_updated=equipment_count,
            ghg_activities_updated=activity_count,
            remaining_issues=remaining,
        )
    finally:
        if previous_bypass is None:
            session.info.pop(TENANT_BYPASS_SESSION_KEY, None)
        else:
            session.info[TENANT_BYPASS_SESSION_KEY] = previous_bypass


def _energy_type_needs_update(row: m.EnergyType, spec: EnergyTypeSpec) -> bool:
    return (
        row.name != spec.name
        or row.category != spec.category
        or row.default_scope != spec.default_scope
        or row.original_unit != spec.original_unit
        or row.standard_unit != spec.standard_unit
        or _decimal_or_none(row.standard_factor) != spec.standard_factor
        or row.standard_code != spec.standard_code
        or row.conversion_factor_source != spec.conversion_factor_source
        or row.remark != spec.remark
        or row.is_enabled is not True
    )


def _conversion_needs_update(row: m.EnergyUnitConversion, spec: EnergyUnitConversionSpec) -> bool:
    return (
        _decimal_or_none(row.multiply_factor) != spec.multiply_factor
        or row.standard_code != spec.standard_code
        or row.conversion_factor_source != spec.conversion_factor_source
        or row.remark != spec.remark
        or row.is_default is not True
        or row.is_enabled is not True
    )


def _apply_energy_type_spec(row: m.EnergyType, spec: EnergyTypeSpec) -> None:
    row.name = spec.name
    row.category = spec.category
    row.default_scope = spec.default_scope
    row.original_unit = spec.original_unit
    row.standard_unit = spec.standard_unit
    row.standard_factor = spec.standard_factor
    row.standard_code = spec.standard_code
    row.conversion_factor_source = spec.conversion_factor_source
    row.remark = spec.remark
    row.is_enabled = True


def _apply_conversion_spec(row: m.EnergyUnitConversion, spec: EnergyUnitConversionSpec) -> None:
    row.multiply_factor = spec.multiply_factor
    row.standard_code = spec.standard_code
    row.conversion_factor_source = spec.conversion_factor_source
    row.remark = spec.remark
    row.is_default = True
    row.is_enabled = True


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


async def _teams_by_id(session: AsyncSession) -> dict[UUID, tuple[str, str]]:
    return {team.id: (team.slug, team.name or team.slug) for team in (await session.scalars(select(Team))).all()}


async def _resolve_team_id(session: AsyncSession, team_slug: str | None) -> UUID | None:
    if team_slug in {None, "all"}:
        return None
    team_id = await session.scalar(select(Team.id).where(Team.slug == team_slug))
    if team_id is None:
        msg = f"Unknown team: {team_slug}"
        raise ValueError(msg)
    return team_id


async def _collect_interval_fact_issues(
    session: AsyncSession,
    issues: list[EnergyTypeIssue],
    teams: dict[UUID, tuple[str, str]],
    known_codes: set[str],
    team_id: UUID | None,
) -> None:
    statement = (
        select(m.EnergyIntervalFact.team_id, m.EnergyIntervalFact.energy_type_code, func.count())
        .group_by(m.EnergyIntervalFact.team_id, m.EnergyIntervalFact.energy_type_code)
        .order_by(func.count().desc())
    )
    if team_id is not None:
        statement = statement.where(m.EnergyIntervalFact.team_id == team_id)
    for row_team_id, observed_code, row_count in (await session.execute(statement)).all():
        _append_issue(
            issues,
            teams,
            row_team_id,
            "dataapp_energyintervalfact",
            "energy_type_code",
            observed_code,
            row_count,
            known_codes,
        )


async def _collect_equipment_issues(
    session: AsyncSession,
    issues: list[EnergyTypeIssue],
    teams: dict[UUID, tuple[str, str]],
    known_codes: set[str],
    team_id: UUID | None,
) -> None:
    statement = (
        select(m.MonitorEquipment.team_id, m.MonitorEquipment.energy_type, func.count())
        .where(m.MonitorEquipment.energy_type.is_not(None), m.MonitorEquipment.energy_type != "")
        .group_by(m.MonitorEquipment.team_id, m.MonitorEquipment.energy_type)
        .order_by(func.count().desc())
    )
    if team_id is not None:
        statement = statement.where(m.MonitorEquipment.team_id == team_id)
    for row_team_id, observed_code, row_count in (await session.execute(statement)).all():
        _append_issue(
            issues,
            teams,
            row_team_id,
            "dataapp_monitorequipment",
            "energy_type",
            observed_code,
            row_count,
            known_codes,
        )


async def _collect_device_type_issues(
    session: AsyncSession,
    issues: list[EnergyTypeIssue],
    known_codes: set[str],
) -> None:
    statement = (
        select(m.DeviceType.energy_type, func.count())
        .where(m.DeviceType.energy_type.is_not(None), m.DeviceType.energy_type != "")
        .group_by(m.DeviceType.energy_type)
        .order_by(func.count().desc())
    )
    for observed_code, row_count in (await session.execute(statement)).all():
        _append_issue(
            issues,
            {},
            None,
            "dataapp_devicetype",
            "energy_type",
            observed_code,
            row_count,
            known_codes,
        )


async def _collect_ghg_activity_issues(
    session: AsyncSession,
    issues: list[EnergyTypeIssue],
    teams: dict[UUID, tuple[str, str]],
    known_codes: set[str],
    team_id: UUID | None,
) -> None:
    statement = select(m.GhgActivityRecord).where(
        m.GhgActivityRecord.ghg_scope.in_(["scope1", "scope2"]),
        m.GhgActivityRecord.boundary_status == "included",
    )
    if team_id is not None:
        statement = statement.where(m.GhgActivityRecord.team_id == team_id)
    grouped: dict[tuple[UUID, str], int] = {}
    for activity in (await session.scalars(statement)).all():
        observed_code = _ghg_activity_energy_candidate(activity)
        grouped[(activity.team_id, observed_code)] = grouped.get((activity.team_id, observed_code), 0) + 1
    for (row_team_id, observed_code), row_count in grouped.items():
        _append_issue(
            issues,
            teams,
            row_team_id,
            "ghg_activity_record",
            "source_payload.energy_type_code",
            observed_code,
            row_count,
            known_codes,
        )


def _append_issue(
    issues: list[EnergyTypeIssue],
    teams: dict[UUID, tuple[str, str]],
    row_team_id: UUID | None,
    table_name: str,
    field_name: str,
    observed_code: str | None,
    row_count: int,
    known_codes: set[str],
) -> None:
    if not observed_code:
        normalized = ""
        suggested = None
        issue_type = "missing"
    else:
        normalized = normalize_energy_code_key(observed_code)
        suggested = canonicalize_energy_type_code(observed_code)
        if observed_code in known_codes:
            return
        issue_type = "alias" if suggested and suggested in known_codes else "unknown"
    team_slug, team_name = teams.get(row_team_id, ("global", "全局主数据"))
    issues.append(
        EnergyTypeIssue(
            table_name=table_name,
            team_slug=team_slug,
            team_name=team_name,
            field_name=field_name,
            observed_code=observed_code or normalized,
            row_count=int(row_count),
            issue_type=issue_type,
            suggested_code=suggested if suggested != normalized else None,
        )
    )


async def _repair_interval_facts(session: AsyncSession, team_id: UUID | None) -> int:
    statement = select(m.EnergyIntervalFact)
    if team_id is not None:
        statement = statement.where(m.EnergyIntervalFact.team_id == team_id)
    updated = 0
    for row in (await session.scalars(statement)).all():
        target = canonicalize_energy_type_code(row.energy_type_code)
        if target and target != row.energy_type_code:
            row.energy_type_code = target
            updated += 1
    return updated


async def _repair_equipment(session: AsyncSession, team_id: UUID | None) -> int:
    statement = select(m.MonitorEquipment).where(
        m.MonitorEquipment.energy_type.is_not(None),
        m.MonitorEquipment.energy_type != "",
    )
    if team_id is not None:
        statement = statement.where(m.MonitorEquipment.team_id == team_id)
    updated = 0
    for row in (await session.scalars(statement)).all():
        target = canonicalize_energy_type_code(row.energy_type)
        if target and target != row.energy_type:
            row.energy_type = target
            updated += 1
    return updated


async def _repair_device_types(session: AsyncSession) -> int:
    statement = select(m.DeviceType).where(
        m.DeviceType.energy_type.is_not(None),
        m.DeviceType.energy_type != "",
    )
    updated = 0
    for row in (await session.scalars(statement)).all():
        target = canonicalize_energy_type_code(row.energy_type)
        if target and target != row.energy_type:
            row.energy_type = target
            updated += 1
    return updated


async def _repair_ghg_activities(session: AsyncSession, team_id: UUID | None) -> int:
    statement = select(m.GhgActivityRecord).where(
        m.GhgActivityRecord.ghg_scope.in_(["scope1", "scope2"]),
        m.GhgActivityRecord.boundary_status == "included",
    )
    if team_id is not None:
        statement = statement.where(m.GhgActivityRecord.team_id == team_id)
    updated = 0
    for activity in (await session.scalars(statement)).all():
        payload = dict(activity.source_payload or {})
        target = canonicalize_energy_type_code(_ghg_activity_energy_candidate(activity))
        if target and payload.get("energy_type_code") != target:
            payload["energy_type_code"] = target
            activity.source_payload = payload
            updated += 1
    return updated


def _ghg_activity_energy_candidate(activity: m.GhgActivityRecord) -> str:
    payload = dict(activity.source_payload or {})
    for key in ("energy_type_code", "fuel_type", "energy_type", "fuel_or_material"):
        value = payload.get(key)
        if value:
            return str(value)
    if activity.iso_category_code == "1.4" or payload.get("refrigerant_type"):
        return "refrigerant"
    return str(activity.activity_code or "")
