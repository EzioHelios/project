import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowRight, BarChart3, ClipboardCheck, Factory, Gauge, GitBranch, Landmark, LineChart, PackageCheck, ShieldCheck, SlidersHorizontal, TrendingUp, Zap } from "lucide-react"
import { useState } from "react"

import { AdminPageHeader, ChartPanel } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { createComboTrendChartOption, createDistributionChartOption, useAdminChartTheme } from "@/lib/admin-chart-theme"
import { AdminDomainScope, type DesignDomain } from "@/lib/design-domain"

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
] as const

const carbonFunctions = [
  {
    title: "碳排放核算",
    to: "/carbon/accounting",
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
    to: "/carbon/assets",
    icon: Landmark,
    promise: "管理配额、碳信用、履约清缴和缺口预测。",
    action: "查看资产",
  },
  {
    title: "能碳预算",
    to: "/energy/budget",
    icon: TrendingUp,
    promise: "按年度目标跟踪能耗、碳排、偏差和调整记录。",
    action: "管理预算",
  },
] as const

const trendPoints = [
  { period: "01月", energy: 10820, carbon: 5260 },
  { period: "02月", energy: 11260, carbon: 5410 },
  { period: "03月", energy: 11940, carbon: 5820 },
  { period: "04月", energy: 11780, carbon: 5690 },
  { period: "05月", energy: 12460, carbon: 6110 },
  { period: "06月", energy: 12840, carbon: 6420 },
] as const

const distributionData = {
  energy: [
    { name: "压铸车间 / 电力", value: 36 },
    { name: "热处理区 / 天然气", value: 24 },
    { name: "机加工区 / 电力", value: 21 },
    { name: "公辅系统 / 蒸汽", value: 19 },
  ],
  carbon: [
    { name: "压铸车间 / Scope 2", value: 34 },
    { name: "热处理区 / Scope 1", value: 27 },
    { name: "物流仓储 / Scope 3", value: 22 },
    { name: "公辅系统 / Scope 2", value: 17 },
  ],
}

function HomePage() {
  const [distributionMode, setDistributionMode] = useState<"energy" | "carbon">("energy")
  const neutralChartTheme = useAdminChartTheme("neutral")
  const energyChartTheme = useAdminChartTheme("energy")
  const carbonChartTheme = useAdminChartTheme("carbon")
  const trendOption = createComboTrendChartOption(neutralChartTheme, trendPoints, {
    bars: [{ key: "energy", label: "综合能耗", colorKey: "energy" }],
    lines: [{ key: "carbon", label: "碳排放", colorKey: "carbon", yAxisIndex: 1 }],
    leftAxisName: "MWh",
    rightAxisName: "tCO2e",
  })
  const distributionOption = createDistributionChartOption(distributionMode === "energy" ? energyChartTheme : carbonChartTheme, distributionData[distributionMode], { unit: "%" })

  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="4xl">
      <AdminPageHeader
        title="工作台"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm">
              <Link to="/bigscreen/overview">
                态势大屏
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        }
      />

      <PageSection delay={0.05}>
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="space-y-3">
            <AdminDomainScope domain="energy">
              <FunctionGroup title="能源运营" count="6 项" items={energyFunctions} domain="energy" />
            </AdminDomainScope>
            <AdminDomainScope domain="carbon">
              <FunctionGroup title="碳排放管理" count="6 项" items={carbonFunctions} domain="carbon" />
            </AdminDomainScope>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1">
            <ChartPanel title="能耗与碳排趋势" option={trendOption} height={220} />
            <AdminDomainScope domain={distributionMode}>
              <ChartPanel
                title="分区能碳构成"
                option={distributionOption}
                height={220}
                actions={
                  <Tabs value={distributionMode} onValueChange={(value) => setDistributionMode(value as "energy" | "carbon")} className="gap-0">
                    <TabsList className="h-8">
                      <TabsTrigger value="energy" className="px-2 text-xs">
                        能耗
                      </TabsTrigger>
                      <TabsTrigger value="carbon" className="px-2 text-xs">
                        碳排
                      </TabsTrigger>
                    </TabsList>
                  </Tabs>
                }
              />
            </AdminDomainScope>
          </div>
        </div>
      </PageSection>
    </PageContainer>
  )
}

type FunctionItem = (typeof energyFunctions)[number] | (typeof carbonFunctions)[number]

function FunctionGroup({ title, count, items, domain }: { title: string; count: string; items: readonly FunctionItem[]; domain: DesignDomain }) {
  return (
    <section className="space-y-2.5" data-design-domain={domain}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-semibold text-base leading-6">{title}</h2>
        </div>
        <span className="shrink-0 rounded-md border border-border/70 bg-background px-2 py-1 text-muted-foreground text-xs">{count}</span>
      </div>
      <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => (
          <Link
            key={item.to}
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
            <p className="mt-2 line-clamp-2 flex-1 text-muted-foreground text-xs leading-5">{item.promise}</p>
            <span className="mt-2 font-medium text-primary text-xs leading-5">{item.action}</span>
          </Link>
        ))}
      </div>
    </section>
  )
}
