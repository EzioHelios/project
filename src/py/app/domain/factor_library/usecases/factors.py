"""Application service for enterprise calculation factor maintenance."""

from __future__ import annotations

import base64
import csv
import io
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from litestar.exceptions import ClientException, PermissionDeniedException
from sqlalchemy import func, or_, select

from app.db import models as m
from app.domain.factor_library.schemas import (
    ActivityFactorCandidateResponse,
    ApplyActivityFactorResponse,
    CalculationFactorImportIssue,
    CalculationFactorImportPreviewResponse,
    CalculationFactorImportRow,
    CalculationFactorResponse,
    CalculationFactorWriteRequest,
)
from app.domain.ghg_inventory.models import (
    GhgActivityRecord,
    GhgCalculationMethodDefinition,
    GhgMethodParameterDefinition,
    GhgParameterValue,
)
from app.lib.tenancy import require_session_tenant_id, session_tenant_id

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement


TEMPLATE_COLUMNS = (
    "scope",
    "category",
    "sub_category",
    "unit",
    "factor_value",
    "factor_unit",
    "year",
    "source",
    "source_system",
    "source_snapshot_id",
    "raw_record_id",
    "projection_status",
    "review_status",
    "is_active",
    "note",
)

TEMPLATE_TEXT = ",".join(TEMPLATE_COLUMNS) + "\n" + (
    "scope2,electricity,grid_electricity_jiangsu,kWh,0.5827,kgCO2e/kWh,2026,"
    "企业批准电力排放因子,enterprise,,,manual,approved,true,适用于购入电力活动数据\n"
)

SCOPE_VALUES = {"scope1", "scope2", "scope3"}
PROJECTION_STATUS_VALUES = {"manual", "direct", "derived"}
REVIEW_STATUS_VALUES = {"draft", "pending", "approved", "rejected"}
SOURCE_SYSTEM_VALUES = {"enterprise", "custom_approved", "manual", "ncsc_ghg_efdb", "ipcc", "ecoinvent"}
MIN_FACTOR_YEAR = 1900
MAX_FACTOR_YEAR = 2100


