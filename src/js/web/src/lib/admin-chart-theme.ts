import { useRouterState } from "@tanstack/react-router"
import type { EChartsOption, SeriesOption } from "echarts"
import { useMemo } from "react"

import { type DesignDomain, resolveAdminDomain } from "@/lib/design-domain"
import { type ResolvedTheme, useTheme } from "@/lib/theme-context"

export type AdminChartColorKey =
  | "energy"
  | "electricity"
  | "fuel"
  | "heat"
  | "steam"
  | "water"
  | "carbon"
  | "scope1"
  | "scope2"
  | "scope3"
  | "cost"
  | "warning"
  | "danger"
  | "success"
  | "neutral"
  | "muted"
  | "axis"
  | "grid"
  | "gridSubtle"
  | "text"
  | "label"
  | "panel"

type AdminChartPalette = Record<AdminChartColorKey, string>

export type AdminChartTheme = {
  domain: DesignDomain
  mode: ResolvedTheme
  palette: AdminChartPalette
  seriesColors: string[]
  flowColors: string[]
  tooltip: {
    background: string
    border: string
    text: string
    shadow: string
  }
}

const lightBase = {
  fuel: "#66705b",
  heat: "#b97820",
  steam: "#607d8a",
  water: "#168cb0",
  scope1: "#9b6438",
  scope2: "#2d74a8",
  scope3: "#2f8064",
  cost: "#b07a18",
  warning: "#c87508",
  danger: "#c93434",
  success: "#608b24",
  neutral: "#5a6f7a",
  muted: "#93a9b3",
  axis: "#58717d",
  grid: "#cfe0e7",
  gridSubtle: "#ebf3f7",
  text: "#071e2a",
  label: "#365867",
  panel: "#ffffff",
} as const

const darkBase = {
  fuel: "#b5c2a3",
  heat: "#f1b955",
  steam: "#8db7c5",
  water: "#38bdf8",
  scope1: "#d6a06c",
  scope2: "#60a5fa",
  scope3: "#4fd1a1",
  cost: "#e7b64f",
  warning: "#fbbf24",
  danger: "#fb7185",
  success: "#b6ed69",
  neutral: "#9ab2bc",
  muted: "#617f8a",
  axis: "#8db0bc",
  grid: "#1d4855",
  gridSubtle: "#12303a",
  text: "#ecfafe",
  label: "#b5d2da",
  panel: "#0b2530",
} as const

const domainPalettes: Record<ResolvedTheme, Record<DesignDomain, Pick<AdminChartPalette, "energy" | "electricity" | "carbon">>> = {
  light: {
    neutral: { energy: "#3e6873", electricity: "#407d91", carbon: "#477763" },
    energy: { energy: "#007ea8", electricity: "#00a9d6", carbon: "#287962" },
    carbon: { energy: "#237b98", electricity: "#2d8ba8", carbon: "#0a7d5e" },
  },
  dark: {
    neutral: { energy: "#77b8c4", electricity: "#72c7d8", carbon: "#75b89f" },
    energy: { energy: "#22d3ee", electricity: "#38bdf8", carbon: "#56c59d" },
    carbon: { energy: "#5cc6dd", electricity: "#71d2e5", carbon: "#34d399" },
  },
}

export function getAdminChartTheme(domain: DesignDomain, mode: ResolvedTheme): AdminChartTheme {
  const palette: AdminChartPalette = { ...(mode === "dark" ? darkBase : lightBase), ...domainPalettes[mode][domain] }
  const seriesColors = [
    domain === "carbon" ? palette.carbon : palette.energy,
    palette.electricity,
    domain === "energy" ? palette.carbon : palette.energy,
    palette.heat,
    palette.water,
    palette.cost,
    palette.scope1,
    palette.scope2,
    palette.scope3,
    palette.neutral,
    palette.danger,
  ]
  return {
    domain,
    mode,
    palette,
    seriesColors,
    flowColors:
      mode === "dark"
        ? ["#22d3ee", "#34d399", "#a78bfa", "#5cc6dd", "#6adcaf", "#818cf8", "#9ab2bc"]
        : ["#007ea8", "#0a7d5e", "#7660b5", "#2a9fc1", "#32a67d", "#5367c6", "#6a8792"],
    tooltip:
      mode === "dark"
        ? { background: "rgba(4, 19, 25, 0.98)", border: "rgba(119, 184, 196, 0.3)", text: "#ecfafe", shadow: "0 16px 42px rgba(0, 7, 11, .5)" }
        : { background: "rgba(7, 30, 42, 0.98)", border: "rgba(0, 169, 214, 0.28)", text: "#f8fcfe", shadow: "0 14px 34px rgba(4, 25, 34, .24)" },
  }
}

export function useAdminChartTheme(domainOverride?: DesignDomain) {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const { resolvedTheme } = useTheme()
  const domain = domainOverride ?? resolveAdminDomain(pathname)
  return useMemo(() => getAdminChartTheme(domain, resolvedTheme), [domain, resolvedTheme])
}

