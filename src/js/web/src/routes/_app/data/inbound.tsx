import { createFileRoute } from "@tanstack/react-router"
import { ReadonlyLedgerPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/inbound")({
  component: InboundPage,
})

function InboundPage() {
  return (
    <ReadonlyLedgerPage
      title="入库管理"
      description="查看外部系统同步的入库流水，不提供手工新增或编辑。"
      endpoint="/api/data/in-money"
      queryKey={["data", "in-money"]}
      columns={[
        { key: "rkdbh", label: "入库单号" },
        { key: "gysmc", label: "供应商" },
        { key: "wlbh", label: "物料编号" },
        { key: "wlms", label: "物料描述" },
        { key: "shsl", label: "数量" },
        { key: "shje", label: "金额" },
      ]}
    />
  )
}
