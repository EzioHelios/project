import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import {
  type ApiEnvelope,
  FlowGraph,
  type FlowLink,
  type FlowNode,
  fetchCarbonApi,
  InsightCallout,
  LedgerTable,
  type RankingItem,
  RankingList,
  SectionHeader,
  TrendChart,
} from "@/components/carbon/analytics-panels"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"

type TrendData = {
  series: {
    period: string
    energy_kwh: number
    carbon_co2e: number
    scope2_co2e: number
    source_kind?: string
  }[]
}

type RankingData = {
  latest_month?: string | null
  diagnostics?: { source_kind?: string }
  energy_by_area: RankingItem[]
  alerts_by_area: RankingItem[]
}

type EfficiencyData = {
  latest_month?: string | null
  source_mix: { name: string; energy_kwh: number; carbon_co2e: number; record_count: number }[]
  workflow: { name: string; value: number }[]
  energy_efficiency?: { source_kind?: string; energy_kwh?: number; carbon_co2e?: number; record_count?: number }
  storage?: Record<string, unknown>
}

type FlowData = {
  title: string
  unit: string
  nodes: FlowNode[]
  links: FlowLink[]
  diagnostics?: Record<string, unknown>
}

type LedgerPage = {
  items: Record<string, unknown>[]
}

export const Route = createFileRoute("/_app/carbon/page3")({
  component: CarbonEnergyPage,
})

function CarbonEnergyPage() {
  const trendQuery = useQuery<ApiEnvelope<TrendData>>({
    queryKey: ["carbon", "analytics", "trend", "energy"],
    queryFn: () => fetchCarbonApi<TrendData>("/api/carbon/analytics/trend?months=12"),
  })
  const rankingQuery = useQuery<ApiEnvelope<RankingData>>({
    queryKey: ["carbon", "analytics", "ranking"],
    queryFn: () => fetchCarbonApi<RankingData>("/api/carbon/analytics/ranking"),
  })
  const efficiencyQuery = useQuery<ApiEnvelope<EfficiencyData>>({
    queryKey: ["carbon", "analytics", "efficiency"],
    queryFn: () => fetchCarbonApi<EfficiencyData>("/api/carbon/analytics/efficiency"),
  })
  const energyFlowQuery = useQuery<ApiEnvelope<FlowData>>({
    queryKey: ["carbon", "energy-flow"],
    queryFn: () => fetchCarbonApi<FlowData>("/api/carbon/energy-flow"),
  })
  const ledgerQuery = useQuery<ApiEnvelope<LedgerPage>>({
    queryKey: ["carbon", "ledger", "energy"],
    queryFn: () => fetchCarbonApi<LedgerPage>("/api/carbon/ledger/energy?limit=12&offset=0"),
  })

  const ranking = rankingQuery.data?.data
  const efficiency = efficiencyQuery.data?.data
  const energyFlow = energyFlowQuery.data?.data

  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="能耗分析" title="仓库用能分析" description="统一看电表主来源、区域排行、能流图和 Scope2 能源账本，不再拆成一堆原始 JSON 卡片。" />

      <PageSection className="space-y-4">
        <InsightCallout
          title="当前主来源"
          description={`本页默认把 ${efficiency?.energy_efficiency?.source_kind ?? ranking?.diagnostics?.source_kind ?? "暂无来源"} 作为 Scope2 主链路；账单只作为补录或兜底来源。`}
        />
        <TrendChart
          title="用电与范围2趋势"
          description="同一张图里看主来源用电量与范围2核算结果，便于发现采集与核算是否脱节。"
          points={trendQuery.data?.data.series ?? []}
          lines={[
            { key: "energy_kwh", label: "用电量", color: "#f59e0b" },
            { key: "scope2_co2e", label: "范围2碳排", color: "#2563eb" },
          ]}
        />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-2">
        <RankingList
          title="区域用电排行"
          description={ranking?.latest_month ? `${ranking.latest_month} 账期` : "按当前可用账期"}
          items={ranking?.energy_by_area ?? []}
          unit="kWh"
        />
        <RankingList title="区域预警排行" description="辅助判断用电问题是否集中在同一片区。" items={ranking?.alerts_by_area ?? []} unit="条" />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <FlowGraph
          title={energyFlow?.title ?? "仓库级能流图"}
          description="外部购电 -> 区域 -> 电表 -> Scope2 聚合结果。"
          unit={energyFlow?.unit}
          nodes={energyFlow?.nodes ?? []}
          links={energyFlow?.links ?? []}
        />
        <RankingList
          title="来源占比"
          description="看电表聚合、账单补录以及其它来源在能耗与碳排上的占比。"
          items={(efficiency?.source_mix ?? []).map((item) => ({
            name: item.name,
            value: item.energy_kwh,
          }))}
          unit="kWh"
        />
      </PageSection>

      <PageSection>
        <SectionHeader badge="能耗账本" title="Scope2 能源账本" description="统一查看电表聚合与账单补录，不再让来源页面盖过真正用于核算的主记录。" />
        <LedgerTable
          title="最近 12 条主记录"
          rows={ledgerQuery.data?.data.items ?? []}
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
