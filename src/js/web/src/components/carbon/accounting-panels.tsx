import { Link } from "@tanstack/react-router"
import { ArrowRight, ClipboardCheck, Fuel, Landmark, PlugZap, Truck } from "lucide-react"

import { AdminPanel, MetricStrip, MetricTile, StatusBadge } from "@/components/admin-ui"
import { CarbonAccountingResultsPanel } from "@/components/carbon/accounting-inventory-panel"
import { ScopeRecordPage } from "@/components/carbon/scope-record-page"
import { Scope2RecordsPanel } from "@/components/carbon/scope2-records-panel"
import { Button } from "@/components/ui/button"
import { PendingReviewPanel } from "@/routes/_app/carbon-mgmt/pending"

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
        description="组织边界、活动数据、排放清单、审核归档"
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
          <MetricStrip>
            <MetricTile label="边界确认" value="01" meta="组织与账期" />
            <MetricTile label="活动数据" value="02" meta="范围 1/2/3" />
            <MetricTile label="排放清单" value="03" meta="计算与质检" />
            <MetricTile label="审核归档" value="04" meta="核查与锁定" />
          </MetricStrip>
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
    <div className="space-y-4">
      <Scope1MobilePanel />
      <Scope1StationaryPanel />
      <Scope1RefrigerantPanel />
    </div>
  )
}

export function Scope2AccountingPanel() {
  return (
    <div className="space-y-4">
      <Scope2RecordsPanel defaultSourceKind="all" />
      <div className="grid gap-4 md:grid-cols-3">
        <EntryCard title="账单补录" description="人工电费账单作为电表聚合缺失时的辅助核算来源。" to="/carbon-mgmt/scope2-bill" actionLabel="进入账单补录" />
        <EntryCard title="外购热/汽/冷" description="维护外购热力、蒸汽和冷量数据，纳入范围2核算。" to="/carbon-mgmt/scope2-purchased-energy" actionLabel="进入填报" />
        <EntryCard title="数据对账" description="按账期比较账单总量与电表月聚合总量，排查差异和缺失点位。" to="/carbon-mgmt/scope2-reconciliation" actionLabel="进入数据对账" />
      </div>
    </div>
  )
}

export function Scope3AccountingPanel() {
  return (
    <div className="space-y-4">
      <Scope3WastePanel />
      <Scope3TransportPanel />
    </div>
  )
}

export { CarbonAccountingResultsPanel, PendingReviewPanel }

