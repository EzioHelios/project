import type { EChartsOption, SeriesOption } from "echarts"
import { AlertTriangle, ArrowRight, GitBranch, TrendingUp } from "lucide-react"

import { ChartPanel } from "@/components/admin-ui"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { type AdminChartColorKey, adminChartAxis, adminChartPalette, createAdminChartOption, getAdminChartColor } from "@/lib/admin-chart-theme"
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

type SeriesConfig = {
  key: keyof TrendPoint
  label: string
  color?: string
  colorKey?: AdminChartColorKey
}

type BarSeriesConfig = SeriesConfig & {
  stack?: string
}

type LineSeriesConfig = SeriesConfig & {
  yAxisIndex?: number
}

export async function fetchCarbonApi<T>(url: string) {
  const res = await fetch(url)
  const text = await res.text()
  const raw = text ? JSON.parse(text) : {}
  if (!res.ok || (raw.code && raw.code >= 400)) {
    throw new Error(raw.msg || raw.detail || `HTTP ${res.status}`)
  }
  return raw as ApiEnvelope<T>
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return Number(value).toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
  })
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

function resolveSeriesColor(series: SeriesConfig, index: number) {
  return series.color ?? getAdminChartColor(series.colorKey, index)
}

function buildLineSeries(points: TrendPoint[], lines: SeriesConfig[]): SeriesOption[] {
  return lines
    .filter((line) => points.some((point) => Number(point[line.key] ?? 0) > 0))
    .map((line, index) => {
      const color = resolveSeriesColor(line, index)
      return {
        type: "line",
        name: line.label,
        smooth: true,
        showSymbol: false,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: {
          width: 2,
          color,
        },
        itemStyle: {
          color,
        },
        areaStyle: line.key === "energy_kwh" ? { color: `${color}14` } : undefined,
        data: points.map((point) => Number(point[line.key] ?? 0)),
      }
    })
}

function buildTrendOption(points: TrendPoint[], lines: SeriesConfig[]): EChartsOption | undefined {
  if (points.length === 0) return undefined
  return createAdminChartOption({
    xAxis: {
      ...adminChartAxis.category(points.map((point) => point.period)),
      boundaryGap: false,
    },
    yAxis: adminChartAxis.value(),
    series: buildLineSeries(points, lines),
  })
}

function buildComboTrendOption(
  points: TrendPoint[],
  config: {
    bars: BarSeriesConfig[]
    lines: LineSeriesConfig[]
    leftAxisName?: string
    rightAxisName?: string
  },
): EChartsOption | undefined {
  if (points.length === 0) return undefined
  const barSeries = config.bars
    .filter((bar) => points.some((point) => Number(point[bar.key] ?? 0) > 0))
    .map<SeriesOption>((bar, index) => ({
      type: "bar",
      name: bar.label,
      stack: bar.stack,
      barMaxWidth: 16,
      itemStyle: {
        color: resolveSeriesColor(bar, index),
        borderRadius: [4, 4, 0, 0],
      },
      emphasis: { focus: "series" },
      data: points.map((point) => Number(point[bar.key] ?? 0)),
    }))
  const lineSeries = config.lines
    .filter((line) => points.some((point) => Number(point[line.key] ?? 0) > 0))
    .map<SeriesOption>((line, index) => ({
      type: "line",
      name: line.label,
      smooth: true,
      showSymbol: false,
      yAxisIndex: line.yAxisIndex ?? 1,
      lineStyle: {
        width: 2,
        color: resolveSeriesColor(line, index + config.bars.length),
      },
      itemStyle: {
        color: resolveSeriesColor(line, index + config.bars.length),
      },
      data: points.map((point) => Number(point[line.key] ?? 0)),
    }))
  if (barSeries.length === 0 && lineSeries.length === 0) return undefined
  return createAdminChartOption({
    xAxis: adminChartAxis.category(points.map((point) => point.period)),
    yAxis: [
      adminChartAxis.value(config.leftAxisName),
      {
        ...adminChartAxis.value(config.rightAxisName),
        type: "value",
        name: config.rightAxisName,
        splitLine: { show: false },
      },
    ],
    series: [...barSeries, ...lineSeries],
  })
}

