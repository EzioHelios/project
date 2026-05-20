import { motion } from "framer-motion"
import type * as React from "react"

import { cn } from "@/lib/utils"

type AnchorPosition = "lt" | "lb" | "rt" | "rb" | "ct"

export type BigscreenSceneAnchor = {
  id: string
  label: string
  value: string
  position: AnchorPosition
}

export function BigscreenSceneHost({
  eyebrow,
  title,
  description,
  status,
  anchors,
  background,
  overlay,
  showSafezone = true,
  showCore = true,
  className,
}: {
  eyebrow: string
  title: string
  description: string
  status?: string
  anchors?: BigscreenSceneAnchor[]
  background?: React.ReactNode
  overlay?: React.ReactNode
  showSafezone?: boolean
  showCore?: boolean
  className?: string
}) {
  return (
    <section className={cn("bigscreen-scene-shell", className)} data-has-media={background ? "true" : "false"}>
      {background ? <div className="bigscreen-scene-media">{background}</div> : null}
      <div className="bigscreen-scene-grid" />
      <div className="bigscreen-scene-lines" />
      {showSafezone ? <div className="bigscreen-scene-safezone" /> : null}
      {showCore ? (
        <div className="bigscreen-scene-center">
          <div className="bigscreen-scene-core px-8">
            <div className="text-[11px] uppercase tracking-[0.28em] text-cyan-100/52">{eyebrow}</div>
            <div className="bigscreen-title mt-3 text-[32px] text-white">{title}</div>
            <div className="mt-4 text-sm leading-6 text-white/56">{description}</div>
            {status ? (
              <div className="mt-6 inline-flex rounded-full border border-cyan-300/16 bg-cyan-300/8 px-4 py-2 text-xs uppercase tracking-[0.22em] text-cyan-100/70">{status}</div>
            ) : null}
          </div>
        </div>
      ) : null}

      {(anchors ?? []).map((anchor, index) => (
        <motion.div
          key={anchor.id}
          className="bigscreen-scene-anchor"
          data-position={anchor.position}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: index * 0.12 }}
        >
          <div>
            <div className="bigscreen-anchor-label">{anchor.label}</div>
            <div className="bigscreen-anchor-value mt-1">{anchor.value}</div>
          </div>
        </motion.div>
      ))}

      {overlay ? <div className="absolute inset-0 p-5">{overlay}</div> : null}
    </section>
  )
}
