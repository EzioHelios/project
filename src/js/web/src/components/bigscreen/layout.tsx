import { Link, Outlet, useLocation } from "@tanstack/react-router"
import { useEffect, useMemo, useState } from "react"

import "@/components/bigscreen/bigscreen.css"

import { useBigscreenMeta } from "@/lib/bigscreen/hooks"
import { cn } from "@/lib/utils"

const fallbackNav = [
  { label: "企业介绍", path: "/bigscreen/intro" },
  { label: "态势总览", path: "/bigscreen/overview" },
  { label: "电量监控", path: "/bigscreen/power" },
  { label: "能碳协同", path: "/bigscreen/carbon" },
]

function useBigscreenScale() {
  const [scale, setScale] = useState(1)

  useEffect(() => {
    const update = () => {
      const next = Math.min(window.innerWidth / 1920, window.innerHeight / 1080)
      setScale(next)
    }
    update()
    window.addEventListener("resize", update)
    return () => window.removeEventListener("resize", update)
  }, [])

  return scale
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
  const scale = useBigscreenScale()
  const now = useClock()
  const metaQuery = useBigscreenMeta()
  const meta = metaQuery.data?.data
  const navItems = meta?.nav_items ?? fallbackNav

  const currentLabel = useMemo(() => navItems.find((item) => item.path === pathname)?.label ?? "态势总览", [navItems, pathname])

  return (
    <div className="bigscreen-root">
      <div className="bigscreen-viewport">
        <div className="bigscreen-stage" style={{ ["--bigscreen-scale" as string]: scale }}>
          <div className="bigscreen-shell">
            <header className="mb-4 rounded-[24px] border border-cyan-300/12 bg-[linear-gradient(180deg,rgba(4,16,32,0.92),rgba(7,22,42,0.7))] px-6 py-4 shadow-[0_28px_60px_rgba(0,0,0,0.25)]">
              <div className="flex items-center justify-between gap-6">
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-cyan-300/18 bg-cyan-300/8 text-cyan-100">
                    <span className="bigscreen-title text-2xl">{meta?.short_name ?? "LC"}</span>
                  </div>
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.34em] text-cyan-100/60">Bigscreen Center</div>
                    <h1 className="bigscreen-title mt-1 text-[34px] text-white">{meta?.title ?? "仓库能碳态势大屏"}</h1>
                    <div className="mt-1 text-sm text-cyan-100/55">{meta?.description ?? "平台内正式大屏模块，首版聚焦介绍、总览、电量与能碳协同四屏。"}</div>
                  </div>
                </div>

                <div className="flex min-w-[420px] items-center justify-end gap-4">
                  <div className="rounded-full border border-emerald-300/18 bg-emerald-300/8 px-4 py-2 text-right">
                    <div className="text-[10px] uppercase tracking-[0.26em] text-emerald-100/60">Current Screen</div>
                    <div className="mt-1 text-sm font-medium text-emerald-50">{currentLabel}</div>
                  </div>
                  <div className="rounded-full border border-cyan-300/18 bg-cyan-300/8 px-4 py-2 text-right">
                    <div className="bigscreen-kpi-value text-[28px] leading-none text-cyan-50">{now.toLocaleTimeString("zh-CN", { hour12: false })}</div>
                    <div className="mt-1 text-[11px] uppercase tracking-[0.22em] text-cyan-100/55">
                      {now.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit", weekday: "short" })}
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 flex items-center gap-3">
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

            <main className="h-[calc(100%-116px)]">
              <Outlet />
            </main>
          </div>
        </div>
      </div>
    </div>
  )
}
