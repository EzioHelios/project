import type * as React from "react"

import { BigscreenCountUp } from "@/components/bigscreen/motion"
import { cn } from "@/lib/utils"

export function BigscreenPanel({
  title,
  eyebrow,
  children,
  className,
  bodyClassName,
  style,
  headerExtra,
}: {
  title: string
  eyebrow?: string
  children: React.ReactNode
  className?: string
  bodyClassName?: string
  style?: React.CSSProperties
  headerExtra?: React.ReactNode
}) {
  return (
    <section className={cn("bigscreen-panel rounded-[var(--panel-radius)]", className)} style={style}>
      <div className="bigscreen-panel-glow" />
      <header className="bigscreen-panel-header">
        {eyebrow ? <div className="mb-2 text-[var(--eyebrow-size)] font-semibold uppercase tracking-[0.28em] text-cyan-200/68">{eyebrow}</div> : null}
        <div className="flex items-center justify-between gap-3">
          <h2 className="bigscreen-title text-[var(--panel-title-size)] text-cyan-50">{title}</h2>
          {headerExtra}
        </div>
      </header>
      <div className={cn("bigscreen-panel-body text-slate-100", bodyClassName)}>{children}</div>
    </section>
  )
}

export function BigscreenMetricCard({
  metric,
  tone = "cyan",
  compact = false,
}: {
  metric: { label: string; value: number; unit?: string | null; ratio?: number | null }
  tone?: "cyan" | "amber" | "emerald"
  compact?: boolean
}) {
  const toneMap = {
    cyan: "from-cyan-400/16 to-blue-500/8 text-cyan-100",
    amber: "from-amber-300/16 to-orange-500/8 text-amber-100",
    emerald: "from-emerald-300/16 to-teal-500/8 text-emerald-100",
  }

  return (
    <div className={cn("bigscreen-metric-card bg-gradient-to-br shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]", toneMap[tone], compact ? "p-4" : undefined)}>
      <div className="text-[11px] uppercase tracking-[0.24em] text-white/50">{metric.label}</div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <div className={cn("bigscreen-kpi-value font-semibold leading-none", compact ? "text-[30px]" : "text-[var(--hero-metric-size)]")}>
          <BigscreenCountUp value={metric.value} />
        </div>
        {metric.unit ? <div className="rounded-full border border-white/10 bg-white/6 px-2 py-1 text-[var(--metric-unit-size)] text-white/60">{metric.unit}</div> : null}
      </div>
      <div className="mt-3 text-xs text-white/55">
        {metric.ratio === null || metric.ratio === undefined ? "本期暂无对比" : `较上期 ${metric.ratio > 0 ? "+" : ""}${metric.ratio.toFixed(1)}%`}
      </div>
    </div>
  )
}

export function BigscreenInfoCard({ label, value, accent = "cyan", detail }: { label: string; value: string; accent?: "cyan" | "amber" | "emerald"; detail?: string }) {
  const accentMap = {
    cyan: "text-cyan-100 border-cyan-300/14 bg-cyan-300/6",
    amber: "text-amber-100 border-amber-300/14 bg-amber-300/6",
    emerald: "text-emerald-100 border-emerald-300/14 bg-emerald-300/6",
  }

  return (
    <div className={cn("bigscreen-info-card", accentMap[accent])}>
      <div className="text-[11px] uppercase tracking-[0.22em] text-white/48">{label}</div>
      <div className="mt-3 text-lg font-semibold text-white">{value}</div>
      {detail ? <div className="mt-2 text-sm leading-6 text-white/56">{detail}</div> : null}
    </div>
  )
}

export function BigscreenEmpty({ label }: { label: string }) {
  return <div className="flex h-full items-center justify-center rounded-[20px] border border-dashed border-white/10 bg-white/[0.03] text-sm text-white/45">{label}</div>
}
