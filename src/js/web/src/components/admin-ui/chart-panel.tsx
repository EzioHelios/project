import type { EChartsOption } from "echarts"
import { BarChart, GaugeChart, LineChart, PieChart, SankeyChart } from "echarts/charts"
import { GridComponent, LegendComponent, TitleComponent, TooltipComponent } from "echarts/components"
import * as echarts from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"
import ReactEChartsCore from "echarts-for-react/lib/core"
import type * as React from "react"

import { AdminEmptyState } from "@/components/admin-ui/empty-state"
import { AdminPanel } from "@/components/admin-ui/section"
import { cn } from "@/lib/utils"

echarts.use([LineChart, BarChart, PieChart, GaugeChart, SankeyChart, GridComponent, LegendComponent, TitleComponent, TooltipComponent, CanvasRenderer])

type ChartPanelProps = {
  title: React.ReactNode
  unit?: React.ReactNode
  source?: React.ReactNode
  updatedAt?: React.ReactNode
  actions?: React.ReactNode
  option?: EChartsOption
  height?: number
  emptyLabel?: React.ReactNode
  className?: string
}

export function ChartPanel({ title, unit, source, updatedAt, actions, option, height = 320, emptyLabel = "暂无图表数据", className }: ChartPanelProps) {
  const metaItems = [unit ? `单位：${unit}` : null, source ? `来源：${source}` : null, updatedAt ? `更新：${updatedAt}` : null].filter(Boolean)

  return (
    <AdminPanel title={title} actions={actions} className={className} contentClassName="pt-3" data-chart-panel="">
      {metaItems.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-x-3 gap-y-1 text-muted-foreground text-[0.72rem]">{metaItems.map((item) => item && <span key={item}>{item}</span>)}</div>
      )}
      {option ? (
        <ReactEChartsCore echarts={echarts} option={option} style={{ height: `${height}px`, width: "100%" }} className={cn("admin-chart", "min-w-0")} notMerge lazyUpdate />
      ) : (
        <AdminEmptyState title={emptyLabel} className="min-h-0" style={{ height: `${height}px` }} />
      )}
    </AdminPanel>
  )
}
