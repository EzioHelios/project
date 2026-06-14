import { createFileRoute } from "@tanstack/react-router"

import { EnergyConsumptionPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/consumption")({
  component: EnergyConsumptionPage,
})

function EnergyConsumptionPage() {
  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <EnergyConsumptionPanel />
    </PageContainer>
  )
}
