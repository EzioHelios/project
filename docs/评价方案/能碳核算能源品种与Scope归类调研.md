# 能碳核算能源品种与 Scope 归类调研

更新时间：2026-06-11

## 目的

为能耗查询、能源消费量和强度计算、碳排放核算共用底层数据口径，先明确哪些活动数据属于能源消费，哪些属于碳排放但不应进入能耗查询，避免 Scope1、Scope2、能源品种和耗能工质串表。

本文用于指导后续 P0 数据模型和页面改造：

- Scope1 燃料活动数据需要进入能源消费事实层。
- Scope2 外购电力、外购热力/蒸汽/冷量需要进入能源消费事实层。
- 制冷剂泄漏、过程排放、废弃物处理等不应被误认为能源消费。
- 水、压缩空气等可以作为能源管理/耗能工质统计项，但不应默认作为 Scope2 碳核算能源品种。

## 参考资料

优先采用国家标准、主管部门指南；国际资料只用于解释 Scope2 的电力、蒸汽、热力、冷量边界。

| 来源 | 适用结论 | 链接 |
| --- | --- | --- |
| GB/T 32150-2015《工业企业温室气体排放核算和报告通则》 | 工业企业核算边界包括燃料燃烧排放、过程排放、购入的电力和热力产生的排放、输出的电力和热力产生的排放等；2015 版现行，2025 版即将全部代替 | https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=29DE620206A268D0E27B8739E332D70E |
| GB/T 32150-2025《工业企业温室气体排放核算和报告通则》 | 已发布、即将实施，应预留标准版本字段，后续切换到 2025 版 | https://std.samr.gov.cn/gb/search/gbDetailed?id=473EBB99D6C3455EE06397BE0A0ABB9A |
| GB/T 2589-2020《综合能耗计算通则》 | 综合能耗按能源实物量和折标准煤系数计算；折标系数单位可按 kgce/kg、kgce/m3、kgce/(kW·h)、kgce/MJ 等；用于能源管理和强度计算 | https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=53D1440B68E6D50B8BA0CCAB619B6B3E |
| 国家发展改革委《工业其他行业企业温室气体排放核算方法与报告指南（试行）》 | 工业其他行业可参考燃料燃烧、工业生产过程、购入电力/热力等排放源分类 | https://www.ndrc.gov.cn/xxgk/zcfb/tz/201511/W020190905506438889540.pdf |
| 生态环境部《企业温室气体排放核算与报告指南 发电设施》 | 发电设施指南明确化石燃料燃烧、购入使用电力等核算边界和数据质量控制要求，可作为电力相关 MRV 参考 | https://www.mee.gov.cn/xxgk2018/xxgk/xxgk06/202212/W020221221671986519778.pdf |
| GHG Protocol Scope 2 Guidance | Scope2 包括购入/取得并消耗的电力、热、蒸汽、冷量；用于补充解释蒸汽和冷量在国际口径下的位置 | https://ghgprotocol.org/scope-2-guidance |

## 归类规则

### 1. Scope1：直接排放中的能源燃烧

Scope1 能源消费来自企业边界内自有或受控设备的燃料燃烧。当前系统已有两类数据：

- 移动源燃烧：`Scope1MobileCombustion`
- 固定源燃烧：`Scope1StationaryCombustion`

应进入能耗查询和能源消费事实层的字段：

| 字段 | 说明 |
| --- | --- |
| `fuel_type` | 能源品种，例如柴油、汽油、天然气、煤、燃料油等 |
| `amount` | 原始活动量 |
| `unit` | 原始单位，例如 L、kg、t、m3 |
| `period_start/end` 或 `record_date` | 消费周期 |
| `facility_name` / `asset_name` | 设施或移动源 |
| `computed_co2e` | 碳核算结果，可同步展示但不是能耗原始量 |

注意：

- Scope1 制冷剂泄漏 `Scope1RefrigerantLeak` 是直接排放活动数据，但不是能源消费；不能放入能耗查询主表。
- 工业过程排放也是碳排放，不是能源消费；应在碳排放核算页展示。
- 氢、氨等作为燃料时可以进入能源消费事实层；但其直接 CO2 排放因子不能按含碳燃料默认处理，应由因子库和标准版本决定。

### 2. Scope2：购入能源产生的间接排放

