# ruff: noqa: RUF001, SLF001, TC002, TC003
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportPrivateUsage=false, reportAttributeAccessIssue=false
"""Formal A4 organization-GHG report rendering."""

from __future__ import annotations

import datetime
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC
from decimal import Decimal
from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from app.domain.carbon_verification.domain.reporting import validate_report_context


@dataclass(frozen=True, slots=True)
class RenderedReportFile:
    """One rendered report artifact."""

    path: str
    content: bytes
    content_type: str
    source_name: str


class ReportDocumentRenderer:
    """Render a domestic organization-GHG report from a frozen report context."""

    def __init__(self, *, template_path: Path | None, output_dir: Path) -> None:
        self._template_path = template_path
        self._output_dir = output_dir

    def render(self, report: dict[str, Any]) -> list[RenderedReportFile]:
        validate_report_context(report)
        template = _mapping(report.get("template"))
        if template.get("implementation_status") != "supported" or template.get("renderer_kind") != "generic_a4":
            msg = "所选行业和年度尚未实现正式监管报告适配器"
            raise ValueError(msg)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        year = _safe_filename_part(_mapping(report.get("reporting_period")).get("year") or "all")
        stem = f"{year}-organization-ghg-report"
        docx_path = self._output_dir / f"{stem}.docx"
        pdf_path = self._output_dir / f"{stem}.pdf"
        document = _build_document(report)
        document.save(str(docx_path))
        rendered = [
            RenderedReportFile(
                path=f"report/{docx_path.name}",
                content=docx_path.read_bytes(),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                source_name="carbon_verification.organization_report",
            )
        ]
        if _convert_docx_to_pdf(docx_path, pdf_path):
            rendered.append(
                RenderedReportFile(
                    path=f"report/{pdf_path.name}",
                    content=pdf_path.read_bytes(),
                    content_type="application/pdf",
                    source_name="carbon_verification.organization_report",
                )
            )
        return rendered


def _build_document(report: dict[str, Any]) -> DocumentObject:
    document = Document()
    _configure_document(document)
    _cover(document, report)
    _declaration(document, report)
    _contents(document)
    _organization_section(document, report)
    _basis_and_boundary_section(document, report)
    _inventory_chart_section(document, report)
    _inventory_summary_section(document, report)
    _activity_section(document, report)
    _factor_section(document, report)
    _quality_section(document, report)
    _evidence_section(document, report)
    _approval_section(document, report)
    return document


def _configure_document(document: DocumentObject) -> None:
    section = document.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin, section.bottom_margin = Cm(2.5), Cm(2.3)
    section.left_margin, section.right_margin = Cm(2.6), Cm(2.4)
    section.header_distance, section.footer_distance = Cm(1.2), Cm(1.2)
    normal = document.styles["Normal"]
    _style_font(normal, "宋体", 10.5)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(3)
    for name, size in (("Title", 22), ("Heading 1", 15), ("Heading 2", 12)):
        style = document.styles[name]
        _style_font(style, "黑体", size, bold=True, color="000000")
        _clear_style_paragraph_borders(style)
    document.styles["Heading 1"].paragraph_format.space_before = Pt(12)
    document.styles["Heading 1"].paragraph_format.space_after = Pt(8)
    document.styles["Heading 2"].paragraph_format.space_before = Pt(8)
    document.styles["Heading 2"].paragraph_format.space_after = Pt(5)
    header = section.header.paragraphs[0]
    header.text, header.alignment = "组织温室气体排放盘查报告", WD_ALIGN_PARAGRAPH.RIGHT
    _set_run_font(header.runs[0], "宋体", 8, color="666666")
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_page_number(footer)
    document.core_properties.title = "组织温室气体排放盘查报告"
    document.core_properties.author = "能碳管理平台"


