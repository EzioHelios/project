import { Outlet, useLocation } from "@tanstack/react-router"
import type * as React from "react"
import { useEffect, useState } from "react"

import "@/components/bigscreen/bigscreen.css"

import { TenantCampusScene } from "@/components/bigscreen/campus/tenant-campus-scene"
import { ScreenHeader } from "@/components/bigscreen/primitives/ScreenHeader"
import { BigscreenSkinProvider } from "@/components/bigscreen/skins/context"
import { getBigscreenSkinDefinition } from "@/components/bigscreen/skins/registry"
import { BigscreenTenantSwitcher } from "@/components/bigscreen/tenant-switcher"
import { useAuthStore } from "@/lib/auth"
import { useBigscreenEnvironment, useBigscreenMeta } from "@/lib/bigscreen/hooks"

const fallbackNav = [
  { label: "态势总览", path: "/bigscreen/overview" },
  { label: "运行监测", path: "/bigscreen/monitor" },
  { label: "电量监控", path: "/bigscreen/power" },
  { label: "碳排管理", path: "/bigscreen/carbon" },
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
  const teamName = useAuthStore((state) => state.currentTeam?.name)
  const pathname = useLocation({ select: (location) => location.pathname })
  const { scale, tier } = useBigscreenViewport()
  const now = useClock()
  const metaQuery = useBigscreenMeta()
  const meta = metaQuery.data?.data
  const environmentQuery = useBigscreenEnvironment(meta?.show_weather !== false)
  const environment = environmentQuery.data
  const skin = getBigscreenSkinDefinition()
  const navItems = meta?.nav_items ?? fallbackNav
  const resolution = tier === "2160" ? "2160" : "1080"
  const displayCity = meta?.city ?? environment?.city ?? "--"
  const displayWeather = meta?.show_weather === false ? "--" : (environment?.weather ?? "--")

  return (
    <BigscreenSkinProvider skin={skin}>
      <div className={`bigscreen-root ${skin.tokenClassName}`} data-bigscreen-tier={tier} data-bigscreen-resolution={resolution}>
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
              {pathname !== "/bigscreen/vision" && <TenantCampusScene showControls={pathname === "/bigscreen/model"} />}
            </div>
            <div className="bigscreen-shell">
              <ScreenHeader
                title={teamName ? `${teamName}能碳驾驶舱` : (meta?.title ?? "能碳驾驶舱")}
                shortName="能碳"
                description=""
                city={displayCity}
                tenantSwitcher={<BigscreenTenantSwitcher />}
                weather={displayWeather}
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
