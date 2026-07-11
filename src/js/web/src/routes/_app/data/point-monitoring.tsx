import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pause, Play, RefreshCw } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { AdminDataTable, AdminFilterBar, AdminPageHeader, AdminPanel, AdminTableStateRow, ChartPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { createTrendChartOption, formatAdminChartNumber } from "@/lib/admin-chart-theme"
import { useAuthStore } from "@/lib/auth"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_app/data/point-monitoring")({
  component: PointMonitoringPage,
})

type ApiEnvelope<T> = {
  code: number
  msg?: string
  data: T
}

type PointSummary = {
  total_points: number
  valid_points: number
  invalid_points: number
  timeout_points: number
  latest_reading_time?: string | null
}

type FilterOption = {
  id: number
  code?: string | null
  name?: string | null
  topic_filter?: string | null
  source_id?: number
}

type PointRow = {
  selection_key: string
  binding_id: number
  equipment_id: number
  equipment_code?: string | null
  equipment_name?: string | null
  sector_name?: string | null
  point_code: string
  point_name: string
  unit?: string | null
  latest_value?: number | null
  raw_value?: string | null
  latest_reading_time?: string | null
  quality_status: string
  source_message_id: number
  gateway_key: string
  meter_key: string
  temporary_address?: string | null
  identity_status: string
  source_id: number
  source_code?: string | null
  source_name?: string | null
  subscription_id: number
  topic_filter?: string | null
  source_point_code: string
  source_point_name?: string | null
  mapping_version: string
}

type PointsPayload = {
  items: PointRow[]
  summary: PointSummary
  filter_options: {
    sources: FilterOption[]
    subscriptions: FilterOption[]
    equipment: FilterOption[]
  }
  total: number
  limit: number
  offset: number
}

type SeriesRow = {
  id: number
  reading_time?: string | null
  normalized_value?: number | null
  raw_value?: string | null
  quality_status: string
  unit?: string | null
  source_message_id: number
}

type SeriesPayload = {
  items: SeriesRow[]
  total: number
  limit: number
  binding_id: number
  source_point_code: string
  mapping_version: string
}

