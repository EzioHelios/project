import generationIllustration from "@/components/bigscreen/custom/assets/fadiantu.56d2c826.png"
import consumptionIllustration from "@/components/bigscreen/custom/assets/yongdiantu.a4bf1067.png"
import { BigscreenCountUp } from "@/components/bigscreen/motion"
import { BigscreenEmpty } from "@/components/bigscreen/panel"
import type { HuayiBigscreenKeyValue } from "@/lib/bigscreen/types"
import { cn } from "@/lib/utils"

const illustrationMap = {
  consumption: consumptionIllustration,
  generation: generationIllustration,
} as const

function normalizeValue(value: number | string) {
  if (typeof value === "number") {
    return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })
  }
  return value
}

export function EnergyAssetOverviewPanel({ kind, metrics, className }: { kind: keyof typeof illustrationMap; metrics: HuayiBigscreenKeyValue[]; className?: string }) {
  if (!metrics.length) {
    return <BigscreenEmpty label="暂无能源概览数据" />
  }

  const [heroMetric, ...restMetrics] = metrics

  return (
    <div className={cn("bigscreen-energy-asset-overview", className)} data-kind={kind}>
      <div className="bigscreen-energy-asset-overview-hero">
        <img className="bigscreen-energy-asset-overview-illustration" src={illustrationMap[kind]} alt="" aria-hidden="true" />
        <div className="bigscreen-energy-asset-overview-hero-copy">
          <div className="bigscreen-energy-asset-overview-hero-label">{heroMetric.label}</div>
          <div className="bigscreen-energy-asset-overview-hero-value">
            {typeof heroMetric.value === "number" ? <BigscreenCountUp value={heroMetric.value} /> : normalizeValue(heroMetric.value)}
            {heroMetric.unit ? <span className="bigscreen-energy-asset-overview-hero-unit">{heroMetric.unit}</span> : null}
          </div>
          {heroMetric.detail ? <div className="bigscreen-energy-asset-overview-hero-detail">{heroMetric.detail}</div> : null}
        </div>
      </div>

      <div className="bigscreen-energy-asset-overview-list">
        {restMetrics.map((metric, index) => (
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
      </div>
    </div>
  )
}
