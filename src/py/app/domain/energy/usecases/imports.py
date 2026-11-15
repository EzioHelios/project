from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from litestar.exceptions import ClientException, PermissionDeniedException
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.db import models as m
from app.domain.energy.usecases.interval_facts import _normalize_energy_interval_fact_data
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
    preview: bool = False
    records: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    imported_ids: list[int] = field(default_factory=list[int])
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
        preview: bool = False,
    ) -> EnergyDatasetImportResult:
        team_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        if team_id is None:
            msg = "导入需要先选择一个企业租户。"
            raise PermissionDeniedException(detail=msg)

        normalized_dataset = dataset.strip()
        if normalized_dataset == "energy_interval_facts":
            return await self._import_energy_rows(rows=rows, source_name=source_name, preview=preview)
        if preview:
            raise ClientException(detail="该数据类型暂不支持预检", status_code=400)
        result = EnergyDatasetImportResult(dataset=normalized_dataset, received_count=len(rows))
        if len(rows) > MAX_IMPORT_ROWS:
            result.errors.append({"row_number": 0, "message": "单次导入最多支持 1000 行。"})
            return result

        for index, raw_row in enumerate(rows, start=2):
            try:
                row = {str(key).strip(): value for key, value in raw_row.items()}
                async with self._session.begin_nested():
                    if normalized_dataset == "production_output_facts":
                        await self._upsert_production_output_fact(
                            team_id=str(team_id), row=row, source_name=source_name
                        )
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

    async def _import_energy_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        source_name: str | None,
        preview: bool,
    ) -> EnergyDatasetImportResult:
        result = EnergyDatasetImportResult(dataset="energy_interval_facts", received_count=len(rows), preview=preview)
        if not rows or len(rows) > MAX_IMPORT_ROWS:
            result.skipped_count = len(rows)
            result.errors.append({"row_number": 0, "message": "请选择包含 1 至 1000 行数据的文件。"})
            return result
        team_id = self._session.info[TENANT_ID_SESSION_KEY]
        seen: set[tuple[str, str]] = set()
        for index, raw_row in enumerate(rows, start=2):
            payload: dict[str, Any] = {}
            try:
                data = {str(key).strip(): value for key, value in raw_row.items()}
                data["source_system"] = _text(data.get("source_system")) or IMPORT_SOURCE_SYSTEM
                data["data_quality"] = _data_quality(data.get("data_quality") or "imported")
                payload = await _normalize_energy_interval_fact_data(self._session, data)
                if not _text(data.get("source_record_id")):
                    identity = "|".join(
                        str(payload.get(key) or "")
                        for key in (
                            "energy_type_code",
                            "area_id",
                            "equipment_id",
                            "period_start",
                            "period_end",
                            "granularity",
                            "tariff_segment_type",
                        )
                    )
                    payload["source_record_id"] = "CSV-" + sha256(identity.encode()).hexdigest()[:32]
                key = (payload["source_system"], payload["source_record_id"])
                exists = await self._session.scalar(
                    select(m.EnergyIntervalFact.id).where(
                        m.EnergyIntervalFact.team_id == team_id,
                        m.EnergyIntervalFact.source_system == key[0],
                        m.EnergyIntervalFact.source_record_id == key[1],
                    )
                )
                if key in seen or exists is not None:
                    msg = "记录重复。未覆盖已有数据。请在列表中编辑已有记录。"
                    raise EnergyImportValidationError(msg)
                seen.add(key)
                record_id = None
                if not preview:
                    async with self._session.begin_nested():
                        saved = await self._session.scalar(
                            insert(m.EnergyIntervalFact)
                            .values(
                                team_id=team_id,
                                revision_no=1,
                                is_current=True,
                                source_snapshot={"source_name": source_name} if source_name else None,
                                **payload,
                            )
                            .on_conflict_do_nothing(constraint="uq_energy_interval_team_source_record")
                            .returning(m.EnergyIntervalFact)
                        )
                        if saved is None:
                            msg = "记录已由其他操作保存。未覆盖。请刷新后查看。"
                            raise EnergyImportValidationError(msg)
                        record_id = saved.id
                        payload = {key: getattr(saved, key) for key in payload}
                    result.imported_ids.append(record_id)
                    result.imported_count += 1
                result.records.append(
                    {
                        **_preview_payload(payload),
                        "id": record_id,
                        "row_number": index,
                        "source_name": source_name,
                        "status": "ready" if preview else "imported",
                    }
                )
            except (ClientException, TypeError, ValueError, InvalidOperation, SQLAlchemyError) as exc:
                result.skipped_count += 1
                message = (
                    exc.detail
                    if isinstance(exc, ClientException)
                    else "数据写入失败。请检查字段后重试。"
                    if isinstance(exc, SQLAlchemyError)
                    else str(exc)
                )
                result.errors.append({"row_number": index, "message": message})
                result.records.append(
                    {**_preview_payload(payload or raw_row), "row_number": index, "status": "error", "message": message}
                )
        if not preview:
            if result.imported_count:
                await self._session.commit()
            else:
                await self._session.rollback()
        return result

    async def _upsert_production_output_fact(
        self, *, team_id: str, row: dict[str, Any], source_name: str | None
    ) -> None:
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
    if any(token in text_value for token in ("import", "导入")):
        return "imported"
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


def _preview_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat()
        if isinstance(value, (datetime, date))
        else float(value)
        if isinstance(value, Decimal)
        else value
        for key, value in payload.items()
    }
