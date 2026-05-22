import { Link } from "@tanstack/react-router"

import { ScreenHeaderFrame } from "@/components/bigscreen/primitives/ScreenHeaderFrame"
import { ScreenHeaderNavFrame } from "@/components/bigscreen/primitives/ScreenHeaderNavFrame"
import { ScreenHeaderNavTabFrame } from "@/components/bigscreen/primitives/ScreenHeaderNavTabFrame"
import { useBigscreenSkin } from "@/components/bigscreen/skins/context"
import { cn } from "@/lib/utils"

type BigscreenNavItem = {
  label: string
  path: string
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
}: {
  title: string
  shortName: string
  description: string
  currentLabel: string
  city: string
  weather: string
  now: Date
  navItems: BigscreenNavItem[]
  pathname: string
}) {
  const skin = useBigscreenSkin()

  return (
    <header className="bigscreen-header-stack bigscreen-screen-header">
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
              <span className="bigscreen-screen-header-utility-key">地级市</span>
              <span className="bigscreen-screen-header-utility-value">{city}</span>
            </div>
            <div className="bigscreen-screen-header-utility-item">
              <span className="bigscreen-screen-header-utility-key">天气</span>
              <span className="bigscreen-screen-header-utility-value">{weather}</span>
            </div>
            <div className="bigscreen-screen-header-utility-item">
              <span className="bigscreen-screen-header-utility-key">日期</span>
              <span className="bigscreen-screen-header-utility-value">{now.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })}</span>
            </div>
            <div className="bigscreen-screen-header-utility-item bigscreen-screen-header-utility-item-time">
              <span className="bigscreen-screen-header-utility-key">时间</span>
              <span className="bigscreen-screen-header-time-value">{now.toLocaleTimeString("zh-CN", { hour12: false })}</span>
            </div>
          </div>
        </div>
      </div>

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
    </header>
  )
}
