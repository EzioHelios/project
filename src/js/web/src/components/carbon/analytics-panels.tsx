import { AlertTriangle, ArrowRight, GitBranch, TrendingUp } from "lucide-react"

import { ChartPanel } from "@/components/admin-ui"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  type AdminChartBarSeriesConfig,
  type AdminChartLineSeriesConfig,
  type AdminChartSeriesConfig,
  createComboTrendChartOption,
  createDistributionChartOption,
  createGaugeChartOption,
  createRankingChartOption,
  createSankeyChartOption,
  createTrendChartOption,
  formatAdminChartNumber,
} from "@/lib/admin-chart-theme"
import { cn } from "@/lib/utils"

export type ApiEnvelope<T> = {
  code: number
  msg?: string
  data: T
}

export type KpiItem = {
  id: string
  label: string
  value: number
  unit?: string
  ratio?: number | null
}

export type RankingItem = {
  name: string
  value: number
}

export type TrendPoint = {
  period: string
  energy_kwh?: number
  carbon_co2e?: number
  scope1_co2e?: number
  scope2_co2e?: number
  scope3_co2e?: number
  source_kind?: string
  alerts_count?: number
  handled_count?: number
  total_tce?: number
  total_kgce?: number
  total_co2e?: number
  electricity_kwh?: number
  store_area_tce_per_m2?: number | null
  park_area_tce_per_m2?: number | null
  store_area_kgce_per_m2?: number | null
  park_area_kgce_per_m2?: number | null
  store_area_kwh_per_m2?: number | null
  park_area_kwh_per_m2?: number | null
}

export type FlowNode = {
  id: string
  name: string
  value?: number
  category?: string
}

export type FlowLink = {
  source: string
  target: string
  value: number
}

type DistributionItem = {
  name: string
  value: number
}

type SeriesConfig = AdminChartSeriesConfig<keyof TrendPoint & string>
type BarSeriesConfig = AdminChartBarSeriesConfig<keyof TrendPoint & string>
type LineSeriesConfig = AdminChartLineSeriesConfig<keyof TrendPoint & string>