def _cover(document: DocumentObject, report: dict[str, Any]) -> None:
    enterprise, period = _mapping(report.get("enterprise")), _mapping(report.get("reporting_period"))
    template, project = _mapping(report.get("template")), _mapping(report.get("project"))
    document.add_paragraph().paragraph_format.space_after = Pt(70)
    title = document.add_paragraph("组织温室气体排放盘查报告", style="Title")
    title.alignment, title.paragraph_format.space_after = WD_ALIGN_PARAGRAPH.CENTER, Pt(36)
    document.add_paragraph().paragraph_format.space_after = Pt(42)
    rows = (
        ("报告主体（盖章）", enterprise.get("name")),
        ("统一社会信用代码", enterprise.get("unify_code") or enterprise.get("code")),
        ("报告年度", period.get("year")),
        ("编制日期", datetime.datetime.now(UTC).date().isoformat()),
        ("核算依据", f"{_display(template.get('standard_name'))} / {_display(template.get('standard_code'))}"),
        ("报告版本", project.get("report_version")),
    )
    _key_value_table(document, rows)
    document.add_page_break()


def _declaration(document: DocumentObject, report: dict[str, Any]) -> None:
    _heading(document, "一、报告声明", 1)
    enterprise, period = _mapping(report.get("enterprise")), _mapping(report.get("reporting_period"))
    paragraphs = (
        f"本报告由{_display(enterprise.get('name'))}依据已发布的组织温室气体盘查结果编制，报告期为"
        f"{_display(period.get('period_start'))}至{_display(period.get('period_end'))}。",
        "报告中的组织边界、活动数据、排放因子、温室气体排放量及证据索引均来自报告发布时冻结的数据快照。",
        "报告主体对所提供资料的真实性、完整性和一致性负责；任何后续修订均应形成新版本并保留变更记录。",
        "本报告适用于组织碳盘查成果归档、内部复核、核查支撑材料准备及披露材料编制。",
    )
    for text in paragraphs:
        paragraph = document.add_paragraph(text)
        paragraph.paragraph_format.first_line_indent = Cm(0.74)
    _signature_grid(document, ("编制人", "复核人", "批准人"))
    document.add_page_break()


def _contents(document: DocumentObject) -> None:
    _heading(document, "目录", 1)
    for entry in (
        "一、报告声明",
        "二、报告主体基本情况",
        "三、核算边界与排放源识别",
        "四、温室气体排放关键图表",
        "五、温室气体排放量化明细",
        "六、活动水平数据及来源说明",
        "七、排放因子与计算参数说明",
        "八、数据质量控制与文件存档",
        "九、编制、复核与批准",
    ):
        paragraph = document.add_paragraph(entry)
        paragraph.paragraph_format.left_indent, paragraph.paragraph_format.space_after = Cm(0.8), Pt(8)
    document.add_page_break()


def _organization_section(document: DocumentObject, report: dict[str, Any]) -> None:
    _heading(document, "二、报告主体基本情况", 1)
    enterprise, period = _mapping(report.get("enterprise")), _mapping(report.get("reporting_period"))
    rows = (
        ("组织名称", enterprise.get("name"), "统一标识", enterprise.get("unify_code") or enterprise.get("code")),
        ("组织类型", enterprise.get("organization_type"), "所属行业", enterprise.get("industry")),
        ("注册地址", enterprise.get("registered_address"), "运营地址", enterprise.get("operation_address")),
        (
            "报告期",
            f"{_display(period.get('period_start'))} 至 {_display(period.get('period_end'))}",
            "基准年",
            period.get("base_year"),
        ),
    )
    table = _table(document, len(rows), 4, widths=(2.6, 5.0, 2.8, 5.2))
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            _set_cell(table.cell(row_index, column_index), value, header=column_index in {0, 2})