class CalculationFactorMaintenance:
    """Maintain shared-readable and tenant-owned calculation factors."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_factors(
        self,
        *,
        limit: int,
        offset: int,
        keyword: str | None,
        scope: str | None,
        category: str | None,
        is_active: bool | None,
        owner: str | None,
    ) -> dict[str, Any]:
        tenant_id = session_tenant_id(self.session)
        filters = self._read_scope_filters(tenant_id)
        if scope:
            filters.append(m.EmissionFactor.scope == _normalize_code(scope))
        if category:
            filters.append(m.EmissionFactor.category == _normalize_code(category))
        if is_active is not None:
            filters.append(m.EmissionFactor.is_active == is_active)
        if owner == "enterprise":
            if tenant_id is None:
                filters.append(m.EmissionFactor.team_id.is_not(None))
            else:
                filters.append(m.EmissionFactor.team_id == tenant_id)
        elif owner == "shared":
            filters.append(m.EmissionFactor.team_id.is_(None))
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            filters.append(
                or_(
                    m.EmissionFactor.category.ilike(pattern),
                    m.EmissionFactor.sub_category.ilike(pattern),
                    m.EmissionFactor.unit.ilike(pattern),
                    m.EmissionFactor.factor_unit.ilike(pattern),
                    m.EmissionFactor.source.ilike(pattern),
                    m.EmissionFactor.source_system.ilike(pattern),
                    m.EmissionFactor.note.ilike(pattern),
                )
            )
        limit_clamped = max(10, min(limit, 200))
        offset_clamped = max(0, offset)
        total = int(await self.session.scalar(select(func.count()).select_from(m.EmissionFactor).where(*filters)) or 0)
        rows = list(
            (
                await self.session.scalars(
                    select(m.EmissionFactor)
                    .where(*filters)
                    .order_by(m.EmissionFactor.team_id.is_(None), m.EmissionFactor.year.desc(), m.EmissionFactor.id.desc())
                    .limit(limit_clamped)
                    .offset(offset_clamped)
                )
            ).all()
        )
        return {
            "items": [self.factor_payload(row, tenant_id) for row in rows],
            "total": total,
            "limit": limit_clamped,
            "offset": offset_clamped,
        }

    async def get_factor(self, factor_id: int) -> CalculationFactorResponse:
        factor = await self._get_readable_factor(factor_id)
        return self.factor_payload(factor, session_tenant_id(self.session))

    async def create_factor(self, data: CalculationFactorWriteRequest) -> CalculationFactorResponse:
        tenant_id = require_session_tenant_id(self.session)
        payload = self._validated_payload(data)
        existing = await self._find_tenant_factor(tenant_id, payload)
        if existing is not None:
            msg = "同一租户、范围、类别、子类、单位和年份的计算因子已存在"
            raise ClientException(detail=msg, status_code=400)
        factor = m.EmissionFactor(team_id=tenant_id, **payload)
        self.session.add(factor)
        await self.session.commit()
        return self.factor_payload(factor, tenant_id)

    async def update_factor(self, factor_id: int, data: CalculationFactorWriteRequest) -> CalculationFactorResponse:
        tenant_id = require_session_tenant_id(self.session)
        factor = await self._get_editable_factor(factor_id, tenant_id)
        payload = self._validated_payload(data)
        existing = await self._find_tenant_factor(tenant_id, payload)
        if existing is not None and existing.id != factor.id:
            msg = "同一租户、范围、类别、子类、单位和年份的计算因子已存在"
            raise ClientException(detail=msg, status_code=400)
        for field, value in payload.items():
            setattr(factor, field, value)
        await self.session.commit()
        return self.factor_payload(factor, tenant_id)

    async def delete_factor(self, factor_id: int) -> dict[str, Any]:
        tenant_id = require_session_tenant_id(self.session)
        factor = await self._get_editable_factor(factor_id, tenant_id)
        await self.session.delete(factor)
        await self.session.commit()
        return {"deleted": True, "id": factor_id}

    async def preview_import(self, *, file_name: str, csv_base64: str) -> CalculationFactorImportPreviewResponse:
        require_session_tenant_id(self.session)
        rows = await self._parse_import(file_name=file_name, csv_base64=csv_base64)
        return self._preview_payload(file_name, rows)

    async def commit_import(self, *, file_name: str, csv_base64: str) -> CalculationFactorImportPreviewResponse:
        tenant_id = require_session_tenant_id(self.session)
        rows = await self._parse_import(file_name=file_name, csv_base64=csv_base64)
        preview = self._preview_payload(file_name, rows)
        if preview.error_count:
            msg = "导入文件存在错误, 请修正后重新导入"
            raise ClientException(detail=msg, status_code=400)
        for row in rows:
            if row.factor is None or row.issues:
                continue
            payload = self._validated_payload(row.factor)
            existing = await self._find_tenant_factor(tenant_id, payload)
            if existing is None:
                self.session.add(m.EmissionFactor(team_id=tenant_id, **payload))
                continue
            for field, value in payload.items():
                setattr(existing, field, value)
        await self.session.commit()
        return preview

    async def factor_candidates(self, *, inventory_code: str, record_code: str) -> dict[str, Any]:
        activity = await self._get_activity(inventory_code=inventory_code, record_code=record_code)
        tenant_id = session_tenant_id(self.session)
        filters = self._read_scope_filters(tenant_id)
        filters.extend(
            [
                m.EmissionFactor.is_active.is_(True),
                m.EmissionFactor.scope == activity.ghg_scope,
            ]
        )
        category, sub_category = _suggest_factor_key(activity)
        if category:
            filters.append(m.EmissionFactor.category == category)
        if activity.activity_unit:
            filters.append(m.EmissionFactor.unit == activity.activity_unit)
        rows = list(
            (
                await self.session.scalars(
                    select(m.EmissionFactor)
                    .where(*filters)
                    .order_by(m.EmissionFactor.team_id.is_(None), m.EmissionFactor.year.desc(), m.EmissionFactor.id.desc())
                    .limit(100)
                )
            ).all()
        )
        parameter_rows = list(
            (
                await self.session.scalars(
                    select(GhgParameterValue).where(
                        GhgParameterValue.value_code.startswith(f"{activity.inventory_code}:{activity.parameter_set_code or ''}:")
                    )
                )
            ).all()
        )
        return {
            "items": [self.factor_candidate_payload(row, preferred_sub_category=sub_category) for row in rows],
            "current_parameters": [
                {
                    "parameterCode": row.parameter_code,
                    "parameterName": row.parameter_name,
                    "value": str(row.value),
                    "unit": row.unit,
                    "sourceMode": row.source_mode,
                    "sourceName": row.source_name,
                    "sourceVersion": row.source_version,
                    "qualityGrade": row.quality_grade,
                }
                for row in parameter_rows
            ],
        }

    async def apply_activity_factor(
        self,
        *,
        inventory_code: str,
        record_code: str,
        factor_id: int,
        parameter_code: str | None,
    ) -> ApplyActivityFactorResponse:
        tenant_id = require_session_tenant_id(self.session)
        activity = await self._get_activity(inventory_code=inventory_code, record_code=record_code)
        factor = await self._get_readable_factor(factor_id)
        resolved_parameter_code, parameter_name, method_code = await self._resolve_parameter(activity, parameter_code)
        parameter_set_code = activity.parameter_set_code or f"{activity.record_code}-PS1"
        activity.parameter_set_code = parameter_set_code
        activity.source_payload = {
            **dict(activity.source_payload or {}),
            "method_code": method_code,
            "gas_code": "CO2e",
            "factor_id": factor.id,
            "factor_source": factor.source,
            "factor_year": factor.year,
            "factor_unit": factor.factor_unit,
        }
        value_code = f"{activity.inventory_code}:{parameter_set_code}:{resolved_parameter_code}"
        parameter = await self.session.scalar(
            select(GhgParameterValue).where(GhgParameterValue.value_code == value_code, GhgParameterValue.version == 1)
        )
        if parameter is None:
            parameter = GhgParameterValue(value_code=value_code, version=1)
            self.session.add(parameter)
        parameter.parameter_code = resolved_parameter_code
        parameter.parameter_name = parameter_name
        parameter.parameter_role = "emission_factor"
        parameter.value = factor.factor_value
        parameter.unit = factor.factor_unit
        parameter.source_mode = "custom_approved" if factor.team_id == tenant_id else _source_mode(factor)
        parameter.source_name = factor.source
        parameter.source_version = str(factor.year)
        parameter.standard_code = factor.source
        parameter.reference_year = factor.year
        parameter.geography = _geography(factor)
        parameter.fuel_or_material = factor.sub_category
        parameter.quality_grade = "A" if factor.review_status == "approved" else "B"
        parameter.approval_status = "approved"
        parameter.status = "active"
        await self.session.commit()
        return ApplyActivityFactorResponse(
            record_code=activity.record_code,
            inventory_code=activity.inventory_code,
            parameter_set_code=parameter_set_code,
            parameter_code=resolved_parameter_code,
            factor_id=factor.id,
            source_name=factor.source,
            factor_value=str(factor.factor_value),
            factor_unit=factor.factor_unit,
        )

    def _read_scope_filters(self, tenant_id: UUID | None) -> list[ColumnElement[bool]]:
        if tenant_id is None:
            return []
        return [or_(m.EmissionFactor.team_id.is_(None), m.EmissionFactor.team_id == tenant_id)]

    async def _get_readable_factor(self, factor_id: int) -> m.EmissionFactor:
        tenant_id = session_tenant_id(self.session)
        filters = [m.EmissionFactor.id == factor_id, *self._read_scope_filters(tenant_id)]
        factor = await self.session.scalar(select(m.EmissionFactor).where(*filters))
        if factor is None:
            raise ClientException(detail="计算因子不存在", status_code=404)
        return factor

    async def _get_editable_factor(self, factor_id: int, tenant_id: UUID) -> m.EmissionFactor:
        factor = await self.session.scalar(
            select(m.EmissionFactor).where(m.EmissionFactor.id == factor_id, m.EmissionFactor.team_id == tenant_id)
        )
        if factor is None:
            raise PermissionDeniedException(detail="只能维护当前租户自建计算因子")
        return factor

    async def _find_tenant_factor(self, tenant_id: UUID, payload: dict[str, Any]) -> m.EmissionFactor | None:
        return await self.session.scalar(
            select(m.EmissionFactor).where(
                m.EmissionFactor.team_id == tenant_id,
                m.EmissionFactor.scope == payload["scope"],
                m.EmissionFactor.category == payload["category"],
                m.EmissionFactor.sub_category == payload["sub_category"],
                m.EmissionFactor.unit == payload["unit"],
                m.EmissionFactor.year == payload["year"],
            )
        )

    async def _get_activity(self, *, inventory_code: str, record_code: str) -> GhgActivityRecord:
        activity = await self.session.scalar(
            select(GhgActivityRecord).where(
                GhgActivityRecord.inventory_code == inventory_code,
                GhgActivityRecord.record_code == record_code,
            )
        )
        if activity is None:
            raise ClientException(detail="活动数据不存在", status_code=404)
        return activity

    async def _resolve_parameter(self, activity: GhgActivityRecord, parameter_code: str | None) -> tuple[str, str, str]:
        method_code = _method_for_activity(activity)
        requested = parameter_code or _default_parameter_code(method_code)
        method = await self.session.scalar(
            select(GhgCalculationMethodDefinition).where(
                GhgCalculationMethodDefinition.code == method_code,
                GhgCalculationMethodDefinition.status == "published",
            )
        )
        filters = [GhgMethodParameterDefinition.parameter_code == requested]
        if method is not None:
            filters.append(GhgMethodParameterDefinition.method_id == method.id)
        definition = await self.session.scalar(
            select(GhgMethodParameterDefinition).where(*filters).order_by(GhgMethodParameterDefinition.id.desc())
        )
        return requested, definition.parameter_name if definition else _parameter_name(requested), method_code

    def _validated_payload(self, data: CalculationFactorWriteRequest) -> dict[str, Any]:
        scope = _normalize_code(data.scope)
        projection_status = _normalize_code(data.projection_status)
        review_status = _normalize_code(data.review_status)
        if scope not in SCOPE_VALUES:
            raise ClientException(detail="范围必须为 scope1、scope2 或 scope3", status_code=400)
        if projection_status not in PROJECTION_STATUS_VALUES:
            raise ClientException(detail="导入方式必须为 manual、direct 或 derived", status_code=400)
        if review_status not in REVIEW_STATUS_VALUES:
            raise ClientException(detail="审核状态必须为 draft、pending、approved 或 rejected", status_code=400)
        if data.factor_value < 0:
            raise ClientException(detail="因子值不能为负数", status_code=400)
        if data.year < MIN_FACTOR_YEAR or data.year > MAX_FACTOR_YEAR:
            raise ClientException(detail="年份超出可维护范围", status_code=400)
        return {
            "scope": scope,
            "category": _normalize_code(data.category),
            "sub_category": _normalize_code(data.sub_category),
            "unit": _required_text(data.unit, "活动单位"),
            "factor_value": data.factor_value,
            "factor_unit": _required_text(data.factor_unit, "因子单位"),
            "year": data.year,
            "source": _required_text(data.source, "来源"),
            "source_system": _normalize_code(data.source_system) if data.source_system else "enterprise",
            "source_snapshot_id": _clean(data.source_snapshot_id),
            "raw_record_id": data.raw_record_id,
            "projection_status": projection_status,
            "review_status": review_status,
            "is_active": data.is_active,
            "note": _clean(data.note),
        }

    async def _parse_import(self, *, file_name: str, csv_base64: str) -> list[CalculationFactorImportRow]:
        if not file_name.lower().endswith(".csv"):
            raise ClientException(detail="计算因子模板目前支持 CSV 文件", status_code=400)
        try:
            text = base64.b64decode(csv_base64).decode("utf-8-sig")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ClientException(detail="CSV 文件编码应为 UTF-8", status_code=400) from exc
        reader = csv.DictReader(io.StringIO(text))
        missing_columns = [column for column in TEMPLATE_COLUMNS if column not in (reader.fieldnames or [])]
        if missing_columns:
            msg = f"模板缺少字段: {', '.join(missing_columns)}"
            raise ClientException(detail=msg, status_code=400)
        rows: list[CalculationFactorImportRow] = []
        tenant_id = session_tenant_id(self.session)
        for line_number, raw in enumerate(reader, start=2):
            factor, issues = self._parse_row(line_number, raw)
            action = "invalid"
            if factor is not None and not issues:
                payload = self._validated_payload(factor)
                existing = await self._find_tenant_factor(tenant_id, payload) if tenant_id is not None else None
                action = "update" if existing else "create"
            rows.append(CalculationFactorImportRow(row_number=line_number, action=action, factor=factor, issues=issues))
        return rows

    def _parse_row(self, line_number: int, raw: dict[str, str | None]) -> tuple[CalculationFactorWriteRequest | None, list[CalculationFactorImportIssue]]:
        issues: list[CalculationFactorImportIssue] = []

        def require(field: str) -> str:
            value = _clean(raw.get(field))
            if value is None:
                issues.append(_issue(line_number, field, "REQUIRED", f"{field} 不能为空"))
                return ""
            return value

        try:
            factor_value = Decimal(require("factor_value"))
        except InvalidOperation:
            issues.append(_issue(line_number, "factor_value", "INVALID_DECIMAL", "因子值不是有效数值", raw.get("factor_value")))
            factor_value = Decimal(0)
        try:
            year = int(require("year"))
        except ValueError:
            issues.append(_issue(line_number, "year", "INVALID_YEAR", "年份不是有效整数", raw.get("year")))
            year = 0
        source_system = _normalize_code(raw.get("source_system")) if _clean(raw.get("source_system")) else "enterprise"
        if source_system not in SOURCE_SYSTEM_VALUES:
            issues.append(_issue(line_number, "source_system", "INVALID_SOURCE_SYSTEM", "来源系统不在可选范围内", raw.get("source_system")))
        raw_record_text = _clean(raw.get("raw_record_id"))
        try:
            raw_record_id = int(raw_record_text) if raw_record_text else None
        except ValueError:
            issues.append(_issue(line_number, "raw_record_id", "INVALID_RAW_RECORD", "原始记录 ID 不是有效整数", raw_record_text))
            raw_record_id = None
        factor = CalculationFactorWriteRequest(
            scope=require("scope"),
            category=require("category"),
            sub_category=require("sub_category"),
            unit=require("unit"),
            factor_value=factor_value,
            factor_unit=require("factor_unit"),
            year=year,
            source=require("source"),
            source_system=source_system,
            source_snapshot_id=_clean(raw.get("source_snapshot_id")),
            raw_record_id=raw_record_id,
            projection_status=_clean(raw.get("projection_status")) or "manual",
            review_status=_clean(raw.get("review_status")) or "approved",
            is_active=_parse_bool(raw.get("is_active"), default=True),
            note=_clean(raw.get("note")),
        )
        try:
            self._validated_payload(factor)
        except ClientException as exc:
            issues.append(_issue(line_number, None, "INVALID_FACTOR", str(exc.detail)))
        return factor, issues

    @staticmethod
    def _preview_payload(file_name: str, rows: list[CalculationFactorImportRow]) -> CalculationFactorImportPreviewResponse:
        valid = [row for row in rows if not row.issues and row.factor is not None]
        errors = sum(len([issue for issue in row.issues if issue.severity == "error"]) for row in rows)
        return CalculationFactorImportPreviewResponse(
            file_name=file_name,
            row_count=len(rows),
            valid_count=len(valid),
            error_count=errors,
            create_count=sum(1 for row in valid if row.action == "create"),
            update_count=sum(1 for row in valid if row.action == "update"),
            rows=rows,
        )

    @staticmethod
    def factor_payload(row: m.EmissionFactor, tenant_id: UUID | None) -> CalculationFactorResponse:
        return CalculationFactorResponse(
            id=row.id,
            owner_type="enterprise" if row.team_id else "shared",
            editable=tenant_id is not None and row.team_id == tenant_id,
            scope=row.scope,
            category=row.category,
            sub_category=row.sub_category,
            unit=row.unit,
            factor_value=str(row.factor_value),
            factor_unit=row.factor_unit,
            year=row.year,
            source=row.source,
            source_system=row.source_system,
            source_snapshot_id=row.source_snapshot_id,
            raw_record_id=row.raw_record_id,
            projection_status=row.projection_status,
            review_status=row.review_status,
            is_active=row.is_active,
            note=row.note,
        )

    @staticmethod
    def factor_candidate_payload(
        row: m.EmissionFactor,
        *,
        preferred_sub_category: str | None,
    ) -> ActivityFactorCandidateResponse:
        return ActivityFactorCandidateResponse(
            id=row.id,
            owner_type="enterprise" if row.team_id else "shared",
            scope=row.scope,
            category=row.category,
            sub_category=row.sub_category,
            unit=row.unit,
            factor_value=str(row.factor_value),
            factor_unit=row.factor_unit,
            year=row.year,
            source=row.source,
            source_system=row.source_system,
            projection_status=row.projection_status,
            review_status=row.review_status,
            is_active=row.is_active,
            match_reason="推荐匹配" if preferred_sub_category and row.sub_category == preferred_sub_category else "同范围和单位可选",
        )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_text(value: Any, label: str) -> str:
    text = _clean(value)
    if text is None:
        raise ClientException(detail=f"{label}不能为空", status_code=400)
    return text


def _normalize_code(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_bool(value: Any, *, default: bool) -> bool:
    text = _normalize_code(value)
    if not text:
        return default
    return text in {"1", "true", "yes", "y", "on", "是", "启用", "active"}


def _issue(
    row_number: int,
    field: str | None,
    code: str,
    message: str,
    value: str | None = None,
) -> CalculationFactorImportIssue:
    return CalculationFactorImportIssue(
        severity="error",
        row_number=row_number,
        field=field,
        code=code,
        message=message,
        value=value,
    )


def _source_mode(factor: m.EmissionFactor) -> str:
    source_text = f"{factor.source} {factor.source_system or ''}".lower()
    if any(marker in source_text for marker in ("ncsc", "ipcc", "生态环境部", "官方")):
        return "authority_published"
    return "library"


def _geography(factor: m.EmissionFactor) -> str:
    text = factor.sub_category.lower()
    if "jiangsu" in text:
        return "江苏"
    if "shanghai" in text:
        return "上海"
    if "zhejiang" in text:
        return "浙江"
    return "中国"


def _method_for_activity(activity: GhgActivityRecord) -> str:
    category = activity.iso_category_code
    if category in {"2.1", "2.2"}:
        return "F08_PURCHASED_ENERGY"
    if category == "3.1":
        return "F09_TRANSPORT_ACTIVITY"
    return "F02_EF"


def _default_parameter_code(method_code: str) -> str:
    if method_code == "F08_PURCHASED_ENERGY":
        return "ENERGY_FACTOR"
    if method_code == "F09_TRANSPORT_ACTIVITY":
        return "TRANSPORT_FACTOR"
    return "EMISSION_FACTOR"


def _parameter_name(parameter_code: str) -> str:
    return {
        "ENERGY_FACTOR": "购入能源排放因子",
        "TRANSPORT_FACTOR": "运输活动排放因子",
        "EMISSION_FACTOR": "排放因子",
    }.get(parameter_code, parameter_code)


def _suggest_factor_key(activity: GhgActivityRecord) -> tuple[str | None, str | None]:
    payload = dict(activity.source_payload or {})
    category = activity.iso_category_code
    if category in {"1.1", "1.2"}:
        return "fuel", _normalize_code(payload.get("fuel_type"))
    if category == "1.4":
        return "refrigerant", _normalize_code(payload.get("refrigerant_type"))
    if category in {"2.1", "2.2"}:
        return "electricity", _normalize_code(payload.get("energy_type"))
    if category == "3.1":
        return "transport", _normalize_code(payload.get("vehicle_type"))
    if category == "4.4":
        return "waste", _normalize_code(payload.get("waste_type"))
    return None, None
