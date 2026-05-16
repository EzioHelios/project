import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useMemo, useState } from "react"

import { type ApiEnvelope, CompositeTrendChart, DiagnosticsPanel, DistributionChart, fetchCarbonApi, LedgerTable, RankingList } from "@/components/carbon/analytics-panels"
import { JumpLinks, sourceLabel } from "@/components/carbon/energy-carbon-center"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

type EnergySummary = {
  latest_month?: string | null
  energy_by_area: { name: string; value: number }[]
  alerts_by_area: { name: string; value: number }[]
  carbon_by_type: { name: string; value: number }[]
  source_mix: { name: string; energy_kwh: number; carbon_co2e: number; record_count: number }[]
  energy_efficiency?: { source_kind?: string; energy_kwh?: number; carbon_co2e?: number; record_count?: number }
  workflow: { name: string; value: number }[]
  diagnostics: { label: string; value: string | number }[]
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

export const Route = createFileRoute("/_app/energy-carbon/energy")({
  component: EnergyMonitoringPage,
})

function EnergyMonitoringPage() {
  const [months, setMonths] = useState("12")
  const [areaKeyword, setAreaKeyword] = useState("")
  const [sourceFilter, setSourceFilter] = useState("all")

  const summaryQuery = useQuery<ApiEnvelope<EnergySummary>>({
    queryKey: ["energy-carbon", "energy", "summary"],
    queryFn: () => fetchCarbonApi<EnergySummary>("/api/energy-carbon/energy/summary"),
  })
  const trendQuery = useQuery<ApiEnvelope<TrendData>>({
    queryKey: ["energy-carbon", "energy", "trend", months],
    queryFn: () => fetchCarbonApi<TrendData>(`/api/energy-carbon/energy/trend?months=${months}`),
  })
  const intensityQuery = useQuery<ApiEnvelope<EnergyIntensity>>({
    queryKey: ["energy-carbon", "energy", "intensity"],
    queryFn: () => fetchCarbonApi<EnergyIntensity>("/api/energy-carbon/energy/intensity"),
  })

  const summary = summaryQuery.data?.data
  const keyword = areaKeyword.trim()
  const filteredEnergyRanking = useMemo(() => (summary?.energy_by_area ?? []).filter((item) => (!keyword ? true : item.name.includes(keyword))), [keyword, summary?.energy_by_area])
  const filteredAlertRanking = useMemo(() => (summary?.alerts_by_area ?? []).filter((item) => (!keyword ? true : item.name.includes(keyword))), [keyword, summary?.alerts_by_area])
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

  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能碳中心" title="综能监测" description="这一页不做图表拼盘，而是围绕结构、趋势、来源和异常，让能源主管能直接判断当前经营与采集状态。" />

      <PageSection className="rounded-lg border border-border/60 bg-card/60 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <div className="xl:col-span-2">
            <Input value={areaKeyword} onChange={(event) => setAreaKeyword(event.target.value)} placeholder="筛选区域名称" />
          </div>
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
          <div className="xl:col-span-2 flex items-center justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setAreaKeyword("")
                setMonths("12")
                setSourceFilter("all")
              }}
            >
              重置
            </Button>
            <JumpLinks
              items={[
                { label: "查看能流分析", to: "/energy-carbon/flows" },
                { label: "查看电表台账", to: "/data/meter" },
              ]}
            />
          </div>
        </div>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.75fr)]">
        <CompositeTrendChart
          title="用能趋势主图"
          description="总用电量与范围2碳排放在同一张主图里联动展示，用来判断采集、聚合与核算是否同步。"
          points={trendQuery.data?.data.series ?? []}
          bars={[{ key: "energy_kwh", label: "总用电量", color: "#fdba74" }]}
          lines={[{ key: "scope2_co2e", label: "范围2碳排", color: "#2563eb", yAxisIndex: 1 }]}
          leftAxisName="电量"
          rightAxisName="碳排"
          height={360}
        />
        <div className="grid gap-4">
          <DistributionChart
            title="来源结构"
            description="账本来源和回退来源占比，不让补录与回退隐藏在列表里。"
            items={(summary?.source_mix ?? []).map((item) => ({ name: sourceLabel(item.name), value: item.record_count }))}
          />
          <DiagnosticsPanel
            title="强度与诊断"
            items={[
              { label: "主来源", value: sourceLabel(summary?.energy_efficiency?.source_kind) },
              { label: "当前账期", value: summary?.latest_month || "-" },
              ...(intensityQuery.data?.data.metrics ?? []).map((item) => ({
                label: item.label,
                value: item.value === null ? "-" : `${item.value}${item.unit ? ` ${item.unit}` : ""}`,
              })),
            ]}
          />
        </div>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-4">
        <RankingList title="区域用能排行" description="快速找出当前高耗片区。" items={filteredEnergyRanking} unit="kWh" height={300} />
        <RankingList title="区域异常排行" description="结合预警数量，识别需要优先排查的片区。" items={filteredAlertRanking} unit="条" height={300} />
        <DistributionChart
          title="核算来源碳排结构"
          description="辅助判断当前碳排更集中在哪类记录。"
          items={(summary?.carbon_by_type ?? []).map((item) => ({ name: item.name, value: item.value }))}
          unit="kgCO2e"
          height={300}
        />
        <DiagnosticsPanel
          title="分析结论"
          items={[
            { label: "补录来源占比", value: `${(summary?.source_mix ?? []).find((item) => item.name === "manual_bill")?.record_count ?? 0} 条` },
            { label: "电表聚合来源", value: `${(summary?.source_mix ?? []).find((item) => item.name === "meter_aggregate")?.record_count ?? 0} 条` },
            { label: "高频工作流状态", value: (summary?.workflow ?? []).map((item) => `${item.name}:${item.value}`).join(" / ") || "-" },
            { label: "建议查看", value: keyword ? `优先检查区域“${keyword}”的电表、告警和回退来源` : "优先查看高耗区域与来源占比异常的账本" },
          ]}
        />
      </PageSection>

      <PageSection>
        <LedgerTable
          title="最近主记录账本"
          description="统一展示电表聚合、账单补录和回退来源，用来验证趋势图和结构图背后的真实账本。"
          rows={filteredLedger}
          columns={[
            { key: "source_kind", label: "来源" },
            { key: "display_name", label: "电表 / 户号" },
            { key: "area_name", label: "区域" },
            { key: "period", label: "账期" },
            { key: "total_kwh", label: "总电量", align: "right" },
            { key: "computed_co2e", label: "碳排", align: "right" },
            { key: "status", label: "审核状态" },
          ]}
        />
      </PageSection>
    </PageContainer>
  )
}
