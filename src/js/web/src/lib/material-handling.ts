import { useAuthStore } from "@/lib/auth"

export type HandlingOption = {
  id: number
  name?: string
  code?: string
  study_name?: string
  study_id?: number
  stage_name?: string
  source?: string
  sub_category?: string
  factor_value?: number
  default_unit?: string
}
export type HandlingOptions = {
  can_manage: boolean
  can_calculate: boolean
  devices: HandlingOption[]
  materials: HandlingOption[]
  studies: HandlingOption[]
  stages: HandlingOption[]
  factors: HandlingOption[]
  sources: { equipment_id: number; source_system: string }[]
}
export type HandlingRow = {
  input_snapshot?: { command?: { equipment_id: number; energy_source_system: string; period_start: string; period_end: string; factor_id: number; applicability_note: string } }
  id: number
  operation_no: string
  operation_status: string
  operation_type: string
  equipment_id: number
  equipment_type: string
  equipment_name: string
  area_name: string
  material_id: number
  material_name: string
  batch_no: string
  quantity: number
  unit: string
  weight_kg: number | null
  remark: string | null
  duration_minutes: number
  source_system: string
  data_quality: string
  active_intervals: { start: string; end: string }[] | null
  period_start: string
  period_end: string
  data_status: string
  allocated_energy_kwh: number
  allocated_co2e_kg: number
  total_energy_kwh: number
  unallocated_energy_kwh: number
  status: string
  product_footprint_item_id: number | null
}

export async function handlingRequest<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const team = useAuthStore.getState().currentTeam?.id
  if (!team) throw new Error("请先选择租户")
  const response = await fetch(path, {
    method,
    credentials: "include",
    headers: { "X-Team-Id": team, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const value = await response.json()
  if (!response.ok) throw new Error(value.detail || value.msg || "请求失败")
  return value.data ?? value
}

export const equipmentKinds = { forklift: "叉车", rotary_crane: "旋转吊", bridge_crane: "行吊", stacker: "堆垛机" }
export const handlingStates: Record<string, string> = {
  draft: "待确认",
  confirmed: "已确认",
  ready: "有效",
  completed: "已计算",
  stale: "待重新计算",
  simulated: "模拟",
  estimated: "估算",
  reported: "人工填报",
  vision_confirmed: "视觉观测",
}
export function localTime(value: string) {
  const d = new Date(value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  return Number.isNaN(d.valueOf()) ? "" : new Date(d.valueOf() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
