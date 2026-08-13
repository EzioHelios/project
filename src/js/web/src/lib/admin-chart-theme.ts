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
export type AdminChartFlowNode = { id: string; name: string; value?: number; category?: string }
export type AdminChartFlowLink = { source: string; target: string; value: number }
export type AdminMarketKlinePoint = { trade_date: string; open: number; close: number; low: number; high: number; volume?: number | null }

export function getAdminChartColor(theme: AdminChartTheme, key: AdminChartColorKey | undefined, fallbackIndex = 0) {
  return key ? theme.palette[key] : theme.seriesColors[fallbackIndex % theme.seriesColors.length]
}

export function formatAdminChartNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits })
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
      axisLabel: { color: theme.palette.axis, margin: 10, formatter: (value: number) => `${formatAdminChartNumber(value, 0)}${unit ? ` ${unit}` : ""}` },
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
  config: { categoryColorMap?: Record<string, AdminChartColorKey> } = {},
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
        right: "4%",
        top: 24,
        bottom: 12,
        data: sankeyNodes,
        links: sankeyLinks,
        nodeAlign: "justify",
        draggable: false,
        nodeGap: 18,
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
          formatter: (params: unknown) => {
            const node = nameMap.get(String(chartParamRecord(params).name ?? ""))
            return `${node?.name ?? ""}${node?.value && node.value > 0 ? `\n${formatAdminChartNumber(node.value, 2)}` : ""}`
          },
        },
      },
    ],
  })
}

export function createMarketKlineChartOption(theme: AdminChartTheme, points: AdminMarketKlinePoint[], config: { showVolume?: boolean } = {}): EChartsOption | undefined {
  if (points.length === 0) return undefined
  const priceSeries: SeriesOption = {
    type: "candlestick",
    name: "价格",
    data: points.map((point) => [point.open, point.close, point.low, point.high]),
    itemStyle: { color: theme.palette.danger, color0: theme.palette.success, borderColor: theme.palette.danger, borderColor0: theme.palette.success },
  }
  const volumeSeries: SeriesOption | null =
    (config.showVolume ?? true)
      ? {
          type: "bar",
          name: "成交量",
          yAxisIndex: 1,
          barMaxWidth: 10,
          itemStyle: { color: theme.palette.neutral, opacity: 0.3, borderRadius: [4, 4, 0, 0] },
          data: points.map((point) => point.volume ?? 0),
        }
      : null
  return createAdminChartOption(theme, {
    legend: { top: 0, left: 0 },
    xAxis: categoryAxis(
      theme,
      points.map((point) => point.trade_date),
    ),
    yAxis: [valueAxis(theme, "元/吨"), { ...valueAxis(theme, "吨"), splitLine: { show: false } }],
    series: volumeSeries ? [priceSeries, volumeSeries] : [priceSeries],
  })
}
