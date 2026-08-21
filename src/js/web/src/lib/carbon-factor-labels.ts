const SCOPE_LABELS: Record<string, string> = {
  scope1: "范围1",
  scope2: "范围2",
  scope3: "范围3",
}

const CATEGORY_LABELS: Record<string, string> = {
  fuel: "燃料",
  electricity: "购电",
  refrigerant: "制冷剂",
  waste: "废弃物",
  transport: "运输",
}

const SUBCATEGORY_LABELS: Record<string, string> = {
  diesel: "柴油",
  gasoline: "汽油",
  lng: "LNG",
  cng: "CNG",
  natural_gas: "天然气",
  r22: "R22",
  r32: "R32",
  r134a: "R134a",
  r410a: "R410A",
  grid_electricity_national: "全国电力因子",
  grid_electricity_jiangsu: "江苏电力因子",
  waste_municipal_incineration: "生活垃圾焚烧",
  waste_municipal_landfill: "生活垃圾填埋",
  waste_packaging_recycle: "包装物回收",
  transport_light_truck: "轻型卡车",
  transport_heavy_truck: "重型卡车",
}

const UNIT_LABELS: Record<string, string> = {
  L: "升",
  kg: "千克",
  "m³": "立方米",
  t: "吨",
  kWh: "千瓦时",
  t·km: "吨公里",
  TJ: "太焦耳",
}

const SOURCE_SYSTEM_LABELS: Record<string, string> = {
  ncsc_ghg_efdb: "NCSC官方因子库",
  ncsc_gwp_ar5: "NCSC GWP(AR5)",
}

const CONVERSION_STATUS_LABELS: Record<string, string> = {
  candidate: "可转换",
  raw_only: "仅原始保留",
}

const IMPORT_METHOD_LABELS: Record<string, string> = {
  manual: "人工维护",
  direct: "直接导入",
  derived: "换算导入",
}

export function normalizeCarbonCode(value?: string | null) {
  return (value ?? "").trim().toLowerCase()
}

export function getScopeLabel(scope?: string | null) {
  const normalized = normalizeCarbonCode(scope)
  return SCOPE_LABELS[normalized] ?? scope ?? "未标记"
}

export function getCategoryLabel(category?: string | null) {
  const normalized = normalizeCarbonCode(category)
  return CATEGORY_LABELS[normalized] ?? category ?? "未标记"
}

export function getSubCategoryLabel(subCategory?: string | null) {
  const normalized = normalizeCarbonCode(subCategory)
  return SUBCATEGORY_LABELS[normalized] ?? subCategory ?? "未标记"
}

export function getActivityUnitLabel(unit?: string | null) {
  if (!unit) return "未标记"
  return UNIT_LABELS[unit] ?? unit
}

export function getSourceSystemLabel(sourceSystem?: string | null) {
  if (!sourceSystem) return "未标记"
  return SOURCE_SYSTEM_LABELS[sourceSystem] ?? sourceSystem
}

export function getConversionStatusLabel(status?: string | null) {
  if (!status) return "未标记"
  return CONVERSION_STATUS_LABELS[status] ?? status
}

export function getImportMethodLabel(status?: string | null) {
  if (!status) return "未标记"
  return IMPORT_METHOD_LABELS[status] ?? status
}
