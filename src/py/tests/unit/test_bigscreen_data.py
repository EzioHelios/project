from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.domain.carbon.services._bigscreen import BigscreenCarbonService, BigscreenIntroService, BigscreenMetaService
from app.domain.carbon.services._bigscreen_ledger import parse_ledger_date
from app.domain.carbon.services._bigscreen_operations import descendant_codes, resolve_window, trend_points

pytestmark = [pytest.mark.anyio, pytest.mark.unit]


async def test_warehouse_profile_omits_unknown_dimensions_and_has_no_invented_photos():
    session = AsyncMock()
    session.scalar.return_value = SimpleNamespace(
        name="安方中心库",
        belong_unit="",
        industry=None,
        location=None,
        people_count=0,
        store_area=0,
        park_area=None,
        unify_code=None,
        other_info={},
    )
    session.scalars.return_value = Mock(all=Mock(return_value=[]))
    payload = await BigscreenIntroService(session, BigscreenMetaService("平台", "能碳", "")).build()
    assert [(item.label, item.value) for item in payload.company_facts] == [("企业名称", "安方中心库")]
    assert payload.company_gallery == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2024/2/9", date(2024, 2, 9)),
        ("2024-02-9", date(2024, 2, 9)),
        ("2024-02-29", date(2024, 2, 29)),
        ("2023-02-29", None),
        ("02/03/2024", None),
        (None, None),
    ],
)
def test_ledger_date_accepts_only_known_year_first_formats(raw, expected):
    assert parse_ledger_date(raw) == expected


async def test_missing_carbon_results_do_not_fabricate_scope_charts():
    session = AsyncMock()
    session.scalar.return_value = None
    payload = await BigscreenCarbonService(session).build()
    assert all(metric.value is None for metric in payload.hero_metrics)
    assert payload.scope_distribution == []
    assert payload.area_ranking == []
    assert payload.period_facts == []


def test_window_defaults_to_available_month():
    assert resolve_window(None, None, datetime(2024, 4, 16, tzinfo=UTC)) == (date(2024, 4, 1), date(2024, 4, 16))


@pytest.mark.parametrize(("start", "end"), [(date(2026, 5, 1), date(2026, 4, 1)), (date(2024, 1, 1), date(2026, 1, 1))])
def test_reject_invalid_window(start, end):
    with pytest.raises(ValueError):
        resolve_window(start, end, None)


def test_missing_intervals_are_null_not_zero():
    points = trend_points(
        [(datetime(2026, 10, 1, tzinfo=UTC), 0), (datetime(2026, 10, 3, tzinfo=UTC), 5)],
        date(2026, 10, 1),
        date(2026, 10, 3),
        "day",
    )
    assert [point["value"] for point in points] == [0, None, 5]


def test_month_grain_respects_year_transition():
    points = trend_points([(datetime(2025, 12, 1, tzinfo=UTC), 20)], date(2025, 12, 10), date(2026, 1, 2), "month")
    assert [point["period"] for point in points] == ["2025-12-01T00:00:00", "2026-01-01T00:00:00"]
    assert points[1]["value"] is None


def test_area_hierarchy_uses_ids_and_rejects_unknown_roots():
    rows = [(1, "ROOT", None, "Root"), (2, "A", 1, "Area"), (3, "B", 2, "Area"), (4, "OTHER", None, "Area")]
    assert descendant_codes(rows, "ROOT") == ["ROOT", "A", "B"]
    assert descendant_codes(rows, "A") == ["A", "B"]
    assert descendant_codes(rows, "missing") == []
