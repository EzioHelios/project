"""Methodology-specific monitoring workbook generation and deterministic validation."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportOptionalMemberAccess=false

from __future__ import annotations

# mypy: disable-error-code=import-untyped
# ruff: noqa: C901, RUF001, TRY301 - one-pass validation preserves workbook row context.
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

TEMPLATE_VERSION = "DECARB-MRV-2026.1"
MONITORING_HEADERS = ("参数代码", "参数名称", "期间开始", "期间结束", "数值", "单位", "数据来源", "监测频率", "证据编号")


@dataclass(slots=True)
class MonitoringImportIssue:
    row_number: int | None
    field_code: str | None
    issue_code: str
    message: str
    severity: str = "error"

    def payload(self) -> dict[str, Any]:
        return {
            "rowNumber": self.row_number,
            "fieldCode": self.field_code,
            "issueCode": self.issue_code,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(slots=True)
class MonitoringImportPreview:
    rows: list[dict[str, Any]] = field(default_factory=list)
    issues: list[MonitoringImportIssue] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        error_count = sum(item.severity == "error" for item in self.issues)
        return {
            "rows": self.rows,
            "issues": [item.payload() for item in self.issues],
            "metrics": {
                "rowCount": len(self.rows),
                "validCount": max(0, len(self.rows) - error_count),
                "errorCount": error_count,
                "warningCount": sum(item.severity == "warning" for item in self.issues),
            },
            "canCommit": error_count == 0 and bool(self.rows),
        }


def build_monitoring_template(methodology: dict[str, Any]) -> bytes:
    """Generate an auditable workbook whose monitoring columns come from the method version."""
    workbook = Workbook()
    metadata = workbook.active
    metadata.title = "00_模板信息"
    metadata.append(["模板版本", TEMPLATE_VERSION])
    metadata.append(["方法学编号", methodology["code"]])
    metadata.append(["方法学名称", methodology["name"]])
    metadata.append(["方法学版本", methodology["version"]])
    metadata.append(["正式来源", methodology["source_url"]])

    sheet = workbook.create_sheet("01_监测数据")
    sheet.append(list(MONITORING_HEADERS))
    for parameter in methodology.get("parameter_schema") or []:
        sheet.append(
            [
                parameter.get("code"),
                parameter.get("name"),
                None,
                None,
                None,
                parameter.get("unit"),
                None,
                None,
                None,
            ]
        )
    evidence = workbook.create_sheet("02_证据索引")
    evidence.append(["证据编号", "文件名称", "文件SHA-256", "出具机构", "覆盖期始", "覆盖期止", "备注"])
    for item in methodology.get("evidence_schema") or []:
        evidence.append([None, item, None, None, None, None, None])

    for worksheet in workbook.worksheets:
        for cell in worksheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="176B73")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        worksheet.freeze_panes = "A2"
        for index in range(1, worksheet.max_column + 1):
            worksheet.column_dimensions[get_column_letter(index)].width = 20

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def preview_monitoring_workbook(content: bytes, methodology: dict[str, Any]) -> MonitoringImportPreview:
    preview = MonitoringImportPreview()
    try:
        workbook = load_workbook(BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001 - normalize parser failures for the import workbench.
        preview.issues.append(MonitoringImportIssue(None, None, "invalid_workbook", f"无法读取工作簿：{exc}"))
        return preview
    if "00_模板信息" not in workbook.sheetnames or "01_监测数据" not in workbook.sheetnames:
        preview.issues.append(MonitoringImportIssue(None, None, "missing_sheet", "缺少模板信息或监测数据工作表。"))
        return preview
    metadata = {
        str(row[0].value or ""): str(row[1].value or "")
        for row in workbook["00_模板信息"].iter_rows(min_row=1, max_col=2)
    }
    if metadata.get("模板版本") != TEMPLATE_VERSION:
        preview.issues.append(MonitoringImportIssue(None, None, "template_version", "模板版本与当前系统不一致。"))
    if metadata.get("方法学编号") != methodology["code"]:
        preview.issues.append(MonitoringImportIssue(None, "methodology_code", "methodology_mismatch", "模板方法学与项目方法学不一致。"))
    sheet = workbook["01_监测数据"]
    headers = [str(cell.value or "") for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
    if tuple(headers[: len(MONITORING_HEADERS)]) != MONITORING_HEADERS:
        preview.issues.append(MonitoringImportIssue(1, None, "invalid_headers", "监测数据表头已被修改。"))
        return preview
    schema = {str(item["code"]): item for item in methodology.get("parameter_schema") or []}
    seen: set[str] = set()
    for row_number, cells in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        if not any(value not in {None, ""} for value in cells):
            continue
        row = dict(zip(MONITORING_HEADERS, cells, strict=False))
        code = str(row.get("参数代码") or "").strip()
        if not code:
            preview.issues.append(MonitoringImportIssue(row_number, "parameter_code", "required", "参数代码不能为空。"))
            continue
        definition = schema.get(code)
        if definition is None:
            preview.issues.append(MonitoringImportIssue(row_number, "parameter_code", "unknown_parameter", "参数不属于当前方法学版本。"))
            continue
        if row.get("数值") in {None, ""}:
            preview.issues.append(MonitoringImportIssue(row_number, "value", "required", "参数值不能为空。"))
        else:
            try:
                numeric = float(str(row["数值"]))
                if numeric < float(definition.get("minimum") or 0):
                    raise ValueError
            except (TypeError, ValueError):
                preview.issues.append(MonitoringImportIssue(row_number, "value", "invalid_number", "参数值超出物理边界。"))
        expected_unit = str(definition.get("unit") or "")
        if str(row.get("单位") or "") != expected_unit:
            preview.issues.append(MonitoringImportIssue(row_number, "unit", "unit_mismatch", f"单位必须为 {expected_unit}。"))
        if not row.get("数据来源"):
            preview.issues.append(MonitoringImportIssue(row_number, "source", "required", "数据来源不能为空。"))
        if not row.get("监测频率"):
            preview.issues.append(MonitoringImportIssue(row_number, "frequency", "required", "监测频率不能为空。"))
        seen.add(code)
        preview.rows.append(
            {
                "parameterCode": code,
                "parameterName": definition["name"],
                "periodStart": str(row.get("期间开始") or ""),
                "periodEnd": str(row.get("期间结束") or ""),
                "value": row.get("数值"),
                "unit": expected_unit,
                "source": str(row.get("数据来源") or ""),
                "frequency": str(row.get("监测频率") or ""),
                "evidenceCode": str(row.get("证据编号") or ""),
            }
        )
    for code, definition in schema.items():
        if definition.get("required") and code not in seen:
            preview.issues.append(MonitoringImportIssue(None, code, "missing_required_parameter", f"缺少必填参数：{definition['name']}。"))
    return preview
