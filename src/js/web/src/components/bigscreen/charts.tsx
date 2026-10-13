import type { EChartsOption } from "echarts"
import ReactECharts from "echarts-for-react"
import { useState } from "react"
import { createSankeyChartOption, getAdminChartTheme } from "@/lib/admin-chart-theme"

import type { BigscreenComparisonItem, BigscreenDistributionItem, BigscreenFlowData, BigscreenTrendPoint } from "@/lib/bigscreen/types"

const baseText = "#dbeafe"
const mutedText = "rgba(219,234,254,0.58)"
const gridColor = "rgba(147,197,253,0.12)"
const palette = ["#38bdf8", "#fbbf24", "#34d399", "#a78bfa", "#f87171", "#22d3ee", "#f59e0b"]
const sankeyPalette = ["#38bdf8", "#34d399", "#a78bfa", "#22d3ee", "#6ee7b7", "#818cf8", "#94a3b8"]

type ChartClick = (event: { componentType: string; dataIndex: number }) => void

function ScreenChart({ option, height, onClick }: { option: EChartsOption; height: number | string; onClick?: ChartClick }) {
  const [ready, setReady] = useState(false)
  return (
    <div data-chart-ready={ready} style={{ height }}>
      <ReactECharts
        option={option}
        notMerge
        style={{ width: "100%", height }}
        opts={{ renderer: "canvas" }}
        onEvents={{ finished: () => setReady(true), ...(onClick ? { click: onClick } : {}) }}
      />
    </div>
  )
}

function shell(option?: EChartsOption, height: number | string = 260, emptyLabel = "暂无数据", onClick?: ChartClick) {
  if (!option) {
    return (
      <div className="bigscreen-empty-state flex items-center justify-center text-sm text-white/45" style={{ height }}>
        {emptyLabel}
      </div>
    )
  }
  return <ScreenChart key={JSON.stringify(option)} option={option} height={height} onClick={onClick} />
}

export function BigscreenLineChart({
  points,
  height = 260,
  mode = "energy-carbon",
}: {
  points: BigscreenTrendPoint[]
  height?: number | string
  mode?: "energy-carbon" | "single"
}) {
  if (points.length === 0) return shell(undefined, height)
  const option: EChartsOption =
    mode === "single"
      ? {
          animationDuration: 400,
          grid: { top: 34, left: 16, right: 24, bottom: 24, containLabel: true },
          tooltip: { trigger: "axis" },
          xAxis: { type: "category", data: points.map((point) => point.period), axisLine: { lineStyle: { color: gridColor } }, axisLabel: { color: mutedText } },
          yAxis: { type: "value", name: "kWh", nameTextStyle: { color: mutedText }, splitLine: { lineStyle: { color: gridColor } }, axisLabel: { color: mutedText } },
          series: [
            {
              type: "line",
              smooth: false,
              showSymbol: points.length < 32,
              connectNulls: false,
              data: points.map((point) => point.value),
              lineStyle: { color: palette[0], width: 3 },
              areaStyle: { color: "rgba(56, 189, 248, 0.16)" },
            },
          ],
        }
      : {
          animationDuration: 400,
          grid: { top: 30, left: 16, right: 16, bottom: 24, containLabel: true },
          tooltip: { trigger: "axis" },
          legend: { top: 0, textStyle: { color: mutedText } },
          xAxis: { type: "category", data: points.map((point) => point.period), axisLine: { lineStyle: { color: gridColor } }, axisLabel: { color: mutedText } },
          yAxis: [
            { type: "value", splitLine: { lineStyle: { color: gridColor } }, axisLabel: { color: mutedText } },
            { type: "value", splitLine: { show: false }, axisLabel: { color: mutedText } },
          ],
          series: [
            {
              type: "bar",
              name: "能耗",
              data: points.map((point) => point.energy_kwh),
              itemStyle: { color: "rgba(56, 189, 248, 0.72)", borderRadius: [0, 0, 0, 0] },
            },
            {
              type: "line",
              name: "碳排",
              yAxisIndex: 1,
              smooth: true,
              showSymbol: false,
              data: points.map((point) => point.carbon_co2e),
              lineStyle: { color: palette[1], width: 3 },
              itemStyle: { color: palette[1] },
            },
          ],
        }
  return shell(option, height)
}

export function BigscreenPieChart({ items, height = 260 }: { items: BigscreenDistributionItem[]; height?: number }) {
  items = items.filter((item) => item.value > 0)
  if (items.length === 0) return shell(undefined, height)
  const option: EChartsOption = {
    animationDuration: 400,
    tooltip: { trigger: "item" },
    legend: { bottom: 0, textStyle: { color: mutedText } },
    series: [
      {
        type: "pie",
        radius: ["35%", "59%"],
        center: ["50%", "42%"],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: "rgba(5, 20, 38, 0.24)", borderWidth: 1 },
        label: { color: baseText, formatter: "{d}%" },
        data: items.map((item, index) => ({
          name: item.name,
          value: item.value,
          itemStyle: { color: palette[index % palette.length] },
        })),
      },
    ],
  }
  return shell(option, height)
}

