import type * as React from "react"

import { useBigscreenSkin } from "@/components/bigscreen/skins/context"
import { cn } from "@/lib/utils"

export function PanelTitleBar({ title, className }: { title: string; eyebrow?: string; extra?: React.ReactNode; className?: string }) {
  const skin = useBigscreenSkin()

  return (
    <header
      className={cn("bigscreen-panel-header", className)}
      style={
        {
          ["--bigscreen-panel-title-strip" as string]: skin.assets.panelTitleStrip ? `url(${skin.assets.panelTitleStrip})` : undefined,
        } as React.CSSProperties
      }
    >
      <div className="bigscreen-panel-title-strip">
        <h2 className="bigscreen-title bigscreen-panel-title-text">{title}</h2>
      </div>
    </header>
  )
}
