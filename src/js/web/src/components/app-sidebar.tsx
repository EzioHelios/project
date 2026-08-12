import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useRouterState } from "@tanstack/react-router"
import { BellRing, Building2, ClipboardList, Cpu, Database, FileInput, Home, MonitorPlay, Network, Settings, ShieldCheck, Zap } from "lucide-react"
import type * as React from "react"
import { useCallback, useEffect, useMemo } from "react"
import { NavMain } from "@/components/nav-main"
import { NavUser } from "@/components/nav-user"
import { ThemeToggle } from "@/components/theme-toggle"
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail } from "@/components/ui/sidebar"
import { usePublicConfig } from "@/hooks/use-public-config"
import { useAuthStore } from "@/lib/auth"
import { listTeams, type Team } from "@/lib/generated/api"

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { teams, currentTeam, setTeams, setCurrentTeam, isAuthenticated } = useAuthStore()
  const queryClient = useQueryClient()
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const { config } = usePublicConfig()

  const {
    data: teamsData = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["teams"],
    queryFn: async () => {
      const response = await listTeams()
      return response.data?.items ?? []
    },
    enabled: isAuthenticated,
  })

  const teamIds = useMemo(() => teamsData.map((team) => team.id).join("|"), [teamsData])
  const storeIds = useMemo(() => teams.map((team) => team.id).join("|"), [teams])

  useEffect(() => {
    if (isLoading || isError || teamIds === storeIds) {
      return
    }
    const nextCurrentTeam = currentTeam && teamsData.some((team) => team.id === currentTeam.id) ? currentTeam : (teamsData[0] ?? null)
    const shouldRefreshTenantQueries = nextCurrentTeam?.id !== currentTeam?.id
    setTeams(teamsData)
    if (shouldRefreshTenantQueries) {
      void queryClient.invalidateQueries()
    }
  }, [currentTeam, isError, isLoading, queryClient, setTeams, storeIds, teamIds, teamsData])

  const navMain = useMemo(() => {
    const isCarbonModuleRoute = pathname === "/carbon" || pathname.startsWith("/carbon/")
    const isEnergyBudgetRoute = pathname === "/energy/budget"
    const isCarbonMgmtRoute = pathname.startsWith("/carbon-mgmt")
    const items: React.ComponentProps<typeof NavMain>["items"] = [
      {
        title: "工作台",
        to: "/home",
        icon: Home,
      },
      {
        title: "系统管理",
        to: "/auth/users",
        icon: Settings,
        isActive:
          pathname.startsWith("/auth") ||
          pathname === "/admin" ||
          pathname.startsWith("/admin/users") ||
          pathname.startsWith("/admin/roles") ||
          pathname.startsWith("/admin/audit") ||
          pathname.startsWith("/tasks"),
        items: [
          { title: "用户管理", to: "/auth/users" },
          { title: "角色管理", to: "/auth/roles" },
          { title: "权限配置", to: "/admin/roles" },
          { title: "审计日志", to: "/admin/audit" },
          { title: "平台任务", kind: "section" },
          { title: "时间间隔", to: "/tasks/interval" },
          { title: "Crontab", to: "/tasks/crontab" },
          { title: "任务计划", to: "/tasks/schedules" },
        ],
      },
      {
        title: "能源运营",
        to: "/energy/consumption",
        icon: Zap,
        isActive: pathname.startsWith("/energy") && !isEnergyBudgetRoute,
        items: [
          { title: "能耗查询", to: "/energy/consumption" },
          { title: "能耗强度", to: "/energy/intensity" },
          { title: "用能分析", to: "/energy/analysis" },
          { title: "能效对标", to: "/energy/benchmark" },
          { title: "能流分析", to: "/energy/flow" },
          { title: "能效平衡", to: "/energy/balance" },
        ],
      },
      {
        title: "微电网运营",
        to: "/microgrid/overview",
        icon: Network,
        isActive: pathname.startsWith("/microgrid"),
        items: [
          { title: "运行总览", to: "/microgrid/overview" },
          { title: "运行监控", to: "/microgrid/operations" },
          { title: "预测分析", to: "/microgrid/forecast" },
          { title: "智能优化", to: "/microgrid/optimization" },
        ],
      },
      {
        title: "碳排放管理",
        to: "/carbon/accounting",
        icon: ShieldCheck,
        isActive: isCarbonModuleRoute || isEnergyBudgetRoute,
        items: [
          { title: "碳排放核算", to: "/carbon/accounting" },
          { title: "产品碳足迹", to: "/carbon/product-footprint" },
          { title: "供应链碳", to: "/carbon/supply-chain" },
          { title: "核查支撑", to: "/carbon/verification" },
          { title: "碳资产管理", to: "/carbon/assets" },
          { title: "能碳预算", to: "/energy/budget" },
        ],
      },
      {
        title: "态势大屏",
        to: "/bigscreen/overview",
        icon: MonitorPlay,
        isActive: pathname.startsWith("/bigscreen"),
        items: [
          { title: "态势总览", to: "/bigscreen/overview" },
          { title: "企业介绍", to: "/bigscreen/intro" },
          { title: "电量监控", to: "/bigscreen/power" },
          { title: "能碳协同", to: "/bigscreen/carbon" },
          { title: "华谊园区", to: "/bigscreen/huayi" },
        ],
      },
      {
        title: "组织档案",
        to: "/data/company",
        icon: Building2,
        isActive: pathname.startsWith("/data/company") || pathname.startsWith("/data/monitor-area") || pathname.startsWith("/data/production-products"),
        items: [
          { title: "企业基本信息", to: "/data/company" },
          { title: "监测区域", to: "/data/monitor-area" },
          { title: "产品档案", to: "/data/production-products" },
        ],
      },
      {
        title: "活动台账",
        to: "/data/commute",
        icon: ClipboardList,
        isActive:
          pathname.startsWith("/data/commute") ||
          pathname.startsWith("/data/inbound") ||
          pathname.startsWith("/data/outbound") ||
          pathname.startsWith("/data/product-prices") ||
          pathname.startsWith("/data/production-output") ||
          pathname.startsWith("/data/product-resource-bindings"),
        items: [
          { title: "员工通勤", to: "/data/commute" },
          { title: "入库管理", to: "/data/inbound" },
          { title: "出库管理", to: "/data/outbound" },
          { title: "产品价格", to: "/data/product-prices" },
          { title: "产品批次产量", to: "/data/production-output" },
          { title: "产品产线关联", to: "/data/product-resource-bindings" },
        ],
      },
      {
        title: "碳数据填报",
        to: "/carbon-mgmt/scope2-bill",
        icon: FileInput,
        isActive: isCarbonMgmtRoute,
        items: [
          { title: "Scope 1", kind: "section" },
          { title: "固定源燃烧", to: "/carbon-mgmt/scope1-stationary" },
          { title: "移动源燃烧", to: "/carbon-mgmt/scope1-mobile" },
          { title: "制冷剂逸散", to: "/carbon-mgmt/scope1-refrigerant" },
          { title: "Scope 2", kind: "section" },
          { title: "电力账单", to: "/carbon-mgmt/scope2-bill" },
          { title: "电表聚合", to: "/carbon-mgmt/scope2-records" },
          { title: "外购热汽冷", to: "/carbon-mgmt/scope2-purchased-energy" },
          { title: "Scope2 对账", to: "/carbon-mgmt/scope2-reconciliation" },
          { title: "Scope 3", kind: "section" },
          { title: "废弃物处理", to: "/carbon-mgmt/scope3-waste" },
          { title: "外购运输", to: "/carbon-mgmt/scope3-transport" },
          { title: "审核流转", kind: "section" },
          { title: "待审核", to: "/carbon-mgmt/pending" },
          { title: "审核日志", to: "/carbon-mgmt/audit" },
        ],
      },
      {
        title: "设备与测点",
        to: "/data/terminals",
        icon: Cpu,
        isActive:
          pathname.startsWith("/data/terminals") ||
          pathname.startsWith("/data/device-types") ||
          pathname.startsWith("/data/device-points") ||
          pathname.startsWith("/data/point-monitoring") ||
          pathname.startsWith("/data/meter") ||
          pathname.startsWith("/data/energy-consumption") ||
          pathname.startsWith("/data/video"),
        items: [
          { title: "监控终端", to: "/data/terminals" },
          { title: "设备类型", to: "/data/device-types" },
          { title: "设备测点", to: "/data/device-points" },
          { title: "点位监测", to: "/data/point-monitoring" },
          { title: "电表电量", to: "/data/meter" },
          { title: "能源消费明细", to: "/data/energy-consumption" },
          { title: "视频监控", to: "/data/video" },
        ],
      },
      {
        title: "因子与口径",
        to: "/carbon-mgmt/factors",
        icon: Database,
        isActive:
          pathname.startsWith("/carbon-mgmt/factors") ||
          pathname.startsWith("/carbon-mgmt/calculation-factors") ||
          pathname.startsWith("/data/api-key-mapping") ||
          pathname.startsWith("/data/energy-storage"),
        items: [
          { title: "排放因子库", to: "/carbon-mgmt/factors" },
          { title: "计算因子库", to: "/carbon-mgmt/calculation-factors" },
          { title: "折标与储能", to: "/data/energy-storage" },
          { title: "接口映射", to: "/data/api-key-mapping" },
        ],
      },
      {
        title: "监测告警",
        to: "/energy-carbon/monitor",
        icon: BellRing,
        isActive:
          pathname.startsWith("/energy-carbon/monitor") ||
          pathname.startsWith("/energy-carbon/alerts") ||
          pathname.startsWith("/data/alarm-rules") ||
          pathname.startsWith("/data/alarm-events") ||
          pathname.startsWith("/data/video-alarm-events"),
        items: [
          { title: "监测中心", to: "/energy-carbon/monitor" },
          { title: "告警中心", to: "/energy-carbon/alerts" },
          { title: "规则与事件台账", kind: "section" },
          { title: "预警规则", to: "/data/alarm-rules" },
          { title: "预警事件", to: "/data/alarm-events" },
          { title: "视频预警", to: "/data/video-alarm-events" },
        ],
      },
    ]

    return items
  }, [pathname])

  const teamOptions = teamsData.length > 0 ? teamsData : teams
  const handleTeamSelect = useCallback(
    (team: Team) => {
      if (team.id === currentTeam?.id) {
        return
      }
      setCurrentTeam(team)
      void queryClient.invalidateQueries()
    },
    [currentTeam?.id, queryClient, setCurrentTeam],
  )

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <span className="text-sm font-semibold">{config.shortName}</span>
          </div>
          <div className="min-w-0 group-data-[collapsible=icon]:hidden">
            <div className="truncate text-sm font-semibold">{config.displayName}</div>
            <div className="truncate text-xs text-muted-foreground">仓库碳管理</div>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={navMain} />
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-center gap-2">
          <div className="flex-1 min-w-0">
            <NavUser teams={teamOptions} currentTeam={currentTeam} onTeamSelect={handleTeamSelect} />
          </div>
          <div className="shrink-0 group-data-[collapsible=icon]:hidden">
            <ThemeToggle />
          </div>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
