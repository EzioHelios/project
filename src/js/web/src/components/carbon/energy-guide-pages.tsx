import { useQuery } from "@tanstack/react-query"
import { ChevronDown, ChevronRight } from "lucide-react"
import { useMemo, useState } from "react"

import { type ApiEnvelope, CompositeTrendChart, DiagnosticsPanel, DistributionChart, FlowGraph, fetchCarbonApi, RankingList } from "@/components/carbon/analytics-panels"
import { JumpLinks } from "@/components/carbon/energy-carbon-center"
import { type PageResult, PaginationBar, requestPage } from "@/components/platform/data-admin-pages"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

type EnergySummary = {
  latest_month?: string | null
  energy_by_area: { name: string; value: number }[]
  alerts_by_area: { name: string; value: number }[]
  carbon_by_type: { name: string; value: number }[]
  source_mix: { name: string; energy_kwh: number; carbon_co2e: number; record_count: number }[]
  energy_efficiency?: { source_kind?: string; energy_kwh?: number; carbon_co2e?: number; record_count?: number }
  workflow: { name: string; value: number }[]
  ledger: Record<string, unknown>[]
}

type TrendData = {
  series: {
    period: string
    energy_kwh: number
    scope2_co2e: number
  }[]
}

type FlowData = {
  title: string
  unit: string
  nodes: { id: string; name: string; value?: number; category?: string }[]
  links: { source: string; target: string; value: number }[]
}

type BalanceData = {
  billing_month?: string | null
  table: { label: string; value: number; unit: string }[]
  diagnostics: { label: string; value: string | number }[]
}

type TopLinksData = {
  items: { source: string; target: string; value: number }[]
}

type EnergyFact = {
  source_record_type: string
  source_record_id: number
  scope: string
  emission_category: string
  energy_type_code: string
  energy_type_name: string
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

type EnergyUnitConversionRow = {
  id: number
  energy_type_code: string
  from_unit: string
  to_unit: string
  multiply_factor: number
  standard_code?: string | null
  conversion_factor_source?: string | null
  is_default: boolean
  is_enabled: boolean
  remark?: string | null
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

function useEnergySummary() {
  return useQuery<ApiEnvelope<EnergySummary>>({
    queryKey: ["energy-carbon", "energy", "summary"],
    queryFn: () => fetchCarbonApi<EnergySummary>("/api/energy-carbon/energy/summary"),
  })
}

function useEnergyTrend(months: string) {
  return useQuery<ApiEnvelope<TrendData>>({
    queryKey: ["energy-carbon", "energy", "trend", months],
    queryFn: () => fetchCarbonApi<TrendData>(`/api/energy-carbon/energy/trend?months=${months}`),
  })
}

const formatEnergyValue = (value: number | null | undefined, digits = 4) =>
  value === null || value === undefined ? "-" : Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })

const formatKgcePerM2 = (value: number | null | undefined, digits = 4) => formatEnergyValue(value === null || value === undefined ? null : value * 1000, digits)

