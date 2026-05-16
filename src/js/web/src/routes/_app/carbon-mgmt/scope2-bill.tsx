import { createFileRoute } from "@tanstack/react-router"

import { ScopeRecordPage } from "@/components/carbon/scope-record-page"

type Scope2Bill = {
  id: number
  account_number: string
  billing_month: string
  total_kwh: string | number
  amount_cny?: string | number | null
  status?: string
  source_kind?: string
}

export const Route = createFileRoute("/_app/carbon-mgmt/scope2-bill")({
  component: Scope2BillPage,
})

function Scope2BillPage() {
  return (
    <ScopeRecordPage<Scope2Bill>
      title="[范围2] 账单补录"
      description="维护人工电费账单补录数据，作为范围2用电核算的辅助来源。"
      endpoint="/api/carbon/scope2-electricity-bill"
      queryKey={["carbon-mgmt", "scope2-bill", "list"]}
      searchPlaceholder="搜索：户号/账期…"
      columns={[
        { key: "account_number", label: "户号" },
        { key: "billing_month", label: "账期" },
        { key: "total_kwh", label: "总电量(kWh)", align: "right" },
        { key: "amount_cny", label: "金额(元)", align: "right" },
        { key: "source_kind", label: "来源" },
      ]}
      fields={[
        { name: "account_number", label: "户号", required: true, placeholder: "例如：电力户号/表号" },
        { name: "billing_month", label: "账期（月）", required: true, placeholder: "例如：2026-03" },
        { name: "total_kwh", label: "总电量(kWh)", type: "number", required: true },
        { name: "amount_cny", label: "金额(元)", type: "number" },
        { name: "peak_kwh", label: "峰(kWh)", type: "number" },
        { name: "flat_kwh", label: "平(kWh)", type: "number" },
        { name: "valley_kwh", label: "谷(kWh)", type: "number" },
        { name: "remark", label: "备注", type: "textarea" },
      ]}
    />
  )
}
