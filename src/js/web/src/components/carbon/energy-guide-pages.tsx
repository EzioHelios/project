import { useQuery } from "@tanstack/react-query"
import { useMemo, useState } from "react"

import {
  type ApiEnvelope,
  CompositeTrendChart,
  DiagnosticsPanel,
  DistributionChart,
  FlowGraph,
  fetchCarbonApi,
  LedgerTable,
  RankingList,
} from "@/components/carbon/analytics-panels"
import { JumpLinks, sourceLabel } from "@/components/carbon/energy-carbon-center"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

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
  const [areaKeyword, setAreaKeyword] = useState("")
  const [sourceFilter, setSourceFilter] = useState("all")
  const summaryQuery = useEnergySummary()
  const summary = summaryQuery.data?.data
  const keyword = areaKeyword.trim()
  const filteredLedger = useMemo(
    () =>
      (summary?.ledger ?? []).filter((row) => {
        const areaName = String(row.area_name ?? "")
        const sourceKind = String(row.source_kind ?? "")
        if (keyword && !areaName.includes(keyword)) return false
        if (sourceFilter !== "all" && sourceKind !== sourceFilter) return false
        return true
      }),
    [keyword, sourceFilter, summary?.ledger],
  )
  const filteredEnergyRanking = useMemo(() => (summary?.energy_by_area ?? []).filter((item) => (!keyword ? true : item.name.includes(keyword))), [keyword, summary?.energy_by_area])

  return (
    <div className="space-y-6">
      <PageSection className="rounded-lg border border-border/60 bg-card/60 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(220px,1fr)_220px_auto]">
          <Input value={areaKeyword} onChange={(event) => setAreaKeyword(event.target.value)} placeholder="筛选区域名称" />
          <Select value={sourceFilter} onValueChange={setSourceFilter}>
            <SelectTrigger>
              <SelectValue placeholder="来源筛选" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部来源</SelectItem>
              <SelectItem value="meter_aggregate">电表聚合</SelectItem>
              <SelectItem value="manual_bill">账单补录</SelectItem>
              <SelectItem value="raw_meter_fallback">明细回退</SelectItem>
            </SelectContent>
          </Select>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setAreaKeyword("")
                setSourceFilter("all")
              }}
            >
              重置
            </Button>
            <JumpLinks items={[{ label: "电表台账", to: "/data/meter" }]} />
          </div>
        </div>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,0.7fr)_minmax(0,1.3fr)]">
        <RankingList title="区域用能排行" description="围绕区域、设备和能源来源进行能耗查询。" items={filteredEnergyRanking} unit="kWh" height={360} />
        <LedgerTable
          title="能耗原始记录"
          description="统一展示电表聚合、账单补录和回退来源，作为能耗查询的主表。"
          rows={filteredLedger}
          columns={[
            { key: "source_kind", label: "来源" },
            { key: "display_name", label: "电表 / 户号" },
            { key: "area_name", label: "区域" },
            { key: "period", label: "账期" },
            { key: "total_kwh", label: "总电量", align: "right" },
            { key: "status", label: "审核状态" },
          ]}
        />
      </PageSection>
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
