import { createFileRoute } from "@tanstack/react-router"

import { ProductFootprintPanel } from "@/components/carbon/product-footprint-panel"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/product-footprint")({
  component: ProductFootprintPage,
})

function ProductFootprintPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="full">
      <PageHeader eyebrow="碳排放管理" title="产品碳足迹核算" />
      <ProductFootprintPanel />
    </PageContainer>
  )
}
