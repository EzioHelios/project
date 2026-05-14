import { createFileRoute } from "@tanstack/react-router"
import { ReadonlyLedgerPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/outbound")({
  component: OutboundPage,
})

function OutboundPage() {
  return (
    <ReadonlyLedgerPage
      title="出库管理"
      description="查看外部系统同步的出库流水，不提供手工新增或编辑。"
      endpoint="/api/data/out-money"
      queryKey={["data", "out-money"]}
      columns={[
        { key: "ckdbh", label: "出库单号" },
        { key: "xmmc", label: "项目名称" },
        { key: "wlbm", label: "物料编码" },
        { key: "wlms", label: "物料描述" },
        { key: "sfsl", label: "数量" },
        { key: "je", label: "金额" },
      ]}
    />
  )
}