export async function fetchCarbonApi<T>(url: string) {
  const res = await fetch(url)
  const text = await res.text()
  const raw = text ? JSON.parse(text) : {}
  if (!res.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${res.status}`)
  }
  return raw as ApiEnvelope<T>
}

function ratioText(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—"
  const prefix = value > 0 ? "+" : ""
  return `${prefix}${value.toFixed(1)}%`
}

function sourceLabel(value?: string | null) {
  if (value === "meter_aggregate") return "电表聚合"
  if (value === "historical_estimate") return "历史估算"
  if (value === "manual_bill") return "账单补录"
  if (value === "raw_meter_fallback") return "电表明细回退"
  if (value === "activity_data") return "活动数据"
  if (value === "demo_seed") return "演示样例"
  if (value === "empty") return "暂无来源"
  return value || "未标注"
}

export function KpiStrip({ items }: { items: KpiItem[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
      {items.map((item) => (
        <Card key={item.id} className="border-border/60 shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription>{item.label}</CardDescription>
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="text-3xl font-semibold tabular-nums">{formatAdminChartNumber(item.value)}</CardTitle>
              {item.unit && <Badge variant="secondary">{item.unit}</Badge>}
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <TrendingUp className="h-3.5 w-3.5" />
              <span>{ratioText(item.ratio)}</span>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

export function TrendChart({ title, points, lines, height = 340 }: { title: string; description?: string; points: TrendPoint[]; lines: SeriesConfig[]; height?: number }) {
  return <ChartPanel title={title} option={createTrendChartOption(points, lines)} height={height} emptyLabel="暂无趋势数据" />
}

export function CompositeTrendChart({
  title,
  points,
  bars,
  lines,
  height = 340,
  leftAxisName,
  rightAxisName,
}: {
  title: string
  description?: string
  points: TrendPoint[]
  bars: BarSeriesConfig[]
  lines: LineSeriesConfig[]
  height?: number
  leftAxisName?: string
  rightAxisName?: string
}) {
  return <ChartPanel title={title} option={createComboTrendChartOption(points, { bars, lines, leftAxisName, rightAxisName })} height={height} emptyLabel="暂无趋势数据" />
}

export function RankingList({ title, items, unit, height = 320 }: { title: string; description?: string; items: RankingItem[]; unit?: string; height?: number }) {
  return <ChartPanel title={title} unit={unit} option={createRankingChartOption(items, { unit })} height={height} emptyLabel="暂无排行数据" />
}

export function DistributionChart({ title, items, unit, height = 280 }: { title: string; description?: string; items: DistributionItem[]; unit?: string; height?: number }) {
  return <ChartPanel title={title} unit={unit} option={createDistributionChartOption(items, { unit })} height={height} emptyLabel="暂无分布数据" />
}

export function GaugeStatCard({ title, value, suffix, height = 240 }: { title: string; description?: string; value: number; suffix?: string; height?: number }) {
  return <ChartPanel title={title} unit={suffix} option={createGaugeChartOption(value, { suffix })} height={height} emptyLabel="暂无完成度数据" />
}

export function DiagnosticsPanel({ title, items }: { title: string; items: { label: string; value: string | number | null | undefined }[] }) {
  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <div key={item.label} className="rounded-md border border-border/60 bg-card/70 px-3 py-2">
            <div className="text-xs text-muted-foreground">{item.label}</div>
            <div className="mt-1 text-sm font-medium">{item.value === null || item.value === undefined || item.value === "" ? "-" : String(item.value)}</div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

export function FlowGraph({
  title,
  unit,
  nodes,
  links,
  height = 620,
}: {
  title: string
  description?: string
  unit?: string
  nodes: FlowNode[]
  links: FlowLink[]
  height?: number
}) {
  return <ChartPanel title={title} unit={unit} option={createSankeyChartOption(nodes, links)} height={height} emptyLabel="暂无流向数据" />
}

export function LedgerTable({
  title,
  description,
  rows,
  columns,
}: {
  title: string
  description?: string
  rows: Record<string, unknown>[]
  columns: { key: string; label: string; align?: "left" | "right" }[]
}) {
  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((column) => (
                <TableHead key={column.key} className={column.align === "right" ? "text-right" : undefined}>
                  {column.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                  暂无账本数据
                </TableCell>
              </TableRow>
            )}
            {rows.map((row, index) => (
              <TableRow key={`${row.record_type ?? "row"}-${row.record_id ?? index}`}>
                {columns.map((column) => (
                  <TableCell key={column.key} className={column.align === "right" ? "text-right" : undefined}>
                    {column.key === "source_kind" ? sourceLabel(String(row[column.key] ?? "")) : String(row[column.key] ?? "-")}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

export function ScopeSummary({ items }: { items: RankingItem[] }) {
  const chartItems = items.map((item) => ({ name: item.name, value: item.value }))
  return <ChartPanel title="范围贡献" unit="kgCO2e" option={createDistributionChartOption(chartItems, { unit: "kgCO2e" })} height={260} emptyLabel="暂无范围汇总" />
}

export function InsightCallout({ title, description, tone = "default" }: { title: string; description: string; tone?: "default" | "warning" }) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-lg border px-4 py-3 text-sm",
        tone === "warning" ? "border-amber-300/60 bg-amber-50 text-amber-950 dark:border-amber-700/40 dark:bg-amber-950/20 dark:text-amber-100" : "border-border/60 bg-card/70",
      )}
    >
      {tone === "warning" ? <AlertTriangle className="mt-0.5 h-4 w-4" /> : <GitBranch className="mt-0.5 h-4 w-4" />}
      <div className="space-y-1">
        <div className="font-medium">{title}</div>
        <div className="text-muted-foreground dark:text-inherit/80">{description}</div>
      </div>
    </div>
  )
}

export function MiniStatList({ title, items }: { title: string; items: { label: string; value: string | number }[] }) {
  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between gap-3 text-sm">
            <span className="text-muted-foreground">{item.label}</span>
            <span className="font-medium tabular-nums">{item.value}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

export function SectionHeader({ badge, title, description }: { badge?: string; title: string; description?: string }) {
  return (
    <div className="space-y-2">
      {badge && <Badge variant="outline">{badge}</Badge>}
      <div className="flex items-center gap-2">
        <ArrowRight className="h-4 w-4 text-primary" />
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
    </div>
  )
}

export function TrendComparison({ title, points }: { title: string; description?: string; points: TrendPoint[] }) {
  return (
    <CompositeTrendChart
      title={title}
      points={points}
      bars={[{ key: "energy_kwh", label: "总能耗", colorKey: "energy" }]}
      lines={[
        { key: "carbon_co2e", label: "总碳排", colorKey: "carbon", yAxisIndex: 1 },
        { key: "alerts_count", label: "告警数", colorKey: "danger", yAxisIndex: 1 },
      ]}
      leftAxisName="能耗"
      rightAxisName="碳排 / 告警"
    />
  )
}