Scope2 不是企业现场燃烧，而是购入能源在外部生产过程中产生的间接排放。

国家标准通用口径明确包括：

- 购入电力
- 购入热力

国际 Scope2 指南进一步明确包括：

- 购入电力
- 购入热力
- 购入蒸汽
- 购入冷量

系统设计建议：

| 能源品种 | 系统 Scope 映射 | 当前系统状态 | 改造建议 |
| --- | --- | --- | --- |
| 外购电力 | Scope2 | 已有 `Scope2ElectricityBill` 和 `Scope2MeterAggregate` | 保留，投影到统一能源消费事实层 |
| 外购热力 | Scope2 | 当前未见专用模型 | 新增外购热力/蒸汽/冷量记录模型 |
| 外购蒸汽 | Scope2，按热力类能源管理 | 当前未见专用模型 | 作为 `purchased_steam` 能源品种，不要放到 Scope1 燃料 |
| 外购冷量 | Scope2 或能源管理扩展项，取决于报告标准 | 当前未见专用模型 | 作为 `purchased_cooling` 独立品种，标准映射可配置 |

注意：

- 蒸汽如果是企业自有锅炉燃料燃烧产生，燃料消耗属于 Scope1；蒸汽本身是内部转换产物，不应再重复作为 Scope2。
- 蒸汽如果从外部购入，属于购入热力/蒸汽产生的间接排放，应按 Scope2 管理。
- 输出电力/热力是核算调整项，不是企业能源消费增加项，应单独建 `energy_export` 或核算调整记录，避免与购入量混淆。

### 3. 能源管理品类不等于碳核算 Scope

建设指南提到光、风、储、充、氢、电、气、冷、热、水、空调、空压等，是能源管理和监测品类，不应全部直接映射为碳核算 Scope。

| 品类 | 能源管理中是否可查 | 碳核算建议 |
| --- | --- | --- |
| 电 | 是 | 外购电力为 Scope2；自发自用光伏/风电需按能源平衡展示，碳核算按标准决定 |
| 气、煤、油类燃料 | 是 | 企业边界内燃烧为 Scope1 |
| 热、蒸汽、冷量 | 是 | 外购为 Scope2；自制时按消耗燃料或电力归类 |
| 光伏、风电 | 是 | 发电量用于能源结构和能流；不是天然的 Scope1/Scope2 排放源 |
| 储能 | 是 | 储能充放电是能源流转，不能重复计入能源消费总量 |
| 充电桩 | 是 | 多为电力用途或分配场景，消费归入电力，需防重复 |
| 水 | 是 | 能源管理/耗能工质或资源管理项；不默认作为 Scope2 排放源 |
| 空调、空压 | 是 | 通常是用能设备/系统，不是能源品种；其耗能归入电力、热力、冷量等 |

## 推荐数据模型口径

### 能源消费事实层

建议新增统一事实层，名称可为 `EnergyConsumptionFact`，也可以先做数据库视图。

核心字段：

| 字段 | 说明 |
| --- | --- |
| `source_record_type` | 原始表名，例如 `Scope1StationaryCombustion`、`Scope2MeterAggregate` |
| `source_record_id` | 原始记录 ID |
| `scope` | `scope1`、`scope2`、`energy_management_only` |
| `emission_category` | `stationary_combustion`、`mobile_combustion`、`purchased_electricity`、`purchased_heat`、`purchased_steam`、`purchased_cooling` |
| `energy_type_code` | 能源品种编码 |
| `energy_type_name` | 能源品种名称 |
| `original_amount` | 原始活动量 |
| `original_unit` | 原始单位 |
| `standard_amount` | 标准化活动量，例如 kWh、GJ、t、m3 |
| `standard_unit` | 标准单位 |
| `tce_amount` | 折标准煤量 |
| `co2e_amount` | 碳排放量 |
| `period_start` / `period_end` | 统计周期 |
| `area_id` / `area_name` | 区域 |
| `equipment_id` / `facility_name` | 设备或设施 |
| `status` | 草稿、待审核、已审核、驳回 |
| `standard_code` | 使用的标准，例如 `GB/T 32150-2015`、`GB/T 2589-2020` |
| `conversion_factor_id` | 折标或单位换算因子 |
| `emission_factor_id` | 碳排放因子 |

### 能源品种字典

