"""Editable report prose stored on the existing report version."""

MAX_NARRATIVE_LENGTH = 10000
NARRATIVE_FIELDS = {
    "purpose": "编制目的与预期用途",
    "intended_users": "预期使用者与披露范围",
    "prepared_by": "编制负责人及联系方式",
    "boundary_rationale": "边界确定与重要性评价",
    "base_year_policy": "基准年选择与重新计算政策",
    "monitoring_procedures": "数据收集与监测方法",
    "missing_data_treatment": "缺失数据与估算处理",
    "quality_controls": "质量管理与记录保存",
    "uncertainty_assessment": "不确定性评价",
    "results_commentary": "排放结果分析",
    "reduction_actions": "减排措施与绩效",
}


def validate_narrative(value: dict[str, str]) -> dict[str, str]:
    """Reject unknown fields and non-text content rather than silently dropping it."""
    if value.keys() - NARRATIVE_FIELDS.keys():
        msg = "报告正文包含未定义字段"
        raise ValueError(msg)
    for key, text in value.items():
        if not isinstance(text, str) or len(text) > MAX_NARRATIVE_LENGTH:
            msg = f"{NARRATIVE_FIELDS[key]}必须为不超过10000字的文本"
            raise ValueError(msg)
    return {key: text.strip() for key, text in value.items() if text.strip()}