export function EnergyConsumptionPanel() {
  const [periodStart, setPeriodStart] = useState("")
  const [periodEnd, setPeriodEnd] = useState("")
  const [scope, setScope] = useState("all")
  const [energyTypeCode, setEnergyTypeCode] = useState("all")
  const [status, setStatus] = useState("all")
  const [areaKeyword, setAreaKeyword] = useState("")
  const [sourceRecordType, setSourceRecordType] = useState("all")
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [appliedFilters, setAppliedFilters] = useState({
    periodStart: "",
    periodEnd: "",
    scope: "all",
    energyTypeCode: "all",
    status: "all",
    areaKeyword: "",
    sourceRecordType: "all",
  })

  const queryParams = useMemo(() => {
    const qs = new URLSearchParams()
    if (appliedFilters.periodStart) qs.set("period_start", appliedFilters.periodStart)
    if (appliedFilters.periodEnd) qs.set("period_end", appliedFilters.periodEnd)
    if (appliedFilters.scope !== "all") qs.set("scope", appliedFilters.scope)
    if (appliedFilters.energyTypeCode !== "all") qs.set("energy_type_code", appliedFilters.energyTypeCode)
    if (appliedFilters.status !== "all") qs.set("status", appliedFilters.status)
    else qs.set("status", "all")
    if (appliedFilters.areaKeyword.trim()) qs.set("area_keyword", appliedFilters.areaKeyword.trim())
    if (appliedFilters.sourceRecordType !== "all") qs.set("source_record_type", appliedFilters.sourceRecordType)
    return qs
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
  const energyTypesQuery = useQuery<ApiEnvelope<{ items: EnergyTypeRow[] }>>({
    queryKey: ["energy", "types"],
    queryFn: () => fetchCarbonApi<{ items: EnergyTypeRow[] }>("/api/energy/types"),
  })
  const unitConversionsQuery = useQuery<ApiEnvelope<{ items: EnergyUnitConversionRow[] }>>({
    queryKey: ["energy", "unit-conversions"],
    queryFn: () => fetchCarbonApi<{ items: EnergyUnitConversionRow[] }>("/api/energy/unit-conversions"),
  })

  const energyTypes = energyTypesQuery.data?.data.items ?? []
  const unitConversions = unitConversionsQuery.data?.data.items ?? []
  const summary = summaryQuery.data?.data
  const facts = factsQuery.data?.items ?? []
  const exportUrl = `/api/energy/consumption/export?${queryParams.toString()}`

  function applyFilters() {
    setAppliedFilters({ periodStart, periodEnd, scope, energyTypeCode, status, areaKeyword, sourceRecordType })
    setPageIndex(0)
  }

  function resetFilters() {
    setPeriodStart("")
    setPeriodEnd("")
    setScope("all")
    setEnergyTypeCode("all")
    setStatus("all")
    setAreaKeyword("")
    setSourceRecordType("all")
    setAppliedFilters({
      periodStart: "",
      periodEnd: "",
      scope: "all",
      energyTypeCode: "all",
      status: "all",
      areaKeyword: "",
      sourceRecordType: "all",
    })
    setPageIndex(0)
  }

  const formatNumber = (value: number | null | undefined, digits = 4) =>
    value === null || value === undefined ? "-" : Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
  const sourceRoute: Record<string, string> = {
    Scope1MobileCombustion: "/carbon-mgmt/scope1-mobile",
    Scope1StationaryCombustion: "/carbon-mgmt/scope1-stationary",
    Scope2ElectricityBill: "/carbon-mgmt/scope2-bill",
    Scope2MeterAggregate: "/carbon-mgmt/scope2-records",
    Scope2PurchasedEnergy: "/carbon-mgmt/scope2-purchased-energy",
  }

  return (
    <div className="space-y-6">
      <PageSection className="rounded-lg border border-border/60 bg-card/60 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[160px_160px_140px_180px_150px_180px_1fr_auto]">
          <Input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} />
          <Input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} />
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
              {energyTypes.map((item) => (
                <SelectItem key={item.code} value={item.code}>
                  {item.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger>
              <SelectValue placeholder="状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="approved">已通过</SelectItem>
              <SelectItem value="pending">待审核</SelectItem>
              <SelectItem value="draft">草稿</SelectItem>
              <SelectItem value="rejected">已驳回</SelectItem>
            </SelectContent>
          </Select>
          <Select value={sourceRecordType} onValueChange={setSourceRecordType}>
            <SelectTrigger>
              <SelectValue placeholder="来源类型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部来源</SelectItem>
              <SelectItem value="Scope1MobileCombustion">Scope1 移动源</SelectItem>
              <SelectItem value="Scope1StationaryCombustion">Scope1 固定源</SelectItem>
              <SelectItem value="Scope2ElectricityBill">Scope2 电费账单</SelectItem>
              <SelectItem value="Scope2MeterAggregate">Scope2 电表聚合</SelectItem>
              <SelectItem value="Scope2PurchasedEnergy">Scope2 外购热/汽/冷</SelectItem>
            </SelectContent>
          </Select>
          <Input value={areaKeyword} onChange={(event) => setAreaKeyword(event.target.value)} placeholder="区域关键字" />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={applyFilters} disabled={summaryQuery.isFetching || factsQuery.isFetching}>
              查询
            </Button>
            <Button variant="outline" onClick={resetFilters}>
              重置
            </Button>
          </div>
        </div>
      </PageSection>

      <Tabs defaultValue="summary" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2 lg:grid-cols-4">
          <TabsTrigger value="summary">汇总查询</TabsTrigger>
          <TabsTrigger value="facts">明细追溯</TabsTrigger>
          <TabsTrigger value="types">能源品种</TabsTrigger>
          <TabsTrigger value="export">导出记录</TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-4">
          <PageSection className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader>
                <CardTitle>记录数</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{summary?.totals.record_count ?? 0}</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>原始消费量</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatNumber(summary?.totals.original_amount)}</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>折标煤</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatNumber(summary?.totals.tce_amount)} tce</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>CO2e</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatNumber(summary?.totals.co2e_amount, 2)} kg</CardContent>
            </Card>
          </PageSection>
          <PageSection>
            <Card>
              <CardHeader>
                <CardTitle>按能源品种汇总</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>能源品种</TableHead>
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
                    {(summary?.items ?? []).length === 0 && (
                      <TableRow>
                        <TableCell colSpan={8} className="h-24 text-center text-muted-foreground">
                          暂无数据
                        </TableCell>
                      </TableRow>
                    )}
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
              </CardContent>
            </Card>
          </PageSection>
        </TabsContent>

        <TabsContent value="facts">
          <PageSection>
            <Card>
              <CardHeader>
                <CardTitle>能源消费明细</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>来源</TableHead>
                      <TableHead>ID</TableHead>
                      <TableHead>Scope</TableHead>
                      <TableHead>能源品种</TableHead>
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
                    {facts.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={12} className="h-24 text-center text-muted-foreground">
                          暂无数据
                        </TableCell>
                      </TableRow>
                    )}
                    {facts.map((row) => (
                      <TableRow key={`${row.source_record_type}-${row.source_record_id}`}>
                        <TableCell>{row.source_record_type}</TableCell>
                        <TableCell>{row.source_record_id}</TableCell>
                        <TableCell>{row.scope}</TableCell>
                        <TableCell>{row.energy_type_name}</TableCell>
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
              </CardContent>
            </Card>
          </PageSection>
        </TabsContent>

        <TabsContent value="types">
          <PageSection>
            <Card>
              <CardHeader>
                <CardTitle>能源品种</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>编码</TableHead>
                      <TableHead>名称</TableHead>
                      <TableHead>类别</TableHead>
                      <TableHead>默认 Scope</TableHead>
                      <TableHead>折标基准单位</TableHead>
                      <TableHead>标准单位</TableHead>
                      <TableHead className="text-right">折标系数</TableHead>
                      <TableHead>标准来源</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {energyTypes.map((item) => (
                      <TableRow key={item.code}>
                        <TableCell>{item.code}</TableCell>
                        <TableCell>{item.name}</TableCell>
                        <TableCell>{item.category}</TableCell>
                        <TableCell>{item.default_scope}</TableCell>
                        <TableCell>{item.original_unit || "-"}</TableCell>
                        <TableCell>{item.standard_unit || "-"}</TableCell>
                        <TableCell className="text-right">{formatNumber(item.standard_factor)}</TableCell>
                        <TableCell>{item.standard_code || "-"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </PageSection>
          <PageSection>
            <Card>
              <CardHeader>
                <CardTitle>单位换算</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>能源品种</TableHead>
                      <TableHead>业务单位</TableHead>
                      <TableHead>折标基准单位</TableHead>
                      <TableHead className="text-right">换算系数</TableHead>
                      <TableHead>来源</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {unitConversions.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                          暂无单位换算数据
                        </TableCell>
                      </TableRow>
                    )}
                    {unitConversions.map((item) => (
                      <TableRow key={`${item.energy_type_code}-${item.from_unit}-${item.to_unit}`}>
                        <TableCell>{energyTypes.find((type) => type.code === item.energy_type_code)?.name ?? item.energy_type_code}</TableCell>
                        <TableCell>{item.from_unit}</TableCell>
                        <TableCell>{item.to_unit}</TableCell>
                        <TableCell className="text-right">{formatNumber(item.multiply_factor, 6)}</TableCell>
                        <TableCell className="max-w-[420px] truncate" title={item.conversion_factor_source || item.remark || ""}>
                          {item.conversion_factor_source || "-"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </PageSection>
        </TabsContent>

        <TabsContent value="export">
          <PageSection>
            <Card>
              <CardHeader>
                <CardTitle>导出</CardTitle>
              </CardHeader>
              <CardContent className="flex justify-end">
                <Button asChild>
                  <a href={exportUrl}>导出 CSV</a>
                </Button>
              </CardContent>
            </Card>
          </PageSection>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export function EnergyIntensityPanel() {
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
    <div className="space-y-6">
      <PageSection className="rounded-lg border border-border/60 bg-card/60 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
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
          <div className="xl:col-span-2">
            <JumpLinks items={[{ label: "查看能耗查询", to: "/energy/consumption" }]} />
          </div>
          <div className="flex justify-end gap-2 xl:col-span-4">
            <Button onClick={applyFilters}>查询</Button>
            <Button variant="outline" onClick={resetFilters}>
              重置
            </Button>
          </div>
        </div>
      </PageSection>

      <Tabs defaultValue="summary" className="space-y-4">
        <TabsList>
          <TabsTrigger value="summary">消费量汇总</TabsTrigger>
          <TabsTrigger value="area">面积强度</TabsTrigger>
          <TabsTrigger value="product">产品强度</TabsTrigger>
          <TabsTrigger value="value">产值强度</TabsTrigger>
          <TabsTrigger value="hierarchy">区域设备</TabsTrigger>
          <TabsTrigger value="trend">趋势分析</TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-4">
          <PageSection className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardHeader>
                <CardTitle>综合能耗</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(summary?.totals.total_tce, 4)} tce</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>折标煤</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(summary?.totals.total_kgce, 2)} kgce</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>外购电力</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(summary?.totals.electricity_kwh, 2)} kWh</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>记录数</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(summary?.totals.record_count, 0)}</CardContent>
            </Card>
          </PageSection>

          <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
            <Card>
              <CardHeader>
                <CardTitle>能源品种汇总</CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
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
              </CardContent>
            </Card>
            <DistributionChart
              title="综合能耗结构"
              items={(summary?.by_energy_type ?? []).map((item) => ({ name: item.energy_type_name, value: item.total_tce }))}
              unit="tce"
              height={360}
            />
          </PageSection>
        </TabsContent>

        <TabsContent value="area" className="space-y-4">
          <PageSection className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardHeader>
                <CardTitle>仓储面积折标强度</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatKgcePerM2(summary?.intensities.store_area_tce_per_m2, 4)} kgce/㎡</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>园区面积折标强度</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatKgcePerM2(summary?.intensities.park_area_tce_per_m2, 4)} kgce/㎡</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>仓储面积电力强度</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(summary?.intensities.store_area_kwh_per_m2, 4)} kWh/㎡</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>园区面积电力强度</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(summary?.intensities.park_area_kwh_per_m2, 4)} kWh/㎡</CardContent>
            </Card>
          </PageSection>
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
          <PageSection className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardHeader>
                <CardTitle>综合能耗</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(productSummary?.energy_totals.total_kgce, 2)} kgce</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>产品产量</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(productSummary?.production_totals.total_good_qty, 2)}</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>标准产量</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(productSummary?.production_totals.total_standard_qty, 2)}</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>覆盖产品</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(productSummary?.production_totals.product_count, 0)}</CardContent>
            </Card>
          </PageSection>
          <PageSection>
            <Card>
              <CardHeader>
                <CardTitle>产品单位强度</CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
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
                    {(productSummary?.items ?? []).length === 0 && (
                      <TableRow>
                        <TableCell colSpan={9} className="h-24 text-center text-muted-foreground">
                          暂无产品批次产量数据
                        </TableCell>
                      </TableRow>
                    )}
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
              </CardContent>
            </Card>
          </PageSection>
        </TabsContent>

        <TabsContent value="value" className="space-y-4">
          <PageSection className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardHeader>
                <CardTitle>综合能耗</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(valueSummary?.energy_totals.total_kgce, 2)} kgce</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>产品产值</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(valueSummary?.output_value_10k, 4)} 万元</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>单位产值综合能耗</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(valueSummary?.kgce_per_10k_value, 4)} kgce/万元</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>缺价格产品</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{formatEnergyValue(valueSummary?.missing_price_products.length, 0)}</CardContent>
            </Card>
          </PageSection>
          <PageSection>
            <Card>
              <CardHeader>
                <CardTitle>产值强度明细</CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
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
                    {(valueSummary?.items ?? []).length === 0 && (
                      <TableRow>
                        <TableCell colSpan={9} className="h-24 text-center text-muted-foreground">
                          暂无产品产值数据
                        </TableCell>
                      </TableRow>
                    )}
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
              </CardContent>
            </Card>
          </PageSection>
        </TabsContent>

        <TabsContent value="hierarchy" className="space-y-4">
          <PageSection>
            <Card>
              <CardHeader>
                <CardTitle>区域设备层级</CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
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
              </CardContent>
            </Card>
          </PageSection>
        </TabsContent>

        <TabsContent value="trend" className="space-y-4">
          <PageSection>
            <CompositeTrendChart
              title="综合能耗和面积折标强度趋势"
              points={intensityTrendSeries}
              bars={[{ key: "total_tce", label: "综合能耗", color: "#d97706" }]}
              lines={[{ key: "store_area_kgce_per_m2", label: "仓储面积折标强度", color: "#0f766e", yAxisIndex: 1 }]}
              leftAxisName="tce"
              rightAxisName="kgce/㎡"
              height={360}
            />
          </PageSection>
          <PageSection>
            <CompositeTrendChart
              title="外购电力专项强度趋势"
              points={trend?.series ?? []}
              bars={[{ key: "electricity_kwh", label: "外购电力", color: "#2563eb" }]}
              lines={[{ key: "store_area_kwh_per_m2", label: "仓储面积电力强度", color: "#7c3aed", yAxisIndex: 1 }]}
              leftAxisName="kWh"
              rightAxisName="kWh/㎡"
              height={320}
            />
          </PageSection>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export function EnergyAnalysisPanel() {
  const [months, setMonths] = useState("12")
  const [areaKeyword, setAreaKeyword] = useState("")
  const summaryQuery = useEnergySummary()
  const trendQuery = useEnergyTrend(months)
  const summary = summaryQuery.data?.data
  const keyword = areaKeyword.trim()
  const filteredEnergyRanking = useMemo(() => (summary?.energy_by_area ?? []).filter((item) => (!keyword ? true : item.name.includes(keyword))), [keyword, summary?.energy_by_area])
  const filteredAlertRanking = useMemo(() => (summary?.alerts_by_area ?? []).filter((item) => (!keyword ? true : item.name.includes(keyword))), [keyword, summary?.alerts_by_area])

  return (
    <div className="space-y-6">
      <PageSection className="rounded-lg border border-border/60 bg-card/60 p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <Input value={areaKeyword} onChange={(event) => setAreaKeyword(event.target.value)} placeholder="筛选区域名称" />
          <Select value={months} onValueChange={setMonths}>
            <SelectTrigger>
              <SelectValue placeholder="时间范围" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="6">近 6 个月</SelectItem>
              <SelectItem value="12">近 12 个月</SelectItem>
              <SelectItem value="24">近 24 个月</SelectItem>
            </SelectContent>
          </Select>
          <div className="flex justify-end">
            <Button
              variant="outline"
              onClick={() => {
                setAreaKeyword("")
                setMonths("12")
              }}
            >
              重置
            </Button>
          </div>
        </div>
      </PageSection>

      <PageSection>
        <CompositeTrendChart
          title="用能趋势分析"
          points={trendQuery.data?.data.series ?? []}
          bars={[{ key: "energy_kwh", label: "总用电量", color: "#fdba74" }]}
          lines={[{ key: "scope2_co2e", label: "范围2碳排", color: "#2563eb", yAxisIndex: 1 }]}
          leftAxisName="电量"
          rightAxisName="碳排"
          height={360}
        />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-3">
        <RankingList title="区域用能排行" items={filteredEnergyRanking} unit="kWh" height={320} />
        <RankingList title="区域异常排行" items={filteredAlertRanking} unit="条" height={320} />
        <DiagnosticsPanel
          title="策略建议"
          items={[
            { label: "补录来源", value: `${(summary?.source_mix ?? []).find((item) => item.name === "manual_bill")?.record_count ?? 0} 条` },
            { label: "电表聚合", value: `${(summary?.source_mix ?? []).find((item) => item.name === "meter_aggregate")?.record_count ?? 0} 条` },
            { label: "审核状态", value: (summary?.workflow ?? []).map((item) => `${item.name}:${item.value}`).join(" / ") || "-" },
            { label: "建议", value: keyword ? `优先检查区域“${keyword}”的电表、告警和回退来源` : "优先检查高耗区域、异常排行和手工补录占比" },
          ]}
        />
      </PageSection>
    </div>
  )
}

