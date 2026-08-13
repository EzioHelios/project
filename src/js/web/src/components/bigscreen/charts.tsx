import type { EChartsOption } from "echarts"
import ReactECharts from "echarts-for-react"

import type { BigscreenComparisonItem, BigscreenDistributionItem, BigscreenFlowData, BigscreenTrendPoint } from "@/lib/bigscreen/types"

const baseText = "#dbeafe"
const mutedText = "rgba(219,234,254,0.58)"
const gridColor = "rgba(147,197,253,0.12)"
const palette = ["#38bdf8", "#fbbf24", "#34d399", "#a78bfa", "#f87171", "#22d3ee", "#f59e0b"]
const sankeyPalette = ["#38bdf8", "#34d399", "#a78bfa", "#22d3ee", "#6ee7b7", "#818cf8", "#94a3b8"]

function shell(option?: EChartsOption, height = 260, emptyLabel = "暂无数据") {
  if (!option) {
    return <div className="bigscreen-empty-state flex h-full min-h-[220px] items-center justify-center text-sm text-white/45">{emptyLabel}</div>
  }
  return <ReactECharts option={option} style={{ width: "100%", height: `${height}px` }} opts={{ renderer: "canvas" }} />
}

export function BigscreenLineChart({ points, height = 260, mode = "energy-carbon" }: { points: BigscreenTrendPoint[]; height?: number; mode?: "energy-carbon" | "single" }) {
  if (points.length === 0) return shell(undefined, height)
  const option: EChartsOption =
    mode === "single"
      ? {
          animationDuration: 400,
          grid: { top: 24, left: 16, right: 16, bottom: 24, containLabel: true },
          tooltip: { trigger: "axis" },
          xAxis: { type: "category", data: points.map((point) => point.period), axisLine: { lineStyle: { color: gridColor } }, axisLabel: { color: mutedText } },
          yAxis: { type: "value", splitLine: { lineStyle: { color: gridColor } }, axisLabel: { color: mutedText } },
          series: [
            {
              type: "line",
              smooth: true,
              showSymbol: false,
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
  if (items.length === 0) return shell(undefined, height)
  const option: EChartsOption = {
    animationDuration: 400,
    tooltip: { trigger: "item" },
    legend: { bottom: 0, textStyle: { color: mutedText } },
    series: [
      {
        type: "pie",
        radius: ["44%", "72%"],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: "rgba(5, 20, 38, 0.24)", borderWidth: 1 },
        label: { color: baseText, formatter: "{b}\n{d}%" },
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

export function BigscreenBarChart({ items, height = 260, unit }: { items: BigscreenDistributionItem[]; height?: number; unit?: string }) {
  if (items.length === 0) return shell(undefined, height)
  const sortedItems = [...items].sort((left, right) => right.value - left.value)
  const option: EChartsOption = {
    animationDuration: 400,
    grid: { top: 12, left: 16, right: 16, bottom: 24, containLabel: true },
    tooltip: { trigger: "axis" },
    xAxis: { type: "value", splitLine: { lineStyle: { color: gridColor } }, axisLabel: { color: mutedText, formatter: unit ? `{value} ${unit}` : undefined } },
    yAxis: { type: "category", data: sortedItems.map((item) => item.name), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: baseText } },
    series: [
      {
        type: "bar",
        data: sortedItems.map((item, index) => ({ value: item.value, itemStyle: { color: palette[index % palette.length], borderRadius: [0, 0, 0, 0] } })),
        barWidth: 14,
      },
    ],
  }
  return shell(option, height)
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

export function BigscreenSankeyChart({ flow, height = 320 }: { flow: BigscreenFlowData; height?: number }) {
  if (flow.nodes.length === 0 || flow.links.length === 0) return shell(undefined, height, "暂无流向数据")
  const option: EChartsOption = {
    animationDuration: 400,
    tooltip: { trigger: "item", triggerOn: "mousemove" },
    series: [
      {
        type: "sankey",
        layout: "none",
        data: flow.nodes.map((node, index) => ({
          name: node.name,
          itemStyle: { color: sankeyPalette[index % sankeyPalette.length], borderColor: "rgba(255,255,255,0.18)" },
        })),
        links: flow.links.map((link) => ({
          source: flow.nodes.find((node) => node.id === link.source)?.name ?? link.source,
          target: flow.nodes.find((node) => node.id === link.target)?.name ?? link.target,
          value: link.value,
        })),
        lineStyle: { color: "gradient", curveness: 0.45, opacity: 0.38 },
        label: { color: baseText, fontSize: 12 },
        emphasis: { focus: "adjacency" },
      },
    ],
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
