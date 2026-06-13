from __future__ import annotations

import datetime
from datetime import UTC
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_verification.domain.policies import (
    PROJECT_DRAFT,
    PROJECT_IN_PROGRESS,
    project_readiness,
    validate_project_status,
    validate_project_transition,
)
from app.domain.carbon_verification.usecases.templates import CarbonVerificationTemplateUseCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


PROJECT_FIELDS = {
    "project_no",
    "project_name",
    "project_type",
    "reporting_org_id",
    "period_id",
    "boundary_id",
    "accounting_batch_id",
    "template_version_id",
    "status",
    "verification_year",
    "planned_start",
    "planned_end",
    "started_at",
    "completed_at",
    "lead_reviewer",
    "responsible_person",
    "verifier_org",
    "readiness_status",
    "conclusion",
    "scope_description",
    "finding_summary",
    "source_name",
    "standard_code",
    "confidence_level",
    "remark",
}
INTEGER_FIELDS = {"reporting_org_id", "period_id", "boundary_id", "accounting_batch_id", "template_version_id", "verification_year"}
DATE_FIELDS = {"planned_start", "planned_end"}
DATETIME_FIELDS = {"started_at", "completed_at"}


class CarbonVerificationProjectUseCase:
    """Application workflows for formal carbon verification projects."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_project(self, data: dict[str, Any]) -> m.CarbonVerificationProject:
        payload = _payload(data, PROJECT_FIELDS, required={"project_name"})
        payload.setdefault("project_type", "organization_inventory")
        payload.setdefault("status", PROJECT_DRAFT)
        payload.setdefault("source_name", "carbon_verification")
        validate_project_status(str(payload["status"]))
        await self._complete_references(payload)
        payload.setdefault("project_no", await self._next_no(payload.get("verification_year")))
        payload.setdefault("readiness_status", "empty")
        project = m.CarbonVerificationProject(**payload)
        self._session.add(project)
        await self._session.commit()
        await self._session.refresh(project)
        await self.refresh_project_status(project.id)
        await self._session.refresh(project)
        return project

    async def update_project(self, project_id: int, data: dict[str, Any]) -> m.CarbonVerificationProject:
        project = await self._get_or_raise(project_id)
        payload = _payload(data, PROJECT_FIELDS - {"project_no"})
        if "status" in payload:
            validate_project_transition(project.status, str(payload["status"]))
            if payload["status"] == PROJECT_IN_PROGRESS:
                payload.setdefault("started_at", _utc_now_naive())
            if payload["status"] == "completed":
                payload.setdefault("completed_at", _utc_now_naive())
        await self._complete_references(payload, current=project)
        _assign(project, payload)
        await self._session.commit()
        await self._session.refresh(project)
        await self.refresh_project_status(project.id)
        await self._session.refresh(project)
        return project

    async def refresh_project_status(self, project_id: int) -> m.CarbonVerificationProject:
        project = await self._get_or_raise(project_id)
        missing_result_count = int(project.accounting_batch.missing_result_count or 0) if project.accounting_batch else 0
        open_finding_count = int(
            await self._session.scalar(
                select(func.count(m.CarbonVerificationFinding.id)).where(
                    m.CarbonVerificationFinding.project_id == project.id,
                    m.CarbonVerificationFinding.status.in_(("open", "rectifying", "resolved")),
                )
            )
            or 0
        )
        missing_evidence_count = int(
            await self._session.scalar(
                select(func.count(m.CarbonVerificationAttachment.id)).where(
                    m.CarbonVerificationAttachment.project_id == project.id,
                    m.CarbonVerificationAttachment.status != "ready",
                )
            )
            or 0
        )
        project.finding_summary = {
            "open_finding_count": open_finding_count,
            "missing_evidence_count": missing_evidence_count,
            "missing_result_count": missing_result_count,
        }
        if project.accounting_batch and (project.accounting_batch.status != "locked" or project.accounting_batch.inventory_status != "locked"):
            project.readiness_status = "blocked"
        elif project.accounting_batch_id is None and project.boundary_id is None:
            project.readiness_status = "empty"
        else:
            project.readiness_status = project_readiness(
                finding_open_count=open_finding_count,
                missing_evidence_count=missing_evidence_count,
                missing_result_count=missing_result_count,
            )
        await self._session.commit()
        return project

    async def _complete_references(self, payload: dict[str, Any], *, current: m.CarbonVerificationProject | None = None) -> None:
        batch_id = payload.get("accounting_batch_id", current.accounting_batch_id if current else None)
        if batch_id is not None:
            batch = await self._get_model_or_raise(m.CarbonAccountingBatch, int(batch_id), "核算批次不存在")
            payload.setdefault("reporting_org_id", batch.reporting_org_id)
            payload.setdefault("period_id", batch.period_id)
            payload.setdefault("boundary_id", batch.boundary_id)
            payload.setdefault("verification_year", batch.period.period_end.year if batch.period else None)
        boundary_id = payload.get("boundary_id", current.boundary_id if current else None)
        if boundary_id is not None:
            boundary = await self._get_model_or_raise(m.OrganizationBoundary, int(boundary_id), "组织边界不存在")
            payload.setdefault("reporting_org_id", boundary.reporting_org_id)
            payload.setdefault("period_id", boundary.period_id)
            payload.setdefault("verification_year", boundary.period.period_end.year if boundary.period else None)
        if payload.get("reporting_org_id") is not None:
            await self._get_model_or_raise(m.ReportingOrganization, int(payload["reporting_org_id"]), "报告主体不存在")
        if payload.get("period_id") is not None:
            await self._get_model_or_raise(m.ReportingPeriod, int(payload["period_id"]), "报告期不存在")
        if payload.get("template_version_id") is not None:
            await self._get_model_or_raise(m.CarbonVerificationTemplateVersion, int(payload["template_version_id"]), "报告模板不存在")
        elif current is None:
            template = await CarbonVerificationTemplateUseCase(self._session).ensure_default_template()
            payload["template_version_id"] = template.id

    async def _get_model_or_raise(self, model: type[Any], obj_id: int, message: str) -> Any:
        obj = await self._session.get(model, obj_id)
        if obj is None:
            raise ValueError(message)
        return obj

    async def _next_no(self, year: Any) -> str:
        timestamp = datetime.datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        count = await self._session.scalar(select(func.count(m.CarbonVerificationProject.id)))
        return f"VP-{year or 'all'}-{timestamp}-{int(count or 0) + 1:04d}"

    async def _get_or_raise(self, project_id: int) -> m.CarbonVerificationProject:
        project = await self._session.get(m.CarbonVerificationProject, project_id)
        if project is None:
            msg = "核查项目不存在"
            raise ValueError(msg)
        return project


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
    if key in INTEGER_FIELDS:
        return int(value)
    if key in DATE_FIELDS and isinstance(value, str):
        return datetime.date.fromisoformat(value[:10])
    if key in DATETIME_FIELDS and isinstance(value, str):
        return datetime.datetime.fromisoformat(value).replace(tzinfo=None)
    return value


def _assign(obj: Any, payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        setattr(obj, key, value)


def _utc_now_naive() -> datetime.datetime:
    return datetime.datetime.now(UTC).replace(tzinfo=None)
