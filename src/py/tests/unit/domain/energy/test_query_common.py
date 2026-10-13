from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app.domain.energy.queries.analysis import (
    EnergyAnalysisQuery,
    _analysis_granularity,
    _analysis_source_granularity,
)
from app.domain.energy.queries.analysis import (
    _build_energy_interval_filters as build_energy_analysis_filters,
)
from app.domain.energy.queries.common import period_param, ratio_or_none
from app.domain.energy.queries.consumption import EnergyConsumptionQuery, build_energy_fact_filters
from app.domain.energy.queries.flow import EnergyFlowQuery, _build_flow_model, _build_report_items
from app.domain.energy.queries.flow import _build_filters as build_energy_flow_filters
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


def test_energy_analysis_month_granularity_reads_month_facts() -> None:
    where_sql, params = build_energy_analysis_filters(EnergyAnalysisQuery(granularity="month"), team_id="tenant-1")

    assert "granularity = :source_granularity" in where_sql
    assert _analysis_granularity("month") == "month"
    assert _analysis_source_granularity("month") == "month"
    assert params["source_granularity"] == "month"


def test_energy_analysis_filters_include_business_object_selectors() -> None:
    where_sql, params = build_energy_analysis_filters(
        EnergyAnalysisQuery(
            energy_type_code="purchased_electricity",
            area_id="12",
            equipment_id="34",
            use_system_code="warehouse_lighting",
            tariff_segment_type="peak",
        ),
        team_id="tenant-1",
    )

    assert "energy_type_code = :energy_type_code" in where_sql
    assert "area_id = :area_id" in where_sql
    assert "equipment_id = :equipment_id" in where_sql
    assert "use_system_code = :use_system_code" in where_sql
    assert "tariff_segment_type = :tariff_segment_type" in where_sql
    assert params["energy_type_code"] == "purchased_electricity"
    assert params["area_id"] == "12"
    assert params["equipment_id"] == 34


def test_energy_flow_filters_include_area_and_equipment_selectors() -> None:
    where_sql, params = build_energy_flow_filters(
        EnergyFlowQuery(energy_type_code="purchased_electricity", area_id="12", equipment_id="34"),
        team_id="tenant-1",
    )

    assert "energy_type_code in ('electricity', 'purchased_electricity')" in where_sql
    assert "area_id = :area_id" in where_sql
    assert "equipment_id = :equipment_id" in where_sql
    assert params["area_id"] == "12"
    assert params["equipment_id"] == 34


def test_energy_flow_model_preserves_recorded_attribution_without_inventing_losses() -> None:
    model = _build_flow_model(
        [
            {
                "energy_type_code": "purchased_electricity",
                "energy_type_name": "外购电力",
                "use_system_code": "warehouse_lighting",
                "use_system_name": "仓储照明",
                "area_id": "AUTO_WH",
                "area_name": "总装库",
                "energy_amount": 1200,
            }
        ],
        threshold_pct=5,
    )

    assert model["summary"]["total_input"] == 1200
    assert model["summary"]["high_loss_count"] == 0
    assert model["losses"] == []
    assert model["summary"]["total_loss"] is None
    assert {node["category"] for node in model["nodes"]} == {"source", "area", "equipment"}
    assert [link["value"] for link in model["links"]] == [1200, 1200]


def test_energy_flow_refuses_to_sum_incompatible_units() -> None:
    model = _build_flow_model(
        [
            {"energy_type_code": "electricity", "unit": "kWh", "energy_amount": 100},
            {"energy_type_code": "natural_gas", "unit": "m3", "energy_amount": 20},
        ],
        threshold_pct=5,
    )
    assert model["nodes"] == model["links"] == []
    assert model["summary"]["total_input"] is None
    assert model["summary"]["data_quality"] == "incompatible_units"


def test_energy_flow_report_items_follow_non_empty_flow_data() -> None:
    model = _build_flow_model(
        [
            {
                "energy_type_code": "purchased_electricity",
                "energy_type_name": "外购电力",
                "use_system_code": "charging",
                "use_system_name": "充电设施",
                "area_id": "CHARGING",
                "area_name": "充电区",
                "energy_amount": 860,
            }
        ],
        threshold_pct=5,
    )

    report_items = _build_report_items(model["summary"], model["links"], model["nodes"], model["unit"])

    assert len(report_items) == 1
    assert report_items[0]["title"] == "能流结构复盘"
    assert report_items[0]["evidence"]["归集总量(kWh)"] == 860
    assert "energy:" not in report_items[0]["evidence"]["重点链路"]


def test_energy_flow_report_items_empty_without_flow_data() -> None:
    report_items = _build_report_items({"total_input": 0, "utilized_energy": 0, "row_count": 0}, [], [], "kWh")

    assert report_items == []


def test_production_filters_always_include_the_active_team() -> None:
    team_id = UUID("22222222-2222-2222-2222-222222222222")

    where_sql, params = production_output_where_sql(ProductionOutputQuery(), team_id=team_id)

    assert "o.team_id = :team_id" in where_sql
    assert params["team_id"] == str(team_id)