function buildRankingOption(items: RankingItem[], unit?: string): EChartsOption | undefined {
  if (items.length === 0) return undefined
  const sliced = items.slice(0, 10)
  return createAdminChartOption({
    tooltip: {
      trigger: "item",
      formatter: (params: { name: string; value: number }) => `${params.name}<br/>${formatNumber(params.value, 2)}${unit ? ` ${unit}` : ""}`,
    },
    grid: {
      top: 8,
      left: 10,
      right: 18,
      bottom: 6,
      containLabel: true,
    },
    xAxis: {
      type: "value",
      splitLine: { lineStyle: { color: adminChartPalette.grid, type: "dashed" } },
      axisLabel: {
        color: adminChartPalette.axis,
        formatter: (value: number) => `${formatNumber(value, 0)}${unit ? ` ${unit}` : ""}`,
      },
    },
    yAxis: {
      type: "category",
      inverse: true,
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: {
        color: adminChartPalette.label,
        width: 150,
        overflow: "truncate",
      },
      data: sliced.map((item) => item.name),
    },
    series: [
      {
        type: "bar",
        data: sliced.map((item) => item.value),
        barWidth: 14,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: adminChartPalette.energy,
        },
        label: {
          show: true,
          position: "right",
          color: adminChartPalette.label,
          formatter: ({ value }: { value: number }) => `${formatNumber(value, 2)}${unit ? ` ${unit}` : ""}`,
        },
      },
    ],
  })
}

function buildDistributionOption(items: DistributionItem[], unit = ""): EChartsOption | undefined {
  if (items.length === 0) return undefined
  return createAdminChartOption({
    tooltip: {
      trigger: "item",
      formatter: (params: { name: string; value: number; percent: number }) => `${params.name}<br/>${formatNumber(params.value, 2)}${unit ? ` ${unit}` : ""} (${params.percent}%)`,
    },
    series: [
      {
        type: "pie",
        radius: ["54%", "76%"],
        center: ["50%", "58%"],
        avoidLabelOverlap: true,
        label: {
          formatter: "{b}",
          color: adminChartPalette.label,
        },
        itemStyle: {
          borderColor: adminChartPalette.panel,
          borderWidth: 2,
        },
        data: items,
      },
    ],
  })
}

function buildGaugeOption(value: number, suffix: string): EChartsOption {
  return createAdminChartOption({
    tooltip: { show: false },
    series: [
      {
        type: "gauge",
        startAngle: 220,
        endAngle: -40,
        min: 0,
        max: 100,
        radius: "100%",
        progress: {
          show: true,
          roundCap: true,
          width: 10,
          itemStyle: {
            color: value >= 80 ? adminChartPalette.success : value >= 50 ? adminChartPalette.warning : adminChartPalette.danger,
          },
        },
        axisLine: {
          lineStyle: {
            width: 10,
            color: [[1, adminChartPalette.grid]],
          },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, "10%"],
          fontSize: 24,
          fontWeight: 700,
          formatter: `{value}${suffix}`,
          color: adminChartPalette.text,
        },
        data: [{ value }],
      },
    ],
  })
}

