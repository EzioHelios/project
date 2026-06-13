# ruff: noqa: RUF001
from __future__ import annotations

import datetime
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape

if TYPE_CHECKING:
    from pathlib import Path

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*[^{}]+\s*\}\}")


@dataclass(frozen=True, slots=True)
class RenderedReportFile:
    path: str
    content: bytes
    content_type: str
    source_name: str


class ReportDocumentRenderer:
    """Render organization-carbon verification report files from the report context."""

    def __init__(self, *, template_path: Path, output_dir: Path) -> None:
        self._template_path = template_path
        self._output_dir = output_dir

    def render(self, report: dict[str, Any]) -> list[RenderedReportFile]:
        if not self._template_path.exists():
            msg = f"报告模板不存在: {self._template_path}"
            raise FileNotFoundError(msg)

        self._output_dir.mkdir(parents=True, exist_ok=True)
        report_year = _safe_filename_part(_value_at(report, "reporting_period.year") or "all")
        stem = f"{report_year}-organization-ghg-report"
        docx_path = self._output_dir / f"{stem}.docx"
        pdf_path = self._output_dir / f"{stem}.pdf"

        mapping = _placeholder_mapping(report)
        _render_docx_template(self._template_path, docx_path, mapping)
        rendered = [
            RenderedReportFile(
                path=f"report/{docx_path.name}",
                content=docx_path.read_bytes(),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                source_name="carbon_verification.report_renderer",
            )
        ]

        if _convert_docx_to_pdf(docx_path, pdf_path):
            rendered.append(
                RenderedReportFile(
                    path=f"report/{pdf_path.name}",
                    content=pdf_path.read_bytes(),
                    content_type="application/pdf",
                    source_name="carbon_verification.report_renderer",
                )
            )
        return rendered


def _render_docx_template(template_path: Path, output_path: Path, mapping: dict[str, str]) -> None:
    with zipfile.ZipFile(template_path) as source, zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if _is_xml_part(info.filename):
                text = content.decode("utf-8")
                for placeholder, value in mapping.items():
                    text = text.replace(placeholder, _xml_text(value))
                text = PLACEHOLDER_PATTERN.sub(_xml_text("-"), text)
                content = text.encode("utf-8")
            target.writestr(info, content)


def _is_xml_part(filename: str) -> bool:
    return filename.endswith(".xml") and filename.startswith(("word/", "docProps/"))


def _convert_docx_to_pdf(docx_path: Path, pdf_path: Path) -> bool:
    converter = shutil.which("soffice") or shutil.which("libreoffice")
    if converter is None:
        return False
    result = subprocess.run(  # noqa: S603
        [converter, "--headless", "--convert-to", "pdf", "--outdir", str(pdf_path.parent), str(docx_path)],
        check=False,
        capture_output=True,
        timeout=90,
    )
    return result.returncode == 0 and pdf_path.exists()


