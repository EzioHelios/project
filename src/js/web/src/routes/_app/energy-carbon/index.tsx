import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { BellRing, Database, Factory, FileSearch, GitPullRequestArrow, Network } from "lucide-react"

import { type ApiEnvelope, DistributionChart, fetchCarbonApi, GaugeStatCard, KpiStrip, RankingList, TrendComparison } from "@/components/carbon/analytics-panels"
import { HealthMatrix, QuickLinkGrid, TaskList } from "@/components/carbon/energy-carbon-center"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"

type DashboardOverview = {
  latest_month?: string | null
  kpis: { id: string; label: string; value: number; unit?: string; ratio?: number | null }[]
  risk_items: { title: string; area_name?: string; occurred_at?: string | null }[]
  todo_items: { label: string; value: number }[]
  health_matrix: {
    id: number
    name: string
    status: string
    health_ratio?: number
    alert_unhandled?: number
    equipment_online?: number
    equipment_total?: number
  }[]
  completion: {
    carbon_completion_rate: number
    approval_completion_rate: number
    quality_completion_rate: number
    alert_closure_rate: number
  }
  recent_activities: {
    type: string
    title: string
    subtitle?: string | null
    time?: string | null
    status?: string | null
  }[]
}

type TrendData = {
  series: {
    period: string
    energy_kwh: number
    carbon_co2e: number
    scope1_co2e: number
    scope2_co2e: number
    scope3_co2e: number
    alerts_count?: number
  }[]
}

type DashboardHealth = {
  areas: { id: number; name: string; alert_unhandled: number; status: string }[]
}

export const Route = createFileRoute("/_app/energy-carbon/")({
  component: EnergyCarbonOverviewPage,
})

function EnergyCarbonOverviewPage() {
  const overviewQuery = useQuery<ApiEnvelope<DashboardOverview>>({
    queryKey: ["energy-carbon", "dashboard", "overview"],
    queryFn: () => fetchCarbonApi<DashboardOverview>("/api/energy-carbon/dashboard/overview"),
  })
  const trendQuery = useQuery<ApiEnvelope<TrendData>>({
    queryKey: ["energy-carbon", "dashboard", "trend"],
    queryFn: () => fetchCarbonApi<TrendData>("/api/energy-carbon/dashboard/trend?months=12"),
  })
  const healthQuery = useQuery<ApiEnvelope<DashboardHealth>>({
    queryKey: ["energy-carbon", "dashboard", "health"],
    queryFn: () => fetchCarbonApi<DashboardHealth>("/api/energy-carbon/dashboard/health"),
  })

  const overview = overviewQuery.data?.data
  const health = healthQuery.data?.data
  const completion = overview?.completion

  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader
        eyebrow="能碳中心"
        title="经营总览"
        description="先看整体运行，再看风险、待办、区域健康度和核算完整度。首页只回答经营层真正关心的四个问题。"
        actions={overview?.latest_month ? <Badge variant="secondary">当前账期 {overview.latest_month}</Badge> : undefined}
      />

      <PageSection>
        <KpiStrip items={overview?.kpis ?? []} />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(360px,0.95fr)]">
        <TrendComparison title="能碳经营趋势" description="用一张主图同时看总能耗、总碳排与告警数量，先判断本期经营面有没有偏离。" points={trendQuery.data?.data.series ?? []} />
        <div className="grid gap-4">
          <TaskList
            title="风险与待办"
            items={[
              ...(overview?.risk_items ?? []).slice(0, 4).map((item) => ({
                label: item.title,
                value: item.area_name || item.occurred_at || "高风险事件",
                tone: "warning" as const,
              })),
              ...(overview?.todo_items ?? []).slice(0, 3).map((item) => ({
                label: item.label,
                value: `${item.value} 项`,
                tone: "default" as const,
              })),
            ]}
            emptyLabel="当前没有高风险待办"
          />
          <DistributionChart
            title="风险分布"
            description="把经营层真正需要催办的风险压缩成可读分布。"
            items={[
              { name: "高风险事件", value: overview?.risk_items.length ?? 0 },
              { name: "待处理告警", value: overview?.todo_items.find((item) => item.label === "待处理告警")?.value ?? 0 },
              { name: "待审核记录", value: overview?.todo_items.find((item) => item.label === "待审核记录")?.value ?? 0 },
              { name: "质量问题", value: overview?.todo_items.find((item) => item.label === "质量问题")?.value ?? 0 },
            ]}
          />
        </div>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_340px_340px]">
        <HealthMatrix title="区域健康矩阵" description="从设备在线、告警堆积和区域状态三个角度快速找出需要立刻查看的片区。" items={overview?.health_matrix ?? []} />
        <RankingList
          title="区域风险排行"
          description="优先盯住当前告警最集中的片区。"
          items={(health?.areas ?? []).map((item) => ({ name: item.name, value: item.alert_unhandled }))}
          unit="条"
          height={340}
        />
        <div className="grid gap-4">
          <GaugeStatCard title="核算完成率" description="已形成有效碳结果的记录占比。" value={completion?.carbon_completion_rate ?? 0} suffix="%" />
          <GaugeStatCard title="数据完整率" description="当前核算链路可直接消费的数据完整程度。" value={completion?.quality_completion_rate ?? 0} suffix="%" />
        </div>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <QuickLinkGrid
          items={[
            { label: "监测中心", to: "/energy-carbon/monitor", description: "看区域、设备、测点与视频联动状态", icon: Factory },
            { label: "告警中心", to: "/energy-carbon/alerts", description: "集中处理设备、视频与碳告警", icon: BellRing },
            { label: "碳盘查与核算", to: "/energy-carbon/carbon", description: "统一看账本、待审、缺失因子与凭证", icon: GitPullRequestArrow },
            { label: "能流分析", to: "/energy-carbon/flows", description: "看输入、分配、利用与损耗链路", icon: Network },
            { label: "数据质量与追溯", to: "/energy-carbon/quality", description: "快速定位缺失、异常、回退和不可核算记录", icon: FileSearch },
            { label: "因子数据库", to: "/energy-carbon/factors", description: "检查因子口径、版本、适用范围与命中情况", icon: Database },
          ]}
        />
        <Card className="border-border/60 shadow-sm">
          <CardHeader>
            <CardTitle>最近动态</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(overview?.recent_activities ?? []).length === 0 && <div className="text-sm text-muted-foreground">当前没有最近动态。</div>}
            {(overview?.recent_activities ?? []).slice(0, 6).map((item, index) => (
              <div key={`${item.type}-${index}`} className="rounded-lg border border-border/60 bg-card/60 px-3 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">{item.title}</div>
                  <Badge variant="outline">{item.type === "alert" ? "告警" : "核算"}</Badge>
                </div>
                <div className="mt-1 text-sm text-muted-foreground">{item.subtitle || "最近动态"}</div>
                <div className="mt-2 text-xs text-muted-foreground">
                  {item.time || "-"} · {item.status || "未标注"}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}
