import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { SupplyChainCarbonPanel } from "@/components/carbon/supply-chain-carbon-panel"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/supply-chain")({
  component: SupplyChainCarbonPage,
})

function SupplyChainCarbonPage() {
  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="full">
      <AdminPageHeader title="供应链碳管理" />
      <SupplyChainCarbonPanel />
    </PageContainer>
  )
}