type AdminChartOptionConfig = { compact?: boolean }
export type AdminChartDatum = Record<string, unknown>
export type AdminChartSeriesConfig<K extends string = string> = { key: K; label: string; color?: string; colorKey?: AdminChartColorKey }
export type AdminChartBarSeriesConfig<K extends string = string> = AdminChartSeriesConfig<K> & { stack?: string }
export type AdminChartLineSeriesConfig<K extends string = string> = AdminChartSeriesConfig<K> & { yAxisIndex?: number }
export type AdminChartRankingItem = { name: string; value: number }
export type AdminChartDistributionItem = { name: string; value: number }
export type AdminChartParetoItem = { name: string; value: number }
export type AdminChartWaterfallItem = { name: string; value: number; kind?: "start" | "increase" | "decrease" | "total" }
export type AdminChartBubbleItem = { name: string; x: number; y: number; size: number; category?: string }
export type AdminChartMaccItem = { name: string; reduction: number; cost: number }
export type AdminChartFlowNode = { id: string; name: string; value?: number; category?: string }
export type AdminChartFlowLink = { source: string; target: string; value: number }
export type AdminMarketKlinePoint = { trade_date: string; open: number; close: number; low: number; high: number; volume?: number | null }
export type AdminTargetPathPoint = { period: string; actual?: number | null; reference?: number | null; forecast?: number | null }
export type AdminReadinessStatus = "complete" | "partial" | "missing" | "blocked" | "not_applicable"
export type AdminReadinessMatrixItem = { domain: string; dimension: string; status: AdminReadinessStatus; detail?: string }
export type AdminBulletSegment = { name: string; value: number; colorKey?: AdminChartColorKey }
export type AdminMarketPriceVolumePoint = {
  period: string
  price: number
  volume?: number | null
  open?: number | null
  high?: number | null
  low?: number | null
}
export type AdminTornadoItem = { name: string; downside: number; upside: number }

export function getAdminChartColor(theme: AdminChartTheme, key: AdminChartColorKey | undefined, fallbackIndex = 0) {
  return key ? theme.palette[key] : theme.seriesColors[fallbackIndex % theme.seriesColors.length]
}

export function formatAdminChartNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
}

function formatAdminAxisNumber(value: number) {
  return new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 }).format(value)
}

function niceAdminAxisMaximum(value: number) {
  if (!Number.isFinite(value) || value <= 0) return 1
  const magnitude = 10 ** Math.floor(Math.log10(value))
  const fraction = value / magnitude
  const niceFraction = [1, 1.2, 1.5, 2, 2.5, 5, 10].find((candidate) => candidate >= fraction) ?? 10
  return niceFraction * magnitude
}

function chartParamRecord(params: unknown) {
  return params && typeof params === "object" ? (params as Record<string, unknown>) : {}
}

function chartParamNumber(value: unknown) {
  return typeof value === "number" ? value : Number(value ?? 0)
}

export function createAdminChartOption(theme: AdminChartTheme, option: EChartsOption, config: AdminChartOptionConfig = {}): EChartsOption {
  const reduceMotion = typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  return {
    color: theme.seriesColors,
    backgroundColor: "transparent",
    animation: !reduceMotion,
    animationDuration: 220,
    animationDurationUpdate: 180,
    animationEasing: "cubicOut",
    animationEasingUpdate: "cubicOut",
    textStyle: { color: theme.palette.text, fontFamily: "inherit", fontSize: 12 },
    grid: { top: config.compact ? 14 : 32, left: 10, right: 18, bottom: 12, containLabel: true },
    legend: {
      top: 0,
      left: 0,
      icon: "roundRect",
      itemWidth: 10,
      itemHeight: 8,
      itemGap: 16,
      textStyle: { color: theme.palette.label, fontSize: 11, fontWeight: 500 },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: theme.tooltip.background,
      borderColor: theme.tooltip.border,
      borderWidth: 1,
      padding: [9, 11],
      textStyle: { color: theme.tooltip.text, fontSize: 12 },
      extraCssText: `border-radius:7px;box-shadow:${theme.tooltip.shadow};`,
    },
    ...option,
  }
}

function categoryAxis(theme: AdminChartTheme, data: string[] | number[]) {
  return {
    type: "category" as const,
    data,
    axisTick: { show: false },
    axisLine: { show: false },
    axisLabel: { color: theme.palette.axis, fontSize: 11, margin: 10 },
  }
}

function valueAxis(theme: AdminChartTheme, name?: string) {
  return {
    type: "value" as const,
    name,
    nameTextStyle: { color: theme.palette.axis, fontSize: 11, padding: [0, 0, 6, 0] },
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: theme.palette.axis, fontSize: 11, margin: 10 },
    splitLine: { lineStyle: { color: theme.palette.grid, type: "dashed" as const } },
  }
}

function readChartNumber<T extends AdminChartDatum>(point: T, key: string) {
  return Number(point[key] ?? 0)
}

function readChartLabel<T extends AdminChartDatum>(point: T, key: string) {
  const value = point[key]
  return value === null || value === undefined ? "" : String(value)
}

function resolveSeriesColor(theme: AdminChartTheme, series: AdminChartSeriesConfig, index: number) {
  return series.color ?? getAdminChartColor(theme, series.colorKey, index)
}

function buildLineSeries<T extends AdminChartDatum>(
  theme: AdminChartTheme,
  points: readonly T[],
  lines: AdminChartSeriesConfig<Extract<keyof T, string>>[],
  config: { includeZeroSeries?: boolean } = {},
): SeriesOption[] {
  return lines
    .filter((line) => points.some((point) => Number.isFinite(readChartNumber(point, line.key)) && (config.includeZeroSeries || readChartNumber(point, line.key) > 0)))
    .map((line, index) => {
      const color = resolveSeriesColor(theme, line, index)
      return {
        type: "line",
        name: line.label,
        smooth: true,
        showSymbol: false,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { width: 2.25, color },
        itemStyle: { color },
        areaStyle: { color: `${color}14` },
        emphasis: { focus: "series" },
        data: points.map((point) => readChartNumber(point, line.key)),
      }
    })
}

