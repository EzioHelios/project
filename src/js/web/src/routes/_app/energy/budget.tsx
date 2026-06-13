import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { EnergyBudgetPanel } from "@/components/carbon/energy-budget-panel"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/budget")({
  component: EnergyBudgetPage,
})

function EnergyBudgetPage() {
  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="4xl">
      <AdminPageHeader title="用能与碳排放预算管理" />
      <EnergyBudgetPanel />
    </PageContainer>
  )
}
