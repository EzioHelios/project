import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import { useMemo, useState } from "react"

import { type ApiEnvelope, DistributionChart, fetchCarbonApi, RankingList, TrendChart } from "@/components/carbon/analytics-panels"
import { DetailPanel, FacetNavigation, IssueSummaryStrip, TraceTimeline } from "@/components/carbon/energy-carbon-center"
import { Button } from "@/components/ui/button"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

type QualityIssue = {
  id: string
  issue_type: string
  severity: string
  module: string
  object_name: string
  period: string
  message: string
  record_type?: string
  record_id?: number
}

type QualityPage = {
  items: QualityIssue[]
  total: number
  summary: Record<string, number>
}

type QualitySummary = {
  summary: Record<string, number>
  by_module: { name: string; value: number }[]
}

type QualityTrend = {
  series: {
    period: string
    alerts_count: number
    handled_count: number
    energy_kwh: number
    carbon_co2e: number
  }[]
}

type TraceData = {
  trace: { step: string; summary?: string | null; detail?: unknown }[]
}

export const Route = createFileRoute("/_app/energy-carbon/quality")({
  beforeLoad: () => {
    throw redirect({ to: "/carbon/verification" })
  },
  component: QualityTracePage,
})

export function QualityTracePage({ embedded = false }: { embedded?: boolean } = {}) {
  const [issueType, setIssueType] = useState("all")
  const [severity, setSeverity] = useState("all")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const summaryQuery = useQuery<ApiEnvelope<QualitySummary>>({
    queryKey: ["energy-carbon", "quality", "summary"],
    queryFn: () => fetchCarbonApi<QualitySummary>("/api/energy-carbon/quality/summary"),
  })
  const trendQuery = useQuery<ApiEnvelope<QualityTrend>>({
    queryKey: ["energy-carbon", "quality", "trend"],
    queryFn: () => fetchCarbonApi<QualityTrend>("/api/energy-carbon/quality/trend?months=12"),
  })
  const issuesQuery = useQuery<ApiEnvelope<QualityPage>>({
    queryKey: ["energy-carbon", "quality", issueType, severity],
    queryFn: () => {
      const params = new URLSearchParams({ issue_type: issueType, severity, limit: "120", offset: "0" })
      return fetchCarbonApi<QualityPage>(`/api/energy-carbon/quality/issues?${params.toString()}`)
    },
  })

  const issues = issuesQuery.data?.data.items ?? []
  const selectedIssue = useMemo(() => issues.find((item) => item.id === selectedId) ?? issues[0], [issues, selectedId])
  const traceQuery = useQuery<ApiEnvelope<TraceData>>({
    queryKey: ["energy-carbon", "trace", selectedIssue?.record_type, selectedIssue?.record_id],
    queryFn: () => fetchCarbonApi<TraceData>(`/api/energy-carbon/trace/${selectedIssue?.record_type}/${selectedIssue?.record_id}`),
    enabled: Boolean(selectedIssue?.record_type && selectedIssue?.record_id),
  })

  const summary = summaryQuery.data?.data.summary ?? {}
  const facetItems = [{ key: "all", label: "全部问题", count: issues.length }, ...Object.entries(summary).map(([key, value]) => ({ key, label: key, count: value }))]

  const actions = (
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" asChild>
        <Link to="/data/meter">查看电表明细</Link>
      </Button>
      <Button variant="outline" asChild>
        <Link to="/carbon/accounting">查看碳排放核算</Link>
      </Button>
    </div>
  )

  const content = (
    <>
      <PageSection>
        <IssueSummaryStrip
          items={[
            { label: "回退来源", value: summary.回退来源 ?? 0, tone: "warning" },
            { label: "缺失聚合", value: summary.缺失聚合 ?? 0, tone: "warning" },
            { label: "采样不足", value: summary.采样不足 ?? 0, tone: "warning" },
            { label: "异常增量", value: summary.异常增量 ?? 0, tone: "warning" },
            { label: "缺失核算结果", value: summary.缺失核算结果 ?? 0, tone: "warning" },
            { label: "缺失因子", value: summary.缺失因子 ?? 0, tone: "warning" },
          ]}
        />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_340px_340px]">
        <TrendChart
          title="质量问题趋势"
          description="不是为了看图，而是为了确认问题是在扩大还是在收敛。"
          points={trendQuery.data?.data.series ?? []}
          lines={[
            { key: "alerts_count", label: "问题数", color: "#dc2626" },
            { key: "handled_count", label: "非高风险问题", color: "#16a34a" },
          ]}
          height={300}
        />
        <DistributionChart title="问题类型构成" description="先看问题集中在哪一类。" items={Object.entries(summary).map(([name, value]) => ({ name, value }))} />
        <RankingList title="影响模块排行" description="优先看对监测、聚合、核算影响最大的模块。" items={summaryQuery.data?.data.by_module ?? []} unit="项" height={300} />
      </PageSection>

      <PageSection className="rounded-lg border border-border/60 bg-card/60 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Select value={issueType} onValueChange={setIssueType}>
            <SelectTrigger>
              <SelectValue placeholder="问题类型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部问题类型</SelectItem>
              {Object.keys(summary).map((key) => (
                <SelectItem key={key} value={key}>
                  {key}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={severity} onValueChange={setSeverity}>
            <SelectTrigger>
              <SelectValue placeholder="风险等级" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部等级</SelectItem>
              <SelectItem value="high">高</SelectItem>
              <SelectItem value="medium">中</SelectItem>
              <SelectItem value="low">低</SelectItem>
            </SelectContent>
          </Select>
          <div className="xl:col-span-2 flex justify-end">
            <Button
              variant="outline"
              onClick={() => {
                setIssueType("all")
                setSeverity("all")
              }}
            >
              重置
            </Button>
          </div>
        </div>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[260px_minmax(0,1.05fr)_380px]">
        <FacetNavigation title="问题分类" items={facetItems} selectedKey={issueType} onSelect={setIssueType} />

        <div className="rounded-lg border border-border/60 bg-card shadow-sm">
          <div className="border-b px-4 py-3 text-sm font-medium">问题记录表</div>
          <div className="space-y-2 p-3">
            {issues.length === 0 && <div className="text-sm text-muted-foreground">当前筛选条件下没有质量问题。</div>}
            {issues.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSelectedId(item.id)}
                className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${
                  selectedIssue?.id === item.id ? "border-primary bg-primary/5" : "border-border/60 bg-card/60 hover:bg-accent/40"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium">{item.object_name}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {item.module} · {item.period || "未标注期间"}
                    </div>
                  </div>
                  <span
                    className={`rounded-full px-2 py-1 text-xs ${item.severity === "high" ? "bg-red-100 text-red-700" : item.severity === "medium" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-700"}`}
                  >
                    {item.severity === "high" ? "高风险" : item.severity === "medium" ? "中风险" : "一般"}
                  </span>
                </div>
                <div className="mt-2 text-sm text-muted-foreground">{item.issue_type}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <DetailPanel
            title={selectedIssue?.issue_type || "问题详情"}
            description={selectedIssue ? "右侧说明影响模块、问题对象和修复去向。" : "请选择一条问题记录"}
            items={[
              { label: "模块", value: selectedIssue?.module },
              { label: "对象", value: selectedIssue?.object_name },
              { label: "期间", value: selectedIssue?.period },
              { label: "问题说明", value: selectedIssue?.message },
              {
                label: "建议去向",
                value:
                  selectedIssue?.module === "核算" ? "优先查看碳盘查与核算" : selectedIssue?.module === "采集" ? "优先查看监测中心 / 电表明细" : "优先查看对应台账或审核工作台",
              },
            ]}
          />
          <TraceTimeline items={traceQuery.data?.data.trace ?? []} />
        </div>
      </PageSection>
    </>
  )

  if (embedded) {
    return content
  }

  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="碳排放管理" title="碳核查支撑" description="围绕数据质量、过程追溯、原始凭证和审核记录组织材料，支撑碳核查、问题整改和材料汇集。" actions={actions} />
      {content}
    </PageContainer>
  )
}
