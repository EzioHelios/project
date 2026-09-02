import { useQuery } from "@tanstack/react-query"
import { RotateCcw, Search } from "lucide-react"
import { useMemo } from "react"

import { AdminFilterBar, type AdminFilterField } from "@/components/admin-ui"
import { type PageResult, type Row, request, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export type EnergyAnalysisFilterState = {
  periodStart: string
  periodEnd: string
  periodPreset: string
  granularity: string
  energyTypeCode: string
  areaId: string
  areaKeyword: string
  equipmentId: string
  equipmentName: string
  useSystemCode: string
  tariffSegmentType: string
  scope: string
  status: string
  sourceRecordType: string
  groupBy: string
  lossThreshold: string
}

export type EnergyAnalysisFilterField =
  | "period"
  | "periodPreset"
  | "granularity"
  | "energyType"
  | "area"
  | "device"
  | "areaKeyword"
  | "useSystem"
  | "tariff"
  | "scope"
  | "status"
  | "sourceRecordType"
  | "groupBy"
  | "lossThreshold"

export const defaultEnergyAnalysisFilters: EnergyAnalysisFilterState = {
  periodStart: "",
  periodEnd: "",
  periodPreset: "all",
  granularity: "day",
  energyTypeCode: "all",
  areaId: "all",
  areaKeyword: "",
  equipmentId: "all",
  equipmentName: "",
  useSystemCode: "all",
  tariffSegmentType: "all",
  scope: "all",
  status: "all",
  sourceRecordType: "all",
  groupBy: "energy_type",
  lossThreshold: "5",
}

type Option = {
  value: string
  label: string
  data?: Row
}

type EnergyAnalysisFilterBarProps = {
  filters: EnergyAnalysisFilterState
  onFiltersChange: (next: EnergyAnalysisFilterState) => void
  onApply: () => void
  onReset: () => void
  fields: EnergyAnalysisFilterField[]
  areaValueField?: "id" | "code"
  loading?: boolean
  granularityOptions?: { value: string; label: string }[]
  defaultVisibleCount?: number
}

const granularityLabels: Record<string, string> = {
  hour: "小时",
  day: "日",
  month: "月",
}

const energyTypeFallbackLabels: Record<string, string> = {
  purchased_electricity: "外购电力",
  natural_gas: "天然气",
  diesel: "柴油",
  gasoline: "汽油",
  fuel_oil: "燃料油",
  coal: "原煤",
  purchased_heat: "外购热力",
  purchased_steam: "外购蒸汽",
  purchased_cooling: "外购冷量",
  refrigerant: "制冷剂",
}

const periodPresetOptions = [
  { value: "all", label: "全部期间" },
  { value: "2026", label: "2026年" },
  { value: "current_year", label: "本年" },
  { value: "last_12_months", label: "近12个月" },
] as const

const scopeOptions = [
  { value: "all", label: "全部 Scope" },
  { value: "scope1", label: "Scope 1" },
  { value: "scope2", label: "Scope 2" },
] as const

const statusOptions = [
  { value: "all", label: "全部状态" },
  { value: "approved", label: "已通过" },
  { value: "pending", label: "待审核" },
  { value: "draft", label: "草稿" },
  { value: "rejected", label: "已驳回" },
] as const

const sourceRecordTypeOptions = [
  { value: "all", label: "全部来源" },
  { value: "GhgActivityRecord", label: "组织盘查活动" },
] as const

const tariffOptions = [
  { value: "all", label: "全部时段" },
  { value: "peak", label: "峰段" },
  { value: "flat", label: "平段" },
  { value: "valley", label: "谷段" },
] as const

const groupByOptions = [
  { value: "energy_type", label: "按能源品种" },
  { value: "area", label: "按区域" },
  { value: "facility", label: "按设备/设施" },
  { value: "scope", label: "按 Scope" },
  { value: "source", label: "按来源" },
] as const

export function EnergyAnalysisFilterBar({
  filters,
  onFiltersChange,
  onApply,
  onReset,
  fields,
  areaValueField = "code",
  loading = false,
  granularityOptions = [
    { value: "day", label: "日" },
    { value: "hour", label: "小时" },
    { value: "month", label: "月" },
  ],
  defaultVisibleCount = 4,
}: EnergyAnalysisFilterBarProps) {
  const { energyTypeOptions, areaOptions, deviceOptions, useSystemOptions } = useEnergyAnalysisFilterOptions(areaValueField)
  const nodes: AdminFilterField[] = []
  const hasField = (field: EnergyAnalysisFilterField) => fields.includes(field)
  const update = (patch: Partial<EnergyAnalysisFilterState>) => onFiltersChange({ ...filters, ...patch })

  if (hasField("periodPreset")) {
    nodes.push({
      key: "period-preset",
      node: (
        <FilterField label="时间范围">
          <Select value={filters.periodPreset} onValueChange={(value) => update(periodPresetPatch(value))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {periodPresetOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
      ),
    })
  }

  if (hasField("period")) {
    nodes.push({
      key: "period",
      className: "admin-filter-field-wide",
      node: (
        <div className="grid min-w-[260px] grid-cols-2 gap-2">
          <FilterField label="开始日期">
            <Input type="date" value={filters.periodStart} onChange={(event) => update({ periodStart: event.target.value, periodPreset: "custom" })} />
          </FilterField>
          <FilterField label="结束日期">
            <Input type="date" value={filters.periodEnd} onChange={(event) => update({ periodEnd: event.target.value, periodPreset: "custom" })} />
          </FilterField>
        </div>
      ),
    })
  }

  if (hasField("granularity")) {
    nodes.push({
      key: "granularity",
      node: (
        <FilterField label="统计粒度">
          <Select value={filters.granularity} onValueChange={(value) => update({ granularity: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {granularityOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
      ),
    })
  }

  if (hasField("energyType")) {
    nodes.push({
      key: "energy-type",
      node: (
        <FilterField label="能源品种">
          <Select value={filters.energyTypeCode} onValueChange={(value) => update({ energyTypeCode: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部能源品种</SelectItem>
              {energyTypeOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
      ),
    })
  }

  if (hasField("area")) {
    nodes.push({
      key: "area",
      node: (
        <FilterField label="区域">
          <Select value={filters.areaId} onValueChange={(value) => update({ areaId: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部区域</SelectItem>
              {areaOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
      ),
    })
  }

  if (hasField("device")) {
    nodes.push({
      key: "device",
      className: "admin-filter-field-wide",
      node: (
        <FilterField label="设备">
          <Select
            value={filters.equipmentId}
            onValueChange={(value) => {
              const selected = deviceOptions.find((option) => option.value === value)
              update({ equipmentId: value, equipmentName: selected?.data?.name ? String(selected.data.name) : "" })
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部设备</SelectItem>
              {deviceOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
      ),
    })
  }

  if (hasField("areaKeyword")) {
    nodes.push({
      key: "area-keyword",
      node: (
        <FilterField label="区域/设备关键字">
          <Input value={filters.areaKeyword} onChange={(event) => update({ areaKeyword: event.target.value })} placeholder="名称关键字" />
        </FilterField>
      ),
    })
  }

  if (hasField("useSystem")) {
    nodes.push({
      key: "use-system",
      node: (
        <FilterField label="用能系统">
          <Select value={filters.useSystemCode} onValueChange={(value) => update({ useSystemCode: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部用能系统</SelectItem>
              {useSystemOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
      ),
    })
  }

  if (hasField("tariff")) {
    nodes.push({
      key: "tariff",
      node: (
        <FilterField label="分时时段">
          <Select value={filters.tariffSegmentType} onValueChange={(value) => update({ tariffSegmentType: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {tariffOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
      ),
    })
  }

  if (hasField("scope")) {
    nodes.push({
      key: "scope",
      node: (
        <FilterField label="Scope">
          <Select value={filters.scope} onValueChange={(value) => update({ scope: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {scopeOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
      ),
    })
  }

  if (hasField("status")) {
    nodes.push({
      key: "status",
      node: (
        <FilterField label="状态">
          <Select value={filters.status} onValueChange={(value) => update({ status: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {statusOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
      ),
    })
  }

  if (hasField("sourceRecordType")) {
    nodes.push({
      key: "source-record-type",
      node: (
        <FilterField label="来源">
          <Select value={filters.sourceRecordType} onValueChange={(value) => update({ sourceRecordType: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {sourceRecordTypeOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
      ),
    })
  }

  if (hasField("groupBy")) {
    nodes.push({
      key: "group-by",
      node: (
        <FilterField label="汇总维度">
          <Select value={filters.groupBy} onValueChange={(value) => update({ groupBy: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {groupByOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterField>
      ),
    })
  }

  if (hasField("lossThreshold")) {
    nodes.push({
      key: "loss-threshold",
      node: (
        <FilterField label="损耗阈值">
          <Input value={filters.lossThreshold} onChange={(event) => update({ lossThreshold: event.target.value })} inputMode="decimal" placeholder="5" />
        </FilterField>
      ),
    })
  }

  return (
    <AdminFilterBar
      fields={nodes}
      defaultVisibleCount={defaultVisibleCount}
      actions={
        <>
          <Button onClick={onApply} disabled={loading}>
            <Search className="h-4 w-4" />
            查询
          </Button>
          <Button variant="outline" onClick={onReset}>
            <RotateCcw className="h-4 w-4" />
            重置
          </Button>
        </>
      }
    />
  )
}

export function EnergyAppliedFilterMeta({ filters }: { filters: EnergyAnalysisFilterState }) {
  const chips = [
    filters.periodStart || filters.periodEnd ? `${filters.periodStart || "起始"} 至 ${filters.periodEnd || "结束"}` : "全部期间",
    filters.granularity ? `${granularityLabels[filters.granularity] ?? filters.granularity}粒度` : "",
    filters.energyTypeCode !== "all" ? (energyTypeFallbackLabels[filters.energyTypeCode] ?? filters.energyTypeCode) : "全部能源品种",
    filters.areaId !== "all" ? "已选区域" : "",
    filters.equipmentId !== "all" ? filters.equipmentName || "已选设备" : "",
  ].filter(Boolean)
  return (
    <div className="flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        <Badge key={chip} variant="outline">
          {chip}
        </Badge>
      ))}
    </div>
  )
}

export function buildEnergyAnalysisSearchParams(
  filters: EnergyAnalysisFilterState,
  options: {
    includeGranularity?: boolean
    includeScope?: boolean
    includeStatus?: boolean
    includeSourceRecordType?: boolean
    includeGroupBy?: boolean
    includeUseSystem?: boolean
    includeTariff?: boolean
    includeLossThreshold?: boolean
    includeAreaKeyword?: boolean
    includeEquipmentId?: boolean
    includeEquipmentNameAsKeyword?: boolean
  } = {},
) {
  const qs = new URLSearchParams()
  if (filters.periodStart) qs.set("period_start", filters.periodStart)
  if (filters.periodEnd) qs.set("period_end", filters.periodEnd)
  if (options.includeGranularity && filters.granularity) qs.set("granularity", filters.granularity)
  if (filters.energyTypeCode !== "all") qs.set("energy_type_code", filters.energyTypeCode)
  if (options.includeScope && filters.scope !== "all") qs.set("scope", filters.scope)
  if (options.includeStatus) qs.set("status", filters.status || "all")
  if (filters.areaId !== "all") qs.set("area_id", filters.areaId)
  if (options.includeAreaKeyword && filters.areaKeyword.trim()) qs.set("area_keyword", filters.areaKeyword.trim())
  if (options.includeEquipmentId && filters.equipmentId !== "all") qs.set("equipment_id", filters.equipmentId)
  if (options.includeEquipmentNameAsKeyword && filters.equipmentId !== "all" && filters.equipmentName.trim()) qs.set("keyword", filters.equipmentName.trim())
  if (options.includeSourceRecordType && filters.sourceRecordType !== "all") qs.set("source_record_type", filters.sourceRecordType)
  if (options.includeGroupBy && filters.groupBy) qs.set("group_by", filters.groupBy)
  if (options.includeUseSystem && filters.useSystemCode !== "all") qs.set("use_system_code", filters.useSystemCode)
  if (options.includeTariff && filters.tariffSegmentType !== "all") qs.set("tariff_segment_type", filters.tariffSegmentType)
  if (options.includeLossThreshold && filters.lossThreshold.trim()) qs.set("loss_threshold_pct", filters.lossThreshold.trim())
  return qs
}

function FilterField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      {children}
    </div>
  )
}

function useEnergyAnalysisFilterOptions(areaValueField: "id" | "code") {
  const energyTypesQuery = useQuery({
    queryKey: ["energy", "types", "analysis-filter-options"],
    queryFn: async () => (await request<{ items: Row[] }>("/api/energy/types?limit=500")).data.items,
  })
  const areasQuery = useQuery({
    queryKey: ["master-data", "areas", "tree", "analysis-filter-options"],
    queryFn: async () => (await request<{ items: Row[] }>("/api/master-data/areas/tree")).data.items,
  })
  const devicesQuery = useQuery<PageResult<Row>>({
    queryKey: ["master-data", "devices", "analysis-filter-options"],
    queryFn: async () => requestPage<Row>("/api/master-data/devices", { limit: 500, offset: 0 }),
  })

  const energyTypeOptions = useMemo(
    () =>
      (energyTypesQuery.data ?? [])
        .filter((item) => item.code)
        .map((item) => ({
          value: String(item.code),
          label: `${display(item.name) || energyTypeFallbackLabels[String(item.code)] || String(item.code)} · ${String(item.code)}`,
          data: item,
        })),
    [energyTypesQuery.data],
  )
  const areaOptions = useMemo(
    () =>
      flattenRows(areasQuery.data ?? [])
        .map((item) => ({ value: String((areaValueField === "id" ? item.id : item.code) ?? item.id ?? ""), label: areaOptionLabel(item), data: item }))
        .filter((item) => item.value),
    [areaValueField, areasQuery.data],
  )
  const deviceOptions = useMemo(
    () =>
      (devicesQuery.data?.items ?? [])
        .filter((item) => item.id)
        .map((item) => ({
          value: String(item.id),
          label: [display(item.name), display(item.code), display(item.area_name)].filter(Boolean).join(" · "),
          data: item,
        })),
    [devicesQuery.data?.items],
  )
  const useSystemOptions = useMemo(() => {
    const options = new Map<string, Option>()
    for (const item of devicesQuery.data?.items ?? []) {
      const code = String(item.use_system_code ?? "")
      if (!code) continue
      options.set(code, { value: code, label: String(item.use_system_name ?? code), data: item })
    }
    return Array.from(options.values())
  }, [devicesQuery.data?.items])
  return { energyTypeOptions, areaOptions, deviceOptions, useSystemOptions }
}

function periodPresetPatch(value: string): Partial<EnergyAnalysisFilterState> {
  if (value === "all") return { periodPreset: value, periodStart: "", periodEnd: "" }
  if (value === "2026") return { periodPreset: value, periodStart: "2026-01-01", periodEnd: "2026-12-31" }
  const now = new Date()
  const year = now.getFullYear()
  if (value === "current_year") return { periodPreset: value, periodStart: `${year}-01-01`, periodEnd: `${year}-12-31` }
  if (value === "last_12_months") {
    const start = new Date(year, now.getMonth() - 11, 1)
    const end = new Date(year, now.getMonth() + 1, 0)
    return { periodPreset: value, periodStart: toDateInputValue(start), periodEnd: toDateInputValue(end) }
  }
  return { periodPreset: value }
}

function toDateInputValue(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, "0")
  const date = String(value.getDate()).padStart(2, "0")
  return `${year}-${month}-${date}`
}

function display(value: unknown) {
  if (value === null || value === undefined || value === "") return ""
  return String(value)
}

function areaOptionLabel(row: Row) {
  const name = display(row.name) || display(row.code) || display(row.id)
  const code = display(row.code)
  return code && code !== name ? `${name} · ${code}` : name
}

function flattenRows(rows: Row[]): Row[] {
  return rows.flatMap((row) => [row, ...flattenRows(Array.isArray(row.children) ? (row.children as Row[]) : [])])
}