function buildSankeyOption(nodes: FlowNode[], links: FlowLink[]): EChartsOption | undefined {
  if (nodes.length === 0 || links.length === 0) return undefined
  const nameMap = new Map(nodes.map((node) => [node.id, node]))
  const colorForCategory = (category?: string) => {
    if (category === "scope") return adminChartPalette.text
    if (category === "source") return adminChartPalette.energy
    if (category === "conversion") return adminChartPalette.cost
    if (category === "distribution") return adminChartPalette.scope2
    if (category === "use_system") return adminChartPalette.carbon
    if (category === "area") return adminChartPalette.scope3
    if (category === "result") return adminChartPalette.success
    if (category === "loss") return adminChartPalette.danger
    return adminChartPalette.neutral
  }
  const sankeyNodes = nodes.map((node) => ({
    name: node.id,
    value: node.value ?? 0,
    itemStyle: { color: colorForCategory(node.category) },
    label: {
      color: adminChartPalette.label,
      fontSize: 12,
      formatter: () => {
        const amount = node.value && node.value > 0 ? `\n${formatNumber(node.value, 2)}` : ""
        return `${node.name}${amount}`
      },
    },
  }))
  const sankeyLinks = links
    .filter((link) => nameMap.has(link.source) && nameMap.has(link.target) && link.value > 0)
    .map((link) => ({
      source: link.source,
      target: link.target,
      value: link.value,
      lineStyle: {
        color: "gradient",
        opacity: 0.42,
        curveness: 0.48,
      },
    }))
  if (sankeyLinks.length === 0) return undefined
  return createAdminChartOption({
    tooltip: {
      trigger: "item",
      formatter: (params: { dataType?: string; data?: { source?: string; target?: string; value?: number }; name?: string; value?: number }) => {
        if (params.dataType === "edge" && params.data) {
          const sourceNode = nameMap.get(params.data.source ?? "")
          const targetNode = nameMap.get(params.data.target ?? "")
          return `${sourceNode?.name ?? params.data.source}<br/>→ ${targetNode?.name ?? params.data.target}<br/>${formatNumber(params.data.value ?? 0, 2)}`
        }
        const node = nameMap.get(params.name ?? "")
        return `${node?.name ?? params.name}<br/>${formatNumber(params.value ?? 0, 2)}`
      },
    },
    series: [
      {
        type: "sankey",
        left: "2%",
        right: "4%",
        top: 24,
        bottom: 12,
        data: sankeyNodes,
        links: sankeyLinks,
        nodeAlign: "justify",
        draggable: false,
        nodeGap: 18,
        nodeWidth: 18,
        emphasis: { focus: "adjacency" },
        levels: [
          { depth: 0, itemStyle: { color: adminChartPalette.text }, lineStyle: { color: "source", opacity: 0.35 } },
          { depth: 1, itemStyle: { color: adminChartPalette.energy }, lineStyle: { color: "source", opacity: 0.42 } },
          { depth: 2, itemStyle: { color: adminChartPalette.scope2 }, lineStyle: { color: "source", opacity: 0.48 } },
          { depth: 3, itemStyle: { color: adminChartPalette.success }, lineStyle: { color: "source", opacity: 0.55 } },
        ],
        label: {
          color: adminChartPalette.label,
          fontSize: 12,
          formatter: ({ name }: { name: string }) => {
            const node = nameMap.get(name)
            const amount = node?.value && node.value > 0 ? `\n${formatNumber(node.value, 2)}` : ""
            return `${node?.name ?? name}${amount}`
          },
        },
      },
    ],
  })
}

export function KpiStrip({ items }: { items: KpiItem[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
      {items.map((item) => (
        <Card key={item.id} className="border-border/60 shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription>{item.label}</CardDescription>
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="text-3xl font-semibold tabular-nums">{formatNumber(item.value)}</CardTitle>
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

export function TrendChart({
  title,
  description,
  points,
  lines,
  height = 340,
}: {
  title: string
  description?: string
  points: TrendPoint[]
  lines: SeriesConfig[]
  height?: number
}) {
  return <ChartPanel title={title} description={description} option={buildTrendOption(points, lines)} height={height} emptyLabel="暂无趋势数据" />
}

export function CompositeTrendChart({
  title,
  description,
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
  return (
    <ChartPanel
      title={title}
      description={description}
      option={buildComboTrendOption(points, { bars, lines, leftAxisName, rightAxisName })}
      height={height}
      emptyLabel="暂无趋势数据"
    />
  )
}

export function RankingList({ title, description, items, unit, height = 320 }: { title: string; description?: string; items: RankingItem[]; unit?: string; height?: number }) {
  return <ChartPanel title={title} description={description} unit={unit} option={buildRankingOption(items, unit)} height={height} emptyLabel="暂无排行数据" />
}

export function DistributionChart({
  title,
  description,
  items,
  unit,
  height = 280,
}: {
  title: string
  description?: string
  items: DistributionItem[]
  unit?: string
  height?: number
}) {
  return <ChartPanel title={title} description={description} unit={unit} option={buildDistributionOption(items, unit)} height={height} emptyLabel="暂无分布数据" />
}

export function GaugeStatCard({ title, description, value, suffix, height = 240 }: { title: string; description?: string; value: number; suffix?: string; height?: number }) {
  return <ChartPanel title={title} description={description} unit={suffix} option={buildGaugeOption(value, suffix ?? "")} height={height} emptyLabel="暂无完成度数据" />
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
  description,
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
  return <ChartPanel title={title} description={description} unit={unit} option={buildSankeyOption(nodes, links)} height={height} emptyLabel="暂无流向数据" />
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
  return (
    <ChartPanel
      title="范围贡献"
      description="当前已纳入核算的范围级碳排分布"
      unit="kgCO2e"
      option={buildDistributionOption(chartItems, "kgCO2e")}
      height={260}
      emptyLabel="暂无范围汇总"
    />
  )
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

export function TrendComparison({ title, description, points }: { title: string; description?: string; points: TrendPoint[] }) {
  return (
    <CompositeTrendChart
      title={title}
      description={description}
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
