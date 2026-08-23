import { type OperationalStatus, StatusBadge } from "@/components/admin-ui"

export const reductionTrackLabels: Record<string, string> = {
  internal_action: "企业内部措施",
  iso_14064_2: "ISO 14064-2 项目",
  ccer_project: "CCER 开发项目",
}

export const reductionCategoryLabels: Record<string, string> = {
  energy_efficiency: "节能改造",
  renewable_energy: "可再生能源与自发自用",
  green_power: "绿电采购",
  fuel_switching: "燃料替代",
  process_material: "工艺与材料替代",
  refrigerant_industrial_gas: "制冷剂与工业气体控制",
  logistics: "物流运输优化",
  waste_resource: "废弃物资源化",
  forestry_removal: "林业及其他清除项目",
  operational_optimization: "运营管理优化",
}

export const reductionStatusLabels: Record<string, string> = {
  draft: "草稿",
  screening: "适用性筛选",
  approved: "已立项",
  baseline_locked: "基准线已锁定",
  implementing: "实施中",
  monitoring: "监测中",
  calculated: "已计算",
  internally_reviewed: "内部复核",
  verified: "已核查",
  registered: "已登记",
  issued: "已签发",
  archived: "已归档",
}

const badgeStatus: Record<string, OperationalStatus> = {
  draft: "draft",
  screening: "pending",
  approved: "approved",
  baseline_locked: "locked",
  implementing: "in_progress",
  monitoring: "in_progress",
  calculated: "in_progress",
  internally_reviewed: "approved",
  verified: "approved",
  registered: "approved",
  issued: "approved",
  archived: "archived",
}

export function ReductionStatusBadge({ status }: { status: string }) {
  return <StatusBadge status={badgeStatus[status] ?? "inactive"} label={reductionStatusLabels[status] ?? status} />
}

export function formatReductionNumber(value: number | null | undefined, digits = 1) {
  if (value == null || Number.isNaN(value)) return "-"
  return value.toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

export function asNumber(value: unknown) {
  const number = Number(value ?? 0)
  return Number.isFinite(number) ? number : 0
}

export function asText(value: unknown) {
  return value == null ? "" : String(value)
}
