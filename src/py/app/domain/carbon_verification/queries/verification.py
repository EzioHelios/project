# ruff: noqa: RUF001
from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon.emission_calculator import compute_emission_result
from app.domain.carbon_verification.domain.policies import (
    MATERIAL_RULES,
    issue_for_status,
    material_readiness,
    record_material_status,
)
from app.domain.energy.controllers._utils import model_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


REPORT_TEMPLATE_PATH = "docs/评价方案/templates/工业企业温室气体排放盘查报告与核查材料包通用模板.docx"
REPORT_STANDARD_NAME = "工业其他行业企业温室气体排放核算方法与报告指南（试行）"
REPORT_STANDARD_CODE = "发改办气候〔2015〕1722号附件"
YEAR_MONTH_LENGTH = 7


@dataclass(frozen=True, slots=True)
class VerificationQuery:
    year: int | None = None
    status: str | None = None
    scope: str | None = None
    limit: int = 200
    offset: int = 0


class CarbonVerificationQueryService:
    """Read model service for organization-carbon report and verification materials."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def summary(self, query: VerificationQuery) -> dict[str, Any]:
        enterprise = await self._enterprise_profile()
        records = await self._filtered_records(query)
        issues = [issue for record in records if (issue := issue_for_status(record)) is not None]
        totals = _inventory_totals(records)
        statuses = [record["material_status"] for record in records]
        return {
            "enterprise": enterprise,
            "reporting_period": _reporting_period(query.year, records),
            "standard": _standard_payload(),
            "totals": totals,
            "status_summary": _count_by(records, "material_status"),
            "scope_summary": _scope_summary(records),
            "record_count": len(records),
            "issue_count": len(issues),
            "readiness": material_readiness(statuses),
            "template": _template_payload(),
        }

    async def evidence_manifest(self, query: VerificationQuery) -> dict[str, Any]:
        records = await self._filtered_records(query)
        attachments = await self._attachment_rows()
        attachment_keys = {
            (item.source_object_type, item.source_object_id)
            for item in attachments
            if item.source_object_type and item.source_object_id is not None
        }
        evidence_items = [_evidence_item(record) for record in records if record.get("attachment")]
        evidence_items.extend(_attachment_evidence_item(item) for item in attachments)
        missing_items = [
            record
            for record in records
            if not record.get("attachment") and (record.get("record_type"), record.get("record_id")) not in attachment_keys
        ]
        return {
            "items": evidence_items,
            "missing": [_record_ref(record) for record in missing_items],
            "summary": {
                "evidence_count": len(evidence_items),
                "attachment_count": len(attachments),
                "missing_evidence_count": len(missing_items),
                "record_count": len(records),
            },
            "filters": _filters(query),
        }

    async def material_package(self, query: VerificationQuery) -> dict[str, Any]:
        records = await self._filtered_records(query)
        evidence = await self.evidence_manifest(query)
        issues = await self.issues(query)
        audit_trail = await self.audit_trail(query)
        finding_count = int(await self._session.scalar(select(func.count(m.CarbonVerificationFinding.id))) or 0)
        groups = _material_groups(records, evidence, issues, audit_trail, finding_count=finding_count)
        return {
            "package_code": f"org-ghg-{query.year or 'all'}",
            "readiness": material_readiness([record["material_status"] for record in records]),
            "groups": groups,
            "manifest": _package_manifest(query, groups),
            "filters": _filters(query),
        }

    async def report_context(self, query: VerificationQuery) -> dict[str, Any]:
        records = await self._filtered_records(query)
        summary = await self.summary(query)
        issues = await self.issues(query)
        return {
            "template": _template_payload(),
            "standard": _standard_payload(),
            "enterprise": summary["enterprise"],
            "reporting_period": summary["reporting_period"],
            "inventory": {
                "totals": summary["totals"],
                "scope_summary": summary["scope_summary"],
                "source_summary": _source_summary(records),
            },
            "activity_data": [_activity_row(record) for record in records],
            "factor_parameters": _factor_rows(records),
            "quality_issues": issues["items"],
            "verification_findings": await self._finding_rows(),
            "verification_attachments": [_attachment_context_row(item) for item in await self._attachment_rows()],
            "export_fields": _template_field_map(),
            "filters": _filters(query),
        }

    async def issues(self, query: VerificationQuery) -> dict[str, Any]:
        records = await self._filtered_records(query)
        items = [issue for record in records if (issue := issue_for_status(record)) is not None]
        return {
            "items": items,
            "total": len(items),
            "summary": _count_by(items, "issue_type"),
            "filters": _filters(query),
        }

    async def audit_trail(self, query: VerificationQuery) -> dict[str, Any]:
        records = await self._filtered_records(query)
        record_keys = {(record["record_type"], record["record_id"]) for record in records}
        if not record_keys:
            return {"items": [], "total": 0, "filters": _filters(query)}
        logs = (
            (
                await self._session.execute(
                    select(m.CarbonAuditLog).order_by(m.CarbonAuditLog.created_at.desc()).limit(500)
                )
            )
            .scalars()
            .all()
        )
        items = [
            {
                "record_type": log.record_type,
                "record_id": log.record_id,
                "action": log.action,
                "comment": log.comment,
                "operator_id": str(log.operator_id) if log.operator_id else None,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
            if (log.record_type, log.record_id) in record_keys
        ]
        return {"items": items, "total": len(items), "filters": _filters(query)}

    async def _finding_rows(self) -> list[dict[str, Any]]:
        rows = (
            (
                await self._session.execute(
                    select(m.CarbonVerificationFinding).order_by(m.CarbonVerificationFinding.id.desc()).limit(200)
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "finding_no": row.finding_no,
                "issue_type": row.issue_type,
                "severity": row.severity,
                "title": row.title,
                "record_type": row.record_type,
                "record_id": row.record_id,
                "scope": row.scope,
                "display_name": row.display_name,
                "period": row.period,
                "status": row.status,
                "action_required": row.action_required,
                "correction_comment": row.correction_comment,
                "reviewer": row.reviewer,
                "closed_at": row.closed_at.isoformat() if row.closed_at else None,
            }
            for row in rows
        ]

    async def _attachment_rows(self) -> list[m.CarbonVerificationAttachment]:
        return (
            (
                await self._session.execute(
                    select(m.CarbonVerificationAttachment).order_by(m.CarbonVerificationAttachment.id.desc()).limit(500)
                )
            )
            .scalars()
            .all()
        )

    async def _enterprise_profile(self) -> dict[str, Any] | None:
        row = await self._session.scalar(select(m.EnterpriseInfo).order_by(m.EnterpriseInfo.id.desc()).limit(1))
        if row is None:
            return None
        return model_to_dict(row)

    async def _filtered_records(self, query: VerificationQuery) -> list[dict[str, Any]]:
        records = await self._load_scope_records()
        attachment_counts = _attachment_counts(await self._attachment_rows())
        for record in records:
            record["verification_attachment_count"] = attachment_counts.get((record["record_type"], record["record_id"]), 0)
            record["material_status"] = record_material_status(record)
        if query.year is not None:
            records = [record for record in records if _period_year(record.get("period")) == query.year]
        if query.status and query.status != "all":
            records = [record for record in records if record.get("status") == query.status]
        if query.scope and query.scope != "all":
            records = [record for record in records if record.get("scope") == query.scope]
        records.sort(key=lambda item: (_sort_period_key(item.get("period")), item["record_id"]), reverse=True)
        return records[query.offset : query.offset + max(1, min(query.limit, 500))]

    async def _load_scope_records(self) -> list[dict[str, Any]]:
        specs = [
            (m.Scope1MobileCombustion, "Scope1MobileCombustion", "范围1", "移动源燃烧", "record_date"),
            (m.Scope1StationaryCombustion, "Scope1StationaryCombustion", "范围1", "固定源燃烧", "period_start"),
            (m.Scope1RefrigerantLeak, "Scope1RefrigerantLeak", "范围1", "制冷剂逸散", "fill_date"),
            (m.Scope2ElectricityBill, "Scope2ElectricityBill", "范围2", "外购电力账单", "billing_month"),
            (m.Scope2MeterAggregate, "Scope2MeterAggregate", "范围2", "电表月度聚合", "billing_month"),
            (m.Scope2PurchasedEnergy, "Scope2PurchasedEnergy", "范围2", "外购热力/蒸汽/冷量", "period_start"),
            (m.Scope3WasteDisposal, "Scope3WasteDisposal", "范围3", "废弃物处理", "date"),
            (m.Scope3ThirdPartyTransport, "Scope3ThirdPartyTransport", "范围3", "外购运输", "created_at"),
        ]
        records: list[dict[str, Any]] = []
        for model, record_type, scope, label, period_field in specs:
            rows = (await self._session.execute(select(model))).scalars().all()
            records.extend([await self._record_payload(row, record_type, scope, label, period_field) for row in rows])
        return records

    async def _record_payload(self, row: Any, record_type: str, scope: str, label: str, period_field: str) -> dict[str, Any]:
        data = model_to_dict(row)
        computation = await self._computation_payload(row, data)
        payload = {
            "record_type": record_type,
            "record_label": label,
            "record_id": row.id,
            "scope": scope,
            "display_name": _display_name(row),
            "period": _period_value(row, period_field),
            "status": data.get("status"),
            "attachment": data.get("attachment"),
            "activity_amount": computation.get("activity_amount"),
            "activity_unit": computation.get("activity_unit"),
            "computed_co2e": computation.get("computed_co2e"),
            "factor_source": computation.get("factor_source"),
            "factor_year": computation.get("factor_year"),
            "factor_unit": computation.get("factor_unit"),
            "calc_status": computation.get("calc_status"),
            "source": data,
        }
        payload["material_status"] = record_material_status(payload)
        return payload

    async def _computation_payload(self, row: Any, data: dict[str, Any]) -> dict[str, Any]:
        if isinstance(row, (m.Scope2ElectricityBill, m.Scope2MeterAggregate, m.Scope2PurchasedEnergy)):
            return {
                "activity_amount": data.get("activity_amount") or data.get("total_kwh") or data.get("amount"),
                "activity_unit": data.get("activity_unit") or data.get("unit") or "kWh",
                "computed_co2e": data.get("computed_co2e"),
                "factor_source": data.get("factor_source"),
                "factor_year": data.get("factor_year"),
                "factor_unit": data.get("factor_unit"),
                "calc_status": data.get("calc_status"),
            }
        resolved = _activity_spec(row)
        if resolved is None:
            return {"calc_status": "unsupported"}
        scope, category, sub_category, amount, unit, year = resolved
        computation = await compute_emission_result(self._session, scope, category, sub_category, amount, unit, year)
        if computation is None:
            return {
                "activity_amount": _float(amount),
                "activity_unit": unit,
                "computed_co2e": None,
                "factor_source": None,
                "factor_year": year,
                "factor_unit": None,
                "calc_status": "missing_factor",
            }
        return {
            "activity_amount": _float(computation.activity_amount),
            "activity_unit": computation.activity_unit,
            "computed_co2e": _float(computation.co2e),
            "factor_source": computation.factor_source,
            "factor_year": computation.factor_year,
            "factor_unit": computation.factor_unit,
            "calc_status": "ready",
        }


def _activity_spec(row: Any) -> tuple[str, str, str, Any, str, int | None] | None:
    if isinstance(row, m.Scope1MobileCombustion):
        return ("scope1", "fuel", row.fuel_type, row.amount, row.unit, row.record_date.year)
    if isinstance(row, m.Scope1StationaryCombustion):
        return ("scope1", "fuel", row.fuel_type, row.amount, row.unit, row.period_start.year)
    if isinstance(row, m.Scope1RefrigerantLeak):
        return ("scope1", "refrigerant", row.refrigerant_type, row.amount_kg, "kg", row.fill_date.year)
    if isinstance(row, m.Scope3WasteDisposal):
        return ("scope3", "waste", row.category, row.weight_ton, "t", row.date.year)
    if isinstance(row, m.Scope3ThirdPartyTransport):
        amount = Decimal(str(row.distance_km or 0)) * Decimal(str(row.load_ton or 0))
        year = row.created_at.year if row.created_at else None
        return ("scope3", "transport", row.vehicle_type, amount, "t·km", year)
    return None


def _display_name(row: Any) -> str:
    for key in ("asset_name", "facility_name", "device_name", "account_number", "ammeter_name", "energy_type_name", "category", "waybill_no"):
        value = getattr(row, key, None)
        if value:
            return str(value)
    return f"{type(row).__name__}#{row.id}"


def _period_value(row: Any, field: str) -> str | None:
    value = getattr(row, field, None)
    if isinstance(value, str):
        return value[:YEAR_MONTH_LENGTH] if len(value) >= YEAR_MONTH_LENGTH else value
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m")
    return None


def _period_year(value: Any) -> int | None:
    if not value:
        return None
    try:
        return int(str(value)[:4])
    except ValueError:
        return None


def _sort_period_key(value: Any) -> tuple[int, int]:
    if not value:
        return (0, 0)
    try:
        year, month = str(value)[:7].split("-", 1)
        return (int(year), int(month))
    except (TypeError, ValueError):
        return (0, 0)


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _inventory_totals(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(float(record.get("computed_co2e") or 0) for record in records)
    return {
        "total_kg_co2e": round(total, 6),
        "total_t_co2e": round(total / 1000, 6),
        "approved_kg_co2e": round(sum(float(record.get("computed_co2e") or 0) for record in records if record.get("status") == "approved"), 6),
        "missing_result_count": sum(1 for record in records if record.get("computed_co2e") in (None, "")),
    }


def _scope_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        scope = str(record.get("scope") or "未分组")
        item = grouped.setdefault(scope, {"scope": scope, "record_count": 0, "kg_co2e": 0.0})
        item["record_count"] += 1
        item["kg_co2e"] += float(record.get("computed_co2e") or 0)
    return [
        {**item, "kg_co2e": round(item["kg_co2e"], 6), "t_co2e": round(item["kg_co2e"] / 1000, 6)}
        for item in grouped.values()
    ]


def _source_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        key = f"{record.get('scope')}:{record.get('record_label')}"
        item = grouped.setdefault(
            key,
            {"scope": record.get("scope"), "record_label": record.get("record_label"), "record_count": 0, "kg_co2e": 0.0},
        )
        item["record_count"] += 1
        item["kg_co2e"] += float(record.get("computed_co2e") or 0)
    return [
        {**item, "kg_co2e": round(item["kg_co2e"], 6), "t_co2e": round(item["kg_co2e"] / 1000, 6)}
        for item in grouped.values()
    ]


def _factor_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, Any, Any]] = set()
    items = []
    for record in records:
        key = (record.get("factor_source"), record.get("factor_year"), record.get("factor_unit"))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "factor_source": record.get("factor_source"),
                "factor_year": record.get("factor_year"),
                "factor_unit": record.get("factor_unit"),
                "used_by": record.get("record_label"),
                "scope": record.get("scope"),
            }
        )
    return items


def _activity_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": record.get("record_type"),
        "record_id": record.get("record_id"),
        "scope": record.get("scope"),
        "source_category": record.get("record_label"),
        "activity_name": record.get("display_name"),
        "period": record.get("period"),
        "activity_amount": record.get("activity_amount"),
        "activity_unit": record.get("activity_unit"),
        "computed_co2e": record.get("computed_co2e"),
        "status": record.get("status"),
        "evidence_path": record.get("attachment"),
    }


def _evidence_item(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_code": f"EV-{record['record_type']}-{record['record_id']}",
        "record_type": record.get("record_type"),
        "record_id": record.get("record_id"),
        "scope": record.get("scope"),
        "display_name": record.get("display_name"),
        "period": record.get("period"),
        "path": record.get("attachment"),
        "material_status": record.get("material_status"),
    }


def _attachment_evidence_item(row: m.CarbonVerificationAttachment) -> dict[str, Any]:
    return {
        "evidence_code": row.attachment_no,
        "record_type": row.source_object_type,
        "record_id": row.source_object_id,
        "scope": row.source_scope,
        "display_name": row.source_object_label or row.title,
        "period": row.source_period,
        "path": row.file_path,
        "material_status": row.status,
        "attachment_type": row.attachment_type,
        "file_name": row.file_name,
        "sha256": row.sha256,
        "source": "verification_attachment",
    }


def _attachment_context_row(row: m.CarbonVerificationAttachment) -> dict[str, Any]:
    return {
        "attachment_no": row.attachment_no,
        "material_group": row.material_group,
        "attachment_type": row.attachment_type,
        "title": row.title,
        "source_object_type": row.source_object_type,
        "source_object_id": row.source_object_id,
        "source_object_label": row.source_object_label,
        "source_scope": row.source_scope,
        "source_period": row.source_period,
        "file_name": row.file_name,
        "file_path": row.file_path,
        "sha256": row.sha256,
        "status": row.status,
        "confidence_level": row.confidence_level,
    }


def _attachment_counts(rows: list[m.CarbonVerificationAttachment]) -> dict[tuple[str, int], int]:
    counts: dict[tuple[str, int], int] = {}
    for row in rows:
        if row.source_object_id is None:
            continue
        key = (row.source_object_type, row.source_object_id)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _record_ref(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": record.get("record_type"),
        "record_id": record.get("record_id"),
        "scope": record.get("scope"),
        "display_name": record.get("display_name"),
        "period": record.get("period"),
        "material_status": record.get("material_status"),
    }


def _material_groups(
    records: list[dict[str, Any]],
    evidence: dict[str, Any],
    issues: dict[str, Any],
    audit_trail: dict[str, Any],
    *,
    finding_count: int = 0,
) -> list[dict[str, Any]]:
    counts = {
        "boundary": 1,
        "inventory": len(records),
        "activity": len(records),
        "factor": len(_factor_rows(records)),
        "evidence": evidence["summary"]["evidence_count"],
        "audit": audit_trail["total"],
        "quality": issues["total"] + finding_count,
    }
    readiness = material_readiness([record["material_status"] for record in records])
    return [
        {
            "code": rule.code,
            "title": rule.title,
            "material_group": rule.material_group,
            "required": rule.required,
            "item_count": counts.get(rule.material_group, 0),
            "status": readiness if rule.material_group in {"inventory", "activity", "factor", "evidence"} else "ready",
        }
        for rule in MATERIAL_RULES
    ]


def _package_manifest(query: VerificationQuery, groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    year = query.year or "all"
    return [
        {"path": f"report/{year}-organization-ghg-report.docx", "type": "report", "source": REPORT_TEMPLATE_PATH},
        {"path": f"report/{year}-organization-ghg-report.pdf", "type": "report_pdf", "source": "rendered_from_docx"},
        {"path": f"data/{year}-activity-data.xlsx", "type": "activity_data", "source": "carbon_accounting"},
        {"path": f"data/{year}-factor-parameters.xlsx", "type": "factor_parameters", "source": "factor_library"},
        {"path": f"evidence/{year}/", "type": "evidence_folder", "source": "record_attachments"},
        {"path": f"audit/{year}-review-trail.xlsx", "type": "audit_trail", "source": "carbon_audit_log"},
        {"path": "manifest.json", "type": "manifest", "source": {"groups": groups}},
    ]


def _template_field_map() -> list[dict[str, str]]:
    return [
        {"field": "{{ enterprise_name }}", "source": "enterprise.name"},
        {"field": "{{ org_code }}", "source": "enterprise.unify_code"},
        {"field": "{{ report_year }}", "source": "reporting_period.year"},
        {"field": "{{ accounting_standard_name }}", "source": "standard.name"},
        {"field": "{{ scope_summary }}", "source": "inventory.scope_summary"},
        {"field": "{{ activity_data }}", "source": "activity_data"},
        {"field": "{{ factor_parameters }}", "source": "factor_parameters"},
        {"field": "{{ evidence_manifest }}", "source": "evidence_manifest.items"},
        {"field": "{{ quality_issues }}", "source": "quality_issues"},
    ]


def _reporting_period(year: int | None, records: list[dict[str, Any]]) -> dict[str, Any]:
    periods = sorted({record.get("period") for record in records if record.get("period")})
    return {
        "year": year or (_period_year(periods[-1]) if periods else None),
        "period_start": periods[0] if periods else None,
        "period_end": periods[-1] if periods else None,
    }


def _standard_payload() -> dict[str, str]:
    return {
        "name": REPORT_STANDARD_NAME,
        "code": REPORT_STANDARD_CODE,
        "source_name": "国家发展改革委办公厅",
        "applicable_scope": "工业其他行业企业组织层面温室气体排放报告",
    }


def _template_payload() -> dict[str, str]:
    return {
        "name": "工业企业温室气体排放盘查报告与核查材料包通用模板",
        "path": REPORT_TEMPLATE_PATH,
        "format": "docx",
    }


def _filters(query: VerificationQuery) -> dict[str, Any]:
    return {"year": query.year, "status": query.status, "scope": query.scope, "limit": query.limit, "offset": query.offset}


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        result[value] = result.get(value, 0) + 1
    return result
