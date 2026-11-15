import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowRight, BarChart3, ClipboardCheck, Factory, Gauge, GitBranch, Landmark, LineChart, PackageCheck, ShieldCheck, SlidersHorizontal, TrendingUp, Zap } from "lucide-react"

import { AdminPageHeader } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { useAuthStore } from "@/lib/auth"
import type { DesignDomain } from "@/lib/design-domain"
import { canAccessPath } from "@/lib/permissions"

export const Route = createFileRoute("/_app/home")({
  component: HomePage,
})

const energyFunctions = [
  {
    title: "能耗查询",
    to: "/energy/consumption",
    icon: Zap,
    promise: "查清每一类能源的消耗、单耗和账期。",
    action: "查看明细",
  },
  {
    title: "能耗强度",
    to: "/energy/intensity",
    icon: Gauge,
    promise: "把产量、产值和能耗放在同一个强度口径里。",
    action: "计算强度",
  },
  {
    title: "用能分析",
    to: "/energy/analysis",
    icon: LineChart,
    promise: "定位趋势、峰谷和异常，让问题落到区域与设备。",
    action: "打开分析",
  },
  {
    title: "能效对标",
    to: "/energy/benchmark",
    icon: BarChart3,
    promise: "用基准线识别低效环节，保留改进证据。",
    action: "查看对标",
  },
  {
    title: "能流分析",
    to: "/energy/flow",
    icon: GitBranch,
    promise: "追踪能源从输入、转换到使用的流向。",
    action: "追踪能流",
  },
  {
    title: "能效平衡",
    to: "/energy/balance",
    icon: SlidersHorizontal,
    promise: "核对供入、有效利用和损失，找出平衡缺口。",
    action: "核对平衡",
  },
  {
    title: "能碳预算",
    to: "/energy/budget",
    icon: TrendingUp,
    promise: "按年度目标跟踪能耗、碳排、偏差和调整记录。",
    action: "管理预算",
  },
] as const

const carbonFunctions = [
  {
    title: "碳排放核算",
    to: "/carbon/organization/records",
    icon: ShieldCheck,
    promise: "从活动数据、因子匹配到计算结果形成可审核碳账。",
    action: "发起核算",
  },
  {
    title: "产品碳足迹",
    to: "/carbon/product-footprint",
    icon: PackageCheck,
    promise: "按生命周期阶段归集活动数据和分配规则。",
    action: "维护研究",
  },
  {
    title: "供应链碳",
    to: "/carbon/supply-chain",
    icon: Factory,
    promise: "把供应商填报、披露范围和高碳品类连成闭环。",
    action: "查看任务",
  },
  {
    title: "核查支撑",
    to: "/carbon/verification",
    icon: ClipboardCheck,
    promise: "集中处理证据、异常、审核意见和核查记录。",
    action: "进入核查",
  },
  {
    title: "碳资产管理",
    to: "/carbon/assets/overview",
    icon: Landmark,
    promise: "管理配额、碳信用、履约清缴和缺口预测。",
    action: "查看资产",
  },
] as const

function HomePage() {
  const access = useAuthStore((state) => state.access)
  const functions = [
    ...energyFunctions.map((item) => ({ ...item, domain: "energy" as const, category: "能源运营" })),
    ...carbonFunctions.map((item) => ({ ...item, domain: "carbon" as const, category: "碳排放管理" })),
  ].filter((item) => canAccessPath(access, item.to))
  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="4xl">
      <AdminPageHeader
        title="工作台"
        actions={
          canAccessPath(access, "/bigscreen/overview") ? (
            <Button asChild size="sm">
              <Link to="/bigscreen/overview">态势大屏</Link>
            </Button>
          ) : undefined
        }
      />
      <PageSection delay={0.05}>
        <FunctionGrid items={functions} />
      </PageSection>
    </PageContainer>
  )
}

type FunctionItem = ((typeof energyFunctions)[number] | (typeof carbonFunctions)[number]) & { domain: DesignDomain; category: string }

function FunctionGrid({ items }: { items: readonly FunctionItem[] }) {
  return (
    <section className="@container" aria-label="业务功能">
      <div className="grid grid-cols-1 gap-2.5 @min-[32rem]:grid-cols-2 @min-[48rem]:grid-cols-3 @min-[64rem]:grid-cols-4">
        {items.map((item) => (
          <Link
            key={item.to}
            data-design-domain={item.domain}
            to={item.to}
            className="group flex min-h-24 flex-col rounded-md border border-border/70 bg-background p-3 transition-colors hover:border-primary/25 hover:bg-accent/30"
          >
            <div className="flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent text-accent-foreground">
                <item.icon className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center justify-between gap-2">
                  <span className="font-medium text-sm leading-5">{item.title}</span>
                  <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground/60 opacity-0 transition-opacity group-hover:opacity-100" />
                </span>
              </span>
            </div>
            <span className="mt-2 text-muted-foreground text-xs">{item.category}</span>
            <p className="mt-2 line-clamp-2 flex-1 text-muted-foreground text-xs leading-5">{item.promise}</p>
            <span className="mt-2 font-medium text-primary text-xs leading-5">{item.action}</span>
          </Link>
        ))}
      </div>
    </section>
  )
}