export function EnergyFlowPanel() {
  const [billingMonth, setBillingMonth] = useState("")
  const [queryMonth, setQueryMonth] = useState("")
  const flowQuery = useQuery<ApiEnvelope<FlowData>>({
    queryKey: ["energy-carbon", "flows", "energy", queryMonth],
    queryFn: () => fetchCarbonApi<FlowData>(`/api/energy-carbon/flows/energy${queryMonth ? `?billing_month=${queryMonth}` : ""}`),
  })
  const topLinksQuery = useQuery<ApiEnvelope<TopLinksData>>({
    queryKey: ["energy-carbon", "flows", "top-links", queryMonth],
    queryFn: () => fetchCarbonApi<TopLinksData>(`/api/energy-carbon/flows/energy-top-links${queryMonth ? `?billing_month=${queryMonth}` : ""}`),
  })

  return (
    <div className="space-y-6">
      <MonthFilter billingMonth={billingMonth} setBillingMonth={setBillingMonth} onQuery={() => setQueryMonth(billingMonth)} />
      <PageSection>
        <FlowGraph
          title={flowQuery.data?.data.title ?? "仓库 / 园区能流图"}
          unit={flowQuery.data?.data.unit}
          nodes={flowQuery.data?.data.nodes ?? []}
          links={flowQuery.data?.data.links ?? []}
          height={640}
        />
      </PageSection>
      <PageSection>
        <RankingList
          title="关键链路贡献"
          items={(topLinksQuery.data?.data.items ?? []).map((item) => ({ name: `${item.source} -> ${item.target}`, value: item.value }))}
          unit="kWh"
          height={320}
        />
      </PageSection>
    </div>
  )
}

