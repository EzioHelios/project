import { Outlet, useRouterState } from "@tanstack/react-router"
import { useEffect, useMemo } from "react"
import { AppSidebar } from "@/components/app-sidebar"
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { resolveAdminDomain } from "@/lib/design-domain"
import { GHG_CATEGORY_GROUPS } from "@/lib/ghg-categories"

export function AppLayout() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const isBigscreenRoute = pathname.startsWith("/bigscreen")
  const designDomain = resolveAdminDomain(pathname)

  useEffect(() => {
    const root = document.documentElement
    if (isBigscreenRoute) {
      delete root.dataset.adminDomain
      return
    }
    root.dataset.adminDomain = designDomain
    return () => {
      delete root.dataset.adminDomain
    }
  }, [designDomain, isBigscreenRoute])

  const header = useMemo(() => {
    if (pathname === "/home") {
      return { eyebrow: "工作台", title: "能碳中心" }
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
      return { eyebrow: "团队空间", title: "团队详情" }
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
      if (pathname === "/data/terminals") return { eyebrow: "采集设备与测点", title: "设备台账" }
      if (pathname === "/data/point-monitoring") return { eyebrow: "采集设备与测点", title: "点位监测" }
      if (pathname === "/data/meter") return { eyebrow: "采集设备与测点", title: "电表电量" }
      if (pathname === "/data/video") return { eyebrow: "采集设备与测点", title: "视频监控" }
      if (pathname === "/data/alarm-rules") return { eyebrow: "监测告警运维", title: "预警规则" }
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
      if (pathname === "/carbon-mgmt/activities") return { eyebrow: "温室气体盘查", title: "活动数据台账" }
      if (pathname === "/carbon-mgmt/import") return { eyebrow: "温室气体盘查", title: "活动数据导入" }
      if (pathname.startsWith("/carbon-mgmt/category/")) {
        const pathSegments = pathname.split("/")
        const categoryCode = pathSegments[pathSegments.length - 1]
        const category = GHG_CATEGORY_GROUPS.flatMap((group) => group.items).find((item) => item.code === categoryCode)
        return { eyebrow: "碳数据填报", title: category ? `${category.code} ${category.name}` : "活动数据分类" }
      }
      if (pathname === "/carbon-mgmt/factors") return { eyebrow: "碳排放因子库", title: "排放因子库" }
      if (pathname === "/carbon-mgmt/calculation-factors") return { eyebrow: "碳排放因子库", title: "计算因子库" }
      return { eyebrow: "碳排放管理", title: "碳排放管理" }
    }
    if (pathname.startsWith("/energy-carbon/monitor")) {
      return { eyebrow: "监测告警运维", title: "监测中心" }
    }
    if (pathname.startsWith("/energy-carbon/alerts")) {
      return { eyebrow: "监测告警运维", title: "告警中心" }
    }
    if (pathname === "/energy" || pathname.startsWith("/energy/")) {
      if (pathname === "/energy/consumption") return { eyebrow: "能源运营", title: "能耗查询" }
      if (pathname === "/energy/intensity") return { eyebrow: "能源运营", title: "能耗强度" }
      if (pathname === "/energy/analysis") return { eyebrow: "能源运营", title: "用能分析" }
      if (pathname === "/energy/benchmark") return { eyebrow: "能源运营", title: "能效对标" }
      if (pathname === "/energy/flow") return { eyebrow: "能源运营", title: "能流分析" }
      if (pathname === "/energy/balance") return { eyebrow: "能源运营", title: "能效平衡" }
      if (pathname === "/energy/budget") return { eyebrow: "气候与减碳", title: "能碳预算" }
      return { eyebrow: "能源运营", title: "能源运营" }
    }
    if (pathname === "/microgrid" || pathname.startsWith("/microgrid/")) {
      if (pathname === "/microgrid/overview") return { eyebrow: "微电网运营", title: "运行总览" }
      if (pathname === "/microgrid/operations") return { eyebrow: "微电网运营", title: "运行监控" }
      if (pathname === "/microgrid/forecast") return { eyebrow: "微电网运营", title: "预测分析" }
      if (pathname === "/microgrid/optimization") return { eyebrow: "微电网运营", title: "智能优化" }
      if (pathname === "/microgrid/dispatch") return { eyebrow: "微电网运营", title: "调度记录" }
      if (pathname === "/microgrid/settings/assets") return { eyebrow: "微电网配置", title: "设备与场景" }
      if (pathname === "/microgrid/settings/flexibility") return { eyebrow: "微电网配置", title: "柔性契约" }
      return { eyebrow: "微电网运营", title: "微电网运营" }
    }
    if (pathname.startsWith("/carbon")) {
      if (pathname === "/carbon/organization/overview") return { eyebrow: "组织温室气体盘查", title: "组织碳总览" }
      if (pathname === "/carbon/organization/records") return { eyebrow: "组织温室气体盘查", title: "碳排放查询" }
      if (pathname === "/carbon/organization/flow") return { eyebrow: "组织温室气体盘查", title: "碳流分析" }
      if (pathname === "/carbon/organization/boundary") return { eyebrow: "组织温室气体盘查", title: "核算边界" }
      if (pathname === "/carbon/organization/inventory") return { eyebrow: "组织温室气体盘查", title: "碳盘查" }
      if (pathname === "/carbon/product-footprint") return { eyebrow: "专项碳核算", title: "产品碳足迹核算" }
      if (pathname === "/carbon/supply-chain") return { eyebrow: "专项碳核算", title: "供应链碳管理" }
      if (pathname === "/carbon/verification") return { eyebrow: "组织温室气体盘查", title: "碳核查支撑" }
      if (pathname.startsWith("/carbon/assets")) return { eyebrow: "碳资产", title: "碳资产管理" }
      if (pathname.startsWith("/carbon/climate")) return { eyebrow: "气候与减碳", title: "气候目标与披露" }
      if (pathname === "/carbon/reduction/overview") return { eyebrow: "气候与减碳", title: "减排概览" }
      if (pathname === "/carbon/reduction/projects") return { eyebrow: "气候与减碳", title: "减排项目库" }
      if (pathname === "/carbon/reduction/methodologies") return { eyebrow: "气候与减碳", title: "方法学与CCER" }
      return { eyebrow: "碳核算", title: "碳核算" }
    }
    return { eyebrow: "工作台", title: "首页" }
  }, [pathname])

  if (isBigscreenRoute) {
    return <Outlet />
  }

  return (
    <div className="admin-shell flex min-h-svh flex-col" data-design-domain={designDomain}>
      <main className="flex flex-1">
        <SidebarProvider>
          <AppSidebar />
          <SidebarInset>
            <header className="admin-shell-header flex h-14 shrink-0 items-center gap-2 border-b">
              <div className="flex w-full items-center justify-between gap-4 px-4">
                <div className="flex items-center gap-2">
                  <SidebarTrigger className="-ml-1" />
                  <Separator orientation="vertical" className="mr-2 h-4" />
                  <div className="flex min-w-0 items-center gap-2 text-sm">
                    <span className="font-medium text-muted-foreground">{header.eyebrow}</span>
                    <span className="text-muted-foreground/50">/</span>
                    <span className="truncate font-medium text-foreground">{header.title}</span>
                  </div>
                </div>
              </div>
            </header>
            <Outlet />
          </SidebarInset>
        </SidebarProvider>
      </main>
    </div>
  )
}
