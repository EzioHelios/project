from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.production_denominator.policies import (
    ProductionDenominatorValidationError,
    normalize_production_output_payload,
    normalize_production_product_payload,
)


class _ProductSession:
    async def scalar(self, _statement: object) -> object:
        return SimpleNamespace(
            name="仓储作业",
            spec="出库",
            output_kind="operation_workload",
            default_unit="次",
            standard_unit="次",
        )


class _EmptySession:
    async def scalar(self, _statement: object) -> None:
        return None


def test_production_product_defaults_to_product_output_kind() -> None:
    payload = normalize_production_product_payload({"code": "P001", "name": "A 产品"})

    assert payload["output_kind"] == "product"


def test_production_product_rejects_unknown_output_kind() -> None:
    with pytest.raises(ProductionDenominatorValidationError):
        normalize_production_product_payload({"code": "P001", "name": "A 产品", "output_kind": "pcf_model"})


@pytest.mark.anyio
async def test_production_output_inherits_output_kind_from_output_object() -> None:
    payload = await normalize_production_output_payload(
        {
            "product_code": "OPS001",
            "period_start": "2026-06-01",
            "good_qty": "12",
        },
        _ProductSession(),  # type: ignore[arg-type]
    )

    assert payload["product_name"] == "仓储作业"
    assert payload["output_kind"] == "operation_workload"
    assert payload["unit"] == "次"
    assert payload["standard_unit"] == "次"


@pytest.mark.anyio
async def test_production_output_allows_material_handling_sample() -> None:
    payload = await normalize_production_output_payload(
        {
            "product_code": "MAT001",
            "product_name": "电力物资出库",
            "output_kind": "material_handling",
            "period_start": "2026-06-01",
            "good_qty": "300",
            "unit": "t",
        },
        _EmptySession(),  # type: ignore[arg-type]
    )

    assert payload["output_kind"] == "material_handling"
    assert payload["standard_qty"] == payload["good_qty"]
