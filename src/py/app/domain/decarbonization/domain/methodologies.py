"""Versioned, executable methodology adapters with no dynamic expression evaluation."""

from __future__ import annotations

# ruff: noqa: EM101, EM102, RUF001, TRY003 - local domain guards and formal notation are intentional.
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class MethodologyInputError(ValueError):
    """Raised when method input is incomplete or outside a physical boundary."""


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    code: str
    name: str
    unit: str
    required: bool = True
    minimum: Decimal | None = Decimal(0)


@dataclass(frozen=True, slots=True)
class MethodologyDefinition:
    code: str
    version: str
    name: str
    sector: str
    published_on: str
    source_url: str
    executable: bool
    adapter_code: str | None = None
    parameters: tuple[ParameterSpec, ...] = ()
    applicability_checks: tuple[tuple[str, str], ...] = ()
    monitoring_items: tuple[str, ...] = ()
    evidence_items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CalculationResult:
    baseline_tco2e: Decimal
    project_tco2e: Decimal
    leakage_tco2e: Decimal
    deduction_tco2e: Decimal
    reduction_tco2e: Decimal
    components: dict[str, Any]
    diagnostics: tuple[dict[str, str], ...]


MEE = "https://www.mee.gov.cn"


def _p(code: str, name: str, unit: str, *, required: bool = True, minimum: str | None = "0") -> ParameterSpec:
    return ParameterSpec(code, name, unit, required, Decimal(minimum) if minimum is not None else None)


