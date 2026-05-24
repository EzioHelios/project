import { BigscreenCountUp } from "@/components/bigscreen/motion"
import { BigscreenEmpty } from "@/components/bigscreen/panel"
import type { HuayiBigscreenMetricGroup } from "@/lib/bigscreen/types"
import { cn } from "@/lib/utils"

function normalizeTone(tone?: string) {
  if (tone === "amber" || tone === "emerald") {
    return tone
  }
  return "cyan"
}

export function ResourceConversionPanel({
  group,
  className,
  variant = "default",
}: {
  group: HuayiBigscreenMetricGroup | null | undefined
  className?: string
  variant?: "default" | "dense"
}) {
  if (!group) {
    return <BigscreenEmpty label="暂无环保数据" />
  }

  return (
    <div className={cn("bigscreen-resource-conversion", className)} data-variant={variant}>
      <div className="bigscreen-resource-conversion-title">{group.title}</div>
      <div className="bigscreen-resource-conversion-grid">
        {group.metrics.map((metric, index) => (
          <article key={`${metric.label}-${index}`} className="bigscreen-resource-conversion-card" data-tone={normalizeTone(metric.tone)}>
            <div className="bigscreen-resource-conversion-label">{metric.label}</div>
            <div className="bigscreen-resource-conversion-value">
              {typeof metric.value === "number" ? <BigscreenCountUp value={metric.value} /> : metric.value}
              {metric.unit ? <span className="bigscreen-resource-conversion-unit">{metric.unit}</span> : null}
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
