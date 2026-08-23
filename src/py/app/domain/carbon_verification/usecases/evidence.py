"""Canonical evidence upload, review and download workflows."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from app.db import models as m
from app.domain.carbon_verification.usecases.projects import CarbonVerificationProjectUseCase
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


EVIDENCE_STORAGE_ROOT = Path(".storage/ghg-evidence")
MAX_EVIDENCE_FILE_BYTES = 25 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
    "text/csv",
    "text/plain",
}
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+")


class CanonicalEvidenceUseCase:
    """Persist evidence bytes and link them to canonical records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upload(
        self,
        *,
        project_id: int,
        record_type: str,
        record_code: str,
        evidence_role: str,
        document_type: str,
        file_name: str,
        content_type: str | None,
        content: bytes,
        uploaded_by: str,
        evidence_code: str | None = None,
        link_code: str | None = None,
    ) -> m.GhgEvidenceFile:
        team_id = require_session_tenant_id(self.session)
        project = await self._project(project_id)
        await self._validate_target(project, record_type=record_type, record_code=record_code)
        if not content:
            msg = "证据文件不能为空"
            raise ValueError(msg)
        if len(content) > MAX_EVIDENCE_FILE_BYTES:
            msg = "单个证据文件不能超过25MB"
            raise ValueError(msg)
        normalized_content_type = (content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
        if normalized_content_type not in ALLOWED_CONTENT_TYPES:
            msg = "仅支持PDF、Office文档、图片、CSV和文本文件"
            raise ValueError(msg)
        safe_name = _safe_filename(file_name)
        digest = hashlib.sha256(content).hexdigest()
        resolved_evidence_code = evidence_code or f"EVD-{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid4().hex[:10]}"
        existing = await self.session.scalar(
            select(m.GhgEvidenceFile).where(m.GhgEvidenceFile.evidence_code == resolved_evidence_code)
        )
        if existing is not None:
            if existing.sha256 != digest:
                msg = "相同证据编号不能对应不同文件内容"
                raise ValueError(msg)
            storage_path = Path(existing.storage_key)
            if not storage_path.is_file():
                storage_path.parent.mkdir(parents=True, exist_ok=True)
                storage_path.write_bytes(content)
            await self._ensure_link(
                evidence=existing,
                record_type=record_type,
                record_code=record_code,
                evidence_role=evidence_role,
                uploaded_by=uploaded_by,
                link_code=link_code,
            )
            await self.session.commit()
            await CarbonVerificationProjectUseCase(self.session).refresh_project_status(project.id)
            return existing

        storage_path = EVIDENCE_STORAGE_ROOT / str(team_id) / resolved_evidence_code / safe_name
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(content)
        evidence = m.GhgEvidenceFile(
            evidence_code=resolved_evidence_code,
            file_name=safe_name,
            document_type=document_type,
            storage_key=str(storage_path),
            sha256=digest,
            confidentiality="internal",
            verification_status="pending",
        )
        self.session.add(evidence)
        await self.session.flush()
        await self._ensure_link(
            evidence=evidence,
            record_type=record_type,
            record_code=record_code,
            evidence_role=evidence_role,
            uploaded_by=uploaded_by,
            link_code=link_code,
        )
        await self.session.commit()
        await self.session.refresh(evidence)
        await CarbonVerificationProjectUseCase(self.session).refresh_project_status(project.id)
        return evidence

    async def _ensure_link(
        self,
        *,
        evidence: m.GhgEvidenceFile,
        record_type: str,
        record_code: str,
        evidence_role: str,
        uploaded_by: str,
        link_code: str | None,
    ) -> m.GhgEvidenceLink:
        existing = await self.session.scalar(
            select(m.GhgEvidenceLink).where(
                m.GhgEvidenceLink.record_type == record_type,
                m.GhgEvidenceLink.record_code == record_code,
                m.GhgEvidenceLink.evidence_id == evidence.id,
                m.GhgEvidenceLink.evidence_role == evidence_role,
            )
        )
        if existing is not None:
            return existing
        link = m.GhgEvidenceLink(
            link_code=link_code or f"EL-{uuid4().hex}",
            record_type=record_type,
            record_code=record_code,
            evidence_id=evidence.id,
            evidence_role=evidence_role,
            review_status="pending",
            reviewer=uploaded_by,
            reviewed_at=None,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def review(self, *, project_id: int, evidence_code: str, decision: str, reviewer: str) -> m.GhgEvidenceFile:
        if decision not in {"approved", "rejected"}:
            msg = "证据复核结果只能为approved或rejected"
            raise ValueError(msg)
        evidence = await self.session.scalar(
            select(m.GhgEvidenceFile).where(m.GhgEvidenceFile.evidence_code == evidence_code)
        )
        if evidence is None:
            msg = "证据文件不存在"
            raise ValueError(msg)
        project = await self._project(project_id)
        evidence.verification_status = decision
        links = list(
            (
                await self.session.scalars(
                    select(m.GhgEvidenceLink).where(m.GhgEvidenceLink.evidence_id == evidence.id)
                )
            ).all()
        )
        now = datetime.now(UTC)
        for link in links:
            await self._validate_target(project, record_type=link.record_type, record_code=link.record_code)
            link.review_status = decision
            link.reviewer = reviewer
            link.reviewed_at = now
        await self.session.commit()
        await CarbonVerificationProjectUseCase(self.session).refresh_project_status(project.id)
        return evidence

    async def file_path(self, evidence_code: str) -> Path:
        evidence = await self.session.scalar(
            select(m.GhgEvidenceFile).where(m.GhgEvidenceFile.evidence_code == evidence_code)
        )
        if evidence is None:
            msg = "证据文件不存在"
            raise ValueError(msg)
        path = Path(evidence.storage_key)
        resolved_root = EVIDENCE_STORAGE_ROOT.resolve()
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(resolved_root) or not resolved_path.is_file():
            msg = "证据文件不可读取"
            raise ValueError(msg)
        if hashlib.sha256(resolved_path.read_bytes()).hexdigest() != evidence.sha256:
            msg = "证据文件完整性校验失败"
            raise ValueError(msg)
        return resolved_path

    async def _project(self, project_id: int) -> m.CarbonVerificationProject:
        project = await self.session.get(m.CarbonVerificationProject, project_id)
        if project is None or project.inventory_report is None or project.calculation_run is None:
            msg = "核查项目不存在或未绑定盘查报告"
            raise ValueError(msg)
        return project

    async def _validate_target(
        self, project: m.CarbonVerificationProject, *, record_type: str, record_code: str
    ) -> None:
        if record_type == "verification_project":
            if record_code != project.project_no:
                msg = "证据关联的核查项目不一致"
                raise ValueError(msg)
            return
        if record_type != "activity":
            msg = "证据只能关联活动数据或核查项目"
            raise ValueError(msg)
        calculation_run = project.calculation_run
        if calculation_run is None:
            msg = "核查项目未绑定核算运行"
            raise ValueError(msg)
        activity = await self.session.scalar(
            select(m.GhgActivityRecord).where(
                m.GhgActivityRecord.inventory_code == calculation_run.inventory_code,
                m.GhgActivityRecord.record_code == record_code,
            )
        )
        if activity is None:
            msg = "证据关联的活动数据不属于当前核查项目"
            raise ValueError(msg)


def _safe_filename(value: str) -> str:
    name = SAFE_FILENAME_PATTERN.sub("-", Path(value).name).strip(".-")
    if not name:
        return "evidence-file"
    return name[:180]
