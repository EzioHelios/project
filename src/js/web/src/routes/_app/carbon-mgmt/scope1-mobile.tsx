import { createFileRoute } from "@tanstack/react-router"

import { ScopeRecordPage } from "@/components/carbon/scope-record-page"

type Scope1Mobile = {
  id: number
  record_date: string
  asset_name?: string | null
  fuel_type: string
  amount: string | number
  unit: string
  status?: string
  computed_co2e?: number | null
}

export const Route = createFileRoute("/_app/carbon-mgmt/scope1-mobile")({
  component: Scope1MobilePage,
})

function Scope1MobilePage() {
  return (
    <ScopeRecordPage<Scope1Mobile>
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
        { name: "unit", label: "单位", required: true, placeholder: "L/kg/m³" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}
