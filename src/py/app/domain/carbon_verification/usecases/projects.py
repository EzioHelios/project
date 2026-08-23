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
    "inventory_report_id",
    "calculation_run_id",
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
    "assurance_level",
    "materiality_threshold_pct",
    "verification_basis",
    "sampling_strategy",
    "site_visit_required",
    "site_visit_status",
    "conclusion_status",
    "readiness_status",
    "conclusion",
    "scope_description",
    "finding_summary",
    "source_name",
    "standard_code",
    "confidence_level",
    "remark",
}
INTEGER_FIELDS = {
    "reporting_org_id",
    "period_id",
    "boundary_id",
    "inventory_report_id",
    "calculation_run_id",
    "template_version_id",
    "verification_year",
}
DATE_FIELDS = {"planned_start", "planned_end"}
DATETIME_FIELDS = {"started_at", "completed_at"}
MAX_MATERIALITY_THRESHOLD_PCT = 100


class CarbonVerificationProjectUseCase:
    """Application workflows for formal carbon verification projects."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_project(self, data: dict[str, Any]) -> m.CarbonVerificationProject:
        payload = _payload(data, PROJECT_FIELDS, required={"project_name"})
        payload.setdefault("project_type", "organization_inventory")
        payload.setdefault("status", PROJECT_DRAFT)
        payload.setdefault("source_name", "carbon_verification")
        payload.setdefault("assurance_level", "internal_review")
        payload.setdefault("verification_basis", "ISO 14064-3:2019")
        payload.setdefault("site_visit_status", "not_planned")
        payload.setdefault("conclusion_status", "pending")
        validate_project_status(str(payload["status"]))
        _validate_verification_plan(payload)
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
                conclusion_status = str(payload.get("conclusion_status", project.conclusion_status))
                if project.readiness_status != "ready" or conclusion_status != "approved":
                    msg = "核查材料未就绪或核查结论未批准, 不能完成项目"
                    raise ValueError(msg)
                _validate_completion_plan(payload, project)
                payload.setdefault("completed_at", _utc_now_naive())
        _validate_verification_plan(payload, current=project)
        await self._complete_references(payload, current=project)
        _assign(project, payload)
        await self._session.commit()
        await self._session.refresh(project)
        await self.refresh_project_status(project.id)
        await self._session.refresh(project)
        return project

    async def refresh_project_status(self, project_id: int) -> m.CarbonVerificationProject:
        project = await self._get_or_raise(project_id)
        missing_result_count, missing_factor_count, pending_review_count = await self._material_gap_counts(project)
        open_finding_count = int(
            await self._session.scalar(
                select(func.count(m.CarbonVerificationFinding.id)).where(
                    m.CarbonVerificationFinding.project_id == project.id,
                    m.CarbonVerificationFinding.status.in_(("open", "rectifying", "resolved")),
                )
            )
            or 0
        )
        missing_evidence_count = await self._missing_activity_evidence_count(project)
        project.finding_summary = {
            "open_finding_count": open_finding_count,
            "missing_evidence_count": missing_evidence_count,
            "missing_result_count": missing_result_count,
            "missing_factor_count": missing_factor_count,
            "pending_review_count": pending_review_count,
        }
        if (
            project.inventory_report is None
            or project.inventory_report.status != "published"
            or missing_factor_count > 0
        ):
            project.readiness_status = "blocked"
        elif pending_review_count > 0:
            project.readiness_status = "attention"
        else:
            project.readiness_status = project_readiness(
                finding_open_count=open_finding_count,
                missing_evidence_count=missing_evidence_count,
                missing_result_count=missing_result_count,
            )
        await self._session.commit()
        return project

    async def _material_gap_counts(self, project: m.CarbonVerificationProject) -> tuple[int, int, int]:
        run = project.calculation_run
        if run is None or run.status != "completed":
            return 1, 0, 0
        activities = list(
            (
                await self._session.scalars(
                    select(m.GhgActivityRecord).where(
                        m.GhgActivityRecord.inventory_code == run.inventory_code,
                        m.GhgActivityRecord.boundary_status == "included",
                    )
                )
            ).all()
        )
        if not activities:
            return 1, 0, 0
        activity_ids = [item.id for item in activities]
        result_ids = set(
            (
                await self._session.scalars(
                    select(m.GhgCalculationResult.activity_id).where(
                        m.GhgCalculationResult.run_id == run.id,
                        m.GhgCalculationResult.activity_id.in_(activity_ids),
                    )
                )
            ).all()
        )
        parameter_ids = set(
            (
                await self._session.scalars(
                    select(m.GhgParameterAssignment.activity_id).where(
                        m.GhgParameterAssignment.run_id == run.id,
                        m.GhgParameterAssignment.activity_id.in_(activity_ids),
                    )
                )
            ).all()
        )
        pending_review_count = sum(1 for item in activities if item.quality_status not in {"pass", "ready", "approved"})
        return len(set(activity_ids) - result_ids), len(set(activity_ids) - parameter_ids), pending_review_count

    async def _complete_references(
        self, payload: dict[str, Any], *, current: m.CarbonVerificationProject | None = None
    ) -> None:
        report_id = payload.get("inventory_report_id", current.inventory_report_id if current else None)
        if report_id is None:
            msg = "核查项目必须绑定已发布的组织温室气体盘查报告"
            raise ValueError(msg)
        report = await self._get_model_or_raise(m.GhgInventoryReport, int(report_id), "盘查报告不存在")
        if report.status != "published":
            msg = "只有已发布的盘查报告才能创建或更新核查项目"
            raise ValueError(msg)
        run = await self._get_model_or_raise(m.GhgCalculationRun, int(report.run_id), "盘查报告绑定的核算运行不存在")
        if run.status != "completed":
            msg = "盘查报告绑定的核算运行尚未完成"
            raise ValueError(msg)
        supplied_run_id = payload.get("calculation_run_id")
        if supplied_run_id is not None and int(supplied_run_id) != run.id:
            msg = "核查项目核算运行与盘查报告不一致"
            raise ValueError(msg)
        payload["calculation_run_id"] = run.id
        payload["reporting_org_id"] = report.reporting_org_id
        payload["period_id"] = report.reporting_period_id
        payload["boundary_id"] = report.organization_boundary_id
        period = await self._get_model_or_raise(m.ReportingPeriod, report.reporting_period_id, "报告期不存在")
        payload.setdefault("verification_year", period.period_end.year)
        if payload.get("reporting_org_id") is not None:
            await self._get_model_or_raise(m.ReportingOrganization, int(payload["reporting_org_id"]), "报告主体不存在")
        if payload.get("period_id") is not None:
            await self._get_model_or_raise(m.ReportingPeriod, int(payload["period_id"]), "报告期不存在")
        if payload.get("template_version_id") is not None:
            await self._get_model_or_raise(
                m.CarbonVerificationTemplateVersion, int(payload["template_version_id"]), "报告模板不存在"
            )
        elif current is None:
            template = await CarbonVerificationTemplateUseCase(self._session).ensure_default_template()
            payload["template_version_id"] = template.id

    async def _missing_activity_evidence_count(self, project: m.CarbonVerificationProject) -> int:
        run = project.calculation_run
        if run is None:
            return 0
        activity_codes = list(
            (
                await self._session.scalars(
                    select(m.GhgActivityRecord.record_code).where(
                        m.GhgActivityRecord.inventory_code == run.inventory_code
                    )
                )
            ).all()
        )
        if not activity_codes:
            return 0
        ready = int(
            await self._session.scalar(
                select(func.count(func.distinct(m.GhgEvidenceLink.record_code)))
                .join(m.GhgEvidenceFile, m.GhgEvidenceFile.id == m.GhgEvidenceLink.evidence_id)
                .where(
                    m.GhgEvidenceLink.record_type == "activity",
                    m.GhgEvidenceLink.record_code.in_(activity_codes),
                    m.GhgEvidenceFile.verification_status.in_(("reviewed", "approved")),
                )
            )
            or 0
        )
        return max(len(activity_codes) - ready, 0)

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


def _validate_verification_plan(payload: dict[str, Any], *, current: m.CarbonVerificationProject | None = None) -> None:
    assurance_level = str(payload.get("assurance_level", current.assurance_level if current else "internal_review"))
    if assurance_level not in {"internal_review", "limited", "reasonable"}:
        msg = "不支持的保证等级"
        raise ValueError(msg)
    site_visit_status = str(payload.get("site_visit_status", current.site_visit_status if current else "not_planned"))
    if site_visit_status not in {"not_planned", "planned", "completed", "waived"}:
        msg = "不支持的现场核查状态"
        raise ValueError(msg)
    conclusion_status = str(payload.get("conclusion_status", current.conclusion_status if current else "pending"))
    if conclusion_status not in {"pending", "draft", "reviewed", "approved"}:
        msg = "不支持的核查结论状态"
        raise ValueError(msg)
    threshold = payload.get("materiality_threshold_pct")
    if threshold is not None and not 0 < float(threshold) <= MAX_MATERIALITY_THRESHOLD_PCT:
        msg = "重要性水平必须大于0且不超过100%"
        raise ValueError(msg)


def _validate_completion_plan(payload: dict[str, Any], project: m.CarbonVerificationProject) -> None:
    assurance_level = str(payload.get("assurance_level", project.assurance_level))
    basis = payload.get("verification_basis", project.verification_basis)
    sampling = payload.get("sampling_strategy", project.sampling_strategy)
    threshold = payload.get("materiality_threshold_pct", project.materiality_threshold_pct)
    conclusion = payload.get("conclusion", project.conclusion)
    site_visit_required = bool(payload.get("site_visit_required", project.site_visit_required))
    site_visit_status = str(payload.get("site_visit_status", project.site_visit_status))
    if not basis or not conclusion:
        msg = "完成核查前必须填写核查依据和核查结论"
        raise ValueError(msg)
    if assurance_level in {"limited", "reasonable"} and (threshold is None or not sampling):
        msg = "有限保证或合理保证项目必须填写重要性水平和抽样策略"
        raise ValueError(msg)
    if site_visit_required and site_visit_status != "completed":
        msg = "需要现场核查的项目必须完成现场核查后才能结项"
        raise ValueError(msg)
