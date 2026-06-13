import type * as React from "react"

import { cn } from "@/lib/utils"

type MetricStripProps = React.HTMLAttributes<HTMLDivElement>

export function MetricStrip({ className, ...props }: MetricStripProps) {
  return <div className={cn("grid gap-3 md:grid-cols-2 xl:grid-cols-4", className)} {...props} />
}

type MetricTileProps = React.HTMLAttributes<HTMLDivElement> & {
  label: React.ReactNode
  value: React.ReactNode
  unit?: React.ReactNode
  meta?: React.ReactNode
  tone?: "default" | "success" | "warning" | "danger" | "info"
}

const toneClassName: Record<NonNullable<MetricTileProps["tone"]>, string> = {
  default: "",
  success: "border-[hsl(var(--status-success))]/30 bg-[hsl(var(--status-success))]/5",
  warning: "border-[hsl(var(--status-warning))]/35 bg-[hsl(var(--status-warning))]/10",
  danger: "border-[hsl(var(--status-danger))]/30 bg-[hsl(var(--status-danger))]/5",
  info: "border-[hsl(var(--status-info))]/30 bg-[hsl(var(--status-info))]/5",
}

export function MetricTile({ label, value, unit, meta, tone = "default", className, ...props }: MetricTileProps) {
  return (
    <div className={cn("rounded-md border border-border/70 bg-card px-4 py-3 shadow-[0_1px_0_hsl(215_20%_20%/0.03)]", toneClassName[tone], className)} {...props}>
      <div className="text-muted-foreground text-xs leading-5">{label}</div>
      <div className="mt-2 flex min-h-8 items-baseline gap-1.5">
        <span className="admin-kpi-value">{value}</span>
        {unit && <span className="text-muted-foreground text-xs">{unit}</span>}
      </div>
      {meta && <div className="mt-1 text-muted-foreground text-xs leading-5">{meta}</div>}
    </div>
  )
}
