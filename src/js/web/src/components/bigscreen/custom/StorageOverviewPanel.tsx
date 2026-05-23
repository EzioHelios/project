import storageBackdrop from "@/components/bigscreen/custom/assets/chunengzonglan-bg.ea664e7b.png"
import type { HuayiBigscreenKeyValue } from "@/lib/bigscreen/types"
import { cn } from "@/lib/utils"

function splitDisplayValue(value: number | string) {
  const raw = typeof value === "number" ? value.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) : value
  const counts = new Map<string, number>()

  return raw.split("").map((char) => {
    const count = (counts.get(char) ?? 0) + 1
    counts.set(char, count)
    return {
      char,
      key: `${char}-${count}`,
    }
  })
}

export function StorageOverviewPanel({ metric, className }: { metric: HuayiBigscreenKeyValue | null | undefined; className?: string }) {
  if (!metric) {
    return <div className={cn("bigscreen-storage-overview", className)}>--</div>
  }

  const chars = splitDisplayValue(metric.value)

  return (
    <div className={cn("bigscreen-storage-overview", className)}>
      <img className="bigscreen-storage-overview-backdrop" src={storageBackdrop} alt="" aria-hidden="true" />
      <div className="bigscreen-storage-overview-copy">
        <div className="bigscreen-storage-overview-label">{metric.label}</div>
        <div className="bigscreen-storage-overview-digits">
          {chars.map((digit) => (
            <span key={digit.key} className="bigscreen-storage-overview-digit">
              {digit.char}
            </span>
          ))}
          {metric.unit ? <span className="bigscreen-storage-overview-unit">{metric.unit}</span> : null}
        </div>
        {metric.detail ? <div className="bigscreen-storage-overview-detail">{metric.detail}</div> : null}
      </div>
    </div>
  )
}
