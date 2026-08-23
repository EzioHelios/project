import type { PageImportField } from "@/components/admin-ui"

export const scope2BillImportFields: PageImportField[] = [
  { key: "source_record_id", label: "来源记录ID", required: true, aliases: ["sourceRecordId"] },
  { key: "account_number", label: "户号", required: true, aliases: ["accountNumber"] },
  { key: "billing_month", label: "账期", required: true, aliases: ["billingMonth"] },
  { key: "total_kwh", label: "总电量(kWh)", required: true, type: "number", aliases: ["totalKwh"] },
  { key: "amount_cny", label: "金额(元)", type: "number", aliases: ["amountCny"] },
]
