import { BigscreenCountUp, BigscreenHighlightCycle } from "@/components/bigscreen/motion"
import { BigscreenEmpty } from "@/components/bigscreen/panel"
import type { HuayiBigscreenKeyValue } from "@/lib/bigscreen/types"
import { cn } from "@/lib/utils"

function normalizeTone(tone?: string) {
  if (tone === "amber" || tone === "emerald") {
    return tone
  }
  return "cyan"
}

export function CarbonStatsBoard({
  metrics,
  className,
  variant = "default",
  highlightMode = "static",
}: {
  metrics: HuayiBigscreenKeyValue[]
  className?: string
  variant?: "default" | "dense" | "minimal"
  highlightMode?: "static" | "rotate"
}) {
  if (!metrics.length) {
    return <BigscreenEmpty label="暂无碳统计数据" />
  }

  const renderRow = (metric: HuayiBigscreenKeyValue, index: number, isActive: boolean) => (
    <article key={`${metric.label}-${index}`} className="bigscreen-carbon-stats-row" data-tone={normalizeTone(metric.tone)} data-highlight={isActive}>
      <div className="bigscreen-carbon-stats-row-label">{metric.label}</div>
      <div className="bigscreen-carbon-stats-row-main">
        <span className="bigscreen-carbon-stats-row-value">{typeof metric.value === "number" ? <BigscreenCountUp value={metric.value} /> : metric.value}</span>
        {metric.unit ? <span className="bigscreen-carbon-stats-row-unit">{metric.unit}</span> : null}
      </div>
    </article>
  )

  return (
    <div className={cn("bigscreen-carbon-stats-board", className)} data-variant={variant}>
      {highlightMode === "rotate" ? (
        <BigscreenHighlightCycle
          items={metrics}
          intervalMs={variant === "minimal" ? 2800 : 3200}
          getItemKey={(metric, index) => `${metric.label}-${index}`}
          renderItem={(metric, index, isActive) => renderRow(metric, index, isActive)}
        />
      ) : (
        metrics.map((metric, index) => renderRow(metric, index, index === 1))
      )}
    </div>
  )
}
