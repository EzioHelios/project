from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_verification.domain.policies import attachment_material_status

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class AttachmentQuery:
    project_id: int | None = None
    source_object_type: str | None = None
    source_object_id: int | None = None
    status: str | None = None
    material_group: str | None = None
    limit: int = 100
    offset: int = 0


class CarbonVerificationAttachmentQueryService:
    """Read model service for verification attachments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_attachment(self, attachment_id: int) -> dict[str, Any]:
        row = await self._session.get(m.CarbonVerificationAttachment, attachment_id)
        if row is None:
            msg = "核查附件不存在"
            raise ValueError(msg)
        return attachment_payload(row)

    async def list_attachments(self, query: AttachmentQuery) -> dict[str, Any]:
        stmt = select(m.CarbonVerificationAttachment).order_by(m.CarbonVerificationAttachment.id.desc())
        count_stmt = select(func.count(m.CarbonVerificationAttachment.id))
        for condition in _conditions(query):
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        rows = (await self._session.execute(stmt.limit(_limit(query.limit)).offset(max(0, query.offset)))).scalars().all()
        total = int(await self._session.scalar(count_stmt) or 0)
        summary = await self.summary()
        return {
            "items": [attachment_payload(row) for row in rows],
            "total": total,
            "limit": _limit(query.limit),
            "offset": max(0, query.offset),
            "summary": summary,
            "filters": _filters(query),
        }

    async def summary(self) -> dict[str, Any]:
        rows = (await self._session.execute(select(m.CarbonVerificationAttachment))).scalars().all()
        return {
            "total": len(rows),
            "by_status": _count_by(rows, "status"),
            "by_group": _count_by(rows, "material_group"),
            "ready_count": sum(1 for row in rows if attachment_material_status(row.status, row.file_path) == "ready"),
            "pending_count": sum(1 for row in rows if attachment_material_status(row.status, row.file_path) != "ready"),
        }


def attachment_payload(row: m.CarbonVerificationAttachment) -> dict[str, Any]:
    return {
        "id": row.id,
        "attachment_no": row.attachment_no,
        "project_id": row.project_id,
        "material_group": row.material_group,
        "attachment_type": row.attachment_type,
        "title": row.title,
        "source_object_type": row.source_object_type,
        "source_object_id": row.source_object_id,
        "source_object_label": row.source_object_label,
        "source_scope": row.source_scope,
        "source_period": row.source_period,
        "file_name": row.file_name,
        "file_path": row.file_path,
        "content_type": row.content_type,
        "file_size_bytes": row.file_size_bytes,
        "sha256": row.sha256,
        "version_no": row.version_no,
        "status": row.status,
        "material_status": attachment_material_status(row.status, row.file_path),
        "uploaded_by": row.uploaded_by,
        "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "source_name": row.source_name,
        "standard_code": row.standard_code,
        "confidence_level": row.confidence_level,
        "ocr_payload": row.ocr_payload,
        "remark": row.remark,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _conditions(query: AttachmentQuery) -> list[Any]:
    conditions = []
    if query.project_id is not None:
        conditions.append(m.CarbonVerificationAttachment.project_id == query.project_id)
    if query.source_object_type and query.source_object_type != "all":
        conditions.append(m.CarbonVerificationAttachment.source_object_type == query.source_object_type)
    if query.source_object_id is not None:
        conditions.append(m.CarbonVerificationAttachment.source_object_id == query.source_object_id)
    if query.status and query.status != "all":
        conditions.append(m.CarbonVerificationAttachment.status == query.status)
    if query.material_group and query.material_group != "all":
        conditions.append(m.CarbonVerificationAttachment.material_group == query.material_group)
    return conditions


def _count_by(rows: list[m.CarbonVerificationAttachment], attr: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        value = str(getattr(row, attr, None) or "unknown")
        result[value] = result.get(value, 0) + 1
    return result


def _filters(query: AttachmentQuery) -> dict[str, Any]:
    return {
        "source_object_type": query.source_object_type,
        "project_id": query.project_id,
        "source_object_id": query.source_object_id,
        "status": query.status,
        "material_group": query.material_group,
        "limit": query.limit,
        "offset": query.offset,
    }


def _limit(value: int) -> int:
    return max(1, min(int(value or 100), 500))