def _basis_and_boundary_section(document: DocumentObject, report: dict[str, Any]) -> None:
    _heading(document, "三、核算边界与排放源识别", 1)
    standard, template = _mapping(report.get("standard")), _mapping(report.get("template"))
    source, inventory = _mapping(report.get("inventory_source")), _mapping(report.get("inventory"))
    _key_value_table(
        document,
        (
            (
                "核算与报告依据",
                f"{_display(template.get('standard_name') or standard.get('name'))}（{_display(template.get('standard_code') or standard.get('code'))}）",
            ),
            ("模板与数据结构版本", f"{_display(template.get('version'))} / {_display(template.get('schema_version'))}"),
            ("组织边界版本", _display(source.get("boundary_no"))),
            ("Scope 2 默认方法", _scope2_label(inventory.get("default_scope2_method"))),
            ("GWP 版本", "、".join(str(item) for item in inventory.get("gwp_versions", [])) or "未记录"),
        ),
    )
    _heading(document, "（一）纳入边界的排放源", 2)
    _data_table(
        document,
        ("Scope", "排放源", "记录数", "排放量（tCO₂e）"),
        [
            (
                _scope_label(row.get("scope")),
                row.get("record_label"),
                row.get("record_count"),
                _number(row.get("t_co2e")),
            )
            for row in _rows(inventory, "source_summary")
        ],
        widths=(2.5, 7.2, 2.3, 3.5),
    )
    _heading(document, "（二）排除项", 2)
    exclusions = _rows(report, "exclusions")
    if exclusions:
        _data_table(
            document,
            ("排除项", "理由", "影响评估"),
            [(row.get("name"), row.get("reason"), row.get("impact")) for row in exclusions],
            widths=(4.2, 6.2, 5.1),
        )
    else:
        document.add_paragraph("本报告冻结数据中未登记排除项。")


def _inventory_chart_section(document: DocumentObject, report: dict[str, Any]) -> None:
    document.add_page_break()
    _heading(document, "四、温室气体排放关键图表", 1)
    inventory = _mapping(report.get("inventory"))
    totals = _mapping(inventory.get("totals"))
    activity_rows = _rows(report, "activity_data")
    evidence_rows = _rows(report, "verification_attachments")
    total_t = _decimal(totals.get("total_t_co2e"))
    _key_value_table(
        document,
        (
            ("报告期排放总量", f"{_number(total_t)} tCO₂e"),
            ("活动数据记录", f"{len(activity_rows)} 条"),
            ("证据文件记录", f"{len(evidence_rows)} 项"),
        ),
    )
    _heading(document, "（一）按 Scope 排放构成", 2)
    _bar_chart_table(
        document,
        [
            (_scope_label(row.get("scope")), _decimal(row.get("t_co2e")))
            for row in _rows(inventory, "scope_summary")
        ],
        total=total_t,
        widths=(3.2, 6.0, 2.8, 2.4),
    )
    _heading(document, "（二）主要排放源贡献", 2)
    source_rows = sorted(
        (
            (_display(row.get("record_label")), _decimal(row.get("t_co2e")))
            for row in _rows(inventory, "source_summary")
        ),
        key=lambda item: item[1],
        reverse=True,
    )[:8]
    _bar_chart_table(document, source_rows, total=total_t, widths=(4.6, 5.0, 2.7, 2.2), font_size=7.5)
    document.add_page_break()


def _inventory_summary_section(document: DocumentObject, report: dict[str, Any]) -> None:
    _heading(document, "五、温室气体排放量化明细", 1)
    inventory, totals = _mapping(report.get("inventory")), _mapping(_mapping(report.get("inventory")).get("totals"))
    paragraph = document.add_paragraph()
    paragraph.add_run("报告期温室气体排放总量：").bold = True
    total_run = paragraph.add_run(f"{_number(totals.get('total_t_co2e'))} tCO₂e")
    _set_run_font(total_run, "Arial", 12, bold=True, color="000000")
    for heading, rows, key, labeler in (
        ("（一）按 Scope 汇总", _rows(inventory, "scope_summary"), "scope", _scope_label),
        ("（二）按温室气体汇总", _rows(inventory, "gas_summary"), "gas_code", _uppercase_label),
        ("（三）按 ISO 14064-1 六类汇总", _rows(inventory, "iso_category_summary"), "label", _display),
        ("（四）Scope 2 方法结果", _rows(inventory, "scope2_method_summary"), "method", _scope2_label),
        ("（五）Scope 3 类别结果", _rows(inventory, "scope3_category_summary"), "label", _display),
    ):
        if rows:
            _heading(document, heading, 2)
            _summary_table(document, rows, key, labeler)


