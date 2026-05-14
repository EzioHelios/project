import { createFileRoute } from "@tanstack/react-router"

import { ScopeRecordPage } from "@/components/carbon/scope-record-page"

type Scope3Waste = {
  id: number
  date: string
  category: string
  weight_ton: string | number
  treatment_method: string
  vendor_name?: string | null
  status?: string
}

export const Route = createFileRoute("/_app/carbon-mgmt/scope3-waste")({
  component: Scope3WastePage,
})

function Scope3WastePage() {
  return (
    <ScopeRecordPage<Scope3Waste>
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
