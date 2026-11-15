import { useQuery, useQueryClient } from "@tanstack/react-query"

import { type Row, request, requestPage } from "@/components/platform/data-admin-pages"
import { useAuthStore } from "@/lib/auth"

export type EnergyRow = Row & {
  id?: number
  energy_type_code: string
  period_start: string
  period_end: string
  amount: number
  unit: string
  area_id?: string | null
  area_name?: string | null
  equipment_id?: number | null
  equipment_name?: string | null
  cost_cny?: number | null
  source_record_id?: string
  source_name?: string | null
  source_system?: string
  granularity?: string
  remark?: string | null
  row_number?: number
  status?: string
  message?: string
}
export type EnergyTotal = { energy_type_code: string; unit: string; amount: number; cost_cny: number | null; count: number }
export type EnergyPage = { items: EnergyRow[]; total: number; limit: number; offset: number; totals: EnergyTotal[] }
export type EnergyImportResult = {
  received_count: number
  imported_count: number
  skipped_count: number
  imported_ids: number[]
  records: EnergyRow[]
  errors: { row_number: number; message: string }[]
}
export type EnergyFilters = { keyword: string; month: string; energy_type_code: string; area_id: string; equipment_id: string }
export const emptyEnergyFilters: EnergyFilters = { keyword: "", month: "", energy_type_code: "", area_id: "", equipment_id: "" }
export const energyEndpoint = "/api/energy/interval-facts"

export async function allOptions(endpoint: string): Promise<Row[]> {
  const rows: Row[] = []
  let offset = 0
  for (;;) {
    const page = await requestPage<Row>(endpoint, { limit: 500, offset })
    rows.push(...page.items)
    offset += page.items.length
    if (!page.items.length || offset >= page.total) return rows
  }
}
export function flattenAreas(rows: Row[]): Row[] {
  return rows.flatMap((row) => [row, ...flattenAreas(Array.isArray(row.children) ? (row.children as Row[]) : [])])
}
export function energyUnits(code: string, types: Row[], conversions: Row[]) {
  return [
    ...new Set(
      [types.find((row) => row.code === code)?.original_unit, ...conversions.filter((row) => row.energy_type_code === code).map((row) => row.from_unit)]
        .filter(Boolean)
        .map(String),
    ),
  ]
}
export function monthRange(month: string) {
  const [year, number] = month.split("-").map(Number)
  const last = new Date(year, number, 0).getDate()
  return { period_start: `${month}-01T00:00:00`, period_end: `${month}-${last}T23:59:59` }
}
export function energyQueryParams(filters: EnergyFilters, ids: number[] | null, page: number) {
  const params = new URLSearchParams({ limit: "20", offset: String(page * 20) })
  for (const [key, value] of Object.entries(filters)) if (value && key !== "month") params.set(key, value)
  if (filters.month) for (const [key, value] of Object.entries(monthRange(filters.month))) params.set(key, value)
  if (ids !== null) params.set("ids", ids.join(","))
  return params
}
export function useEnergyEntry(filters: EnergyFilters, ids: number[] | null, page: number) {
  const teamId = useAuthStore((state) => state.currentTeam?.id)
  const qc = useQueryClient()
  const references = useQuery({
    queryKey: ["energy-entry-references", teamId],
    queryFn: async () => {
      const [types, areas, devices, conversions] = await Promise.all([
        allOptions("/api/energy/types"),
        allOptions("/api/master-data/areas/tree"),
        allOptions("/api/master-data/devices"),
        allOptions("/api/energy/unit-conversions"),
      ])
      return { types, areas: flattenAreas(areas), devices, conversions }
    },
  })
  const list = useQuery({
    queryKey: ["data", "energy-interval-facts", teamId, filters, ids, page],
    queryFn: async () => {
      const response = await fetch(`${energyEndpoint}?${energyQueryParams(filters, ids, page)}`)
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail || "能源数据读取失败")
      return body as EnergyPage
    },
  })
  const refresh = async () => {
    await Promise.all([qc.invalidateQueries({ queryKey: ["data", "energy-interval-facts"] }), qc.invalidateQueries({ queryKey: ["energy"] })])
  }
  return { references, list, refresh, teamId }
}
export async function importEnergy(rows: Record<string, string>[], sourceName: string, preview: boolean) {
  return (
    await request<EnergyImportResult>("/api/energy/imports/datasets", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ dataset: "energy_interval_facts", rows, source_name: sourceName, preview }),
    })
  ).data
}
