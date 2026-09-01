import { Bell, CheckCircle2, ChevronLeft, Home, Monitor, UserRound, Zap } from "lucide-react"
import type { ComponentType, ReactNode } from "react"
import type { Team } from "@/lib/generated/api"
import { cn } from "@/lib/utils"

export type MobileSectionKey = "energy" | "devices" | "alerts" | "work-orders" | "profile"

export const mobileSections: {
  key: MobileSectionKey
  label: string
  title: string
  href: string
  icon: ComponentType<{ className?: string }>
}[] = [
  { key: "energy", label: "能碳", title: "能碳", href: "/mobile/energy", icon: Zap },
  { key: "devices", label: "设备", title: "设备", href: "/mobile/devices", icon: Monitor },
  { key: "alerts", label: "告警", title: "告警", href: "/mobile/alerts", icon: Bell },
  { key: "work-orders", label: "工单", title: "工单", href: "/mobile/work-orders", icon: CheckCircle2 },
  { key: "profile", label: "我的", title: "我的", href: "/mobile/profile", icon: UserRound },
]

export function MobileAppShell({
  activeSection,
  teams,
  currentTeam,
  onTeamSelect,
  children,
}: {
  activeSection: MobileSectionKey
  teams: Team[]
  currentTeam: Team | null
  onTeamSelect: (team: Team) => void
  children: ReactNode
}) {
  const active = mobileSections.find((item) => item.key === activeSection) ?? mobileSections[0]

  return (
    <main className="min-h-dvh bg-[#eef1f3] text-[#17212f]">
      <style>{`.tsqd-open-btn-container{display:none!important}`}</style>
      <section className="mx-auto flex min-h-dvh w-full max-w-[430px] flex-col bg-gradient-to-b from-[#fbfcfd] to-[#f4f6f7] shadow-[0_18px_54px_rgba(15,23,42,0.13)]">
        <StatusBar />
        <header className="grid grid-cols-[40px_1fr_40px] items-center px-5 pb-3 pt-1">
          {activeSection !== "energy" ? (
            <a className="grid h-8 w-8 place-items-center rounded-full text-[#17212f] transition active:scale-95" href="/mobile/energy" aria-label="返回能碳首页">
              <ChevronLeft className="h-5 w-5" />
            </a>
          ) : (
            <span className="grid h-8 w-8 place-items-center rounded-full bg-[#e6f3ec] text-[#26734f]" aria-hidden="true">
              <Home className="h-4 w-4" />
            </span>
          )}
          <h1 className="truncate text-center text-[15px] font-semibold tracking-[0] text-[#17212f]">{active.title}</h1>
          <span className="h-8 w-8" aria-hidden="true" />
        </header>

        <div className="px-4 pb-2">
          <label className="sr-only" htmlFor="mobile-team-select">
            当前租户
          </label>
          <select
            id="mobile-team-select"
            className="h-9 w-full rounded-[10px] border border-[#dce4e8] bg-white px-3 text-[12px] font-medium text-[#243145] shadow-[0_5px_14px_rgba(15,23,42,0.04)]"
            value={currentTeam?.id ?? ""}
            onChange={(event) => {
              const team = teams.find((item) => item.id === event.target.value)
              if (team) onTeamSelect(team)
            }}
          >
            {teams.length === 0 ? <option value="">暂无可用租户</option> : null}
            {teams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 px-4 pb-[82px]">{children}</div>

        <nav className="fixed inset-x-0 bottom-0 z-10 mx-auto grid w-full max-w-[430px] grid-cols-5 border-t border-[#e7ebef] bg-white/95 px-2 pb-[calc(env(safe-area-inset-bottom)+8px)] pt-1.5 shadow-[0_-12px_30px_rgba(15,23,42,0.05)]">
          {mobileSections.map((item) => {
            const NavIcon = item.icon
            const selected = item.key === activeSection
            return (
              <a key={item.key} className={cn("grid min-h-11 place-items-center gap-0.5 text-[10px] font-medium", selected ? "text-[#1f8f62]" : "text-[#667085]")} href={item.href}>
                <NavIcon className="h-[18px] w-[18px]" />
                <span>{item.label}</span>
              </a>
            )
          })}
        </nav>
      </section>
    </main>
  )
}

function StatusBar() {
  return (
    <div className="flex h-11 items-center justify-between px-7 pt-2 text-[15px] font-semibold text-[#151922]">
      <span>10:30</span>
      <span className="flex items-center gap-1.5 text-[10px]">
        <span>5G</span>
        <span className="flex h-3 items-end gap-0.5">
          <i className="block h-1.5 w-0.5 rounded bg-[#151922]" />
          <i className="block h-2 w-0.5 rounded bg-[#151922]" />
          <i className="block h-2.5 w-0.5 rounded bg-[#151922]" />
        </span>
        <span className="relative h-2.5 w-5 rounded-[3px] border-[1.5px] border-[#151922] after:absolute after:left-0.5 after:top-0.5 after:h-1 after:w-3 after:rounded-sm after:bg-[#151922] before:absolute before:-right-1 before:top-[3px] before:h-1 before:w-0.5 before:rounded-r before:bg-[#151922]" />
      </span>
    </div>
  )
}
