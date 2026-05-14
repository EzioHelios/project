import { createFileRoute } from "@tanstack/react-router"
import { ReadonlyLedgerPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/meter")({
  component: MeterPage,
})

function MeterPage() {
  return (
    <ReadonlyLedgerPage
      title="电表电量"
      description="查看采集生成的电表读数明细，支持关键字查询和详情查看。"
      endpoint="/api/data/ammeter-values"
      queryKey={["data", "ammeter-values"]}
      columns={[
        { key: "reading_time", label: "读数时间" },
        { key: "ammeter_name", label: "电表" },
        { key: "area_name", label: "区域" },
        { key: "zygdn", label: "总有功电能" },
        { key: "zygdnsz", label: "总有功电能数值" },
      ]}
    />
  )
}
