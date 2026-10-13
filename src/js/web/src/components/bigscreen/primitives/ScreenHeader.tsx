import { Link } from "@tanstack/react-router"
import type { ReactNode } from "react"

import { ScreenHeaderFrame } from "@/components/bigscreen/primitives/ScreenHeaderFrame"
import { ScreenHeaderNavFrame } from "@/components/bigscreen/primitives/ScreenHeaderNavFrame"
import { ScreenHeaderNavTabFrame } from "@/components/bigscreen/primitives/ScreenHeaderNavTabFrame"
import { useBigscreenSkin } from "@/components/bigscreen/skins/context"
import { cn } from "@/lib/utils"

type BigscreenNavItem = {
  label: string
  path: string
}

function getWeatherKind(weather: string) {
  if (weather.includes("雨")) {
    return "rain"
  }
  if (weather.includes("云") || weather.includes("阴")) {
    return "overcast"
  }
  if (weather.includes("晴")) {
    return "sunny"
  }
  return "unknown"
}

function splitWeatherValue(weather: string) {
  if (weather === "--") {
    return { summary: "--", detail: "" }
  }

  const [summary, detail] = weather.split(/\s+/u)
  return {
    summary: summary ?? weather,
    detail: detail ?? "",
  }
}

function formatChineseDate(now: Date) {
  const year = now.getFullYear()
  const month = `${now.getMonth() + 1}`.padStart(2, "0")
  const day = `${now.getDate()}`.padStart(2, "0")
  const weekday = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"][now.getDay()]
  return `${year}年${month}月${day}日 ${weekday}`
}

function WeatherGlyph({ kind }: { kind: "sunny" | "overcast" | "rain" | "unknown" }) {
  if (kind === "sunny") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="4.1" fill="currentColor" />
        <path
          d="M12 3.1v2.2M12 18.7v2.2M20.9 12h-2.2M5.3 12H3.1M18.35 5.65l-1.55 1.55M7.2 16.8l-1.55 1.55M18.35 18.35 16.8 16.8M7.2 7.2 5.65 5.65"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    )
  }

  if (kind === "rain") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M8.1 14.8h8a3.3 3.3 0 0 0 .55-6.56A5.08 5.08 0 0 0 7.45 7.1a3.3 3.3 0 0 0 .65 7.7Z" fill="none" stroke="currentColor" strokeWidth="1.55" />
        <path d="M9.2 17.2 8.45 19.7M13 17.2l-.75 2.5M16.8 17.2l-.75 2.5" fill="none" stroke="currentColor" strokeWidth="1.45" strokeLinecap="round" />
      </svg>
    )
  }

  if (kind === "overcast") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M8.15 17.8h8.2a3.4 3.4 0 0 0 .58-6.74A5.25 5.25 0 0 0 7.25 9.45a3.45 3.45 0 0 0 .9 8.35Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.55"
          strokeLinejoin="round"
        />
      </svg>
    )
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="2.1" fill="currentColor" />
    </svg>
  )
}

export function ScreenHeader({
  title,
  shortName,
  description: _description,
  city,
  weather,
  now,
  navItems,
  pathname,
  tenantSwitcher,
}: {
  title: string
  shortName: string
  description: string
  city: string
  weather: string
  now: Date
  navItems: BigscreenNavItem[]
  pathname: string
  tenantSwitcher?: ReactNode
}) {
  const skin = useBigscreenSkin()
  const weatherKind = getWeatherKind(weather)
  const weatherValue = splitWeatherValue(weather)
  const hasNav = navItems.length > 1

  return (
    <header className="bigscreen-header-stack bigscreen-screen-header" data-has-nav={hasNav}>
      <div className="bigscreen-header-main-shell">
        <ScreenHeaderFrame />

        <div className="bigscreen-screen-header-main-content">
          <div className="bigscreen-screen-header-brand">
            <div className="bigscreen-screen-header-brand-mark">
              <span className="bigscreen-screen-header-brand-mark-ring" />
              <span className="bigscreen-screen-header-brand-mark-ring bigscreen-screen-header-brand-mark-ring-inner" />
              <span className="bigscreen-title bigscreen-screen-header-brand-short">{shortName}</span>
            </div>

            <div className="bigscreen-screen-header-brand-copy">
              <div className="bigscreen-screen-header-title-plate-shell">
                {skin.assets.headerTitlePlate ? (
                  <div className="bigscreen-screen-header-title-plate" aria-hidden="true" style={{ backgroundImage: `url(${skin.assets.headerTitlePlate})` }} />
                ) : null}
                <h1 className="bigscreen-title bigscreen-screen-header-title">{title}</h1>
              </div>
            </div>
          </div>

          <div className="bigscreen-screen-header-utility">
            <div className="bigscreen-screen-header-utility-item">
              <span className="bigscreen-screen-header-utility-value">{city}</span>
            </div>
            {tenantSwitcher}
            {weather !== "--" && (
              <div className="bigscreen-screen-header-utility-item bigscreen-screen-header-utility-item-weather">
                <span className="bigscreen-screen-header-weather-icon" data-kind={weatherKind}>
                  <WeatherGlyph kind={weatherKind} />
                </span>
                <span className="bigscreen-screen-header-utility-value">{weatherValue.summary}</span>
                {weatherValue.detail ? <span className="bigscreen-screen-header-utility-detail">{weatherValue.detail}</span> : null}
              </div>
            )}
            <div className="bigscreen-screen-header-utility-item">
              <span className="bigscreen-screen-header-utility-value">{formatChineseDate(now)}</span>
            </div>
            <div className="bigscreen-screen-header-utility-item bigscreen-screen-header-utility-item-time">
              <span className="bigscreen-screen-header-time-value">{now.toLocaleTimeString("zh-CN", { hour12: false })}</span>
            </div>
          </div>
        </div>
      </div>

      {hasNav ? (
        <div className="bigscreen-header-nav-shell">
          <ScreenHeaderNavFrame />

          <div className="bigscreen-screen-header-nav-content">
            <nav className="bigscreen-screen-header-nav">
              {navItems.map((item) => {
                const active = pathname === item.path
                return (
                  <Link key={item.path} to={item.path} className={cn("bigscreen-screen-header-tab", active && "bigscreen-screen-header-tab-active")}>
                    <ScreenHeaderNavTabFrame active={active} />
                    <span className="bigscreen-title bigscreen-screen-header-tab-label">{item.label}</span>
                  </Link>
                )
              })}
            </nav>
          </div>
        </div>
      ) : null}
    </header>
  )
}
