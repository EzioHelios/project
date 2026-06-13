import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import { useMemo, useState } from "react"
import { AdminPageHeader } from "@/components/admin-ui"
import { type ApiEnvelope, CompositeTrendChart, DistributionChart, FlowGraph, fetchCarbonApi, LedgerTable } from "@/components/carbon/analytics-panels"
import { DetailPanel, JumpLinks, sourceLabel, TraceTimeline } from "@/components/carbon/energy-carbon-center"
import { Button } from "@/components/ui/button"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

type CarbonRecordsPage = {
  items: {
    scope: string
    record_type: string
    record_id: number
    record_label: string
    display_name: string
    period: string
    source_kind?: string
    activity_amount?: number
    activity_unit?: string
    computed_co2e?: number
    status?: string
    factor_source?: string | null
  }[]
  total: number
  summary: {
    total: number
    pending: number
    approved: number
    missing_factor: number
    missing_result: number
    rejected: number
  }
}

type CarbonRecordDetail = {
  record_type: string
  record_label: string
  record_id: number
  source: Record<string, unknown>
  computation: Record<string, unknown>
  audit_logs: Record<string, unknown>[]
}

type CarbonTrend = {
  series: {
    period: string
    carbon_co2e: number
    scope1_co2e: number
    scope2_co2e: number
    scope3_co2e: number
  }[]
}

type CarbonFlow = {
  title: string
  unit: string
  nodes: { id: string; name: string; value?: number; category?: string }[]
  links: { source: string; target: string; value: number }[]
}

export const Route = createFileRoute("/_app/energy-carbon/carbon")({
  beforeLoad: () => {
    throw redirect({ to: "/carbon/accounting" })
  },
  component: CarbonWorkbenchPage,
})