EXECUTABLE: dict[str, MethodologyDefinition] = {
    "CCER-01-001-V01": MethodologyDefinition(
        "CCER-01-001-V01",
        "V01",
        "并网光热发电",
        "能源产业",
        "2023-10-24",
        f"{MEE}/xxgk2018/xxgk/xxgk06/202310/W020231024631536565589.pdf",
        True,
        "grid_solar_thermal_v01",
        (
            _p("exported_electricity_mwh", "上网电量", "MWh"),
            _p("imported_electricity_mwh", "下网电量", "MWh"),
            _p("grid_om_factor", "电量边际排放因子", "tCO2/MWh"),
            _p("grid_bm_factor", "容量边际排放因子", "tCO2/MWh"),
            _p("om_weight", "电量边际权重", "ratio", minimum="0"),
            _p("fuel_emissions_tco2", "防凝化石燃料排放", "tCO2", required=False),
        ),
        (("independent_metering", "光热发电部分上网、下网电量能够单独计量"),),
        ("上网电量", "下网电量", "化石燃料消耗", "低位发热量", "含碳量", "氧化率"),
        ("并网证明", "电量计量记录", "燃料台账", "计量器具检定记录"),
    ),
    "CCER-01-004-V01": MethodologyDefinition(
        "CCER-01-004-V01",
        "V01",
        "可再生能源电解水制氢",
        "能源产业",
        "2025-12-26",
        f"{MEE}/xxgk2018/xxgk/xxgk06/202512/W020251226497535481024.pdf",
        True,
        "renewable_hydrogen_v01",
        (
            _p("sold_hydrogen_t", "售出纯氢质量", "tH2"),
            _p("renewable_power_mwh", "自有可再生能源电量", "MWh"),
            _p("grid_import_mwh", "下网电量", "MWh"),
            _p("baseline_hydrogen_factor", "基准线制氢排放因子", "tCO2/tH2"),
        ),
        (
            ("new_build", "项目为新建项目而非既有项目改造或扩建"),
            ("same_legal_entity", "制氢项目与自有可再生能源电厂属于同一法人"),
            ("self_consumption", "可再生能源电力用于项目自发自用"),
            ("platform_connected", "监测数据具备国家碳市场管理平台联网条件"),
        ),
        ("可再生能源电量", "下网电量", "售出氢气质量或体积", "氢气纯度", "温度", "压力"),
        ("项目核准文件", "电源权属证明", "氢气销售记录", "计量器具检定记录"),
    ),
    "CCER-06-001-V01": MethodologyDefinition(
        "CCER-06-001-V01",
        "V01",
        "既有公共建筑围护结构与供暖通风空调系统能效提升",
        "建筑业和能源需求",
        "2025-12-23",
        f"{MEE}/xxgk2018/xxgk/xxgk06/202512/W020251223502007241623.pdf",
        True,
        "existing_public_building_v01",
        (
            _p("baseline_emissions_tco2e", "24个月基准期折算排放", "tCO2e"),
            _p("project_emissions_tco2e", "项目期能源排放", "tCO2e"),
            _p("refrigerant_emissions_tco2e", "制冷剂泄漏排放", "tCO2e", required=False),
            _p("minimum_monthly_use_hours", "月最低使用时间", "h"),
            _p("baseline_hdd", "基准期采暖度日数", "℃·d", required=False),
            _p("project_hdd", "项目期采暖度日数", "℃·d", required=False),
            _p("baseline_cdd", "基准期供冷度日数", "℃·d", required=False),
            _p("project_cdd", "项目期供冷度日数", "℃·d", required=False),
        ),
        (
            ("existing_public_building", "项目对象为功能稳定的既有公共建筑"),
            ("stable_24_month_baseline", "改造前具备连续稳定运行24个月数据"),
            ("same_building_function", "改造前后建筑使用功能一致"),
        ),
        ("电力", "热力", "冷量", "化石燃料", "制冷剂泄漏", "建筑使用时间", "HDD", "CDD"),
        ("节能设计符合性文件", "改造合同", "能源账单", "运行记录", "气象记录"),
    ),
    "CCER-14-001-V01": MethodologyDefinition(
        "CCER-14-001-V01",
        "V01",
        "造林碳汇",
        "林业和其他土地利用",
        "2023-10-24",
        f"{MEE}/xxgk2018/xxgk/xxgk06/202310/W020231024631535201815.pdf",
        True,
        "afforestation_v01",
        (
            _p("biomass_change_tco2e", "生物质碳储量变化", "tCO2e"),
            _p("dead_organic_matter_change_tco2e", "死有机质碳储量变化", "tCO2e", required=False),
            _p("soil_carbon_change_tco2e", "土壤有机碳储量变化", "tCO2e", required=False),
            _p("fire_emissions_tco2e", "火烧温室气体排放", "tCO2e", required=False),
            _p("pre_existing_biomass_change_tco2e", "原有植被碳储量变化", "tCO2e", required=False),
            _p("risk_deduction_tco2e", "非持久性风险扣减", "tCO2e", required=False),
        ),
        (
            ("non_forest_three_years", "项目开始前至少3年为符合方法学要求的非林地"),
            ("clear_tenure", "土地及林木权属清晰且覆盖计入期"),
            ("not_commercial_or_landscaping", "不属于经济林、道路或城镇工矿区绿化"),
        ),
        ("地块边界", "碳层", "样地", "树种", "胸径/株高", "土壤有机碳", "火灾与采伐"),
        ("权属文件", "造林作业设计", "遥感或GIS边界", "样地记录", "灾害记录"),
    ),
    "CCER-14-002-V01": MethodologyDefinition(
        "CCER-14-002-V01",
        "V01",
        "红树林营造",
        "林业和其他土地利用",
        "2023-10-24",
        f"{MEE}/xxgk2018/xxgk/xxgk06/202310/W020231024631537753613.pdf",
        True,
        "mangrove_v01",
        (
            _p("biomass_carbon_change_tc", "生物质碳储量变化", "tC"),
            _p("soil_carbon_change_tc", "土壤有机碳储量变化", "tC", required=False),
            _p("soil_ch4_emissions_tco2e", "土壤CH4排放", "tCO2e", required=False),
            _p("soil_n2o_emissions_tco2e", "土壤N2O排放", "tCO2e", required=False),
            _p("risk_deduction_tco2e", "非持久性风险扣减", "tCO2e", required=False),
        ),
        (
            ("eligible_habitat", "地块为适宜或修复后适宜的无植被潮滩或退养养殖塘"),
            ("minimum_area", "人工种植红树林连续面积不低于400平方米"),
            ("clear_tenure", "海域或土地使用权及减排量归属清晰"),
        ),
        ("地块边界", "种植面积", "碳层", "样地", "树种与测树因子", "土壤碳", "CH4", "N2O"),
        ("海域或土地权属", "种植设计", "GIS边界", "样地记录", "生态影响记录"),
    ),
}


