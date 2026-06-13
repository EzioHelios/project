/**
 * 数据管理平台 - 首页
 * 结构：快捷操作（图标宫格） + 最近动作
 */
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  Activity,
  AlarmClock,
  ArrowRight,
  Building2,
  Camera,
  ClipboardList,
  Database,
  FileDigit,
  HardDrive,
  KeyRound,
  MapPinned,
  PlugZap,
  ShieldCheck,
  Truck,
  Users,
  Video,
  Warehouse,
} from "lucide-react"

import { AdminEmptyState, AdminPageHeader, AdminPanel } from "@/components/admin-ui"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { usePublicConfig } from "@/hooks/use-public-config"

export const Route = createFileRoute("/_app/platform")({
  component: PlatformHome,
})

const platformGroups = [
  {
    title: "组织与权限",
    items: [
      { title: "用户管理", to: "/auth/users", icon: Users },
      { title: "角色管理", to: "/auth/roles", icon: KeyRound },
      { title: "企业基本信息", to: "/data/company", icon: Building2 },
    ],
  },
  {
    title: "主数据台账",
    items: [
      { title: "员工通勤", to: "/data/commute", icon: Truck },
      { title: "监测区域", to: "/data/monitor-area", icon: MapPinned },
      { title: "入库管理", to: "/data/inbound", icon: Warehouse },
      { title: "出库管理", to: "/data/outbound", icon: HardDrive },
      { title: "设备类型", to: "/data/device-types", icon: FileDigit },
      { title: "设备测点", to: "/data/device-points", icon: Activity },
    ],
  },
  {
    title: "监测与告警",
    items: [
      { title: "监控终端", to: "/data/terminals", icon: Camera },
      { title: "电表电量", to: "/data/meter", icon: PlugZap },
      { title: "视频监控", to: "/data/video", icon: Video },
      { title: "预警规则", to: "/data/alarm-rules", icon: AlarmClock },
      { title: "预警事件", to: "/data/alarm-events", icon: Activity },
      { title: "视频监控预警事件", to: "/data/video-alarm-events", icon: ClipboardList },
    ],
  },
  {
    title: "平台配置",
    items: [
      { title: "储能数值设置", to: "/data/energy-storage", icon: Database },
      { title: "接口结果 key 映射", to: "/data/api-key-mapping", icon: ShieldCheck },
      { title: "能碳中心", to: "/energy-carbon", icon: ShieldCheck },
    ],
  },
] as const

function PlatformHome() {
  const { config } = usePublicConfig()

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title={config.displayName} />

      <PageSection>
        <AdminPanel title="平台入口" contentClassName="grid gap-5 lg:grid-cols-2">
          {platformGroups.map((group) => (
            <section key={group.title} className="space-y-2">
              <h3 className="font-semibold text-muted-foreground text-xs leading-5">{group.title}</h3>
              <div className="grid gap-1.5">
                {group.items.map((item) => (
                  <Link key={item.to} to={item.to} className="group flex items-center gap-3 rounded-md bg-background/60 px-3 py-2.5 transition-colors hover:bg-muted/55">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground transition-colors group-hover:bg-accent group-hover:text-accent-foreground">
                      <item.icon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1 truncate font-medium text-sm">{item.title}</span>
                    <ArrowRight className="h-4 w-4 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </AdminPanel>
      </PageSection>

      <PageSection>
        <AdminPanel title="最近动作">
          <AdminEmptyState title="暂无最近动作" className="min-h-28" />
        </AdminPanel>
      </PageSection>
    </PageContainer>
  )
}
