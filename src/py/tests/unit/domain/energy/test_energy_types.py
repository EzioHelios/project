from __future__ import annotations

from app.domain.energy.usecases.energy_types import (
    STANDARD_ENERGY_TYPES,
    canonicalize_energy_type_code,
)
from app.domain.energy.usecases.imports import _data_quality


def test_canonicalize_energy_type_code_maps_activity_and_legacy_codes() -> None:
    assert canonicalize_energy_type_code("C21-ELECTRICITY") == "purchased_electricity"
    assert canonicalize_energy_type_code("electricity") == "purchased_electricity"
    assert canonicalize_energy_type_code("C11-GAS") == "natural_gas"
    assert canonicalize_energy_type_code("C12-DIESEL") == "diesel"
    assert canonicalize_energy_type_code("C22-STEAM") == "purchased_steam"
    assert canonicalize_energy_type_code("C14-REFRIGERANT") == "refrigerant"


def test_standard_energy_types_include_warehouse_scope_one_and_two_types() -> None:
    codes = {item.code for item in STANDARD_ENERGY_TYPES}

    assert {
        "purchased_electricity",
        "natural_gas",
        "diesel",
        "purchased_steam",
        "refrigerant",
    } <= codes


def test_energy_import_data_quality_keeps_imported_source() -> None:
    assert _data_quality("imported") == "imported"
    assert _data_quality("导入") == "imported"
    assert _data_quality("manual") == "manual"
    assert _data_quality("estimated") == "estimated"