function Scope1MobilePanel() {
  return (
    <ScopeRecordPage
      embedded
      title="[范围1] 移动源燃烧"
      description="移动源燃烧数据填报、核算与审核流转。"
      endpoint="/api/carbon/scope1-mobile-combustion"
      queryKey={["carbon-mgmt", "scope1-mobile", "list"]}
      searchPlaceholder="搜索：资产名称/燃料类型/单位…"
      columns={[
        { key: "record_date", label: "日期" },
        { key: "asset_name", label: "资产名称" },
        { key: "fuel_type", label: "燃料类型" },
        { key: "amount", label: "用量", align: "right" },
        { key: "unit", label: "单位" },
      ]}
      fields={[
        { name: "record_date", label: "记录日期", type: "date", required: true },
        { name: "asset_name", label: "资产/车辆名称", placeholder: "例如：叉车/货车" },
        {
          name: "fuel_type",
          label: "燃料类型",
          type: "select",
          required: true,
          options: [
            { label: "柴油", value: "diesel" },
            { label: "汽油", value: "gasoline" },
            { label: "LNG", value: "lng" },
            { label: "CNG", value: "cng" },
          ],
        },
        { name: "amount", label: "用量", type: "number", required: true },
        { name: "unit", label: "单位", required: true, placeholder: "L/kg/m3" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}

function Scope1StationaryPanel() {
  return (
    <ScopeRecordPage
      embedded
      title="[范围1] 固定源燃烧"
      description="固定源燃烧数据填报、核算与审核流转。"
      endpoint="/api/carbon/scope1-stationary-combustion"
      queryKey={["carbon-mgmt", "scope1-stationary", "list"]}
      searchPlaceholder="搜索：设施名称/燃料类型/单位…"
      columns={[
        { key: "facility_name", label: "设施名称" },
        { key: "period_start", label: "开始日期" },
        { key: "period_end", label: "结束日期" },
        { key: "fuel_type", label: "燃料类型" },
        { key: "amount", label: "用量", align: "right" },
        { key: "unit", label: "单位" },
      ]}
      fields={[
        { name: "facility_name", label: "设施名称", required: true, placeholder: "例如：锅炉/发电机" },
        { name: "period_start", label: "开始日期", type: "date", required: true },
        { name: "period_end", label: "结束日期", type: "date", required: true },
        {
          name: "fuel_type",
          label: "燃料类型",
          type: "select",
          required: true,
          options: [
            { label: "柴油", value: "diesel" },
            { label: "汽油", value: "gasoline" },
            { label: "LNG", value: "lng" },
            { label: "CNG", value: "cng" },
            { label: "天然气", value: "natural_gas" },
          ],
        },
        { name: "amount", label: "用量", type: "number", required: true },
        { name: "unit", label: "单位", required: true, placeholder: "L/kg/m3" },
        { name: "meter_reading_start", label: "读数（开始）", type: "number" },
        { name: "meter_reading_end", label: "读数（结束）", type: "number" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}

function Scope1RefrigerantPanel() {
  return (
    <ScopeRecordPage
      embedded
      title="[范围1] 制冷剂逸散"
      description="制冷剂填充、泄漏数据填报、核算与审核流转。"
      endpoint="/api/carbon/scope1-refrigerant-leak"
      queryKey={["carbon-mgmt", "scope1-refrigerant", "list"]}
      searchPlaceholder="搜索：设备名称/制冷剂类型/类型…"
      columns={[
        { key: "fill_date", label: "日期" },
        { key: "device_name", label: "设备名称" },
        { key: "refrigerant_type", label: "制冷剂类型" },
        { key: "amount_kg", label: "数量(kg)", align: "right" },
        { key: "leak_type", label: "类型" },
      ]}
      fields={[
        { name: "fill_date", label: "填充/泄漏日期", type: "date", required: true },
        { name: "device_name", label: "设备名称", placeholder: "例如：冷库机组" },
        { name: "refrigerant_type", label: "制冷剂类型", required: true, placeholder: "例如：R410A" },
        { name: "amount_kg", label: "数量(kg)", type: "number", required: true },
        {
          name: "leak_type",
          label: "类型",
          type: "select",
          required: true,
          options: [
            { label: "填充", value: "fill" },
            { label: "泄漏", value: "leak" },
            { label: "维修补充", value: "repair" },
          ],
        },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}

function Scope3WastePanel() {
  return (
    <ScopeRecordPage
      embedded
      title="[范围3] 废弃物处理"
      description="废弃物处理数据填报、核算与审核流转。"
      endpoint="/api/carbon/scope3-waste-disposal"
      queryKey={["carbon-mgmt", "scope3-waste", "list"]}
      searchPlaceholder="搜索：类别/处理方式/处置方…"
      columns={[
        { key: "date", label: "日期" },
        { key: "category", label: "类别" },
        { key: "weight_ton", label: "重量(吨)", align: "right" },
        { key: "treatment_method", label: "处理方式" },
        { key: "vendor_name", label: "处置方" },
      ]}
      fields={[
        { name: "date", label: "日期", type: "date", required: true },
        { name: "category", label: "类别", required: true, placeholder: "例如：生活垃圾/包装物" },
        { name: "weight_ton", label: "重量(吨)", type: "number", required: true },
        {
          name: "treatment_method",
          label: "处理方式",
          type: "select",
          required: true,
          options: [
            { label: "焚烧", value: "incineration" },
            { label: "填埋", value: "landfill" },
            { label: "回收", value: "recycle" },
            { label: "堆肥", value: "compost" },
          ],
        },
        { name: "vendor_name", label: "供应商/处置方" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}

function Scope3TransportPanel() {
  return (
    <ScopeRecordPage
      embedded
      title="[范围3] 外购运输"
      description="外购运输数据填报、核算与审核流转。"
      endpoint="/api/carbon/scope3-third-party-transport"
      queryKey={["carbon-mgmt", "scope3-transport", "list"]}
      searchPlaceholder="搜索：运单号/起点/终点/车辆类型…"
      columns={[
        { key: "waybill_no", label: "运单号" },
        { key: "origin", label: "起点" },
        { key: "destination", label: "终点" },
        { key: "vehicle_type", label: "车辆类型" },
        { key: "distance_km", label: "距离(km)", align: "right" },
        { key: "load_ton", label: "载重(吨)", align: "right" },
      ]}
      fields={[
        { name: "waybill_no", label: "运单号", required: true },
        { name: "origin", label: "起点", required: true },
        { name: "destination", label: "终点", required: true },
        { name: "vehicle_type", label: "车辆类型", required: true },
        { name: "distance_km", label: "距离(km)", type: "number", required: true },
        { name: "load_ton", label: "载重(吨)", type: "number", required: true },
        { name: "fuel_amount", label: "燃料用量", type: "number" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}

function EntryCard({
  title,
  description,
  actionLabel,
  to,
}: {
  title: string
  description: string
  actionLabel: string
  to: "/carbon-mgmt/scope2-bill" | "/carbon-mgmt/scope2-purchased-energy" | "/carbon-mgmt/scope2-reconciliation"
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild>
          <Link to={to}>{actionLabel}</Link>
        </Button>
      </CardContent>
    </Card>
  )
}
