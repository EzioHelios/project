import type { EChartsOption } from "echarts"

export const adminChartPalette = {
  energy: "#2f6f7e",
  carbon: "#2d7d67",
  scope1: "#9a5b36",
  scope2: "#2f6f7e",
  scope3: "#5d7f4f",
  cost: "#b0792f",
  warning: "#b0792f",
  danger: "#b34a42",
  success: "#2d7d67",
  neutral: "#6b7480",
  muted: "#9aa4b2",
  axis: "#8290a0",
  grid: "#e4e9ef",
  text: "#172033",
  label: "#485568",
  panel: "#ffffff",
} as const

export type AdminChartColorKey = keyof typeof adminChartPalette

export const adminChartSeriesColors = [
  adminChartPalette.energy,
  adminChartPalette.carbon,
  adminChartPalette.cost,
  adminChartPalette.scope1,
  adminChartPalette.scope3,
  adminChartPalette.neutral,
  adminChartPalette.danger,
]

type AdminChartOptionConfig = {
  compact?: boolean
}

export function getAdminChartColor(key: AdminChartColorKey | undefined, fallbackIndex = 0) {
  if (key && adminChartPalette[key]) return adminChartPalette[key]
  return adminChartSeriesColors[fallbackIndex % adminChartSeriesColors.length]
}

export function createAdminChartOption(option: EChartsOption, config: AdminChartOptionConfig = {}): EChartsOption {
  const compact = config.compact ?? false
  return {
    color: adminChartSeriesColors,
    animationDuration: 360,
    animationDurationUpdate: 240,
    textStyle: {
      color: adminChartPalette.text,
      fontFamily: "inherit",
      fontSize: 12,
    },
    grid: {
      top: compact ? 16 : 34,
      left: 12,
      right: 18,
      bottom: 12,
      containLabel: true,
    },
    legend: {
      top: 0,
      left: 0,
      icon: "circle",
      itemWidth: 8,
      itemHeight: 8,
      itemGap: 14,
      textStyle: {
        color: adminChartPalette.label,
        fontSize: 11,
      },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(23, 32, 51, 0.96)",
      borderWidth: 0,
      padding: [8, 10],
      textStyle: {
        color: "#f8fafc",
        fontSize: 12,
      },
      extraCssText: "border-radius:6px;box-shadow:0 10px 28px rgba(23,32,51,.22);",
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
      axisLine: { lineStyle: { color: adminChartPalette.grid } },
      axisLabel: { color: adminChartPalette.axis, fontSize: 11 },
    }
  },
  value(name?: string) {
    return {
      type: "value" as const,
      name,
      nameTextStyle: { color: adminChartPalette.axis, fontSize: 11 },
      axisLabel: { color: adminChartPalette.axis, fontSize: 11 },
      splitLine: { lineStyle: { color: adminChartPalette.grid, type: "dashed" as const } },
    }
  },
}
