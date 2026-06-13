import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useRouterState } from "@tanstack/react-router"
import { AlarmClock, BellRing, Building2, ClipboardList, Cpu, Database, Home, MonitorPlay, ShieldCheck, Users, Zap } from "lucide-react"
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
    setTeams(teamsData)
  }, [isError, isLoading, setTeams, storeIds, teamIds, teamsData])

  const navMain = useMemo(() => {
    const items: React.ComponentProps<typeof NavMain>["items"] = [
      {
        title: "首页",
        to: "/home",
        icon: Home,
      },
      {
        title: "权限中心",
        to: "/auth/users",
        icon: Users,
        isActive:
          pathname.startsWith("/auth") ||
          pathname === "/admin" ||
          pathname.startsWith("/admin/users") ||
          pathname.startsWith("/admin/roles") ||
          pathname.startsWith("/admin/audit"),
        items: [
          { title: "用户管理", to: "/auth/users" },
          { title: "角色管理", to: "/auth/roles" },
          { title: "权限配置", to: "/admin/roles" },
          { title: "审计日志", to: "/admin/audit" },
        ],
      },
      {
        title: "能源管理",
        to: "/energy/consumption",
        icon: Zap,
        isActive: pathname.startsWith("/energy"),
        items: [
          { title: "能耗查询", to: "/energy/consumption" },
          { title: "能源消费量和强度计算", to: "/energy/intensity" },
          { title: "能源消费分析与用能策略推荐", to: "/energy/analysis" },
          { title: "能效对标", to: "/energy/benchmark" },
          { title: "能流分析", to: "/energy/flow" },
          { title: "能效平衡与优化", to: "/energy/balance" },
          { title: "用能与碳排放预算管理", to: "/energy/budget" },
        ],
      },
      {
        title: "碳排放管理",
        to: "/carbon/accounting",
        icon: ShieldCheck,
        isActive:
          pathname.startsWith("/carbon") || pathname.startsWith("/carbon-mgmt/scope") || pathname.startsWith("/carbon-mgmt/pending") || pathname.startsWith("/carbon-mgmt/audit"),
        items: [
          { title: "碳排放核算", to: "/carbon/accounting" },
          { title: "产品碳足迹核算", to: "/carbon/product-footprint" },
          { title: "供应链碳管理", to: "/carbon/supply-chain" },
          { title: "碳核查支撑", to: "/carbon/verification" },
          { title: "碳资产管理", to: "/carbon/assets" },
        ],
      },
      {
        title: "大屏中心",
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
        title: "企业与组织",
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
        title: "业务活动台账",
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
        title: "采集设备与测点",
        to: "/data/terminals",
        icon: Cpu,
        isActive:
          pathname.startsWith("/data/terminals") ||
          pathname.startsWith("/data/device-types") ||
          pathname.startsWith("/data/device-points") ||
          pathname.startsWith("/data/meter") ||
          pathname.startsWith("/data/energy-consumption") ||
          pathname.startsWith("/data/video") ||
          pathname.startsWith("/carbon-mgmt/iot"),
        items: [
          { title: "监控终端", to: "/data/terminals" },
          { title: "设备类型", to: "/data/device-types" },
          { title: "设备测点", to: "/data/device-points" },
          { title: "电表电量", to: "/data/meter" },
          { title: "能源消费明细", to: "/data/energy-consumption" },
          { title: "视频监控", to: "/data/video" },
          { title: "IoT时序数据", to: "/carbon-mgmt/iot" },
        ],
      },
      {
        title: "碳排放因子库",
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
          { title: "能源折标与储能口径", to: "/data/energy-storage" },
          { title: "接口结果key映射", to: "/data/api-key-mapping" },
        ],
      },
      {
        title: "监测告警运维",
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
          { title: "视频监控预警事件", to: "/data/video-alarm-events" },
        ],
      },
      {
        title: "定时任务",
        to: "/tasks/interval",
        icon: AlarmClock,
        isActive: pathname.startsWith("/tasks"),
        items: [
          { title: "时间间隔设置", to: "/tasks/interval" },
          { title: "crontab设置", to: "/tasks/crontab" },
          { title: "定时任务设置", to: "/tasks/schedules" },
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
