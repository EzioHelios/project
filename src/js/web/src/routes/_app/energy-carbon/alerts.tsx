import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"
import { AdminFilterBar, AdminPageHeader, MetricStrip, MetricTile } from "@/components/admin-ui"
import { type ApiEnvelope, CompositeTrendChart, DistributionChart, fetchCarbonApi, RankingList } from "@/components/carbon/analytics-panels"
import { DetailPanel, FacetNavigation, severityLabel, statusBadge } from "@/components/carbon/energy-carbon-center"
import { Button } from "@/components/ui/button"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"

type AlertSummary = {
  total: number
  unhandled: number
  high_risk: number
  today_added: number
  avg_handle_hours: number | null
  by_source: { name: string; value: number }[]
  by_severity: { name: string; value: number }[]
  by_status: { name: string; value: number }[]
  by_area: { name: string; value: number }[]
}

type AlertTrend = {
  series: {
    period: string
    alerts_count: number
    handled_count: number
    energy_kwh: number
    carbon_co2e: number
  }[]
}

type AlertRow = {
  id: string
  source: string
  record_id: number
  record_type?: string
  alert_type: string
  severity: string
  title: string
  area_name?: string
  object_name?: string
  status: string
  occurred_at?: string | null
  description?: string | null
}

type AlertDetail = AlertRow & {
  history: { label: string; value: string | null | undefined }[]
}

export const Route = createFileRoute("/_app/energy-carbon/alerts")({
  component: AlertsCenterPage,
})