function CarbonWorkbenchPage() {
  const [tab, setTab] = useState("all")
  const [selectedKey, _setSelectedKey] = useState<string | null>(null)

  const recordsQuery = useQuery<ApiEnvelope<CarbonRecordsPage>>({
    queryKey: ["energy-carbon", "carbon", "records"],
    queryFn: () => fetchCarbonApi<CarbonRecordsPage>("/api/energy-carbon/carbon/records?limit=200&offset=0"),
  })
  const trendQuery = useQuery<ApiEnvelope<CarbonTrend>>({
    queryKey: ["energy-carbon", "carbon", "trend"],
    queryFn: () => fetchCarbonApi<CarbonTrend>("/api/energy-carbon/carbon/trend?months=12"),
  })
  const flowQuery = useQuery<ApiEnvelope<CarbonFlow>>({
    queryKey: ["energy-carbon", "carbon", "flow"],
    queryFn: () => fetchCarbonApi<CarbonFlow>("/api/energy-carbon/carbon/flow"),
  })

  const allRows = recordsQuery.data?.data.items ?? []
  const filteredRows = useMemo(() => {
    if (tab === "pending") return allRows.filter((row) => row.status === "pending")
    if (tab === "abnormal") return allRows.filter((row) => row.status === "rejected" || row.computed_co2e === null || row.computed_co2e === undefined)
    if (tab === "missing") return allRows.filter((row) => !row.factor_source || row.computed_co2e === null || row.computed_co2e === undefined)
    return allRows
  }, [allRows, tab])

  const selectedRow = useMemo(() => filteredRows.find((row) => `${row.record_type}:${row.record_id}` === selectedKey) ?? filteredRows[0], [filteredRows, selectedKey])
  const detailQuery = useQuery<ApiEnvelope<CarbonRecordDetail>>({
    queryKey: ["energy-carbon", "carbon", "detail", selectedRow?.record_type, selectedRow?.record_id],
    queryFn: () => fetchCarbonApi<CarbonRecordDetail>(`/api/energy-carbon/carbon/records/${selectedRow?.record_type}/${selectedRow?.record_id}`),
    enabled: Boolean(selectedRow),
  })

  const summary = recordsQuery.data?.data.summary

  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="4xl">
      <AdminPageHeader
        title="碳排放核算"
        actions={
          <JumpLinks
            items={[
              { label: "待审核工作台", to: "/carbon-mgmt/pending" },
              { label: "范围2用电核算", to: "/carbon-mgmt/scope2" },
              { label: "审核日志", to: "/carbon-mgmt/audit" },
            ]}
          />
        }
      />

      <PageSection className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {[
          { label: "总记录", value: summary?.total ?? 0 },
          { label: "待审核", value: summary?.pending ?? 0 },
          { label: "已通过", value: summary?.approved ?? 0 },
          { label: "缺失因子", value: summary?.missing_factor ?? 0 },
          { label: "缺失结果", value: summary?.missing_result ?? 0 },
          { label: "驳回", value: summary?.rejected ?? 0 },
        ].map((item) => (
          <div key={item.label} className="rounded-lg border border-border/60 bg-card px-4 py-4 shadow-sm">
            <div className="text-xs text-muted-foreground">{item.label}</div>
            <div className="mt-2 text-2xl font-semibold">{item.value}</div>
          </div>
        ))}
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)_340px]">
        <CompositeTrendChart
          title="范围级碳排趋势"
          description="看范围1/2/3 的期间波动，确认当前碳排贡献结构。"
          points={trendQuery.data?.data.series ?? []}
          bars={[
            { key: "scope1_co2e", label: "范围1", colorKey: "scope1", stack: "scope" },
            { key: "scope2_co2e", label: "范围2", colorKey: "scope2", stack: "scope" },
            { key: "scope3_co2e", label: "范围3", colorKey: "scope3", stack: "scope" },
          ]}
          lines={[{ key: "carbon_co2e", label: "总碳排", colorKey: "carbon", yAxisIndex: 1 }]}
          leftAxisName="分范围碳排"
          rightAxisName="总碳排"
          height={320}
        />
        <FlowGraph
          title={flowQuery.data?.data.title ?? "碳流图"}
          description="用来源和范围串起核算结果，不再只看孤立表格。"
          unit={flowQuery.data?.data.unit}
          nodes={flowQuery.data?.data.nodes ?? []}
          links={flowQuery.data?.data.links ?? []}
          height={320}
        />
        <div className="grid gap-4">
          <DistributionChart
            title="审核状态构成"
            description="先确认工作量堵在哪。"
            items={[
              { name: "待审核", value: summary?.pending ?? 0 },
              { name: "已通过", value: summary?.approved ?? 0 },
              { name: "缺失因子", value: summary?.missing_factor ?? 0 },
              { name: "缺失结果", value: summary?.missing_result ?? 0 },
              { name: "驳回", value: summary?.rejected ?? 0 },
            ]}
          />
        </div>
      </PageSection>

      <PageSection>
        <div className="rounded-lg border border-border/60 bg-card/60 p-3">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="all">全部账本</TabsTrigger>
              <TabsTrigger value="pending">待审</TabsTrigger>
              <TabsTrigger value="abnormal">异常</TabsTrigger>
              <TabsTrigger value="missing">缺失项</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1.28fr)_380px]">
        <LedgerTable
          title="统一碳账本"
          description="统一看范围、对象、活动量、因子和结果。这里是盘查工作台的主表，不再把 Scope 明细页摆在主入口。"
          rows={filteredRows}
          columns={[
            { key: "scope", label: "范围" },
            { key: "record_label", label: "记录类型" },
            { key: "display_name", label: "对象" },
            { key: "period", label: "期间" },
            { key: "activity_amount", label: "活动量", align: "right" },
            { key: "computed_co2e", label: "CO2e", align: "right" },
            { key: "status", label: "状态" },
          ]}
        />

        <div className="space-y-4">
          <DetailPanel
            title={selectedRow?.display_name || "记录详情"}
            description={selectedRow ? `${selectedRow.record_label} · ${selectedRow.period}` : "请选择一条核算记录"}
            items={[
              { label: "范围", value: selectedRow?.scope },
              { label: "来源", value: sourceLabel(selectedRow?.source_kind) },
              { label: "活动量", value: selectedRow?.activity_amount ? `${selectedRow.activity_amount}${selectedRow.activity_unit ? ` ${selectedRow.activity_unit}` : ""}` : "-" },
              { label: "因子来源", value: selectedRow?.factor_source },
              { label: "碳排结果", value: selectedRow?.computed_co2e },
              { label: "审核状态", value: selectedRow?.status },
            ]}
            footer={
              <Button variant="outline" size="sm" asChild>
                <Link to="/carbon-mgmt/pending">发起 / 继续审核</Link>
              </Button>
            }
          />
          <TraceTimeline
            items={[
              { step: "采集 / 录入", summary: detailQuery.data?.data.record_label, detail: detailQuery.data?.data.source },
              { step: "核算结果", summary: "活动量 / 因子 / CO2e", detail: detailQuery.data?.data.computation },
              { step: "审核留痕", summary: `${detailQuery.data?.data.audit_logs.length ?? 0} 条`, detail: detailQuery.data?.data.audit_logs },
            ]}
          />
        </div>
      </PageSection>
    </PageContainer>
  )
}
