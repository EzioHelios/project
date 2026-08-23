import { RefreshCw } from "lucide-react"
import type * as React from "react"
import { z } from "zod"

import { AdminFilterBar, type AdminFilterField, StatusBadge } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { GhgCalculationRunList } from "@/lib/api/hooks/ghg-inventory"
import type { GhgAreaOptionResponse, GhgEquipmentOptionResponse } from "@/lib/generated/api"

export type Scope2Method = "location" | "market"

export const organizationCarbonSearchSchema = z.object({
  run: z.string().optional(),
  scope2: z.enum(["location", "market"]).catch("location"),
  from: z.string().optional(),
  to: z.string().optional(),
  grain: z.enum(["month", "quarter", "year"]).catch("month"),
  scope: z.string().optional(),
  iso: z.string().optional(),
  source: z.string().optional(),
  mechanism: z.string().optional(),
  areaId: z.coerce.number().int().positive().optional(),
  equipmentId: z.coerce.number().int().positive().optional(),
  quality: z.string().optional(),
  keyword: z.string().optional(),
  page: z.coerce.number().int().positive().catch(1),
  pageSize: z.coerce
    .number()
    .catch(25)
    .transform((value) => (value === 50 || value === 100 ? value : 25)),
  sortBy: z.string().catch("period_start"),
  sortOrder: z.enum(["asc", "desc"]).catch("desc"),
})

export type OrganizationCarbonSearch = z.infer<typeof organizationCarbonSearchSchema>

export function toAnalyticsFilters(search: OrganizationCarbonSearch, runCode?: string) {
  return {
    runCode: search.run ?? runCode,
    scope2Method: search.scope2,
    dateFrom: search.from,
    dateTo: search.to,
    ghgScope: search.scope,
    isoCategoryCode: search.iso,
    sourceCode: search.source,
    sourceMechanism: search.mechanism,
    areaId: search.areaId,
    equipmentId: search.equipmentId,
    qualityStatus: search.quality,
    keyword: search.keyword,
  }
}

export function equipmentOptionsForArea(areas: GhgAreaOptionResponse[], equipment: GhgEquipmentOptionResponse[], areaId?: number) {
  if (!areaId) return equipment
  const includedAreaIds = new Set([areaId])
  let changed = true
  while (changed) {
    changed = false
    for (const area of areas) {
      if (area.parentId && includedAreaIds.has(area.parentId) && !includedAreaIds.has(area.id)) {
        includedAreaIds.add(area.id)
        changed = true
      }
    }
  }
  return equipment.filter((item) => item.areaId != null && includedAreaIds.has(item.areaId))
}

export function toTonnes(value?: string | number | null) {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed / 1000 : 0
}

export function formatTonnes(value?: string | number | null, digits = 2) {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(toTonnes(value))
}

export function formatPercent(value?: string | number | null) {
  const parsed = Number(value ?? 0)
  return `${Number.isFinite(parsed) ? parsed.toFixed(1) : "0.0"}%`
}

export function formatQuantity(value?: string | number | null) {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 4 }).format(parsed) : "-"
}

export function formatDateTime(value?: string | null) {
  if (!value) return "-"
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
}

export function scopeLabel(scope?: string | null) {
  return ({ scope1: "Scope 1", scope2: "Scope 2", scope3: "Scope 3" } as Record<string, string>)[scope ?? ""] ?? scope ?? "-"
}

export function scope2Label(method: Scope2Method) {
  return method === "market" ? "市场法" : "地点法"
}

export function InventoryStatusBadge({ status }: { status?: string | null }) {
  if (status === "completed" || status === "published" || status === "approved" || status === "pass")
    return <StatusBadge status="approved" label={status === "published" ? "已发布" : status === "completed" ? "已完成" : "已通过"} />
  if (status === "failed" || status === "rejected") return <StatusBadge status="rejected" label={status === "failed" ? "失败" : "已驳回"} />
  if (status === "running" || status === "in_progress") return <StatusBadge status="in_progress" label="处理中" />
  if (status === "submitted" || status === "pending_review" || status === "pending" || status === "warning")
    return <StatusBadge status="pending" label={status === "submitted" ? "待审批" : status === "warning" ? "需关注" : "待处理"} />
  return <StatusBadge status="draft" />
}

type RunFilterBarProps = {
  runs?: GhgCalculationRunList
  runCode?: string
  scope2Method: Scope2Method
  onRunCodeChange: (value: string) => void
  onScope2MethodChange: (value: Scope2Method) => void
  onRefresh?: () => void
  refreshing?: boolean
  extraFields?: AdminFilterField[]
  actions?: React.ReactNode
}

export function OrganizationRunFilterBar({
  runs,
  runCode,
  scope2Method,
  onRunCodeChange,
  onScope2MethodChange,
  onRefresh,
  refreshing,
  extraFields = [],
  actions,
}: RunFilterBarProps) {
  const fields: AdminFilterField[] = [
    {
      key: "run",
      node: (
        <Select value={runCode ?? ""} onValueChange={onRunCodeChange}>
          <SelectTrigger aria-label="核算运行">
            <SelectValue placeholder="选择核算运行" />
          </SelectTrigger>
          <SelectContent>
            {(runs?.items ?? []).map((run) => (
              <SelectItem value={run.runCode} key={run.runCode}>
                {run.reportingPeriodName ?? run.inventoryCode} · {run.organizationBoundaryName ?? "组织边界"}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ),
    },
    {
      key: "scope2",
      node: (
        <Select value={scope2Method} onValueChange={(value) => onScope2MethodChange(value as Scope2Method)}>
          <SelectTrigger aria-label="排放总量口径">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="location">地点法总量</SelectItem>
            <SelectItem value="market">市场法总量</SelectItem>
          </SelectContent>
        </Select>
      ),
    },
    ...extraFields,
  ]
  return (
    <AdminFilterBar
      fields={fields}
      actions={
        <>
          {actions}
          {onRefresh && (
            <Button variant="outline" size="sm" onClick={onRefresh} disabled={refreshing}>
              <RefreshCw className={refreshing ? "animate-spin" : ""} />
              刷新
            </Button>
          )}
        </>
      }
    />
  )
}
