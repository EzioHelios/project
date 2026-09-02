"""Canonical import of legacy XTCK scope ledgers.

The legacy database remains a read-only source. Rows are normalized into the
method-neutral organization inventory and are never copied into the removed
Scope 1/2/3 persistence tables.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.domain.carbon import models as carbon_models
from app.domain.ghg_inventory.models import GhgActivityRecord
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from sqlalchemy.ext.asyncio import AsyncSession


LEGACY_SOURCE_SYSTEM = "xtck_legacy"


@dataclass(frozen=True, slots=True)
class LegacyXtckImportResult:
    """Import counts for one idempotent legacy-ledger pass."""

    source_rows: int
    created: int
    updated: int
    skipped: int
    inventory_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LegacyXtckMasterDataResult:
    """Idempotent master-data import counts."""

    enterprises: int
    sectors: int
    sector_photos: int
    equipment: int
    video_monitors: int


@dataclass(frozen=True, slots=True)
class LegacyActivitySpec:
    """Normalized values required to persist one canonical activity."""

    period_start: date
    period_end: date
    iso_category_code: str
    ghg_scope: str
    scope3_category: int | None
    source_mechanism: str
    value_chain_position: str
    activity_name: str
    activity_amount: Decimal
    activity_unit: str
    source_code: str
    activity_code: str
    payload: dict[str, Any]


class LegacyXtckInventoryImport:
    """Upsert reflected legacy rows into the canonical GHG inventory."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        organization_code: str,
        facility_code: str,
        inventory_prefix: str = "XTCK",
    ) -> None:
        self.session = session
        self.organization_code = organization_code
        self.facility_code = facility_code
        self.inventory_prefix = inventory_prefix

    async def execute(self, source_rows: Mapping[str, Iterable[Mapping[str, Any]]]) -> LegacyXtckImportResult:
        """Normalize and idempotently import every supported source row."""
        require_session_tenant_id(self.session)
        created = 0
        updated = 0
        skipped = 0
        source_count = 0
        inventory_codes: set[str] = set()

        for table_name, rows in source_rows.items():
            for row in rows:
                source_count += 1
                source_id = _int_or_none(row.get("id"))
                if source_id is None:
                    skipped += 1
                    continue
                spec = map_legacy_activity(table_name, row)
                if spec is None or spec.activity_amount < 0:
                    skipped += 1
                    continue
                inventory_code = f"{self.inventory_prefix}-{spec.period_start.year}"
                inventory_codes.add(inventory_code)
                record_code = f"XTCK-{_table_suffix(table_name)}-{source_id}"
                activity = await self.session.scalar(
                    select(GhgActivityRecord).where(
                        GhgActivityRecord.inventory_code == inventory_code,
                        GhgActivityRecord.record_code == record_code,
                    )
                )
                if activity is None:
                    activity = GhgActivityRecord(record_code=record_code, inventory_code=inventory_code)
                    self.session.add(activity)
                    created += 1
                else:
                    updated += 1
                _apply_activity(
                    activity,
                    spec,
                    table_name=table_name,
                    source_id=source_id,
                    organization_code=self.organization_code,
                    facility_code=self.facility_code,
                    legacy_row=row,
                )

        await self.session.commit()
        return LegacyXtckImportResult(
            source_rows=source_count,
            created=created,
            updated=updated,
            skipped=skipped,
            inventory_codes=tuple(sorted(inventory_codes)),
        )


