type EnergyQuantity = {
  energy_type_code: string
  original_unit?: string | null
}

type SummaryQuantity = {
  original_unit?: string | null
  groups?: { dimension: string; key: string | null }[]
}

/** A summary's MAX(unit) does not establish that its underlying units agree. */
export function energyQuantityMetric(amount: number | null | undefined, recordCount: number, records: EnergyQuantity[], summaryItems: SummaryQuantity[] = []) {
  const summaryUnits = new Set(summaryItems.map((item) => item.original_unit).filter(Boolean))
  const summaryEnergies = new Set(summaryItems.flatMap((item) => item.groups?.filter((group) => group.dimension === "energy_type" && group.key).map((group) => group.key) ?? []))
  if (summaryUnits.size > 1 || summaryEnergies.size > 1) return { value: "按能源品种查看", unit: undefined }
  const identities = new Set(records.map((row) => `${row.energy_type_code}|${row.original_unit ?? ""}`))
  if (identities.size > 1) return { value: "按能源品种查看", unit: undefined }
  if (!recordCount || records.length !== recordCount || !records[0]?.original_unit || amount == null || !Number.isFinite(amount)) {
    return { value: "—", unit: undefined }
  }
  return { value: amount.toLocaleString("zh-CN", { maximumFractionDigits: 3 }), unit: records[0].original_unit }
}
