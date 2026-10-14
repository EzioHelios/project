"""Customer meter preparation never silently authorizes an organizational total."""

# ruff: noqa: DTZ001 - matches the database's timezone-naive interval columns.

import importlib.util
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

_path = Path(__file__).resolve().parents[4] / "tools/maintenance/prepare_xiangtai_meter_activities.py"
_spec = importlib.util.spec_from_file_location("xiangtai_meter_preparation", _path)
assert _spec is not None and _spec.loader is not None
maintenance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(maintenance)
pytestmark = pytest.mark.unit


def fixture_data():
    devices = {1: {"id": 1, "code": "meter-1", "name": "Meter", "sector_id": 2, "category": 0, "is_enable": True}}
    areas = {2: {"id": 2, "code": "P1", "name": "Area"}}
    fact = {
        "id": 10,
        "equipment_id": 1,
        "equipment_code": "meter-1",
        "area_id": "P1",
        "source_system": "meter_projection",
        "granularity": "hour",
        "data_quality": "measured",
        "unit": "kWh",
        "is_current": True,
        "energy_type_code": "purchased_electricity",
        "amount": Decimal("1.25"),
        "period_start": datetime(2026, 9, 1),
        "period_end": datetime(2026, 9, 1, 1),
        "projection_run_id": 3,
        "revision_no": 1,
        "source_snapshot": {"reading_source_system": "yunji"},
    }
    return [fact], devices, areas


def test_monthly_preparation_is_stable_and_not_calculable():
    facts, devices, areas = fixture_data()
    next_fact = {**facts[0], "id": 11, "period_start": datetime(2026, 9, 1, 2), "period_end": datetime(2026, 9, 1, 3)}
    plan = maintenance.monthly_plan([*facts, next_fact], devices, areas)
    row = plan["items"][0]
    assert row["kwh"] == "2.50"
    assert row["fact_count"] == 2
    assert row["missing_hours"] == 718
    assert row["status"] == "draft"
    assert row["boundary_status"] == "excluded"
    assert maintenance.digest(plan) == maintenance.digest(maintenance.monthly_plan([next_fact, *facts], devices, areas))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("granularity", "day"),
        ("is_current", False),
        ("data_quality", "simulated"),
        ("source_system", "meter_hourly"),
        ("unit", "MWh"),
        ("amount", Decimal(-1)),
        ("area_id", "other"),
        ("equipment_id", 99),
        ("equipment_code", "other"),
        ("source_snapshot", {"reading_source_system": "demo_seed"}),
    ],
)
def test_bad_sources_and_bindings_fail_closed(field, value):
    facts, devices, areas = fixture_data()
    facts[0][field] = value
    with pytest.raises(ValueError):
        maintenance.monthly_plan(facts, devices, areas)


def test_overlap_and_month_crossing_are_rejected():
    facts, devices, areas = fixture_data()
    with pytest.raises(ValueError, match="Overlapping"):
        maintenance.monthly_plan([*facts, facts[0]], devices, areas)
    facts[0]["period_start"] = datetime(2026, 9, 30, 23, 30)
    facts[0]["period_end"] = facts[0]["period_start"] + timedelta(hours=1)
    with pytest.raises(ValueError, match="crosses"):
        maintenance.monthly_plan(facts, devices, areas)


@pytest.mark.parametrize("kind", ["pv", "storage", "disabled"])
def test_unconfirmed_energy_roles_are_held(kind):
    facts, devices, areas = fixture_data()
    if kind == "pv":
        devices[1]["category"] = 1
    elif kind == "storage":
        devices[1]["code"] = "432301227008"
    else:
        devices[1]["is_enable"] = False
    plan = maintenance.monthly_plan(facts, devices, areas)
    assert plan["items"] == []
    assert sum(plan["held_fact_counts"].values()) == 1


@pytest.mark.anyio
async def test_exact_replay_does_not_rewrite_existing_data():
    existing = SimpleNamespace(name="original")
    session = SimpleNamespace(scalar=AsyncMock(return_value=existing), add=Mock(), flush=AsyncMock())
    row = await maintenance.ensure(session, maintenance.m.ReportingOrganization, {"code": "XT"}, {"name": "original"})
    assert row is existing
    session.add.assert_not_called()
    session.flush.assert_not_awaited()
    with pytest.raises(ValueError, match="differs"):
        await maintenance.ensure(session, maintenance.m.ReportingOrganization, {"code": "XT"}, {"name": "replacement"})
    assert existing.name == "original"


@pytest.mark.anyio
async def test_apply_keeps_candidates_out_of_inventory_and_uses_category_catalog(monkeypatch):
    facts, devices, areas = fixture_data()
    captured = []

    async def capture(_session, model, key, values):
        captured.append((model, key, values))
        return SimpleNamespace(id=len(captured), **key, **values)

    allocation = SimpleNamespace(execute=AsyncMock())
    monkeypatch.setattr(maintenance, "ensure", capture)
    monkeypatch.setattr(maintenance, "ReplaceActivityAllocations", lambda _session: allocation)
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    result = await maintenance.apply_plan(session, maintenance.monthly_plan(facts, devices, areas))
    assert result == {"created": 1, "reused": 0, "formal_runs_created": 0}
    activity = next(values for model, _, values in captured if model is maintenance.g.GhgActivityRecord)
    assert activity["source_mechanism"] == maintenance.CATEGORY.source_mechanism
    assert activity["value_chain_position"] == maintenance.CATEGORY.value_chain_position
    assert activity["source_payload"]["organization_total_eligible"] is False
    assert activity["status"] == "draft"
    assert activity["boundary_status"] == "excluded"
    assert activity["organization_boundary_id"] is None
    assert activity["source_payload"]["supplier_name"] == ""
    assert allocation.execute.await_args.kwargs["commit"] is False
