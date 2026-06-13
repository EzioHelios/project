from __future__ import annotations

import datetime
import hashlib
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_verification.domain.policies import (
    ATTACHMENT_PENDING_UPLOAD,
    validate_attachment_status,
    validate_attachment_type,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


ATTACHMENT_FIELDS = {
    "attachment_no",
    "material_group",
    "attachment_type",
    "title",
    "source_object_type",
    "source_object_id",
    "source_object_label",
    "source_scope",
    "source_period",
    "file_name",
    "file_path",
    "content_type",
    "file_size_bytes",
    "sha256",
    "version_no",
    "status",
    "uploaded_by",
    "uploaded_at",
    "reviewed_by",
    "reviewed_at",
    "source_name",
    "standard_code",
    "confidence_level",
    "ocr_payload",
    "remark",
}
INTEGER_FIELDS = {"source_object_id", "file_size_bytes", "version_no"}
DATETIME_FIELDS = {"uploaded_at", "reviewed_at"}


class CarbonVerificationAttachmentUseCase:
    """Application workflows for verification material attachments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_attachment(self, data: dict[str, Any]) -> m.CarbonVerificationAttachment:
        payload = _payload(data, ATTACHMENT_FIELDS, required={"title", "source_object_type"})
        payload.setdefault("attachment_no", await self._next_no())
        payload.setdefault("material_group", "evidence")
        payload.setdefault("attachment_type", "supporting_document")
        payload.setdefault("status", ATTACHMENT_PENDING_UPLOAD)
        payload.setdefault("version_no", 1)
        payload.setdefault("source_name", "carbon_verification")
        _enrich_file_metadata(payload)
        validate_attachment_type(str(payload["attachment_type"]))
        validate_attachment_status(str(payload["status"]))
        existing = await self._existing_attachment(payload)
        if existing is not None:
            _assign(existing, {key: value for key, value in payload.items() if key not in {"attachment_no", "source_object_type", "source_object_id"}})
            await self._session.commit()
            await self._session.refresh(existing)
            return existing
        attachment = m.CarbonVerificationAttachment(**payload)
        self._session.add(attachment)
        await self._session.commit()
        await self._session.refresh(attachment)
        return attachment

    async def update_attachment(self, attachment_id: int, data: dict[str, Any]) -> m.CarbonVerificationAttachment:
        attachment = await self._get_or_raise(attachment_id)
        payload = _payload(data, ATTACHMENT_FIELDS - {"attachment_no", "source_object_type", "source_object_id"})
        if "attachment_type" in payload:
            validate_attachment_type(str(payload["attachment_type"]))
        if "status" in payload:
            validate_attachment_status(str(payload["status"]))
        _enrich_file_metadata(payload)
        _assign(attachment, payload)
        await self._session.commit()
        await self._session.refresh(attachment)
        return attachment

    async def _existing_attachment(self, payload: dict[str, Any]) -> m.CarbonVerificationAttachment | None:
        source_object_type = payload.get("source_object_type")
        source_object_id = payload.get("source_object_id")
        if not source_object_type or not source_object_id:
            return None
        return await self._session.scalar(
            select(m.CarbonVerificationAttachment)
            .where(
                m.CarbonVerificationAttachment.source_object_type == str(source_object_type),
                m.CarbonVerificationAttachment.source_object_id == int(source_object_id),
                m.CarbonVerificationAttachment.material_group == str(payload.get("material_group") or "evidence"),
            )
            .order_by(m.CarbonVerificationAttachment.id.desc())
            .limit(1)
        )

    async def _get_or_raise(self, attachment_id: int) -> m.CarbonVerificationAttachment:
        attachment = await self._session.get(m.CarbonVerificationAttachment, attachment_id)
        if attachment is None:
            msg = "核查附件不存在"
            raise ValueError(msg)
        return attachment

    async def _next_no(self) -> str:
        timestamp = datetime.datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        count = await self._session.scalar(select(func.count(m.CarbonVerificationAttachment.id)))
        return f"VA-{timestamp}-{int(count or 0) + 1:04d}"


def _payload(data: dict[str, Any], fields: set[str], *, required: set[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in fields:
        if key not in data or data[key] in (None, ""):
            continue
        payload[key] = _coerce_value(key, data[key])
    missing = [field for field in required or set() if field not in payload]
    if missing:
        msg = f"缺少必填字段: {', '.join(sorted(missing))}"
        raise ValueError(msg)
    return payload


def _coerce_value(key: str, value: Any) -> Any:
    if key in INTEGER_FIELDS:
        return int(value)
    if key in DATETIME_FIELDS and isinstance(value, str):
        return datetime.datetime.fromisoformat(value).replace(tzinfo=None)
    return value


def _enrich_file_metadata(payload: dict[str, Any]) -> None:
    file_path = payload.get("file_path")
    if not file_path:
        return
    path = Path(str(file_path))
    payload.setdefault("file_name", path.name)
    if path.is_file():
        payload.setdefault("file_size_bytes", path.stat().st_size)
        payload.setdefault("sha256", _sha256_file(path))
    if payload.get("status") == ATTACHMENT_PENDING_UPLOAD:
        payload["status"] = "ready"
    payload.setdefault("uploaded_at", datetime.datetime.now(UTC).replace(tzinfo=None))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assign(obj: Any, payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        setattr(obj, key, value)
