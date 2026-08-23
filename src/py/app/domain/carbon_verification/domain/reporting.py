"""Typed organization-GHG report contracts and formal export gates."""

from __future__ import annotations

from typing import Any, cast

import msgspec


class ReportCheck(msgspec.Struct, frozen=True, kw_only=True):
    """One auditable prerequisite for a formal report export."""

    code: str
    label: str
    status: str
    detail: str | None = None


class ReportReadiness(msgspec.Struct, frozen=True, kw_only=True):
    """Formal report readiness derived from frozen inventory data."""

    status: str
    checks: list[ReportCheck]
    blocking_count: int
    warning_count: int


class RegulatoryTemplateDescriptor(msgspec.Struct, frozen=True, kw_only=True):
    """Immutable routing metadata for a domestic report specification."""

    template_code: str
    report_purpose: str
    jurisdiction: str
    program_code: str
    industry_codes: tuple[str, ...]
    standard_name: str
    standard_code: str
    technical_spec_code: str | None
    effective_from: str
    renderer_kind: str
    schema_version: str
    implementation_status: str
    source_url: str


class ReportEnterprise(msgspec.Struct, frozen=True, kw_only=True):
    """Frozen report-subject identity."""

    name: str
    code: str
    unify_code: str | None = None
    organization_type: str | None = None
    industry: str | None = None
    registered_address: str | None = None
    operation_address: str | None = None


class ReportPeriod(msgspec.Struct, frozen=True, kw_only=True):
    """Frozen reporting period and base year."""

    year: int
    period_start: str
    period_end: str
    base_year: int | None = None


class ReportTemplateReference(msgspec.Struct, frozen=True, kw_only=True):
    """Resolved report template and regulatory routing metadata."""

    template_code: str
    version: str
    standard_name: str
    standard_code: str
    renderer_kind: str
    schema_version: str
    implementation_status: str
    report_purpose: str


class OrganizationReportContext(msgspec.Struct, frozen=True, kw_only=True):
    """Strongly typed top-level contract consumed by the report renderer."""

    enterprise: ReportEnterprise
    reporting_period: ReportPeriod
    template: ReportTemplateReference
    project: dict[str, Any]
    standard: dict[str, Any]
    inventory: dict[str, Any]
    inventory_source: dict[str, Any]
    activity_data: list[dict[str, Any]]
    factor_parameters: list[dict[str, Any]]
    verification_attachments: list[dict[str, Any]]
    quality_issues: list[dict[str, Any]]
    verification_findings: list[dict[str, Any]]
    formal_readiness: dict[str, Any]
    exclusions: list[dict[str, Any]]


ISO_CATEGORY_LABELS: dict[str, str] = {
    "1": "直接温室气体排放和清除",
    "2": "输入能源产生的间接温室气体排放",
    "3": "运输产生的间接温室气体排放",
    "4": "组织使用的产品产生的间接温室气体排放",
    "5": "与组织产品使用相关的间接温室气体排放",
    "6": "其他来源产生的间接温室气体排放",
}

SCOPE3_CATEGORY_LABELS: dict[str, str] = {
    str(index): label
    for index, label in enumerate(
        (
            "购买的商品和服务",
            "资本货物",
            "燃料和能源相关活动",
            "上游运输和配送",
            "运营中产生的废弃物",
            "商务旅行",
            "员工通勤",
            "上游租赁资产",
            "下游运输和配送",
            "售出产品的加工",
            "售出产品的使用",
            "售出产品的报废处理",
            "下游租赁资产",
            "特许经营",
            "投资",
        ),
        start=1,
    )
}


def formal_report_readiness(report: dict[str, Any]) -> ReportReadiness:
    """Evaluate whether a frozen inventory can be exported as a formal report."""

    activities = _rows(report, "activity_data")
    factors = _rows(report, "factor_parameters")
    evidence = _rows(report, "verification_attachments")
    issues = _rows(report, "quality_issues")
    findings = _rows(report, "verification_findings")
    enterprise = _mapping(report.get("enterprise"))
    template = _mapping(report.get("template"))
    inventory_source = _mapping(report.get("inventory_source"))
    factor_codes = {str(row.get("record_code")) for row in factors if row.get("record_code")}
    evidence_codes = {
        str(row.get("record_code"))
        for row in evidence
        if row.get("record_code") and row.get("material_status") == "ready"
    }
    activity_codes = {str(row.get("record_code")) for row in activities if row.get("record_code")}
    open_findings = [row for row in findings if row.get("status") not in {"closed", "accepted"}]

    checks = [
        _check(
            "organization",
            "报告主体",
            bool(enterprise.get("name") and enterprise.get("code")),
            "组织名称和统一标识必须完整",
        ),
        _check(
            "published_inventory",
            "已发布盘查结果",
            inventory_source.get("status") == "published",
            "仅允许使用已发布盘查报告",
        ),
        _check("activities", "活动数据", bool(activities), "报告期必须至少包含一条纳入边界的活动数据"),
        _check(
            "factors",
            "排放因子及参数",
            bool(activity_codes) and activity_codes <= factor_codes,
            "每条活动数据必须冻结计算参数及来源",
        ),
        _check(
            "evidence",
            "原始凭证",
            bool(activity_codes) and activity_codes <= evidence_codes,
            "每条活动数据必须具备已复核证据",
        ),
        _check("quality", "数据质量", not issues, "正式报告不得存在未解决的数据质量问题"),
        _check("findings", "核查问题", not open_findings, "正式报告不得存在未关闭核查问题"),
        _check(
            "boundary",
            "组织边界",
            inventory_source.get("boundary_status") == "published",
            "正式报告必须引用已发布的组织边界版本",
        ),
        _check(
            "template",
            "报告模板",
            template.get("implementation_status") == "supported",
            "所选年度和行业必须具备已实现的现行模板适配器",
        ),
    ]
    blocking_count = sum(check.status == "blocked" for check in checks)
    warning_count = sum(check.status == "warning" for check in checks)
    return ReportReadiness(
        status="ready" if blocking_count == 0 else "blocked",
        checks=checks,
        blocking_count=blocking_count,
        warning_count=warning_count,
    )


def readiness_dict(readiness: ReportReadiness) -> dict[str, Any]:
    """Serialize the msgspec contract for existing dict-based APIs."""

    return msgspec.to_builtins(readiness)


def validate_report_context(report: dict[str, Any]) -> OrganizationReportContext:
    """Validate the API dictionary at the renderer boundary."""

    return msgspec.convert(report, type=OrganizationReportContext, strict=False)


def _rows(report: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = report.get(key)
    if not isinstance(value, list):
        return []
    rows = cast("list[Any]", value)
    return [cast("dict[str, Any]", row) for row in rows if isinstance(row, dict)]


def _mapping(value: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _check(code: str, label: str, passed: bool, detail: str) -> ReportCheck:
    return ReportCheck(
        code=code, label=label, status="ready" if passed else "blocked", detail=None if passed else detail
    )
