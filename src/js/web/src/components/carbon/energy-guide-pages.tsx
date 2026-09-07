import { useQuery } from "@tanstack/react-query"
import { ChevronDown, ChevronRight } from "lucide-react"
import type { ReactNode } from "react"
import { useMemo, useState } from "react"

import { AdminDataTable, AdminPageScaffold, AdminPanel, AdminTableStateRow, AdminTabsList, ContextBar, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type ApiEnvelope, CompositeTrendChart, DiagnosticsPanel, DistributionChart, FlowGraph, fetchCarbonApi, RankingList } from "@/components/carbon/analytics-panels"
import {
  buildEnergyAnalysisSearchParams,
  defaultEnergyAnalysisFilters,
  EnergyAnalysisFilterBar,
  type EnergyAnalysisFilterState,
  EnergyAppliedFilterMeta,
} from "@/components/carbon/energy-analysis-filters"
import { JumpLinks } from "@/components/carbon/energy-carbon-center"
import { type PageResult, PaginationBar, requestPage } from "@/components/platform/data-admin-pages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsTrigger } from "@/components/ui/tabs"

const tariffLabel: Record<string, string> = { peak: "峰段", flat: "平段", valley: "谷段", none: "未分时" }

type EnergyAnalysisSummary = {
  totals: {
    record_count: number
    total_energy: number
    total_cost: number
    equipment_count: number
    area_count: number
    system_count: number
    min_period?: string | null
    max_period?: string | null
  }
  workload: {
    record_count: number
    workload_amount: number
    run_hours: number
    equipment_count: number
  }
  performance: {
    kwh_per_run_hour: number | null
    cost_per_kwh: number | null
  }
  by_system: {
    use_system_code: string
    use_system_name: string
    record_count: number
    equipment_count: number
    total_energy: number
    total_cost: number
  }[]
  by_area: {
    area_id: string
    area_name: string
    record_count: number
    equipment_count: number
    total_energy: number
    total_cost: number
  }[]
  by_equipment: {
    equipment_id: number
    equipment_name: string
    area_name: string
    use_system_name: string
    record_count: number
    total_energy: number
    total_cost: number
  }[]
  by_tariff: {
    tariff_segment_type: string
    record_count: number
    total_energy: number
    total_cost: number
  }[]
  trend: {
    period: string
    total_energy: number
    total_cost: number
    equipment_count: number
  }[]
}

type EnergyAnalysisAnomaly = {
  equipment_id: number
  equipment_name: string
  area_name: string
  use_system_name: string
  period_start: string
  amount: number
  cost_cny: number
  avg_amount: number
  deviation_score: number | null
  anomaly_type: string
}

type EnergyAnalysisAlarm = {
  id: number
  alarm_name?: string | null
  alarm_level?: string | null
  alarm_category?: string | null
  event_desc?: string | null
  event_time?: string | null
  current_value?: number | null
  threshold_value?: number | null
  status?: string | null
}

type EnergyAnalysisStrategy = {
  code: string
  title: string
  priority: string
  strategy_type: string
  target: string
  evidence: Record<string, unknown>
  steps: string[]
  expected_effect: string
}

type EnergyAnalysisAnomalies = {
  items: EnergyAnalysisAnomaly[]
  alarms: EnergyAnalysisAlarm[]
}

type EnergyAnalysisStrategies = {
  items: EnergyAnalysisStrategy[]
  evidence_summary: {
    total_energy: number
    total_cost: number
    anomaly_count: number
    alarm_count: number
  }
}

type FlowData = {
  title: string
  unit: string
  nodes: { id: string; name: string; value?: number; category?: string }[]
  links: { source: string; target: string; value: number }[]
  summary?: EnergyFlowSummary
}

type BalanceData = {
  billing_month?: string | null
  table: { label: string; value: number | null; unit: string }[]
  diagnostics: { label: string; value: string | number }[]
  summary?: EnergyFlowSummary
}

type EnergyFlowSummary = {
  total_input: number
  transform_loss: number | null
  distribution_loss: number | null
  total_loss: number | null
  loss_rate_pct: number | null
  utilized_energy: number
  high_loss_count: number | null
  row_count: number
  loss_threshold_pct: number
  data_quality: string
}

type EnergyFlowLoss = {
  stage: string
  source: string
  target: string
  input_amount: number
  loss_amount: number
  loss_rate_pct: number
  threshold_pct: number
  status: string
  suggestion: string
}

type EnergyFlowLossData = {
  items: EnergyFlowLoss[]
  total: number
  summary: EnergyFlowSummary
}

type EnergyFlowReportItem = {
  title: string
  priority: string
  target: string
  evidence: Record<string, string | number | null>
  steps: string[]
  expected_effect: string
}

type EnergyFlowReportData = {
  summary: EnergyFlowSummary
  items: EnergyFlowReportItem[]
}

type EnergyFact = {
  source_record_type: string
  source_record_id: number
  granularity?: string | null
  scope: string
  emission_category: string
  energy_type_code: string
  energy_type_name: string
  tariff_segment_type?: string | null
  original_amount: number | null
  original_unit: string | null
  factor_amount: number | null
  factor_unit: string | null
  unit_conversion_factor?: number | null
  unit_conversion_source?: string | null
  standard_amount: number | null
  standard_unit: string | null
  tce_amount: number | null
  co2e_amount: number | null
  period_start: string
  period_end: string
  area_name?: string | null
  facility_or_device_name?: string | null
  status: string
  standard_code?: string | null
  conversion_factor_source?: string | null
}

type EnergyTypeRow = {
  id: number
  code: string
  name: string
  category: string
  default_scope: string
  original_unit?: string | null
  standard_unit?: string | null
  standard_factor?: number | null
  standard_code?: string | null
  conversion_factor_source?: string | null
  is_enabled: boolean
}

type EnergySummaryItem = {
  group_key: string
  group_label: string
  record_count: number
  original_amount: number | null
  original_unit?: string | null
  factor_amount?: number | null
  factor_unit?: string | null
  standard_amount: number | null
  standard_unit?: string | null
  tce_amount: number | null
  co2e_amount: number | null
}

type EnergyConsumptionSummary = {
  items: EnergySummaryItem[]
  totals: {
    record_count: number
    original_amount: number | null
    factor_amount?: number | null
    standard_amount: number | null
    tce_amount: number | null
    co2e_amount: number | null
  }
  group_by?: string[]
}

type EnergyIntensityDenominators = {
  enterprise?: {
    id?: number | string | null
    name?: string | null
    belong_unit?: string | null
    unify_code?: string | null
    industry?: string | null
    location?: string | null
  }
  store_area: number | null
  park_area: number | null
  source_record_type: string
  source_table: string
  source_fields: Record<string, string>
}

type EnergyIntensitySummary = {
  totals: {
    record_count: number
    total_tce: number
    total_kgce: number
    total_co2e: number
    electricity_kwh: number
  }
  denominators: EnergyIntensityDenominators
  intensities: {
    store_area_tce_per_m2: number | null
    park_area_tce_per_m2: number | null
    store_area_kwh_per_m2: number | null
    park_area_kwh_per_m2: number | null
  }
  by_energy_type: {
    energy_type_code: string
    energy_type_name: string
    record_count: number
    original_amount: number
    original_unit?: string | null
    total_tce: number
    total_kgce: number
    total_co2e: number
  }[]
  by_scope: {
    scope: string
    record_count: number
    total_tce: number
    total_kgce: number
    total_co2e: number
  }[]
  by_area: {
    area_id: string
    area_name: string
    record_count: number
    total_tce: number
    total_kgce: number
    total_co2e: number
    electricity_kwh: number
  }[]
  by_device: {
    facility_or_device_name: string
    area_name: string
    record_count: number
    total_tce: number
    total_kgce: number
    total_co2e: number
    electricity_kwh: number
  }[]
}

