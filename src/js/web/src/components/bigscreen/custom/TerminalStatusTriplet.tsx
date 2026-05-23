import faultGenerationIcon from "@/components/bigscreen/custom/assets/fadianzhongduanguzhang.49af1207.png"
import onlineGenerationIcon from "@/components/bigscreen/custom/assets/fadianzhongduanzaixian.a5bcee55.png"
import totalGenerationIcon from "@/components/bigscreen/custom/assets/fadianzhongduanzongshu.636bd929.png"
import faultPowerIcon from "@/components/bigscreen/custom/assets/yongdianzhongduanguzhang.b9d3e33b.png"
import onlinePowerIcon from "@/components/bigscreen/custom/assets/yongdianzhongduanzaixian.791eb30d.png"
import totalPowerIcon from "@/components/bigscreen/custom/assets/yongdianzhongduanzongshu.9f537936.png"
import { BigscreenCountUp } from "@/components/bigscreen/motion"
import { BigscreenEmpty } from "@/components/bigscreen/panel"
import { cn } from "@/lib/utils"

type TerminalStatusKind = "total" | "online" | "fault"

export type TerminalStatusItem = {
  id: string
  label: string
  value: number
  unit?: string | null
  kind: TerminalStatusKind
}

const iconMap = {
  generation: {
    total: totalGenerationIcon,
    online: onlineGenerationIcon,
    fault: faultGenerationIcon,
  },
  power: {
    total: totalPowerIcon,
    online: onlinePowerIcon,
    fault: faultPowerIcon,
  },
} as const

export function TerminalStatusTriplet({
  items,
  family = "power",
  summary,
  className,
}: {
  items: TerminalStatusItem[]
  family?: keyof typeof iconMap
  summary?: { label: string; value: number | string; unit?: string | null; detail?: string | null }
  className?: string
}) {
  if (!items.length) {
    return <BigscreenEmpty label="暂无终端状态数据" />
  }

  return (
    <div className={cn("bigscreen-terminal-status", className)}>
      <div className="bigscreen-terminal-status-grid" data-columns={items.length}>
        {items.map((item) => (
          <article key={item.id} className="bigscreen-terminal-status-item">
            <img className="bigscreen-terminal-status-icon" src={iconMap[family][item.kind]} alt="" aria-hidden="true" />
            <div className="bigscreen-terminal-status-copy">
              <div className="bigscreen-terminal-status-label">{item.label}</div>
              <div className="bigscreen-terminal-status-value">
                <BigscreenCountUp value={item.value} />
                {item.unit ? <span className="bigscreen-terminal-status-unit">{item.unit}</span> : null}
              </div>
            </div>
          </article>
        ))}
      </div>

      {summary ? (
        <div className="bigscreen-terminal-status-summary">
          <div className="bigscreen-terminal-status-summary-label">{summary.label}</div>
          <div className="bigscreen-terminal-status-summary-main">
            <span className="bigscreen-terminal-status-summary-value">
              {typeof summary.value === "number" ? summary.value.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) : summary.value}
            </span>
            {summary.unit ? <span className="bigscreen-terminal-status-summary-unit">{summary.unit}</span> : null}
          </div>
          {summary.detail ? <div className="bigscreen-terminal-status-summary-detail">{summary.detail}</div> : null}
        </div>
      ) : null}
    </div>
  )
}