def _activity_section(document: DocumentObject, report: dict[str, Any]) -> None:
    document.add_section(WD_SECTION.NEW_PAGE)
    _heading(document, "六、活动水平数据及来源说明", 1)
    _data_table(
        document,
        ("记录编号", "Scope/ISO类", "活动数据", "数量", "单位", "排放量（tCO₂e）", "证据状态"),
        [
            (
                row.get("record_code"),
                f"{_scope_label(row.get('scope'))} / {row.get('iso_category_code') or '—'}",
                row.get("activity_name") or row.get("source_category"),
                _number(row.get("activity_amount")),
                row.get("activity_unit"),
                _number(_decimal(row.get("computed_co2e")) / Decimal(1000)),
                _material_status(row.get("evidence_status")),
            )
            for row in _rows(report, "activity_data")
        ],
        widths=(2.8, 2.4, 4.1, 2.0, 1.8, 2.5, 2.3),
        font_size=7.5,
    )


def _factor_section(document: DocumentObject, report: dict[str, Any]) -> None:
    _heading(document, "七、排放因子与计算参数说明", 1)
    _data_table(
        document,
        ("记录编号", "Scope", "参数来源", "版本/年份", "单位"),
        [
            (
                row.get("record_code"),
                _scope_label(row.get("scope")),
                row.get("factor_source"),
                row.get("factor_version"),
                row.get("factor_unit"),
            )
            for row in _rows(report, "factor_parameters")
        ],
        widths=(3.2, 2.1, 6.2, 2.6, 2.6),
        font_size=8,
    )


def _quality_section(document: DocumentObject, report: dict[str, Any]) -> None:
    _heading(document, "八、数据质量控制与文件存档", 1)
    issues, findings = _rows(report, "quality_issues"), _rows(report, "verification_findings")
    readiness = _mapping(report.get("formal_readiness"))
    _key_value_table(
        document,
        (
            ("正式报告就绪状态", "满足正式导出条件" if readiness.get("status") == "ready" else "存在待完善事项"),
            ("数据质量问题", f"{len(issues)} 项"),
            ("核查发现", f"{len(findings)} 项"),
            (
                "不确定性管理",
                "活动数据、计算参数、计量与证据状态按记录逐项留痕；重大估算和替代数据应在审批记录中说明。",
            ),
        ),
    )
    issue_rows = [(row.get("record_code"), row.get("title"), row.get("severity"), row.get("action")) for row in issues]
    issue_rows += [
        (row.get("finding_no"), row.get("title"), row.get("severity"), row.get("status")) for row in findings
    ]
    if issue_rows:
        _data_table(document, ("编号", "事项", "级别", "处理状态/要求"), issue_rows, widths=(3.0, 5.4, 2.0, 5.4))
    else:
        document.add_paragraph("截至本报告版本发布时，未发现未解决的数据质量问题或核查发现。")


def _evidence_section(document: DocumentObject, report: dict[str, Any]) -> None:
    _heading(document, "附表：证据文件索引", 1)
    _data_table(
        document,
        ("证据编号", "活动记录", "文件名称", "文件类型", "复核状态", "SHA-256"),
        [
            (
                row.get("evidence_code"),
                row.get("record_code"),
                row.get("file_name"),
                row.get("attachment_type"),
                _material_status(row.get("material_status")),
                str(row.get("sha256") or "—")[:12],
            )
            for row in _rows(report, "verification_attachments")
        ],
        widths=(2.7, 2.7, 4.4, 2.2, 2.1, 3.0),
        font_size=7.5,
    )


def _approval_section(document: DocumentObject, report: dict[str, Any]) -> None:
    _heading(document, "九、编制、复核与批准", 1)
    project = _mapping(report.get("project"))
    _key_value_table(
        document,
        (
            ("盘查报告编号", _display(project.get("report_code"))),
            ("盘查报告版本", _display(project.get("report_version"))),
            ("核算运行编号", _display(project.get("run_code"))),
            ("核查依据", _display(project.get("verification_basis"))),
        ),
    )
    _signature_grid(document, ("编制人/日期", "复核人/日期", "批准人/日期"))


