# ruff: noqa: RUF001
"""Semantic checks for the exact downloadable Woheng inputs."""

from datetime import datetime, time
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.demo.ops.enterprise_entry import calculation_parameters, compare_cases, load_cases, sample_rows
from app.demo.showcase.builder import ACTIVITY_SERIES, REFRIGERANT_EVENTS, ShowcaseDemoBuilder
from app.domain.ghg_inventory.domain.calculation import calculate


def persisted_cases(city):
    cases = load_cases(city)
    facts, activities = [], []
    for index, case in enumerate(cases, 1):
        payload = dict(case.payload)
        if case.energy_type:
            facts.append(
                SimpleNamespace(
                    id=index,
                    source_record_id=case.record_code,
                    amount=case.amount,
                    unit=case.unit,
                    energy_type_code=case.energy_type,
                    equipment_code=case.equipment_code,
                    cost_cny=case.cost,
                    period_start=datetime.combine(case.start, time.min),
                    period_end=datetime.combine(case.end, time.max),
                )
            )
            payload["source_fact_ids"] = [index]
        activities.append(
            SimpleNamespace(
                record_code=case.record_code,
                activity_amount=case.amount,
                activity_unit=case.unit,
                period_start=case.start,
                period_end=case.end,
                iso_category_code=case.category,
                facility_code=case.area_code,
                source_payload=payload,
                source_record_type="energy_interval_fact" if case.energy_type else "business_ledger",
                source_record_id=index if case.energy_type else None,
            )
        )
    return cases, facts, activities


@pytest.mark.parametrize("city", ["TZ", "HZ"])
def test_actual_csv_inputs_match_energy_activity_and_business_semantics(city):
    cases, facts, activities = persisted_cases(city)
    assert compare_cases(cases, facts, activities) == []
    assert len(sample_rows(city, "能源导入")) == 4
    for raw, ready in zip(sample_rows(city, "能源月结"), sample_rows(city, "能源导入"), strict=True):
        assert raw["数量"] == ready["能源用量"]
        assert raw["费用（元）"] == ready["费用"]
        assert ready["月份"] == "2026-10"
        assert list(ready) == ["区域", "设备", "能源种类", "月份", "能源用量", "单位", "费用", "备注"]
        assert ready["能源种类"] in {"外购电力", "天然气", "柴油"}
        assert not any(
            code in str(ready)
            for code in ("BOILER-01", "PCC-METER-01", "natural_gas", "source_system", "woheng_enterprise_entry")
        )
    standby = next(c for c in cases if c.equipment_code == "GENSET-01")
    assert standby.amount == 0
    assert standby.category == "1.1"
    electricity = next(c for c in cases if c.energy_type == "purchased_electricity")
    assert electricity.area_code == "ENERGY"
    assert electricity.amount != electricity.cost
    assert all(f.energy_type_code != "refrigerant" for f in facts)


@pytest.mark.parametrize(
    "field,value", [("amount", Decimal(1)), ("unit", "L"), ("cost_cny", Decimal(0)), ("equipment_code", "GENSET-01")]
)
def test_semantic_validation_detects_wrong_values_even_with_identical_counts(field, value):
    cases, facts, activities = persisted_cases("TZ")
    setattr(facts[0], field, value)
    assert compare_cases(cases, facts, activities)


def test_semantic_validation_rejects_duplicate_and_wrong_source_links():
    cases, facts, activities = persisted_cases("TZ")
    activities[0].source_payload["source_fact_ids"] = [999]
    assert compare_cases(cases, facts, activities)
    cases, facts, activities = persisted_cases("TZ")
    assert compare_cases(cases, [*facts, facts[0]], activities)


@pytest.mark.parametrize(
    "city,expected",
    [
        ("TZ", ("283192.2", "40213.2", "1819.68", "0", "1620", "0", "106.92", "172.8")),
        ("HZ", ("205110.4", "48428.8", "1391.52", "0", "1215", "0", "95.04", "108")),
    ],
)
def test_exact_calculation_results_and_gas_identity(city, expected):
    for case, expected_co2e in zip(load_cases(city), expected, strict=True):
        method, parameters = calculation_parameters(case)
        output = calculate(method, case.amount, {key: value for key, (value, _) in parameters.items()}, case.payload)
        assert output.co2e_kg == Decimal(expected_co2e)
        if case.category == "1.4":
            assert output.gas_code == "R32"
            assert output.gas_mass_kg == case.amount
            assert output.gwp_value == 675
            assert case.start == case.end
            assert case.amount != Decimal(case.payload["rated_charge_kg"])


