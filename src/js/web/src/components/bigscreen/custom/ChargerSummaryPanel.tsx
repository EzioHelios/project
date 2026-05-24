import chargerIllustration from "@/components/bigscreen/custom/assets/chongdianzhuangtu.png"
import { BigscreenEmpty } from "@/components/bigscreen/panel"
import type { HuayiBigscreenKeyValue } from "@/lib/bigscreen/types"
import { cn } from "@/lib/utils"

function normalizeTone(tone?: string) {
  if (tone === "amber" || tone === "emerald") {
    return tone
  }
  return "cyan"
}

function normalizeValue(value: number | string) {
  if (typeof value === "number") {
    return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })
  }
  return value
}

export function ChargerSummaryPanel({ metrics, className, variant = "default" }: { metrics: HuayiBigscreenKeyValue[]; className?: string; variant?: "default" | "dense" }) {
  if (!metrics.length) {
    return <BigscreenEmpty label="暂无充电桩数据" />
  }

  return (
    <div className={cn("bigscreen-charger-summary", className)} data-variant={variant}>
      <div className="bigscreen-charger-summary-hero">
        <img className="bigscreen-charger-summary-illustration" src={chargerIllustration} alt="" aria-hidden="true" />
      </div>
      <div className="bigscreen-charger-summary-board">
        {metrics.map((metric, index) => (
          <article key={`${metric.label}-${index}`} className="bigscreen-charger-summary-row" data-tone={normalizeTone(metric.tone)}>
            <div className="bigscreen-charger-summary-label">{metric.label}</div>
            <div className="bigscreen-charger-summary-value">
              <span>{normalizeValue(metric.value)}</span>
              {metric.unit ? <span className="bigscreen-charger-summary-unit">{metric.unit}</span> : null}
            </div>
            {metric.detail && variant === "default" ? <div className="bigscreen-charger-summary-detail">{metric.detail}</div> : null}
          </article>
        ))}
      </div>
    </div>
  )
}
