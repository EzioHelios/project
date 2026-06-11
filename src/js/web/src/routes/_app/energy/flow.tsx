import { createFileRoute } from "@tanstack/react-router"

import { EnergyFlowPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/flow")({
  component: EnergyFlowPage,
})

function EnergyFlowPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="能流分析" />
      <EnergyFlowPanel />
    </PageContainer>
  )
}