export function EnergyBalancePanel() {
  const [billingMonth, setBillingMonth] = useState("")
  const [queryMonth, setQueryMonth] = useState("")
  const balanceQuery = useQuery<ApiEnvelope<BalanceData>>({
    queryKey: ["energy-carbon", "flows", "balance", queryMonth],
    queryFn: () => fetchCarbonApi<BalanceData>(`/api/energy-carbon/flows/energy-balance${queryMonth ? `?billing_month=${queryMonth}` : ""}`),
  })

  return (
    <div className="space-y-6">
      <MonthFilter billingMonth={billingMonth} setBillingMonth={setBillingMonth} onQuery={() => setQueryMonth(billingMonth)} />
      <PageSection className="grid gap-4 xl:grid-cols-2">
        <DiagnosticsPanel title="能量平衡表" items={(balanceQuery.data?.data.table ?? []).map((item) => ({ label: item.label, value: `${item.value} ${item.unit}` }))} />
        <DiagnosticsPanel
          title="损耗诊断与优化建议"
          items={[...(balanceQuery.data?.data.diagnostics ?? []), { label: "当前账期", value: balanceQuery.data?.data.billing_month || "自动取最近账期" }]}
        />
      </PageSection>
      <PageSection>
        <JumpLinks
          items={[
            { label: "查看能流分析", to: "/energy/flow" },
            { label: "查看电表台账", to: "/data/meter" },
          ]}
        />
      </PageSection>
    </div>
  )
}

function MonthFilter({ billingMonth, setBillingMonth, onQuery }: { billingMonth: string; setBillingMonth: (value: string) => void; onQuery: () => void }) {
  return (
    <PageSection className="rounded-lg border border-border/60 bg-card/60 p-4">
      <div className="grid gap-3 md:grid-cols-[220px_1fr_auto]">
        <Input type="month" value={billingMonth} onChange={(event) => setBillingMonth(event.target.value)} />
        <JumpLinks items={[{ label: "能耗查询", to: "/energy/consumption" }]} />
        <div className="flex justify-end">
          <Button onClick={onQuery}>查询</Button>
        </div>
      </div>
    </PageSection>
  )
}
