import { createFileRoute } from "@tanstack/react-router"

import { ScopeRecordPage } from "@/components/carbon/scope-record-page"

type Scope1Refrigerant = {
  id: number
  fill_date: string
  device_name?: string | null
  refrigerant_type: string
  amount_kg: string | number
  leak_type: string
  status?: string
}

export const Route = createFileRoute("/_app/carbon-mgmt/scope1-refrigerant")({
  component: Scope1RefrigerantPage,
})

function Scope1RefrigerantPage() {
  return (
    <ScopeRecordPage<Scope1Refrigerant>
      title="[范围1] 制冷剂逸散"
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
