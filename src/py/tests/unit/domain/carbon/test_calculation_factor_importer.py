from __future__ import annotations

from pathlib import Path

from app.domain.carbon.calculation_factor_importer import load_checklist_rows


def test_load_checklist_rows_parses_template() -> None:
    template_path = Path(__file__).resolve().parents[6] / "docs/carbon/calculation-factor-checklist-template.csv"
    rows = load_checklist_rows(template_path)

    assert len(rows) == 16
    first = rows[0]
    assert first.scope == "scope1"
    assert first.category == "fuel"
    assert first.sub_category == "diesel"
    assert str(first.factor_value) == "2.65"
    assert first.projection_status == "derived"
    assert first.is_active is True