type EnergyIntensityTrendPoint = {
  period: string
  record_count: number
  total_tce: number
  total_kgce: number
  total_co2e: number
  electricity_kwh: number
  store_area_tce_per_m2: number | null
  park_area_tce_per_m2: number | null
  store_area_kgce_per_m2?: number | null
  park_area_kgce_per_m2?: number | null
  store_area_kwh_per_m2: number | null
  park_area_kwh_per_m2: number | null
}

type EnergyIntensityTrend = {
  series: EnergyIntensityTrendPoint[]
  denominators: EnergyIntensityDenominators
}

type ProductionProductRow = {
  id: number
  code: string
  name: string
  spec?: string | null
  category?: string | null
  output_kind?: string | null
  default_unit?: string | null
  standard_unit?: string | null
  is_enabled?: boolean
}

type ProductIntensityItem = {
  product_code: string
  product_name: string
  product_spec?: string | null
  category?: string | null
  output_kind?: string | null
  standard_unit?: string | null
  record_count: number
  total_good_qty: number
  total_standard_qty: number
  total_kgce: number | null
  kgce_per_unit: number | null
  calculation_status?: string
}

type ProductIntensitySummary = {
  energy_totals: {
    record_count: number
    total_tce: number
    total_kgce: number
    total_co2e: number
  }
  production_totals: {
    record_count: number
    product_count: number
    total_good_qty: number
    total_standard_qty: number
  }
  items: ProductIntensityItem[]
  unit_intensity: number | null
}

const outputKindOptions = [
  { label: "产品产量", value: "product" },
  { label: "库存量", value: "material_storage" },
  { label: "出入库处理量", value: "material_handling" },
  { label: "作业量", value: "operation_workload" },
]

function outputKindLabel(value?: string | null) {
  return outputKindOptions.find((option) => option.value === value)?.label ?? value ?? "-"
}

type ValueIntensityItem = ProductIntensityItem & {
  selected_price_type: string
  selected_price: number | null
  selected_output_value: number
  selected_output_value_10k: number
  kgce_per_10k_value: number | null
  price_missing: boolean
}

type ValueIntensitySummary = {
  energy_totals: ProductIntensitySummary["energy_totals"]
  production_totals: ProductIntensitySummary["production_totals"]
  price_type: string
  output_value: number
  output_value_10k: number
  kgce_per_10k_value: number | null
  missing_price_products: { product_code: string; product_name?: string | null; price_type: string }[]
  items: ValueIntensityItem[]
}

type EnergyHierarchyRow = {
  id: string
  parentId?: string
  level: 0 | 1 | 2
  name: string
  subtitle?: string
  type: string
  record_count: number
  total_tce: number
  total_co2e: number
  electricity_kwh: number
  hasChildren?: boolean
}

function initialEnergyImportTab() {
  if (typeof window === "undefined") return "summary"
  return new URLSearchParams(window.location.search).get("tab") === "export" ? "export" : "summary"
}

const formatEnergyValue = (value: number | null | undefined, digits = 4) =>
  value === null || value === undefined ? "-" : Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })

const formatKgcePerM2 = (value: number | null | undefined, digits = 4) => formatEnergyValue(value === null || value === undefined ? null : value * 1000, digits)

