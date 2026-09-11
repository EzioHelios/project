import type * as React from "react"

import { BigscreenCountUp } from "@/components/bigscreen/motion"
import { NarrowPanelFrame } from "@/components/bigscreen/primitives/NarrowPanelFrame"
import { PanelTitleBar } from "@/components/bigscreen/primitives/PanelTitleBar"
import { TallPanelFrame } from "@/components/bigscreen/primitives/TallPanelFrame"
import { WidePanelFrame } from "@/components/bigscreen/primitives/WidePanelFrame"
import { useBigscreenSkin } from "@/components/bigscreen/skins/context"
import type { BigscreenPanelFrame } from "@/components/bigscreen/skins/types"
import { cn } from "@/lib/utils"

export function BigscreenPanel(props: {
  title: string
  children: React.ReactNode
  className?: string
  bodyClassName?: string
  style?: React.CSSProperties
  frame?: BigscreenPanelFrame
}) {
  const { title, children, className, bodyClassName, style, frame = "wide" } = props
  const skin = useBigscreenSkin()
  const frameConfig = skin.panelFrames[frame]
  const renderMode = frameConfig.renderMode ?? "background-image"
  const frameImage = frame === "tall" ? skin.assets.panelFrameTall : frame === "narrow" ? skin.assets.panelFrameNarrow : skin.assets.panelFrameWide

  const panelStyle = {
    ...style,
    ["--bigscreen-panel-frame-image" as string]: renderMode === "background-image" && frameImage ? `url(${frameImage})` : "none",
    ["--bigscreen-panel-header-height" as string]: `${frameConfig.headerHeight}px`,
    ["--bigscreen-panel-title-width" as string]: `${frameConfig.titleWidth}px`,
    ["--bigscreen-panel-body-padding-top" as string]: `${frameConfig.bodyPadding.top}px`,
    ["--bigscreen-panel-body-padding-right" as string]: `${frameConfig.bodyPadding.right}px`,
    ["--bigscreen-panel-body-padding-bottom" as string]: `${frameConfig.bodyPadding.bottom}px`,
    ["--bigscreen-panel-body-padding-left" as string]: `${frameConfig.bodyPadding.left}px`,
  } as React.CSSProperties

  if (renderMode === "svg-frame") {
    return (
      <section
        className={cn("bigscreen-panel bigscreen-panel-svg-shell", className)}
        data-bigscreen-panel-frame={frame}
        data-bigscreen-panel-render-mode={renderMode}
        style={panelStyle}
      >
        {frame === "tall" ? <TallPanelFrame /> : frame === "narrow" ? <NarrowPanelFrame /> : <WidePanelFrame />}
        <div className="bigscreen-panel-content-layer">
          <PanelTitleBar title={title} />
          <div className={cn("bigscreen-panel-body text-slate-100", bodyClassName)}>{children}</div>
        </div>
      </section>
    )
  }

  return (
    <section className={cn("bigscreen-panel", className)} data-bigscreen-panel-frame={frame} data-bigscreen-panel-render-mode={renderMode} style={panelStyle}>
      <div className="bigscreen-panel-glow" />
      <PanelTitleBar title={title} />
      <div className={cn("bigscreen-panel-body text-slate-100", bodyClassName)}>{children}</div>
    </section>
  )
}

export function BigscreenMetricCard({
  metric,
  tone = "cyan",
  compact = false,
}: {
  metric: { label: string; value: number | null; unit?: string | null; ratio?: number | null; emphasis?: string | null }
  tone?: "cyan" | "amber" | "emerald"
  compact?: boolean
}) {
  const toneMap = {
    cyan: "text-cyan-100",
    amber: "text-amber-100",
    emerald: "text-emerald-100",
  }
  const ratioTone = metric.ratio === null || metric.ratio === undefined ? "neutral" : metric.ratio > 0 ? "up" : metric.ratio < 0 ? "down" : "flat"

  return (
    <article className={cn("bigscreen-metric-card", toneMap[tone])} data-tone={tone} data-compact={compact}>
      <div className="bigscreen-metric-card-top">
        <div className="bigscreen-metric-card-label">{metric.label}</div>
        {metric.unit ? <div className="bigscreen-metric-card-unit">{metric.unit}</div> : null}
      </div>
      <div className="bigscreen-metric-card-main">
        <div className={cn("bigscreen-kpi-value bigscreen-metric-card-value", compact ? "text-[30px]" : "text-[var(--hero-metric-size)]")}>
          {metric.value == null ? "—" : <BigscreenCountUp value={metric.value} />}
        </div>
      </div>
      <div className="bigscreen-metric-card-bottom" data-ratio-tone={ratioTone}>
        {metric.emphasis ?? (metric.ratio === null || metric.ratio === undefined ? "本期暂无对比" : `较上期 ${metric.ratio > 0 ? "+" : ""}${metric.ratio.toFixed(1)}%`)}
      </div>
    </article>
  )
}

export function BigscreenInfoCard({ label, value, accent = "cyan", detail }: { label: string; value: string; accent?: "cyan" | "amber" | "emerald"; detail?: string }) {
  return (
    <article className="bigscreen-info-card" data-accent={accent}>
      <div className="bigscreen-info-card-head">
        <div className="bigscreen-info-card-marker" />
        <div className="bigscreen-info-card-label">{label}</div>
      </div>
      <div className="bigscreen-info-card-value">{value}</div>
      {detail ? <div className="bigscreen-info-card-detail">{detail}</div> : null}
    </article>
  )
}

export function BigscreenEmpty({ label }: { label: string }) {
  return <div className="bigscreen-empty-state flex h-full items-center justify-center text-sm text-white/45">{label}</div>
}
