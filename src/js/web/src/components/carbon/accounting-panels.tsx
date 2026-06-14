import { Link } from "@tanstack/react-router"
import type { LucideIcon } from "lucide-react"
import { ArrowRight, ClipboardCheck, Fuel, Landmark, PlugZap, Truck } from "lucide-react"

import { AdminPanel, StatusBadge } from "@/components/admin-ui"
import { CarbonAccountingResultsPanel } from "@/components/carbon/accounting-inventory-panel"
import { Button } from "@/components/ui/button"
import { PendingReviewPanel } from "@/routes/_app/carbon-mgmt/pending"

type CarbonMgmtRoute =
  | "/carbon-mgmt/scope1-stationary"
  | "/carbon-mgmt/scope1-mobile"
  | "/carbon-mgmt/scope1-refrigerant"
  | "/carbon-mgmt/scope2-records"
  | "/carbon-mgmt/scope2-bill"
  | "/carbon-mgmt/scope2-purchased-energy"
  | "/carbon-mgmt/scope2-reconciliation"
  | "/carbon-mgmt/scope3-waste"
  | "/carbon-mgmt/scope3-transport"

export function AccountingOverviewPanel() {
  const entries = [
    { label: "Scope 1", description: "移动源、固定源、制冷剂", icon: Fuel, to: "/carbon-mgmt/scope1-mobile" },
    { label: "Scope 2", description: "电表、账单、外购能源", icon: PlugZap, to: "/carbon-mgmt/scope2-records" },
    { label: "Scope 3", description: "废弃物、外购运输", icon: Truck, to: "/carbon-mgmt/scope3-waste" },
    { label: "审核队列", description: "待复核记录与核算结果", icon: ClipboardCheck, to: "/carbon-mgmt/pending" },
  ] as const

  const readiness = [
    { label: "企业档案", to: "/data/company" },
    { label: "排放因子", to: "/carbon-mgmt/factors" },
    { label: "计算因子", to: "/carbon-mgmt/calculation-factors" },
    { label: "电表台账", to: "/data/meter" },
  ] as const

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.65fr)]">
      <AdminPanel
        title="本期核算工作台"
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to="/carbon/accounting">
              查看核算结果
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        }
      >
        <div className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            {entries.map((item) => (
              <Link
                key={item.label}
                to={item.to}
                className="group rounded-lg border border-border/70 bg-background/70 p-4 transition-colors hover:border-primary/25 hover:bg-accent/35"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-accent text-accent-foreground">
                    <item.icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-sm">{item.label}</div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                    </div>
                    <div className="mt-1 text-muted-foreground text-xs leading-5">{item.description}</div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </AdminPanel>

      <div className="space-y-4">
        <AdminPanel title="待办入口">
          <div className="grid gap-2">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-muted-foreground text-xs">审核状态</span>
              <StatusBadge status="pending" />
            </div>
            <Button asChild className="justify-between">
              <Link to="/carbon-mgmt/pending">
                待审核记录
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button asChild variant="outline" className="justify-between">
              <Link to="/carbon-mgmt/scope2-reconciliation">
                范围 2 对账
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button asChild variant="outline" className="justify-between">
              <Link to="/carbon/verification">
                核查支撑
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>
        </AdminPanel>

        <AdminPanel
          title={
            <span className="flex items-center gap-2">
              <Landmark className="h-4 w-4 text-muted-foreground" />
              <span>数据准备</span>
            </span>
          }
        >
          <div className="grid gap-2">
            {readiness.map((item) => (
              <Button key={item.label} asChild variant="outline" className="justify-between">
                <Link to={item.to}>
                  {item.label}
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
            ))}
          </div>
        </AdminPanel>
      </div>
    </div>
  )
}

export function Scope1AccountingPanel() {
  return (
    <ScopeWorkflowPanel
      title="Scope 1 直接排放"
      icon={Fuel}
      entries={[
        { title: "固定源燃烧", category: "燃料燃烧", source: "锅炉、窑炉、备用发电机", to: "/carbon-mgmt/scope1-stationary" },
        { title: "移动源燃烧", category: "车辆与移动设备", source: "自有车辆、叉车、非道路移动机械", to: "/carbon-mgmt/scope1-mobile" },
        { title: "制冷剂逸散", category: "逸散排放", source: "冷库、空调、制冷机组补充记录", to: "/carbon-mgmt/scope1-refrigerant" },
      ]}
    />
  )
}

export function Scope2AccountingPanel() {
  return (
    <ScopeWorkflowPanel
      title="Scope 2 外购能源"
      icon={PlugZap}
      entries={[
        { title: "电表聚合", category: "自动采集", source: "电表读数、月度聚合、缺口估算", to: "/carbon-mgmt/scope2-records" },
        { title: "电力账单", category: "人工补录", source: "电费账单、峰平谷电量、金额", to: "/carbon-mgmt/scope2-bill" },
        { title: "外购热/汽/冷", category: "外购能源", source: "供应商结算单、折标与因子匹配", to: "/carbon-mgmt/scope2-purchased-energy" },
        { title: "Scope2 对账", category: "校验闭环", source: "账单、电表、外购能源一致性", to: "/carbon-mgmt/scope2-reconciliation" },
      ]}
    />
  )
}

export function Scope3AccountingPanel() {
  return (
    <ScopeWorkflowPanel
      title="Scope 3 价值链活动"
      icon={Truck}
      entries={[
        { title: "废弃物处理", category: "运营废弃物", source: "重量、处理方式、处置方", to: "/carbon-mgmt/scope3-waste" },
        { title: "外购运输", category: "第三方物流", source: "运单、里程、载重、车型", to: "/carbon-mgmt/scope3-transport" },
      ]}
    />
  )
}

export { CarbonAccountingResultsPanel, PendingReviewPanel }

function ScopeWorkflowPanel({
  title,
  icon: Icon,
  entries,
}: {
  title: string
  icon: LucideIcon
  entries: Array<{ title: string; category: string; source: string; to: CarbonMgmtRoute }>
}) {
  return (
    <AdminPanel
      title={
        <span className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          <span>{title}</span>
        </span>
      }
      contentClassName="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
    >
      {entries.map((entry) => (
        <Link
          key={entry.to}
          to={entry.to}
          className="group flex min-h-32 flex-col justify-between rounded-md border border-border/70 bg-background/70 p-4 transition-colors hover:border-primary/25 hover:bg-accent/35"
        >
          <div>
            <div className="flex items-center justify-between gap-3">
              <span className="rounded-sm bg-muted px-2 py-1 text-muted-foreground text-xs">{entry.category}</span>
              <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
            </div>
            <div className="mt-3 font-medium text-sm">{entry.title}</div>
            <div className="mt-2 text-muted-foreground text-xs leading-5">{entry.source}</div>
          </div>
          <div className="mt-4 text-primary text-xs">进入台账</div>
        </Link>
      ))}
    </AdminPanel>
  )
}
