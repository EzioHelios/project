import { createFileRoute, Link } from "@tanstack/react-router"
import { AlarmClock, ArrowRight, BookOpen, Gauge, MapPinned, MonitorPlay, ShieldCheck, Zap } from "lucide-react"

import { AdminPageHeader, AdminPanel } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { useAuthStore } from "@/lib/auth"

export const Route = createFileRoute("/_app/home")({
  component: HomePage,
})

const quickActions = [
  { title: "经营总览", to: "/energy-carbon", icon: Gauge },
  { title: "综能监测", to: "/energy-carbon/energy", icon: Zap },
  { title: "监测中心", to: "/energy-carbon/monitor", icon: MonitorPlay },
  { title: "告警中心", to: "/energy-carbon/alerts", icon: AlarmClock },
  { title: "能流分析", to: "/energy-carbon/flows", icon: MapPinned },
  { title: "碳盘查与核算", to: "/energy-carbon/carbon", icon: ShieldCheck },
  { title: "数据质量与追溯", to: "/energy-carbon/quality", icon: BookOpen },
  { title: "因子数据库", to: "/energy-carbon/factors", icon: BookOpen },
] as const

function HomePage() {
  const user = useAuthStore((state) => state.user)
  const displayName = user?.name || user?.email?.split("@")[0] || "您"

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader
        title={`欢迎回来，${displayName}`}
        actions={
          <div className="flex flex-wrap gap-3">
            <Button asChild size="sm">
              <Link to="/energy-carbon">
                进入能碳中心 <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to="/energy-carbon/alerts">查看告警</Link>
            </Button>
          </div>
        }
      />

      <PageSection delay={0.05}>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {quickActions.map((item) => (
            <Link key={item.to} to={item.to} className="group rounded-lg border border-border/70 bg-background/70 p-4 transition-colors hover:border-primary/25 hover:bg-accent/35">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent text-accent-foreground">
                  <item.icon className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-sm">{item.title}</div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </PageSection>

      <PageSection delay={0.1}>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <AdminPanel title="工作重点" contentClassName="grid gap-3 sm:grid-cols-2">
            <Link to="/energy-carbon/energy" className="rounded-lg border border-border/60 bg-muted/20 p-4 transition-colors hover:bg-muted/40">
              <p className="text-sm font-medium">查看能耗趋势</p>
            </Link>
            <Link to="/energy-carbon/alerts" className="rounded-lg border border-border/60 bg-muted/20 p-4 transition-colors hover:bg-muted/40">
              <p className="text-sm font-medium">处理告警事件</p>
            </Link>
            <Link to="/energy-carbon/carbon" className="rounded-lg border border-border/60 bg-muted/20 p-4 transition-colors hover:bg-muted/40">
              <p className="text-sm font-medium">进入核算工作台</p>
            </Link>
            <Link to="/admin" className="rounded-lg border border-border/60 bg-muted/20 p-4 transition-colors hover:bg-muted/40">
              <p className="text-sm font-medium">权限中心</p>
            </Link>
          </AdminPanel>

          <AdminPanel title="最近动作" contentClassName="space-y-1.5">
            <Link to="/energy-carbon" className="group flex items-center gap-3 rounded-lg bg-background/60 p-3 transition-all hover:bg-background hover:shadow-sm">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                <Gauge className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">能碳中心总览</p>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
            </Link>
            <Link to="/energy-carbon/alerts" className="group flex items-center gap-3 rounded-lg bg-background/60 p-3 transition-all hover:bg-background hover:shadow-sm">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                <AlarmClock className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">告警中心</p>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
            </Link>
            <Link to="/auth/users" className="group flex items-center gap-3 rounded-lg bg-background/60 p-3 transition-all hover:bg-background hover:shadow-sm">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">权限中心</p>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
            </Link>
          </AdminPanel>
        </div>
      </PageSection>
    </PageContainer>
  )
}
