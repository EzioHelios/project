import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { ProductFootprintPanel } from "@/components/carbon/product-footprint-panel"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/product-footprint")({
  component: ProductFootprintPage,
})

function ProductFootprintPage() {
  return (
    <PageContainer className="flex-1" maxWidth="full">
      <ProductFootprintPanel header={<AdminPageHeader title="产品碳足迹核算" />} />
    </PageContainer>
  )
}