def _placeholder_mapping(report: dict[str, Any]) -> dict[str, str]:
    enterprise = report.get("enterprise") if isinstance(report.get("enterprise"), dict) else {}
    reporting_period = report.get("reporting_period") if isinstance(report.get("reporting_period"), dict) else {}
    inventory = report.get("inventory") if isinstance(report.get("inventory"), dict) else {}
    totals = inventory.get("totals") if isinstance(inventory.get("totals"), dict) else {}
    source_summary = inventory.get("source_summary") if isinstance(inventory.get("source_summary"), list) else []
    scope_summary = inventory.get("scope_summary") if isinstance(inventory.get("scope_summary"), list) else []
    activity_data = report.get("activity_data") if isinstance(report.get("activity_data"), list) else []
    factor_parameters = report.get("factor_parameters") if isinstance(report.get("factor_parameters"), list) else []
    quality_issues = report.get("quality_issues") if isinstance(report.get("quality_issues"), list) else []
    verification_findings = report.get("verification_findings") if isinstance(report.get("verification_findings"), list) else []
    standard = report.get("standard") if isinstance(report.get("standard"), dict) else {}
    template = report.get("template") if isinstance(report.get("template"), dict) else {}

    direct = {
        "enterprise_name": _first_text(enterprise, "enterprise_name", "name", "company_name"),
        "org_code": _first_text(enterprise, "unify_code", "credit_code", "organization_code"),
        "organization_nature": _first_text(enterprise, "enterprise_type", "organization_nature", "ownership_type"),
        "legal_person": _first_text(enterprise, "legal_person", "legal_representative"),
        "registration_date": _first_text(enterprise, "registration_date", "established_at"),
        "registered_capital": _first_text(enterprise, "registered_capital"),
        "registered_address": _first_text(enterprise, "registered_address", "address"),
        "operation_address": _first_text(enterprise, "operation_address", "production_address", "address"),
        "contact_person": _first_text(enterprise, "contact_person", "contact_name"),
        "contact_tel": _first_text(enterprise, "contact_tel", "phone", "telephone"),
        "contact_email": _first_text(enterprise, "contact_email", "email"),
        "competent_authority": _first_text(enterprise, "competent_authority"),
        "industry_category": _first_text(enterprise, "industry_category", "industry"),
        "operation_change_summary": _first_text(enterprise, "operation_change_summary"),
        "report_year": reporting_period.get("year"),
        "period_start": reporting_period.get("period_start"),
        "period_end": reporting_period.get("period_end"),
        "generated_date": datetime.datetime.now(UTC).date().isoformat(),
        "signed_date": datetime.datetime.now(UTC).date().isoformat(),
        "accounting_standard_name": standard.get("name"),
        "accounting_standard_code": standard.get("code"),
        "report_version": template.get("version") or "v1.0",
        "reporting_boundary_description": _boundary_description(source_summary),
        "included_facilities_summary": _source_lines(source_summary),
        "excluded_sources_summary": "无已登记排除源；如存在排除源，应在正式报告中列明排除原因和影响。",
        "total_without_purchased_energy": _number(totals.get("total_t_co2e")),
        "total_with_purchased_energy": _number(totals.get("total_t_co2e")),
        "scope_summary": _scope_lines(scope_summary),
        "activity_data": _activity_lines(activity_data),
        "factor_parameters": _factor_lines(factor_parameters),
        "quality_issues": _issue_lines([*quality_issues, *verification_findings]),
        "evidence_manifest": "见核查材料包 evidence/evidence-manifest.csv。",
        "audit_trail": "见核查材料包 audit/audit-trail.csv。",
        "inventory_quality": _quality_status(quality_issues),
        "missing_data_status": "存在缺失项" if quality_issues else "未发现缺失项",
        "internal_review_status": "待内审确认" if quality_issues else "可提交内审",
        "monitoring_plan_status": "按现有活动数据记录和证据材料执行",
        "qa_policy_status": "按企业数据质量控制程序执行",
        "report_compiler_name": "-",
        "data_owner": "-",
        "qa_owner": "-",
        "review_owner": "-",
        "monitoring_owner": "-",
        "calibration_owner": "-",
        "monitoring_method": "台账、账单、计量记录和活动数据记录",
        "record_frequency": "月度或按业务发生记录",
        "calibration_status": "按计量器具管理记录确认",
        "boundary_method": "组织控制边界",
        "boundary_version": template.get("name") or "通用模板",
    }

    category_values = _category_values(activity_data)
    direct.update(category_values)
    direct.update(_default_yes_no_values(activity_data))
    direct.update(_generic_table_words())
    return {f"{{{{ {key} }}}}": _display(value) for key, value in direct.items()} | {"{{变量名}}": "-"}


