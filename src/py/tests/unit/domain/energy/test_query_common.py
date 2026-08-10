from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app.domain.energy.queries.common import period_param, ratio_or_none
from app.domain.energy.queries.consumption import EnergyConsumptionQuery, build_energy_fact_filters
from app.domain.production_denominator.queries import ProductionOutputQuery, production_output_where_sql


def test_period_param_converts_http_date_and_datetime_strings() -> None:
    assert period_param("2026-05-01") == date(2026, 5, 1)
    assert period_param("2026-05-01T08:30:00") == datetime.fromisoformat("2026-05-01T08:30:00")


def test_ratio_or_none_returns_none_for_missing_denominator() -> None:
    assert ratio_or_none(10, None) is None


def test_ratio_or_none_returns_none_for_zero_denominator() -> None:
    assert ratio_or_none(10, 0) is None


def test_ratio_or_none_rounds_non_zero_ratio() -> None:
    assert ratio_or_none(1, 3, 4) == 0.3333


def test_energy_fact_filters_always_include_the_active_team() -> None:
    team_id = UUID("11111111-1111-1111-1111-111111111111")

    where_sql, params = build_energy_fact_filters(EnergyConsumptionQuery(), team_id=team_id)

    assert "team_id = :team_id" in where_sql
    assert params["team_id"] == str(team_id)


def test_production_filters_always_include_the_active_team() -> None:
    team_id = UUID("22222222-2222-2222-2222-222222222222")

    where_sql, params = production_output_where_sql(ProductionOutputQuery(), team_id=team_id)

    assert "o.team_id = :team_id" in where_sql
    assert params["team_id"] == str(team_id)
