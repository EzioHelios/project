from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape

from app.domain.product_footprint.queries.footprint import ProductFootprintQueryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


EXPORT_ROOT = Path(".exports/product-footprint")


@dataclass(frozen=True, slots=True)
class ProductFootprintReportExport:
    path: Path
    filename: str
    sha256: str
    size_bytes: int


class ProductFootprintReportExportUseCase:
    """Application workflow for product footprint report package export."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def export_report(self, study_id: int) -> ProductFootprintReportExport:
        report = await ProductFootprintQueryService(self._session).report(study_id)
        if not report:
            msg = "产品碳足迹研究不存在"
            raise ValueError(msg)

        export_no = _export_no(report)
        export_dir = EXPORT_ROOT / export_no
        export_dir.mkdir(parents=True, exist_ok=True)
        docx_path = export_dir / "product-footprint-report.docx"
        pdf_path = export_dir / "product-footprint-report.pdf"
        archive_path = export_dir / f"{export_no}.zip"

        _write_report_docx(docx_path, report)
        pdf_created = _convert_docx_to_pdf(docx_path, pdf_path)
        manifest = _manifest(report=report, export_no=export_no, docx_path=docx_path, pdf_path=pdf_path if pdf_created else None)

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(docx_path, "report/product-footprint-report.docx")
            if pdf_created:
                archive.write(pdf_path, "report/product-footprint-report.pdf")
            archive.writestr("report/report-context.json", _json_bytes(report))
            archive.writestr("data/inventory-items.csv", _csv_bytes(report.get("inventory_items", [])))
            archive.writestr("data/stage-summary.csv", _csv_bytes(report.get("stage_summary", [])))
            archive.writestr("data/allocation-rules.csv", _csv_bytes(report.get("allocation_rules", [])))
            archive.writestr("quality/quality-summary.json", _json_bytes(report.get("quality_summary", {})))
            archive.writestr("manifest.json", _json_bytes(manifest))

        return ProductFootprintReportExport(
            path=archive_path,
            filename=archive_path.name,
            sha256=_sha256_file(archive_path),
            size_bytes=archive_path.stat().st_size,
        )


def _export_no(report: dict[str, Any]) -> str:
    study = report.get("study") if isinstance(report.get("study"), dict) else {}
    code = _safe_part(study.get("study_code") or study.get("id") or "study")
    timestamp = datetime.datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"pcf-report-{code}-{timestamp}"


def _manifest(*, report: dict[str, Any], export_no: str, docx_path: Path, pdf_path: Path | None) -> dict[str, Any]:
    study = report.get("study") if isinstance(report.get("study"), dict) else {}
    files = [
        _file_item("report/product-footprint-report.docx", docx_path, "report_docx"),
        {
            "path": "report/report-context.json",
            "file_type": "report_context",
            "source_name": "product_footprint.report",
        },
        {"path": "data/inventory-items.csv", "file_type": "inventory_data", "source_name": "product_footprint.inventory"},
        {"path": "data/stage-summary.csv", "file_type": "stage_summary", "source_name": "product_footprint.result"},
        {"path": "data/allocation-rules.csv", "file_type": "allocation_rules", "source_name": "product_footprint.allocation"},
        {"path": "quality/quality-summary.json", "file_type": "quality_summary", "source_name": "product_footprint.quality"},
    ]
    if pdf_path is not None:
        files.insert(1, _file_item("report/product-footprint-report.pdf", pdf_path, "report_pdf"))
    return {
        "export_no": export_no,
        "generated_at": datetime.datetime.now(UTC).isoformat(),
        "template_name": "product_footprint_internal_report",
        "template_version": "v2026.06.13",
        "study_id": study.get("id"),
        "study_code": study.get("study_code"),
        "product_code": study.get("product_code"),
        "standard_code": study.get("standard_code"),
        "pcr_code": study.get("pcr_code"),
        "report_status": (report.get("latest_result") or {}).get("result_status") if isinstance(report.get("latest_result"), dict) else None,
        "files": files,
    }


def _file_item(path: str, file_path: Path, file_type: str) -> dict[str, Any]:
    return {
        "path": path,
        "file_type": file_type,
        "source_name": "product_footprint.report_export",
        "size_bytes": file_path.stat().st_size,
        "sha256": _sha256_file(file_path),
    }


def _write_report_docx(path: Path, report: dict[str, Any]) -> None:
    document_xml = _document_xml(report)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", _content_types_xml())
        docx.writestr("_rels/.rels", _rels_xml())
        docx.writestr("docProps/core.xml", _core_xml())
        docx.writestr("docProps/app.xml", _app_xml())
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", _styles_xml())


def _document_xml(report: dict[str, Any]) -> str:
    study = _dict(report.get("study"))
    boundary = _dict(report.get("boundary"))
    latest_result = _dict(report.get("latest_result"))
    blocks = [
        _p("产品碳足迹核算报告", style="Title"),
        _p("企业内部 PCF 盘查报告。EPD、碳标签和第三方认证应由独立认证/声明流程承接。", style="Subtitle"),
        _heading("一、研究与产品信息", level=1),
        _table(
            ["项目", "内容"],
            [
                ["研究编号", study.get("study_code")],
                ["研究名称", study.get("study_name")],
                ["产品", study.get("product_name") or study.get("product_code")],
                ["产品规格", study.get("product_spec")],
                ["采用标准", study.get("standard_code")],
                ["PCR/CFP-PCR", study.get("pcr_code")],
                ["功能单位", study.get("functional_unit")],
                ["声明单位", study.get("declared_unit")],
                ["报告期", _date_range(study.get("period_start"), study.get("period_end"))],
                ["边界类型", study.get("boundary_type")],
            ],
        ),
        _heading("二、目标、范围和系统边界", level=1),
        _table(
            ["项目", "内容"],
            [
                ["纳入阶段", _join(boundary.get("included_stages"))],
                ["排除阶段", _join(boundary.get("excluded_stages"))],
                ["地理范围", boundary.get("geography")],
                ["技术范围", boundary.get("technology_scope")],
                ["时间范围", boundary.get("temporal_scope")],
                ["截断规则", boundary.get("cutoff_rule")],
                ["主要假设", boundary.get("assumption")],
            ],
        ),
        _heading("三、核算结果", level=1),
        _table(
            ["指标", "结果"],
            [
                ["结果版本", latest_result.get("result_version")],
                ["总量", f"{_num(latest_result.get('total_co2e'))} kgCO2e"],
                ["单位足迹", f"{_num(latest_result.get('footprint_per_declared_unit'))} {latest_result.get('unit') or ''}".strip()],
                ["纳入清单项", latest_result.get("inventory_count")],
                ["缺失因子项", latest_result.get("missing_factor_count")],
                ["结果状态", latest_result.get("result_status") or study.get("result_status")],
                ["核算时间", latest_result.get("calculated_at")],
            ],
        ),
        _heading("四、生命周期阶段贡献", level=1),
        _table(
            ["阶段编码", "阶段名称", "活动数", "排放量(kgCO2e)"],
            [
                [row.get("stage_code"), row.get("stage_name"), row.get("item_count"), _num(row.get("kg_co2e"))]
                for row in _list(report.get("stage_summary"))
            ],
        ),
        _heading("五、活动数据清单", level=1),
        _table(
            ["编号", "阶段", "活动", "活动量", "因子/供应商 PCF", "结果(kgCO2e)", "状态"],
            [
                [
                    row.get("item_no"),
                    row.get("stage_name") or row.get("stage_code"),
                    row.get("item_name"),
                    _amount(row.get("activity_amount"), row.get("activity_unit")),
                    _factor_text(row),
                    _num(row.get("computed_co2e")),
                    row.get("calc_status"),
                ]
                for row in _list(report.get("inventory_items"))[:80]
            ],
        ),
        _heading("六、分配规则", level=1),
        _table(
            ["过程", "方法", "依据", "比例", "来源"],
            [
                [
                    row.get("process_name") or row.get("process_code"),
                    row.get("allocation_method"),
                    row.get("basis"),
                    _num(row.get("ratio")),
                    row.get("source_name"),
                ]
                for row in _list(report.get("allocation_rules"))
            ],
        ),
        _heading("七、数据质量摘要", level=1),
        _table(
            ["质量状态", "数量"],
            [[key, value] for key, value in sorted(_dict(report.get("quality_summary")).items())],
        ),
    ]
    body = "".join(blocks) + _sect_pr()
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W_NS}><w:body>{body}</w:body></w:document>'


def _p(text: Any, *, style: str | None = None) -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{style_xml}<w:r><w:t>{_xml_text(_display(text))}</w:t></w:r></w:p>"


def _heading(text: str, *, level: int) -> str:
    return _p(text, style=f"Heading{level}")


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    safe_rows = rows or [["-" for _ in headers]]
    col_width = max(1000, 9000 // max(len(headers), 1))
    grid = "".join(f'<w:gridCol w:w="{col_width}"/>' for _ in headers)
    body = _tr(headers, header=True, col_width=col_width) + "".join(_tr(row, col_width=col_width) for row in safe_rows)
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/><w:tblLook w:firstRow="1" w:noVBand="1" w:val="04A0"/>'
        '<w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:start w:w="100" w:type="dxa"/>'
        '<w:bottom w:w="80" w:type="dxa"/><w:end w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>{body}</w:tbl>"
    )


def _tr(values: list[Any], *, col_width: int, header: bool = False) -> str:
    shade = '<w:shd w:fill="E9EEF5"/>' if header else ""
    cells = "".join(
        f'<w:tc><w:tcPr><w:tcW w:w="{col_width}" w:type="dxa"/>{shade}</w:tcPr><w:p><w:r><w:t>{_xml_text(_display(value))}</w:t></w:r></w:p></w:tc>'
        for value in values
    )
    return f"<w:tr>{cells}</w:tr>"


def _sect_pr() -> str:
    return (
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )


W_NS = (
    'xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:o="urn:schemas-microsoft-com:office:office" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
    'xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:w10="urn:schemas-microsoft-com:office:word" '
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
    'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
    'xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" '
    'xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'mc:Ignorable="w14 wp14"'
)


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""


def _rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def _core_xml() -> str:
    now = datetime.datetime.now(UTC).isoformat()
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>产品碳足迹核算报告</dc:title><dc:creator>product_footprint.report_export</dc:creator>
<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""


def _app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>litestar-fullstack</Application>
</Properties>"""


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Microsoft YaHei"/><w:sz w:val="21"/></w:rPr><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Microsoft YaHei"/><w:b/><w:sz w:val="40"/><w:color w:val="17365D"/></w:rPr><w:pPr><w:spacing w:before="240" w:after="180"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Microsoft YaHei"/><w:sz w:val="20"/><w:color w:val="666666"/></w:rPr><w:pPr><w:spacing w:after="240"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Microsoft YaHei"/><w:b/><w:sz w:val="28"/><w:color w:val="1F4E79"/></w:rPr><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr></w:style>
</w:styles>"""


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


def _csv_bytes(rows: Any) -> bytes:
    records = _list(rows)
    if not records:
        return b""
    output = io.StringIO()
    keys = sorted({key for row in records for key in row})
    writer = csv.DictWriter(output, fieldnames=keys)
    writer.writeheader()
    for row in records:
        writer.writerow({key: _csv_value(row.get(key)) for key in keys})
    return output.getvalue().encode("utf-8-sig")


def _json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _display(value: Any) -> str:
    if value in (None, ""):
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _xml_text(value: str) -> str:
    return escape(value).replace("\n", "</w:t><w:br/><w:t>")


def _csv_value(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _join(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value) if value else "-"
    return _display(value)


def _date_range(start: Any, end: Any) -> str:
    if not start and not end:
        return "-"
    return f"{_display(start)} 至 {_display(end)}"


def _amount(amount: Any, unit: Any) -> str:
    return f"{_num(amount)} {_display(unit)}".strip()


def _factor_text(row: dict[str, Any]) -> str:
    if row.get("supplier_pcf_value") not in (None, ""):
        return f"{_num(row.get('supplier_pcf_value'))} {_display(row.get('supplier_pcf_unit'))} / {_display(row.get('supplier_name'))}"
    return f"{_num(row.get('factor_value'))} {_display(row.get('factor_unit'))} / {_display(row.get('factor_source'))}"


def _num(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _safe_part(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-") or "study"
