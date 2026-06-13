import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { EnergyIntensityPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/intensity")({
  component: EnergyIntensityPage,
})

function EnergyIntensityPage() {
  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="4xl">
      <AdminPageHeader title="能源消费量和强度计算" />
      <EnergyIntensityPanel />
    </PageContainer>
  )
}