class LegacyXtckMasterDataImport:
    """Upsert legacy warehouse master data while remapping string keys."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, source_rows: Mapping[str, Iterable[Mapping[str, Any]]]) -> LegacyXtckMasterDataResult:
        require_session_tenant_id(self.session)
        enterprises = await self._upsert_enterprises(source_rows.get("dataapp_enterpriseinfo", []))
        sectors = await self._upsert_sectors(source_rows.get("dataapp_monitorsector", []))
        sector_photos = await self._upsert_sector_photos(source_rows.get("dataapp_monitorsectorphoto", []))
        equipment = await self._upsert_equipment(source_rows.get("dataapp_monitorequipment", []))
        video_monitors = await self._upsert_video(source_rows.get("dataapp_videomonitor", []))
        await self.session.commit()
        return LegacyXtckMasterDataResult(enterprises, sectors, sector_photos, equipment, video_monitors)

    async def _upsert_enterprises(self, rows: Iterable[Mapping[str, Any]]) -> int:
        count = 0
        for row in rows:
            unify_code = _optional_text(row.get("unify_code"))
            existing = await self.session.scalar(
                select(carbon_models.EnterpriseInfo).where(carbon_models.EnterpriseInfo.unify_code == unify_code)
            )
            if existing is None:
                existing = carbon_models.EnterpriseInfo()
                self.session.add(existing)
            existing.name = _optional_text(row.get("name"))
            existing.belong_unit = _optional_text(row.get("belong_unit"))
            existing.people_count = _int_or_none(row.get("people_count"))
            existing.park_area = _float_or_none(row.get("park_area"))
            existing.unify_code = unify_code
            existing.industry = _optional_text(row.get("industry"))
            existing.store_area = _float_or_none(row.get("store_area"))
            existing.green_area = _float_or_none(row.get("green_area"))
            existing.location = _optional_text(row.get("location"))
            existing.other_info = dict(row.get("other_info") or {})
            count += 1
        await self.session.flush()
        return count

    async def _upsert_sectors(self, rows: Iterable[Mapping[str, Any]]) -> int:
        root = await self.session.scalar(select(carbon_models.MonitorSector).where(carbon_models.MonitorSector.code == "ROOT"))
        if root is None:
            root = carbon_models.MonitorSector(
                code="ROOT",
                name="仓库园区",
                area_type="site",
                path="ROOT",
                level=0,
                sort_index=0,
                is_enable=True,
            )
            self.session.add(root)
            await self.session.flush()
        count = 0
        for index, row in enumerate(rows, start=1):
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            sector = await self.session.scalar(
                select(carbon_models.MonitorSector).where(carbon_models.MonitorSector.code == code)
            )
            if sector is None:
                sector = carbon_models.MonitorSector(code=code)
                self.session.add(sector)
            sector.name = _optional_text(row.get("name"))
            sector.parent_id = root.id
            sector.area_type = "warehouse_zone"
            sector.path = f"ROOT/{code}"
            sector.level = 1
            sector.sort_index = index
            sector.area = _optional_text(row.get("area"))
            sector.description = _optional_text(row.get("description"))
            sector.area_id = _int_or_none(row.get("area_id"))
            sector.is_enable = bool(row.get("is_enable", True))
            count += 1
        await self.session.flush()
        return count

    async def _upsert_sector_photos(self, rows: Iterable[Mapping[str, Any]]) -> int:
        sectors = {
            row.code: row for row in (await self.session.scalars(select(carbon_models.MonitorSector))).all()
        }
        count = 0
        for row in rows:
            path = _optional_text(row.get("path"))
            sector = sectors.get(str(row.get("sector_id") or ""))
            if path is None or sector is None:
                continue
            photo = await self.session.scalar(
                select(carbon_models.MonitorSectorPhoto).where(
                    carbon_models.MonitorSectorPhoto.path == path,
                    carbon_models.MonitorSectorPhoto.sector_id == sector.id,
                )
            )
            if photo is None:
                photo = carbon_models.MonitorSectorPhoto(path=path, sector_id=sector.id)
                self.session.add(photo)
            photo.description = _optional_text(row.get("description"))
            photo.area_id = _int_or_none(row.get("area_id"))
            count += 1
        await self.session.flush()
        return count

    async def _upsert_equipment(self, rows: Iterable[Mapping[str, Any]]) -> int:
        sectors = {
            row.code: row for row in (await self.session.scalars(select(carbon_models.MonitorSector))).all()
        }
        count = 0
        for row in rows:
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            equipment = await self.session.scalar(
                select(carbon_models.MonitorEquipment).where(carbon_models.MonitorEquipment.code == code)
            )
            if equipment is None:
                equipment = carbon_models.MonitorEquipment(code=code)
                self.session.add(equipment)
            equipment.name = _optional_text(row.get("name"))
            equipment.external_device_id = _optional_text(row.get("code2"))
            sector = sectors.get(str(row.get("sector_id") or ""))
            equipment.sector_id = sector.id if sector else None
            equipment.category = _int_or_none(row.get("category"))
            equipment.status = _int_or_none(row.get("status"))
            equipment.trip_state = _int_or_none(row.get("trip_state"))
            equipment.location = _optional_text(row.get("location"))
            equipment.install_time = _naive_datetime(row.get("install_time"))
            equipment.sort_index = _int_or_none(row.get("sort_index"))
            equipment.supplier = _optional_text(row.get("supplier"))
            equipment.is_enable = bool(row.get("is_enable", True))
            equipment.energy_type = "purchased_electricity" if equipment.category == 0 else equipment.energy_type
            equipment.data_acquisition_method = "legacy_import"
            equipment.protocol = "http_yunji"
            count += 1
        await self.session.flush()
        return count

    async def _upsert_video(self, rows: Iterable[Mapping[str, Any]]) -> int:
        count = 0
        for row in rows:
            ip_address = _optional_text(row.get("ip_address"))
            location = _optional_text(row.get("location"))
            video = await self.session.scalar(
                select(carbon_models.VideoMonitor).where(
                    carbon_models.VideoMonitor.ip_address == ip_address,
                    carbon_models.VideoMonitor.location == location,
                )
            )
            if video is None:
                video = carbon_models.VideoMonitor()
                self.session.add(video)
            for field in (
                "location",
                "f_area",
                "f_area_type",
                "video_url",
                "ip_address",
                "install_method",
                "vedio_type",
                "pixel",
                "brand",
                "b_model",
                "install_time",
            ):
                setattr(video, field, _optional_text(row.get(field)))
            video.status = _int_or_none(row.get("status"))
            video.install_height = _float_or_none(row.get("install_height"))
            video.install_x = _float_or_none(row.get("install_x"))
            video.install_y = _float_or_none(row.get("install_y"))
            video.add_time = _naive_datetime(row.get("add_time"))
            count += 1
        await self.session.flush()
        return count


def map_legacy_activity(  # noqa: PLR0911 - every legacy table has an explicit, auditable mapping
    table_name: str, row: Mapping[str, Any]
) -> LegacyActivitySpec | None:
    """Map one reflected source row without depending on legacy ORM classes."""
    if table_name == "dataapp_scope1mobilecombustion":
        record_date = _date(row.get("record_date"))
        amount = _decimal(row.get("amount"))
        if record_date is None or amount is None:
            return None
        fuel = str(row.get("fuel_type") or "unknown")
        asset = str(row.get("asset_name") or row.get("asset_id") or "移动燃烧源")
        return LegacyActivitySpec(
            record_date,
            record_date,
            "1.2",
            "scope1",
            None,
            "mobile",
            "own",
            asset,
            amount,
            _unit(row.get("unit")),
            str(row.get("asset_id") or f"mobile-{row.get('id')}"),
            "mobile_fuel",
            {
                "fuel_type": _fuel_alias(fuel),
                "legacy_fuel_type": fuel,
                "mileage_km": _json_value(row.get("mileage_km")),
                "work_hours": _json_value(row.get("work_hours")),
            },
        )
    if table_name == "dataapp_scope1stationarycombustion":
        period_start = _date(row.get("period_start"))
        period_end = _date(row.get("period_end"))
        amount = _decimal(row.get("amount"))
        if period_start is None or period_end is None or amount is None:
            return None
        fuel = str(row.get("fuel_type") or "unknown")
        facility = str(row.get("facility_name") or "固定燃烧源")
        return LegacyActivitySpec(
            period_start,
            period_end,
            "1.1",
            "scope1",
            None,
            "stationary",
            "own",
            facility,
            amount,
            _unit(row.get("unit")),
            f"stationary-{row.get('id')}",
            "stationary_fuel",
            {
                "fuel_type": _fuel_alias(fuel),
                "legacy_fuel_type": fuel,
                "facility_name": facility,
                "meter_reading_start": _json_value(row.get("meter_reading_start")),
                "meter_reading_end": _json_value(row.get("meter_reading_end")),
            },
        )
    if table_name == "dataapp_scope1refrigerantleak":
        fill_date = _date(row.get("fill_date"))
        amount = _decimal(row.get("amount_kg"))
        if fill_date is None or amount is None:
            return None
        refrigerant = str(row.get("refrigerant_type") or "unknown").lower()
        device = str(row.get("device_name") or row.get("device_id") or "制冷设备")
        return LegacyActivitySpec(
            fill_date,
            fill_date,
            "1.4",
            "scope1",
            None,
            "fugitive",
            "own",
            device,
            amount,
            "kg",
            str(row.get("device_id") or f"refrigerant-{row.get('id')}"),
            "refrigerant_refill",
            {"refrigerant_type": refrigerant, "leak_type": _json_value(row.get("leak_type"))},
        )
    if table_name == "dataapp_scope2electricitybill":
        period = _billing_period(row.get("billing_month"))
        amount = _decimal(row.get("total_kwh"))
        if period is None or amount is None:
            return None
        account = str(row.get("account_number") or f"electricity-{row.get('id')}")
        return LegacyActivitySpec(
            period[0],
            period[1],
            "2.1",
            "scope2",
            None,
            "energy",
            "upstream",
            f"购入电力 {account}",
            amount,
            "kWh",
            account,
            "purchased_electricity",
            {
                "scope2_method": "location",
                "account_number": account,
                "peak_kwh": _json_value(row.get("peak_kwh")),
                "flat_kwh": _json_value(row.get("flat_kwh")),
                "valley_kwh": _json_value(row.get("valley_kwh")),
                "amount_cny": _json_value(row.get("amount_cny")),
            },
        )
    if table_name == "dataapp_scope2purchasedenergy":
        period_start = _date(row.get("period_start"))
        period_end = _date(row.get("period_end"))
        amount = _decimal(row.get("activity_amount")) or _decimal(row.get("amount"))
        if period_start is None or period_end is None or amount is None:
            return None
        energy_type = str(row.get("energy_type_code") or "purchased_energy")
        return LegacyActivitySpec(
            period_start,
            period_end,
            "2.2",
            "scope2",
            None,
            "energy",
            "upstream",
            str(row.get("energy_type_name") or energy_type),
            amount,
            _unit(row.get("activity_unit") or row.get("unit")),
            f"purchased-energy-{row.get('id')}",
            energy_type,
            {
                "scope2_method": "location",
                "energy_type": energy_type,
                "supplier_name": _json_value(row.get("supplier_name")),
                "factor_source": _json_value(row.get("factor_source")),
                "factor_year": _json_value(row.get("factor_year")),
                "factor_unit": _json_value(row.get("factor_unit")),
                "standard_code": _json_value(row.get("standard_code")),
            },
        )
    if table_name == "dataapp_scope3thirdpartytransport":
        period_start = _fallback_date(row)
        distance = _decimal(row.get("distance_km"))
        load = _decimal(row.get("load_ton"))
        if period_start is None or distance is None or load is None:
            return None
        vehicle = _vehicle_alias(str(row.get("vehicle_type") or "transport_heavy_truck"))
        waybill = str(row.get("waybill_no") or f"transport-{row.get('id')}")
        return LegacyActivitySpec(
            period_start,
            period_start,
            "3.1",
            "scope3",
            4,
            "transport",
            "upstream",
            f"第三方运输 {waybill}",
            distance * load,
            "t·km",
            waybill,
            "third_party_transport",
            {
                "vehicle_type": vehicle,
                "origin": _json_value(row.get("origin")),
                "destination": _json_value(row.get("destination")),
                "distance_km": str(distance),
                "load_ton": str(load),
            },
        )
    if table_name == "dataapp_scope3wastedisposal":
        record_date = _date(row.get("date"))
        amount = _decimal(row.get("weight_ton"))
        if record_date is None or amount is None:
            return None
        category = str(row.get("category") or "unknown")
        treatment = str(row.get("treatment_method") or "unknown")
        material = _waste_alias(category, treatment)
        return LegacyActivitySpec(
            record_date,
            record_date,
            "4.4",
            "scope3",
            5,
            "value_chain",
            "upstream",
            f"运营废物处置 {category}",
            amount,
            "t",
            f"waste-{row.get('id')}",
            "operational_waste",
            {
                "waste_type": material,
                "legacy_waste_category": category,
                "treatment_method": treatment,
                "vendor_name": _json_value(row.get("vendor_name")),
            },
        )
    return None


def _apply_activity(
    activity: GhgActivityRecord,
    spec: LegacyActivitySpec,
    *,
    table_name: str,
    source_id: int,
    organization_code: str,
    facility_code: str,
    legacy_row: Mapping[str, Any],
) -> None:
    activity.organization_code = organization_code
    activity.facility_code = facility_code
    activity.source_code = spec.source_code[:96]
    activity.activity_code = spec.activity_code
    activity.activity_name = spec.activity_name[:255]
    activity.period_start = spec.period_start
    activity.period_end = spec.period_end
    activity.iso_category_code = spec.iso_category_code
    activity.ghg_scope = spec.ghg_scope
    activity.scope3_category = spec.scope3_category
    activity.source_mechanism = spec.source_mechanism
    activity.value_chain_position = spec.value_chain_position
    activity.boundary_status = "included"
    activity.activity_amount = spec.activity_amount
    activity.activity_unit = spec.activity_unit
    activity.data_source_type = str(legacy_row.get("data_source") or "legacy_database")[:32]
    activity.measurement_method = str(legacy_row.get("collection_method") or "legacy_import")[:255]
    activity.quality_status = "pass" if legacy_row.get("status") == "approved" else "warning"
    activity.source_payload = {
        **spec.payload,
        "legacy": _json_mapping(legacy_row),
        "migration_version": "xtck-canonical-v1",
    }
    activity.remarks = _optional_text(legacy_row.get("remark"))
    activity.status = "approved" if legacy_row.get("status") == "approved" else "draft"
    activity.source_system = LEGACY_SOURCE_SYSTEM
    activity.source_record_type = table_name
    activity.source_record_id = source_id


def _table_suffix(table_name: str) -> str:
    return table_name.removeprefix("dataapp_").replace("scope", "S").upper()[:48]


def _fuel_alias(value: str) -> str:
    return {
        "diesel_0": "diesel",
        "gas_92": "gasoline",
        "gas_95": "gasoline",
        "ng": "natural_gas",
        "pipe_ng": "natural_gas",
    }.get(value.lower(), value.lower())


def _vehicle_alias(value: str) -> str:
    return {
        "heavy_truck": "transport_heavy_truck",
        "light_truck": "transport_light_truck",
    }.get(value.lower(), value.lower())


def _waste_alias(category: str, treatment: str) -> str:
    if treatment.lower() == "incineration" or category.lower() == "domestic":
        return "waste_municipal_incineration"
    return f"waste_{category.lower()}_{treatment.lower()}"


def _billing_period(value: Any) -> tuple[date, date] | None:
    try:
        year_text, month_text = str(value).split("-", maxsplit=1)
        year, month = int(year_text), int(month_text)
        return date(year, month, 1), date(year, month, monthrange(year, month)[1])
    except (TypeError, ValueError):
        return None


def _fallback_date(row: Mapping[str, Any]) -> date | None:
    created_at = _date(row.get("created_at"))
    if created_at is not None:
        return created_at
    year = _int_or_none(row.get("data_year"))
    return date(year, 1, 1) if year is not None else None


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _naive_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=None)


def _unit(value: Any) -> str:
    unit = str(value or "unknown")
    return {"m3": "m³", "ton": "t"}.get(unit, unit)[:64]


def _optional_text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    return value


def _json_mapping(row: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_value(value) for key, value in row.items() if key != "team_id"}
