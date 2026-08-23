from __future__ import annotations

from dataclasses import dataclass

READY_STATUS = "ready"
MISSING_EVIDENCE_STATUS = "missing_evidence"
MISSING_FACTOR_STATUS = "missing_factor"
MISSING_RESULT_STATUS = "missing_result"
PENDING_REVIEW_STATUS = "pending_review"
REJECTED_STATUS = "rejected"

FINDING_OPEN = "open"
FINDING_RECTIFYING = "rectifying"
FINDING_RESOLVED = "resolved"
FINDING_CLOSED = "closed"
FINDING_STATUSES = {FINDING_OPEN, FINDING_RECTIFYING, FINDING_RESOLVED, FINDING_CLOSED}
FINDING_SEVERITIES = {"low", "medium", "high"}
FINDING_TRANSITIONS: dict[str, set[str]] = {
    FINDING_OPEN: {FINDING_RECTIFYING, FINDING_RESOLVED, FINDING_CLOSED},
    FINDING_RECTIFYING: {FINDING_OPEN, FINDING_RESOLVED},
    FINDING_RESOLVED: {FINDING_RECTIFYING, FINDING_CLOSED},
    FINDING_CLOSED: set(),
}

TEMPLATE_ACTIVE = "active"
TEMPLATE_DISABLED = "disabled"
TEMPLATE_DRAFT = "draft"
TEMPLATE_STATUSES = {TEMPLATE_ACTIVE, TEMPLATE_DISABLED, TEMPLATE_DRAFT}

PROJECT_DRAFT = "draft"
PROJECT_IN_PROGRESS = "in_progress"
PROJECT_REVIEW = "review"
PROJECT_COMPLETED = "completed"
PROJECT_ARCHIVED = "archived"
PROJECT_STATUSES = {PROJECT_DRAFT, PROJECT_IN_PROGRESS, PROJECT_REVIEW, PROJECT_COMPLETED, PROJECT_ARCHIVED}
PROJECT_TRANSITIONS: dict[str, set[str]] = {
    PROJECT_DRAFT: {PROJECT_IN_PROGRESS, PROJECT_ARCHIVED},
    PROJECT_IN_PROGRESS: {PROJECT_DRAFT, PROJECT_REVIEW, PROJECT_COMPLETED, PROJECT_ARCHIVED},
    PROJECT_REVIEW: {PROJECT_IN_PROGRESS, PROJECT_COMPLETED, PROJECT_ARCHIVED},
    PROJECT_COMPLETED: {PROJECT_ARCHIVED},
    PROJECT_ARCHIVED: set(),
}


@dataclass(frozen=True, slots=True)
class VerificationRule:
    code: str
    title: str
    material_group: str
    required: bool = True


MATERIAL_RULES: tuple[VerificationRule, ...] = (
    VerificationRule("enterprise-profile", "报告主体基本信息", "boundary"),
    VerificationRule("boundary-description", "组织边界与运营边界说明", "boundary"),
    VerificationRule("source-identification", "排放源识别清单", "inventory"),
    VerificationRule("activity-data", "活动水平数据台账", "activity"),
    VerificationRule("factor-parameters", "排放因子与计算参数来源", "factor"),
    VerificationRule("calculation-results", "排放量化结果和分项汇总", "inventory"),
    VerificationRule("evidence-files", "原始凭证和台账附件", "evidence"),
    VerificationRule("audit-trail", "内部审核与修正记录", "audit"),
    VerificationRule("quality-issues", "数据质量问题和整改记录", "quality", required=False),
)


def material_readiness(statuses: list[str]) -> str:
    if not statuses:
        return "empty"
    if any(status in {MISSING_FACTOR_STATUS, MISSING_RESULT_STATUS} for status in statuses):
        return "blocked"
    if any(status in {MISSING_EVIDENCE_STATUS, PENDING_REVIEW_STATUS, REJECTED_STATUS} for status in statuses):
        return "attention"
    return READY_STATUS


def validate_finding_status(status: str) -> None:
    if status not in FINDING_STATUSES:
        msg = f"不支持的核查发现状态: {status}"
        raise ValueError(msg)


def validate_finding_severity(severity: str) -> None:
    if severity not in FINDING_SEVERITIES:
        msg = f"不支持的核查发现等级: {severity}"
        raise ValueError(msg)


def validate_finding_transition(current_status: str, next_status: str) -> None:
    validate_finding_status(next_status)
    if current_status == next_status:
        return
    allowed = FINDING_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        msg = f"核查发现状态不能从 {current_status} 变更为 {next_status}"
        raise ValueError(msg)


def finding_readiness(statuses: list[str]) -> str:
    if not statuses:
        return "empty"
    if any(status in {FINDING_OPEN, FINDING_RECTIFYING} for status in statuses):
        return "attention"
    if any(status == FINDING_RESOLVED for status in statuses):
        return "review"
    return READY_STATUS


def validate_template_status(status: str) -> None:
    if status not in TEMPLATE_STATUSES:
        msg = f"不支持的报告模板状态: {status}"
        raise ValueError(msg)


def template_usable(status: str) -> bool:
    validate_template_status(status)
    return status == TEMPLATE_ACTIVE


def validate_project_status(status: str) -> None:
    if status not in PROJECT_STATUSES:
        msg = f"不支持的核查项目状态: {status}"
        raise ValueError(msg)


def validate_project_transition(current_status: str, next_status: str) -> None:
    validate_project_status(next_status)
    if current_status == next_status:
        return
    allowed = PROJECT_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        msg = f"核查项目状态不能从 {current_status} 变更为 {next_status}"
        raise ValueError(msg)


def project_readiness(*, finding_open_count: int, missing_evidence_count: int, missing_result_count: int) -> str:
    if missing_result_count > 0:
        return "blocked"
    if finding_open_count > 0 or missing_evidence_count > 0:
        return "attention"
    return READY_STATUS
