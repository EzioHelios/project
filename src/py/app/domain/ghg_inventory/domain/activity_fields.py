"""Activity fields shared by category workbooks and business projections."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActivityFieldDefinition:
    """One category-specific activity data field."""

    code: str
    label: str
    required: bool = False
    width: int = 18
    choices: tuple[str, ...] = ()


CATEGORY_ACTIVITY_FIELDS: dict[str, tuple[ActivityFieldDefinition, ...]] = {
    "stationary_combustion": (
        ActivityFieldDefinition("facility_or_device", "设备/设施", True),
        ActivityFieldDefinition("fuel_or_material", "燃料品种", True),
        ActivityFieldDefinition("meter_point", "计量点"),
    ),
    "mobile_combustion": (
        ActivityFieldDefinition("vehicle_or_machine", "车辆/机械", True),
        ActivityFieldDefinition("fuel_or_material", "燃料品种"),
        ActivityFieldDefinition("vehicle_type", "车型/机械类型"),
        ActivityFieldDefinition("work_hours", "运行工时"),
    ),
    "process_emissions": (
        ActivityFieldDefinition("process_name", "工序", True),
        ActivityFieldDefinition("product_or_material", "产品/原料", True),
        ActivityFieldDefinition("recovery_amount", "回收量"),
        ActivityFieldDefinition("abatement_runtime", "减排设施运行时间"),
    ),
    "fugitive_emissions": (
        ActivityFieldDefinition("gas_code", "气体", True),
        ActivityFieldDefinition("facility_or_device", "设备", True),
        ActivityFieldDefinition("opening_stock", "期初库存"),
        ActivityFieldDefinition("purchases", "购入量"),
        ActivityFieldDefinition("charges", "充注量"),
        ActivityFieldDefinition("closing_stock", "期末库存"),
        ActivityFieldDefinition("transfers", "转移量"),
        ActivityFieldDefinition("recovery", "回收量"),
    ),
    "purchased_energy": (
        ActivityFieldDefinition("energy_type", "能源种类", True),
        ActivityFieldDefinition("supplier_name", "供应商", True),
        ActivityFieldDefinition("meter_point", "计量点", True),
        ActivityFieldDefinition(
            "scope2_method",
            "Scope 2 方法",
            True,
            choices=("location", "market", "not_applicable"),
        ),
        ActivityFieldDefinition("market_instrument", "市场工具/凭证", width=24),
    ),
    "transport_travel": (
        ActivityFieldDefinition(
            "transport_direction",
            "运输方向",
            True,
            choices=("upstream", "downstream", "commute", "business_travel", "visitor"),
        ),
        ActivityFieldDefinition("transport_mode", "运输方式", True),
        ActivityFieldDefinition("distance_km", "里程(km)"),
        ActivityFieldDefinition("cargo_ton", "货物质量(t)"),
        ActivityFieldDefinition("passenger_count", "人数"),
        ActivityFieldDefinition("carrier", "承运商"),
        ActivityFieldDefinition("origin", "起点"),
        ActivityFieldDefinition("destination", "终点"),
    ),
    "purchased_products": (
        ActivityFieldDefinition("supplier_name", "供应商", True),
        ActivityFieldDefinition("product_or_service", "产品/服务", True),
        ActivityFieldDefinition("spend_cny", "支出(元)"),
        ActivityFieldDefinition("geography", "地域"),
        ActivityFieldDefinition("technology", "技术"),
        ActivityFieldDefinition("lifecycle_boundary", "生命周期边界", True),
    ),
    "operational_waste": (
        ActivityFieldDefinition("waste_type", "废物/废水类型", True),
        ActivityFieldDefinition("treatment_method", "处理方式", True),
        ActivityFieldDefinition("treatment_vendor", "处理方", True),
        ActivityFieldDefinition("transport_included", "是否含运输", True, choices=("yes", "no")),
    ),
    "upstream_leased_assets": (
        ActivityFieldDefinition("asset_name", "租入资产", True),
        ActivityFieldDefinition("lessor", "出租方", True),
        ActivityFieldDefinition("organization_boundary", "组织边界判定", True),
    ),
    "sold_products": (
        ActivityFieldDefinition("product_name", "售出产品", True),
        ActivityFieldDefinition("sales_quantity", "销量", True),
        ActivityFieldDefinition("use_lifetime", "使用寿命"),
        ActivityFieldDefinition("use_scenario", "使用/报废情景", True, 24),
    ),
    "downstream_assets": (
        ActivityFieldDefinition("counterparty", "承租方/加盟商/被投资方", True, 28),
        ActivityFieldDefinition("asset_or_investment", "资产/项目", True),
        ActivityFieldDefinition("attribution_ratio", "归因比例", True),
        ActivityFieldDefinition("coverage_ratio", "数据覆盖率"),
    ),
    "land_removals": (
        ActivityFieldDefinition("land_plot", "地块/GIS边界", True),
        ActivityFieldDefinition("land_category", "土地类别", True),
        ActivityFieldDefinition("area_ha", "面积(ha)", True),
        ActivityFieldDefinition("baseline_stock", "基期碳库", True),
        ActivityFieldDefinition("reporting_stock", "报告期碳库", True),
        ActivityFieldDefinition("reversal_event", "逆转事件"),
    ),
    "other_indirect": (
        ActivityFieldDefinition("unclassified_reason", "未归类理由", True, 28),
        ActivityFieldDefinition("materiality_assessment", "重要性评估", True, 28),
        ActivityFieldDefinition("approved_by", "批准人", True),
    ),
}


def activity_field_payload(package_code: str) -> list[dict[str, object]]:
    """Return serializable field metadata for one category package."""
    return [
        {
            "code": field.code,
            "label": field.label,
            "required": field.required,
            "choices": list(field.choices),
        }
        for field in CATEGORY_ACTIVITY_FIELDS.get(package_code, ())
    ]
