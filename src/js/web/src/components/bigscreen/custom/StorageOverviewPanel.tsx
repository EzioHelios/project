import storageIllustration from "@/components/bigscreen/custom/assets/fadiantu.56d2c826.png"
import type { HuayiBigscreenKeyValue } from "@/lib/bigscreen/types"
import { cn } from "@/lib/utils"

function normalizeValue(value: number | string) {
  if (typeof value === "number") {
    return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })
  }
  return value
}

function parseStorageDetail(detail?: string | null) {
  if (!detail) {
    return []
  }

  return detail
    .split("/")
    .map((segment) => segment.trim())
    .filter(Boolean)
    .map((segment, index) => {
      const [label, ...valueParts] = segment.split(/\s+/)
      const rawValue = valueParts.join(" ").trim()
      const match = rawValue.match(/^([+-]?\d+(?:\.\d+)?)(?:\s*)([a-zA-Z%]+)$/)
      return {
        key: `${label}-${index}`,
        label,
        value: match ? match[1] : rawValue,
        unit: match ? match[2] : null,
      }
    })
}

export function StorageOverviewPanel({
  metric,
  className,
  variant = "default",
}: {
  metric: HuayiBigscreenKeyValue | null | undefined
  className?: string
  variant?: "default" | "dense"
}) {
  if (!metric) {
    return <div className={cn("bigscreen-storage-overview", className)}>--</div>
  }

  const detailRows = parseStorageDetail(metric.detail)
  const rows = [
    {
      key: "primary",
      label: metric.label,
      value: normalizeValue(metric.value),
      unit: metric.unit ?? null,
      tone: metric.tone === "amber" || metric.tone === "emerald" ? metric.tone : "cyan",
    },
    ...detailRows.map((row) => ({
      key: row.key,
      label: row.label,
      value: row.value,
      unit: row.unit,
      tone: "cyan" as const,
    })),
  ]

  return (
    <div className={cn("bigscreen-storage-overview", className)} data-variant={variant}>
      <img className="bigscreen-storage-overview-illustration" src={storageIllustration} alt="" aria-hidden="true" />
      <div className="bigscreen-storage-overview-board">
        <div className="bigscreen-storage-overview-copy">
          {rows.map((row) => (
            <article key={row.key} className="bigscreen-storage-overview-row" data-tone={row.tone}>
              <div className="bigscreen-storage-overview-label">{row.label}</div>
              <div className="bigscreen-storage-overview-value">
                <span>{row.value}</span>
                {row.unit ? <span className="bigscreen-storage-overview-unit">{row.unit}</span> : null}
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  )
}
