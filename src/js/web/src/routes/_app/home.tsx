import { createFileRoute, Link } from "@tanstack/react-router"
import { AlarmClock, ArrowRight, BookOpen, Gauge, MapPinned, MonitorPlay, ShieldCheck, Zap } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"
import { useAuthStore } from "@/lib/auth"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_app/home")({
  component: HomePage,
})

const quickActions = [
  { title: "经营总览", to: "/energy-carbon", icon: Gauge, description: "查看核心指标和整体运行态势" },
  { title: "综能监测", to: "/energy-carbon/energy", icon: Zap, description: "查看能源结构、趋势和异常" },
  { title: "监测中心", to: "/energy-carbon/monitor", icon: MonitorPlay, description: "聚合区域、设备和视频链路" },
  { title: "告警中心", to: "/energy-carbon/alerts", icon: AlarmClock, description: "处置待办告警和风险事件" },
  { title: "能流分析", to: "/energy-carbon/flows", icon: MapPinned, description: "查看能流路径与关键节点" },
  { title: "碳盘查与核算", to: "/energy-carbon/carbon", icon: ShieldCheck, description: "进入核算与盘查工作台" },
  { title: "数据质量与追溯", to: "/energy-carbon/quality", icon: BookOpen, description: "检查数据完整性和可追溯性" },
  { title: "因子数据库", to: "/energy-carbon/factors", icon: BookOpen, description: "维护排放与计算因子" },
] as const

function HomePage() {
  const user = useAuthStore((state) => state.user)
  const displayName = user?.name || user?.email?.split("@")[0] || "您"

  return (
    <PageContainer className="flex-1 space-y-8">
      <PageHeader
        eyebrow="首页"
        title={`欢迎回来，${displayName}`}
        description="这里是能碳中心的统一入口，围绕经营总览、监测、告警、核算和因子管理展开。"
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
          {quickActions.map((item, index) => (
            <Card key={item.to} hover className="border-border/60 bg-card/80">
              <CardHeader className="space-y-2">
                <div
                  className={cn(
                    "flex h-11 w-11 items-center justify-center rounded-xl text-primary-foreground",
                    index % 4 === 0 && "bg-emerald-500",
                    index % 4 === 1 && "bg-sky-500",
                    index % 4 === 2 && "bg-indigo-500",
                    index % 4 === 3 && "bg-amber-500",
                  )}
                >
                  <item.icon className="h-5 w-5" />
                </div>
                <CardTitle className="text-base">{item.title}</CardTitle>
                <CardDescription>{item.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Button asChild variant="ghost" className="px-0 text-primary hover:bg-transparent hover:text-primary/80">
                  <Link to={item.to}>
                    进入页面 <ArrowRight className="ml-1 h-4 w-4" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </PageSection>

      <PageSection delay={0.1}>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="border-border/60">
            <CardHeader>
              <CardTitle>工作重点</CardTitle>
              <CardDescription>首页不再承载团队创建，而是围绕能碳业务的常用路径组织入口。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <Link to="/energy-carbon/energy" className="rounded-lg border border-border/60 bg-muted/20 p-4 transition-colors hover:bg-muted/40">
                <p className="text-sm font-medium">查看能耗趋势</p>
                <p className="mt-1 text-xs text-muted-foreground">快速进入综能监测，查看能源结构和趋势变化。</p>
              </Link>
              <Link to="/energy-carbon/alerts" className="rounded-lg border border-border/60 bg-muted/20 p-4 transition-colors hover:bg-muted/40">
                <p className="text-sm font-medium">处理告警事件</p>
                <p className="mt-1 text-xs text-muted-foreground">先看风险，再看处理闭环，减少页面跳转。</p>
              </Link>
              <Link to="/energy-carbon/carbon" className="rounded-lg border border-border/60 bg-muted/20 p-4 transition-colors hover:bg-muted/40">
                <p className="text-sm font-medium">进入核算工作台</p>
                <p className="mt-1 text-xs text-muted-foreground">围绕盘查、核算和审核动作组织主流程。</p>
              </Link>
              <Link to="/admin" className="rounded-lg border border-border/60 bg-muted/20 p-4 transition-colors hover:bg-muted/40">
                <p className="text-sm font-medium">权限中心</p>
                <p className="mt-1 text-xs text-muted-foreground">管理用户、角色、权限配置和审计日志。</p>
              </Link>
            </CardContent>
          </Card>

          <Card className="border-border/60 bg-linear-to-br from-muted/30 to-muted/10">
            <CardHeader className="space-y-1 pb-3">
              <CardTitle className="text-lg">最近动作</CardTitle>
              <CardDescription>常用的能碳与权限入口</CardDescription>
            </CardHeader>
            <CardContent className="space-y-1.5">
              <Link to="/energy-carbon" className="group flex items-center gap-3 rounded-lg bg-background/60 p-3 transition-all hover:bg-background hover:shadow-sm">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 transition-colors group-hover:bg-emerald-500 group-hover:text-white dark:text-emerald-400">
                  <Gauge className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm">能碳中心总览</p>
                  <p className="text-xs text-muted-foreground">查看整体运行态势</p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
              </Link>
              <Link to="/energy-carbon/alerts" className="group flex items-center gap-3 rounded-lg bg-background/60 p-3 transition-all hover:bg-background hover:shadow-sm">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 text-amber-600 transition-colors group-hover:bg-amber-500 group-hover:text-white dark:text-amber-400">
                  <AlarmClock className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm">告警中心</p>
                  <p className="text-xs text-muted-foreground">查看待处理事件</p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
              </Link>
              <Link to="/auth/users" className="group flex items-center gap-3 rounded-lg bg-background/60 p-3 transition-all hover:bg-background hover:shadow-sm">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-500/10 text-sky-600 transition-colors group-hover:bg-sky-500 group-hover:text-white dark:text-sky-400">
                  <ShieldCheck className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm">权限中心</p>
                  <p className="text-xs text-muted-foreground">管理用户、角色与审计</p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
              </Link>
            </CardContent>
          </Card>
        </div>
      </PageSection>
    </PageContainer>
  )
}
