import { Outlet, useLocation } from "@tanstack/react-router"
import type * as React from "react"
import { useEffect, useMemo, useState } from "react"

import "@/components/bigscreen/bigscreen.css"

import { ScreenHeader } from "@/components/bigscreen/primitives/ScreenHeader"
import { BigscreenSceneCanvas } from "@/components/bigscreen/scene-canvas"
import { BigscreenSkinProvider } from "@/components/bigscreen/skins/context"
import { getBigscreenSkinDefinition } from "@/components/bigscreen/skins/registry"
import { useBigscreenMeta } from "@/lib/bigscreen/hooks"

const fallbackNav = [
  { label: "企业介绍", path: "/bigscreen/intro" },
  { label: "态势总览", path: "/bigscreen/overview" },
  { label: "电量监控", path: "/bigscreen/power" },
  { label: "能碳协同", path: "/bigscreen/carbon" },
]

function resolveStageScale() {
  return Math.min(window.innerWidth / 1920, window.innerHeight / 1080)
}

function resolveTier() {
  const stageWidth = Math.min(window.innerWidth, (window.innerHeight * 16) / 9)
  if (stageWidth >= 3200) return "2160"
  if (stageWidth >= 2400) return "1440"
  return "1080"
}

function useBigscreenViewport() {
  const [state, setState] = useState(() => ({
    scale: typeof window === "undefined" ? 1 : resolveStageScale(),
    tier: typeof window === "undefined" ? "1080" : resolveTier(),
  }))

  useEffect(() => {
    const update = () => {
      setState({
        scale: resolveStageScale(),
        tier: resolveTier(),
      })
    }
    update()
    window.addEventListener("resize", update)
    return () => window.removeEventListener("resize", update)
  }, [])

  return state
}

function useClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return now
}

export function BigscreenLayout() {
  const pathname = useLocation({ select: (location) => location.pathname })
  const { scale, tier } = useBigscreenViewport()
  const now = useClock()
  const metaQuery = useBigscreenMeta()
  const meta = metaQuery.data?.data
  const skin = getBigscreenSkinDefinition()
  const navItems = meta?.nav_items ?? fallbackNav

  const currentLabel = useMemo(() => navItems.find((item) => item.path === pathname)?.label ?? "态势总览", [navItems, pathname])

  return (
    <BigscreenSkinProvider skin={skin}>
      <div className={`bigscreen-root ${skin.tokenClassName}`} data-bigscreen-tier={tier}>
        <div className="bigscreen-viewport">
          <div className="bigscreen-stage" style={{ ["--bigscreen-scale" as string]: scale }}>
            <div
              className="bigscreen-stage-backdrop"
              style={
                {
                  ["--bigscreen-stage-backdrop-image" as string]: skin.assets.backdropImage ? `url(${skin.assets.backdropImage})` : undefined,
                } as React.CSSProperties
              }
            >
              <BigscreenSceneCanvas variant="stage" />
            </div>
            <div className="bigscreen-shell">
              <ScreenHeader
                title={meta?.title ?? "仓储能碳态势指挥大屏"}
                shortName={meta?.short_name ?? "LC"}
                description={meta?.description ?? "围绕园区主视觉对象组织经营总览、电量监控、能碳协同与企业介绍，形成可上墙、可持续观看的大屏系统。"}
                currentLabel={currentLabel}
                city="台州"
                weather={meta?.show_weather === false ? "--" : "晴"}
                now={now}
                navItems={navItems}
                pathname={pathname}
              />

              <main className="bigscreen-shell-main">
                <Outlet />
              </main>
            </div>
          </div>
        </div>
      </div>
    </BigscreenSkinProvider>
  )
}
