import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { ClipboardCheck, Fuel, PlugZap, Truck } from "lucide-react"

import { type ApiEnvelope, fetchCarbonApi, LedgerTable } from "@/components/carbon/analytics-panels"
import { ScopeRecordPage } from "@/components/carbon/scope-record-page"
import { Scope2RecordsPanel } from "@/components/carbon/scope2-records-panel"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { PendingReviewPanel } from "@/routes/_app/carbon-mgmt/pending"

export function AccountingOverviewPanel() {
  const entries = [
    { label: "Scope1 填报", description: "移动源、固定源和制冷剂逸散活动数据。", icon: Fuel },
    { label: "Scope2 填报", description: "电表月聚合、账单补录和用电核算记录。", icon: PlugZap },
    { label: "Scope3 填报", description: "废弃物处理和外购运输活动数据。", icon: Truck },
    { label: "待审核", description: "集中处理已送审的各类核算记录。", icon: ClipboardCheck },
  ] as const

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <Card>
        <CardHeader>
          <CardTitle>核算业务闭环</CardTitle>
          <CardDescription>本页承载组织碳排放核算的业务动作：填报、核算、送审、审核和结果追踪。</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {entries.map((item) => (
            <div key={item.label} className="rounded-lg border border-border/60 bg-card/60 p-4">
              <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <item.icon className="h-5 w-5" />
              </div>
              <div className="text-sm font-medium">{item.label}</div>
              <div className="mt-1 text-xs leading-5 text-muted-foreground">{item.description}</div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>底座数据入口</CardTitle>
          <CardDescription>因子、设备和电表属于底座能力，从业务页跳转使用，不作为碳排放管理 Tab。</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2">
          <Button asChild variant="outline" className="justify-start">
            <Link to="/carbon-mgmt/factors">排放因子库</Link>
          </Button>
          <Button asChild variant="outline" className="justify-start">
            <Link to="/carbon-mgmt/calculation-factors">计算因子库</Link>
          </Button>
          <Button asChild variant="outline" className="justify-start">
            <Link to="/data/meter">电表电量台账</Link>
          </Button>
          <Button asChild variant="outline" className="justify-start">
            <Link to="/data/company">企业基本信息</Link>
          </Button>
        </CardContent>
      </Card>
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
      <div className="grid gap-4 md:grid-cols-2">
        <EntryCard title="账单补录" description="人工电费账单作为电表聚合缺失时的辅助核算来源。" to="/carbon-mgmt/scope2-bill" actionLabel="进入账单补录" />
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

export { PendingReviewPanel }

type CarbonRecordsPage = {
  items: Record<string, unknown>[]
}

export function CarbonAccountingResultsPanel() {
  const recordsQuery = useQuery<ApiEnvelope<CarbonRecordsPage>>({
    queryKey: ["energy-carbon", "carbon", "records"],
    queryFn: () => fetchCarbonApi<CarbonRecordsPage>("/api/energy-carbon/carbon/records?limit=200&offset=0"),
  })

  return (
    <LedgerTable
      title="核算结果账本"
      description="汇总 Scope1/2/3 已形成的组织碳排放核算结果，作为核查、报告和碳资产管理的结果来源。"
      rows={recordsQuery.data?.data.items ?? []}
      columns={[
        { key: "scope", label: "范围" },
        { key: "record_label", label: "记录类型" },
        { key: "display_name", label: "对象" },
        { key: "period", label: "期间" },
        { key: "source_kind", label: "来源" },
        { key: "activity_amount", label: "活动量", align: "right" },
        { key: "computed_co2e", label: "核算结果", align: "right" },
        { key: "status", label: "状态" },
      ]}
    />
  )
}

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
  to: "/carbon-mgmt/scope2-bill" | "/carbon-mgmt/scope2-reconciliation"
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