async function fetchApi<T>(url: string) {
  const res = await fetch(url)
  const text = await res.text()
  const raw = text ? JSON.parse(text) : {}
  if (!res.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${res.status}`)
  }
  return raw as ApiEnvelope<T>
}

function buildQuery(params: Record<string, string | number | undefined>) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value))
  }
  return query.toString()
}

function formatDateTime(value?: string | null) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
}

function formatFullDateTime(value?: string | null) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

function formatValue(value?: number | null) {
  return value === null || value === undefined ? "-" : formatAdminChartNumber(value, 4)
}

function qualityLabel(status: string) {
  if (status === "valid") return "有效"
  if (status === "invalid") return "无效"
  return status || "-"
}

function identityLabel(status: string) {
  if (status === "temporary") return "临时地址"
  if (status === "verified") return "已确认"
  return status || "-"
}

function QualityBadge({ status }: { status: string }) {
  const invalid = status !== "valid"
  return (
    <Badge
      variant={invalid ? "destructive" : "secondary"}
      className={cn(!invalid && "border-[hsl(var(--status-success))]/30 bg-[hsl(var(--status-success))]/10 text-[hsl(var(--status-success-foreground-admin))]")}
    >
      {qualityLabel(status)}
    </Badge>
  )
}

function PointMonitoringPage() {
  const currentTeam = useAuthStore((state) => state.currentTeam)
  const [keyword, setKeyword] = useState("")
  const [appliedKeyword, setAppliedKeyword] = useState("")
  const [equipmentId, setEquipmentId] = useState("all")
  const [qualityStatus, setQualityStatus] = useState("all")
  const [sourceId, setSourceId] = useState("all")
  const [subscriptionId, setSubscriptionId] = useState("all")
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const pointsQuery = useQuery({
    queryKey: ["iot-monitoring", "points", appliedKeyword, equipmentId, qualityStatus, sourceId, subscriptionId],
    queryFn: () =>
      fetchApi<PointsPayload>(
        `/api/iot-monitoring/points?${buildQuery({
          keyword: appliedKeyword.trim() || undefined,
          equipment_id: equipmentId === "all" ? undefined : equipmentId,
          quality_status: qualityStatus === "all" ? undefined : qualityStatus,
          source_id: sourceId === "all" ? undefined : sourceId,
          subscription_id: subscriptionId === "all" ? undefined : subscriptionId,
          limit: 100,
        })}`,
      ),
    refetchInterval: autoRefresh ? 60_000 : false,
  })

  const points = pointsQuery.data?.data.items ?? []
  const summary = pointsQuery.data?.data.summary ?? {
    total_points: 0,
    valid_points: 0,
    invalid_points: 0,
    timeout_points: 0,
    latest_reading_time: null,
  }
  const selectedPoint = points.find((point) => point.selection_key === selectedKey) ?? null

  useEffect(() => {
    if (points.length === 0) {
      setSelectedKey(null)
      return
    }
    if (!selectedKey || !points.some((point) => point.selection_key === selectedKey)) {
      setSelectedKey(points[0]?.selection_key ?? null)
    }
  }, [points, selectedKey])

  const seriesQuery = useQuery({
    queryKey: ["iot-monitoring", "point-series", selectedPoint?.selection_key],
    queryFn: () =>
      fetchApi<SeriesPayload>(
        `/api/iot-monitoring/point-series?${buildQuery({
          binding_id: selectedPoint?.binding_id,
          source_point_code: selectedPoint?.source_point_code,
          mapping_version: selectedPoint?.mapping_version,
          limit: 500,
        })}`,
      ),
    enabled: selectedPoint !== null,
    refetchInterval: autoRefresh ? 60_000 : false,
  })

  const chartPoints = useMemo(
    () =>
      (seriesQuery.data?.data.items ?? [])
        .filter((item) => item.normalized_value !== null && item.normalized_value !== undefined)
        .map((item) => ({
          period: formatDateTime(item.reading_time),
          value: item.normalized_value ?? 0,
        })),
    [seriesQuery.data?.data.items],
  )
  const trendOption = useMemo(
    () =>
      createTrendChartOption(chartPoints, [{ key: "value", label: selectedPoint?.point_name ?? "点位值", colorKey: "energy" }], {
        periodKey: "period",
        includeZeroSeries: true,
      }),
    [chartPoints, selectedPoint?.point_name],
  )
  const recentRows = useMemo(() => [...(seriesQuery.data?.data.items ?? [])].slice(-20).reverse(), [seriesQuery.data?.data.items])
  const filters = pointsQuery.data?.data.filter_options

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader
        title="点位监测"
        meta={
          <>
            <span>{currentTeam?.name ?? "当前租户"}</span>
            <span>最新采集 {formatFullDateTime(summary.latest_reading_time)}</span>
            <span>{autoRefresh ? "自动刷新 60 秒" : "自动刷新已暂停"}</span>
          </>
        }
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void pointsQuery.refetch()} disabled={pointsQuery.isFetching}>
              <RefreshCw className={cn("h-4 w-4", pointsQuery.isFetching && "animate-spin")} />
              刷新
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setAutoRefresh((value) => !value)}>
              {autoRefresh ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              {autoRefresh ? "暂停" : "恢复"}
            </Button>
          </>
        }
      />

      <AdminFilterBar
        fields={[
          { key: "keyword", node: <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索设备、点位、来源编码" /> },
          {
            key: "equipment",
            node: (
              <Select value={equipmentId} onValueChange={setEquipmentId}>
                <SelectTrigger>
                  <SelectValue placeholder="设备" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部设备</SelectItem>
                  {(filters?.equipment ?? []).map((item) => (
                    <SelectItem key={item.id} value={String(item.id)}>
                      {item.name || item.code || item.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ),
          },
          {
            key: "quality",
            node: (
              <Select value={qualityStatus} onValueChange={setQualityStatus}>
                <SelectTrigger>
                  <SelectValue placeholder="质量状态" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="valid">有效</SelectItem>
                  <SelectItem value="invalid">无效</SelectItem>
                </SelectContent>
              </Select>
            ),
          },
          {
            key: "source",
            node: (
              <Select value={sourceId} onValueChange={setSourceId}>
                <SelectTrigger>
                  <SelectValue placeholder="数据源" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部数据源</SelectItem>
                  {(filters?.sources ?? []).map((item) => (
                    <SelectItem key={item.id} value={String(item.id)}>
                      {item.name || item.code || item.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ),
          },
          {
            key: "subscription",
            node: (
              <Select value={subscriptionId} onValueChange={setSubscriptionId}>
                <SelectTrigger>
                  <SelectValue placeholder="订阅" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部订阅</SelectItem>
                  {(filters?.subscriptions ?? [])
                    .filter((item) => sourceId === "all" || String(item.source_id) === sourceId)
                    .map((item) => (
                      <SelectItem key={item.id} value={String(item.id)}>
                        {item.topic_filter || item.id}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            ),
          },
        ]}
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setAppliedKeyword(keyword)
              }}
              disabled={pointsQuery.isFetching}
            >
              查询
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setKeyword("")
                setAppliedKeyword("")
                setEquipmentId("all")
                setQualityStatus("all")
                setSourceId("all")
                setSubscriptionId("all")
              }}
            >
              重置
            </Button>
          </>
        }
      />

      <MetricStrip className="md:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="总点位" value={summary.total_points} unit="个" meta="映射后点位" />
        <MetricTile label="有效点位" value={summary.valid_points} unit="个" tone="success" />
        <MetricTile label="无效点位" value={summary.invalid_points} unit="个" tone={summary.invalid_points > 0 ? "danger" : "default"} />
        <MetricTile label="超时未更新" value={summary.timeout_points} unit="个" tone={summary.timeout_points > 0 ? "warning" : "default"} />
      </MetricStrip>

      <PageSection className="grid gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
        <AdminPanel title="点位列表" contentClassName="p-0">
          <div className="h-[620px] overflow-y-auto p-3">
            {pointsQuery.isLoading && <div className="py-12 text-center text-muted-foreground text-sm">正在加载点位...</div>}
            {pointsQuery.isError && <div className="py-12 text-center text-destructive text-sm">点位加载失败，请稍后重试。</div>}
            {!pointsQuery.isLoading && !pointsQuery.isError && points.length === 0 && (
              <div className="py-12 text-center text-muted-foreground text-sm">当前筛选条件下没有点位。</div>
            )}
            <div className="space-y-2">
              {points.map((point) => (
                <button
                  key={point.selection_key}
                  type="button"
                  onClick={() => setSelectedKey(point.selection_key)}
                  className={cn(
                    "w-full rounded-md border px-3 py-3 text-left transition-colors",
                    selectedKey === point.selection_key ? "border-primary/45 bg-primary/5" : "border-border/70 bg-background hover:bg-accent/45",
                  )}
                >
                  <div className="flex min-w-0 items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-sm">{point.point_name}</div>
                      <div className="mt-0.5 truncate text-muted-foreground text-xs">
                        {point.equipment_name || point.equipment_code || "-"} · {point.sector_name || "未分区"}
                      </div>
                    </div>
                    <QualityBadge status={point.quality_status} />
                  </div>
                  <div className="mt-3 flex items-end justify-between gap-3">
                    <div className="min-w-0">
                      <span className="font-semibold text-lg tabular-nums">{formatValue(point.latest_value)}</span>
                      {point.unit && <span className="ml-1 text-muted-foreground text-xs">{point.unit}</span>}
                    </div>
                    <span className="shrink-0 text-muted-foreground text-xs">{formatDateTime(point.latest_reading_time)}</span>
                  </div>
                  <div className="mt-2 truncate text-muted-foreground text-xs">
                    {point.source_point_code} · {identityLabel(point.identity_status)}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </AdminPanel>

        <div className="space-y-4">
          <ChartPanel
            title={selectedPoint?.point_name ?? "点位趋势"}
            unit={selectedPoint?.unit ?? undefined}
            source={selectedPoint?.source_name || selectedPoint?.source_code || undefined}
            updatedAt={formatFullDateTime(selectedPoint?.latest_reading_time)}
            option={trendOption}
            height={320}
            emptyLabel={selectedPoint ? "暂无时序数据" : "请选择点位"}
          />

          <AdminPanel
            title="最近读数"
            actions={
              selectedPoint ? (
                <div className="text-muted-foreground text-xs">
                  {selectedPoint.source_point_code} · 消息 {selectedPoint.source_message_id}
                </div>
              ) : null
            }
          >
            <AdminDataTable className="rounded-none border-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>时间</TableHead>
                    <TableHead className="text-right">标准值</TableHead>
                    <TableHead>原始值</TableHead>
                    <TableHead>质量</TableHead>
                    <TableHead className="text-right">来源消息</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {seriesQuery.isLoading && <AdminTableStateRow colSpan={5}>正在加载读数...</AdminTableStateRow>}
                  {seriesQuery.isError && (
                    <AdminTableStateRow colSpan={5} tone="danger">
                      读数加载失败，请稍后重试。
                    </AdminTableStateRow>
                  )}
                  {!seriesQuery.isLoading && !seriesQuery.isError && recentRows.length === 0 && <AdminTableStateRow colSpan={5}>暂无读数</AdminTableStateRow>}
                  {!seriesQuery.isLoading &&
                    !seriesQuery.isError &&
                    recentRows.map((row) => (
                      <TableRow key={row.id}>
                        <TableCell>{formatFullDateTime(row.reading_time)}</TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatValue(row.normalized_value)}
                          {row.unit ? ` ${row.unit}` : ""}
                        </TableCell>
                        <TableCell>{row.raw_value ?? "-"}</TableCell>
                        <TableCell>
                          <QualityBadge status={row.quality_status} />
                        </TableCell>
                        <TableCell className="text-right">{row.source_message_id}</TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </AdminDataTable>
          </AdminPanel>

          {selectedPoint && (
            <AdminPanel title="来源追溯">
              <div className="grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
                <TraceItem label="设备编码" value={selectedPoint.equipment_code} />
                <TraceItem label="网关" value={selectedPoint.gateway_key} />
                <TraceItem label="电表选择" value={selectedPoint.meter_key} />
                <TraceItem label="来源名称" value={selectedPoint.source_point_name} />
                <TraceItem label="临时地址" value={selectedPoint.temporary_address} />
                <TraceItem label="订阅" value={selectedPoint.topic_filter} />
                <TraceItem label="映射版本" value={selectedPoint.mapping_version} />
                <TraceItem label="来源消息" value={String(selectedPoint.source_message_id)} />
              </div>
            </AdminPanel>
          )}
        </div>
      </PageSection>
    </PageContainer>
  )
}

function TraceItem({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="min-w-0">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-1 truncate font-medium text-sm">{value || "-"}</div>
    </div>
  )
}
