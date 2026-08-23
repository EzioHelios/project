"""Domestic organization-GHG report template registry and routing rules."""

from __future__ import annotations

from app.domain.carbon_verification.domain.reporting import RegulatoryTemplateDescriptor

GENERIC_ORGANIZATION_REPORT = RegulatoryTemplateDescriptor(
    template_code="organization_ghg_generic",
    report_purpose="organization_inventory",
    jurisdiction="CN",
    program_code="corporate_inventory",
    industry_codes=("generic", "other"),
    standard_name="工业企业温室气体排放核算和报告通则",
    standard_code="GB/T 32150—2025",
    technical_spec_code=None,
    effective_from="2026-07-01",
    renderer_kind="generic_a4",
    schema_version="2026.1",
    implementation_status="supported",
    source_url="https://std.samr.gov.cn/gb/search/gbDetailed?id=473EBB99D6C3455EE06397BE0A0ABB9A",
)


REGULATORY_TEMPLATES: tuple[RegulatoryTemplateDescriptor, ...] = (
    GENERIC_ORGANIZATION_REPORT,
    RegulatoryTemplateDescriptor(
        template_code="ets_power_2026",
        report_purpose="national_ets",
        jurisdiction="CN",
        program_code="national_ets",
        industry_codes=("power", "electricity", "发电", "电力"),
        standard_name="企业温室气体排放核算与报告指南 发电设施",
        standard_code="CETS-AG-01.01-V04-2026",
        technical_spec_code="CETS-AG-01.01-V04-2026",
        effective_from="2026-01-01",
        renderer_kind="ets_power_2026",
        schema_version="2026.1",
        implementation_status="registered",
        source_url="https://www.mee.gov.cn/xxgk2018/xxgk/xxgk06/202606/t20260629_1160473.html",
    ),
    RegulatoryTemplateDescriptor(
        template_code="ets_steel_2024",
        report_purpose="national_ets",
        jurisdiction="CN",
        program_code="national_ets",
        industry_codes=("steel", "钢铁"),
        standard_name="企业温室气体排放核算与报告指南 钢铁行业",
        standard_code="CETS-AG-03.01-V01-2024",
        technical_spec_code="CETS-AG-03.01-V01-2024",
        effective_from="2024-01-01",
        renderer_kind="ets_steel_2024",
        schema_version="2024.1",
        implementation_status="registered",
        source_url="https://www.mee.gov.cn/xxgk2018/xxgk/xxgk06/202501/t20250124_1101316.html",
    ),
    RegulatoryTemplateDescriptor(
        template_code="ets_cement_2024",
        report_purpose="national_ets",
        jurisdiction="CN",
        program_code="national_ets",
        industry_codes=("cement", "水泥"),
        standard_name="企业温室气体排放核算与报告指南 水泥行业",
        standard_code="CETS-AG-02.01-V01-2024",
        technical_spec_code="CETS-AG-02.01-V01-2024",
        effective_from="2024-01-01",
        renderer_kind="ets_cement_2024",
        schema_version="2024.1",
        implementation_status="registered",
        source_url="https://www.mee.gov.cn/xxgk2018/xxgk/xxgk06/202409/t20240914_1086067.html",
    ),
    RegulatoryTemplateDescriptor(
        template_code="ets_aluminum_2024",
        report_purpose="national_ets",
        jurisdiction="CN",
        program_code="national_ets",
        industry_codes=("aluminum", "铝冶炼", "电解铝"),
        standard_name="企业温室气体排放核算与报告指南 铝冶炼行业",
        standard_code="CETS-AG-04.01-V01-2024",
        technical_spec_code="CETS-AG-04.01-V01-2024",
        effective_from="2024-01-01",
        renderer_kind="ets_aluminum_2024",
        schema_version="2024.1",
        implementation_status="registered",
        source_url="https://www.mee.gov.cn/xxgk2018/xxgk/xxgk06/202409/t20240914_1086067.html",
    ),
)


def descriptor_for_template(template_code: str | None) -> RegulatoryTemplateDescriptor:
    """Return immutable routing metadata without treating unknown templates as supported."""

    matched = next(
        (item for item in REGULATORY_TEMPLATES if item.template_code == template_code),
        None,
    )
    if matched is not None:
        return matched
    return RegulatoryTemplateDescriptor(
        template_code=template_code or "unregistered",
        report_purpose="organization_inventory",
        jurisdiction="CN",
        program_code="unregistered",
        industry_codes=(),
        standard_name="未登记报告规范",
        standard_code="UNREGISTERED",
        technical_spec_code=None,
        effective_from="1900-01-01",
        renderer_kind="unimplemented",
        schema_version="0",
        implementation_status="registered",
        source_url="",
    )


def select_descriptor(*, purpose: str, industry: str | None, year: int | None) -> RegulatoryTemplateDescriptor:
    """Resolve a report specification without silently substituting another purpose."""

    del year  # Version windows are explicit in descriptors and reserved for the next update.
    if purpose != "national_ets":
        return GENERIC_ORGANIZATION_REPORT
    normalized = (industry or "").strip().lower()
    matched = next(
        (
            item
            for item in REGULATORY_TEMPLATES
            if item.report_purpose == purpose
            and normalized
            and any(code.lower() in normalized or normalized in code.lower() for code in item.industry_codes)
        ),
        None,
    )
    if matched is None:
        msg = "未找到适用于该行业和报告年度的全国碳市场报告规范"
        raise ValueError(msg)
    return matched
