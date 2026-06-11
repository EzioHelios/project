import { createFileRoute } from "@tanstack/react-router"

import { EnergyIntensityPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/intensity")({
  component: EnergyIntensityPage,
})

function EnergyIntensityPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="能源消费量和强度计算" />
      <EnergyIntensityPanel />
    </PageContainer>
  )
}
