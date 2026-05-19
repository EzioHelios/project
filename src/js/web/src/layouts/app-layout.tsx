import { Link, Outlet, useRouterState } from "@tanstack/react-router"
import { useMemo } from "react"
import { AppSidebar } from "@/components/app-sidebar"
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { useAuthStore } from "@/lib/auth"

export function AppLayout() {
  const currentTeam = useAuthStore((state) => state.currentTeam)
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const isBigscreenRoute = pathname.startsWith("/bigscreen")

  const header = useMemo(() => {
    if (pathname === "/platform") {
      return { eyebrow: "首页", title: "数据管理平台" }
    }
    if (pathname === "/teams") {
      return { eyebrow: "Workspace", title: "Teams" }
    }
    if (pathname === "/teams/new") {
      return { eyebrow: "Workspace", title: "Create team" }
    }
    if (pathname.startsWith("/teams/")) {
      return { eyebrow: "Workspace", title: currentTeam?.name ?? "Team" }
    }
    if (pathname.startsWith("/admin")) {
      return { eyebrow: "权限管理", title: "后台管理" }
    }
    if (pathname.startsWith("/profile")) {
      return { eyebrow: "Account", title: "Profile" }
    }
    if (pathname.startsWith("/auth")) {
      if (pathname === "/auth/users") return { eyebrow: "权限管理", title: "用户管理" }
      if (pathname === "/auth/roles") return { eyebrow: "权限管理", title: "角色管理" }
      return { eyebrow: "权限管理", title: "权限管理" }
    }
    if (pathname.startsWith("/data")) {
      if (pathname === "/data/company") return { eyebrow: "数据管理", title: "企业基本信息" }
      if (pathname === "/data/commute") return { eyebrow: "数据管理", title: "员工通勤" }
      if (pathname === "/data/monitor-area") return { eyebrow: "数据管理", title: "监测区域" }
      if (pathname === "/data/inbound") return { eyebrow: "数据管理", title: "入库管理" }
      if (pathname === "/data/outbound") return { eyebrow: "数据管理", title: "出库管理" }
      if (pathname === "/data/terminals") return { eyebrow: "数据管理", title: "监控终端" }
      if (pathname === "/data/meter") return { eyebrow: "数据管理", title: "电表电量" }
      if (pathname === "/data/video") return { eyebrow: "数据管理", title: "视频监控" }
      if (pathname === "/data/alarm-rules") return { eyebrow: "数据管理", title: "预警规则" }
      if (pathname === "/data/alarm-events") return { eyebrow: "数据管理", title: "预警事件" }
      if (pathname === "/data/video-alarm-events") return { eyebrow: "数据管理", title: "视频监控预警事件" }
      if (pathname === "/data/energy-storage") return { eyebrow: "数据管理", title: "储能数值设置" }
      if (pathname === "/data/api-key-mapping") return { eyebrow: "数据管理", title: "接口结果key映射" }
      return { eyebrow: "数据管理", title: "数据管理" }
    }
    if (pathname.startsWith("/tasks")) {
      if (pathname === "/tasks/interval") return { eyebrow: "定时任务", title: "时间间隔设置" }
      if (pathname === "/tasks/crontab") return { eyebrow: "定时任务", title: "crontab设置" }
      if (pathname === "/tasks/schedules") return { eyebrow: "定时任务", title: "定时任务设置" }
      return { eyebrow: "定时任务", title: "定时任务" }
    }
    if (pathname.startsWith("/carbon-mgmt")) {
      if (pathname === "/carbon-mgmt/scope1-mobile") return { eyebrow: "碳排放管理", title: "[范围1] 移动源燃烧" }
      if (pathname === "/carbon-mgmt/scope1-stationary") return { eyebrow: "碳排放管理", title: "[范围1] 固定源燃烧" }
      if (pathname === "/carbon-mgmt/scope1-refrigerant") return { eyebrow: "碳排放管理", title: "[范围1] 制冷剂逸散" }
      if (pathname === "/carbon-mgmt/scope2-bill") return { eyebrow: "碳排放管理", title: "[范围2] 电费账单" }
      if (pathname === "/carbon-mgmt/scope3-waste") return { eyebrow: "碳排放管理", title: "[范围3] 废弃物处理" }
      if (pathname === "/carbon-mgmt/scope3-transport") return { eyebrow: "碳排放管理", title: "[范围3] 外购运输" }
      if (pathname === "/carbon-mgmt/factors") return { eyebrow: "碳排放管理", title: "排放因子库" }
      if (pathname === "/carbon-mgmt/calculation-factors") return { eyebrow: "碳排放管理", title: "计算因子库" }
      if (pathname === "/carbon-mgmt/iot") return { eyebrow: "碳排放管理", title: "IoT时序数据" }
      if (pathname === "/carbon-mgmt/audit") return { eyebrow: "碳排放管理", title: "审核操作日志" }
      return { eyebrow: "碳排放管理", title: "碳排放管理" }
    }
    if (pathname === "/carbon" || pathname === "/carbon/") {
      return { eyebrow: "碳管理", title: "态势总览" }
    }
    if (pathname === "/carbon/page2") {
      return { eyebrow: "碳管理", title: "视频监控" }
    }
    if (pathname === "/carbon/page3") {
      return { eyebrow: "碳管理", title: "电能监测" }
    }
    if (pathname === "/carbon/page4") {
      return { eyebrow: "碳管理", title: "碳能协同" }
    }
    if (pathname === "/carbon/map") {
      return { eyebrow: "碳管理", title: "地图" }
    }
    if (pathname === "/carbon/hwpm") {
      return { eyebrow: "碳管理", title: "户外大屏" }
    }
    return { eyebrow: "Workspace", title: "Dashboard" }
  }, [currentTeam?.name, pathname])

  if (isBigscreenRoute) {
    return <Outlet />
  }

  return (
    <div className="flex min-h-screen flex-col">
      <main className="flex flex-1">
        <SidebarProvider>
          <AppSidebar />
          <SidebarInset>
            <header className="flex h-16 shrink-0 items-center gap-2 border-b border-border/60 bg-background/80 backdrop-blur">
              <div className="flex w-full items-center justify-between gap-4 px-4">
                <div className="flex items-center gap-2">
                  <SidebarTrigger className="-ml-1" />
                  <Separator orientation="vertical" className="mr-2 h-4" />
                  <div>
                    <p className="text-[0.65rem] font-semibold uppercase tracking-[0.24em] text-muted-foreground">{header.eyebrow}</p>
                    <p className="font-heading text-lg font-semibold text-foreground">{header.title}</p>
                  </div>
                </div>
                {currentTeam && pathname !== "/teams/new" && !pathname.startsWith(`/teams/${currentTeam.id}`) && (
                  <Link
                    to="/teams/$teamId"
                    params={{ teamId: currentTeam.id }}
                    className="hidden items-center gap-2 rounded-full border border-border/60 bg-card/80 px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground md:flex"
                  >
                    Active team
                    <span className="text-foreground">{currentTeam.name}</span>
                  </Link>
                )}
              </div>
            </header>
            <Outlet />
          </SidebarInset>
        </SidebarProvider>
      </main>
    </div>
  )
}
