from __future__ import annotations

from app.domain.carbon.collectors.yunji_adapter import YunjiAdapter


def test_yunji_normalize_converts_timestamps_and_preserves_meter_address() -> None:
    raw = {
        "IsSuccess": True,
        "_meta": {"start_time": "2026-07-10 15:00:00", "end_time": "2026-07-10 16:00:00"},
        "Data": [
            {
                "Address": "YJ-METER-001",
                "AmmeterID": "YJ-METER-001",
                "AmmeterName": "测试电表",
                "AreaID": "area-1",
                "AreaName": "测试区域",
                "ReadingDate": "2026-07-10 15:45",
                "ZYGDN": 10.1,
                "FYGDN": 0,
                "ZWGDN": 2.3,
                "FWGDN": 0,
                "ZYGDNSZ": 10.1,
                "FYGDNSZ": 0,
                "ZWGDNSZ": 2.3,
                "FWGDNSZ": 0,
            }
        ],
    }

    adapter = YunjiAdapter()
    try:
        rows = adapter.normalize(raw)
    finally:
        # The test does not open a network connection, but the adapter owns this client.
        import asyncio

        asyncio.run(adapter.client.aclose())

    assert len(rows) == 1
    assert rows[0]["equipment_id"] == "YJ-METER-001"
    assert rows[0]["reading_time"].isoformat() == "2026-07-10T15:45:00"
    assert rows[0]["start_time"].isoformat() == "2026-07-10T15:00:00"
