import type * as React from "react"

import { cn } from "@/lib/utils"

export function BigscreenPanel({
  title,
  eyebrow,
  children,
  className,
  bodyClassName,
  style,
}: {
  title: string
  eyebrow?: string
  children: React.ReactNode
  className?: string
  bodyClassName?: string
  style?: React.CSSProperties
}) {
  return (
    <section className={cn("bigscreen-panel rounded-[22px]", className)} style={style}>
      <div className="bigscreen-panel-glow" />
      <header className="border-b border-white/8 px-5 py-4">
        {eyebrow ? <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-200/70">{eyebrow}</div> : null}
        <div className="flex items-center justify-between gap-3">
          <h2 className="bigscreen-title text-[18px] text-cyan-50">{title}</h2>
        </div>
      </header>
      <div className={cn("h-[calc(100%-72px)] px-5 py-4 text-slate-100", bodyClassName)}>{children}</div>
    </section>
  )
}

export function BigscreenMetricCard({
  metric,
  tone = "cyan",
}: {
  metric: { label: string; value: number; unit?: string | null; ratio?: number | null }
  tone?: "cyan" | "amber" | "emerald"
}) {
  const toneMap = {
    cyan: "from-cyan-400/16 to-blue-500/10 text-cyan-100",
    amber: "from-amber-300/16 to-orange-500/10 text-amber-100",
    emerald: "from-emerald-300/16 to-teal-500/10 text-emerald-100",
  }
  return (
    <div className={cn("rounded-[18px] border border-white/8 bg-gradient-to-br px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]", toneMap[tone])}>
      <div className="text-[11px] uppercase tracking-[0.22em] text-white/50">{metric.label}</div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <div className="bigscreen-kpi-value text-[30px] font-semibold leading-none">{metric.value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}</div>
        {metric.unit ? <div className="rounded-full border border-white/10 bg-white/6 px-2 py-1 text-[11px] text-white/60">{metric.unit}</div> : null}
      </div>
      <div className="mt-3 text-xs text-white/55">
        {metric.ratio === null || metric.ratio === undefined ? "本期暂无对比" : `较上期 ${metric.ratio > 0 ? "+" : ""}${metric.ratio.toFixed(1)}%`}
      </div>
    </div>
  )
}

export function BigscreenEmpty({ label }: { label: string }) {
  return <div className="flex h-full items-center justify-center rounded-[18px] border border-dashed border-white/10 bg-white/[0.03] text-sm text-white/45">{label}</div>
}
