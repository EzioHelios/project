from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.db import models as m
from app.domain.carbon_verification.domain.policies import validate_template_status
from app.domain.carbon_verification.queries.verification_constants import (
    REPORT_STANDARD_CODE,
    REPORT_STANDARD_NAME,
    REPORT_TEMPLATE_NAME,
    REPORT_TEMPLATE_PATH,
    REPORT_TEMPLATE_VERSION,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


TEMPLATE_FIELDS = {
    "template_code",
    "template_name",
    "version",
    "template_format",
    "template_path",
    "applicable_industry",
    "applicable_scope",
    "standard_name",
    "standard_code",
    "source_name",
    "status",
    "is_default",
    "effective_from",
    "effective_to",
    "confidence_level",
    "remark",
}
DATE_FIELDS = {"effective_from", "effective_to"}
BOOLEAN_FIELDS = {"is_default"}


class CarbonVerificationTemplateUseCase:
    """Application workflows for report template versions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_template(self, data: dict[str, Any]) -> m.CarbonVerificationTemplateVersion:
        payload = _payload(data, TEMPLATE_FIELDS, required={"template_code", "template_name", "template_path"})
        payload.setdefault("version", "v1.0")
        payload.setdefault("template_format", "docx")
        payload.setdefault("status", "active")
        payload.setdefault("is_default", False)
        validate_template_status(str(payload["status"]))
        if payload["is_default"]:
            payload["status"] = "active"
            await self._clear_default_templates()
        obj = m.CarbonVerificationTemplateVersion(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def ensure_default_template(self) -> m.CarbonVerificationTemplateVersion:
        existing = await self._session.scalar(
            select(m.CarbonVerificationTemplateVersion)
            .where(
                m.CarbonVerificationTemplateVersion.template_code == "organization_ghg_generic",
                m.CarbonVerificationTemplateVersion.version == REPORT_TEMPLATE_VERSION,
            )
            .limit(1)
        )
        if existing is not None:
            await self._clear_default_templates(except_id=existing.id)
            existing.status = "active"
            existing.is_default = True
            await self._session.commit()
            await self._session.refresh(existing)
            return existing
        await self._clear_default_templates()
        obj = m.CarbonVerificationTemplateVersion(
            template_code="organization_ghg_generic",
            template_name=REPORT_TEMPLATE_NAME,
            version=REPORT_TEMPLATE_VERSION,
            template_format="docx",
            template_path=REPORT_TEMPLATE_PATH,
            applicable_industry="工业其他行业",
            applicable_scope="工业企业组织层面温室气体排放报告和核查材料包",
            standard_name=REPORT_STANDARD_NAME,
            standard_code=REPORT_STANDARD_CODE,
            source_name="repository_default",
            status="active",
            is_default=True,
            effective_from=datetime.date(2026, 6, 13),
            confidence_level="standard_reference",
            remark="仓库内置通用模板",
        )
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_template(self, template_id: int, data: dict[str, Any]) -> m.CarbonVerificationTemplateVersion:
        obj = await self._get_or_raise(template_id)
        payload = _payload(data, TEMPLATE_FIELDS - {"template_code"})
        if "status" in payload:
            validate_template_status(str(payload["status"]))
        if payload.get("is_default") is True:
            await self._clear_default_templates(except_id=obj.id)
            payload.setdefault("status", "active")
        if payload.get("status") in {"disabled", "draft"}:
            payload["is_default"] = False
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def _clear_default_templates(self, *, except_id: int | None = None) -> None:
        rows = (await self._session.execute(select(m.CarbonVerificationTemplateVersion))).scalars().all()
        for row in rows:
            if except_id is not None and row.id == except_id:
                continue
            row.is_default = False

    async def _get_or_raise(self, template_id: int) -> m.CarbonVerificationTemplateVersion:
        obj = await self._session.get(m.CarbonVerificationTemplateVersion, template_id)
        if obj is None:
            msg = "报告模板不存在"
            raise ValueError(msg)
        return obj


def _payload(data: dict[str, Any], fields: set[str], *, required: set[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in fields:
        if key not in data or data[key] in (None, ""):
            continue
        payload[key] = _coerce_value(key, data[key])
    missing = [field for field in required or set() if field not in payload]
    if missing:
        msg = f"缺少必填字段: {', '.join(sorted(missing))}"
        raise ValueError(msg)
    return payload


def _coerce_value(key: str, value: Any) -> Any:
    if key in DATE_FIELDS and isinstance(value, str):
        return datetime.date.fromisoformat(value[:10])
    if key in BOOLEAN_FIELDS:
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "y"}
        return bool(value)
    return value


def _assign(obj: Any, payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        setattr(obj, key, value)
