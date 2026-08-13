import type { PageImportField } from "@/components/admin-ui/page-import-panel"

export const scope2BillImportFields: PageImportField[] = [
  { key: "source_record_id", label: "来源记录ID", required: true },
  { key: "account_number", label: "户号", required: true },
  { key: "billing_month", label: "账期", required: true },
  { key: "total_kwh", label: "总电量(kWh)", required: true, type: "number" },
  { key: "amount_cny", label: "金额(元)", type: "number" },
]
