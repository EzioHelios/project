import { Outlet, useLocation } from "@tanstack/react-router"
import type * as React from "react"
import { useEffect, useState } from "react"

import "@/components/bigscreen/bigscreen.css"

import { ScreenHeader } from "@/components/bigscreen/primitives/ScreenHeader"
import { BigscreenSceneCanvas } from "@/components/bigscreen/scene-canvas"
import { BigscreenSkinProvider } from "@/components/bigscreen/skins/context"
import { getBigscreenSkinDefinition } from "@/components/bigscreen/skins/registry"
import { useBigscreenEnvironment, useBigscreenMeta } from "@/lib/bigscreen/hooks"

const fallbackNav = [
  { label: "企业介绍", path: "/bigscreen/intro" },
  { label: "态势总览", path: "/bigscreen/overview" },
  { label: "电量监控", path: "/bigscreen/power" },
  { label: "能碳协同", path: "/bigscreen/carbon" },
]

const fallbackNavByVariant = {
  default: fallbackNav,
  huayi: [],
  zhijiang: [],
} as const

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
  const metaVariant = pathname.startsWith("/bigscreen/huayi")
    ? "huayi"
    : pathname.startsWith("/bigscreen/zhijiang")
      ? "zhijiang"
      : "default"
  const { scale, tier } = useBigscreenViewport()
  const now = useClock()
  const queryVariant = metaVariant === "zhijiang" ? "default" : metaVariant
  const metaQuery = useBigscreenMeta(queryVariant)
  const meta = metaQuery.data?.data
  const environmentQuery = useBigscreenEnvironment(meta?.show_weather !== false)
  const environment = environmentQuery.data
  const skin = getBigscreenSkinDefinition()
  const navItems =
    metaVariant === "zhijiang"
      ? []
      : metaVariant === "huayi"
        ? []
        : meta?.nav_items ?? [...fallbackNavByVariant[metaVariant]]
  const resolution = tier === "2160" ? "2160" : "1080"
  const fallbackMeta =
    metaVariant === "zhijiang"
      ? {
          title: "公共设施节能降碳管理平台",
          shortName: "ZJ",
          description: "围绕县域试点点位，把设备改造、节能验证、碳减排成果与复制推广潜力汇聚到一张 GIS 主屏。",
          city: "浙江省杭州市",
        }
      : metaVariant === "huayi"
        ? {
            city: "上海市",
          }
        : {
            city: "江苏省泰州市",
          }
  const displayCity = meta?.city ?? fallbackMeta?.city ?? environment?.city ?? "--"
  const displayWeather = meta?.show_weather === false ? "--" : environment?.weather ?? "--"

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
              <BigscreenSceneCanvas variant="stage" />
            </div>
            <div className="bigscreen-shell">
              <ScreenHeader
                title={meta?.title ?? fallbackMeta?.title ?? "仓储能碳态势指挥大屏"}
                shortName={meta?.short_name ?? fallbackMeta?.shortName ?? "LC"}
                description={
                  meta?.description ??
                  fallbackMeta?.description ??
                  "围绕园区主视觉对象组织经营总览、电量监控、能碳协同与企业介绍，形成可上墙、可持续观看的大屏系统。"
                }
                city={displayCity}
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