_CATALOG_ROWS = (
    ("CCER-01-001-V01", "并网光热发电", "能源产业", "2023-10-24"),
    ("CCER-01-002-V01", "并网海上风力发电", "能源产业", "2023-10-24"),
    ("CCER-01-003-V01", "中深层地热能井下换热供暖技术应用工程", "能源产业", "2025-12-26"),
    ("CCER-01-004-V01", "可再生能源电解水制氢", "能源产业", "2025-12-26"),
    ("CCER-06-001-V01", "既有公共建筑围护结构与供暖通风空调系统能效提升", "建筑业和能源需求", "2025-12-23"),
    ("CCER-07-001-V01", "公路隧道照明系统节能", "交通运输", "2025-01-03"),
    ("CCER-10-001-V01", "甲烷体积浓度低于8%的煤矿低浓度瓦斯和风排瓦斯利用", "甲烷减排", "2025-01-03"),
    ("CCER-10-002-V01", "海上油田伴生气回收利用", "甲烷减排", "2025-11-21"),
    ("CCER-10-003-V01", "陆上气田试气放喷气回收利用", "甲烷减排", "2025-11-21"),
    ("CCER-10-004-V01", "陆上油田低气量伴生气回收利用", "甲烷减排", "2025-11-21"),
    ("CCER-11-001-V01", "电气设备六氟化硫回收和净化", "工业气体", "2025-12-26"),
    ("CCER-14-001-V01", "造林碳汇", "林业和其他土地利用", "2023-10-24"),
    ("CCER-14-002-V01", "红树林营造", "林业和其他土地利用", "2023-10-24"),
    ("CCER-14-003-V01", "滨海盐沼植被修复", "林业和其他土地利用", "2025-12-03"),
    ("CCER-14-004-V01", "海草床植被修复", "林业和其他土地利用", "2025-12-03"),
    ("CCER-14-005-V01", "淤地坝碳汇", "林业和其他土地利用", "2025-12-02"),
    ("CCER-15-001-V01", "规模化猪场粪污沼气回收利用工程", "农业", "2025-12-17"),
    ("CCER-15-002-V01", "农业废弃物集中处理工程", "农业", "2025-12-17"),
)


METHODOLOGY_CATALOG: tuple[MethodologyDefinition, ...] = tuple(
    EXECUTABLE.get(code)
    or MethodologyDefinition(
        code=code,
        version="V01",
        name=name,
        sector=sector,
        published_on=published_on,
        source_url="https://ccer.cets.org.cn/",
        executable=False,
    )
    for code, name, sector, published_on in _CATALOG_ROWS
)


def _decimal(inputs: dict[str, Any], code: str, *, default: str | None = None) -> Decimal:
    raw = inputs.get(code, default)
    if raw is None or raw == "":
        raise MethodologyInputError(f"Missing required methodology parameter: {code}.")
    try:
        value = Decimal(str(raw))
    except Exception as exc:
        raise MethodologyInputError(f"Methodology parameter {code} is not numeric.") from exc
    if not value.is_finite():
        raise MethodologyInputError(f"Methodology parameter {code} must be finite.")
    return value


def _optional(inputs: dict[str, Any], code: str) -> Decimal:
    return _decimal(inputs, code, default="0")


