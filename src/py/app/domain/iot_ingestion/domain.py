"""Pure domain parsing and identity rules for external MQTT payloads."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class PayloadValidationError(ValueError):
    """Raised when an inbound payload does not satisfy its source contract."""


METER_NAME_PATTERN = re.compile(r"^(?P<meter_number>\d+)号电表(?P<label>.+)$")
MILLISECONDS_TIMESTAMP_THRESHOLD = 100_000_000_000
ERR_DEVS_REQUIRED = "devs must be a non-empty list"
ERR_DEVICE_ENTRY = "devs entries must be objects"
ERR_DEVICE_DATA = "devs[].data must be a list"
ERR_POINT_ENTRY = "data entries must be objects"
ERR_NO_POINTS = "payload contains no points"
ERR_TIMESTAMP = "ts must be a Unix timestamp"
ERR_TIMESTAMP_RANGE = "ts is outside the supported timestamp range"


@dataclass(frozen=True, slots=True)
class ParsedPoint:
    """A source point expanded from a SZSCADA payload."""

    meter_number: int
    meter_key: str
    source_name: str
    source_label: str
    source_tag: str
    raw_value: str | None
    numeric_value: Decimal | None
    is_valid: bool
    source_type: int | None


@dataclass(frozen=True, slots=True)
class ParsedSzscadaPayload:
    """Normalized envelope for the SZSCADA SCADA v1 payload contract."""

    gateway_key: str
    published_at: datetime
    points: tuple[ParsedPoint, ...]


def payload_hash(payload: dict[str, Any]) -> str:
    """Return a stable SHA-256 digest for idempotent inbound-message storage."""
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def parse_szscada_scada_v1(payload: dict[str, Any]) -> ParsedSzscadaPayload:
    """Parse the observed SZSCADA `devs[].data[]` payload without DB dependencies."""
    gateway_key = _required_text(payload.get("guid"), "guid")
    published_at = _timestamp(payload.get("ts"))
    devices = payload.get("devs")
    if not isinstance(devices, list) or not devices:
        raise PayloadValidationError(ERR_DEVS_REQUIRED)

    points: list[ParsedPoint] = []
    for device in devices:
        if not isinstance(device, dict):
            raise PayloadValidationError(ERR_DEVICE_ENTRY)
        data = device.get("data")
        if not isinstance(data, list):
            raise PayloadValidationError(ERR_DEVICE_DATA)
        for raw_point in data:
            if not isinstance(raw_point, dict):
                raise PayloadValidationError(ERR_POINT_ENTRY)
            source_name = _required_text(raw_point.get("name"), "data[].name")
            matched = METER_NAME_PATTERN.match(source_name)
            if matched is None:
                msg = f"cannot derive temporary meter identity from point name: {source_name}"
                raise PayloadValidationError(msg)
            meter_number = int(matched.group("meter_number"))
            value = raw_point.get("value")
            raw_value = None if value is None else str(value)
            points.append(
                ParsedPoint(
                    meter_number=meter_number,
                    meter_key=f"m{meter_number:03d}",
                    source_name=source_name,
                    source_label=matched.group("label"),
                    source_tag=_required_text(raw_point.get("tag"), "data[].tag"),
                    raw_value=raw_value,
                    numeric_value=_decimal(value),
                    is_valid=raw_point.get("valid") == 1,
                    source_type=_optional_int(raw_point.get("t")),
                )
            )

    if not points:
        raise PayloadValidationError(ERR_NO_POINTS)
    return ParsedSzscadaPayload(gateway_key=gateway_key, published_at=published_at, points=tuple(points))


def temporary_external_device_id(gateway_key: str, meter_number: int) -> str:
    """Build the temporary external identifier used before a DL/T 645 address is known."""
    return f"szxc:{gateway_key}:m{meter_number:03d}"


def temporary_meter_address(gateway_key: str, meter_number: int) -> str:
    """Build a visible, explicitly temporary ammeter address."""
    return f"TEMP-SZXC-{gateway_key}-M{meter_number:03d}"


def temporary_equipment_code(gateway_key: str, meter_number: int) -> str:
    """Build a short team-local equipment code within the legacy 30-character column limit."""
    gateway_token = hashlib.sha1(gateway_key.encode(), usedforsecurity=False).hexdigest()[:8].upper()
    return f"SZXC-{gateway_token}-M{meter_number:03d}"


def _timestamp(value: object) -> datetime:
    raw = _timestamp_as_int(value)
    seconds = raw / 1000 if raw >= MILLISECONDS_TIMESTAMP_THRESHOLD else raw
    try:
        return datetime.fromtimestamp(seconds, UTC).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError) as exc:
        raise PayloadValidationError(ERR_TIMESTAMP_RANGE) from exc


def _timestamp_as_int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError) as exc:
        raise PayloadValidationError(ERR_TIMESTAMP) from exc


def _required_text(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        msg = f"{field_name} is required"
        raise PayloadValidationError(msg)
    return text


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        msg = f"point value is not numeric: {value}"
        raise PayloadValidationError(msg) from exc


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError) as exc:
        msg = f"point type is not an integer: {value}"
        raise PayloadValidationError(msg) from exc
