import type { EnergyRow, EnergyTotal } from "@/hooks/use-energy-entry"

export const energyCsvFields: Record<string, string> = {
  能源种类: "energy_type_name",
  能源种类编码: "energy_type_code",
  区域: "area_name",
  区域名称: "area_name",
  设备: "equipment_name",
  设备名称: "equipment_name",
  月份: "month",
  开始日期: "period_start",
  开始时间: "period_start",
  结束日期: "period_end",
  结束时间: "period_end",
  能源用量: "amount",
  用量: "amount",
  单位: "unit",
  费用: "cost_cny",
  备注: "remark",
  记录编码: "source_record_id",
  设备编码: "equipment_code",
  区域ID: "area_id",
  数据来源: "source_system",
  时间粒度: "granularity",
  电价时段: "tariff_segment_type",
  数据质量: "data_quality",
}
export function parseEnergyCsv(text: string): Record<string, string>[] {
  const lines: string[][] = []
  let row: string[] = [],
    cell = "",
    quoted = false
  const source = text.replace(/^\uFEFF/, "")
  for (let i = 0; i < source.length; i++) {
    const ch = source[i]
    if (ch === '"' && quoted && source[i + 1] === '"') {
      cell += '"'
      i++
    } else if (ch === '"') quoted = !quoted
    else if (ch === "," && !quoted) {
      row.push(cell.trim())
      cell = ""
    } else if (ch === "\n" && !quoted) {
      row.push(cell.trim())
      if (row.some(Boolean)) lines.push(row)
      row = []
      cell = ""
    } else cell += ch
  }
  if (quoted) throw new Error("CSV 引号未闭合，请检查文件")
  row.push(cell.trim())
  if (row.some(Boolean)) lines.push(row)
  if (lines.length < 2) throw new Error("文件中没有可导入的数据")
  if (lines.length > 1001) throw new Error("单次最多导入 1000 行")
  const headers = lines[0].map((name) => energyCsvFields[name] ?? name)
  const recognized = new Set([...Object.values(energyCsvFields), "equipment_id"])
  if (!headers.includes("amount")) throw new Error("文件缺少“能源用量”列")
  return lines.slice(1).map((values, index) => {
    if (values.length !== headers.length) throw new Error(`第 ${index + 2} 行列数与表头不一致`)
    return Object.fromEntries(headers.flatMap((key, column) => (recognized.has(key) ? [[key, values[column]]] : [])))
  })
}
export function summarizeEnergy(rows: EnergyRow[]): EnergyTotal[] {
  const groups = new Map<string, EnergyTotal>()
  for (const row of rows) {
    const key = `${row.energy_type_code}|${row.unit}`
    const group = groups.get(key) ?? { energy_type_code: row.energy_type_code, unit: row.unit, amount: 0, cost_cny: null, count: 0 }
    group.amount += Number(row.amount)
    if (row.cost_cny != null) group.cost_cny = (group.cost_cny ?? 0) + Number(row.cost_cny)
    group.count++
    groups.set(key, group)
  }
  return [...groups.values()]
}
export const numberLabel = (value: unknown) => (value == null || value === "" ? "—" : Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 3 }))
export const dateLabel = (value: unknown) => String(value ?? "").slice(0, 10) || "—"
export function sourceLabel(value: unknown) {
  return (
    (
      {
        woheng_enterprise_entry_v1: "企业月结台账",
        demo_ghg_activity_monthly: "历史非电月度台账",
        demo_ghg_activity_daily: "历史非电日度台账",
        demo_showcase: "历史能源台账",
        demo_generator: "历史能源台账",
        scope2_meter_monthly: "表计月度汇总",
        meter_monthly: "表计月度汇总",
        "woheng-material-hour": "物资作业用能",
        "woheng-showcase": "企业经营台账",
        mqtt_szscada: "自动采集",
        enterprise: "企业填报",
        manual_entry: "手工录入",
        manual_csv: "文件导入",
        supplier_ledger: "供应商台账",
        meter_projection: "自动采集",
        meter_interval: "表计采集",
        telemetry: "自动采集",
      } as Record<string, string>
    )[String(value)] ?? "其他来源"
  )
}
export function downloadCsv(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([`\uFEFF${text}`], { type: "text/csv;charset=utf-8" }))
  const link = document.createElement("a")
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

export const moneyLabel = (value: unknown) => (value == null || value === "" ? "—" : Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
export function periodLabel(row: EnergyRow) {
  const start = row.period_start ?? ""
  const end = row.period_end ?? ""
  if (row.granularity === "month") return start.slice(0, 7) === end.slice(0, 7) ? start.slice(0, 7) : `${start.slice(0, 7)} 至 ${end.slice(0, 7)}`
  if (row.granularity === "year") return start.slice(0, 4) === end.slice(0, 4) ? `${start.slice(0, 4)} 年` : `${start.slice(0, 4)} 至 ${end.slice(0, 4)} 年`
  if (row.granularity === "hour")
    return `${start.slice(0, 10)} ${start.slice(11, 16)}—${start.slice(0, 10) === end.slice(0, 10) ? end.slice(11, 16) : `${end.slice(0, 10)} ${end.slice(11, 16)}`}`
  return start.slice(0, 10) === end.slice(0, 10) ? dateLabel(start) : `${dateLabel(start)} 至 ${dateLabel(end)}`
}
export function granularityLabel(value: unknown) {
  return ({ hour: "小时", day: "日", month: "月", year: "年" } as Record<string, string>)[String(value)] ?? "其他"
}