export function createTrendChartOption<T extends AdminChartDatum>(
  theme: AdminChartTheme,
  points: readonly T[],
  lines: AdminChartSeriesConfig<Extract<keyof T, string>>[],
  config: { periodKey?: Extract<keyof T, string>; includeZeroSeries?: boolean } = {},
): EChartsOption | undefined {
  if (points.length === 0) return undefined
  const periodKey = config.periodKey ?? ("period" as Extract<keyof T, string>)
  return createAdminChartOption(theme, {
    xAxis: {
      ...categoryAxis(
        theme,
        points.map((point) => readChartLabel(point, periodKey)),
      ),
      boundaryGap: false,
    },
    yAxis: valueAxis(theme),
    series: buildLineSeries(theme, points, lines, { includeZeroSeries: config.includeZeroSeries }),
  })
}

export function createComboTrendChartOption<T extends AdminChartDatum>(
  theme: AdminChartTheme,
  points: readonly T[],
  config: {
    bars: AdminChartBarSeriesConfig<Extract<keyof T, string>>[]
    lines: AdminChartLineSeriesConfig<Extract<keyof T, string>>[]
    leftAxisName?: string
    rightAxisName?: string
    periodKey?: Extract<keyof T, string>
  },
): EChartsOption | undefined {
  if (points.length === 0) return undefined
  const periodKey = config.periodKey ?? ("period" as Extract<keyof T, string>)
  const bars = config.bars
    .filter((bar) => points.some((point) => readChartNumber(point, bar.key) > 0))
    .map<SeriesOption>((bar, index) => ({
      type: "bar",
      name: bar.label,
      stack: bar.stack,
      barMaxWidth: 14,
      showBackground: true,
      backgroundStyle: { color: theme.palette.gridSubtle, borderRadius: [5, 5, 0, 0] },
      itemStyle: { color: resolveSeriesColor(theme, bar, index), borderRadius: [5, 5, 0, 0] },
      emphasis: { focus: "series" },
      data: points.map((point) => readChartNumber(point, bar.key)),
    }))
  const lines = config.lines
    .filter((line) => points.some((point) => readChartNumber(point, line.key) > 0))
    .map<SeriesOption>((line, index) => ({
      type: "line",
      name: line.label,
      smooth: true,
      showSymbol: false,
      yAxisIndex: line.yAxisIndex ?? 1,
      lineStyle: { width: 2.25, color: resolveSeriesColor(theme, line, index + config.bars.length) },
      itemStyle: { color: resolveSeriesColor(theme, line, index + config.bars.length) },
      data: points.map((point) => readChartNumber(point, line.key)),
    }))
  if (bars.length === 0 && lines.length === 0) return undefined
  return createAdminChartOption(theme, {
    xAxis: categoryAxis(
      theme,
      points.map((point) => readChartLabel(point, periodKey)),
    ),
    yAxis: [valueAxis(theme, config.leftAxisName), { ...valueAxis(theme, config.rightAxisName), splitLine: { show: false } }],
    series: [...bars, ...lines],
  })
}

export function createRankingChartOption(
  theme: AdminChartTheme,
  items: AdminChartRankingItem[],
  config: { unit?: string; colorKey?: AdminChartColorKey; limit?: number } = {},
): EChartsOption | undefined {
  if (items.length === 0) return undefined
  const unit = config.unit
  const sliced = items.slice(0, config.limit ?? 10)
  return createAdminChartOption(theme, {
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const param = chartParamRecord(params)
        return `${String(param.name ?? "")}<br/>${formatAdminChartNumber(chartParamNumber(param.value), 2)}${unit ? ` ${unit}` : ""}`
      },
    },
    grid: { top: 8, left: 10, right: 18, bottom: 6, containLabel: true },
    xAxis: {
      ...valueAxis(theme),
      axisLabel: { color: theme.palette.axis, margin: 10, formatter: (value: number) => formatAdminAxisNumber(value) },
    },
    yAxis: {
      type: "category",
      inverse: true,
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: theme.palette.label, width: 150, overflow: "truncate" },
      data: sliced.map((item) => item.name),
    },
    series: [
      {
        type: "bar",
        data: sliced.map((item) => item.value),
        barWidth: 14,
        itemStyle: { borderRadius: [0, 5, 5, 0], color: getAdminChartColor(theme, config.colorKey ?? (theme.domain === "carbon" ? "carbon" : "energy")) },
        showBackground: true,
        backgroundStyle: { color: theme.palette.gridSubtle, borderRadius: [0, 5, 5, 0] },
        label: {
          show: true,
          position: "right",
          color: theme.palette.label,
          fontWeight: 600,
          formatter: (params: unknown) => `${formatAdminChartNumber(chartParamNumber(chartParamRecord(params).value), 2)}${unit ? ` ${unit}` : ""}`,
        },
      },
    ],
  })
}

