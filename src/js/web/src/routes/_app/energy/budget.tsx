import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { EnergyBudgetPanel } from "@/components/carbon/energy-budget-panel"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/budget")({
  component: EnergyBudgetPage,
})

function EnergyBudgetPage() {
  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <EnergyBudgetPanel header={<AdminPageHeader title="能碳预算" />} />
    </PageContainer>
  )
}
