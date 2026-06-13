from __future__ import annotations

from dataclasses import dataclass
from typing import Any

READY_STATUS = "ready"
MISSING_EVIDENCE_STATUS = "missing_evidence"
MISSING_FACTOR_STATUS = "missing_factor"
MISSING_RESULT_STATUS = "missing_result"
PENDING_REVIEW_STATUS = "pending_review"
REJECTED_STATUS = "rejected"


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
    if not record.get("attachment"):
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