export function createParetoChartOption(
  theme: AdminChartTheme,
  items: AdminChartParetoItem[],
  config: { unit?: string; limit?: number; colorKey?: AdminChartColorKey } = {},
): EChartsOption | undefined {
  if (items.length === 0) return undefined
  const unit = config.unit ?? ""
  const sorted = [...items].sort((left, right) => right.value - left.value).slice(0, config.limit ?? 10)
  const total = sorted.reduce((sum, item) => sum + item.value, 0)
  let accumulated = 0
  const cumulative = sorted.map((item) => {
    accumulated += item.value
    return total > 0 ? (accumulated / total) * 100 : 0
  })
  const color = getAdminChartColor(theme, config.colorKey ?? (theme.domain === "carbon" ? "carbon" : "energy"))
  return createAdminChartOption(theme, {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const rows = Array.isArray(params) ? params.map(chartParamRecord) : [chartParamRecord(params)]
        const name = String(rows[0]?.axisValueLabel ?? rows[0]?.name ?? "")
        const amount = chartParamNumber(rows.find((row) => row.seriesName === "排放量")?.value)
        const ratio = chartParamNumber(rows.find((row) => row.seriesName === "累计占比")?.value)
        return `${name}<br/>排放量 ${formatAdminChartNumber(amount, 2)}${unit ? ` ${unit}` : ""}<br/>累计占比 ${formatAdminChartNumber(ratio, 1)}%`
      },
    },
    grid: { top: 36, left: 10, right: 18, bottom: 12, containLabel: true },
    xAxis: categoryAxis(
      theme,
      sorted.map((item) => item.name),
    ),
    yAxis: [valueAxis(theme, unit), { ...valueAxis(theme, "%"), max: 100, splitLine: { show: false } }],
    series: [
      {
        type: "bar",
        name: "排放量",
        data: sorted.map((item) => item.value),
        barMaxWidth: 18,
        itemStyle: { color, borderRadius: [5, 5, 0, 0] },
        showBackground: true,
        backgroundStyle: { color: theme.palette.gridSubtle, borderRadius: [5, 5, 0, 0] },
      },
      {
        type: "line",
        name: "累计占比",
        yAxisIndex: 1,
        data: cumulative,
        smooth: true,
        symbolSize: 6,
        lineStyle: { width: 2.25, color: theme.palette.cost },
        itemStyle: { color: theme.palette.cost },
      },
    ],
  })
}

export function createDistributionChartOption(theme: AdminChartTheme, items: AdminChartDistributionItem[], config: { unit?: string } = {}): EChartsOption | undefined {
  if (items.length === 0) return undefined
  const unit = config.unit ?? ""
  return createAdminChartOption(theme, {
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const param = chartParamRecord(params)
        return `${String(param.name ?? "")}<br/>${formatAdminChartNumber(chartParamNumber(param.value), 2)}${unit ? ` ${unit}` : ""} (${chartParamNumber(param.percent)}%)`
      },
    },
    series: [
      {
        type: "pie",
        radius: ["54%", "76%"],
        center: ["50%", "55%"],
        avoidLabelOverlap: true,
        label: { formatter: "{b}", color: theme.palette.label, fontSize: 11 },
        labelLine: { lineStyle: { color: theme.palette.grid } },
        itemStyle: { borderColor: theme.palette.panel, borderWidth: 3 },
        data: items,
      },
    ],
  })
}

export function createWaterfallChartOption(theme: AdminChartTheme, items: AdminChartWaterfallItem[], config: { unit?: string } = {}): EChartsOption | undefined {
  if (items.length === 0) return undefined
  const unit = config.unit ?? ""
  let running = 0
  const helpers: number[] = []
  const values: Array<{ value: number; itemStyle: { color: string; borderRadius: number[] } }> = []
  for (const item of items) {
    const kind = item.kind ?? (item.value < 0 ? "decrease" : "increase")
    if (kind === "start" || kind === "total") {
      helpers.push(0)
      values.push({ value: Math.abs(item.value), itemStyle: { color: kind === "total" ? theme.palette.carbon : theme.palette.neutral, borderRadius: [5, 5, 0, 0] } })
      running = item.value
    } else if (item.value >= 0) {
      helpers.push(running)
      values.push({ value: item.value, itemStyle: { color: theme.palette.warning, borderRadius: [5, 5, 0, 0] } })
      running += item.value
    } else {
      running += item.value
      helpers.push(running)
      values.push({ value: Math.abs(item.value), itemStyle: { color: theme.palette.success, borderRadius: [5, 5, 0, 0] } })
    }
  }
  return createAdminChartOption(theme, {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const rows = Array.isArray(params) ? params.map(chartParamRecord) : [chartParamRecord(params)]
        const index = Number(rows[0]?.dataIndex ?? 0)
        const item = items[index]
        return `${item?.name ?? ""}<br/>${formatAdminChartNumber(item?.value, 2)}${unit ? ` ${unit}` : ""}`
      },
    },
    xAxis: categoryAxis(
      theme,
      items.map((item) => item.name),
    ),
    yAxis: valueAxis(theme, unit),
    series: [
      { type: "bar", stack: "waterfall", silent: true, itemStyle: { color: "transparent" }, emphasis: { itemStyle: { color: "transparent" } }, data: helpers },
      {
        type: "bar",
        stack: "waterfall",
        barMaxWidth: 30,
        data: values,
        label: {
          show: true,
          position: "top",
          color: theme.palette.label,
          formatter: (params: unknown) => formatAdminChartNumber(items[Number(chartParamRecord(params).dataIndex ?? 0)]?.value, 1),
        },
      },
    ],
  })
}

export function createBubbleChartOption(theme: AdminChartTheme, items: AdminChartBubbleItem[], config: { xUnit?: string; yUnit?: string } = {}): EChartsOption | undefined {
  if (items.length === 0) return undefined
  const maxSize = Math.max(...items.map((item) => item.size), 1)
  return createAdminChartOption(theme, {
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const data = chartParamRecord(chartParamRecord(params).data)
        return `${String(data.name ?? "")}<br/>投资 ${formatAdminChartNumber(chartParamNumber(data.x), 2)}${config.xUnit ?? ""}<br/>减排 ${formatAdminChartNumber(chartParamNumber(data.y), 2)}${config.yUnit ?? ""}`
      },
    },
    xAxis: valueAxis(theme, config.xUnit),
    yAxis: valueAxis(theme, config.yUnit),
    series: [
      {
        type: "scatter",
        data: items.map((item, index) => ({
          name: item.name,
          x: item.x,
          y: item.y,
          value: [item.x, item.y, item.size],
          symbolSize: 12 + 30 * Math.sqrt(item.size / maxSize),
          itemStyle: { color: theme.seriesColors[index % theme.seriesColors.length], opacity: 0.78 },
        })),
        emphasis: { focus: "series", scale: true },
      },
    ],
  })
}

