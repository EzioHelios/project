import { createFileRoute } from "@tanstack/react-router"

import { ScopeRecordPage } from "@/components/carbon/scope-record-page"

type Scope2PurchasedEnergy = {
  id: number
  energy_type_code: string
  energy_type_name?: string | null
  supplier_name?: string | null
  period_start: string
  period_end: string
  amount: string | number
  unit: string
  tce_amount?: string | number | null
  area_name?: string | null
  facility_name?: string | null
  status?: string
}

export const Route = createFileRoute("/_app/carbon-mgmt/scope2-purchased-energy")({
  component: Scope2PurchasedEnergyPage,
})

function Scope2PurchasedEnergyPage() {
  return (
    <ScopeRecordPage<Scope2PurchasedEnergy>
      title="[范围2] 外购热力/蒸汽/冷量"
      description="维护 Scope2 外购热力、外购蒸汽、外购冷量业务数据，作为能耗查询聚合页的底层来源。"
      endpoint="/api/carbon/scope2-purchased-energy"
      queryKey={["carbon-mgmt", "scope2-purchased-energy", "list"]}
      searchPlaceholder="搜索：能源品种/供应商/区域/设施…"
      columns={[
        { key: "energy_type_name", label: "能源品种" },
        { key: "supplier_name", label: "供应商" },
        { key: "period_start", label: "开始日期" },
        { key: "period_end", label: "结束日期" },
        { key: "amount", label: "消费量", align: "right", render: (row) => `${row.amount ?? "-"} ${row.unit ?? ""}` },
        { key: "tce_amount", label: "折标煤(tce)", align: "right" },
        { key: "area_name", label: "区域" },
        { key: "facility_name", label: "设施/系统" },
      ]}
      fields={[
        {
          name: "energy_type_code",
          label: "能源品种",
          type: "select",
          required: true,
          options: [
            { label: "外购热力", value: "purchased_heat" },
            { label: "外购蒸汽", value: "purchased_steam" },
            { label: "外购冷量", value: "purchased_cooling" },
          ],
        },
        { name: "supplier_name", label: "供应商", placeholder: "例如：园区供热公司" },
        { name: "period_start", label: "开始日期", type: "date", required: true },
        { name: "period_end", label: "结束日期", type: "date", required: true },
        { name: "amount", label: "消费量", type: "number", required: true },
        { name: "unit", label: "原始单位", required: true, placeholder: "例如：GJ、t、MWh" },
        { name: "amount_cny", label: "金额(元)", type: "number" },
        { name: "area_id", label: "区域编码" },
        { name: "area_name", label: "区域名称" },
        { name: "facility_name", label: "设施/系统名称" },
        { name: "attachment", label: "附件地址" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}