export function BigscreenLedgerChart({ points, height = 160 }: { points: Array<{ period: string; inbound: number | null; outbound: number | null }>; height?: number }) {
  if (!points.length) return shell(undefined, height, "暂无带日期的经营台账")
  return shell(
    {
      animationDuration: 400,
      grid: { top: 34, left: 8, right: 16, bottom: 8, containLabel: true },
      tooltip: { trigger: "axis", valueFormatter: (value) => (value == null ? "未记录" : `${Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 2 })} 万元`) },
      legend: { top: 0, textStyle: { color: mutedText } },
      xAxis: {
        type: "category",
        data: points.map((point) => point.period),
        axisLine: { lineStyle: { color: gridColor } },
        axisLabel: { color: mutedText, formatter: (value: string) => value.slice(2) },
      },
      yAxis: { type: "value", name: "万元", splitNumber: 3, nameTextStyle: { color: mutedText }, splitLine: { lineStyle: { color: gridColor } }, axisLabel: { color: mutedText } },
      series: (
        [
          ["inbound", "入库"],
          ["outbound", "出库"],
        ] as const
      ).map(([key, name], index) => ({
        type: "line",
        name,
        connectNulls: false,
        showSymbol: true,
        symbolSize: 5,
        data: points.map((point) => point[key]),
        lineStyle: { color: palette[index], width: 2 },
        itemStyle: { color: palette[index] },
      })),
    },
    height,
  )
}

export function BigscreenBarChart({
  items,
  height = 260,
  unit,
  onSelect,
}: {
  items: BigscreenDistributionItem[]
  height?: number | string
  unit?: string
  onSelect?: (item: BigscreenDistributionItem) => void
}) {
  if (items.length === 0) return shell(undefined, height)
  const sortedItems = [...items].sort((left, right) => right.value - left.value)
  const option: EChartsOption = {
    animationDuration: 400,
    grid: { top: 12, left: 4, right: 24, bottom: 32, containLabel: true },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "value",
      name: unit,
      nameLocation: "middle",
      nameGap: 22,
      nameTextStyle: { color: mutedText },
      splitNumber: 3,
      splitLine: { lineStyle: { color: gridColor } },
      axisLabel: { color: mutedText },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: sortedItems.map((item) => item.name),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: baseText, width: 105, overflow: "truncate" },
    },
    series: [
      {
        type: "bar",
        data: sortedItems.map((item) => ({ value: item.value, itemStyle: { color: palette[0] } })),
        barWidth: 14,
      },
    ],
  }
  return shell(
    option,
    height,
    "暂无数据",
    onSelect
      ? (event) => {
          if (event.componentType === "series" && sortedItems[event.dataIndex]) onSelect(sortedItems[event.dataIndex])
        }
      : undefined,
  )
}

export function BigscreenLoadCompositeChart({ points, height = 260 }: { points: BigscreenTrendPoint[]; height?: number }) {
  if (points.length === 0) return shell(undefined, height)
  const option: EChartsOption = {
    animationDuration: 500,
    grid: { top: 28, left: 20, right: 20, bottom: 24, containLabel: true },
    tooltip: { trigger: "axis" },
    legend: { top: 0, textStyle: { color: mutedText } },
    xAxis: {
      type: "category",
      data: points.map((point) => point.period),
      axisLine: { lineStyle: { color: gridColor } },
      axisLabel: { color: mutedText },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: "value",
        name: "能耗",
        nameTextStyle: { color: mutedText },
        splitLine: { lineStyle: { color: gridColor } },
        axisLabel: { color: mutedText },
      },
      {
        type: "value",
        name: "碳排",
        nameTextStyle: { color: mutedText },
        splitLine: { show: false },
        axisLabel: { color: mutedText },
      },
    ],
    series: [
      {
        type: "line",
        name: "能耗",
        smooth: true,
        showSymbol: false,
        yAxisIndex: 0,
        data: points.map((point) => point.energy_kwh),
        lineStyle: { color: palette[0], width: 3 },
        areaStyle: { color: "rgba(56, 189, 248, 0.18)" },
      },
      {
        type: "bar",
        name: "每日碳排放",
        yAxisIndex: 1,
        data: points.map((point) => point.carbon_co2e),
        barWidth: 14,
        itemStyle: { color: "rgba(251, 191, 36, 0.74)", borderRadius: [0, 0, 0, 0] },
      },
    ],
  }
  return shell(option, height)
}

export function BigscreenSankeyChart({ flow, height = 320 }: { flow: BigscreenFlowData; height?: number | string }) {
  const base = getAdminChartTheme("energy", "dark")
  const theme = {
    ...base,
    flowColors: sankeyPalette,
    palette: { ...base.palette, text: baseText, label: baseText, panel: "transparent" },
    tooltip: { ...base.tooltip, background: "#071e32", text: baseText },
  }
  const option = createSankeyChartOption(
    theme,
    flow.nodes.map((node) => ({ ...node, value: node.value ?? undefined, category: node.category ?? undefined })),
    flow.links,
    {
      labelWidth: 176,
      nodeGap: 28,
      right: "18%",
      categoryColorMap: { boundary: "electricity", classification: "scope2", category: "carbon", resource: "scope3", equipment: "scope3" },
    },
  )
  if (option) {
    option.animationDuration = 400
    option.tooltip = {
      ...option.tooltip,
      valueFormatter: (value) => `${Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 2 })} ${flow.unit ?? ""}`,
    }
  }
  return shell(option, height, "暂无流向数据")
}

export function BigscreenCompareChart({ items, height = 250 }: { items: BigscreenComparisonItem[]; height?: number }) {
  if (items.length === 0) return shell(undefined, height)
  const option: EChartsOption = {
    animationDuration: 400,
    grid: { top: 16, left: 16, right: 16, bottom: 24, containLabel: true },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: items.map((item) => item.name), axisLine: { lineStyle: { color: gridColor } }, axisLabel: { color: mutedText } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: gridColor } }, axisLabel: { color: mutedText } },
    series: [
      {
        type: "bar",
        data: items.map((item, index) => ({ value: item.current, itemStyle: { color: palette[index % palette.length], borderRadius: [0, 0, 0, 0] } })),
      },
    ],
  }
  return shell(option, height)
}