export function createMaccChartOption(theme: AdminChartTheme, items: AdminChartMaccItem[], config: { costUnit?: string } = {}): EChartsOption | undefined {
  if (items.length === 0) return undefined
  const sorted = [...items].filter((item) => item.reduction > 0).sort((left, right) => left.cost - right.cost)
  if (sorted.length === 0) return undefined
  let cumulative = 0
  const data = sorted.map((item, index) => {
    const start = cumulative
    cumulative += item.reduction
    return { ...item, start, end: cumulative, color: item.cost <= 0 ? theme.palette.success : theme.seriesColors[(index + 1) % theme.seriesColors.length] }
  })
  return createAdminChartOption(theme, {
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const item = data[Number(chartParamRecord(params).dataIndex ?? 0)]
        return `${item?.name ?? ""}<br/>减排潜力 ${formatAdminChartNumber(item?.reduction, 2)} tCO₂e<br/>边际成本 ${formatAdminChartNumber(item?.cost, 2)} ${config.costUnit ?? "元/tCO₂e"}`
      },
    },
    xAxis: valueAxis(theme, "累计减排量 tCO₂e"),
    yAxis: valueAxis(theme, config.costUnit ?? "元/tCO₂e"),
    series: [
      {
        type: "custom",
        renderItem: (params: unknown, api: unknown) => {
          const apiObject = api as { value: (index: number) => number; coord: (point: number[]) => number[] }
          const start = apiObject.coord([apiObject.value(0), apiObject.value(2)])
          const end = apiObject.coord([apiObject.value(1), 0])
          const zero = apiObject.coord([0, 0])
          return {
            type: "rect",
            shape: { x: start[0] + 1, y: Math.min(start[1], zero[1]), width: Math.max(end[0] - start[0] - 2, 2), height: Math.abs(zero[1] - start[1]) },
            style: { fill: data[Number((params as { dataIndex?: number }).dataIndex ?? 0)]?.color, opacity: 0.86 },
          }
        },
        encode: { x: [0, 1], y: 2 },
        data: data.map((item) => [item.start, item.end, item.cost]),
      },
    ],
  })
}

export function createGaugeChartOption(theme: AdminChartTheme, value: number, config: { suffix?: string } = {}): EChartsOption {
  const suffix = config.suffix ?? ""
  return createAdminChartOption(theme, {
    tooltip: { show: false },
    series: [
      {
        type: "gauge",
        startAngle: 220,
        endAngle: -40,
        min: 0,
        max: 100,
        radius: "96%",
        progress: {
          show: true,
          roundCap: true,
          width: 10,
          itemStyle: { color: value >= 80 ? theme.palette.success : value >= 50 ? theme.palette.warning : theme.palette.danger },
        },
        axisLine: { lineStyle: { width: 10, color: [[1, theme.palette.gridSubtle]] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        detail: { valueAnimation: true, offsetCenter: [0, "10%"], fontSize: 23, fontWeight: 650, formatter: `{value}${suffix}`, color: theme.palette.text },
        data: [{ value }],
      },
    ],
  })
}

export function createSankeyChartOption(
  theme: AdminChartTheme,
  nodes: AdminChartFlowNode[],
  links: AdminChartFlowLink[],
  config: { categoryColorMap?: Record<string, AdminChartColorKey>; labelWidth?: number; nodeGap?: number; right?: string } = {},
): EChartsOption | undefined {
  if (nodes.length === 0 || links.length === 0) return undefined
  const nameMap = new Map(nodes.map((node) => [node.id, node]))
  const semanticCategoryColorMap: Record<string, AdminChartColorKey> = {
    scope: "text",
    loss: "danger",
    ...config.categoryColorMap,
  }
  const flowCategoryIndex: Record<string, number> = {
    source: 0,
    use_system: 1,
    conversion: 2,
    distribution: 3,
    area: 4,
    result: 5,
  }
  const colorForCategory = (category?: string) => {
    const semanticColorKey = category ? semanticCategoryColorMap[category] : undefined
    if (semanticColorKey) return getAdminChartColor(theme, semanticColorKey)
    const flowIndex = category ? flowCategoryIndex[category] : undefined
    return theme.flowColors[flowIndex === undefined ? theme.flowColors.length - 1 : flowIndex % theme.flowColors.length]
  }
  const sankeyNodes = nodes.map((node) => ({
    name: node.id,
    value: node.value ?? 0,
    itemStyle: { color: colorForCategory(node.category) },
    label: {
      color: theme.palette.label,
      fontSize: 12,
      width: config.labelWidth ?? 132,
      overflow: "truncate" as const,
      formatter: () => `${node.name}${node.value && node.value > 0 ? `\n${formatAdminChartNumber(node.value, 2)}` : ""}`,
    },
  }))
  const sankeyLinks = links
    .filter((link) => nameMap.has(link.source) && nameMap.has(link.target) && link.value > 0)
    .map((link) => ({ source: link.source, target: link.target, value: link.value, lineStyle: { color: "gradient", opacity: 0.42, curveness: 0.48 } }))
  if (sankeyLinks.length === 0) return undefined
  return createAdminChartOption(theme, {
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const param = chartParamRecord(params)
        const data = chartParamRecord(param.data)
        if (param.dataType === "edge" && param.data) {
          const source = String(data.source ?? "")
          const target = String(data.target ?? "")
          return `${nameMap.get(source)?.name ?? source}<br/>→ ${nameMap.get(target)?.name ?? target}<br/>${formatAdminChartNumber(chartParamNumber(data.value), 2)}`
        }
        const name = String(param.name ?? "")
        return `${nameMap.get(name)?.name ?? name}<br/>${formatAdminChartNumber(chartParamNumber(param.value), 2)}`
      },
    },
    series: [
      {
        type: "sankey",
        left: "2%",
        right: config.right ?? "4%",
        top: 24,
        bottom: 12,
        data: sankeyNodes,
        links: sankeyLinks,
        nodeAlign: "justify",
        draggable: false,
        nodeGap: config.nodeGap ?? 18,
        nodeWidth: 16,
        emphasis: { focus: "adjacency" },
        levels: [
          { depth: 0, itemStyle: { color: theme.palette.text }, lineStyle: { color: "source", opacity: 0.35 } },
          { depth: 1, itemStyle: { color: theme.flowColors[0] }, lineStyle: { color: "source", opacity: 0.42 } },
          { depth: 2, itemStyle: { color: theme.flowColors[2] }, lineStyle: { color: "source", opacity: 0.48 } },
          { depth: 3, itemStyle: { color: theme.flowColors[1] }, lineStyle: { color: "source", opacity: 0.55 } },
        ],
        label: {
          color: theme.palette.label,
          fontSize: 12,
          width: config.labelWidth ?? 132,
          overflow: "truncate",
          formatter: (params: unknown) => {
            const node = nameMap.get(String(chartParamRecord(params).name ?? ""))
            return `${node?.name ?? ""}${node?.value && node.value > 0 ? `\n${formatAdminChartNumber(node.value, 2)}` : ""}`
          },
        },
      },
    ],
  })
}