export function EnergyConsumptionPanel({ header }: { header?: ReactNode }) {
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [filters, setFilters] = useState<EnergyAnalysisFilterState>(defaultEnergyAnalysisFilters)
  const [appliedFilters, setAppliedFilters] = useState<EnergyAnalysisFilterState>(defaultEnergyAnalysisFilters)

  const queryParams = useMemo(() => {
    return buildEnergyAnalysisSearchParams(appliedFilters, {
      includeGranularity: true,
      includeScope: true,
      includeStatus: true,
      includeSourceRecordType: true,
      includeGroupBy: true,
      includeTariff: true,
      includeAreaKeyword: true,
      includeEquipmentNameAsKeyword: true,
    })
  }, [appliedFilters])

  const summaryQuery = useQuery<ApiEnvelope<EnergyConsumptionSummary>>({
    queryKey: ["energy", "consumption", "summary", appliedFilters],
    queryFn: () => fetchCarbonApi<EnergyConsumptionSummary>(`/api/energy/consumption/summary?${queryParams.toString()}`),
  })
  const factsQuery = useQuery<PageResult<EnergyFact>>({
    queryKey: ["energy", "consumption", "facts", appliedFilters, pageIndex, pageSize],
    queryFn: () =>
      requestPage<EnergyFact>("/api/energy/consumption/facts", {
        ...Object.fromEntries(queryParams.entries()),
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })
  const summary = summaryQuery.data?.data
  const facts = factsQuery.data?.items ?? []
  const exportUrl = `/api/energy/consumption/export?${queryParams.toString()}`

  function applyFilters() {
    setAppliedFilters(filters)
    setPageIndex(0)
  }

  function resetFilters() {
    setFilters(defaultEnergyAnalysisFilters)
    setAppliedFilters(defaultEnergyAnalysisFilters)
    setPageIndex(0)
  }

  const formatNumber = (value: number | null | undefined, digits = 4) =>
    value === null || value === undefined ? "-" : Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
  const sourceRoute: Record<string, string> = {
    GhgActivityRecord: "/carbon-mgmt/activities",
  }

  return (
    <Tabs defaultValue={initialEnergyImportTab()} className="space-y-4">
      <AdminPageScaffold
        header={header}
        title={header ? undefined : "能耗查询"}
        tabs={
          <AdminTabsList>
            <TabsTrigger value="summary">汇总查询</TabsTrigger>
            <TabsTrigger value="facts">明细追溯</TabsTrigger>
            <TabsTrigger value="export">导出记录</TabsTrigger>
          </AdminTabsList>
        }
        filters={
          <EnergyAnalysisFilterBar
            filters={filters}
            onFiltersChange={setFilters}
            onApply={applyFilters}
            onReset={resetFilters}
            fields={["periodPreset", "period", "granularity", "energyType", "area", "device", "tariff", "groupBy", "scope", "status", "sourceRecordType", "areaKeyword"]}
            areaValueField="id"
            defaultVisibleCount={6}
            loading={summaryQuery.isFetching || factsQuery.isFetching}
          />
        }
        meta={<EnergyAppliedFilterMeta filters={appliedFilters} />}
      >
        <TabsContent value="summary" className="space-y-4">
          <MetricStrip className="md:grid-cols-4 xl:grid-cols-4">
            <MetricTile label="记录数" value={summary?.totals.record_count ?? 0} />
            <MetricTile label="原始消费量" value={formatNumber(summary?.totals.original_amount)} />
            <MetricTile label="折标煤" value={formatNumber(summary?.totals.tce_amount)} unit="tce" />
            <MetricTile label="CO2e" value={formatNumber(summary?.totals.co2e_amount, 2)} unit="kg" />
          </MetricStrip>
          <PageSection>
            <AdminPanel title={summary?.group_by?.[0] ? "能耗汇总" : "按能源品种汇总"} contentClassName="p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>汇总维度</TableHead>
                      <TableHead className="text-right">记录数</TableHead>
                      <TableHead className="text-right">原始量</TableHead>
                      <TableHead>单位</TableHead>
                      <TableHead className="text-right">折标基准量</TableHead>
                      <TableHead className="text-right">折标量</TableHead>
                      <TableHead className="text-right">折标煤(tce)</TableHead>
                      <TableHead className="text-right">CO2e(kg)</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(summary?.items ?? []).length === 0 && <AdminTableStateRow colSpan={8}>暂无数据</AdminTableStateRow>}
                    {(summary?.items ?? []).map((item) => (
                      <TableRow key={item.group_key}>
                        <TableCell>{item.group_label}</TableCell>
                        <TableCell className="text-right">{item.record_count}</TableCell>
                        <TableCell className="text-right">{formatNumber(item.original_amount)}</TableCell>
                        <TableCell>{item.original_unit || "-"}</TableCell>
                        <TableCell className="text-right">
                          {formatNumber(item.factor_amount)} {item.factor_unit || ""}
                        </TableCell>
                        <TableCell className="text-right">
                          {formatNumber(item.standard_amount)} {item.standard_unit || ""}
                        </TableCell>
                        <TableCell className="text-right">{formatNumber(item.tce_amount)}</TableCell>
                        <TableCell className="text-right">{formatNumber(item.co2e_amount, 2)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </PageSection>
        </TabsContent>

        <TabsContent value="facts">
          <PageSection>
            <AdminPanel title="能源消费明细" contentClassName="space-y-3 p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>来源</TableHead>
                      <TableHead>ID</TableHead>
                      <TableHead>Scope</TableHead>
                      <TableHead>能源品种</TableHead>
                      <TableHead>电价时段</TableHead>
                      <TableHead className="text-right">原始量</TableHead>
                      <TableHead className="text-right">折标基准量</TableHead>
                      <TableHead>换算来源</TableHead>
                      <TableHead className="text-right">折标煤(tce)</TableHead>
                      <TableHead>期间</TableHead>
                      <TableHead>区域/设施</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead className="text-right">追溯</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {facts.length === 0 && <AdminTableStateRow colSpan={13}>暂无数据</AdminTableStateRow>}
                    {facts.map((row) => (
                      <TableRow key={`${row.source_record_type}-${row.source_record_id}`}>
                        <TableCell>{row.source_record_type}</TableCell>
                        <TableCell>{row.source_record_id}</TableCell>
                        <TableCell>{row.scope}</TableCell>
                        <TableCell>{row.energy_type_name}</TableCell>
                        <TableCell>
                          {row.energy_type_code === "purchased_electricity" ? tariffLabel[row.tariff_segment_type ?? "none"] || row.tariff_segment_type || "-" : "-"}
                        </TableCell>
                        <TableCell className="text-right">
                          {formatNumber(row.original_amount)} {row.original_unit || ""}
                        </TableCell>
                        <TableCell className="text-right">
                          {formatNumber(row.factor_amount)} {row.factor_unit || ""}
                        </TableCell>
                        <TableCell className="max-w-[260px] truncate" title={row.unit_conversion_source || row.conversion_factor_source || ""}>
                          {row.unit_conversion_source || "-"}
                        </TableCell>
                        <TableCell className="text-right">{formatNumber(row.tce_amount)}</TableCell>
                        <TableCell>
                          {row.period_start} 至 {row.period_end}
                        </TableCell>
                        <TableCell>{[row.area_name, row.facility_or_device_name].filter(Boolean).join(" / ") || "-"}</TableCell>
                        <TableCell>{row.status}</TableCell>
                        <TableCell className="text-right">
                          <Button variant="outline" size="sm" asChild>
                            <a href={sourceRoute[row.source_record_type] ?? "/energy/consumption"}>打开</a>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AdminDataTable>
              <div className="px-4 pb-4">
                <PaginationBar
                  page={factsQuery.data ?? { items: [], total: 0, limit: pageSize, offset: pageIndex * pageSize }}
                  pageIndex={pageIndex}
                  pageSize={pageSize}
                  onPageChange={setPageIndex}
                  onPageSizeChange={(value) => {
                    setPageSize(value)
                    setPageIndex(0)
                  }}
                />
              </div>
            </AdminPanel>
          </PageSection>
        </TabsContent>

        <TabsContent value="export">
          <PageSection>
            <AdminPanel title="导出" contentClassName="flex justify-end">
              <Button asChild>
                <a href={exportUrl}>导出 CSV</a>
              </Button>
            </AdminPanel>
          </PageSection>
        </TabsContent>
      </AdminPageScaffold>
    </Tabs>
  )
}

export function EnergyIntensityPanel({ header }: { header?: ReactNode }) {
  const [periodStart, setPeriodStart] = useState("")
  const [periodEnd, setPeriodEnd] = useState("")
  const [months, setMonths] = useState("12")
  const [granularity, setGranularity] = useState("month")
  const [scope, setScope] = useState("all")
  const [energyTypeCode, setEnergyTypeCode] = useState("all")
  const [status, setStatus] = useState("all")
  const [productCode, setProductCode] = useState("all")
  const [outputKind, setOutputKind] = useState("all")
  const [lineCode, setLineCode] = useState("")
  const [areaId, setAreaId] = useState("")
  const [equipmentCode, setEquipmentCode] = useState("")
  const [priceType, setPriceType] = useState("standard_price")
  const [expandedHierarchy, setExpandedHierarchy] = useState<Record<string, boolean>>({ root: true })
  const [appliedFilters, setAppliedFilters] = useState({
    periodStart: "",
    periodEnd: "",
    months: "12",
    granularity: "month",
    scope: "all",
    energyTypeCode: "all",
    status: "all",
    productCode: "all",
    outputKind: "all",
    lineCode: "",
    areaId: "",
    equipmentCode: "",
    priceType: "standard_price",
  })

  const summaryParams = useMemo(() => {
    const qs = new URLSearchParams()
    if (appliedFilters.periodStart) qs.set("period_start", appliedFilters.periodStart)
    if (appliedFilters.periodEnd) qs.set("period_end", appliedFilters.periodEnd)
    qs.set("status", appliedFilters.status)
    if (appliedFilters.scope !== "all") qs.set("scope", appliedFilters.scope)
    if (appliedFilters.energyTypeCode !== "all") qs.set("energy_type_code", appliedFilters.energyTypeCode)
    return qs
  }, [appliedFilters])

  const trendParams = useMemo(() => {
    const qs = new URLSearchParams()
    qs.set("months", appliedFilters.months)
    qs.set("granularity", appliedFilters.granularity)
    if (appliedFilters.periodStart) qs.set("period_start", appliedFilters.periodStart)
    if (appliedFilters.periodEnd) qs.set("period_end", appliedFilters.periodEnd)
    qs.set("status", appliedFilters.status)
    if (appliedFilters.scope !== "all") qs.set("scope", appliedFilters.scope)
    if (appliedFilters.energyTypeCode !== "all") qs.set("energy_type_code", appliedFilters.energyTypeCode)
    return qs
  }, [appliedFilters])

  const productionParams = useMemo(() => {
    const qs = new URLSearchParams(summaryParams)
    qs.set("granularity", appliedFilters.granularity)
    qs.set("record_status", "confirmed")
    if (appliedFilters.productCode !== "all") qs.set("product_code", appliedFilters.productCode)
    if (appliedFilters.outputKind !== "all") qs.set("output_kind", appliedFilters.outputKind)
    if (appliedFilters.lineCode) qs.set("line_code", appliedFilters.lineCode)
    if (appliedFilters.areaId) qs.set("area_id", appliedFilters.areaId)
    if (appliedFilters.equipmentCode) qs.set("equipment_code", appliedFilters.equipmentCode)
    return qs
  }, [appliedFilters, summaryParams])

  const valueParams = useMemo(() => {
    const qs = new URLSearchParams(productionParams)
    qs.set("price_type", appliedFilters.priceType)
    return qs
  }, [appliedFilters.priceType, productionParams])

  const summaryQuery = useQuery<ApiEnvelope<EnergyIntensitySummary>>({
    queryKey: ["energy", "intensity", "summary", appliedFilters],
    queryFn: () => fetchCarbonApi<EnergyIntensitySummary>(`/api/energy/intensity/summary?${summaryParams.toString()}`),
  })
  const trendQuery = useQuery<ApiEnvelope<EnergyIntensityTrend>>({
    queryKey: ["energy", "intensity", "trend", appliedFilters],
    queryFn: () => fetchCarbonApi<EnergyIntensityTrend>(`/api/energy/intensity/trend?${trendParams.toString()}`),
  })
  const energyTypesQuery = useQuery<ApiEnvelope<{ items: EnergyTypeRow[] }>>({
    queryKey: ["energy", "types"],
    queryFn: () => fetchCarbonApi<{ items: EnergyTypeRow[] }>("/api/energy/types"),
  })
  const productsQuery = useQuery<PageResult<ProductionProductRow>>({
    queryKey: ["production", "products", "enabled"],
    queryFn: () => requestPage<ProductionProductRow>("/api/production/products", { limit: 500, is_enabled: true }),
  })
  const productSummaryQuery = useQuery<ApiEnvelope<ProductIntensitySummary>>({
    queryKey: ["energy", "intensity", "product-summary", appliedFilters],
    queryFn: () => fetchCarbonApi<ProductIntensitySummary>(`/api/energy/intensity/product-summary?${productionParams.toString()}`),
  })
  const valueSummaryQuery = useQuery<ApiEnvelope<ValueIntensitySummary>>({
    queryKey: ["energy", "intensity", "value-summary", appliedFilters],
    queryFn: () => fetchCarbonApi<ValueIntensitySummary>(`/api/energy/intensity/value-summary?${valueParams.toString()}`),
  })

  const summary = summaryQuery.data?.data
  const trend = trendQuery.data?.data
  const productSummary = productSummaryQuery.data?.data
  const valueSummary = valueSummaryQuery.data?.data
  const intensityTrendSeries = useMemo(
    () =>
      (trend?.series ?? []).map((item) => ({
        ...item,
        store_area_kgce_per_m2: item.store_area_tce_per_m2 === null ? null : item.store_area_tce_per_m2 * 1000,
        park_area_kgce_per_m2: item.park_area_tce_per_m2 === null ? null : item.park_area_tce_per_m2 * 1000,
      })),
    [trend?.series],
  )
  const hierarchyRows = useMemo<EnergyHierarchyRow[]>(() => {
    if (!summary) return []
    const enterprise = summary.denominators.enterprise
    const enterpriseSubtitle = [enterprise?.belong_unit, enterprise?.industry, enterprise?.unify_code].filter(Boolean).join(" · ")
    const devicesByArea = new Map<string, EnergyIntensitySummary["by_device"]>()
    for (const device of summary.by_device) {
      const key = device.area_name || "未分区"
      const next = devicesByArea.get(key) ?? []
      next.push(device)
      devicesByArea.set(key, next)
    }
    const root: EnergyHierarchyRow = {
      id: "root",
      level: 0,
      name: enterprise?.name || "企业/园区",
      subtitle: enterpriseSubtitle,
      type: "企业/园区",
      record_count: summary.totals.record_count,
      total_tce: summary.totals.total_tce,
      total_co2e: summary.totals.total_co2e,
      electricity_kwh: summary.totals.electricity_kwh,
      hasChildren: summary.by_area.length > 0,
    }
    const rows: EnergyHierarchyRow[] = [root]
    if (!expandedHierarchy.root) return rows
    for (const area of summary.by_area) {
      const areaId = `area:${area.area_id || area.area_name}`
      const devices = devicesByArea.get(area.area_name) ?? []
      rows.push({
        id: areaId,
        parentId: "root",
        level: 1,
        name: area.area_name,
        type: "区域",
        record_count: area.record_count,
        total_tce: area.total_tce,
        total_co2e: area.total_co2e,
        electricity_kwh: area.electricity_kwh,
        hasChildren: devices.length > 0,
      })
      if (!expandedHierarchy[areaId]) continue
      for (const device of devices) {
        rows.push({
          id: `device:${area.area_name}:${device.facility_or_device_name}`,
          parentId: areaId,
          level: 2,
          name: device.facility_or_device_name,
          type: "设备/设施",
          record_count: device.record_count,
          total_tce: device.total_tce,
          total_co2e: device.total_co2e,
          electricity_kwh: device.electricity_kwh,
        })
      }
    }
    return rows
  }, [expandedHierarchy, summary])
  const totalHierarchyTce = Number(summary?.totals.total_tce ?? 0)

  function applyFilters() {
    setAppliedFilters({ periodStart, periodEnd, months, granularity, scope, energyTypeCode, status, productCode, outputKind, lineCode, areaId, equipmentCode, priceType })
  }

  function resetFilters() {
    setPeriodStart("")
    setPeriodEnd("")
    setMonths("12")
    setGranularity("month")
    setScope("all")
    setEnergyTypeCode("all")
    setStatus("all")
    setProductCode("all")
    setOutputKind("all")
    setLineCode("")
    setAreaId("")
    setEquipmentCode("")
    setPriceType("standard_price")
    setAppliedFilters({
      periodStart: "",
      periodEnd: "",
      months: "12",
      granularity: "month",
      scope: "all",
      energyTypeCode: "all",
      status: "all",
      productCode: "all",
      outputKind: "all",
      lineCode: "",
      areaId: "",
      equipmentCode: "",
      priceType: "standard_price",
    })
  }

  function toggleHierarchyNode(id: string) {
    setExpandedHierarchy((current) => ({ ...current, [id]: !current[id] }))
  }

  return (
    <Tabs defaultValue="summary" className="space-y-4">
      <AdminPageScaffold
        header={header}
        tabs={
          <AdminTabsList>
            <TabsTrigger value="summary">消费量汇总</TabsTrigger>
            <TabsTrigger value="area">面积强度</TabsTrigger>
            <TabsTrigger value="product">产品强度</TabsTrigger>
            <TabsTrigger value="value">产值强度</TabsTrigger>
            <TabsTrigger value="hierarchy">区域设备</TabsTrigger>
            <TabsTrigger value="trend">趋势分析</TabsTrigger>
          </AdminTabsList>
        }
        filters={
          <ContextBar
            actions={
              <>
                <JumpLinks items={[{ label: "查看能耗查询", to: "/energy/consumption" }]} />
                <Button onClick={applyFilters}>查询</Button>
                <Button variant="outline" onClick={resetFilters}>
                  重置
                </Button>
              </>
            }
          >
            <Input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} />
            <Input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} />
            <Select value={months} onValueChange={setMonths}>
              <SelectTrigger>
                <SelectValue placeholder="周期数" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7">7 期</SelectItem>
                <SelectItem value="12">12 期</SelectItem>
                <SelectItem value="24">24 期</SelectItem>
                <SelectItem value="36">36 期</SelectItem>
              </SelectContent>
            </Select>
            <Select value={granularity} onValueChange={setGranularity}>
              <SelectTrigger>
                <SelectValue placeholder="统计粒度" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="day">日</SelectItem>
                <SelectItem value="month">月</SelectItem>
                <SelectItem value="year">年</SelectItem>
              </SelectContent>
            </Select>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger>
                <SelectValue placeholder="状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="approved">已审核</SelectItem>
                <SelectItem value="pending">待审核</SelectItem>
                <SelectItem value="draft">草稿</SelectItem>
                <SelectItem value="rejected">已驳回</SelectItem>
              </SelectContent>
            </Select>
            <Select value={scope} onValueChange={setScope}>
              <SelectTrigger>
                <SelectValue placeholder="Scope" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部 Scope</SelectItem>
                <SelectItem value="scope1">Scope1</SelectItem>
                <SelectItem value="scope2">Scope2</SelectItem>
              </SelectContent>
            </Select>
            <Select value={energyTypeCode} onValueChange={setEnergyTypeCode}>
              <SelectTrigger>
                <SelectValue placeholder="能源品种" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部能源品种</SelectItem>
                {(energyTypesQuery.data?.data.items ?? []).map((item) => (
                  <SelectItem key={item.code} value={item.code}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={productCode} onValueChange={setProductCode}>
              <SelectTrigger>
                <SelectValue placeholder="产品" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部产品</SelectItem>
                {(productsQuery.data?.items ?? []).map((item) => (
                  <SelectItem key={item.code} value={item.code}>
                    {item.name || item.code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={outputKind} onValueChange={setOutputKind}>
              <SelectTrigger>
                <SelectValue placeholder="业务类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部业务类型</SelectItem>
                {outputKindOptions.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input value={lineCode} onChange={(event) => setLineCode(event.target.value)} placeholder="产线编码" />
            <Input value={areaId} onChange={(event) => setAreaId(event.target.value)} placeholder="区域ID" />
            <Input value={equipmentCode} onChange={(event) => setEquipmentCode(event.target.value)} placeholder="设备编码" />
            <Select value={priceType} onValueChange={setPriceType}>
              <SelectTrigger>
                <SelectValue placeholder="价格口径" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="standard_price">标准价</SelectItem>
                <SelectItem value="actual_average_price">实际均价</SelectItem>
                <SelectItem value="base_period_price">基期价</SelectItem>
              </SelectContent>
            </Select>
          </ContextBar>
        }
      >
        <TabsContent value="summary" className="space-y-4">
          <MetricStrip>
            <MetricTile label="综合能耗" value={formatEnergyValue(summary?.totals.total_tce, 4)} unit="tce" />
            <MetricTile label="折标煤" value={formatEnergyValue(summary?.totals.total_kgce, 2)} unit="kgce" />
            <MetricTile label="外购电力" value={formatEnergyValue(summary?.totals.electricity_kwh, 2)} unit="kWh" />
            <MetricTile label="记录数" value={formatEnergyValue(summary?.totals.record_count, 0)} />
          </MetricStrip>
          <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
            <AdminPanel title="能源品种汇总" contentClassName="p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>能源品种</TableHead>
                      <TableHead className="text-right">原始量</TableHead>
                      <TableHead className="text-right">综合能耗(tce)</TableHead>
                      <TableHead className="text-right">记录数</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(summary?.by_energy_type ?? []).map((item) => (
                      <TableRow key={item.energy_type_code}>
                        <TableCell>{item.energy_type_name}</TableCell>
                        <TableCell className="text-right">
                          {formatEnergyValue(item.original_amount, 2)} {item.original_unit || ""}
                        </TableCell>
                        <TableCell className="text-right">{formatEnergyValue(item.total_tce, 4)}</TableCell>
                        <TableCell className="text-right">{formatEnergyValue(item.record_count, 0)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
            <DistributionChart
              title="综合能耗结构"
              items={(summary?.by_energy_type ?? []).map((item) => ({ name: item.energy_type_name, value: item.total_tce }))}
              unit="tce"
              height={360}
            />
          </PageSection>
        </TabsContent>

        <TabsContent value="area" className="space-y-4">
          <MetricStrip>
            <MetricTile label="仓储面积折标强度" value={formatKgcePerM2(summary?.intensities.store_area_tce_per_m2, 4)} unit="kgce/㎡" />
            <MetricTile label="园区面积折标强度" value={formatKgcePerM2(summary?.intensities.park_area_tce_per_m2, 4)} unit="kgce/㎡" />
            <MetricTile label="仓储面积电力强度" value={formatEnergyValue(summary?.intensities.store_area_kwh_per_m2, 4)} unit="kWh/㎡" />
            <MetricTile label="园区面积电力强度" value={formatEnergyValue(summary?.intensities.park_area_kwh_per_m2, 4)} unit="kWh/㎡" />
          </MetricStrip>
          <PageSection className="grid gap-4 xl:grid-cols-2">
            <DiagnosticsPanel
              title="面积分母"
              items={[
                { label: "仓储面积", value: `${formatEnergyValue(summary?.denominators.store_area, 2)} ㎡` },
                { label: "园区面积", value: `${formatEnergyValue(summary?.denominators.park_area, 2)} ㎡` },
              ]}
            />
            <DistributionChart title="Scope 综合能耗结构" items={(summary?.by_scope ?? []).map((item) => ({ name: item.scope.toUpperCase(), value: item.total_tce }))} unit="tce" />
          </PageSection>
        </TabsContent>

        <TabsContent value="product" className="space-y-4">
          <MetricStrip>
            <MetricTile label="综合能耗" value={formatEnergyValue(productSummary?.energy_totals.total_kgce, 2)} unit="kgce" />
            <MetricTile label="产品产量" value={formatEnergyValue(productSummary?.production_totals.total_good_qty, 2)} />
            <MetricTile label="标准产量" value={formatEnergyValue(productSummary?.production_totals.total_standard_qty, 2)} />
            <MetricTile label="覆盖产品" value={formatEnergyValue(productSummary?.production_totals.product_count, 0)} />
          </MetricStrip>
          <PageSection>
            <AdminPanel title="产品单位强度" contentClassName="p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>产品</TableHead>
                      <TableHead>业务类型</TableHead>
                      <TableHead>规格</TableHead>
                      <TableHead className="text-right">产量</TableHead>
                      <TableHead className="text-right">标准产量</TableHead>
                      <TableHead>单位</TableHead>
                      <TableHead className="text-right">综合能耗(kgce)</TableHead>
                      <TableHead className="text-right">kgce/单位</TableHead>
                      <TableHead className="text-right">记录数</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(productSummary?.items ?? []).length === 0 && <AdminTableStateRow colSpan={9}>暂无产品批次产量数据</AdminTableStateRow>}
                    {(productSummary?.items ?? []).map((item) => (
                      <TableRow key={item.product_code}>
                        <TableCell>
                          <div className="font-medium">{item.product_name || item.product_code}</div>
                          <div className="text-xs text-muted-foreground">{item.product_code}</div>
                        </TableCell>
                        <TableCell>{outputKindLabel(item.output_kind)}</TableCell>
                        <TableCell>{item.product_spec || "-"}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.total_good_qty, 2)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.total_standard_qty, 2)}</TableCell>
                        <TableCell>{item.standard_unit || "-"}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.total_kgce, 2)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.kgce_per_unit, 6)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.record_count, 0)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </PageSection>
        </TabsContent>

        <TabsContent value="value" className="space-y-4">
          <MetricStrip>
            <MetricTile label="综合能耗" value={formatEnergyValue(valueSummary?.energy_totals.total_kgce, 2)} unit="kgce" />
            <MetricTile label="产品产值" value={formatEnergyValue(valueSummary?.output_value_10k, 4)} unit="万元" />
            <MetricTile label="单位产值综合能耗" value={formatEnergyValue(valueSummary?.kgce_per_10k_value, 4)} unit="kgce/万元" />
            <MetricTile label="缺价格产品" value={formatEnergyValue(valueSummary?.missing_price_products.length, 0)} />
          </MetricStrip>
          <PageSection>
            <AdminPanel title="产值强度明细" contentClassName="p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>产品</TableHead>
                      <TableHead>业务类型</TableHead>
                      <TableHead className="text-right">标准产量</TableHead>
                      <TableHead>单位</TableHead>
                      <TableHead className="text-right">单价</TableHead>
                      <TableHead className="text-right">产值(元)</TableHead>
                      <TableHead className="text-right">综合能耗(kgce)</TableHead>
                      <TableHead className="text-right">kgce/万元</TableHead>
                      <TableHead className="text-right">记录数</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(valueSummary?.items ?? []).length === 0 && <AdminTableStateRow colSpan={9}>暂无产品产值数据</AdminTableStateRow>}
                    {(valueSummary?.items ?? []).map((item) => (
                      <TableRow key={item.product_code}>
                        <TableCell>
                          <div className="font-medium">{item.product_name || item.product_code}</div>
                          <div className="text-xs text-muted-foreground">{item.product_code}</div>
                        </TableCell>
                        <TableCell>{outputKindLabel(item.output_kind)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.total_standard_qty, 2)}</TableCell>
                        <TableCell>{item.standard_unit || "-"}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.selected_price, 4)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.selected_output_value, 2)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.total_kgce, 2)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.kgce_per_10k_value, 4)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.record_count, 0)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </PageSection>
        </TabsContent>

        <TabsContent value="hierarchy" className="space-y-4">
          <PageSection>
            <AdminPanel title="区域设备层级" contentClassName="p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="min-w-[320px]">对象</TableHead>
                      <TableHead className="w-[180px]">占比</TableHead>
                      <TableHead className="text-right">综合能耗(tce)</TableHead>
                      <TableHead className="text-right">外购电力(kWh)</TableHead>
                      <TableHead className="text-right">记录数</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {hierarchyRows.map((row) => {
                      const share = totalHierarchyTce > 0 ? Math.max(0, Math.min(100, (row.total_tce / totalHierarchyTce) * 100)) : 0
                      const isExpanded = expandedHierarchy[row.id]
                      return (
                        <TableRow key={row.id} className={row.level === 0 ? "bg-muted/50 font-medium" : row.level === 1 ? "bg-muted/20" : "text-muted-foreground"}>
                          <TableCell>
                            <div className="flex items-center gap-2" style={{ paddingLeft: `${row.level * 28}px` }}>
                              {row.hasChildren ? (
                                <Button variant="ghost" size="icon" className="size-7" onClick={() => toggleHierarchyNode(row.id)}>
                                  {isExpanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                                </Button>
                              ) : (
                                <span className="size-7" />
                              )}
                              <span className="rounded border border-border/70 px-2 py-0.5 text-xs text-muted-foreground">{row.type}</span>
                              <span className="min-w-0">
                                <span className={row.level === 2 ? "block truncate font-normal" : "block truncate font-medium"}>{row.name}</span>
                                {row.subtitle ? <span className="block truncate text-xs font-normal text-muted-foreground">{row.subtitle}</span> : null}
                              </span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-3">
                              <div className="h-2 w-24 overflow-hidden rounded-full bg-muted">
                                <div className="h-full rounded-full bg-primary" style={{ width: `${share}%` }} />
                              </div>
                              <span className="w-12 text-right tabular-nums text-xs text-muted-foreground">{formatEnergyValue(share, 1)}%</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-right tabular-nums">{formatEnergyValue(row.total_tce, 4)}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatEnergyValue(row.electricity_kwh, 2)}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatEnergyValue(row.record_count, 0)}</TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </PageSection>
        </TabsContent>

        <TabsContent value="trend" className="space-y-4">
          <PageSection>
            <CompositeTrendChart
              title="综合能耗和面积折标强度趋势"
              points={intensityTrendSeries}
              bars={[{ key: "total_tce", label: "综合能耗", colorKey: "energy" }]}
              lines={[{ key: "store_area_kgce_per_m2", label: "仓储面积折标强度", colorKey: "scope2", yAxisIndex: 1 }]}
              leftAxisName="tce"
              rightAxisName="kgce/㎡"
              height={360}
            />
          </PageSection>
          <PageSection>
            <CompositeTrendChart
              title="外购电力专项强度趋势"
              points={trend?.series ?? []}
              bars={[{ key: "electricity_kwh", label: "外购电力", colorKey: "electricity" }]}
              lines={[{ key: "store_area_kwh_per_m2", label: "仓储面积电力强度", colorKey: "energy", yAxisIndex: 1 }]}
              leftAxisName="kWh"
              rightAxisName="kWh/㎡"
              height={320}
            />
          </PageSection>
        </TabsContent>
      </AdminPageScaffold>
    </Tabs>
  )
}

export function EnergyAnalysisPanel({ header }: { header?: ReactNode }) {
  const [filters, setFilters] = useState<EnergyAnalysisFilterState>(defaultEnergyAnalysisFilters)
  const [appliedFilters, setAppliedFilters] = useState<EnergyAnalysisFilterState>(defaultEnergyAnalysisFilters)

  const analysisParams = useMemo(() => {
    return buildEnergyAnalysisSearchParams(appliedFilters, {
      includeGranularity: true,
      includeAreaKeyword: true,
      includeEquipmentId: true,
      includeUseSystem: true,
      includeTariff: true,
    })
  }, [appliedFilters])

  const strategyParams = useMemo(() => {
    return buildEnergyAnalysisSearchParams(appliedFilters, {
      includeGranularity: true,
      includeAreaKeyword: true,
      includeEquipmentId: true,
      includeUseSystem: true,
      includeTariff: true,
    })
  }, [appliedFilters])

  const summaryQuery = useQuery<ApiEnvelope<EnergyAnalysisSummary>>({
    queryKey: ["energy", "analysis", "summary", appliedFilters],
    queryFn: () => fetchCarbonApi<EnergyAnalysisSummary>(`/api/energy/analysis/summary?${analysisParams.toString()}`),
  })
  const anomaliesQuery = useQuery<ApiEnvelope<EnergyAnalysisAnomalies>>({
    queryKey: ["energy", "analysis", "anomalies", appliedFilters],
    queryFn: () => fetchCarbonApi<EnergyAnalysisAnomalies>(`/api/energy/analysis/anomalies?${strategyParams.toString()}`),
  })
  const strategiesQuery = useQuery<ApiEnvelope<EnergyAnalysisStrategies>>({
    queryKey: ["energy", "analysis", "strategies", appliedFilters],
    queryFn: () => fetchCarbonApi<EnergyAnalysisStrategies>(`/api/energy/analysis/strategies?${strategyParams.toString()}`),
  })

  const summary = summaryQuery.data?.data
  const anomalies = anomaliesQuery.data?.data
  const strategies = strategiesQuery.data?.data
  function applyFilters() {
    setAppliedFilters(filters)
  }

  function resetFilters() {
    setFilters(defaultEnergyAnalysisFilters)
    setAppliedFilters(defaultEnergyAnalysisFilters)
  }

  return (
    <Tabs defaultValue="structure" className="space-y-4">
      <AdminPageScaffold
        header={header}
        tabs={
          <AdminTabsList>
            <TabsTrigger value="structure">结构分析</TabsTrigger>
            <TabsTrigger value="cost">成本分析</TabsTrigger>
            <TabsTrigger value="performance">能效分析</TabsTrigger>
            <TabsTrigger value="anomaly">异常诊断</TabsTrigger>
            <TabsTrigger value="strategy">策略建议</TabsTrigger>
          </AdminTabsList>
        }
        filters={
          <EnergyAnalysisFilterBar
            filters={filters}
            onFiltersChange={setFilters}
            onApply={applyFilters}
            onReset={resetFilters}
            fields={["periodPreset", "period", "granularity", "energyType", "area", "device", "useSystem", "tariff", "areaKeyword"]}
            defaultVisibleCount={9}
            loading={summaryQuery.isFetching || anomaliesQuery.isFetching || strategiesQuery.isFetching}
          />
        }
        meta={<EnergyAppliedFilterMeta filters={appliedFilters} />}
      >
        <TabsContent value="structure" className="space-y-4">
          <MetricStrip>
            <MetricTile label="总用电量" value={formatEnergyValue(summary?.totals.total_energy, 2)} unit="kWh" />
            <MetricTile label="用能系统" value={formatEnergyValue(summary?.totals.system_count, 0)} />
            <MetricTile label="设备数" value={formatEnergyValue(summary?.totals.equipment_count, 0)} />
            <MetricTile label="区域数" value={formatEnergyValue(summary?.totals.area_count, 0)} />
          </MetricStrip>
          <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
            <RankingList
              title="用能系统排行"
              items={(summary?.by_system ?? []).map((item) => ({ name: item.use_system_name, value: item.total_energy }))}
              unit="kWh"
              height={360}
            />
            <DistributionChart
              title="用能系统结构"
              items={(summary?.by_system ?? []).map((item) => ({ name: item.use_system_name, value: item.total_energy }))}
              unit="kWh"
              height={360}
            />
          </PageSection>
          <PageSection className="grid gap-4 xl:grid-cols-2">
            <RankingList title="区域用能排行" items={(summary?.by_area ?? []).map((item) => ({ name: item.area_name, value: item.total_energy }))} unit="kWh" />
            <RankingList title="设备用能排行" items={(summary?.by_equipment ?? []).map((item) => ({ name: item.equipment_name, value: item.total_energy }))} unit="kWh" />
          </PageSection>
        </TabsContent>

        <TabsContent value="cost" className="space-y-4">
          <MetricStrip className="xl:grid-cols-3">
            <MetricTile label="估算电费" value={formatEnergyValue(summary?.totals.total_cost, 2)} unit="元" tone="warning" />
            <MetricTile label="平均电价" value={formatEnergyValue(summary?.performance.cost_per_kwh, 4)} unit="元/kWh" />
            <MetricTile label="计费记录" value={formatEnergyValue(summary?.totals.record_count, 0)} />
          </MetricStrip>
          <PageSection className="grid gap-4 xl:grid-cols-2">
            <DistributionChart
              title="分时成本结构"
              items={(summary?.by_tariff ?? []).map((item) => ({ name: tariffLabel[item.tariff_segment_type] ?? item.tariff_segment_type, value: item.total_cost }))}
              unit="元"
            />
            <RankingList
              title="分时电量排行"
              items={(summary?.by_tariff ?? []).map((item) => ({ name: tariffLabel[item.tariff_segment_type] ?? item.tariff_segment_type, value: item.total_energy }))}
              unit="kWh"
            />
          </PageSection>
        </TabsContent>

        <TabsContent value="performance" className="space-y-4">
          <MetricStrip className="xl:grid-cols-3">
            <MetricTile label="运行小时" value={formatEnergyValue(summary?.workload.run_hours, 2)} unit="h" />
            <MetricTile label="单位运行小时电耗" value={formatEnergyValue(summary?.performance.kwh_per_run_hour, 4)} unit="kWh/h" />
            <MetricTile label="作业量记录" value={formatEnergyValue(summary?.workload.record_count, 0)} />
          </MetricStrip>
          <PageSection>
            <CompositeTrendChart
              title="能耗和成本趋势"
              points={summary?.trend ?? []}
              bars={[{ key: "total_energy", label: "电量", colorKey: "electricity" }]}
              lines={[{ key: "total_cost", label: "成本", colorKey: "cost", yAxisIndex: 1 }]}
              leftAxisName="kWh"
              rightAxisName="元"
              height={360}
            />
          </PageSection>
          <PageSection>
            <AdminPanel title="设备能效排行" contentClassName="p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>设备</TableHead>
                      <TableHead>区域</TableHead>
                      <TableHead>用能系统</TableHead>
                      <TableHead className="text-right">用电量(kWh)</TableHead>
                      <TableHead className="text-right">成本(元)</TableHead>
                      <TableHead className="text-right">记录数</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(summary?.by_equipment ?? []).map((item) => (
                      <TableRow key={`${item.equipment_id}-${item.equipment_name}`}>
                        <TableCell>{item.equipment_name}</TableCell>
                        <TableCell>{item.area_name}</TableCell>
                        <TableCell>{item.use_system_name}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.total_energy, 2)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.total_cost, 2)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.record_count, 0)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </PageSection>
        </TabsContent>

        <TabsContent value="anomaly" className="space-y-4">
          <MetricStrip className="xl:grid-cols-2">
            <MetricTile label="异常时段" value={formatEnergyValue(anomalies?.items.length, 0)} tone="danger" />
            <MetricTile label="能源告警" value={formatEnergyValue(anomalies?.alarms.length, 0)} tone="warning" />
          </MetricStrip>
          <PageSection>
            <AdminPanel title="异常时段明细" contentClassName="p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>时段</TableHead>
                      <TableHead>设备</TableHead>
                      <TableHead>区域</TableHead>
                      <TableHead>用能系统</TableHead>
                      <TableHead className="text-right">电量(kWh)</TableHead>
                      <TableHead className="text-right">均值(kWh)</TableHead>
                      <TableHead className="text-right">偏离分</TableHead>
                      <TableHead>类型</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(anomalies?.items ?? []).length === 0 && <AdminTableStateRow colSpan={8}>暂无异常时段</AdminTableStateRow>}
                    {(anomalies?.items ?? []).map((item) => (
                      <TableRow key={`${item.equipment_id}-${item.period_start}`}>
                        <TableCell>{item.period_start}</TableCell>
                        <TableCell>{item.equipment_name}</TableCell>
                        <TableCell>{item.area_name}</TableCell>
                        <TableCell>{item.use_system_name}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.amount, 2)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.avg_amount, 2)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.deviation_score, 2)}</TableCell>
                        <TableCell>{item.anomaly_type}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </PageSection>
        </TabsContent>

        <TabsContent value="strategy" className="space-y-4">
          <MetricStrip>
            <MetricTile label="策略数" value={formatEnergyValue(strategies?.items.length, 0)} />
            <MetricTile label="证据电量" value={formatEnergyValue(strategies?.evidence_summary.total_energy, 2)} unit="kWh" />
            <MetricTile label="证据成本" value={formatEnergyValue(strategies?.evidence_summary.total_cost, 2)} unit="元" tone="warning" />
            <MetricTile label="异常证据" value={formatEnergyValue(strategies?.evidence_summary.anomaly_count, 0)} tone="danger" />
          </MetricStrip>
          <PageSection className="space-y-3">
            {(strategies?.items ?? []).map((item) => (
              <AdminPanel
                key={item.code}
                title={item.title}
                actions={
                  <>
                    <Badge variant="outline">{item.priority}</Badge>
                    <Badge variant="outline">{item.strategy_type}</Badge>
                    <Badge variant="outline">{item.target}</Badge>
                  </>
                }
                contentClassName="grid gap-4 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]"
              >
                <div className="rounded-md border border-border/60">
                  <div className="border-b px-4 py-3 text-sm font-medium">证据</div>
                  <div className="divide-y">
                    {Object.entries(item.evidence).map(([key, value]) => (
                      <div key={`${item.code}-${key}`} className="grid grid-cols-[minmax(0,0.7fr)_minmax(0,1fr)] gap-3 px-4 py-3 text-sm">
                        <span className="text-muted-foreground">{key}</span>
                        <span className="text-right font-medium tabular-nums">{typeof value === "number" ? formatEnergyValue(value, 4) : String(value ?? "-")}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-md border border-border/60">
                  <div className="border-b px-4 py-3 text-sm font-medium">实施步骤</div>
                  <div className="space-y-3 p-4">
                    {item.steps.map((step, index) => (
                      <div key={`${item.code}-${index}`} className="flex gap-3 text-sm">
                        <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs tabular-nums">{index + 1}</span>
                        <span>{step}</span>
                      </div>
                    ))}
                    <div className="border-t pt-3 text-sm font-medium">{item.expected_effect}</div>
                  </div>
                </div>
              </AdminPanel>
            ))}
          </PageSection>
        </TabsContent>
      </AdminPageScaffold>
    </Tabs>
  )
}

export function EnergyFlowPanel({ header }: { header?: ReactNode }) {
  const [filters, setFilters] = useState<EnergyAnalysisFilterState>(defaultEnergyAnalysisFilters)
  const [appliedFilters, setAppliedFilters] = useState<EnergyAnalysisFilterState>(defaultEnergyAnalysisFilters)
  const queryString = useMemo(() => buildEnergyFlowQuery(appliedFilters), [appliedFilters])
  const flowQuery = useQuery<ApiEnvelope<FlowData>>({
    queryKey: ["energy", "flow", "graph", queryString],
    queryFn: () => fetchCarbonApi<FlowData>(`/api/energy/flow/graph${queryString}`),
  })
  const balanceQuery = useQuery<ApiEnvelope<BalanceData>>({
    queryKey: ["energy", "flow", "balance", queryString],
    queryFn: () => fetchCarbonApi<BalanceData>(`/api/energy/flow/balance${queryString}`),
  })
  const lossesQuery = useQuery<ApiEnvelope<EnergyFlowLossData>>({
    queryKey: ["energy", "flow", "losses", queryString],
    queryFn: () => fetchCarbonApi<EnergyFlowLossData>(`/api/energy/flow/losses${queryString}`),
  })
  const reportQuery = useQuery<ApiEnvelope<EnergyFlowReportData>>({
    queryKey: ["energy", "flow", "report", queryString],
    queryFn: () => fetchCarbonApi<EnergyFlowReportData>(`/api/energy/flow/report${queryString}`),
  })
  const summary = flowQuery.data?.data.summary

  return (
    <Tabs defaultValue="graph" className="space-y-4">
      <AdminPageScaffold
        header={header}
        tabs={
          <AdminTabsList>
            <TabsTrigger value="graph">能流图</TabsTrigger>
            <TabsTrigger value="balance">能量平衡表</TabsTrigger>
            <TabsTrigger value="losses">损耗诊断</TabsTrigger>
            <TabsTrigger value="report">分析报告</TabsTrigger>
          </AdminTabsList>
        }
        filters={
          <EnergyAnalysisFilterBar
            filters={filters}
            onFiltersChange={setFilters}
            onApply={() => setAppliedFilters(filters)}
            onReset={() => {
              setFilters(defaultEnergyAnalysisFilters)
              setAppliedFilters(defaultEnergyAnalysisFilters)
            }}
            fields={["periodPreset", "period", "granularity", "energyType", "area", "device", "useSystem", "areaKeyword", "lossThreshold"]}
            defaultVisibleCount={9}
            loading={flowQuery.isFetching || balanceQuery.isFetching || lossesQuery.isFetching || reportQuery.isFetching}
          />
        }
        meta={<EnergyAppliedFilterMeta filters={appliedFilters} />}
      >
        <TabsContent value="graph" className="space-y-4">
          <MetricStrip>
            <EnergyFlowKpi title="计量用电" value={summary?.total_input} unit="kWh" />
            <EnergyFlowKpi title="分项用电" value={summary?.utilized_energy} unit="kWh" />
            <EnergyFlowKpi title="总损耗率" value={summary?.loss_rate_pct} unit="%" />
            <EnergyFlowKpi title="高损耗链路" value={summary?.high_loss_count} unit="条" />
          </MetricStrip>
          <PageSection>
            <FlowGraph
              title={flowQuery.data?.data.title ?? "园区能流图"}
              unit={flowQuery.data?.data.unit}
              nodes={flowQuery.data?.data.nodes ?? []}
              links={flowQuery.data?.data.links ?? []}
              height={640}
            />
          </PageSection>
          <PageSection>
            <RankingList
              title="关键链路贡献"
              items={(flowQuery.data?.data.links ?? []).slice(0, 10).map((item) => ({ name: `${item.source} -> ${item.target}`, value: item.value }))}
              unit="kWh"
              height={320}
            />
          </PageSection>
        </TabsContent>
        <TabsContent value="balance">
          <PageSection className="grid gap-4 xl:grid-cols-2">
            <DiagnosticsPanel
              title="能量平衡表"
              items={(balanceQuery.data?.data.table ?? []).map((item) => ({ label: item.label, value: `${formatEnergyValue(item.value, 4)} ${item.unit}` }))}
            />
            <DiagnosticsPanel title="平衡诊断" items={balanceQuery.data?.data.diagnostics ?? []} />
          </PageSection>
        </TabsContent>
        <TabsContent value="losses">
          <PageSection>
            <AdminPanel title="损耗诊断" contentClassName="p-0">
              <AdminDataTable className="rounded-none border-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>环节</TableHead>
                      <TableHead>对象</TableHead>
                      <TableHead className="text-right">输入(kWh)</TableHead>
                      <TableHead className="text-right">损耗(kWh)</TableHead>
                      <TableHead className="text-right">损耗率</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>建议</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(lossesQuery.data?.data.items ?? []).length === 0 && <AdminTableStateRow colSpan={7}>暂无损耗诊断</AdminTableStateRow>}
                    {(lossesQuery.data?.data.items ?? []).map((item) => (
                      <TableRow key={`${item.stage}-${item.target}`}>
                        <TableCell>{item.stage}</TableCell>
                        <TableCell>{item.target}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.input_amount, 2)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.loss_amount, 2)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatEnergyValue(item.loss_rate_pct, 2)}%</TableCell>
                        <TableCell>
                          <Badge variant={item.status === "high_loss" ? "destructive" : "secondary"}>{item.status === "high_loss" ? "高损耗" : "正常"}</Badge>
                        </TableCell>
                        <TableCell>{item.suggestion}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AdminDataTable>
            </AdminPanel>
          </PageSection>
        </TabsContent>
        <TabsContent value="report">
          <PageSection className="space-y-3">
            {(reportQuery.data?.data.items ?? []).map((item) => (
              <AdminPanel
                key={`${item.title}-${item.target}`}
                title={item.title}
                actions={
                  <>
                    <Badge variant={item.priority === "high" ? "destructive" : "secondary"}>{item.priority}</Badge>
                    <Badge variant="outline">{item.target}</Badge>
                  </>
                }
                contentClassName="grid gap-4 xl:grid-cols-2"
              >
                <div className="rounded-md border border-border/60">
                  <div className="border-b px-4 py-3 text-sm font-medium">证据</div>
                  <div className="divide-y">
                    {Object.entries(item.evidence).map(([key, value]) => (
                      <div key={`${item.title}-${key}`} className="grid grid-cols-2 gap-3 px-4 py-3 text-sm">
                        <span className="text-muted-foreground">{key}</span>
                        <span className="text-right font-medium tabular-nums">{typeof value === "number" ? formatEnergyValue(value, 4) : String(value ?? "-")}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-md border border-border/60">
                  <div className="border-b px-4 py-3 text-sm font-medium">动作</div>
                  <div className="space-y-3 p-4">
                    {item.steps.map((step, index) => (
                      <div key={`${item.title}-${index}`} className="flex gap-3 text-sm">
                        <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs tabular-nums">{index + 1}</span>
                        <span>{step}</span>
                      </div>
                    ))}
                    <div className="border-t pt-3 text-sm font-medium">{item.expected_effect}</div>
                  </div>
                </div>
              </AdminPanel>
            ))}
          </PageSection>
        </TabsContent>
      </AdminPageScaffold>
    </Tabs>
  )
}

function EnergyFlowKpi({ title, value, unit }: { title: string; value?: number | null; unit: string }) {
  return <MetricTile label={title} value={formatEnergyValue(value, 2)} unit={unit} />
}

function buildEnergyFlowQuery(filters: EnergyAnalysisFilterState) {
  const params = buildEnergyAnalysisSearchParams(filters, {
    includeGranularity: true,
    includeAreaKeyword: true,
    includeEquipmentId: true,
    includeUseSystem: true,
    includeLossThreshold: true,
  })
  const text = params.toString()
  return text ? `?${text}` : ""
}
