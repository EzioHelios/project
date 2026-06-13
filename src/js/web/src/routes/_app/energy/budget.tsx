import { createFileRoute } from "@tanstack/react-router"

import { EnergyBudgetPanel } from "@/components/carbon/energy-budget-panel"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/budget")({
  component: EnergyBudgetPage,
})

function EnergyBudgetPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="用能与碳排放预算管理" />
      <EnergyBudgetPanel />
    </PageContainer>
  )
}