def _first_text(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _category_values(activity_data: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, float] = {}
    for row in activity_data:
        label = str(row.get("source_category") or "")
        grouped[label] = grouped.get(label, 0.0) + float(row.get("computed_co2e") or 0)

    combustion = _sum_matching(grouped, "燃烧")
    purchased = _sum_matching(grouped, "外购")
    wastewater = _sum_matching(grouped, "废水")
    other = max(sum(grouped.values()) - combustion - purchased - wastewater, 0)
    return {
        "combustion_co2": _number(combustion / 1000),
        "combustion_co2e": _number(combustion / 1000),
        "combustion_facilities": _matched_labels(grouped, "燃烧"),
        "combustion_note": "按已登记燃料活动数据汇总。",
        "combustion_quality": "ready" if combustion else "not_applicable",
        "purchased_electricity_co2": _number(purchased / 1000),
        "purchased_electricity_co2e": _number(purchased / 1000),
        "purchased_heat_co2": "0",
        "purchased_heat_co2e": "0",
        "purchased_energy_activities": _matched_labels(grouped, "外购"),
        "purchased_energy_note": "按外购电力、热力、蒸汽、冷量记录汇总。",
        "electricity_quality": "ready" if purchased else "not_applicable",
        "heat_quality": "ready" if purchased else "not_applicable",
        "wastewater_ch4": "0",
        "wastewater_co2e": _number(wastewater / 1000),
        "wastewater_activities": _matched_labels(grouped, "废水"),
        "wastewater_note": "按废水相关活动数据汇总；无记录时为不适用。",
        "wastewater_quality": "ready" if wastewater else "not_applicable",
        "carbonate_co2": "0",
        "carbonate_co2e": "0",
        "carbonate_activities": "-",
        "carbonate_note": "无已登记碳酸盐使用记录。",
        "carbonate_quality": "not_applicable",
        "ch4_flared": "0",
        "ch4_flared_co2e": "0",
        "ch4_recovered_self": "0",
        "ch4_recovered_self_co2e": "0",
        "ch4_recovered_export": "0",
        "ch4_recovered_export_co2e": "0",
        "ch4_recovery_activities": "-",
        "ch4_recovery_note": "无已登记甲烷回收记录。",
        "ch4_flare_quality": "not_applicable",
        "ch4_recovery_quality": "not_applicable",
        "co2_recovery": "0",
        "co2_recovery_co2e": "0",
        "co2_recovery_activities": "-",
        "co2_recovery_note": "无已登记二氧化碳回收记录。",
        "co2_recovery_quality": "not_applicable",
        "other_gases": _number(other / 1000),
        "other_co2e": _number(other / 1000),
        "other_sources": _matched_labels(grouped, ""),
        "other_sources_note": "其余来源按已登记范围三或其他活动数据汇总。",
        "other_quality": "ready" if other else "not_applicable",
        "other_statement": "本报告数据来自系统内已登记活动数据、排放因子和证据材料。",
    }


def _default_yes_no_values(activity_data: list[dict[str, Any]]) -> dict[str, str]:
    text = "\n".join(str(row.get("source_category") or "") for row in activity_data)
    return {
        "yes_no_combustion": _yes_no("燃烧" in text),
        "yes_no_purchased_energy": _yes_no("外购" in text),
        "yes_no_wastewater": _yes_no("废水" in text),
        "yes_no_carbonate": _yes_no("碳酸盐" in text),
        "yes_no_ch4_recovery": _yes_no("甲烷" in text),
        "yes_no_co2_recovery": _yes_no("回收" in text),
        "yes_no_other_sources": _yes_no(bool(activity_data)),
    }


def _generic_table_words() -> dict[str, str]:
    return {
        "期间": "-",
        "设施": "-",
        "数据项": "-",
        "数值": "-",
        "单位": "-",
        "来源": "-",
        "状态": "-",
        "证据": "-",
        "参数": "-",
        "类别": "-",
        "值": "-",
        "置信": "-",
        "有效期": "-",
        "因子": "-",
        "记录": "-",
        "问题": "-",
        "影响": "-",
        "措施": "-",
        "结论": "-",
        "结果": "-",
        "说明": "-",
        "描述": "-",
        "购入": "0",
        "外供": "0",
        "净购入": "0",
        "低热值": "-",
        "含碳量": "-",
        "氧化率": "-",
        "排放量": "-",
    }


def _boundary_description(source_summary: list[dict[str, Any]]) -> str:
    if not source_summary:
        return "尚未登记排放源活动数据。"
    scopes = sorted({str(item.get("scope") or "未分组") for item in source_summary})
    return f"本报告覆盖系统内已登记的{', '.join(scopes)}排放源。"


def _source_lines(items: list[dict[str, Any]]) -> str:
    if not items:
        return "-"
    return "\n".join(
        f"{item.get('scope') or '-'} / {item.get('record_label') or '-'}：{item.get('record_count') or 0} 条，"
        f"{_number(item.get('t_co2e'))} tCO2e"
        for item in items[:20]
    )


def _scope_lines(items: list[dict[str, Any]]) -> str:
    if not items:
        return "-"
    return "\n".join(
        f"{item.get('scope') or '-'}：{item.get('record_count') or 0} 条，{_number(item.get('t_co2e'))} tCO2e"
        for item in items
    )


def _activity_lines(items: list[dict[str, Any]]) -> str:
    if not items:
        return "-"
    return "\n".join(
        f"{item.get('period') or '-'} {item.get('scope') or '-'} {item.get('source_category') or '-'} "
        f"{item.get('activity_name') or '-'}：{_number(item.get('activity_amount'))} {item.get('activity_unit') or ''}，"
        f"{_number(float(item.get('computed_co2e') or 0) / 1000)} tCO2e"
        for item in items[:50]
    )


def _factor_lines(items: list[dict[str, Any]]) -> str:
    if not items:
        return "-"
    return "\n".join(
        f"{item.get('factor_source') or '-'}，{item.get('factor_year') or '-'}，{item.get('factor_unit') or '-'}"
        for item in items[:50]
    )


def _issue_lines(items: list[dict[str, Any]]) -> str:
    if not items:
        return "未发现待处理问题。"
    return "\n".join(
        f"{item.get('severity') or '-'} / {item.get('issue_type') or '-'}：{item.get('message') or '-'}"
        for item in items[:50]
    )


def _quality_status(items: list[dict[str, Any]]) -> str:
    return "存在待处理问题" if items else "未发现待处理问题"


def _sum_matching(grouped: dict[str, float], needle: str) -> float:
    return sum(value for label, value in grouped.items() if needle in label)


def _matched_labels(grouped: dict[str, float], needle: str) -> str:
    labels = [label for label, value in grouped.items() if value and (not needle or needle in label)]
    return "、".join(labels[:20]) if labels else "-"


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def _number(value: Any) -> str:
    if value in (None, ""):
        return "0"
    number = float(value)
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _value_at(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _display(value: Any) -> str:
    if value in (None, ""):
        return "-"
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return str(value)


def _xml_text(value: str) -> str:
    return escape(value).replace("\n", "</w:t><w:br/><w:t>")


def _safe_filename_part(value: Any) -> str:
    text = str(value)
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-") or "all"
