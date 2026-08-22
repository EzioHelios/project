"""Controlled organization-inventory classification and method catalog."""

from __future__ import annotations

# ruff: noqa: RUF001 - Chinese business formulas intentionally use mathematical glyphs.
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CategoryDefinition:
    code: str
    name: str
    iso_category: str
    ghg_scope: str
    scope3_category: int | None
    source_mechanism: str
    value_chain_position: str
    default_methods: tuple[str, ...]
    package_code: str


CATEGORIES: tuple[CategoryDefinition, ...] = (
    CategoryDefinition(
        "1.1",
        "固定燃烧",
        "类别1 直接排放与清除",
        "scope1",
        None,
        "stationary",
        "own",
        ("F01_NCV",),
        "stationary_combustion",
    ),
    CategoryDefinition(
        "1.2",
        "移动燃烧",
        "类别1 直接排放与清除",
        "scope1",
        None,
        "mobile",
        "own",
        ("F01_NCV", "F09_DISTANCE"),
        "mobile_combustion",
    ),
    CategoryDefinition(
        "1.3",
        "工艺过程排放",
        "类别1 直接排放与清除",
        "scope1",
        None,
        "process",
        "own",
        ("F02_EF", "F03_CARBON_BALANCE", "F04_INDUSTRIAL_GAS"),
        "process_emissions",
    ),
    CategoryDefinition(
        "1.4",
        "逸散排放",
        "类别1 直接排放与清除",
        "scope1",
        None,
        "fugitive",
        "own",
        ("F05_INVENTORY", "F02_EF"),
        "fugitive_emissions",
    ),
    CategoryDefinition(
        "1.5",
        "土地利用、土地利用变化与林业直接排放/清除",
        "类别1 直接排放与清除",
        "scope1",
        None,
        "land",
        "own",
        ("F11_STOCK_CHANGE",),
        "land_removals",
    ),
    CategoryDefinition(
        "2.1",
        "购入电力",
        "类别2 输入能源间接排放",
        "scope2",
        None,
        "energy",
        "upstream",
        ("F08_PURCHASED_ENERGY",),
        "purchased_energy",
    ),
    CategoryDefinition(
        "2.2",
        "购入其他能源",
        "类别2 输入能源间接排放",
        "scope2",
        None,
        "energy",
        "upstream",
        ("F08_PURCHASED_ENERGY",),
        "purchased_energy",
    ),
    CategoryDefinition(
        "3.1",
        "上游运输与配送",
        "类别3 运输间接排放",
        "scope3",
        4,
        "transport",
        "upstream",
        ("F09_TRANSPORT_ACTIVITY", "F10_VALUE_CHAIN"),
        "transport_travel",
    ),
    CategoryDefinition(
        "3.2",
        "下游运输与配送",
        "类别3 运输间接排放",
        "scope3",
        9,
        "transport",
        "downstream",
        ("F09_TRANSPORT_ACTIVITY", "F10_VALUE_CHAIN"),
        "transport_travel",
    ),
    CategoryDefinition(
        "3.3",
        "员工通勤",
        "类别3 运输间接排放",
        "scope3",
        7,
        "transport",
        "upstream",
        ("F09_TRANSPORT_ACTIVITY",),
        "transport_travel",
    ),
    CategoryDefinition(
        "3.4",
        "商务旅行",
        "类别3 运输间接排放",
        "scope3",
        6,
        "transport",
        "upstream",
        ("F09_TRANSPORT_ACTIVITY",),
        "transport_travel",
    ),
    CategoryDefinition(
        "3.5",
        "客户和访客交通",
        "类别3 运输间接排放",
        "scope3",
        None,
        "transport",
        "downstream",
        ("F09_TRANSPORT_ACTIVITY",),
        "transport_travel",
    ),
    CategoryDefinition(
        "4.1",
        "采购商品与服务",
        "类别4 组织使用产品产生的间接排放",
        "scope3",
        1,
        "value_chain",
        "upstream",
        ("F10_VALUE_CHAIN",),
        "purchased_products",
    ),
    CategoryDefinition(
        "4.2",
        "资本货物",
        "类别4 组织使用产品产生的间接排放",
        "scope3",
        2,
        "value_chain",
        "upstream",
        ("F10_VALUE_CHAIN",),
        "purchased_products",
    ),
    CategoryDefinition(
        "4.3",
        "燃料和能源相关活动",
        "类别4 组织使用产品产生的间接排放",
        "scope3",
        3,
        "value_chain",
        "upstream",
        ("F10_VALUE_CHAIN", "F08_PURCHASED_ENERGY"),
        "purchased_products",
    ),
    CategoryDefinition(
        "4.4",
        "运营废物处置",
        "类别4 组织使用产品产生的间接排放",
        "scope3",
        5,
        "value_chain",
        "upstream",
        ("F02_EF", "F07_BIO_WASTE", "F10_VALUE_CHAIN"),
        "operational_waste",
    ),
    CategoryDefinition(
        "4.5",
        "上游租赁资产",
        "类别4 组织使用产品产生的间接排放",
        "scope3",
        8,
        "value_chain",
        "upstream",
        ("F10_VALUE_CHAIN", "F08_PURCHASED_ENERGY"),
        "upstream_leased_assets",
    ),
    CategoryDefinition(
        "5.1",
        "售出产品加工",
        "类别5 与组织输出产品使用相关的间接排放",
        "scope3",
        10,
        "value_chain",
        "downstream",
        ("F10_VALUE_CHAIN",),
        "sold_products",
    ),
    CategoryDefinition(
        "5.2",
        "售出产品使用",
        "类别5 与组织输出产品使用相关的间接排放",
        "scope3",
        11,
        "value_chain",
        "downstream",
        ("F10_VALUE_CHAIN",),
        "sold_products",
    ),
    CategoryDefinition(
        "5.3",
        "售出产品报废处理",
        "类别5 与组织输出产品使用相关的间接排放",
        "scope3",
        12,
        "value_chain",
        "downstream",
        ("F10_VALUE_CHAIN", "F07_BIO_WASTE"),
        "sold_products",
    ),
    CategoryDefinition(
        "5.4",
        "下游租赁资产",
        "类别5 与组织输出产品使用相关的间接排放",
        "scope3",
        13,
        "value_chain",
        "downstream",
        ("F10_VALUE_CHAIN", "F08_PURCHASED_ENERGY"),
        "downstream_assets",
    ),
    CategoryDefinition(
        "5.5",
        "特许经营",
        "类别5 与组织输出产品使用相关的间接排放",
        "scope3",
        14,
        "value_chain",
        "downstream",
        ("F10_VALUE_CHAIN",),
        "downstream_assets",
    ),
    CategoryDefinition(
        "5.6",
        "投资",
        "类别5 与组织输出产品使用相关的间接排放",
        "scope3",
        15,
        "value_chain",
        "downstream",
        ("F10_VALUE_CHAIN",),
        "downstream_assets",
    ),
    CategoryDefinition(
        "6.1",
        "其他经确认的间接排放",
        "类别6 其他间接排放",
        "scope3",
        None,
        "value_chain",
        "other",
        ("F02_EF",),
        "other_indirect",
    ),
)

