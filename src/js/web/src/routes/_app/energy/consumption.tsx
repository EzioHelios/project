import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { EnergyConsumptionPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/consumption")({
  component: EnergyConsumptionPage,
})

function EnergyConsumptionPage() {
  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <EnergyConsumptionPanel header={<AdminPageHeader title="能耗查询" />} />
    </PageContainer>
  )
}
