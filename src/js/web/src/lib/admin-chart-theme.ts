import type { EChartsOption, SeriesOption } from "echarts"

export const adminChartPalette = {
  energy: "#16808a",
  electricity: "#2f77a1",
  fuel: "#6d7458",
  heat: "#a97935",
  steam: "#6c8793",
  water: "#2f8ea7",
  carbon: "#2f7d68",
  scope1: "#8a6a46",
  scope2: "#356f96",
  scope3: "#477d6e",
  cost: "#9a7934",
  warning: "#a57928",
  danger: "#a34f48",
  success: "#2f7d68",
  neutral: "#64717f",
  muted: "#98a4b1",
  axis: "#758391",
  grid: "#dbe6ec",
  gridSubtle: "#edf4f7",
  text: "#142232",
  label: "#455766",
  panel: "#ffffff",
} as const

export type AdminChartColorKey = keyof typeof adminChartPalette

export const adminChartSeriesColors = [
  adminChartPalette.energy,
  adminChartPalette.electricity,
  adminChartPalette.carbon,
  adminChartPalette.heat,
  adminChartPalette.water,
  adminChartPalette.cost,
  adminChartPalette.scope1,
  adminChartPalette.scope2,
  adminChartPalette.scope3,
  adminChartPalette.neutral,
  adminChartPalette.danger,
]

type AdminChartOptionConfig = {
  compact?: boolean
}

export type AdminChartDatum = Record<string, unknown>

export type AdminChartSeriesConfig<K extends string = string> = {
  key: K
  label: string
  color?: string
  colorKey?: AdminChartColorKey
}

export type AdminChartBarSeriesConfig<K extends string = string> = AdminChartSeriesConfig<K> & {
  stack?: string
}

export type AdminChartLineSeriesConfig<K extends string = string> = AdminChartSeriesConfig<K> & {
  yAxisIndex?: number
}

export type AdminChartRankingItem = {
  name: string
  value: number
}

export type AdminChartDistributionItem = {
  name: string
  value: number
}

export type AdminChartFlowNode = {
  id: string
  name: string
  value?: number
  category?: string
}

export type AdminChartFlowLink = {
  source: string
  target: string
  value: number
}

export function getAdminChartColor(key: AdminChartColorKey | undefined, fallbackIndex = 0) {
  if (key && adminChartPalette[key]) return adminChartPalette[key]
  return adminChartSeriesColors[fallbackIndex % adminChartSeriesColors.length]
}

export function formatAdminChartNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return Number(value).toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
  })
}

export function createAdminChartOption(option: EChartsOption, config: AdminChartOptionConfig = {}): EChartsOption {
  const compact = config.compact ?? false
  return {
    color: adminChartSeriesColors,
    backgroundColor: "transparent",
    animationDuration: 420,
    animationDurationUpdate: 260,
    animationEasing: "cubicOut",
    animationEasingUpdate: "cubicOut",
    textStyle: {
      color: adminChartPalette.text,
      fontFamily: "inherit",
      fontSize: 12,
    },
    grid: {
      top: compact ? 14 : 32,
      left: 10,
      right: 18,
      bottom: 12,
      containLabel: true,
    },
    legend: {
      top: 0,
      left: 0,
      icon: "roundRect",
      itemWidth: 10,
      itemHeight: 8,
      itemGap: 16,
      textStyle: {
        color: adminChartPalette.label,
        fontSize: 11,
        fontWeight: 500,
      },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(15, 32, 42, 0.96)",
      borderColor: "rgba(154, 215, 224, 0.18)",
      borderWidth: 1,
      padding: [9, 11],
      textStyle: {
        color: "#f8fafc",
        fontSize: 12,
      },
      extraCssText: "border-radius:6px;box-shadow:0 14px 34px rgba(15,32,42,.26);",
    },
    ...option,
  }
}

export const adminChartAxis = {
  category(data: string[] | number[]) {
    return {
      type: "category" as const,
      data,
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: adminChartPalette.axis, fontSize: 11, margin: 10 },
    }
  },
  value(name?: string) {
    return {
      type: "value" as const,
      name,
      nameTextStyle: { color: adminChartPalette.axis, fontSize: 11, padding: [0, 0, 6, 0] },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: adminChartPalette.axis, fontSize: 11, margin: 10 },
      splitLine: { lineStyle: { color: adminChartPalette.grid, type: "dashed" as const } },
    }
  },
}

