from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
FINDING_TRANSITIONS = {
    FINDING_OPEN: {FINDING_RECTIFYING, FINDING_RESOLVED, FINDING_CLOSED},
    FINDING_RECTIFYING: {FINDING_OPEN, FINDING_RESOLVED},
    FINDING_RESOLVED: {FINDING_RECTIFYING, FINDING_CLOSED},
    FINDING_CLOSED: set(),
}

ATTACHMENT_PENDING_UPLOAD = "pending_upload"
ATTACHMENT_READY = "ready"
ATTACHMENT_ARCHIVED = "archived"
ATTACHMENT_REJECTED = "rejected"
ATTACHMENT_STATUSES = {ATTACHMENT_PENDING_UPLOAD, ATTACHMENT_READY, ATTACHMENT_ARCHIVED, ATTACHMENT_REJECTED}
ATTACHMENT_TYPES = {"supporting_document", "invoice", "meter_record", "calibration_certificate", "inspection_report", "other"}


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


def record_material_status(record: dict[str, Any]) -> str:
    status = str(record.get("status") or "")
    if status == "rejected":
        return REJECTED_STATUS
    if status == "pending":
        return PENDING_REVIEW_STATUS
    if not record.get("factor_source"):
        return MISSING_FACTOR_STATUS
    if record.get("computed_co2e") in (None, ""):
        return MISSING_RESULT_STATUS
    if not record.get("attachment") and not record.get("verification_attachment_count"):
        return MISSING_EVIDENCE_STATUS
    return READY_STATUS


def material_readiness(statuses: list[str]) -> str:
    if not statuses:
        return "empty"
    if any(status in {MISSING_FACTOR_STATUS, MISSING_RESULT_STATUS} for status in statuses):
        return "blocked"
    if any(status in {MISSING_EVIDENCE_STATUS, PENDING_REVIEW_STATUS, REJECTED_STATUS} for status in statuses):
        return "attention"
    return READY_STATUS


def issue_for_status(record: dict[str, Any]) -> dict[str, Any] | None:
    status = record_material_status(record)
    if status == READY_STATUS:
        return None
    issue_map = {
        MISSING_EVIDENCE_STATUS: ("缺少原始凭证", "medium", "补充发票、台账、计量记录或第三方单据附件。"),
        MISSING_FACTOR_STATUS: ("缺少排放因子", "high", "匹配排放因子来源、年份、单位和适用范围。"),
        MISSING_RESULT_STATUS: ("缺少核算结果", "high", "重新核算并保存 CO2e 结果。"),
        PENDING_REVIEW_STATUS: ("记录待审核", "medium", "完成内部审核后再纳入最终报告。"),
        REJECTED_STATUS: ("记录已驳回", "high", "按驳回原因修正或从报告范围中排除。"),
    }
    title, severity, action = issue_map[status]
    return {
        "issue_type": status,
        "severity": severity,
        "title": title,
        "record_type": record.get("record_type"),
        "record_id": record.get("record_id"),
        "scope": record.get("scope"),
        "display_name": record.get("display_name"),
        "period": record.get("period"),
        "action": action,
    }


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


def validate_attachment_status(status: str) -> None:
    if status not in ATTACHMENT_STATUSES:
        msg = f"不支持的核查附件状态: {status}"
        raise ValueError(msg)


def validate_attachment_type(attachment_type: str) -> None:
    if attachment_type not in ATTACHMENT_TYPES:
        msg = f"不支持的核查附件类型: {attachment_type}"
        raise ValueError(msg)


def attachment_material_status(status: str, file_path: str | None) -> str:
    validate_attachment_status(status)
    if status == ATTACHMENT_READY and file_path:
        return READY_STATUS
    if status == ATTACHMENT_REJECTED:
        return REJECTED_STATUS
    return MISSING_EVIDENCE_STATUS
