from __future__ import annotations

import datetime
from datetime import UTC
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.carbon_verification.domain.policies import (
    FINDING_OPEN,
    validate_finding_severity,
    validate_finding_status,
    validate_finding_transition,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


FINDING_FIELDS = {
    "finding_no",
    "project_id",
    "issue_type",
    "finding_type",
    "severity",
    "title",
    "description",
    "action_required",
    "record_type",
    "record_id",
    "scope",
    "display_name",
    "period",
    "status",
    "owner",
    "due_date",
    "correction_comment",
    "correction_evidence",
    "reviewer",
    "reviewed_at",
    "closed_at",
    "source_name",
    "standard_code",
    "source_payload",
    "remark",
}
DATE_FIELDS = {"due_date"}
DATETIME_FIELDS = {"reviewed_at", "closed_at"}
INTEGER_FIELDS = {"project_id", "record_id"}


class CarbonVerificationFindingUseCase:
    """Application workflows for verification findings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_finding(self, data: dict[str, Any]) -> m.CarbonVerificationFinding:
        payload = _payload(data, FINDING_FIELDS, required={"issue_type", "title"})
        payload.setdefault("finding_no", await self._next_no())
        payload.setdefault("finding_type", "data_quality")
        payload.setdefault("severity", "medium")
        payload.setdefault("status", FINDING_OPEN)
        payload.setdefault("source_name", "carbon_verification")
        if payload.get("project_id") is not None:
            await self._get_project_or_raise(int(payload["project_id"]))
        validate_finding_status(str(payload["status"]))
        validate_finding_severity(str(payload["severity"]))

        existing = await self._existing_open_finding(payload)
        if existing is not None:
            return existing

        payload.setdefault("source_payload", _jsonable(data))
        finding = m.CarbonVerificationFinding(**payload)
        self._session.add(finding)
        await self._session.commit()
        await self._session.refresh(finding)
        return finding

    async def update_finding(self, finding_id: int, data: dict[str, Any]) -> m.CarbonVerificationFinding:
        finding = await self._get_or_raise(finding_id)
        payload = _payload(data, FINDING_FIELDS - {"finding_no", "issue_type", "record_type", "record_id"})
        if "severity" in payload:
            validate_finding_severity(str(payload["severity"]))
        if "status" in payload:
            next_status = str(payload["status"])
            validate_finding_transition(finding.status, next_status)
            if next_status == "closed":
                payload.setdefault("closed_at", _utc_now_naive())
                payload.setdefault("reviewed_at", _utc_now_naive())
        if payload.get("project_id") is not None:
            await self._get_project_or_raise(int(payload["project_id"]))
        _assign(finding, payload)
        await self._session.commit()
        await self._session.refresh(finding)
        return finding

    async def _existing_open_finding(self, payload: dict[str, Any]) -> m.CarbonVerificationFinding | None:
        record_type = payload.get("record_type")
        record_id = payload.get("record_id")
        issue_type = payload.get("issue_type")
        if not record_type or not record_id or not issue_type:
            return None
        project_id = payload.get("project_id")
        project_condition = (
            m.CarbonVerificationFinding.project_id == int(project_id)
            if project_id is not None
            else m.CarbonVerificationFinding.project_id.is_(None)
        )
        return await self._session.scalar(
            select(m.CarbonVerificationFinding)
            .where(
                project_condition,
                m.CarbonVerificationFinding.record_type == str(record_type),
                m.CarbonVerificationFinding.record_id == int(record_id),
                m.CarbonVerificationFinding.issue_type == str(issue_type),
                m.CarbonVerificationFinding.status != "closed",
            )
            .order_by(m.CarbonVerificationFinding.id.desc())
            .limit(1)
        )

    async def _get_or_raise(self, finding_id: int) -> m.CarbonVerificationFinding:
        finding = await self._session.get(m.CarbonVerificationFinding, finding_id)
        if finding is None:
            msg = "核查发现不存在"
            raise ValueError(msg)
        return finding

    async def _get_project_or_raise(self, project_id: int) -> m.CarbonVerificationProject:
        project = await self._session.get(m.CarbonVerificationProject, project_id)
        if project is None:
            msg = "核查项目不存在"
            raise ValueError(msg)
        return project

    async def _next_no(self) -> str:
        timestamp = datetime.datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        count = await self._session.scalar(select(func.count(m.CarbonVerificationFinding.id)))
        return f"VF-{timestamp}-{int(count or 0) + 1:04d}"


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
    if key in DATE_FIELDS and isinstance(value, str):
        return datetime.date.fromisoformat(value[:10])
    if key in DATETIME_FIELDS and isinstance(value, str):
        return datetime.datetime.fromisoformat(value).replace(tzinfo=None)
    return value


def _assign(obj: Any, payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        setattr(obj, key, value)


def _utc_now_naive() -> datetime.datetime:
    return datetime.datetime.now(UTC).replace(tzinfo=None)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value
