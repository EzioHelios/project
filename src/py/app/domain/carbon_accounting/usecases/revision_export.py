from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.domain.carbon_accounting.queries.inventory import CarbonAccountingInventoryQueryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


EXPORT_ROOT = Path(".exports/carbon-accounting-revisions")


@dataclass(frozen=True, slots=True)
class RevisionExplanationExport:
    path: Path
    filename: str
    sha256: str
    size_bytes: int


class CarbonAccountingRevisionExportUseCase:
    """Export a revision explanation package from the revision diff read model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def export_revision_explanation(self, batch_id: int) -> RevisionExplanationExport:
        diff = await CarbonAccountingInventoryQueryService(self._session).revision_diff(batch_id)
        if diff.get("status") != "ready":
            msg = "修订差异尚未生成"
            raise ValueError(msg)

        batch = _dict(diff.get("batch"))
        export_no = _export_no(batch)
        export_dir = EXPORT_ROOT / export_no
        export_dir.mkdir(parents=True, exist_ok=True)
        archive_path = export_dir / f"{export_no}.zip"
        manifest = _manifest(diff=diff, export_no=export_no)

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("report/revision-explanation.md", _markdown(diff).encode("utf-8-sig"))
            archive.writestr("data/scope-deltas.csv", _csv_bytes(_list(diff.get("scope_deltas"))))
            archive.writestr("data/revision-changes.csv", _csv_bytes(_list(diff.get("changes"))))
            archive.writestr("report/revision-diff.json", _json_bytes(diff))
            archive.writestr("manifest.json", _json_bytes(manifest))

        return RevisionExplanationExport(
            path=archive_path,
            filename=archive_path.name,
            sha256=_sha256_file(archive_path),
            size_bytes=archive_path.stat().st_size,
        )


def _export_no(batch: dict[str, Any]) -> str:
    batch_no = _safe_part(batch.get("batch_no") or batch.get("id") or "revision")
    timestamp = datetime.datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"carbon-inventory-revision-{batch_no}-{timestamp}"


def _manifest(*, diff: dict[str, Any], export_no: str) -> dict[str, Any]:
    batch = _dict(diff.get("batch"))
    parent = _dict(diff.get("parent_batch"))
    totals = _dict(diff.get("totals"))
    return {
        "export_no": export_no,
        "generated_at": datetime.datetime.now(UTC).isoformat(),
        "template_name": "carbon_inventory_revision_explanation",
        "template_version": "v2026.06.13",
        "batch_id": batch.get("id"),
        "batch_no": batch.get("batch_no"),
        "parent_batch_id": parent.get("id"),
        "parent_batch_no": parent.get("batch_no"),
        "revision_no": batch.get("revision_no"),
        "revision_reason": batch.get("revision_reason"),
        "status": batch.get("status"),
        "diff_status": diff.get("status"),
        "delta_t_co2e": totals.get("delta_t_co2e"),
        "change_count": totals.get("change_count"),
        "files": [
            {"path": "report/revision-explanation.md", "file_type": "revision_explanation", "source_name": "carbon_accounting.revision_diff"},
            {"path": "data/scope-deltas.csv", "file_type": "scope_delta_data", "source_name": "carbon_accounting.revision_diff"},
            {"path": "data/revision-changes.csv", "file_type": "revision_change_data", "source_name": "carbon_accounting.revision_diff"},
            {"path": "report/revision-diff.json", "file_type": "revision_diff_snapshot", "source_name": "carbon_accounting.revision_diff"},
        ],
    }


def _markdown(diff: dict[str, Any]) -> str:
    batch = _dict(diff.get("batch"))
    parent = _dict(diff.get("parent_batch"))
    totals = _dict(diff.get("totals"))
    scope_rows = _list(diff.get("scope_deltas"))
    changes = _list(diff.get("changes"))
    lines = [
        "# 组织排放清单修订说明",
        "",
        "## 一、批次信息",
        "",
        f"- 修订批次: {_display(batch.get('batch_no'))}",
        f"- 来源批次: {_display(parent.get('batch_no'))}",
        f"- 修订号: R{_display(batch.get('revision_no'))}",
        f"- 修订原因: {_display(batch.get('revision_reason'))}",
        f"- 当前状态: {_display(batch.get('status'))}",
        "",
        "## 二、总量差异",
        "",
        f"- 来源清单: {_display(totals.get('parent_t_co2e'))} tCO2e",
        f"- 修订清单: {_display(totals.get('current_t_co2e'))} tCO2e",
        f"- 差异: {_signed(totals.get('delta_t_co2e'))} tCO2e",
        f"- 变更记录数: {_display(totals.get('change_count'))}",
        "",
        "## 三、Scope 差异",
        "",
        "| Scope | 来源清单(tCO2e) | 修订清单(tCO2e) | 差异(tCO2e) |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines.extend(
        f"| {_display(row.get('scope'))} | {_display(row.get('before_t_co2e'))} | {_display(row.get('after_t_co2e'))} | {_signed(row.get('delta_t_co2e'))} |"
        for row in scope_rows
    )
    lines.extend(
        [
            "",
            "## 四、记录级差异",
            "",
            "| 类型 | Scope | 对象 | 差异(tCO2e) | 质量变化 |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    lines.extend(
        (
            f"| {_change_type(row.get('change_type'))} | {_display(row.get('scope'))} | "
            f"{_display(row.get('display_name') or row.get('record_label'))} | {_signed((float(row.get('delta_kg_co2e') or 0)) / 1000)} | "
            f"{_display(row.get('before_quality_status'))} -> {_display(row.get('after_quality_status'))} |"
        )
        for row in changes[:200]
    )
    lines.extend(
        [
            "",
            "## 五、使用边界",
            "",
            "本说明由系统基于修订批次与来源批次的清单快照生成, 用于内部复核、核查支撑和材料包归档。正式报告仍应以已锁定的组织排放清单和核查项目导出包为准。",
            "",
        ]
    )
    return "\n".join(lines)


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    output = io.StringIO()
    if not rows:
        output.write("empty\n")
        return output.getvalue().encode("utf-8-sig")
    fieldnames = sorted({key for row in rows for key in row})
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _display(row.get(key)) for key in fieldnames})
    return output.getvalue().encode("utf-8-sig")


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, default=str, indent=2).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _display(value: Any) -> str:
    if value in (None, ""):
        return "-"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _signed(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return _display(value)
    if number > 0:
        return f"+{number:.6g}"
    if number < 0:
        return f"{number:.6g}"
    return "0"


def _change_type(value: Any) -> str:
    return {"added": "新增", "removed": "移除", "changed": "变更"}.get(str(value), _display(value))


def _safe_part(value: Any) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value))[:80].strip("-") or "revision"
