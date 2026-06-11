import { useQuery } from "@tanstack/react-query"
import { useMemo, useState } from "react"

import { type ApiEnvelope, CompositeTrendChart, DiagnosticsPanel, DistributionChart, FlowGraph, fetchCarbonApi, RankingList } from "@/components/carbon/analytics-panels"
import { JumpLinks, sourceLabel } from "@/components/carbon/energy-carbon-center"
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

type EnergyIntensity = {
  latest_month?: string | null
  metrics: { label: string; value: number | null; unit?: string }[]
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

function useEnergyIntensity() {
  return useQuery<ApiEnvelope<EnergyIntensity>>({
    queryKey: ["energy-carbon", "energy", "intensity"],
    queryFn: () => fetchCarbonApi<EnergyIntensity>("/api/energy-carbon/energy/intensity"),
  })
}

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
          <TabsTrigger value="types">能源品种口径</TabsTrigger>
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
                <CardTitle>能源消费事实明细</CardTitle>
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
                <CardTitle>能源品种与折标口径</CardTitle>
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
                <CardTitle>能源单位换算字典</CardTitle>
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
                <CardTitle>导出当前筛选结果</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm text-muted-foreground">导出接口按当前已查询筛选条件生成 CSV，最多返回 5000 条事实明细。</div>
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
  const [months, setMonths] = useState("12")
  const summaryQuery = useEnergySummary()
  const trendQuery = useEnergyTrend(months)
  const intensityQuery = useEnergyIntensity()
  const summary = summaryQuery.data?.data

  return (
    <div className="space-y-6">
      <PageSection className="rounded-lg border border-border/60 bg-card/60 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Select value={months} onValueChange={setMonths}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="时间范围" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="6">近 6 个月</SelectItem>
              <SelectItem value="12">近 12 个月</SelectItem>
              <SelectItem value="24">近 24 个月</SelectItem>
            </SelectContent>
          </Select>
          <JumpLinks items={[{ label: "查看能耗查询", to: "/energy/consumption" }]} />
        </div>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <CompositeTrendChart
          title="能源消费量趋势"
          description="按账期展示能源消费总量，支撑消费量和强度计算口径核对。"
          points={trendQuery.data?.data.series ?? []}
          bars={[{ key: "energy_kwh", label: "总用电量", color: "#fdba74" }]}
          lines={[{ key: "scope2_co2e", label: "范围2碳排", color: "#2563eb", yAxisIndex: 1 }]}
          leftAxisName="电量"
          rightAxisName="碳排"
          height={360}
        />
        <DiagnosticsPanel
          title="强度指标"
          items={[
            { label: "当前账期", value: intensityQuery.data?.data.latest_month || summary?.latest_month || "-" },
            { label: "主来源", value: sourceLabel(summary?.energy_efficiency?.source_kind) },
            ...(intensityQuery.data?.data.metrics ?? []).map((item) => ({
              label: item.label,
              value: item.value === null ? "-" : `${item.value}${item.unit ? ` ${item.unit}` : ""}`,
            })),
          ]}
        />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-2">
        <DistributionChart
          title="能源来源记录结构"
          description="展示不同数据来源在消费量计算中的占比。"
          items={(summary?.source_mix ?? []).map((item) => ({ name: sourceLabel(item.name), value: item.record_count }))}
        />
        <DistributionChart
          title="核算来源碳排结构"
          description="用于说明能源消费强度与碳排强度之间的关系。"
          items={(summary?.carbon_by_type ?? []).map((item) => ({ name: item.name, value: item.value }))}
          unit="kgCO2e"
        />
      </PageSection>
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
          description="趋势页只负责分析，不承载填报。异常发现后跳转到底座台账或告警处置。"
          points={trendQuery.data?.data.series ?? []}
          bars={[{ key: "energy_kwh", label: "总用电量", color: "#fdba74" }]}
          lines={[{ key: "scope2_co2e", label: "范围2碳排", color: "#2563eb", yAxisIndex: 1 }]}
          leftAxisName="电量"
          rightAxisName="碳排"
          height={360}
        />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-3">
        <RankingList title="区域用能排行" description="识别当前高耗片区。" items={filteredEnergyRanking} unit="kWh" height={320} />
        <RankingList title="区域异常排行" description="结合预警数量判断优先排查对象。" items={filteredAlertRanking} unit="条" height={320} />
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
          description="主链路固定为外部购电 -> 区域 -> 电表 -> 核算结果；节点和链路用于钻取能耗来源。"
          unit={flowQuery.data?.data.unit}
          nodes={flowQuery.data?.data.nodes ?? []}
          links={flowQuery.data?.data.links ?? []}
          height={640}
        />
      </PageSection>
      <PageSection>
        <RankingList
          title="关键链路贡献"
          description="优先看能量值最高的链路，快速定位主耗能节点。"
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
