import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { EnergyFlowPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/flow")({
  component: EnergyFlowPage,
})

function EnergyFlowPage() {
  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="4xl">
      <AdminPageHeader title="能流分析" />
      <EnergyFlowPanel />
    </PageContainer>
  )
}
