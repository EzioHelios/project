from __future__ import annotations

from app.domain.carbon.emission_calculator import _preferred_sub_categories, _preferred_units


def test_factor_sub_category_aliases_map_chinese_natural_gas_to_factor_key() -> None:
    assert _preferred_sub_categories("scope1", "fuel", "天然气") == ["天然气", "natural_gas"]


def test_factor_unit_aliases_match_plain_and_superscript_cubic_meter() -> None:
    assert _preferred_units("m3") == ["m3", "m³", "Nm³", "nm3"]


def test_unknown_factor_key_preserves_original_lookup() -> None:
    assert _preferred_sub_categories("scope3", "waste", "干铝屑") == ["干铝屑"]


def test_factor_sub_category_aliases_map_honda_waste_slag_to_checklist_key() -> None:
    assert _preferred_sub_categories("scope3", "waste", "废铝渣") == ["废铝渣", "铝渣"]
