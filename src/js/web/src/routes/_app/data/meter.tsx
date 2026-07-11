import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { RefreshCw } from "lucide-react"
import { useMemo, useState } from "react"

import { AdminDataTable, AdminFilterBar, AdminPageHeader, AdminPanel, AdminTableStateRow, ChartPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { createTrendChartOption, formatAdminChartNumber } from "@/lib/admin-chart-theme"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_app/data/meter")({
  component: MeterPage,
})

type ApiEnvelope<T> = {
  code: number
  msg?: string
  data: T
}

type EnergySummary = {
  period: string
  total_kwh: number
  meter_count: number
  sample_count: number
  invalid_meter_count: number
  calc_status: string
}

type TrendRow = {
  period: string
  total_kwh: number
  sample_count: number
}

type RankingRow = {
  id: string
  name: string
  total_kwh: number
  sample_count: number
}

type ReadingRow = {
  id: number
  reading_time?: string | null
  equipment_code?: string | null
  equipment_name?: string | null
  area_name?: string | null
  point_code: string
  point_name: string
  normalized_value?: number | null
  unit?: string | null
  quality_status: string
  source_system: string
}

type LatestPayload = {
  items: ReadingRow[]
  summary: {
    total_points: number
    valid_points: number
    invalid_points: number
    timeout_points: number
    latest_reading_time?: string | null
  }
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

function MeterPage() {
  const [period, setPeriod] = useState("day")
  const [granularity, setGranularity] = useState("hour")
  const [rankingBy, setRankingBy] = useState("equipment")

  const summaryQuery = useQuery({
    queryKey: ["metering", "energy-summary", period],
    queryFn: () => fetchApi<EnergySummary>(`/api/metering/energy/summary?${buildQuery({ period })}`),
    refetchInterval: 60_000,
  })

  const trendQuery = useQuery({
    queryKey: ["metering", "energy-trend", granularity],
    queryFn: () => fetchApi<{ items: TrendRow[] }>(`/api/metering/energy/trend?${buildQuery({ granularity })}`),
    refetchInterval: 60_000,
  })

  const rankingQuery = useQuery({
    queryKey: ["metering", "energy-ranking", period, rankingBy],
    queryFn: () => fetchApi<{ items: RankingRow[] }>(`/api/metering/energy/ranking?${buildQuery({ period, group_by: rankingBy, limit: 10 })}`),
    refetchInterval: 60_000,
  })

  const latestQuery = useQuery({
    queryKey: ["metering", "latest-readings"],
    queryFn: () => fetchApi<LatestPayload>("/api/metering/readings/latest?value_kind=register_index&limit=100"),
    refetchInterval: 60_000,
  })

  const summary = summaryQuery.data?.data
  const latest = latestQuery.data?.data.summary
  const trendRows = trendQuery.data?.data.items ?? []
  const chartData = useMemo(() => trendRows.map((row) => ({ period: formatPeriod(row.period), value: row.total_kwh })), [trendRows])
  const trendOption = useMemo(
    () =>
      createTrendChartOption(chartData, [{ key: "value", label: "用电量", colorKey: "energy" }], {
        periodKey: "period",
        includeZeroSeries: true,
      }),
    [chartData],
  )

  const refreshAll = () => {
    void summaryQuery.refetch()
    void trendQuery.refetch()
    void rankingQuery.refetch()
    void latestQuery.refetch()
  }

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader
        title="电表电量"
        meta={
          <>
            <span>最新采集 {formatDateTime(latest?.latest_reading_time)}</span>
            <span>主口径 正向有功总电能</span>
          </>
        }
        actions={
          <Button variant="outline" size="sm" onClick={refreshAll} disabled={summaryQuery.isFetching || trendQuery.isFetching || latestQuery.isFetching}>
            <RefreshCw className={cn("h-4 w-4", (summaryQuery.isFetching || trendQuery.isFetching || latestQuery.isFetching) && "animate-spin")} />
            刷新
          </Button>
        }
      />

      <AdminFilterBar
        fields={[
          {
            key: "period",
            node: (
              <Select value={period} onValueChange={setPeriod}>
                <SelectTrigger>
                  <SelectValue placeholder="统计周期" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="day">今日</SelectItem>
                  <SelectItem value="week">本周</SelectItem>
                  <SelectItem value="month">本月</SelectItem>
                  <SelectItem value="year">本年</SelectItem>
                </SelectContent>
              </Select>
            ),
          },
          {
            key: "granularity",
            node: (
              <Select value={granularity} onValueChange={setGranularity}>
                <SelectTrigger>
                  <SelectValue placeholder="趋势粒度" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="hour">小时</SelectItem>
                  <SelectItem value="day">日</SelectItem>
                  <SelectItem value="month">月</SelectItem>
                </SelectContent>
              </Select>
            ),
          },
          {
            key: "ranking",
            node: (
              <Select value={rankingBy} onValueChange={setRankingBy}>
                <SelectTrigger>
                  <SelectValue placeholder="排行维度" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="equipment">设备</SelectItem>
                  <SelectItem value="area">区域</SelectItem>
                </SelectContent>
              </Select>
            ),
          },
        ]}
      />

      <MetricStrip className="md:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="用电量" value={formatNumber(summary?.total_kwh)} unit="kWh" meta={periodLabel(period)} />
        <MetricTile label="电表数量" value={summary?.meter_count ?? 0} unit="台" />
        <MetricTile label="采样数" value={summary?.sample_count ?? 0} unit="条" />
        <MetricTile label="异常点位" value={latest?.invalid_points ?? 0} unit="个" tone={(latest?.invalid_points ?? 0) > 0 ? "danger" : "default"} />
      </MetricStrip>

      <PageSection className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <ChartPanel title="用电趋势" unit="kWh" option={trendOption} height={340} emptyLabel={trendQuery.isError ? "趋势加载失败" : "暂无趋势数据"} />

        <AdminPanel title={rankingBy === "area" ? "区域排行" : "设备排行"} contentClassName="p-0">
          <AdminDataTable className="rounded-none border-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名称</TableHead>
                  <TableHead className="text-right">用电量</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rankingQuery.isLoading && <AdminTableStateRow colSpan={2}>正在加载排行...</AdminTableStateRow>}
                {rankingQuery.isError && (
                  <AdminTableStateRow colSpan={2} tone="danger">
                    排行加载失败。
                  </AdminTableStateRow>
                )}
                {!rankingQuery.isLoading && !rankingQuery.isError && (rankingQuery.data?.data.items ?? []).length === 0 && (
                  <AdminTableStateRow colSpan={2}>暂无排行</AdminTableStateRow>
                )}
                {(rankingQuery.data?.data.items ?? []).map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.name || "-"}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(row.total_kwh)} kWh</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AdminDataTable>
        </AdminPanel>
      </PageSection>

      <AdminPanel title="最新读数" contentClassName="p-0">
        <AdminDataTable className="rounded-none border-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>时间</TableHead>
                <TableHead>设备</TableHead>
                <TableHead>区域</TableHead>
                <TableHead>点位</TableHead>
                <TableHead className="text-right">读数</TableHead>
                <TableHead>质量</TableHead>
                <TableHead>来源</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {latestQuery.isLoading && <AdminTableStateRow colSpan={7}>正在加载读数...</AdminTableStateRow>}
              {latestQuery.isError && (
                <AdminTableStateRow colSpan={7} tone="danger">
                  读数加载失败。
                </AdminTableStateRow>
              )}
              {!latestQuery.isLoading && !latestQuery.isError && (latestQuery.data?.data.items ?? []).length === 0 && <AdminTableStateRow colSpan={7}>暂无读数</AdminTableStateRow>}
              {(latestQuery.data?.data.items ?? []).map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{formatDateTime(row.reading_time)}</TableCell>
                  <TableCell>{row.equipment_name || row.equipment_code || "-"}</TableCell>
                  <TableCell>{row.area_name || "未分区"}</TableCell>
                  <TableCell>{row.point_name || row.point_code}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.normalized_value)}
                    {row.unit ? ` ${row.unit}` : ""}
                  </TableCell>
                  <TableCell>
                    <Badge variant={row.quality_status === "valid" ? "secondary" : "destructive"}>{row.quality_status === "valid" ? "有效" : "无效"}</Badge>
                  </TableCell>
                  <TableCell>{sourceLabel(row.source_system)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </AdminDataTable>
      </AdminPanel>
    </PageContainer>
  )
}

function formatNumber(value?: number | null) {
  return value === null || value === undefined ? "0" : formatAdminChartNumber(value, 2)
}

function formatDateTime(value?: string | null) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
}

function formatPeriod(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit" })
}

function periodLabel(value: string) {
  if (value === "week") return "本周"
  if (value === "month") return "本月"
  if (value === "year") return "本年"
  return "今日"
}

function sourceLabel(value: string) {
  if (value === "mqtt_szscada") return "SZSCADA"
  if (value === "yunji") return "云集"
  if (value === "infrared_hw") return "红外"
  return value || "-"
}
