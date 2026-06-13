import { createFileRoute } from "@tanstack/react-router"

import { SupplyChainCarbonPanel } from "@/components/carbon/supply-chain-carbon-panel"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/supply-chain")({
  component: SupplyChainCarbonPage,
})

function SupplyChainCarbonPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="full">
      <PageHeader eyebrow="碳排放管理" title="供应链碳管理" />
      <SupplyChainCarbonPanel />
    </PageContainer>
  )
}
