from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

WMS_PRICE_SOURCE_SYSTEMS = (
    "wms_out_standard",
    "wms_out_actual_average",
    "wms_out_base_period",
)
OUTPUT_KIND_MATERIAL_HANDLING = "material_handling"


@dataclass(slots=True)
class WmsProductionDataImportResult:
    """Result summary for generated product denominator sample data."""

    products_upserted: int = 0
    prices_deleted: int = 0
    prices_inserted: int = 0
    output_facts_upserted: int = 0
    skipped_missing_code: int = 0
    skipped_missing_date: int = 0
    skipped_missing_quantity: int = 0


@dataclass(slots=True)
class _ProductDraft:
    team_id: UUID
    code: str
    descriptions: Counter[str]
    units: Counter[str]


@dataclass(slots=True)
class _PriceDraft:
    team_id: UUID
    product_code: str
    min_date: date
    max_date: date
    total_qty: Decimal = Decimal(0)
    total_amount: Decimal = Decimal(0)
    base_qty: Decimal = Decimal(0)
    base_amount: Decimal = Decimal(0)
    base_year: int | None = None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _clip(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    return value[:max_length]


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _positive_decimal(value: Any) -> Decimal | None:
    decimal_value = _to_decimal(value)
    if decimal_value is None or decimal_value <= 0:
        return None
    return decimal_value


def _parse_date(value: Any) -> date | None:
    text_value = _clean_text(value)
    if text_value is None:
        return None
    normalized = text_value.replace(".", "-").replace("/", "-")
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", normalized)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _split_product_description(description: str | None, code: str) -> tuple[str, str | None, str | None]:
    source = _clean_text(description) or code
    parts = [part.strip() for part in re.split(r"[,\uFF0C]", source, maxsplit=1)]
    name = parts[0] or code
    spec = parts[1] if len(parts) > 1 and parts[1] else None
    category = re.split(r"[-\uFF0D/\uFF0F]", name, maxsplit=1)[0].strip() or name
    return _clip(name, 128) or code, _clip(spec, 128), _clip(category, 64)


def _choose_counter_value(counter: Counter[str]) -> str | None:
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def import_wms_production_data(
    session: AsyncSession,
    *,
    limit: int | None = None,
    dry_run: bool = False,
) -> WmsProductionDataImportResult:
    """Generate product, price and product batch quantity samples from WMS inbound/outbound records."""

    result = WmsProductionDataImportResult()
    await session.execute(text("select set_config('app.tenant_bypass', 'true', true)"))

    outbound_rows = (
        await session.execute(
            text(
                """
                select id, team_id, ckdbh, wlbm, wlms, pc, jldw, sfsl, dj, je, gzrq, ckdd, gc, lldh
                from dataapp_outmoney
                order by id
                limit coalesce(:limit, 2147483647)
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()
    inbound_rows = (
        await session.execute(
            text(
                """
                select id, team_id, rkdbh, wlbh, wlms, pc, jldw, shsl, shdj, shje, rkrq, ckmc
                from dataapp_inmoney
                order by id
                limit coalesce(:limit, 2147483647)
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()

    product_rows = _build_product_rows(outbound_rows, inbound_rows)
    price_rows = _build_price_rows(outbound_rows)
    output_rows, skipped = _build_output_rows(outbound_rows, inbound_rows)

    result.products_upserted = len(product_rows)
    result.prices_inserted = len(price_rows)
    result.output_facts_upserted = len(output_rows)
    result.skipped_missing_code = skipped["missing_code"]
    result.skipped_missing_date = skipped["missing_date"]
    result.skipped_missing_quantity = skipped["missing_quantity"]

    if dry_run:
        await session.rollback()
        return result

    if product_rows:
        await _upsert_products(session, product_rows)
    if price_rows:
        result.prices_deleted = await _replace_prices(session, price_rows)
    if output_rows:
        await _upsert_output_facts(session, output_rows)

    await session.commit()
    return result


def _build_product_rows(outbound_rows: list[Any], inbound_rows: list[Any]) -> list[dict[str, Any]]:
    drafts: dict[tuple[UUID, str], _ProductDraft] = {}

    def add_product(team_id: UUID, code_value: Any, description_value: Any, unit_value: Any) -> None:
        code = _clean_text(code_value)
        if code is None:
            return
        key = (team_id, code)
        draft = drafts.get(key)
        if draft is None:
            draft = _ProductDraft(team_id=team_id, code=code, descriptions=Counter(), units=Counter())
            drafts[key] = draft
        description = _clean_text(description_value)
        unit = _clean_text(unit_value)
        if description:
            draft.descriptions[description] += 1
        if unit:
            draft.units[unit] += 1

    for row in outbound_rows:
        add_product(row["team_id"], row["wlbm"], row["wlms"], row["jldw"])
    for row in inbound_rows:
        add_product(row["team_id"], row["wlbh"], row["wlms"], row["jldw"])

    now = _now()
    product_rows: list[dict[str, Any]] = []
    for draft in drafts.values():
        description = _choose_counter_value(draft.descriptions)
        unit = _clip(_choose_counter_value(draft.units), 16)
        name, spec, category = _split_product_description(description, draft.code)
        product_rows.append(
            {
                "team_id": draft.team_id,
                "code": _clip(draft.code, 64),
                "name": name,
                "spec": spec,
                "category": category,
                "output_kind": OUTPUT_KIND_MATERIAL_HANDLING,
                "default_unit": unit,
                "standard_unit": unit,
                "is_enabled": True,
                "remark": "由 WMS 入库/出库流水生成, 用于产品强度和产值强度样本。",
                "created_at": now,
                "updated_at": now,
            }
        )
    return product_rows


def _build_price_rows(outbound_rows: list[Any]) -> list[dict[str, Any]]:
    drafts: dict[tuple[UUID, str], _PriceDraft] = {}
    first_years: dict[tuple[UUID, str], int] = {}

    for row in outbound_rows:
        team_id = row["team_id"]
        code = _clean_text(row["wlbm"])
        quantity = _positive_decimal(row["sfsl"])
        price = _positive_decimal(row["dj"])
        period = _parse_date(row["gzrq"])
        if code is None or quantity is None or price is None or period is None:
            continue
        amount = _positive_decimal(row["je"]) or quantity * price
        key = (team_id, code)
        first_years[key] = min(first_years[key], period.year) if key in first_years else period.year
        draft = drafts.get(key)
        if draft is None:
            draft = _PriceDraft(team_id=team_id, product_code=code, min_date=period, max_date=period)
            drafts[key] = draft
        draft.min_date = min(draft.min_date, period)
        draft.max_date = max(draft.max_date, period)
        draft.total_qty += quantity
        draft.total_amount += amount

    for row in outbound_rows:
        team_id = row["team_id"]
        code = _clean_text(row["wlbm"])
        quantity = _positive_decimal(row["sfsl"])
        price = _positive_decimal(row["dj"])
        period = _parse_date(row["gzrq"])
        if code is None or quantity is None or price is None or period is None:
            continue
        key = (team_id, code)
        draft = drafts.get(key)
        if draft is None or first_years.get(key) != period.year:
            continue
        amount = _positive_decimal(row["je"]) or quantity * price
        draft.base_year = period.year
        draft.base_qty += quantity
        draft.base_amount += amount

    now = _now()
    price_rows: list[dict[str, Any]] = []
    for draft in drafts.values():
        if draft.total_qty <= 0 or draft.total_amount <= 0:
            continue
        standard_price = (draft.total_amount / draft.total_qty).quantize(Decimal("0.000001"))
        price_rows.extend(
            [
                _price_row(
                    draft,
                    price_type="standard_price",
                    price=standard_price,
                    valid_from=draft.min_date,
                    source_system="wms_out_standard",
                    now=now,
                ),
                _price_row(
                    draft,
                    price_type="actual_average_price",
                    price=standard_price,
                    valid_from=draft.min_date,
                    source_system="wms_out_actual_average",
                    now=now,
                ),
            ]
        )
        if draft.base_qty > 0 and draft.base_amount > 0 and draft.base_year is not None:
            base_price = (draft.base_amount / draft.base_qty).quantize(Decimal("0.000001"))
            price_rows.append(
                _price_row(
                    draft,
                    price_type="base_period_price",
                    price=base_price,
                    valid_from=date(draft.base_year, 1, 1),
                    source_system="wms_out_base_period",
                    now=now,
                )
            )
    return price_rows


def _price_row(
    draft: _PriceDraft,
    *,
    price_type: str,
    price: Decimal,
    valid_from: date,
    source_system: str,
    now: datetime,
) -> dict[str, Any]:
    return {
        "team_id": draft.team_id,
        "product_code": _clip(draft.product_code, 64),
        "price_type": price_type,
        "price": price,
        "currency": "CNY",
        "tax_included": False,
        "valid_from": valid_from,
        "valid_to": None,
        "source_system": source_system,
        "source_record_id": _clip(f"{source_system}:{draft.team_id}:{draft.product_code}", 128),
        "remark": "由 WMS 出库单价按数量加权生成。",
        "created_at": now,
        "updated_at": now,
    }


def _build_output_rows(outbound_rows: list[Any], inbound_rows: list[Any]) -> tuple[list[dict[str, Any]], Counter[str]]:
    output_rows: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    now = _now()

    for row in outbound_rows:
        output_row = _output_row_from_wms_out(row, now, skipped)
        if output_row is not None:
            output_rows.append(output_row)
    for row in inbound_rows:
        output_row = _output_row_from_wms_in(row, now, skipped)
        if output_row is not None:
            output_rows.append(output_row)

    return output_rows, skipped


def _output_row_from_wms_out(row: Any, now: datetime, skipped: Counter[str]) -> dict[str, Any] | None:
    code = _clean_text(row["wlbm"])
    if code is None:
        skipped["missing_code"] += 1
        return None
    quantity = _positive_decimal(row["sfsl"])
    if quantity is None:
        skipped["missing_quantity"] += 1
        return None
    period = _parse_date(row["gzrq"])
    if period is None:
        skipped["missing_date"] += 1
        return None
    name, spec, _category = _split_product_description(_clean_text(row["wlms"]), code)
    return _output_row(
        row=row,
        now=now,
        source_system="wms_out",
        source_record_id=f"wms_out:{row['id']}",
        production_order_no=_clean_text(row["ckdbh"]) or _clean_text(row["lldh"]),
        batch_no=_clean_text(row["pc"]),
        code=code,
        name=name,
        spec=spec,
        period=period,
        quantity=quantity,
        unit=_clean_text(row["jldw"]) or "件",
        area_name=_clean_text(row["ckdd"]),
        remark="由 WMS 出库流水生成: 出库处理量样本。",
    )


def _output_row_from_wms_in(row: Any, now: datetime, skipped: Counter[str]) -> dict[str, Any] | None:
    code = _clean_text(row["wlbh"])
    if code is None:
        skipped["missing_code"] += 1
        return None
    quantity = _positive_decimal(row["shsl"])
    if quantity is None:
        skipped["missing_quantity"] += 1
        return None
    period = _parse_date(row["rkrq"])
    if period is None:
        skipped["missing_date"] += 1
        return None
    name, spec, _category = _split_product_description(_clean_text(row["wlms"]), code)
    return _output_row(
        row=row,
        now=now,
        source_system="wms_in",
        source_record_id=f"wms_in:{row['id']}",
        production_order_no=_clean_text(row["rkdbh"]),
        batch_no=_clean_text(row["pc"]),
        code=code,
        name=name,
        spec=spec,
        period=period,
        quantity=quantity,
        unit=_clean_text(row["jldw"]) or "件",
        area_name=_clean_text(row["ckmc"]),
        remark="由 WMS 入库流水生成: 入库处理量样本。",
    )


def _output_row(
    *,
    row: Any,
    now: datetime,
    source_system: str,
    source_record_id: str,
    production_order_no: str | None,
    batch_no: str | None,
    code: str,
    name: str,
    spec: str | None,
    period: date,
    quantity: Decimal,
    unit: str,
    area_name: str | None,
    remark: str,
) -> dict[str, Any]:
    return {
        "team_id": row["team_id"],
        "source_system": source_system,
        "source_record_id": _clip(source_record_id, 128),
        "production_order_no": _clip(production_order_no, 64),
        "batch_no": _clip(batch_no, 64),
        "product_code": _clip(code, 64),
        "product_name": name,
        "product_spec": spec,
        "output_kind": OUTPUT_KIND_MATERIAL_HANDLING,
        "period_start": period,
        "period_end": period,
        "good_qty": quantity,
        "scrap_qty": None,
        "rework_qty": None,
        "unit": _clip(unit, 16) or "件",
        "standard_qty": quantity,
        "standard_unit": _clip(unit, 16) or "件",
        "quality_status": None,
        "record_status": "confirmed",
        "work_center_code": None,
        "line_code": None,
        "area_id": None,
        "area_name": _clip(area_name, 128),
        "equipment_code": None,
        "equipment_name": None,
        "remark": remark,
        "created_at": now,
        "updated_at": now,
    }


async def _upsert_products(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    await _execute_chunks(
        session,
        """
        insert into dataapp_productionproduct (
            team_id, code, name, spec, category, output_kind, default_unit, standard_unit, is_enabled, remark,
            created_at, updated_at
        )
        values (
            :team_id, :code, :name, :spec, :category, :output_kind, :default_unit, :standard_unit, :is_enabled,
            :remark, :created_at, :updated_at
        )
        on conflict (team_id, code) do update set
            name = excluded.name,
            spec = excluded.spec,
            category = excluded.category,
            output_kind = excluded.output_kind,
            default_unit = excluded.default_unit,
            standard_unit = excluded.standard_unit,
            is_enabled = true,
            remark = excluded.remark,
            updated_at = excluded.updated_at
        """,
        rows,
    )


async def _replace_prices(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    deleted = (
        await session.execute(
            text(
                """
                delete from dataapp_productprice
                where source_system in ('wms_out_standard', 'wms_out_actual_average', 'wms_out_base_period')
                """
            )
        )
    ).rowcount
    await _execute_chunks(
        session,
        """
        insert into dataapp_productprice (
            team_id, product_code, price_type, price, currency, tax_included, valid_from, valid_to, source_system,
            source_record_id, remark, created_at, updated_at
        )
        values (
            :team_id, :product_code, :price_type, :price, :currency, :tax_included, :valid_from, :valid_to,
            :source_system, :source_record_id, :remark, :created_at, :updated_at
        )
        """,
        rows,
    )
    return deleted or 0


async def _upsert_output_facts(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    await _execute_chunks(
        session,
        """
        insert into dataapp_productionoutputfact (
            team_id, source_system, source_record_id, production_order_no, batch_no, product_code, product_name,
            product_spec, output_kind, period_start, period_end, good_qty, scrap_qty, rework_qty, unit, standard_qty,
            standard_unit, quality_status, record_status, work_center_code, line_code, area_id, area_name,
            equipment_code, equipment_name, remark, created_at, updated_at
        )
        values (
            :team_id, :source_system, :source_record_id, :production_order_no, :batch_no, :product_code,
            :product_name, :product_spec, :output_kind, :period_start, :period_end, :good_qty, :scrap_qty,
            :rework_qty, :unit, :standard_qty, :standard_unit, :quality_status, :record_status, :work_center_code,
            :line_code, :area_id, :area_name, :equipment_code, :equipment_name, :remark, :created_at, :updated_at
        )
        on conflict (team_id, source_system, source_record_id) do update set
            production_order_no = excluded.production_order_no,
            batch_no = excluded.batch_no,
            product_code = excluded.product_code,
            product_name = excluded.product_name,
            product_spec = excluded.product_spec,
            output_kind = excluded.output_kind,
            period_start = excluded.period_start,
            period_end = excluded.period_end,
            good_qty = excluded.good_qty,
            unit = excluded.unit,
            standard_qty = excluded.standard_qty,
            standard_unit = excluded.standard_unit,
            record_status = excluded.record_status,
            area_name = excluded.area_name,
            remark = excluded.remark,
            updated_at = excluded.updated_at
        """,
        rows,
    )


async def _execute_chunks(session: AsyncSession, sql: str, rows: list[dict[str, Any]], chunk_size: int = 1000) -> None:
    statement = text(sql)
    for index in range(0, len(rows), chunk_size):
        await session.execute(statement, rows[index : index + chunk_size])
