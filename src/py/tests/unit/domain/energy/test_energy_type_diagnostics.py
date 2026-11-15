from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.energy.usecases.energy_types import STANDARD_ENERGY_TYPES, _collect_ghg_activity_issues


async def diagnose(payloads: list[dict[str, object]]) -> list:
    team_id = uuid4()
    activities = [
        SimpleNamespace(
            team_id=team_id, iso_category_code="2.1", activity_code="purchased_energy", source_payload=payload
        )
        for payload in deepcopy(payloads)
    ]
    session = MagicMock()
    session.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: activities))
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    issues = []
    await _collect_ghg_activity_issues(
        session, issues, {team_id: ("factory", "Factory")}, {item.code for item in STANDARD_ENERGY_TYPES}, team_id
    )
    statement = session.scalars.call_args.args[0]
    assert team_id in statement.compile().params.values()
    assert [row.source_payload for row in activities] == payloads
    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    session.flush.assert_not_awaited()
    return issues


@pytest.mark.anyio
@pytest.mark.parametrize("energy_type", ["electricity", "purchased_heat", "steam", "cooling"])
async def test_ghg_purchased_energy_enums_are_valid_without_registry_field(energy_type: str) -> None:
    assert await diagnose([{"energy_type": energy_type}]) == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("code", "issue_type", "suggested"),
    [
        ("electricity", "alias", "purchased_electricity"),
        ("steam", "alias", "purchased_steam"),
        ("unknown_energy", "unknown", None),
        ("", "missing", None),
    ],
)
async def test_real_registry_field_is_still_checked_even_with_valid_ghg_enum(
    code: str, issue_type: str, suggested: str | None
) -> None:
    issues = await diagnose([{"energy_type": "electricity", "energy_type_code": code}])
    assert len(issues) == 1
    assert issues[0].field_name == "source_payload.energy_type_code"
    assert issues[0].issue_type == issue_type
    assert issues[0].suggested_code == suggested


@pytest.mark.anyio
async def test_unknown_ghg_enum_is_not_exempted_and_reports_actual_field() -> None:
    issues = await diagnose([{"energy_type": "purchased_electricity"}, {"energy_type": "unknown_energy"}])
    assert len(issues) == 2
    assert all(issue.field_name == "source_payload.energy_type" and issue.issue_type == "unknown" for issue in issues)


@pytest.mark.anyio
async def test_diagnostic_keeps_alias_counts_separate_by_source_field() -> None:
    issues = await diagnose(
        [
            {"energy_type_code": "electricity"},
            {"energy_type_code": "electricity"},
            {"fuel_type": "electricity"},
            {"energy_type": "electricity"},
            {"energy_type_code": "purchased_electricity"},
        ]
    )
    assert {(issue.field_name, issue.row_count, issue.issue_type) for issue in issues} == {
        ("source_payload.energy_type_code", 2, "alias"),
        ("source_payload.fuel_type", 1, "alias"),
    }