def _result(
    baseline: Decimal,
    project: Decimal,
    leakage: Decimal = Decimal(0),
    deduction: Decimal = Decimal(0),
    *,
    components: dict[str, Any],
    diagnostics: tuple[dict[str, str], ...] = (),
) -> CalculationResult:
    reduction = max(Decimal(0), baseline - project - leakage - deduction)
    quantum = Decimal("0.001")
    return CalculationResult(
        baseline.quantize(quantum, rounding=ROUND_HALF_UP),
        project.quantize(quantum, rounding=ROUND_HALF_UP),
        leakage.quantize(quantum, rounding=ROUND_HALF_UP),
        deduction.quantize(quantum, rounding=ROUND_HALF_UP),
        reduction.quantize(quantum, rounding=ROUND_HALF_UP),
        components,
        diagnostics,
    )


def _solar_thermal(inputs: dict[str, Any]) -> CalculationResult:
    exported = _decimal(inputs, "exported_electricity_mwh")
    imported = _decimal(inputs, "imported_electricity_mwh")
    net = max(Decimal(0), exported - imported)
    om_weight = _decimal(inputs, "om_weight")
    if not Decimal(0) <= om_weight <= Decimal(1):
        raise MethodologyInputError("om_weight must be between 0 and 1.")
    bm_weight = Decimal(1) - om_weight
    combined_margin = _decimal(inputs, "grid_om_factor") * om_weight + _decimal(inputs, "grid_bm_factor") * bm_weight
    baseline = net * combined_margin
    project = _optional(inputs, "fuel_emissions_tco2")
    return _result(
        baseline,
        project,
        components={
            "netElectricityMwh": float(net),
            "combinedMarginFactor": float(combined_margin),
            "formula": "BE=EG_net×EF_CM; ER=BE-PE",
        },
    )


def _hydrogen(inputs: dict[str, Any]) -> CalculationResult:
    sold = _decimal(inputs, "sold_hydrogen_t")
    renewable = _decimal(inputs, "renewable_power_mwh")
    grid = _decimal(inputs, "grid_import_mwh")
    denominator = renewable + grid
    if denominator <= 0:
        raise MethodologyInputError("Renewable power plus grid import must be greater than zero.")
    eligible_hydrogen = sold * renewable / denominator
    factor = _decimal(inputs, "baseline_hydrogen_factor")
    baseline = eligible_hydrogen * factor
    return _result(
        baseline,
        Decimal(0),
        components={
            "eligibleRenewableHydrogenT": float(eligible_hydrogen),
            "renewablePowerShare": float(renewable / denominator),
            "formula": "M_H2,R=M_H2,PJ×E_plant/(EC_grid+E_plant); ER=M_H2,R×EF_H2,BL",
        },
    )


def _building(inputs: dict[str, Any]) -> CalculationResult:
    baseline = _decimal(inputs, "baseline_emissions_tco2e")
    project = _decimal(inputs, "project_emissions_tco2e") + _optional(inputs, "refrigerant_emissions_tco2e")
    use_hours = _decimal(inputs, "minimum_monthly_use_hours")
    diagnostics: list[dict[str, str]] = []
    eligible = use_hours >= Decimal(160)
    for baseline_code, project_code, label in (
        ("baseline_hdd", "project_hdd", "HDD"),
        ("baseline_cdd", "project_cdd", "CDD"),
    ):
        base = _optional(inputs, baseline_code)
        current = _optional(inputs, project_code)
        if base > 0 and abs(current - base) > base * Decimal("0.20"):
            eligible = False
            diagnostics.append({"code": f"{label.lower()}_deviation", "level": "blocking", "message": f"{label}变化超过20%，当年减排量计为0"})
    if not eligible:
        diagnostics.append({"code": "annual_reduction_zero", "level": "blocking", "message": "方法学适用门槛未满足，减排量按0处理"})
        return _result(Decimal(0), Decimal(0), components={"formula": "ER=0 (eligibility gate)"}, diagnostics=tuple(diagnostics))
    return _result(
        baseline,
        project,
        components={"minimumMonthlyUseHours": float(use_hours), "formula": "ER=BE-PE-PER"},
        diagnostics=tuple(diagnostics),
    )