function readChartNumber<T extends AdminChartDatum>(point: T, key: string) {
  return Number(point[key] ?? 0)
}

function readChartLabel<T extends AdminChartDatum>(point: T, key: string) {
  const value = point[key]
  return value === null || value === undefined ? "" : String(value)
}

function resolveSeriesColor(series: AdminChartSeriesConfig, index: number) {
  return series.color ?? getAdminChartColor(series.colorKey, index)
}

function buildLineSeries<T extends AdminChartDatum>(points: T[], lines: AdminChartSeriesConfig<Extract<keyof T, string>>[]): SeriesOption[] {
  return lines
    .filter((line) => points.some((point) => readChartNumber(point, line.key) > 0))
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
          width: 2.25,
          color,
        },
        itemStyle: {
          color,
        },
        areaStyle: { color: `${color}12` },
        emphasis: { focus: "series" },
        data: points.map((point) => readChartNumber(point, line.key)),
      }
    })
}

export function createTrendChartOption<T extends AdminChartDatum>(
  points: T[],
  lines: AdminChartSeriesConfig<Extract<keyof T, string>>[],
  config: { periodKey?: Extract<keyof T, string> } = {},
): EChartsOption | undefined {
  if (points.length === 0) return undefined
  const periodKey = config.periodKey ?? ("period" as Extract<keyof T, string>)
  return createAdminChartOption({
    xAxis: {
      ...adminChartAxis.category(points.map((point) => readChartLabel(point, periodKey))),
      boundaryGap: false,
    },
    yAxis: adminChartAxis.value(),
    series: buildLineSeries(points, lines),
  })
}

