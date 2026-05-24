import photovoltaicIllustration from "@/components/bigscreen/custom/assets/guangfuzhenlie.png"
import consumptionIllustration from "@/components/bigscreen/custom/assets/yongdiantu.a4bf1067.png"
import { BigscreenEmpty } from "@/components/bigscreen/panel"
import type { HuayiBigscreenKeyValue } from "@/lib/bigscreen/types"
import { cn } from "@/lib/utils"

const illustrationMap = {
  consumption: consumptionIllustration,
  generation: photovoltaicIllustration,
} as const

function normalizeValue(value: number | string) {
  if (typeof value === "number") {
    return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })
  }
  return value
}

export function EnergyAssetOverviewPanel({
  kind,
  metrics,
  className,
  variant = "default",
}: {
  kind: keyof typeof illustrationMap
  metrics: HuayiBigscreenKeyValue[]
  className?: string
  variant?: "default" | "dense"
}) {
  if (!metrics.length) {
    return <BigscreenEmpty label="暂无能源概览数据" />
  }

  const [heroMetric, ...restMetrics] = metrics
  const visibleMetrics = [heroMetric, ...restMetrics].slice(0, 5)

  return (
    <div className={cn("bigscreen-energy-asset-overview", className)} data-kind={kind} data-variant={variant}>
      <div className="bigscreen-energy-asset-overview-hero">
        <img className="bigscreen-energy-asset-overview-illustration" src={illustrationMap[kind]} alt="" aria-hidden="true" />
      </div>

      <div className="bigscreen-energy-asset-overview-board">
        {visibleMetrics.map((metric, index) => (
          <article
            key={`${metric.label}-${index}`}
            className="bigscreen-energy-asset-overview-row"
            data-tone={metric.tone === "amber" || metric.tone === "emerald" ? metric.tone : "cyan"}
          >
            <div className="bigscreen-energy-asset-overview-row-label">{metric.label}</div>
            <div className="bigscreen-energy-asset-overview-row-value">
              <span>{normalizeValue(metric.value)}</span>
              {metric.unit ? <span className="bigscreen-energy-asset-overview-row-unit">{metric.unit}</span> : null}
            </div>
          </article>
        ))}
        {heroMetric.detail ? <div className="bigscreen-energy-asset-overview-detail-strip">{heroMetric.detail}</div> : null}
      </div>
    </div>
  )
}
