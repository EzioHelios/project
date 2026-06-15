import { createFileRoute } from "@tanstack/react-router"

import { ScopeRecordPage } from "@/components/carbon/scope-record-page"

type Scope1Stationary = {
  id: number
  facility_name: string
  period_start: string
  period_end: string
  fuel_type: string
  amount: string | number
  unit: string
  status?: string
}

export const Route = createFileRoute("/_app/carbon-mgmt/scope1-stationary")({
  component: Scope1StationaryPage,
})

function Scope1StationaryPage() {
  const queryKey = ["carbon-mgmt", "scope1-stationary", "list"]
  return (
    <ScopeRecordPage<Scope1Stationary>
      title="[范围1] 固定源燃烧"
      endpoint="/api/carbon/scope1-stationary-combustion"
      queryKey={queryKey}
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
        { name: "unit", label: "单位", required: true, placeholder: "L/kg/m³" },
        { name: "meter_reading_start", label: "读数（开始）", type: "number" },
        { name: "meter_reading_end", label: "读数（结束）", type: "number" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}