function AlertsCenterPage() {
  const queryClient = useQueryClient()
  const [source, setSource] = useState("all")
  const [status, setStatus] = useState("all")
  const [severity, setSeverity] = useState("all")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [handleNote, setHandleNote] = useState("已核实告警来源并完成处置记录。")

  const summaryQuery = useQuery<ApiEnvelope<AlertSummary>>({
    queryKey: ["energy-carbon", "alerts", "summary"],
    queryFn: () => fetchCarbonApi<AlertSummary>("/api/energy-carbon/alerts/summary"),
  })
  const trendQuery = useQuery<ApiEnvelope<AlertTrend>>({
    queryKey: ["energy-carbon", "alerts", "trend"],
    queryFn: () => fetchCarbonApi<AlertTrend>("/api/energy-carbon/alerts/trend?months=12"),
  })
  const alertsQuery = useQuery<ApiEnvelope<{ items: AlertRow[] }>>({
    queryKey: ["energy-carbon", "alerts", source, status, severity],
    queryFn: () => {
      const params = new URLSearchParams({ source, status, severity, limit: "120", offset: "0" })
      return fetchCarbonApi<{ items: AlertRow[] }>(`/api/energy-carbon/alerts?${params.toString()}`)
    },
  })

  const alerts = alertsQuery.data?.data.items ?? []
  const selectedAlert = useMemo(() => alerts.find((item) => item.id === selectedId) ?? alerts[0], [alerts, selectedId])
  const detailQuery = useQuery<ApiEnvelope<AlertDetail>>({
    queryKey: ["energy-carbon", "alerts", "detail", selectedAlert?.id],
    queryFn: () => fetchCarbonApi<AlertDetail>(`/api/energy-carbon/alerts/${selectedAlert?.id}`),
    enabled: Boolean(selectedAlert?.id),
  })

  useEffect(() => {
    if (alerts.length > 0 && !alerts.some((item) => item.id === selectedId)) {
      setSelectedId(alerts[0]?.id ?? null)
    }
    if (alerts.length === 0) {
      setSelectedId(null)
    }
  }, [alerts, selectedId])

  const facetItems = [
    { key: "all", label: "全部告警", count: summaryQuery.data?.data.total ?? 0 },
    ...((summaryQuery.data?.data.by_source ?? []).map((item) => ({
      key: item.name,
      label: item.name === "alarm" ? "设备告警" : item.name === "video" ? "视频告警" : item.name === "carbon" ? "碳告警" : item.name,
      count: item.value,
    })) ?? []),
  ]
  const alertAction = useMutation({
    mutationFn: async ({ action, alert }: { action: "acknowledge" | "work-order" | "close"; alert: AlertDetail }) => {
      const note = handleNote.trim() || "已在告警中心处理。"
      if (action === "acknowledge") {
        return fetchCarbonApi(`/api/mobile/alerts/${encodeURIComponent(alert.id)}/acknowledge`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ note }),
        })
      }
      if (action === "work-order") {
        return fetchCarbonApi(`/api/mobile/alerts/${encodeURIComponent(alert.id)}/transfer-work-order`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ note }),
        })
      }
      const workOrderId = `wo:${alert.source}:${alert.record_id}`
      return fetchCarbonApi(`/api/mobile/work-orders/${encodeURIComponent(workOrderId)}/submit`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ result: note, attachments: [] }),
      })
    },
    onSuccess: async (_result, variables) => {
      toast.success(variables.action === "acknowledge" ? "告警已确认" : variables.action === "work-order" ? "告警已转工单" : "告警已关闭")
      await queryClient.invalidateQueries({ queryKey: ["energy-carbon", "alerts"] })
    },
    onError: (error) => toast.error("处理失败", { description: error instanceof Error ? error.message : "请稍后重试" }),
  })
  const detail = detailQuery.data?.data
  const canHandle = Boolean(detail && detail.status !== "已处理")

  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="4xl">
      <AdminPageHeader title="碳告警与预警" />

      <PageSection>
        <MetricStrip className="md:grid-cols-2 xl:grid-cols-5">
          <MetricTile label="总告警" value={summaryQuery.data?.data.total ?? 0} />
          <MetricTile label="未处理" value={summaryQuery.data?.data.unhandled ?? 0} tone="warning" />
          <MetricTile label="高风险" value={summaryQuery.data?.data.high_risk ?? 0} tone="danger" />
          <MetricTile label="今日新增" value={summaryQuery.data?.data.today_added ?? 0} tone="info" />
          <MetricTile label="平均处理时长" value={summaryQuery.data?.data.avg_handle_hours ?? "-"} unit="h" />
        </MetricStrip>
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_340px_340px]">
        <CompositeTrendChart
          title="告警新增与处理趋势"
          points={trendQuery.data?.data.series ?? []}
          bars={[{ key: "alerts_count", label: "新增告警", colorKey: "danger" }]}
          lines={[{ key: "handled_count", label: "已处理", colorKey: "success", yAxisIndex: 1 }]}
          leftAxisName="新增"
          rightAxisName="处理"
          height={320}
        />
        <DistributionChart title="来源分布" items={summaryQuery.data?.data.by_source ?? []} />
        <DistributionChart title="等级分布" items={(summaryQuery.data?.data.by_severity ?? []).map((item) => ({ name: severityLabel(item.name), value: item.value }))} />
      </PageSection>

      <PageSection>
        <AdminFilterBar
          fields={[
            {
              key: "status",
              node: (
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger>
                    <SelectValue placeholder="处理状态" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部状态</SelectItem>
                    <SelectItem value="待处理">待处理</SelectItem>
                    <SelectItem value="已处理">已处理</SelectItem>
                  </SelectContent>
                </Select>
              ),
            },
            {
              key: "severity",
              node: (
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
              ),
            },
          ]}
          actions={
            <Button
              variant="outline"
              onClick={() => {
                setSource("all")
                setStatus("all")
                setSeverity("all")
              }}
            >
              重置
            </Button>
          }
        />
      </PageSection>

      <PageSection className="grid gap-4 xl:grid-cols-[260px_minmax(0,1.1fr)_380px]">
        <div className="space-y-4">
          <FacetNavigation title="告警分组" items={facetItems} selectedKey={source} onSelect={setSource} />
          <RankingList title="区域集中度" items={summaryQuery.data?.data.by_area ?? []} unit="条" height={280} />
        </div>

        <div className="rounded-lg border border-border/60 bg-card shadow-sm">
          <div className="border-b px-4 py-3 text-sm font-medium">告警列表</div>
          <div className="h-[560px] overflow-y-auto">
            <div className="space-y-2 p-3">
              {alerts.length === 0 && <div className="text-sm text-muted-foreground">当前筛选条件下没有告警。</div>}
              {alerts.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedId(item.id)}
                  className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${
                    selectedAlert?.id === item.id ? "border-primary bg-primary/5" : "border-border/60 bg-card/60 hover:bg-accent/40"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-medium">{item.title}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {item.area_name || "未分区"} · {item.object_name || "未关联对象"}
                      </div>
                    </div>
                    {statusBadge(item.status)}
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                    <span>{item.alert_type}</span>
                    <span>{item.occurred_at || "-"}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <DetailPanel
          title={detail?.title || "处理详情"}
          items={[
            { label: "告警类型", value: detail?.alert_type },
            { label: "风险等级", value: severityLabel(detail?.severity) },
            { label: "状态", value: detail?.status },
            { label: "区域", value: detail?.area_name },
            { label: "对象", value: detail?.object_name },
            { label: "发生时间", value: detail?.occurred_at },
            { label: "说明", value: detail?.description },
          ]}
          footer={
            detail ? (
              <div className="space-y-3">
                <div className="space-y-2 text-sm">
                  {(detail.history ?? []).map((row) => (
                    <div key={row.label} className="flex items-center justify-between gap-3 text-muted-foreground">
                      <span>{row.label}</span>
                      <span className="font-medium text-foreground">{row.value || "-"}</span>
                    </div>
                  ))}
                </div>
                <div className="space-y-2 text-sm">
                  <div className="font-medium">处理说明</div>
                  <Textarea value={handleNote} onChange={(event) => setHandleNote(event.target.value)} className="min-h-24" placeholder="填写确认、转工单或关闭说明" />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => alertAction.mutate({ action: "acknowledge", alert: detail })} disabled={!canHandle || alertAction.isPending}>
                    确认
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => alertAction.mutate({ action: "work-order", alert: detail })} disabled={!canHandle || alertAction.isPending}>
                    转工单
                  </Button>
                  <Button size="sm" onClick={() => alertAction.mutate({ action: "close", alert: detail })} disabled={!canHandle || alertAction.isPending}>
                    关闭
                  </Button>
                </div>
              </div>
            ) : null
          }
        />
      </PageSection>
    </PageContainer>
  )
}
