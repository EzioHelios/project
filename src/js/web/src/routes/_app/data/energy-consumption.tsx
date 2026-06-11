import { createFileRoute } from "@tanstack/react-router"

import { ReadonlyLedgerPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/energy-consumption")({
  component: EnergyConsumptionFactsPage,
})

function EnergyConsumptionFactsPage() {
  return (
    <ReadonlyLedgerPage
      title="能源消费明细查询"
      description="只读查询统一能源消费事实视图，按源记录追溯 Scope1 燃料、Scope2 外购电力和外购热力/蒸汽/冷量。"
      endpoint="/api/energy/consumption/facts"
      queryKey={["data", "energy-consumption", "facts"]}
      columns={[
        { key: "source_record_type", label: "源记录类型" },
        { key: "source_record_id", label: "源记录ID" },
        { key: "scope", label: "Scope" },
        { key: "energy_type_name", label: "能源品种" },
        { key: "original_amount", label: "原始量" },
        { key: "original_unit", label: "单位" },
        { key: "tce_amount", label: "折标煤(tce)" },
        { key: "period_start", label: "开始日期" },
        { key: "period_end", label: "结束日期" },
        { key: "area_name", label: "区域" },
        { key: "facility_or_device_name", label: "设施/设备" },
        { key: "status", label: "状态" },
      ]}
    />
  )
}
