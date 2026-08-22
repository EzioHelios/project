"""Pure policies for assigning GHG activities to internal resources."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

AREA_PHYSICAL_REQUIRED = "physical_required"
AREA_ATTRIBUTION_REQUIRED = "attribution_required"
AREA_OPTIONAL = "optional"

EQUIPMENT_RECOMMENDED = "recommended"
EQUIPMENT_CONDITIONAL = "conditional"
EQUIPMENT_NOT_APPLICABLE = "not_applicable"

ALLOCATION_ROLES = {
    "physical_origin",
    "energy_consumption",
    "metering_point",
    "waste_generation",
    "asset_location",
    "responsibility",
    "beneficiary",
    "organization_root",
}


@dataclass(frozen=True, slots=True)
class CategoryAllocationPolicy:
    """Controlled allocation semantics for one ISO 14064-1 subcategory."""

    category_code: str
    area_requirement: str
    equipment_requirement: str
    default_role: str
    external_origin_allowed: bool = False


def _policy(
    category_code: str,
    area_requirement: str,
    equipment_requirement: str,
    default_role: str,
    *,
    external_origin_allowed: bool = False,
) -> CategoryAllocationPolicy:
    return CategoryAllocationPolicy(
        category_code=category_code,
        area_requirement=area_requirement,
        equipment_requirement=equipment_requirement,
        default_role=default_role,
        external_origin_allowed=external_origin_allowed,
    )


CATEGORY_ALLOCATION_POLICIES: tuple[CategoryAllocationPolicy, ...] = (
    _policy("1.1", AREA_PHYSICAL_REQUIRED, EQUIPMENT_RECOMMENDED, "physical_origin"),
    _policy("1.2", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_RECOMMENDED, "asset_location"),
    _policy("1.3", AREA_PHYSICAL_REQUIRED, EQUIPMENT_RECOMMENDED, "physical_origin"),
    _policy("1.4", AREA_PHYSICAL_REQUIRED, EQUIPMENT_RECOMMENDED, "physical_origin"),
    _policy("1.5", AREA_PHYSICAL_REQUIRED, EQUIPMENT_NOT_APPLICABLE, "physical_origin"),
    _policy("2.1", AREA_PHYSICAL_REQUIRED, EQUIPMENT_RECOMMENDED, "energy_consumption"),
    _policy("2.2", AREA_PHYSICAL_REQUIRED, EQUIPMENT_CONDITIONAL, "energy_consumption"),
    _policy("3.1", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_NOT_APPLICABLE, "responsibility", external_origin_allowed=True),
    _policy("3.2", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_NOT_APPLICABLE, "responsibility", external_origin_allowed=True),
    _policy("3.3", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_NOT_APPLICABLE, "responsibility", external_origin_allowed=True),
    _policy("3.4", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_NOT_APPLICABLE, "responsibility", external_origin_allowed=True),
    _policy("3.5", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_NOT_APPLICABLE, "responsibility", external_origin_allowed=True),
    _policy("4.1", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_CONDITIONAL, "beneficiary", external_origin_allowed=True),
    _policy("4.2", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_CONDITIONAL, "asset_location", external_origin_allowed=True),
    _policy("4.3", AREA_PHYSICAL_REQUIRED, EQUIPMENT_CONDITIONAL, "energy_consumption", external_origin_allowed=True),
    _policy("4.4", AREA_PHYSICAL_REQUIRED, EQUIPMENT_CONDITIONAL, "waste_generation", external_origin_allowed=True),
    _policy("4.5", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_CONDITIONAL, "asset_location", external_origin_allowed=True),
    _policy("5.1", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_NOT_APPLICABLE, "responsibility", external_origin_allowed=True),
    _policy("5.2", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_NOT_APPLICABLE, "responsibility", external_origin_allowed=True),
    _policy("5.3", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_NOT_APPLICABLE, "responsibility", external_origin_allowed=True),
    _policy("5.4", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_CONDITIONAL, "responsibility", external_origin_allowed=True),
    _policy("5.5", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_NOT_APPLICABLE, "responsibility", external_origin_allowed=True),
    _policy(
        "5.6", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_NOT_APPLICABLE, "organization_root", external_origin_allowed=True
    ),
    _policy("6.1", AREA_ATTRIBUTION_REQUIRED, EQUIPMENT_CONDITIONAL, "responsibility", external_origin_allowed=True),
)

CATEGORY_ALLOCATION_POLICY_BY_CODE = {item.category_code: item for item in CATEGORY_ALLOCATION_POLICIES}


def validate_allocation(
    *,
    category_code: str,
    role: str,
    area_present: bool,
    equipment_present: bool,
    external_present: bool,
) -> None:
    """Validate one allocation without depending on persistence models."""
    policy = CATEGORY_ALLOCATION_POLICY_BY_CODE.get(category_code)
    if policy is None:
        msg = "不支持的温室气体二级分类"
        raise ValueError(msg)
    if role not in ALLOCATION_ROLES:
        msg = "不支持的区域设备归集角色"
        raise ValueError(msg)
    if not area_present:
        msg = "活动数据必须归集到区域树中的一个节点"
        raise ValueError(msg)
    if equipment_present and policy.equipment_requirement == EQUIPMENT_NOT_APPLICABLE:
        msg = "该分类不得把外部价值链对象登记为内部设备"
        raise ValueError(msg)
    if external_present and not policy.external_origin_allowed:
        msg = "该分类属于内部直接排放或输入能源, 不允许使用外部发生设施替代内部区域"
        raise ValueError(msg)


def validate_allocation_ratios(ratios: Iterable[Decimal]) -> None:
    """Require complete, non-overlapping allocation of one activity."""
    values = list(ratios)
    if not values:
        msg = "活动数据至少需要一条区域归集"
        raise ValueError(msg)
    if any(value <= 0 or value > 1 for value in values):
        msg = "归集比例必须大于0且不超过1"
        raise ValueError(msg)
    if abs(sum(values, Decimal(0)) - Decimal(1)) > Decimal("0.000001"):
        msg = "同一活动的归集比例合计必须等于100%"
        raise ValueError(msg)


def allocation_policy_payload(policy: CategoryAllocationPolicy) -> dict[str, object]:
    return {
        "categoryCode": policy.category_code,
        "areaRequirement": policy.area_requirement,
        "equipmentRequirement": policy.equipment_requirement,
        "defaultRole": policy.default_role,
        "externalOriginAllowed": policy.external_origin_allowed,
    }