def _summary_table(document: DocumentObject, rows: list[dict[str, Any]], key: str, labeler: Any) -> None:
    _data_table(
        document,
        ("分类", "排放量（kgCO₂e）", "排放量（tCO₂e）"),
        [
            (labeler(row.get(key) or row.get("label")), _number(row.get("kg_co2e")), _number(row.get("t_co2e")))
            for row in rows
        ],
        widths=(7.8, 4.0, 4.0),
    )


def _bar_chart_table(
    document: DocumentObject,
    rows: list[tuple[str, Decimal]],
    *,
    total: Decimal,
    widths: tuple[float, float, float, float],
    font_size: float = 8,
) -> None:
    bar_segments = 20
    table = _table(document, max(1, len(rows)) + 1, 4, widths=widths)
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    _set_cell(table.cell(0, 0), "分类", header=True, font_size=font_size)
    _set_cell(table.cell(0, 1), "构成比例", header=True, font_size=font_size, align=WD_ALIGN_PARAGRAPH.CENTER)
    _set_cell(table.cell(0, 2), "排放量（tCO₂e）", header=True, font_size=font_size)
    _set_cell(table.cell(0, 3), "占比", header=True, font_size=font_size)
    if not rows:
        merged = table.cell(1, 0).merge(table.cell(1, 3))
        _set_cell(merged, "无相关记录", font_size=font_size, align=WD_ALIGN_PARAGRAPH.CENTER)
        return
    denominator = total if total > 0 else sum((value for _, value in rows), Decimal(0))
    max_value = max((value for _, value in rows), default=Decimal(0))
    for row_index, (label, value) in enumerate(rows, start=1):
        share = (value / denominator) if denominator > 0 else Decimal(0)
        relative = (value / max_value) if max_value > 0 else Decimal(0)
        filled = max(1 if value > 0 else 0, min(bar_segments, int((relative * bar_segments).to_integral_value())))
        _set_cell(table.cell(row_index, 0), label, font_size=font_size)
        bar = f"{'■' * filled}{'□' * (bar_segments - filled)}"
        _set_cell(table.cell(row_index, 1), bar, font_size=font_size, align=WD_ALIGN_PARAGRAPH.LEFT)
        _set_cell(table.cell(row_index, 2), _number(value), font_size=font_size, align=WD_ALIGN_PARAGRAPH.RIGHT)
        _set_cell(table.cell(row_index, 3), _percent(share), font_size=font_size, align=WD_ALIGN_PARAGRAPH.RIGHT)


def _key_value_table(document: DocumentObject, rows: tuple[tuple[str, Any], ...]) -> None:
    table = _table(document, len(rows), 2, widths=(4.2, 11.4))
    for index, (label, value) in enumerate(rows):
        _set_cell(table.cell(index, 0), label, header=True)
        _set_cell(table.cell(index, 1), value)


def _data_table(
    document: DocumentObject,
    headers: tuple[str, ...],
    rows: list[tuple[Any, ...]],
    *,
    widths: tuple[float, ...],
    font_size: float = 8.5,
) -> None:
    table = _table(document, max(1, len(rows)) + 1, len(headers), widths=widths)
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for index, header in enumerate(headers):
        _set_cell(table.cell(0, index), header, header=True, font_size=font_size)
    if not rows:
        merged = table.cell(1, 0).merge(table.cell(1, len(headers) - 1))
        _set_cell(merged, "无相关记录", font_size=font_size, align=WD_ALIGN_PARAGRAPH.CENTER)
        return
    for row_index, values in enumerate(rows, start=1):
        for column_index, value in enumerate(values):
            _set_cell(table.cell(row_index, column_index), value, font_size=font_size)