CATEGORY_BY_CODE = {item.code: item for item in CATEGORIES}


@dataclass(frozen=True, slots=True)
class MethodDefinition:
    code: str
    name: str
    family: str
    formula: str
    parameters: tuple[dict[str, Any], ...]
    executable: bool = True


def _parameter(
    code: str,
    name: str,
    role: str,
    units: tuple[str, ...],
    *,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "role": role,
        "units": list(units),
        "required": required,
        "sourceModes": [
            "measured",
            "supplier",
            "national_default",
            "authority_published",
            "library",
            "custom_approved",
        ],
    }


METHODS: tuple[MethodDefinition, ...] = (
    MethodDefinition(
        "F01_NCV",
        "燃料燃烧热值法",
        "F01",
        "排放量 = 燃料消耗量 × 低位发热量 × 单位热值含碳量 × 氧化率 × 44/12",
        (
            _parameter("NCV", "低位发热量", "method_parameter", ("GJ/t", "GJ/万Nm3")),
            _parameter("CARBON_CONTENT", "单位热值含碳量", "method_parameter", ("tC/GJ",)),
            _parameter("OXIDATION_FACTOR", "碳氧化率", "method_parameter", ("ratio",)),
            _parameter("GWP", "全球增温潜势", "characterization", ("kgCO2e/kg",), required=False),
        ),
    ),
    MethodDefinition(
        "F02_EF",
        "活动数据排放因子法",
        "F02",
        "排放量 = 活动量 × 排放因子 × 单位换算 × GWP",
        (
            _parameter("EMISSION_FACTOR", "排放因子", "emission_factor", ("kgCO2e/unit", "kgGHG/unit")),
            _parameter("UNIT_CONVERSION", "单位换算", "characterization", ("ratio",), required=False),
            _parameter("GWP", "全球增温潜势", "characterization", ("kgCO2e/kg",), required=False),
        ),
    ),
    MethodDefinition(
        "F03_CARBON_BALANCE",
        "碳/物料平衡法",
        "F03",
        "排放量 =（输入碳－输出碳－库存变化－允许扣减的转移碳）× 44/12",
        (
            _parameter("CARBON_INPUT", "输入碳", "activity", ("tC", "kgC")),
            _parameter("CARBON_OUTPUT", "输出碳", "activity", ("tC", "kgC")),
            _parameter("CARBON_STOCK_CHANGE", "库存碳变化", "activity", ("tC", "kgC")),
            _parameter("CARBON_TRANSFERRED", "转移碳", "activity", ("tC", "kgC"), required=False),
        ),
        executable=False,
    ),
    MethodDefinition(
        "F04_INDUSTRIAL_GAS",
        "工业气体生成与减排法",
        "F04",
        "排放量 = 生成量－回收量－销毁量",
        (
            _parameter("GENERATION", "生成量", "activity", ("kg", "t")),
            _parameter("RECOVERED", "回收量", "activity", ("kg", "t")),
            _parameter("DESTROYED", "销毁量", "activity", ("kg", "t")),
            _parameter("GWP", "全球增温潜势", "characterization", ("kgCO2e/kg",)),
        ),
        executable=False,
    ),
    MethodDefinition(
        "F05_INVENTORY",
        "逸散盘存质量平衡法",
        "F05",
        "排放量 = 期初库存＋购入＋充注－期末库存－转移－回收",
        (
            _parameter("OPENING_STOCK", "期初库存", "activity", ("kg",)),
            _parameter("PURCHASES", "购入量", "activity", ("kg",)),
            _parameter("CHARGES", "充注量", "activity", ("kg",)),
            _parameter("CLOSING_STOCK", "期末库存", "activity", ("kg",)),
            _parameter("TRANSFERS", "转移量", "activity", ("kg",)),
            _parameter("RECOVERY", "回收量", "activity", ("kg",)),
            _parameter("GWP", "全球增温潜势", "characterization", ("kgCO2e/kg",)),
        ),
    ),
    MethodDefinition(
        "F06_MONITORING",
        "连续/周期监测法",
        "F06",
        "排放量 = Σ（流量 × 浓度 × 密度 × 时间 × 单位换算）",
        (
            _parameter("FLOW", "流量", "activity", ("Nm3/h",)),
            _parameter("CONCENTRATION", "浓度", "method_parameter", ("ratio", "mg/Nm3")),
            _parameter("DENSITY", "气体密度", "method_parameter", ("kg/Nm3",)),
            _parameter("DURATION", "有效运行时间", "activity", ("h",)),
        ),
        executable=False,
    ),
    MethodDefinition(
        "F07_BIO_WASTE",
        "生物过程、农业、废物与废水方法族",
        "F07",
        "排放量 = 方法子类活动数据 × 方法参数，并扣除符合要求的回收量",
        (
            _parameter("EMISSION_FACTOR", "方法子类排放因子", "emission_factor", ("kgGHG/unit",)),
            _parameter("RECOVERY", "回收量", "activity", ("kg",), required=False),
            _parameter("GWP", "全球增温潜势", "characterization", ("kgCO2e/kg",)),
        ),
        executable=False,
    ),
    MethodDefinition(
        "F08_PURCHASED_ENERGY",
        "购入能源因子法",
        "F08",
        "排放量 = 购入能源量 × 适用排放因子",
        (_parameter("ENERGY_FACTOR", "购入能源排放因子", "emission_factor", ("kgCO2e/kWh", "kgCO2e/GJ", "kgCO2e/t")),),
    ),
    MethodDefinition(
        "F09_DISTANCE",
        "车辆距离法",
        "F09",
        "排放量 = 车辆行驶里程 × 车型/燃料/负载因子",
        (_parameter("DISTANCE_FACTOR", "车辆距离排放因子", "emission_factor", ("kgCO2e/km",)),),
    ),
    MethodDefinition(
        "F09_TRANSPORT_ACTIVITY",
        "运输活动法",
        "F09",
        "排放量 = 吨公里或人公里 × 运输方式排放因子",
        (_parameter("TRANSPORT_FACTOR", "运输活动排放因子", "emission_factor", ("kgCO2e/tkm", "kgCO2e/pkm")),),
    ),
    MethodDefinition(
        "F10_VALUE_CHAIN",
        "价值链产品、服务和金融活动法",
        "F10",
        "排放量 = 物理量、支出或供应商特定结果 × 适用因子 × 归因比例",
        (
            _parameter("VALUE_CHAIN_FACTOR", "价值链排放因子", "emission_factor", ("kgCO2e/unit", "kgCO2e/CNY")),
            _parameter("ATTRIBUTION_FACTOR", "归因比例", "method_parameter", ("ratio",), required=False),
        ),
        executable=False,
    ),
    MethodDefinition(
        "F11_STOCK_CHANGE",
        "土地与清除碳库变化法",
        "F11",
        "排放或清除量 = 碳库变化 × 碳分数 × 44/12",
        (
            _parameter("STOCK_CHANGE", "碳库变化", "activity", ("tC", "kgC")),
            _parameter("CARBON_FRACTION", "碳分数", "method_parameter", ("ratio",)),
        ),
        executable=False,
    ),
)