export function createMarketKlineChartOption(
  theme: AdminChartTheme,
  points: AdminMarketKlinePoint[],
  config: { showVolume?: boolean; priceUnit?: string; volumeUnit?: string } = {},
): EChartsOption | undefined {
  if (points.length === 0) return undefined
  const showVolume = config.showVolume ?? true
  const useZoom = points.length > 16
  const movingAverage = points.map((_, index) => {
    if (index < 4) return null
    const window = points.slice(index - 4, index + 1)
    return window.reduce((sum, point) => sum + point.close, 0) / window.length
  })
  const priceSeries: SeriesOption = {
    type: "candlestick",
    name: "日K",
    xAxisIndex: 0,
    yAxisIndex: 0,
    data: points.map((point) => [point.open, point.close, point.low, point.high]),
    itemStyle: { color: theme.palette.danger, color0: theme.palette.success, borderColor: theme.palette.danger, borderColor0: theme.palette.success },
  }
  const movingAverageSeries: SeriesOption = {
    type: "line",
    name: "MA5",
    xAxisIndex: 0,
    yAxisIndex: 0,
    data: movingAverage,
    smooth: true,
    showSymbol: false,
    connectNulls: false,
    lineStyle: { color: theme.palette.scope2, width: 1.6 },
    itemStyle: { color: theme.palette.scope2 },
  }
  const volumeSeries: SeriesOption | null = showVolume
    ? {
        type: "bar",
        name: "成交量",
        xAxisIndex: 1,
        yAxisIndex: 1,
        barMaxWidth: 12,
        data: points.map((point) => ({
          value: point.volume ?? 0,
          itemStyle: { color: point.close >= point.open ? theme.palette.danger : theme.palette.success, opacity: 0.44 },
        })),
      }
    : null
  return createAdminChartOption(theme, {
    legend: { top: 0, left: 0 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params.map(chartParamRecord) : [chartParamRecord(params)]
        const candle = list.find((item) => item.seriesName === "日K")
        const values = Array.isArray(candle?.data) ? candle.data.map(Number) : []
        const date = String(candle?.axisValue ?? list[0]?.axisValue ?? "")
        if (values.length < 4) return date
        const volume = points.find((point) => point.trade_date === date)?.volume
        return [
          date,
          `开盘　${formatAdminChartNumber(values[0], 2)}`,
          `收盘　${formatAdminChartNumber(values[1], 2)}`,
          `最低　${formatAdminChartNumber(values[2], 2)}`,
          `最高　${formatAdminChartNumber(values[3], 2)}`,
          volume == null ? "" : `成交量　${formatAdminChartNumber(volume, 0)}`,
        ]
          .filter(Boolean)
          .join("<br/>")
      },
    },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: showVolume
      ? [
          { top: 34, left: 10, right: 18, height: "62%", containLabel: true },
          { left: 10, right: 18, top: "77%", bottom: useZoom ? 38 : 10, containLabel: true },
        ]
      : { top: 34, left: 10, right: 18, bottom: useZoom ? 38 : 12, containLabel: true },
    xAxis: showVolume
      ? [
          {
            ...categoryAxis(
              theme,
              points.map((point) => point.trade_date),
            ),
            boundaryGap: true,
            gridIndex: 0,
          },
          {
            ...categoryAxis(
              theme,
              points.map((point) => point.trade_date),
            ),
            boundaryGap: true,
            gridIndex: 1,
            axisLabel: { show: false },
          },
        ]
      : {
          ...categoryAxis(
            theme,
            points.map((point) => point.trade_date),
          ),
          boundaryGap: true,
        },
    yAxis: showVolume
      ? [
          { ...valueAxis(theme), scale: true, gridIndex: 0 },
          { ...valueAxis(theme), gridIndex: 1, splitNumber: 2, axisLabel: { color: theme.palette.axis, fontSize: 11, formatter: (value: number) => formatAdminAxisNumber(value) } },
        ]
      : { ...valueAxis(theme), scale: true },
    dataZoom: useZoom
      ? [
          { type: "inside", xAxisIndex: showVolume ? [0, 1] : [0], start: 0, end: 100 },
          { type: "slider", xAxisIndex: showVolume ? [0, 1] : [0], height: 16, bottom: 0, borderColor: theme.palette.grid, fillerColor: `${theme.palette.carbon}1f` },
        ]
      : undefined,
    series: volumeSeries ? [priceSeries, movingAverageSeries, volumeSeries] : [priceSeries, movingAverageSeries],
  })
}

