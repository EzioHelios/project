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
  const metaItems = [unit ? { label: "单位", value: unit } : null, source ? { label: "来源", value: source } : null, updatedAt ? { label: "更新", value: updatedAt } : null].filter(
    Boolean,
  )
  const headerActions =
    metaItems.length > 0 || actions ? (
      <>
        {metaItems.length > 0 && (
          <div className="admin-chart-meta">
            {metaItems.map((item) =>
              item ? (
                <span className="admin-chart-meta-item" key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </span>
              ) : null,
            )}
          </div>
        )}
        {actions}
      </>
    ) : undefined

  return (
    <AdminPanel title={title} actions={headerActions} className={className} contentClassName="p-3" data-chart-panel="">
      {option ? (
        <div className="admin-chart-frame">
          <ReactEChartsCore echarts={echarts} option={option} style={{ height: `${height}px`, width: "100%" }} className={cn("admin-chart", "min-w-0")} notMerge lazyUpdate />
        </div>
      ) : (
        <AdminEmptyState title={emptyLabel} className="min-h-0" style={{ height: `${height}px` }} />
      )}
    </AdminPanel>
  )
}