METHOD_BY_CODE = {item.code: item for item in METHODS}


REPORTING_PROFILES = (
    {
        "code": "CORPORATE_ISO14064_GHGP",
        "name": "企业温室气体盘查（ISO 14064-1 / GHG Protocol）",
        "version": "2026.1",
        "standardCode": "ISO 14064-1:2018; GHG Protocol Corporate Standard",
    },
    {
        "code": "GBT32150_2025_GENERAL",
        "name": "工业企业温室气体排放核算通用视图",
        "version": "2026.1",
        "standardCode": "GB/T 32150-2025",
    },
)


def category_payload(category: CategoryDefinition) -> dict[str, Any]:
    from app.domain.ghg_inventory.domain.activity_fields import activity_field_payload
    from app.domain.ghg_inventory.domain.allocation import (
        CATEGORY_ALLOCATION_POLICY_BY_CODE,
        allocation_policy_payload,
    )

    return {
        "code": category.code,
        "name": category.name,
        "isoCategory": category.iso_category,
        "ghgScope": category.ghg_scope,
        "scope3Category": category.scope3_category,
        "sourceMechanism": category.source_mechanism,
        "valueChainPosition": category.value_chain_position,
        "defaultMethods": list(category.default_methods),
        "packageCode": category.package_code,
        "activityFields": activity_field_payload(category.package_code),
        "allocationPolicy": allocation_policy_payload(CATEGORY_ALLOCATION_POLICY_BY_CODE[category.code]),
    }


def method_payload(method: MethodDefinition) -> dict[str, Any]:
    return {
        "code": method.code,
        "name": method.name,
        "family": method.family,
        "formula": method.formula,
        "parameters": list(method.parameters),
        "executable": method.executable,
    }
