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
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.db import models as m
from app.domain.carbon_verification.queries.verification import CarbonVerificationQueryService, VerificationQuery
from app.domain.carbon_verification.usecases.report_renderer import RenderedReportFile, ReportDocumentRenderer

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


EXPORT_ROOT = Path(".exports/carbon-verification")


class CarbonVerificationExportUseCase:
    """Application workflow for carbon verification export jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_export_job(self, data: dict[str, Any]) -> m.CarbonVerificationExportJob:
        query = _query_from_data(data)
        export_type = str(data.get("export_type") or "material_package")
        requested_by = _str_or_none(data.get("requested_by"))
        project_id = _int_or_none(data.get("project_id"))
        if project_id is not None:
            await self._get_project_or_raise(project_id)
        job_no = _job_no(query, export_type)
        query_service = CarbonVerificationQueryService(self._session)
        report = await query_service.report_context(query)
        package = await query_service.material_package(query)
        evidence = await query_service.evidence_manifest(query)
        issues = await query_service.issues(query)
        audit_trail = await query_service.audit_trail(query)

        job = m.CarbonVerificationExportJob(
            job_no=job_no,
            project_id=project_id,
            export_type=export_type,
            report_year=query.year,
            scope_filter=query.scope,
            status_filter=query.status,
            status="running",
            template_name=report["template"].get("name"),
            template_path=report["template"].get("path"),
            standard_name=report["standard"].get("name"),
            standard_code=report["standard"].get("code"),
            requested_by=requested_by,
        )
        self._session.add(job)
        await self._session.flush()

        try:
            export_dir = EXPORT_ROOT / job_no
            rendered_files = ReportDocumentRenderer(
                template_path=Path(str(report["template"].get("path") or "")),
                output_dir=export_dir / "rendered",
            ).render(report)
            archive_path, archive_files, manifest_payload = _write_export_archive(
                job_no=job_no,
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
            job.manifest_payload = manifest_payload
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
            msg = "核查材料包导出失败"
            raise ValueError(msg) from exc

        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def list_export_jobs(self, *, project_id: int | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        stmt = select(m.CarbonVerificationExportJob).order_by(m.CarbonVerificationExportJob.id.desc())
        count_stmt = select(m.CarbonVerificationExportJob.id)
        if project_id is not None:
            stmt = stmt.where(m.CarbonVerificationExportJob.project_id == project_id)
            count_stmt = count_stmt.where(m.CarbonVerificationExportJob.project_id == project_id)
        rows = (await self._session.execute(stmt.limit(_limit(limit)).offset(max(0, offset)))).scalars().all()
        total = len((await self._session.execute(count_stmt)).scalars().all())
        return {"items": [_job_payload(row) for row in rows], "total": total, "limit": _limit(limit), "offset": max(0, offset)}

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


def _query_from_data(data: dict[str, Any]) -> VerificationQuery:
    return VerificationQuery(
        year=_int_or_none(data.get("year")),
        status=_str_or_none(data.get("status")),
        scope=_str_or_none(data.get("scope")),
        limit=max(1, min(_int_or_none(data.get("limit")) or 500, 500)),
        offset=max(0, _int_or_none(data.get("offset")) or 0),
    )


def _write_export_archive(
    *,
    job_no: str,
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
    files = {
        "report/report-context.json": report,
        "data/activity-data.csv": _csv_bytes(report.get("activity_data", [])),
        "data/factor-parameters.csv": _csv_bytes(report.get("factor_parameters", [])),
        "evidence/evidence-manifest.csv": _csv_bytes(evidence.get("items", [])),
        "quality/issues.csv": _csv_bytes(issues.get("items", [])),
        "audit/audit-trail.csv": _csv_bytes(audit_trail.get("items", [])),
    }
    archive_files: list[dict[str, Any]] = []
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
        manifest_payload = {
            **package,
            "generated_at": _utc_now_naive().isoformat(),
            "exported_files": list(archive_files),
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
    payload = {
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
        payload["manifest"] = job.manifest_payload
    return payload


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
        return "carbon_accounting"
    if path.startswith("evidence/"):
        return "scope_record_attachments"
    if path.startswith("quality/"):
        return "carbon_verification.issues"
    if path.startswith("audit/"):
        return "carbon_audit_log"
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