export function createComboTrendChartOption<T extends AdminChartDatum>(
  points: T[],
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
  const barSeries = config.bars
    .filter((bar) => points.some((point) => readChartNumber(point, bar.key) > 0))
    .map<SeriesOption>((bar, index) => ({
      type: "bar",
      name: bar.label,
      stack: bar.stack,
      barMaxWidth: 14,
      showBackground: true,
      backgroundStyle: {
        color: adminChartPalette.gridSubtle,
        borderRadius: [5, 5, 0, 0],
      },
      itemStyle: {
        color: resolveSeriesColor(bar, index),
        borderRadius: [5, 5, 0, 0],
      },
      emphasis: { focus: "series" },
      data: points.map((point) => readChartNumber(point, bar.key)),
    }))
  const lineSeries = config.lines
    .filter((line) => points.some((point) => readChartNumber(point, line.key) > 0))
    .map<SeriesOption>((line, index) => ({
      type: "line",
      name: line.label,
      smooth: true,
      showSymbol: false,
      yAxisIndex: line.yAxisIndex ?? 1,
      lineStyle: {
        width: 2.25,
        color: resolveSeriesColor(line, index + config.bars.length),
      },
      itemStyle: {
        color: resolveSeriesColor(line, index + config.bars.length),
      },
      data: points.map((point) => readChartNumber(point, line.key)),
    }))
  if (barSeries.length === 0 && lineSeries.length === 0) return undefined
  return createAdminChartOption({
    xAxis: adminChartAxis.category(points.map((point) => readChartLabel(point, periodKey))),
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

export function createRankingChartOption(items: AdminChartRankingItem[], config: { unit?: string; colorKey?: AdminChartColorKey; limit?: number } = {}): EChartsOption | undefined {
  if (items.length === 0) return undefined
  const unit = config.unit
  const sliced = items.slice(0, config.limit ?? 10)
  return createAdminChartOption({
    tooltip: {
      trigger: "item",
      formatter: (params: { name: string; value: number }) => `${params.name}<br/>${formatAdminChartNumber(params.value, 2)}${unit ? ` ${unit}` : ""}`,
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
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: adminChartPalette.axis,
        margin: 10,
        formatter: (value: number) => `${formatAdminChartNumber(value, 0)}${unit ? ` ${unit}` : ""}`,
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
          borderRadius: [0, 5, 5, 0],
          color: getAdminChartColor(config.colorKey ?? "energy"),
        },
        showBackground: true,
        backgroundStyle: {
          color: adminChartPalette.gridSubtle,
          borderRadius: [0, 5, 5, 0],
        },
        label: {
          show: true,
          position: "right",
          color: adminChartPalette.label,
          fontWeight: 600,
          formatter: ({ value }: { value: number }) => `${formatAdminChartNumber(value, 2)}${unit ? ` ${unit}` : ""}`,
        },
      },
    ],
  })
}

export function createDistributionChartOption(items: AdminChartDistributionItem[], config: { unit?: string } = {}): EChartsOption | undefined {
  if (items.length === 0) return undefined
  const unit = config.unit ?? ""
  return createAdminChartOption({
    tooltip: {
      trigger: "item",
      formatter: (params: { name: string; value: number; percent: number }) =>
        `${params.name}<br/>${formatAdminChartNumber(params.value, 2)}${unit ? ` ${unit}` : ""} (${params.percent}%)`,
    },
    series: [
      {
        type: "pie",
        radius: ["54%", "76%"],
        center: ["50%", "55%"],
        avoidLabelOverlap: true,
        label: {
          formatter: "{b}",
          color: adminChartPalette.label,
          fontSize: 11,
        },
        labelLine: {
          lineStyle: { color: adminChartPalette.grid },
        },
        itemStyle: {
          borderColor: adminChartPalette.panel,
          borderWidth: 3,
        },
        data: items,
      },
    ],
  })
}

export function createGaugeChartOption(value: number, config: { suffix?: string } = {}): EChartsOption {
  const suffix = config.suffix ?? ""
  return createAdminChartOption({
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
          itemStyle: {
            color: value >= 80 ? adminChartPalette.success : value >= 50 ? adminChartPalette.warning : adminChartPalette.danger,
          },
        },
        axisLine: {
          lineStyle: {
            width: 10,
            color: [[1, adminChartPalette.gridSubtle]],
          },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, "10%"],
          fontSize: 23,
          fontWeight: 650,
          formatter: `{value}${suffix}`,
          color: adminChartPalette.text,
        },
        data: [{ value }],
      },
    ],
  })
}

export function createSankeyChartOption(
  nodes: AdminChartFlowNode[],
  links: AdminChartFlowLink[],
  config: { categoryColorMap?: Record<string, AdminChartColorKey> } = {},
): EChartsOption | undefined {
  if (nodes.length === 0 || links.length === 0) return undefined
  const nameMap = new Map(nodes.map((node) => [node.id, node]))
  const categoryColorMap = {
    scope: "text",
    source: "energy",
    conversion: "cost",
    distribution: "scope2",
    use_system: "carbon",
    area: "scope3",
    result: "success",
    loss: "danger",
    ...config.categoryColorMap,
  } satisfies Record<string, AdminChartColorKey>
  const colorForCategory = (category?: string) => getAdminChartColor(category ? categoryColorMap[category] : undefined, adminChartSeriesColors.length - 2)
  const sankeyNodes = nodes.map((node) => ({
    name: node.id,
    value: node.value ?? 0,
    itemStyle: { color: colorForCategory(node.category) },
    label: {
      color: adminChartPalette.label,
      fontSize: 12,
      formatter: () => {
        const amount = node.value && node.value > 0 ? `\n${formatAdminChartNumber(node.value, 2)}` : ""
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
          return `${sourceNode?.name ?? params.data.source}<br/>-> ${targetNode?.name ?? params.data.target}<br/>${formatAdminChartNumber(params.data.value ?? 0, 2)}`
        }
        const node = nameMap.get(params.name ?? "")
        return `${node?.name ?? params.name}<br/>${formatAdminChartNumber(params.value ?? 0, 2)}`
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
            const amount = node?.value && node.value > 0 ? `\n${formatAdminChartNumber(node.value, 2)}` : ""
            return `${node?.name ?? name}${amount}`
          },
        },
      },
    ],
  })
}
