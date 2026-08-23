"""Typed contracts for the organization-boundary workbench."""

from __future__ import annotations

import msgspec

from app.lib.schema import CamelizedBaseStruct


def _empty_str_list() -> list[str]:
    return []


def _empty_int_list() -> list[int]:
    return []


def _empty_area_list() -> list[BoundaryAreaSelection]:
    return []


def _empty_equipment_list() -> list[BoundaryEquipmentSelection]:
    return []


class OperationalBoundarySelection(CamelizedBaseStruct, kw_only=True):
    """Standards categories enabled for one boundary version."""

    schema_version: str = "organization-boundary-v1"
    scopes: list[str] = msgspec.field(default_factory=_empty_str_list)
    scope2_methods: list[str] = msgspec.field(default_factory=_empty_str_list)
    iso_categories: list[str] = msgspec.field(default_factory=_empty_str_list)
    scope3_categories: list[int] = msgspec.field(default_factory=_empty_int_list)


class BoundaryAreaSelection(CamelizedBaseStruct, kw_only=True):
    area_id: int
    included: bool = True
    exclusion_reason: str | None = None


class BoundaryEquipmentSelection(CamelizedBaseStruct, kw_only=True):
    equipment_id: int
    area_id: int
    included: bool = True
    exclusion_reason: str | None = None


class SaveBoundarySelectionRequest(CamelizedBaseStruct, kw_only=True):
    operational_boundary: OperationalBoundarySelection
    areas: list[BoundaryAreaSelection] = msgspec.field(default_factory=_empty_area_list)
    equipment: list[BoundaryEquipmentSelection] = msgspec.field(default_factory=_empty_equipment_list)


class BoundaryVersionResponse(CamelizedBaseStruct):
    id: int
    reporting_org_id: int
    period_id: int
    boundary_no: str
    boundary_name: str
    boundary_type: str
    boundary_method: str
    version: int
    status: str
    published_at: str | None


class BoundaryAreaResponse(CamelizedBaseStruct):
    area_id: int
    code: str
    name: str
    included: bool
    exclusion_reason: str | None


class BoundaryEquipmentResponse(CamelizedBaseStruct):
    equipment_id: int
    area_id: int
    code: str
    name: str
    included: bool
    exclusion_reason: str | None


class BoundarySelectionResponse(CamelizedBaseStruct):
    boundary: BoundaryVersionResponse
    operational_boundary: OperationalBoundarySelection
    areas: list[BoundaryAreaResponse]
    equipment: list[BoundaryEquipmentResponse]


class BoundarySelectionChange(CamelizedBaseStruct):
    key: str
    change_type: str
    before: str | bool | int | list[str] | None
    after: str | bool | int | list[str] | None


class BoundaryDiffResponse(CamelizedBaseStruct):
    boundary_id: int
    against_boundary_id: int | None
    changes: list[BoundarySelectionChange]