建议新增 `EnergyType`，不要复用 `fuel_type` 或设备 `energy_type` 字段作为唯一口径。

字段建议：

| 字段 | 说明 |
| --- | --- |
| `code` | `diesel`、`natural_gas`、`purchased_electricity`、`purchased_steam` |
| `name` | 中文名称 |
| `category` | `fuel`、`purchased_energy`、`renewable_generation`、`energy_carrier`、`utility_working_medium`、`equipment_system` |
| `default_scope` | `scope1`、`scope2`、`energy_management_only`、`configurable` |
| `default_unit` | 默认原始单位 |
| `standard_unit` | 标准单位 |
| `is_combustion_fuel` | 是否燃料燃烧 |
| `is_purchased_energy` | 是否外购能源 |
| `is_counted_in_energy_total` | 是否默认进入综合能耗 |
| `is_counted_in_scope_emission` | 是否默认进入碳核算 |
| `status` | 启用/停用 |

### 能源单位换算字典

`EnergyType.standard_factor` 只表示“折标基准单位 -> 标准煤单位”的系数，例如 GB/T 2589-2020 中柴油、汽油的折标系数适用单位是质量单位，不能直接用于 `L`。

因此需要单独维护 `EnergyUnitConversion`：

| 字段 | 说明 |
| --- | --- |
| `energy_type_code` | 能源品种编码 |
| `from_unit` | 业务录入单位，例如 `L`、`t`、`MWh` |
| `to_unit` | 折标基准单位，例如 `kg`、`GJ`、`kWh` |
| `multiply_factor` | `from_unit -> to_unit` 的乘数 |
| `standard_code` | 单位换算来源或企业默认口径 |
| `conversion_factor_source` | 换算来源说明 |
| `is_default` | 是否默认口径 |
| `is_enabled` | 是否启用 |

计算链条应固定为：

```text
业务原始量 original_amount/original_unit
  -> 单位换算字典 EnergyUnitConversion
  -> 折标基准量 factor_amount/factor_unit
  -> 能源品种字典 EnergyType.standard_factor
  -> standard_amount(kgce) / tce_amount
```

注意：

- 柴油、汽油的 `L -> kg` 属于密度换算，不是 GB/T 2589 折标准煤系数。P0 可以使用企业默认密度参数，但必须标注来源，并允许后续按批次、供应商或实测密度覆盖。
- 外购蒸汽如果按 `GJ`、`MWh`、`Gcal` 等热量单位计费，可以用热量单位换算后折标；如果按 `t` 计费，不能直接用吨数折标，需要维护蒸汽焓值或供应商热量折算口径。
- 当缺少单位换算时，事实视图应保留原始量，但 `factor_amount`、`standard_amount`、`tce_amount` 应为空，不能硬算。

## P0 改造规则

1. 能耗查询不能只读 Scope2 电力表，需要把 Scope1 燃料和 Scope2 外购电力一起投影到能源消费事实层。
2. Scope2 外购热力/蒸汽/冷量要新增模型，不能塞进 `Scope2ElectricityBill`。
3. `Scope1RefrigerantLeak` 不进入能耗查询。
4. 水、空压、空调作为能源管理对象时，需要区分“品类/设备/耗能工质”，不要默认作为 Scope2 碳排能源。
5. 任何能源品种进入事实层时，必须带 `scope`、`emission_category`、原始单位、标准单位、折标依据和标准版本。
6. 自发电、自供热、储能、充电桩要按能流防重，不能既计购入电量又计充放电/分配量。

## 当前系统差距

| 项 | 当前状态 | 风险 |
| --- | --- | --- |
| Scope1 燃料 | 已有移动源、固定源数据表和页面 | 尚未投影到能源管理/能耗查询 |
| Scope2 电力 | 已有账单、电表聚合、月聚合重建 | 能耗查询页面使用 summary 预览，查询能力不足 |
| Scope2 热力/蒸汽/冷量 | 未见专用模型 | 外购热力/蒸汽容易缺项或被错误塞到电力/燃料 |
| 制冷剂 | 已有 Scope1 逸散排放 | 若进入能耗查询会造成能源口径错误 |
| 水/空压/空调 | 设备和测点可维护 | 未区分能源品种、耗能工质、设备系统，容易与碳核算 Scope 混淆 |
