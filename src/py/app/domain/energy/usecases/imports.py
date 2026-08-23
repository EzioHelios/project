from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from litestar.exceptions import PermissionDeniedException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


IMPORT_SOURCE_SYSTEM = "manual_csv"
IMPORT_MARKER = "[energy_import_csv]"
MAX_IMPORT_ROWS = 1000
YEAR_MONTH_LENGTH = 7
DATE_LENGTH = 10


class EnergyImportValidationError(ValueError):
    """Raised when a CSV row cannot be converted into an energy import record."""


@dataclass(slots=True)
class EnergyDatasetImportResult:
    dataset: str
    received_count: int
    imported_count: int = 0
    skipped_count: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])


class EnergyDatasetImportUseCase:
    """Application service for tenant-scoped energy and activity CSV imports."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def import_rows(
        self,
        *,
        dataset: str,
        rows: list[dict[str, Any]],
        source_name: str | None = None,
    ) -> EnergyDatasetImportResult:
        team_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        if team_id is None:
            msg = "导入需要先选择一个企业租户。"
            raise PermissionDeniedException(detail=msg)

        normalized_dataset = dataset.strip()
        result = EnergyDatasetImportResult(dataset=normalized_dataset, received_count=len(rows))
        if len(rows) > MAX_IMPORT_ROWS:
            result.errors.append({"row_number": 0, "message": "单次导入最多支持 1000 行。"})
            return result

        for index, raw_row in enumerate(rows, start=2):
            try:
                row = {str(key).strip(): value for key, value in raw_row.items()}
                async with self._session.begin_nested():
                    if normalized_dataset == "energy_interval_facts":
                        await self._upsert_energy_interval_fact(team_id=str(team_id), row=row, source_name=source_name)
                    elif normalized_dataset == "production_output_facts":
                        await self._upsert_production_output_fact(team_id=str(team_id), row=row, source_name=source_name)
                    else:
                        result.errors.append({"row_number": index, "message": f"不支持的数据集: {normalized_dataset}"})
                        break
                result.imported_count += 1
            except (TypeError, ValueError, InvalidOperation) as exc:
                result.skipped_count += 1
                result.errors.append({"row_number": index, "message": str(exc)})
            except SQLAlchemyError as exc:
                result.skipped_count += 1
                result.errors.append({"row_number": index, "message": _db_error_message(exc)})

        if result.imported_count:
            await self._session.commit()
        else:
            await self._session.rollback()
        return result

    async def _upsert_energy_interval_fact(self, *, team_id: str, row: dict[str, Any], source_name: str | None) -> None:
        source_record_id = _required_text(row, "source_record_id")
        period_start = _datetime(row.get("period_start"))
        period_end = _datetime(row.get("period_end")) if row.get("period_end") else period_start
        await self._session.execute(
            text(
                """
                insert into dataapp_energyintervalfact (
                    team_id, source_system, source_record_id, energy_type_code, equipment_code, equipment_name,
                    area_id, area_name, use_system_code, use_system_name, granularity, period_start, period_end,
                    amount, unit, cost_cny, tariff_segment_type, reading_count, data_quality, remark, created_at, updated_at
                )
                values (
                    :team_id, :source_system, :source_record_id, :energy_type_code, :equipment_code, :equipment_name,
                    :area_id, :area_name, :use_system_code, :use_system_name, :granularity, :period_start, :period_end,
                    :amount, :unit, :cost_cny, :tariff_segment_type, :reading_count, :data_quality, :remark, now(), now()
                )
                on conflict on constraint uq_energy_interval_team_source_record do update set
                    energy_type_code = excluded.energy_type_code,
                    equipment_code = excluded.equipment_code,
                    equipment_name = excluded.equipment_name,
                    area_id = excluded.area_id,
                    area_name = excluded.area_name,
                    use_system_code = excluded.use_system_code,
                    use_system_name = excluded.use_system_name,
                    granularity = excluded.granularity,
                    period_start = excluded.period_start,
                    period_end = excluded.period_end,
                    amount = excluded.amount,
                    unit = excluded.unit,
                    cost_cny = excluded.cost_cny,
                    tariff_segment_type = excluded.tariff_segment_type,
                    reading_count = excluded.reading_count,
                    data_quality = excluded.data_quality,
                    remark = excluded.remark,
                    updated_at = now()
                """
            ),
            {
                "team_id": team_id,
                "source_system": _text(row.get("source_system")) or IMPORT_SOURCE_SYSTEM,
                "source_record_id": source_record_id,
                "energy_type_code": _text(row.get("energy_type_code")) or "electricity",
                "equipment_code": _nullable_text(row.get("equipment_code")),
                "equipment_name": _nullable_text(row.get("equipment_name")),
                "area_id": _nullable_text(row.get("area_id")),
                "area_name": _nullable_text(row.get("area_name")),
                "use_system_code": _nullable_text(row.get("use_system_code")),
                "use_system_name": _nullable_text(row.get("use_system_name")),
                "granularity": _text(row.get("granularity")) or "month",
                "period_start": period_start,
                "period_end": period_end,
                "amount": _required_decimal(row, "amount"),
                "unit": _text(row.get("unit")) or "kWh",
                "cost_cny": _decimal(row.get("cost_cny")),
                "tariff_segment_type": _nullable_text(row.get("tariff_segment_type")),
                "reading_count": _int(row.get("reading_count")),
                "data_quality": _data_quality(row.get("data_quality")),
                "remark": _remark(row.get("remark"), source_name, source_record_id),
            },
        )

    async def _upsert_production_output_fact(self, *, team_id: str, row: dict[str, Any], source_name: str | None) -> None:
        product_code = _required_text(row, "product_code")
        product_name = _nullable_text(row.get("product_name")) or product_code
        await self._session.execute(
            text(
                """
                insert into dataapp_productionproduct (
                    team_id, code, name, spec, category, output_kind, default_unit, standard_unit, is_enabled, remark, created_at, updated_at
                )
                values (
                    :team_id, :code, :name, :spec, :category, :output_kind, :default_unit, :standard_unit, true, :remark, now(), now()
                )
                on conflict on constraint uq_dataapp_productionproduct_team_code do update set
                    name = excluded.name,
                    spec = excluded.spec,
                    category = excluded.category,
                    output_kind = excluded.output_kind,
                    default_unit = excluded.default_unit,
                    standard_unit = excluded.standard_unit,
                    is_enabled = true,
                    remark = excluded.remark,
                    updated_at = now()
                """
            ),
            {
                "team_id": team_id,
                "code": product_code,
                "name": product_name,
                "spec": _nullable_text(row.get("product_spec")),
                "category": _nullable_text(row.get("category")),
                "output_kind": _text(row.get("output_kind")) or "product",
                "default_unit": _text(row.get("unit")) or "件",
                "standard_unit": _nullable_text(row.get("standard_unit")) or _text(row.get("unit")) or "件",
                "remark": _remark(row.get("remark"), source_name, product_code),
            },
        )
        await self._session.execute(
            text(
                """
                insert into dataapp_productionoutputfact (
                    team_id, source_system, source_record_id, production_order_no, batch_no, product_code,
                    product_name, product_spec, output_kind, period_start, period_end, good_qty, scrap_qty,
                    rework_qty, unit, standard_qty, standard_unit, quality_status, record_status, work_center_code,
                    line_code, area_id, area_name, equipment_code, equipment_name, remark, created_at, updated_at
                )
                values (
                    :team_id, :source_system, :source_record_id, :production_order_no, :batch_no, :product_code,
                    :product_name, :product_spec, :output_kind, :period_start, :period_end, :good_qty, :scrap_qty,
                    :rework_qty, :unit, :standard_qty, :standard_unit, :quality_status, :record_status, :work_center_code,
                    :line_code, :area_id, :area_name, :equipment_code, :equipment_name, :remark, now(), now()
                )
                on conflict on constraint uq_production_output_team_source_record do update set
                    production_order_no = excluded.production_order_no,
                    batch_no = excluded.batch_no,
                    product_code = excluded.product_code,
                    product_name = excluded.product_name,
                    product_spec = excluded.product_spec,
                    output_kind = excluded.output_kind,
                    period_start = excluded.period_start,
                    period_end = excluded.period_end,
                    good_qty = excluded.good_qty,
                    scrap_qty = excluded.scrap_qty,
                    rework_qty = excluded.rework_qty,
                    unit = excluded.unit,
                    standard_qty = excluded.standard_qty,
                    standard_unit = excluded.standard_unit,
                    quality_status = excluded.quality_status,
                    record_status = excluded.record_status,
                    work_center_code = excluded.work_center_code,
                    line_code = excluded.line_code,
                    area_id = excluded.area_id,
                    area_name = excluded.area_name,
                    equipment_code = excluded.equipment_code,
                    equipment_name = excluded.equipment_name,
                    remark = excluded.remark,
                    updated_at = now()
                """
            ),
            {
                "team_id": team_id,
                "source_system": _text(row.get("source_system")) or IMPORT_SOURCE_SYSTEM,
                "source_record_id": _required_text(row, "source_record_id"),
                "production_order_no": _nullable_text(row.get("production_order_no")),
                "batch_no": _nullable_text(row.get("batch_no")),
                "product_code": product_code,
                "product_name": product_name,
                "product_spec": _nullable_text(row.get("product_spec")),
                "output_kind": _text(row.get("output_kind")) or "product",
                "period_start": _date(row.get("period_start")),
                "period_end": _date(row.get("period_end")),
                "good_qty": _required_decimal(row, "good_qty"),
                "scrap_qty": _decimal(row.get("scrap_qty")),
                "rework_qty": _decimal(row.get("rework_qty")),
                "unit": _text(row.get("unit")) or "件",
                "standard_qty": _decimal(row.get("standard_qty")) or _required_decimal(row, "good_qty"),
                "standard_unit": _nullable_text(row.get("standard_unit")) or _text(row.get("unit")) or "件",
                "quality_status": _nullable_text(row.get("quality_status")),
                "record_status": _text(row.get("record_status")) or "confirmed",
                "work_center_code": _nullable_text(row.get("work_center_code")),
                "line_code": _nullable_text(row.get("line_code")),
                "area_id": _int(row.get("area_id")),
                "area_name": _nullable_text(row.get("area_name")),
                "equipment_code": _nullable_text(row.get("equipment_code")),
                "equipment_name": _nullable_text(row.get("equipment_name")),
                "remark": _remark(row.get("remark"), source_name, product_code),
            },
        )

def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _nullable_text(value: Any) -> str | None:
    text_value = _text(value)
    return text_value or None


def _required_text(row: dict[str, Any], field_name: str) -> str:
    value = _text(row.get(field_name))
    if not value:
        msg = f"缺少必填字段 {field_name}"
        raise EnergyImportValidationError(msg)
    return value


def _decimal(value: Any) -> Decimal | None:
    text_value = _text(value)
    if not text_value:
        return None
    return Decimal(text_value.replace(",", ""))


def _required_decimal(row: dict[str, Any], field_name: str) -> Decimal:
    value = _decimal(row.get(field_name))
    if value is None:
        msg = f"缺少必填数值 {field_name}"
        raise EnergyImportValidationError(msg)
    return value


def _int(value: Any) -> int | None:
    text_value = _text(value)
    if not text_value:
        return None
    return int(text_value)


def _date(value: Any) -> date:
    text_value = _text(value)
    if not text_value:
        msg = "缺少日期字段"
        raise EnergyImportValidationError(msg)
    if len(text_value) == YEAR_MONTH_LENGTH:
        text_value = f"{text_value}-01"
    return date.fromisoformat(text_value[:DATE_LENGTH])


def _datetime(value: Any) -> datetime:
    text_value = _text(value)
    if not text_value:
        msg = "缺少时间字段"
        raise EnergyImportValidationError(msg)
    if len(text_value) == YEAR_MONTH_LENGTH:
        text_value = f"{text_value}-01T00:00:00"
    elif len(text_value) == DATE_LENGTH:
        text_value = f"{text_value}T00:00:00"
    return datetime.fromisoformat(text_value.replace(" ", "T"))


def _data_quality(value: Any) -> str:
    text_value = _text(value).lower()
    if not text_value:
        return "measured"
    if any(token in text_value for token in ("estimate", "估", "allocation", "分摊", "allocated")):
        return "estimated"
    if any(token in text_value for token in ("manual", "手工")):
        return "manual"
    return "measured"


def _remark(value: Any, source_name: str | None, source_record_id: str) -> str:
    parts = [IMPORT_MARKER, f"source_record_id={source_record_id}"]
    if source_name:
        parts.append(f"source_name={source_name}")
    if _text(value):
        parts.append(_text(value))
    return " ".join(parts)


def _db_error_message(exc: SQLAlchemyError) -> str:
    original = getattr(exc, "orig", None)
    message = str(original or exc).replace("\n", " ")
    return message[:300]
