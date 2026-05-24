import { BigscreenCountUp } from "@/components/bigscreen/motion"
import { BigscreenEmpty } from "@/components/bigscreen/panel"
import type { HuayiBigscreenMetricGroup } from "@/lib/bigscreen/types"
import { cn } from "@/lib/utils"

type LoadSummaryPanelProps = {
  groups: HuayiBigscreenMetricGroup[]
  className?: string
  variant?: "default" | "dense"
}

function normalizeValue(value: number | string) {
  if (typeof value === "number") {
    return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })
  }
  return value
}

export function LoadSummaryPanel({ groups, className, variant = "default" }: LoadSummaryPanelProps) {
  if (groups.length === 0) {
    return <BigscreenEmpty label="暂无负荷数据" />
  }

  return (
    <div className={cn("bigscreen-load-summary", className)} data-variant={variant}>
      {groups.map((group) => {
        const [currentMetric, accumulatedMetric] = group.metrics
        return (
          <article key={group.id} className="bigscreen-load-summary-row">
            <div className="bigscreen-load-summary-title">{group.title}</div>
            <div className="bigscreen-load-summary-metrics">
              {currentMetric ? (
                <div className="bigscreen-load-summary-metric" data-slot="current">
                  <div className="bigscreen-load-summary-label">{currentMetric.label}</div>
                  <div className="bigscreen-load-summary-value">
                    {typeof currentMetric.value === "number" ? <BigscreenCountUp value={currentMetric.value} /> : normalizeValue(currentMetric.value)}
                    {currentMetric.unit ? <span className="bigscreen-load-summary-unit">{currentMetric.unit}</span> : null}
                  </div>
                </div>
              ) : null}
              {accumulatedMetric ? (
                <div className="bigscreen-load-summary-metric" data-slot="accumulated">
                  <div className="bigscreen-load-summary-label">{accumulatedMetric.label}</div>
                  <div className="bigscreen-load-summary-value">
                    {typeof accumulatedMetric.value === "number" ? <BigscreenCountUp value={accumulatedMetric.value} /> : normalizeValue(accumulatedMetric.value)}
                    {accumulatedMetric.unit ? <span className="bigscreen-load-summary-unit">{accumulatedMetric.unit}</span> : null}
                  </div>
                </div>
              ) : null}
            </div>
          </article>
        )
      })}
    </div>
  )
}