export function createTargetPathChartOption(
  theme: AdminChartTheme,
  points: AdminTargetPathPoint[],
  config: { unit?: string; baselineYear?: number; reportingYear?: number; targetYear?: number } = {},
): EChartsOption | undefined {
  if (points.length === 0) return undefined
  const years = points.map((point) => point.period)
  const markerYears: Array<{ name: string; xAxis: string }> = [
    config.baselineYear ? { name: "基准年", xAxis: String(config.baselineYear) } : null,
    config.reportingYear ? { name: "报告年", xAxis: String(config.reportingYear) } : null,
    config.targetYear ? { name: "目标年", xAxis: String(config.targetYear) } : null,
  ].filter((item): item is { name: string; xAxis: string } => item !== null)
  const series: SeriesOption[] = [
    {
      type: "line",
      name: "年度实际",
      smooth: 0.22,
      connectNulls: false,
      showSymbol: true,
      symbol: "circle",
      symbolSize: 7,
      lineStyle: { width: 2.5, color: theme.palette.carbon },
      itemStyle: { color: theme.palette.carbon, borderColor: theme.palette.panel, borderWidth: 2 },
      data: points.map((point) => (Number.isFinite(point.actual) ? point.actual : null)),
      markLine: markerYears.length
        ? {
            silent: true,
            symbol: ["none", "none"],
            label: { color: theme.palette.axis, fontSize: 10, formatter: "{b}" },
            lineStyle: { color: theme.palette.grid, type: "dashed", width: 1 },
            data: markerYears,
          }
        : undefined,
    },
    {
      type: "line",
      name: "目标年度化路径",
      smooth: false,
      connectNulls: false,
      showSymbol: false,
      lineStyle: { width: 2, color: theme.palette.scope2, type: "dashed" },
      itemStyle: { color: theme.palette.scope2 },
      data: points.map((point) => (Number.isFinite(point.reference) ? point.reference : null)),
    },
  ]
  if (points.some((point) => Number.isFinite(point.forecast))) {
    series.push({
      type: "line",
      name: "年度预测",
      smooth: false,
      connectNulls: false,
      showSymbol: false,
      lineStyle: { width: 2, color: theme.palette.cost, type: "dotted" },
      itemStyle: { color: theme.palette.cost },
      data: points.map((point) => (Number.isFinite(point.forecast) ? point.forecast : null)),
    })
  }
  return createAdminChartOption(theme, {
    xAxis: { ...categoryAxis(theme, years), boundaryGap: false },
    yAxis: valueAxis(theme, config.unit),
    series,
  })
}

export function createReadinessMatrixOption(theme: AdminChartTheme, items: AdminReadinessMatrixItem[]): EChartsOption | undefined {
  if (items.length === 0) return undefined
  const domains = [...new Set(items.map((item) => item.domain))]
  const dimensions = [...new Set(items.map((item) => item.dimension))]
  const statusValues: Record<AdminReadinessStatus, number> = { blocked: 0, missing: 1, partial: 2, complete: 3, not_applicable: 4 }
  const statusLabels: Record<AdminReadinessStatus, string> = { blocked: "阻塞", missing: "缺失", partial: "部分", complete: "完整", not_applicable: "不适用" }
  const data = items.map((item) => ({
    value: [dimensions.indexOf(item.dimension), domains.indexOf(item.domain), statusValues[item.status]],
    status: item.status,
    detail: item.detail,
  }))
  return createAdminChartOption(theme, {
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const param = chartParamRecord(params)
        const item = chartParamRecord(param.data)
        const value = Array.isArray(item.value) ? item.value : []
        const status = String(item.status ?? "missing") as AdminReadinessStatus
        return `${domains[Number(value[1] ?? 0)] ?? ""}<br/>${dimensions[Number(value[0] ?? 0)] ?? ""}：${statusLabels[status]}${item.detail ? `<br/>${String(item.detail)}` : ""}`
      },
    },
    grid: { top: 12, left: 12, right: 16, bottom: 42, containLabel: true },
    xAxis: { ...categoryAxis(theme, dimensions), splitArea: { show: true, areaStyle: { color: [theme.palette.panel, theme.palette.gridSubtle] } } },
    yAxis: { ...categoryAxis(theme, domains), inverse: true, splitArea: { show: true, areaStyle: { color: [theme.palette.panel, theme.palette.gridSubtle] } } },
    visualMap: {
      type: "piecewise",
      orient: "horizontal",
      left: "center",
      bottom: 0,
      itemWidth: 10,
      itemHeight: 8,
      textStyle: { color: theme.palette.label, fontSize: 10 },
      pieces: [
        { value: 3, label: "完整", color: theme.palette.success },
        { value: 2, label: "部分", color: theme.palette.warning },
        { value: 1, label: "缺失", color: theme.palette.muted },
        { value: 0, label: "阻塞", color: theme.palette.danger },
        { value: 4, label: "不适用", color: theme.palette.grid },
      ],
    },
    series: [
      {
        type: "heatmap",
        data,
        label: {
          show: true,
          color: theme.palette.panel,
          fontSize: 10,
          fontWeight: 700,
          formatter: (params: unknown) => {
            const item = chartParamRecord(chartParamRecord(params).data)
            const status = String(item.status ?? "missing") as AdminReadinessStatus
            return statusLabels[status]
          },
        },
        itemStyle: { borderColor: theme.palette.panel, borderWidth: 3, borderRadius: 5 },
        emphasis: { itemStyle: { borderColor: theme.palette.text, borderWidth: 1 } },
      },
    ],
  })
}