def _afforestation(inputs: dict[str, Any]) -> CalculationResult:
    project_removal = (
        _decimal(inputs, "biomass_change_tco2e")
        + _optional(inputs, "dead_organic_matter_change_tco2e")
        + _optional(inputs, "soil_carbon_change_tco2e")
    )
    project_emissions = _optional(inputs, "fire_emissions_tco2e") + _optional(inputs, "pre_existing_biomass_change_tco2e")
    risk = _optional(inputs, "risk_deduction_tco2e")
    return _result(
        project_removal,
        project_emissions,
        deduction=risk,
        components={"baselineRemovalTco2e": 0, "formula": "ER=ΔC_biomass+ΔC_DOM+ΔSOC-GHG_fire-ΔC_pre-existing-D"},
    )


def _mangrove(inputs: dict[str, Any]) -> CalculationResult:
    carbon_change = _decimal(inputs, "biomass_carbon_change_tc") + _optional(inputs, "soil_carbon_change_tc")
    removal = carbon_change * Decimal(44) / Decimal(12)
    project_emissions = _optional(inputs, "soil_ch4_emissions_tco2e") + _optional(inputs, "soil_n2o_emissions_tco2e")
    risk = _optional(inputs, "risk_deduction_tco2e")
    return _result(
        removal,
        project_emissions,
        deduction=risk,
        components={"carbonStockChangeTc": float(carbon_change), "formula": "ER=(ΔC_biomass+ΔSOC)×44/12-GHG_CH4-GHG_N2O-D"},
    )


_ADAPTERS: dict[str, Callable[[dict[str, Any]], CalculationResult]] = {
    "CCER-01-001-V01": _solar_thermal,
    "CCER-01-004-V01": _hydrogen,
    "CCER-06-001-V01": _building,
    "CCER-14-001-V01": _afforestation,
    "CCER-14-002-V01": _mangrove,
}


def screen_applicability(code: str, answers: dict[str, Any]) -> dict[str, Any]:
    definition = EXECUTABLE.get(code)
    if definition is None:
        return {"status": "manual_review", "checks": [], "blockingReasons": ["该方法学尚未配置可执行适用性规则"]}
    checks = [
        {"code": rule_code, "label": label, "passed": answers.get(rule_code) is True}
        for rule_code, label in definition.applicability_checks
    ]
    blocking = [check["label"] for check in checks if not check["passed"]]
    return {"status": "applicable" if not blocking else "not_applicable", "checks": checks, "blockingReasons": blocking}


def calculate_reduction(code: str, inputs: dict[str, Any]) -> CalculationResult:
    definition = EXECUTABLE.get(code)
    adapter = _ADAPTERS.get(code)
    if definition is None or adapter is None:
        raise MethodologyInputError("The selected methodology is reference-only and cannot run a formal calculation.")
    for parameter in definition.parameters:
        if parameter.required and inputs.get(parameter.code) in {None, ""}:
            raise MethodologyInputError(f"Missing required methodology parameter: {parameter.code}.")
        if (
            inputs.get(parameter.code) not in {None, ""}
            and parameter.minimum is not None
            and _decimal(inputs, parameter.code) < parameter.minimum
        ):
            raise MethodologyInputError(f"Methodology parameter {parameter.code} is below its physical boundary.")
    return adapter(inputs)


def methodology_payload(definition: MethodologyDefinition) -> dict[str, Any]:
    return {
        "code": definition.code,
        "version": definition.version,
        "name": definition.name,
        "sector": definition.sector,
        "publishedOn": definition.published_on,
        "sourceUrl": definition.source_url,
        "status": "published",
        "executable": definition.executable,
        "adapterCode": definition.adapter_code,
        "parameters": [
            {
                "code": item.code,
                "name": item.name,
                "unit": item.unit,
                "required": item.required,
                "minimum": float(item.minimum) if item.minimum is not None else None,
            }
            for item in definition.parameters
        ],
        "applicabilityChecks": [{"code": code, "label": label} for code, label in definition.applicability_checks],
        "monitoringItems": list(definition.monitoring_items),
        "evidenceItems": list(definition.evidence_items),
    }