def test_refrigerant_history_has_only_explicit_maintenance_events():
    spec = next(item for item in ACTIVITY_SERIES if item.code == "C14-REFRIGERANT")
    for year in (2024, 2025, 2026):
        for month in range(1, 13):
            amount = ShowcaseDemoBuilder._monthly_amount(spec, year=year, month=month)
            assert bool(amount) == ((year, month) in REFRIGERANT_EVENTS)


@pytest.mark.parametrize("city", ["TZ", "HZ"])
@pytest.mark.parametrize("category", ["1.4", "3.3", "3.1"])
def test_downloadable_xlsx_uses_current_backend_single_sheet_contract(city, category):
    import base64
    from io import BytesIO

    from openpyxl import load_workbook

    from app.demo.ops.enterprise_entry import CITY_NAMES, SAMPLE_ROOT
    from app.demo.ops.entry_samples import CATEGORY_NAMES, sample_context
    from app.domain.ghg_inventory.infrastructure.workbook import decode_and_preview

    path = SAMPLE_ROOT / f"{CITY_NAMES[city]}基地_{CATEGORY_NAMES[category]}.xlsx"
    data = path.read_bytes()
    workbook = load_workbook(BytesIO(data))
    assert [sheet.title for sheet in workbook if sheet.sheet_state == "visible"] == ["03_活动数据"]
    preview, _digest = decode_and_preview(base64.b64encode(data).decode(), sample_context(city, category))
    assert not [issue for issue in preview.issues if issue.severity == "error"]
    cases = [case for case in load_cases(city) if case.category == category]
    for actual, expected in zip(preview.activities, cases, strict=True):
        assert Decimal(str(actual["activity_amount"])) == expected.amount
        assert actual["period_start"] == expected.start.isoformat()
        assert actual["period_end"] == expected.end.isoformat()
        assert actual["activity_unit"] == expected.unit
        assert actual["record_code"] == expected.record_code
        if category == "1.4":
            assert actual["gas_code"] == "R32"
            assert Decimal(str(actual["recovery"])) == Decimal(expected.payload["recovery"])


@pytest.mark.parametrize("city", ["TZ", "HZ"])
@pytest.mark.parametrize("link_kind", ["foreign_key", "source_fact_ids", "both"])
def test_public_energy_links_survive_payload_refresh_without_demo_markers(city, link_kind):
    cases, facts, activities = persisted_cases(city)
    for activity in activities:
        activity.source_payload.pop("input_record", None)
        if activity.source_record_type != "energy_interval_fact":
            continue
        activity.record_code = f"GEN-ENERGY-{activity.source_record_id}"
        activity.source_payload = {"source_fact_ids": [activity.source_record_id]}
        if link_kind == "foreign_key":
            activity.source_payload = {}
        elif link_kind == "source_fact_ids":
            activity.source_record_id = None
    assert compare_cases(cases, facts, list(reversed(activities))) == []


@pytest.mark.parametrize(
    "defect", ["wrong_type", "foreign_fact", "conflicting_links", "multiple_facts", "duplicate", "malformed"]
)
def test_energy_link_validation_rejects_bad_provenance_despite_demo_marker(defect):
    cases, facts, activities = persisted_cases("TZ")
    activity = activities[0]
    activity.source_payload["input_record"] = cases[0].record_code
    if defect == "wrong_type":
        activity.source_record_type = "business_ledger"
    elif defect == "foreign_fact":
        activity.source_record_id = 999
        activity.source_payload["source_fact_ids"] = [999]
    elif defect == "conflicting_links":
        activity.source_payload["source_fact_ids"] = [999]
    elif defect == "multiple_facts":
        activity.source_record_id = None
        activity.source_payload["source_fact_ids"] = [facts[0].id, facts[1].id]
    elif defect == "duplicate":
        activities.append(activity)
    else:
        activity.source_payload["source_fact_ids"] = [{"id": facts[0].id}]
    assert compare_cases(cases, facts, activities)
