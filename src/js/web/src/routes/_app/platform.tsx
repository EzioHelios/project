/**
 * 数据管理平台 - 首页
 * 结构：快捷操作（图标宫格） + 最近动作
 */
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  Activity,
  AlarmClock,
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

import { AdminPageHeader } from "@/components/admin-ui"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { usePublicConfig } from "@/hooks/use-public-config"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_app/platform")({
  component: PlatformHome,
})

const quickActions = [
  { title: "用户管理", to: "/auth/users", icon: Users },
  { title: "角色管理", to: "/auth/roles", icon: KeyRound },
  { title: "企业基本信息", to: "/data/company", icon: Building2 },
  { title: "员工通勤", to: "/data/commute", icon: Truck },
  { title: "监测区域", to: "/data/monitor-area", icon: MapPinned },
  { title: "入库管理", to: "/data/inbound", icon: Warehouse },
  { title: "出库管理", to: "/data/outbound", icon: HardDrive },
  { title: "监控终端", to: "/data/terminals", icon: Camera },
  { title: "设备类型", to: "/data/device-types", icon: FileDigit },
  { title: "设备测点", to: "/data/device-points", icon: Activity },
  { title: "电表电量", to: "/data/meter", icon: PlugZap },
  { title: "视频监控", to: "/data/video", icon: Video },
  { title: "预警规则", to: "/data/alarm-rules", icon: AlarmClock },
  { title: "预警事件", to: "/data/alarm-events", icon: Activity },
  { title: "视频监控预警事件", to: "/data/video-alarm-events", icon: ClipboardList },
  { title: "储能数值设置", to: "/data/energy-storage", icon: Database },
  { title: "接口结果key映射", to: "/data/api-key-mapping", icon: ShieldCheck },
  { title: "能碳中心", to: "/energy-carbon", icon: ShieldCheck },
] as const

function PlatformHome() {
  const { config } = usePublicConfig()

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title={config.displayName} />

      <PageSection>
        <Card>
          <CardHeader>
            <CardTitle>快捷操作</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-8">
              {quickActions.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={cn(
                    "group flex flex-col items-center justify-center gap-2 rounded-lg border border-border/60 bg-card/70 p-3 text-center transition-colors",
                    "hover:bg-accent/60 hover:text-accent-foreground",
                  )}
                >
                  <item.icon className="h-6 w-6 text-muted-foreground transition-colors group-hover:text-foreground" />
                  <span className="text-xs font-medium">{item.title}</span>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </PageSection>

      <PageSection>
        <Card>
          <CardHeader>
            <CardTitle>最近动作</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">暂无数据</CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}
