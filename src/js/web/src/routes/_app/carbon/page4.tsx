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
  ScopeSummary,
  SectionHeader,
  TrendChart,
} from "@/components/carbon/analytics-panels"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"

type OverviewData = {
  scope_totals: RankingItem[]
  workflow: { pending_count: number; approved_count: number; total_records: number }
}

type TrendData = {
  series: {
    period: string
    carbon_co2e: number
    scope1_co2e: number
    scope2_co2e: number
    scope3_co2e: number
  }[]
}

type RankingData = {
  carbon_by_type: RankingItem[]
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

export const Route = createFileRoute("/_app/carbon/page4")({
  component: CarbonCollaborationPage,
})

function CarbonCollaborationPage() {
  const overviewQuery = useQuery<ApiEnvelope<OverviewData>>({
    queryKey: ["carbon", "analytics", "overview", "page4"],
    queryFn: () => fetchCarbonApi<OverviewData>("/api/carbon/analytics/overview"),
  })
  const trendQuery = useQuery<ApiEnvelope<TrendData>>({
    queryKey: ["carbon", "analytics", "trend", "page4"],
    queryFn: () => fetchCarbonApi<TrendData>("/api/carbon/analytics/trend?months=12"),
  })
  const rankingQuery = useQuery<ApiEnvelope<RankingData>>({
    queryKey: ["carbon", "analytics", "ranking", "page4"],
    queryFn: () => fetchCarbonApi<RankingData>("/api/carbon/analytics/ranking"),
  })
  const flowQuery = useQuery<ApiEnvelope<FlowData>>({
    queryKey: ["carbon", "analytics", "carbon-flow"],
    queryFn: () => fetchCarbonApi<FlowData>("/api/carbon/carbon-flow"),
  })
  const ledgerQuery = useQuery<ApiEnvelope<LedgerPage>>({
    queryKey: ["carbon", "ledger", "carbon"],
    queryFn: () => fetchCarbonApi<LedgerPage>("/api/carbon/ledger/carbon?limit=12&offset=0"),
  })

  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="碳能协同" title="碳排协同分析" description="从范围级趋势、流向和账本三层看碳核算链路是否完整，不再把分析页退化成调试输出。" />

      <PageSection className="space-y-4">
        <InsightCallout title="当前设计口径" description="范围1/3 来自活动记录即时核算，范围2 优先来自电表聚合或账单补录。若没有真实核算记录，碳流图会保持空态而不是伪造结果。" />
        <ScopeSummary items={overviewQuery.data?.data.scope_totals ?? []} />
      </PageSection>

      <PageSection className="space-y-4">
        <SectionHeader badge="趋势" title="范围级碳排趋势" description="把 Scope1 / 2 / 3 摊开看，便于确认哪些环节已经接入了核算，哪些还只是数据占位。" />
        <TrendChart
          title="近 12 个月碳排趋势"
          points={trendQuery.data?.data.series ?? []}
          lines={[
            { key: "carbon_co2e", label: "总碳排", color: "#10b981" },
            { key: "scope1_co2e", label: "范围1", color: "#ef4444" },
            { key: "scope2_co2e", label: "范围2", color: "#3b82f6" },
            { key: "scope3_co2e", label: "范围3", color: "#8b5cf6" },
          ]}
        />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <FlowGraph
          title={flowQuery.data?.data.title ?? "范围级碳流图"}
          description="范围 -> 活动 -> 因子 -> 结果，真实反映当前已打通的核算链路。"
          unit={flowQuery.data?.data.unit}
          nodes={flowQuery.data?.data.nodes ?? []}
          links={flowQuery.data?.data.links ?? []}
        />
        <RankingList
          title="碳排类型排行"
          description="看哪类记录目前对总碳排的贡献最高，也能顺手发现哪个模块录入最完整。"
          items={rankingQuery.data?.data.carbon_by_type ?? []}
          unit="kgCO2e"
        />
      </PageSection>

      <PageSection>
        <SectionHeader badge="核算账本" title="统一碳账本" description="汇总 Scope1/2/3 当前记录，展示活动量、来源、因子和 CO2e 结果。" />
        <LedgerTable
          title="最近 12 条核算记录"
          rows={ledgerQuery.data?.data.items ?? []}
          columns={[
            { key: "scope", label: "范围" },
            { key: "record_label", label: "记录类型" },
            { key: "display_name", label: "对象" },
            { key: "period", label: "期间" },
            { key: "source_kind", label: "来源" },
            { key: "activity_amount", label: "活动量", align: "right" },
            { key: "computed_co2e", label: "碳排", align: "right" },
            { key: "status", label: "审核状态" },
          ]}
        />
      </PageSection>
    </PageContainer>
  )
}
