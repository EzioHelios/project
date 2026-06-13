from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_verification.queries.verification_constants import (
    REPORT_STANDARD_CODE,
    REPORT_STANDARD_NAME,
    REPORT_TEMPLATE_NAME,
    REPORT_TEMPLATE_PATH,
    REPORT_TEMPLATE_VERSION,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class TemplateQuery:
    status: str | None = None
    applicable_industry: str | None = None
    limit: int = 100
    offset: int = 0


class CarbonVerificationTemplateQueryService:
    """Read model service for verification report templates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_template(self, template_id: int) -> dict[str, Any]:
        row = await self._session.get(m.CarbonVerificationTemplateVersion, template_id)
        if row is None:
            msg = "报告模板不存在"
            raise ValueError(msg)
        return template_payload(row)

    async def active_template(self) -> dict[str, Any]:
        row = await self._active_row()
        if row is None:
            return default_template_payload()
        return template_payload(row)

    async def list_templates(self, query: TemplateQuery) -> dict[str, Any]:
        stmt = select(m.CarbonVerificationTemplateVersion).order_by(
            m.CarbonVerificationTemplateVersion.is_default.desc(),
            m.CarbonVerificationTemplateVersion.id.desc(),
        )
        count_stmt = select(func.count(m.CarbonVerificationTemplateVersion.id))
        for condition in _conditions(query):
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        rows = (await self._session.execute(stmt.limit(_limit(query.limit)).offset(max(0, query.offset)))).scalars().all()
        total = int(await self._session.scalar(count_stmt) or 0)
        return {
            "items": [template_payload(row) for row in rows],
            "active": await self.active_template(),
            "total": total,
            "limit": _limit(query.limit),
            "offset": max(0, query.offset),
            "filters": _filters(query),
        }

    async def _active_row(self) -> m.CarbonVerificationTemplateVersion | None:
        return await self._session.scalar(
            select(m.CarbonVerificationTemplateVersion)
            .where(m.CarbonVerificationTemplateVersion.status == "active")
            .order_by(m.CarbonVerificationTemplateVersion.is_default.desc(), m.CarbonVerificationTemplateVersion.id.desc())
            .limit(1)
        )


def template_payload(row: m.CarbonVerificationTemplateVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "template_code": row.template_code,
        "template_name": row.template_name,
        "name": row.template_name,
        "version": row.version,
        "format": row.template_format,
        "template_format": row.template_format,
        "path": row.template_path,
        "template_path": row.template_path,
        "applicable_industry": row.applicable_industry,
        "applicable_scope": row.applicable_scope,
        "standard_name": row.standard_name,
        "standard_code": row.standard_code,
        "source_name": row.source_name,
        "status": row.status,
        "is_default": row.is_default,
        "effective_from": row.effective_from.isoformat() if row.effective_from else None,
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "confidence_level": row.confidence_level,
        "remark": row.remark,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def default_template_payload() -> dict[str, Any]:
    return {
        "id": None,
        "template_code": "organization_ghg_generic",
        "template_name": REPORT_TEMPLATE_NAME,
        "name": REPORT_TEMPLATE_NAME,
        "version": REPORT_TEMPLATE_VERSION,
        "format": "docx",
        "template_format": "docx",
        "path": REPORT_TEMPLATE_PATH,
        "template_path": REPORT_TEMPLATE_PATH,
        "applicable_industry": "工业其他行业",
        "applicable_scope": "工业企业组织层面温室气体排放报告和核查材料包",
        "standard_name": REPORT_STANDARD_NAME,
        "standard_code": REPORT_STANDARD_CODE,
        "source_name": "repository_default",
        "status": "active",
        "is_default": True,
        "effective_from": "2026-06-13",
        "effective_to": None,
        "confidence_level": "standard_reference",
        "remark": "仓库内置通用模板 fallback",
    }


def _conditions(query: TemplateQuery) -> list[Any]:
    conditions = []
    if query.status and query.status != "all":
        conditions.append(m.CarbonVerificationTemplateVersion.status == query.status)
    if query.applicable_industry and query.applicable_industry != "all":
        conditions.append(m.CarbonVerificationTemplateVersion.applicable_industry == query.applicable_industry)
    return conditions


def _filters(query: TemplateQuery) -> dict[str, Any]:
    return {
        "status": query.status,
        "applicable_industry": query.applicable_industry,
        "limit": query.limit,
        "offset": query.offset,
    }


def _limit(value: int) -> int:
    return max(1, min(int(value or 100), 500))
