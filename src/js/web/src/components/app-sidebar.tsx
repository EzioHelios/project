import { useQuery } from "@tanstack/react-query"
import { useRouterState } from "@tanstack/react-router"
import { AlarmClock, BellRing, BookOpen, Database, Factory, Gauge, Home, MonitorPlay, ShieldCheck, Users } from "lucide-react"
import type * as React from "react"
import { useEffect, useMemo } from "react"
import { NavMain } from "@/components/nav-main"
import { NavProjects } from "@/components/nav-projects"
import { NavUser } from "@/components/nav-user"
import { TeamSwitcher } from "@/components/team-switcher"
import { ThemeToggle } from "@/components/theme-toggle"
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail } from "@/components/ui/sidebar"
import { usePublicConfig } from "@/hooks/use-public-config"
import { useAuthStore } from "@/lib/auth"
import { listTeams, type Team } from "@/lib/generated/api"

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { teams, currentTeam, setTeams, setCurrentTeam, user, isAuthenticated } = useAuthStore()
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
        to: "/platform",
        icon: Home,
      },
      {
        title: "权限管理",
        to: "/auth/users",
        icon: Users,
        isActive: pathname.startsWith("/auth"),
        items: [
          { title: "用户管理", to: "/auth/users" },
          { title: "角色管理", to: "/auth/roles" },
        ],
      },
      {
        title: "能碳中心",
        to: "/energy-carbon",
        icon: Gauge,
        isActive: pathname.startsWith("/energy-carbon"),
        items: [
          { title: "经营总览", to: "/energy-carbon" },
          { title: "综能监测", to: "/energy-carbon/energy" },
          { title: "监测中心", to: "/energy-carbon/monitor" },
          { title: "告警中心", to: "/energy-carbon/alerts" },
          { title: "能流分析", to: "/energy-carbon/flows" },
          { title: "碳盘查与核算", to: "/energy-carbon/carbon" },
          { title: "数据质量与追溯", to: "/energy-carbon/quality" },
          { title: "因子数据库", to: "/energy-carbon/factors" },
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
        title: "数据台账",
        to: "/data/company",
        icon: Database,
        isActive:
          pathname.startsWith("/data/company") ||
          pathname.startsWith("/data/commute") ||
          pathname.startsWith("/data/inbound") ||
          pathname.startsWith("/data/outbound") ||
          pathname.startsWith("/data/api-key-mapping") ||
          pathname.startsWith("/data/energy-storage"),
        items: [
          { title: "企业基本信息", to: "/data/company" },
          { title: "员工通勤", to: "/data/commute" },
          { title: "入库管理", to: "/data/inbound" },
          { title: "出库管理", to: "/data/outbound" },
          { title: "接口结果key映射", to: "/data/api-key-mapping" },
          { title: "储能数值设置", to: "/data/energy-storage" },
        ],
      },
      {
        title: "监控运维",
        to: "/data/monitor-area",
        icon: Factory,
        isActive:
          pathname.startsWith("/data/monitor-area") ||
          pathname.startsWith("/data/terminals") ||
          pathname.startsWith("/data/device-types") ||
          pathname.startsWith("/data/device-points") ||
          pathname.startsWith("/data/meter") ||
          pathname.startsWith("/data/video") ||
          pathname.startsWith("/carbon-mgmt/iot"),
        items: [
          { title: "监测区域", to: "/data/monitor-area" },
          { title: "监控终端", to: "/data/terminals" },
          { title: "设备类型", to: "/data/device-types" },
          { title: "设备测点", to: "/data/device-points" },
          { title: "电表电量", to: "/data/meter" },
          { title: "视频监控", to: "/data/video" },
          { title: "IoT时序数据", to: "/carbon-mgmt/iot" },
        ],
      },
      {
        title: "预警中心",
        to: "/data/alarm-rules",
        icon: BellRing,
        isActive: pathname.startsWith("/data/alarm-rules") || pathname.startsWith("/data/alarm-events") || pathname.startsWith("/data/video-alarm-events"),
        items: [
          { title: "预警规则", to: "/data/alarm-rules" },
          { title: "预警事件", to: "/data/alarm-events" },
          { title: "视频监控预警事件", to: "/data/video-alarm-events" },
        ],
      },
      {
        title: "碳核算模型",
        to: "/carbon-mgmt/scope1-mobile",
        icon: ShieldCheck,
        isActive:
          pathname.startsWith("/carbon-mgmt/scope1-") ||
          pathname.startsWith("/carbon-mgmt/scope2") ||
          pathname.startsWith("/carbon-mgmt/scope2-") ||
          pathname.startsWith("/carbon-mgmt/scope3-") ||
          pathname.startsWith("/carbon-mgmt/pending") ||
          pathname.startsWith("/carbon-mgmt/audit"),
        items: [
          { title: "数据填报", kind: "section" },
          { title: "[范围1] 移动源燃烧", to: "/carbon-mgmt/scope1-mobile" },
          { title: "[范围1] 固定源燃烧", to: "/carbon-mgmt/scope1-stationary" },
          { title: "[范围1] 制冷剂逸散", to: "/carbon-mgmt/scope1-refrigerant" },
          { title: "[范围2] 用电核算", to: "/carbon-mgmt/scope2" },
          { title: "[范围3] 废弃物处理", to: "/carbon-mgmt/scope3-waste" },
          { title: "[范围3] 外购运输", to: "/carbon-mgmt/scope3-transport" },
          { title: "核算作业", kind: "section" },
          { title: "待审核工作台", to: "/carbon-mgmt/pending" },
          { title: "审核操作日志", to: "/carbon-mgmt/audit" },
        ],
      },
      {
        title: "因子数据库",
        to: "/carbon-mgmt/factors",
        icon: BookOpen,
        isActive: pathname.startsWith("/carbon-mgmt/factors") || pathname.startsWith("/carbon-mgmt/calculation-factors"),
        items: [
          { title: "排放因子库", to: "/carbon-mgmt/factors" },
          { title: "计算因子库", to: "/carbon-mgmt/calculation-factors" },
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

    if (user?.isSuperuser) {
      const auth = items.find((i) => i.title === "权限管理")
      auth?.items?.push({ title: "后台管理", to: "/admin" })
    }

    return items
  }, [pathname, user?.isSuperuser])

  const teamLinks = useMemo(
    () =>
      teams.map((team: Team) => ({
        name: team.name,
        to: "/teams/$teamId",
        params: { teamId: team.id },
        icon: Users,
      })),
    [teams],
  )
  const teamOptions = teamsData.length > 0 ? teamsData : teams

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
        <TeamSwitcher teams={teamOptions} currentTeam={currentTeam} onTeamSelect={setCurrentTeam} />
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={navMain} />
        {teamLinks.length > 0 && <NavProjects label="团队" projects={teamLinks} />}
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-center gap-2">
          <div className="flex-1 min-w-0">
            <NavUser />
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
