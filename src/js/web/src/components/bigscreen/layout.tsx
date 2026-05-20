import { Link, Outlet, useLocation } from "@tanstack/react-router"
import { useEffect, useMemo, useState } from "react"

import "@/components/bigscreen/bigscreen.css"

import { BigscreenSceneCanvas } from "@/components/bigscreen/scene-canvas"
import { useBigscreenMeta } from "@/lib/bigscreen/hooks"
import { cn } from "@/lib/utils"

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
  const navItems = meta?.nav_items ?? fallbackNav

  const currentLabel = useMemo(() => navItems.find((item) => item.path === pathname)?.label ?? "态势总览", [navItems, pathname])

  return (
    <div className="bigscreen-root" data-bigscreen-tier={tier}>
      <div className="bigscreen-viewport">
        <div className="bigscreen-stage" style={{ ["--bigscreen-scale" as string]: scale }}>
          <div className="bigscreen-stage-backdrop">
            <BigscreenSceneCanvas variant="stage" />
          </div>
          <div className="bigscreen-shell">
            <header className="bigscreen-header-band">
              <div className="bigscreen-header-main flex items-start justify-between gap-6">
                <div className="bigscreen-header-brand flex min-w-0 items-start gap-4">
                  <div className="flex h-16 w-16 items-center justify-center rounded-[22px] border border-cyan-300/16 bg-cyan-300/8 text-cyan-50 shadow-[0_0_32px_rgba(34,211,238,0.12)]">
                    <span className="bigscreen-title text-[30px]">{meta?.short_name ?? "LC"}</span>
                  </div>
                  <div className="min-w-0">
                    <div className="text-[11px] uppercase tracking-[0.34em] text-cyan-100/54">Immersive Operations Screen</div>
                    <h1 className="bigscreen-title mt-2 text-[var(--display-title-size)] text-white">{meta?.title ?? "仓储能碳态势指挥大屏"}</h1>
                    <div className="bigscreen-header-description mt-3 max-w-[880px] text-[15px] leading-7 text-cyan-100/58">
                      {meta?.description ?? "围绕园区主视觉对象组织经营总览、电量监控、能碳协同与企业介绍，形成可上墙、可持续观看的大屏系统。"}
                    </div>
                  </div>
                </div>

                <div className="bigscreen-header-side flex flex-col items-end gap-3">
                  <div className="flex items-center gap-3">
                    <div className="rounded-[18px] border border-cyan-300/16 bg-cyan-300/8 px-4 py-3 text-right">
                      <div className="text-[11px] uppercase tracking-[0.24em] text-cyan-100/56">Current Screen</div>
                      <div className="mt-2 text-sm font-semibold text-white">{currentLabel}</div>
                    </div>
                    <div className="rounded-[18px] border border-white/10 bg-white/[0.04] px-4 py-3 text-right">
                      <div className="bigscreen-kpi-value text-[34px] leading-none text-cyan-50">{now.toLocaleTimeString("zh-CN", { hour12: false })}</div>
                      <div className="mt-2 text-[11px] uppercase tracking-[0.22em] text-cyan-100/54">
                        {now.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit", weekday: "short" })}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bigscreen-header-nav flex items-center gap-3">
                {navItems.map((item) => {
                  const active = pathname === item.path
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={cn(
                        "rounded-full border px-4 py-2 text-sm transition-all",
                        active
                          ? "border-cyan-300/40 bg-cyan-300/14 text-cyan-50 shadow-[0_0_22px_rgba(34,211,238,0.16)]"
                          : "border-white/8 bg-white/[0.03] text-cyan-100/62 hover:border-cyan-300/24 hover:text-cyan-50",
                      )}
                    >
                      {item.label}
                    </Link>
                  )
                })}
              </div>
            </header>

            <main className="bigscreen-shell-main">
              <Outlet />
            </main>
          </div>
        </div>
      </div>
    </div>
  )
}