def _table(document: DocumentObject, rows: int, columns: int, *, widths: tuple[float, ...]) -> Any:
    table = document.add_table(rows=rows, cols=columns)
    table.alignment, table.autofit, table.style = WD_TABLE_ALIGNMENT.CENTER, False, "Table Grid"
    for row in table.rows:
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for index, width in enumerate(widths):
            row.cells[index].width = Cm(width)
            row.cells[index].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            _set_cell_margins(row.cells[index])
    document.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def _set_cell(
    cell: Any, value: Any, *, header: bool = False, font_size: float = 9, align: Any = WD_ALIGN_PARAGRAPH.LEFT
) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.alignment, paragraph.paragraph_format.space_after = align, Pt(0)
    run = paragraph.add_run(_display(value))
    _set_run_font(run, "黑体" if header else "宋体", font_size, bold=header, color="000000")


def _heading(document: DocumentObject, text: str, level: int) -> None:
    paragraph = document.add_heading(text, level=level)
    paragraph.keep_with_next = True


def _signature_grid(document: DocumentObject, labels: tuple[str, ...]) -> None:
    table = _table(document, 2, len(labels), widths=tuple(5.2 for _ in labels))
    for index, label in enumerate(labels):
        _set_cell(table.cell(0, index), label, header=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell(table.cell(1, index), "签字：                 日期：", font_size=8)
        table.rows[1].height = Cm(2.1)


def _style_font(style: Any, name: str, size: float, *, bold: bool = False, color: str | None = None) -> None:
    style.font.name, style.font.size, style.font.bold = name, Pt(size), bold
    style._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if color:
        style.font.color.rgb = RGBColor.from_string(color)


def _clear_style_paragraph_borders(style: Any) -> None:
    p_pr = style._element.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is not None:
        p_pr.remove(p_bdr)


def _set_run_font(run: Any, name: str, size: float, *, bold: bool = False, color: str | None = None) -> None:
    run.font.name, run.font.size, run.font.bold = name, Pt(size), bold
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def _set_cell_margins(cell: Any) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar") or OxmlElement("w:tcMar")
    if margins.getparent() is None:
        tc_pr.append(margins)
    for name, value in (("top", 80), ("start", 90), ("bottom", 80), ("end", 90)):
        node = margins.find(qn(f"w:{name}")) or OxmlElement(f"w:{name}")
        if node.getparent() is None:
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _add_page_number(paragraph: Any) -> None:
    run = paragraph.add_run("第 ")
    _set_run_font(run, "宋体", 8, color="666666")
    for kind, text in (("begin", None), (None, " PAGE "), ("end", None)):
        node = OxmlElement("w:instrText" if text else "w:fldChar")
        if text:
            node.set(qn("xml:space"), "preserve")
            node.text = text
        else:
            node.set(qn("w:fldCharType"), kind)
        run._r.append(node)
    suffix = paragraph.add_run(" 页")
    _set_run_font(suffix, "宋体", 8, color="666666")


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


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _rows(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _display(value: Any) -> str:
    if value in (None, ""):
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def _number(value: Any) -> str:
    number = _decimal(value)
    if number == number.to_integral():
        return f"{number:,.0f}"
    return f"{number:,.4f}".rstrip("0").rstrip(".")


def _percent(value: Decimal) -> str:
    return f"{(value * Decimal(100)):.1f}%"


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (ArithmeticError, ValueError):
        return Decimal(0)


def _scope_label(value: Any) -> str:
    return {"scope1": "Scope 1", "scope2": "Scope 2", "scope3": "Scope 3"}.get(str(value), _display(value))


def _uppercase_label(value: Any) -> str:
    return _display(value).upper()


def _scope2_label(value: Any) -> str:
    return {
        "location": "位置法",
        "location_based": "位置法",
        "market": "市场法",
        "market_based": "市场法",
        "not_applicable": "不适用",
    }.get(str(value), _display(value))


def _material_status(value: Any) -> str:
    return {
        "ready": "已复核",
        "pending_review": "待复核",
        "missing_result": "缺少结果",
        "missing_factor": "缺少参数",
        "missing_evidence": "缺少证据",
        "approved": "已批准",
    }.get(str(value), _display(value))


def _safe_filename_part(value: Any) -> str:
    return "".join(char for char in str(value) if char.isalnum() or char in {"-", "_"}) or "all"
