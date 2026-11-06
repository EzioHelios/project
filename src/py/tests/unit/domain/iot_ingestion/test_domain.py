from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.iot_ingestion.domain import (
    PayloadValidationError,
    normalize_meter_unit,
    parse_szscada_metering_v2,
    parse_szscada_scada_v1,
    temporary_equipment_code,
    temporary_external_device_id,
    temporary_meter_address,
)

FIXTURE_PATH = Path(__file__).parents[3] / "fixtures" / "carbon" / "mqtt" / "szscada_xc_v1.json"


def test_szscada_fixture_parses_seconds_timestamp_and_quality_states() -> None:
    payload = json.loads(FIXTURE_PATH.read_text())

    parsed = parse_szscada_scada_v1(payload)

    assert parsed.gateway_key == "gateway-fixture-001"
    assert parsed.published_at.isoformat() == "2026-07-10T05:30:45"
    assert len(parsed.points) == 28
    assert {point.meter_key for point in parsed.points} == {"m001", "m002", "m004"}
    assert any(point.is_valid and point.numeric_value == 0 for point in parsed.points)
    assert any(not point.is_valid and point.numeric_value == 0 for point in parsed.points)


def test_temporary_meter_identity_is_stable_and_visibly_provisional() -> None:
    gateway = "gateway-fixture-001"

    assert temporary_external_device_id(gateway, 4) == "szxc:gateway-fixture-001:m004"
    assert temporary_meter_address(gateway, 4) == "TEMP-SZXC-gateway-fixture-001-M004"
    assert temporary_equipment_code(gateway, 4).startswith("SZXC-")
    assert temporary_equipment_code(gateway, 4).endswith("-M004")


def test_szscada_rejects_points_without_temporary_meter_selector() -> None:
    payload = {
        "guid": "gateway-1",
        "ts": 1_700_000_000,
        "devs": [{"data": [{"name": "未编号总电能", "tag": "p001", "valid": 1, "value": 1}]}],
    }

    with pytest.raises(PayloadValidationError, match="temporary meter identity"):
        parse_szscada_scada_v1(payload)


def test_addressed_szscada_payload_uses_device_address_and_normalizes_units() -> None:
    payload = {
        "guid": "gateway-jy",
        "ts": 1_784_120_146,
        "devs": [
            {
                "devName": "办公室",
                "devAddress": "202501020786",
                "data": [
                    {
                        "t": 0,
                        "tag": "tag_010_p001",
                        "name": "正向有功总电能",
                        "valid": 1,
                        "value": 23.42,
                        "unit": "kWh",
                    },
                    {
                        "t": 0,
                        "tag": "tag_010_p006",
                        "name": "正向无功总电能",
                        "valid": 0,
                        "value": 3.14,
                        "unit": "kVarh",
                    },
                ],
            }
        ],
    }

    parsed = parse_szscada_metering_v2(payload)

    assert parsed.gateway_key == "gateway-jy"
    assert parsed.devices[0].device_address == "202501020786"
    assert [point.source_unit for point in parsed.devices[0].points] == ["kWh", "kvarh"]
    assert parsed.devices[0].points[0].source_type == 0
    assert parsed.devices[0].points[1].is_valid is False
    assert normalize_meter_unit("KVARH") == "kvarh"


def test_addressed_szscada_payload_rejects_duplicate_tags() -> None:
    point = {
        "t": 0,
        "tag": "tag_010_p001",
        "name": "正向有功总电能",
        "valid": 1,
        "value": 1,
        "unit": "kWh",
    }
    payload = {
        "guid": "gateway-jy",
        "ts": 1_784_120_146,
        "devs": [{"devName": "办公室", "devAddress": "202501020786", "data": [point, point]}],
    }

    with pytest.raises(PayloadValidationError, match="duplicate tag"):
        parse_szscada_metering_v2(payload)
