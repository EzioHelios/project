from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import zipfile
from datetime import UTC
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import unquote, urlparse

from sqlalchemy import select

from app.db import models as m
from app.domain.carbon_verification.infrastructure.report_renderer import RenderedReportFile, ReportDocumentRenderer
from app.domain.carbon_verification.queries.canonical import (
    CanonicalVerificationQueryService as CarbonVerificationQueryService,
)
from app.domain.carbon_verification.queries.canonical import (
    VerificationQuery,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


EXPORT_ROOT = Path(".exports/carbon-verification")
CONTROL_CHARACTER_LIMIT = 32


class CarbonVerificationExportUseCase:
    """Application workflow for carbon verification export jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_export_job(self, data: dict[str, Any]) -> m.CarbonVerificationExportJob:
        """Validate and persist a queued export without performing file I/O."""
        export_type = str(data.get("export_type") or "material_package")
        if export_type not in {"organization_report", "material_package"}:
            msg = "不支持的导出类型"
            raise ValueError(msg)
        requested_by = _str_or_none(data.get("requested_by"))
        project_id = _int_or_none(data.get("project_id"))
        project = None
        if project_id is not None:
            project = await self._get_project_or_raise(project_id)
            if project.inventory_report_id is None or project.calculation_run_id is None:
                msg = "核查项目未绑定已发布盘查报告"
                raise ValueError(msg)
            report = await self._session.get(m.GhgInventoryReport, project.inventory_report_id)
            if report is None:
                msg = "核查项目绑定的盘查报告不存在"
                raise ValueError(msg)
            if report.status != "published":
                msg = "核查项目绑定的盘查报告尚未发布"
                raise ValueError(msg)
        query = _query_from_data(data, project=project)
        job_no = _job_no(query, export_type)
        request_snapshot = {
            "year": query.year,
            "status": query.status,
            "scope": query.scope,
            "project_id": project_id,
            "limit": query.limit,
            "offset": query.offset,
        }
        job = m.CarbonVerificationExportJob(
            job_no=job_no,
            project_id=project_id,
            export_type=export_type,
            report_year=query.year,
            scope_filter=query.scope,
            status_filter=query.status,
            status="queued",
            manifest_payload={"request": request_snapshot},
            requested_by=requested_by,
        )
        self._session.add(job)
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def render_export_job(self, job_id: int) -> m.CarbonVerificationExportJob:  # noqa: PLR0915
        """Render one queued export from its frozen request snapshot."""
        job = await self._session.get(m.CarbonVerificationExportJob, job_id)
        if job is None:
            msg = "导出任务不存在"
            raise ValueError(msg)
        if job.status == "completed":
            return job
        manifest_payload = cast("object", job.manifest_payload)
        request_snapshot = _mapping(_mapping(manifest_payload).get("request"))
        project = await self._get_project_or_raise(job.project_id) if job.project_id is not None else None
        query = _query_from_data(request_snapshot, project=project)
        export_type = job.export_type
        job.status = "running"
        job.error_message = None
        await self._session.commit()

        query_service = CarbonVerificationQueryService(self._session)
        report = await query_service.report_context(query)
        package = await query_service.material_package(query)
        evidence = await query_service.evidence_manifest(query)
        issues = await query_service.issues(query)
        audit_trail = await query_service.audit_trail(query)
        formal_readiness = _mapping(report.get("formal_readiness"))
        if export_type == "organization_report" and formal_readiness.get("status") != "ready":
            checks_value = formal_readiness.get("checks")
            checks = cast("list[dict[str, Any]]", checks_value) if isinstance(checks_value, list) else []
            blocked = [str(item.get("label")) for item in checks if item.get("status") == "blocked"]
            msg = f"正式盘查报告尚未就绪: {'、'.join(blocked) or '存在未满足的导出条件'}"
            raise ValueError(msg)
        job.template_name = report["template"].get("name")
        job.template_path = report["template"].get("path")
        job.standard_name = report["standard"].get("name")
        job.standard_code = report["standard"].get("code")

        try:
            export_dir = EXPORT_ROOT / job.job_no
            rendered_files = (
                ReportDocumentRenderer(
                    template_path=Path(str(report["template"].get("path") or "")),
                    output_dir=export_dir / "rendered",
                ).render(report)
                if formal_readiness.get("status") == "ready"
                else []
            )
            archive_path, archive_files, manifest_payload = _write_export_archive(
                job_no=job.job_no,
                export_type=export_type,
                report=report,
                package=package,
                evidence=evidence,
                issues=issues,
                audit_trail=audit_trail,
                rendered_files=rendered_files,
            )
            archive_sha256 = _sha256_file(archive_path)
            job.file_path = str(archive_path)
            job.file_sha256 = archive_sha256
            job.file_size_bytes = archive_path.stat().st_size
            job.manifest_payload = {"request": request_snapshot, "result": manifest_payload}
            job.status = "completed"
            job.completed_at = _utc_now_naive()
            for item in archive_files:
                self._session.add(
                    m.CarbonVerificationExportFile(
                        job_id=job.id,
                        file_type=item["file_type"],
                        path=item["path"],
                        source_name=item.get("source_name"),
                        content_type=item.get("content_type"),
                        size_bytes=item.get("size_bytes"),
                        sha256=item.get("sha256"),
                    )
                )
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = _utc_now_naive()
            await self._session.commit()
            msg = "盘查报告导出失败" if export_type == "organization_report" else "核查材料包导出失败"
            raise ValueError(msg) from exc

        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def list_export_jobs(
        self, *, project_id: int | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        stmt = select(m.CarbonVerificationExportJob).order_by(m.CarbonVerificationExportJob.id.desc())
        count_stmt = select(m.CarbonVerificationExportJob.id)
        if project_id is not None:
            stmt = stmt.where(m.CarbonVerificationExportJob.project_id == project_id)
            count_stmt = count_stmt.where(m.CarbonVerificationExportJob.project_id == project_id)
        rows = (await self._session.execute(stmt.limit(_limit(limit)).offset(max(0, offset)))).scalars().all()
        total = len((await self._session.execute(count_stmt)).scalars().all())
        return {
            "items": [_job_payload(row) for row in rows],
            "total": total,
            "limit": _limit(limit),
            "offset": max(0, offset),
        }

    async def get_export_job(self, job_id: int) -> dict[str, Any]:
        job = await self._session.get(m.CarbonVerificationExportJob, job_id)
        if job is None:
            msg = "导出任务不存在"
            raise ValueError(msg)
        return _job_payload(job, include_files=True)

    async def export_file_path(self, job_id: int) -> Path:
        job = await self._session.get(m.CarbonVerificationExportJob, job_id)
        if job is None or not job.file_path:
            msg = "导出文件不存在"
            raise ValueError(msg)
        path = Path(job.file_path)
        if not path.exists():
            msg = "导出文件已丢失"
            raise ValueError(msg)
        return path

    async def _get_project_or_raise(self, project_id: int) -> m.CarbonVerificationProject:
        project = await self._session.get(m.CarbonVerificationProject, project_id)
        if project is None:
            msg = "核查项目不存在"
            raise ValueError(msg)
        return project


def _query_from_data(data: dict[str, Any], *, project: m.CarbonVerificationProject | None = None) -> VerificationQuery:
    return VerificationQuery(
        year=_int_or_none(data.get("year")) or (project.verification_year if project else None),
        status=_str_or_none(data.get("status")),
        scope=_str_or_none(data.get("scope")),
        project_id=project.id if project else _int_or_none(data.get("project_id")),
        limit=max(1, min(_int_or_none(data.get("limit")) or 500, 500)),
        offset=max(0, _int_or_none(data.get("offset")) or 0),
    )


def _write_export_archive(
    *,
    job_no: str,
    export_type: str,
    report: dict[str, Any],
    package: dict[str, Any],
    evidence: dict[str, Any],
    issues: dict[str, Any],
    audit_trail: dict[str, Any],
    rendered_files: list[RenderedReportFile],
) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    export_dir = EXPORT_ROOT / job_no
    export_dir.mkdir(parents=True, exist_ok=True)
    archive_path = export_dir / f"{job_no}.zip"
    files: dict[str, Any] = {"report/report-context.json": report}
    if export_type == "material_package":
        files.update(
            {
                "data/activity-data.csv": _csv_bytes(report.get("activity_data", [])),
                "data/factor-parameters.csv": _csv_bytes(report.get("factor_parameters", [])),
                "evidence/evidence-manifest.csv": _csv_bytes(evidence.get("items", [])),
                "quality/issues.csv": _csv_bytes(issues.get("items", [])),
                "audit/audit-trail.csv": _csv_bytes(audit_trail.get("items", [])),
            }
        )
    archive_files: list[dict[str, Any]] = []
    evidence_files: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rendered in rendered_files:
            archive.writestr(rendered.path, rendered.content)
            archive_files.append(
                {
                    "file_type": _file_type(rendered.path),
                    "path": rendered.path,
                    "source_name": rendered.source_name,
                    "content_type": rendered.content_type,
                    "size_bytes": len(rendered.content),
                    "sha256": hashlib.sha256(rendered.content).hexdigest(),
                }
            )
        for path, content in files.items():
            payload = content if isinstance(content, bytes) else _json_bytes(content)
            archive.writestr(path, payload)
            archive_files.append(
                {
                    "file_type": _file_type(path),
                    "path": path,
                    "source_name": _source_name(path),
                    "content_type": "application/json" if path.endswith(".json") else "text/csv",
                    "size_bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        if export_type == "material_package":
            evidence_files = _write_evidence_originals(
                archive=archive,
                evidence_items=evidence.get("items", []),
                archive_files=archive_files,
                year=str(
                    report.get("reporting_period", {}).get("year") or package.get("filters", {}).get("year") or "all"
                ),
            )
        manifest_payload = {
            **package,
            "export_type": export_type,
            "generated_at": _utc_now_naive().isoformat(),
            "exported_files": list(archive_files),
            "evidence_files": evidence_files,
            "evidence_file_summary": _evidence_file_summary(evidence_files),
        }
        manifest_content = _json_bytes(manifest_payload)
        archive.writestr("manifest.json", manifest_content)
        archive_files.append(
            {
                "file_type": "manifest",
                "path": "manifest.json",
                "source_name": "carbon_verification.material_package",
                "content_type": "application/json",
                "size_bytes": len(manifest_content),
                "sha256": hashlib.sha256(manifest_content).hexdigest(),
            }
        )
    return archive_path, archive_files, manifest_payload


def _write_evidence_originals(
    *,
    archive: zipfile.ZipFile,
    evidence_items: list[dict[str, Any]],
    archive_files: list[dict[str, Any]],
    year: str,
) -> list[dict[str, Any]]:
    evidence_files: list[dict[str, Any]] = []
    used_archive_paths = {item["path"] for item in archive_files}
    for item in evidence_items:
        source_path = _str_or_none(item.get("path"))
        manifest_item = _evidence_file_manifest_item(item, source_path=source_path)
        if not source_path:
            manifest_item["package_status"] = "missing_path"
            evidence_files.append(manifest_item)
            continue
        file_path, unavailable_reason = _local_evidence_path(source_path)
        if file_path is None:
            manifest_item["package_status"] = unavailable_reason
            evidence_files.append(manifest_item)
            continue
        archive_path = _deduplicate_archive_path(
            _evidence_archive_path(
                year=year, evidence_code=str(item.get("evidence_code") or "evidence"), file_path=file_path, item=item
            ),
            used_archive_paths,
        )
        used_archive_paths.add(archive_path)
        sha256 = _sha256_file(file_path)
        size_bytes = file_path.stat().st_size
        archive.write(file_path, arcname=archive_path)
        exported_file = {
            "file_type": "evidence_original",
            "path": archive_path,
            "source_name": str(item.get("source") or "ghg_evidence"),
            "content_type": item.get("content_type") or _content_type_from_suffix(file_path),
            "size_bytes": size_bytes,
            "sha256": sha256,
        }
        archive_files.append(exported_file)
        manifest_item.update(
            {
                "package_status": "included",
                "package_path": archive_path,
                "size_bytes": size_bytes,
                "sha256": sha256,
            }
        )
        evidence_files.append(manifest_item)
    return evidence_files


def _evidence_file_manifest_item(item: dict[str, Any], *, source_path: str | None) -> dict[str, Any]:
    return {
        "evidence_code": item.get("evidence_code"),
        "record_type": item.get("record_type"),
        "record_id": item.get("record_id"),
        "scope": item.get("scope"),
        "display_name": item.get("display_name"),
        "period": item.get("period"),
        "source_path": source_path,
        "source": item.get("source") or "ghg_evidence",
        "material_status": item.get("material_status"),
        "attachment_type": item.get("attachment_type"),
    }


def _local_evidence_path(source_path: str) -> tuple[Path | None, str]:
    parsed = urlparse(source_path)
    if parsed.scheme in {"http", "https", "s3", "oss", "cos"}:
        return None, "remote_file_unavailable"
    path = Path(unquote(parsed.path)).expanduser() if parsed.scheme == "file" else Path(source_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        return None, "missing_file"
    if not path.is_file():
        return None, "not_a_file"
    return path, "included"


def _evidence_archive_path(*, year: str, evidence_code: str, file_path: Path, item: dict[str, Any]) -> str:
    filename = _safe_archive_segment(str(item.get("file_name") or file_path.name or "evidence-file"))
    code = _safe_archive_segment(evidence_code)
    return f"evidence/{_safe_archive_segment(year)}/{code}-{filename}"


def _deduplicate_archive_path(path: str, used_paths: set[str]) -> str:
    if path not in used_paths:
        return path
    base_path = Path(path)
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent.as_posix()
    counter = 2
    while True:
        candidate = f"{parent}/{stem}-{counter}{suffix}" if parent != "." else f"{stem}-{counter}{suffix}"
        if candidate not in used_paths:
            return candidate
        counter += 1


def _safe_archive_segment(value: str) -> str:
    cleaned = "".join(
        "_" if char in {"/", "\\"} or ord(char) < CONTROL_CHARACTER_LIMIT else char for char in value
    ).strip(" .")
    return cleaned or "unknown"


def _content_type_from_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix in {".xlsx", ".xls"}:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return "application/octet-stream"


def _evidence_file_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "total": len(items),
        "included": 0,
        "missing_path": 0,
        "missing_file": 0,
        "remote_file_unavailable": 0,
        "not_a_file": 0,
    }
    for item in items:
        status = str(item.get("package_status") or "unknown")
        summary[status] = summary.get(status, 0) + 1
    return summary


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO()
    fieldnames = sorted({key for row in rows for key in row})
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})
    return buffer.getvalue().encode("utf-8-sig")


def _json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, default=_json_default).encode("utf-8")


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return str(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _job_payload(job: m.CarbonVerificationExportJob, *, include_files: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": job.id,
        "job_no": job.job_no,
        "project_id": job.project_id,
        "export_type": job.export_type,
        "report_year": job.report_year,
        "scope_filter": job.scope_filter,
        "status_filter": job.status_filter,
        "status": job.status,
        "template_name": job.template_name,
        "standard_name": job.standard_name,
        "standard_code": job.standard_code,
        "file_path": job.file_path,
        "file_sha256": job.file_sha256,
        "file_size_bytes": job.file_size_bytes,
        "requested_by": job.requested_by,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "error_message": job.error_message,
        "download_url": f"/api/carbon/verification/export-jobs/{job.id}/download" if job.file_path else None,
    }
    if include_files:
        payload["files"] = [
            {
                "id": item.id,
                "file_type": item.file_type,
                "path": item.path,
                "source_name": item.source_name,
                "content_type": item.content_type,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
            }
            for item in job.files
        ]
        payload["manifest"] = cast("Any", getattr(job, "manifest_payload", None))
    return payload


def _mapping(value: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _job_no(query: VerificationQuery, export_type: str) -> str:
    timestamp = datetime.datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    year = query.year or "all"
    scope = query.scope or "all"
    return f"cv-{export_type}-{year}-{scope}-{timestamp}"


def _utc_now_naive() -> datetime.datetime:
    return datetime.datetime.now(UTC).replace(tzinfo=None)


def _file_type(path: str) -> str:
    if path == "manifest.json":
        return "manifest"
    return path.split("/", 1)[0]


def _source_name(path: str) -> str:
    if path.startswith("report/"):
        return "carbon_verification.report_context"
    if path.startswith("data/"):
        return "ghg_inventory"
    if path.startswith("evidence/"):
        return "ghg_evidence"
    if path.startswith("quality/"):
        return "carbon_verification.issues"
    if path.startswith("audit/"):
        return "ghg_inventory_audit"
    return "carbon_verification"


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _str_or_none(value: Any) -> str | None:
    if value in (None, "", "all"):
        return None
    return str(value)


def _limit(value: int) -> int:
    return max(1, min(int(value or 50), 200))
