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
    if (pathname === "/home") {
      return { eyebrow: "首页", title: "能碳中心工作台" }
    }
    if (pathname === "/platform") {
      return { eyebrow: "首页", title: "数据管理平台" }
    }
    if (pathname === "/teams") {
      return { eyebrow: "团队空间", title: "团队列表" }
    }
    if (pathname === "/teams/new") {
      return { eyebrow: "团队空间", title: "创建团队" }
    }
    if (pathname.startsWith("/teams/")) {
      return { eyebrow: "团队空间", title: currentTeam?.name ?? "团队详情" }
    }
    if (pathname.startsWith("/admin")) {
      if (pathname === "/admin") return { eyebrow: "权限中心", title: "权限中心概览" }
      if (pathname === "/admin/users" || pathname.startsWith("/admin/users/")) return { eyebrow: "权限中心", title: "用户管理" }
      if (pathname === "/admin/roles") return { eyebrow: "权限中心", title: "权限配置" }
      if (pathname === "/admin/audit") return { eyebrow: "权限中心", title: "审计日志" }
      if (pathname.startsWith("/admin/teams")) return { eyebrow: "后台管理", title: "团队管理" }
      return { eyebrow: "权限中心", title: "权限中心" }
    }
    if (pathname.startsWith("/profile")) {
      return { eyebrow: "账号设置", title: "个人资料" }
    }
    if (pathname.startsWith("/auth")) {
      if (pathname === "/auth/users") return { eyebrow: "权限中心", title: "用户管理" }
      if (pathname === "/auth/roles") return { eyebrow: "权限中心", title: "角色管理" }
      return { eyebrow: "权限中心", title: "权限中心" }
    }
    if (pathname.startsWith("/data")) {
      if (pathname === "/data/company") return { eyebrow: "企业与组织", title: "企业基本信息" }
      if (pathname === "/data/monitor-area") return { eyebrow: "企业与组织", title: "监测区域" }
      if (pathname === "/data/production-products") return { eyebrow: "企业与组织", title: "产品档案" }
      if (pathname === "/data/commute") return { eyebrow: "业务活动台账", title: "员工通勤" }
      if (pathname === "/data/inbound") return { eyebrow: "业务活动台账", title: "入库管理" }
      if (pathname === "/data/outbound") return { eyebrow: "业务活动台账", title: "出库管理" }
      if (pathname === "/data/product-prices") return { eyebrow: "业务活动台账", title: "产品价格" }
      if (pathname === "/data/production-output") return { eyebrow: "业务活动台账", title: "产品批次产量" }
      if (pathname === "/data/product-resource-bindings") return { eyebrow: "业务活动台账", title: "产品产线关联" }
      if (pathname === "/data/terminals") return { eyebrow: "采集设备与测点", title: "监控终端" }
      if (pathname === "/data/meter") return { eyebrow: "采集设备与测点", title: "电表电量" }
      if (pathname === "/data/video") return { eyebrow: "采集设备与测点", title: "视频监控" }
      if (pathname === "/data/alarm-rules") return { eyebrow: "监测告警运维", title: "预警规则" }
      if (pathname === "/data/alarm-events") return { eyebrow: "监测告警运维", title: "预警事件" }
      if (pathname === "/data/video-alarm-events") return { eyebrow: "监测告警运维", title: "视频监控预警事件" }
      if (pathname === "/data/energy-storage") return { eyebrow: "碳排放因子库", title: "能源折标与储能口径" }
      if (pathname === "/data/api-key-mapping") return { eyebrow: "碳排放因子库", title: "接口结果key映射" }
      return { eyebrow: "基础数据", title: "基础数据" }
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
      if (pathname === "/carbon-mgmt/factors") return { eyebrow: "碳排放因子库", title: "排放因子库" }
      if (pathname === "/carbon-mgmt/calculation-factors") return { eyebrow: "碳排放因子库", title: "计算因子库" }
      if (pathname === "/carbon-mgmt/iot") return { eyebrow: "采集设备与测点", title: "IoT时序数据" }
      if (pathname === "/carbon-mgmt/audit") return { eyebrow: "碳排放管理", title: "审核操作日志" }
      return { eyebrow: "碳排放管理", title: "碳排放管理" }
    }
    if (pathname.startsWith("/energy-carbon/monitor")) {
      return { eyebrow: "监测告警运维", title: "监测中心" }
    }
    if (pathname.startsWith("/energy-carbon/alerts")) {
      return { eyebrow: "监测告警运维", title: "告警中心" }
    }
    if (pathname === "/energy" || pathname.startsWith("/energy/")) {
      if (pathname === "/energy/consumption") return { eyebrow: "能源管理", title: "能耗查询" }
      if (pathname === "/energy/intensity") return { eyebrow: "能源管理", title: "能源消费量和强度计算" }
      if (pathname === "/energy/analysis") return { eyebrow: "能源管理", title: "能源消费分析与用能策略推荐" }
      if (pathname === "/energy/benchmark") return { eyebrow: "能源管理", title: "能效对标" }
      if (pathname === "/energy/flow") return { eyebrow: "能源管理", title: "能流分析" }
      if (pathname === "/energy/balance") return { eyebrow: "能源管理", title: "能效平衡与优化" }
      if (pathname === "/energy/budget") return { eyebrow: "能源管理", title: "用能与碳排放预算管理" }
      return { eyebrow: "能源管理", title: "能源管理" }
    }
    if (pathname.startsWith("/carbon")) {
      if (pathname === "/carbon/accounting") return { eyebrow: "碳排放管理", title: "碳排放核算" }
      if (pathname === "/carbon/product-footprint") return { eyebrow: "碳排放管理", title: "产品碳足迹核算" }
      if (pathname === "/carbon/supply-chain") return { eyebrow: "碳排放管理", title: "供应链碳管理" }
      if (pathname === "/carbon/verification") return { eyebrow: "碳排放管理", title: "碳核查支撑" }
      if (pathname === "/carbon/assets") return { eyebrow: "碳排放管理", title: "碳资产管理" }
      return { eyebrow: "碳排放管理", title: "碳排放管理" }
    }
    return { eyebrow: "工作台", title: "首页" }
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
                    当前团队
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
