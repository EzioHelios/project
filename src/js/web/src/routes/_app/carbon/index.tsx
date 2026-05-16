import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import {
  type ApiEnvelope,
  FlowGraph,
  type FlowLink,
  type FlowNode,
  fetchCarbonApi,
  InsightCallout,
  KpiStrip,
  MiniStatList,
  ScopeSummary,
  SectionHeader,
  TrendChart,
} from "@/components/carbon/analytics-panels"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"

type OverviewData = {
  latest_month?: string | null
  enterprise?: Record<string, unknown>
  kpis: { id: string; label: string; value: number; unit?: string; ratio?: number | null }[]
  monitor_stats: { category: string; total: number; online: number; fault: number }[]
  workflow: { pending_count: number; approved_count: number; total_records: number }
  alerts: { alarm_total: number; alarm_unhandled: number; video_alarm_total: number; video_alarm_unhandled: number }
  scope_totals: { name: string; value: number }[]
  source_mix?: { source_kind?: string; energy_kwh?: number; carbon_co2e?: number }
}

type TrendData = {
  months: string[]
  series: {
    period: string
    energy_kwh: number
    scope1_co2e: number
    scope2_co2e: number
    scope3_co2e: number
    carbon_co2e: number
    source_kind?: string
  }[]
}

type FlowData = {
  title: string
  unit: string
  nodes: FlowNode[]
  links: FlowLink[]
  diagnostics?: Record<string, unknown>
}

export const Route = createFileRoute("/_app/carbon/")({
  component: CarbonOverviewPage,
})

function CarbonOverviewPage() {
  const overviewQuery = useQuery<ApiEnvelope<OverviewData>>({
    queryKey: ["carbon", "analytics", "overview"],
    queryFn: () => fetchCarbonApi<OverviewData>("/api/carbon/analytics/overview"),
  })
  const trendQuery = useQuery<ApiEnvelope<TrendData>>({
    queryKey: ["carbon", "analytics", "trend", 12],
    queryFn: () => fetchCarbonApi<TrendData>("/api/carbon/analytics/trend?months=12"),
  })
  const energyFlowQuery = useQuery<ApiEnvelope<FlowData>>({
    queryKey: ["carbon", "analytics", "energy-flow"],
    queryFn: () => fetchCarbonApi<FlowData>("/api/carbon/energy-flow"),
  })
  const carbonFlowQuery = useQuery<ApiEnvelope<FlowData>>({
    queryKey: ["carbon", "analytics", "carbon-flow"],
    queryFn: () => fetchCarbonApi<FlowData>("/api/carbon/carbon-flow"),
  })

  const overview = overviewQuery.data?.data
  const trend = trendQuery.data?.data
  const energyFlow = energyFlowQuery.data?.data
  const carbonFlow = carbonFlowQuery.data?.data

  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="总览工作台" title="仓库能碳运营总览" description="把监测、聚合、核算和审核串成一条可读的数据链路，展示层只消费统一分析 API。" />

      <PageSection>
        <KpiStrip items={overview?.kpis ?? []} />
      </PageSection>

      <PageSection className="space-y-4">
        <SectionHeader badge="数据链路" title="主链路状态" description="先看当前账期的来源口径，再看监测与审核队列是否顺畅。" />
        <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
          <ScopeSummary items={overview?.scope_totals ?? []} />
          <div className="grid gap-4">
            <MiniStatList
              title="监测终端"
              items={(overview?.monitor_stats ?? []).map((item) => ({
                label: item.category,
                value: `${item.online}/${item.total} 在线`,
              }))}
            />
            <MiniStatList
              title="审核与预警"
              items={[
                { label: "待审核记录", value: overview?.workflow?.pending_count ?? 0 },
                { label: "已通过记录", value: overview?.workflow?.approved_count ?? 0 },
                { label: "未处理设备预警", value: overview?.alerts?.alarm_unhandled ?? 0 },
                { label: "未处理视频预警", value: overview?.alerts?.video_alarm_unhandled ?? 0 },
              ]}
            />
          </div>
        </div>
      </PageSection>

      <PageSection className="space-y-4">
        <InsightCallout
          title="当前总览口径"
          description={`当前账期优先使用 ${overview?.source_mix?.source_kind ?? "暂无来源"} 形成用电汇总；若 Scope 核算表为空，碳流图会如实显示为空而不是伪造数据。`}
        />
        <TrendChart
          title="近 12 个月能碳协同趋势"
          description="能耗来自 Scope2 主来源，碳排趋势叠加 Scope1/2/3 当前已纳入核算的结果。"
          points={trend?.series ?? []}
          lines={[
            { key: "energy_kwh", label: "用电量", color: "#f59e0b" },
            { key: "carbon_co2e", label: "总碳排", color: "#10b981" },
            { key: "scope2_co2e", label: "范围2", color: "#3b82f6" },
          ]}
        />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-2">
        <FlowGraph
          title={energyFlow?.title ?? "仓库级能流图"}
          description="外部购电沿区域、电表进入 Scope2 聚合结果；当聚合表为空时，会回退到电表明细月度差值。"
          unit={energyFlow?.unit}
          nodes={energyFlow?.nodes ?? []}
          links={energyFlow?.links ?? []}
        />
        <FlowGraph
          title={carbonFlow?.title ?? "范围级碳流图"}
          description="范围 -> 活动 -> 因子 -> 结果，展示当前核算链路真正落地的排放流向。"
          unit={carbonFlow?.unit}
          nodes={carbonFlow?.nodes ?? []}
          links={carbonFlow?.links ?? []}
        />
      </PageSection>
    </PageContainer>
  )
}