export function createBulletProgressChartOption(
  theme: AdminChartTheme,
  segments: AdminBulletSegment[],
  config: { target?: number; targetLabel?: string; max?: number; unit?: string; label?: string } = {},
): EChartsOption | undefined {
  const usable = segments.filter((segment) => Number.isFinite(segment.value) && segment.value >= 0)
  if (usable.length === 0) return undefined
  const total = usable.reduce((sum, segment) => sum + segment.value, 0)
  const max = Math.max(config.max ?? 0, config.target ?? 0, total, 1)
  return createAdminChartOption(theme, {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value: unknown) => `${formatAdminChartNumber(Number(value), 2)}${config.unit ? ` ${config.unit}` : ""}`,
    },
    grid: { top: 34, left: 10, right: 28, bottom: 12, containLabel: true },
    xAxis: {
      ...valueAxis(theme),
      max: niceAdminAxisMaximum(max * 1.04),
      axisLabel: { color: theme.palette.axis, fontSize: 11, margin: 10, formatter: (value: number) => formatAdminAxisNumber(value) },
    },
    yAxis: { ...categoryAxis(theme, [config.label ?? "进展"]), axisLabel: { color: theme.palette.label, width: 96, overflow: "truncate" } },
    series: usable.map<SeriesOption>((segment, index) => ({
      type: "bar",
      name: segment.name,
      stack: "coverage",
      barWidth: 26,
      data: [segment.value],
      itemStyle: { color: getAdminChartColor(theme, segment.colorKey, index), borderRadius: index === 0 ? [5, 0, 0, 5] : index === usable.length - 1 ? [0, 5, 5, 0] : 0 },
      markLine:
        index === 0 && config.target !== undefined
          ? {
              silent: true,
              symbol: ["none", "none"],
              lineStyle: { color: theme.palette.text, width: 1.5 },
              label: { color: theme.palette.label, formatter: config.targetLabel ?? `目标 ${formatAdminChartNumber(config.target, 1)}${config.unit ?? ""}` },
              data: [{ xAxis: config.target }],
            }
          : undefined,
    })),
  })
}

export function createMarketPriceVolumeChartOption(
  theme: AdminChartTheme,
  points: AdminMarketPriceVolumePoint[],
  config: { priceUnit?: string; volumeUnit?: string; priceLabel?: string } = {},
): EChartsOption | undefined {
  if (points.length === 0) return undefined
  const useZoom = points.length > 16
  return createAdminChartOption(theme, {
    xAxis: {
      ...categoryAxis(
        theme,
        points.map((point) => point.period),
      ),
      boundaryGap: true,
    },
    yAxis: [valueAxis(theme, config.volumeUnit), { ...valueAxis(theme, config.priceUnit), scale: true, splitLine: { show: false } }],
    dataZoom: useZoom
      ? [
          { type: "inside", start: 0, end: 100 },
          { type: "slider", height: 16, bottom: 0, borderColor: theme.palette.grid, fillerColor: `${theme.palette.carbon}1f` },
        ]
      : undefined,
    grid: { top: 34, left: 10, right: 18, bottom: useZoom ? 42 : 12, containLabel: true },
    series: [
      {
        type: "bar",
        name: "成交量",
        data: points.map((point) => point.volume ?? 0),
        barMaxWidth: 14,
        itemStyle: { color: theme.palette.neutral, opacity: 0.34, borderRadius: [4, 4, 0, 0] },
      },
      {
        type: "line",
        name: config.priceLabel ?? "价格",
        yAxisIndex: 1,
        smooth: false,
        connectNulls: false,
        showSymbol: true,
        symbolSize: 6,
        data: points.map((point) => point.price),
        lineStyle: { color: theme.palette.carbon, width: 2.4 },
        itemStyle: { color: theme.palette.carbon, borderColor: theme.palette.panel, borderWidth: 1.5 },
      },
    ],
  })
}

export function createTornadoChartOption(theme: AdminChartTheme, items: AdminTornadoItem[], config: { unit?: string } = {}): EChartsOption | undefined {
  if (items.length === 0) return undefined
  return createAdminChartOption(theme, {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value: unknown) => `${formatAdminChartNumber(Number(value), 2)}${config.unit ? ` ${config.unit}` : ""}`,
    },
    grid: { top: 16, left: 12, right: 24, bottom: 10, containLabel: true },
    xAxis: { ...valueAxis(theme, config.unit), axisLabel: { color: theme.palette.axis, formatter: (value: number) => formatAdminChartNumber(Math.abs(value), 0) } },
    yAxis: {
      ...categoryAxis(
        theme,
        items.map((item) => item.name),
      ),
      inverse: true,
    },
    series: [
      {
        type: "bar",
        name: "下行情景",
        stack: "impact",
        data: items.map((item) => -Math.abs(item.downside)),
        itemStyle: { color: theme.palette.success, borderRadius: [5, 0, 0, 5] },
        barMaxWidth: 18,
      },
      {
        type: "bar",
        name: "上行情景",
        stack: "impact",
        data: items.map((item) => Math.abs(item.upside)),
        itemStyle: { color: theme.palette.warning, borderRadius: [0, 5, 5, 0] },
        barMaxWidth: 18,
      },
    ],
  })
}
