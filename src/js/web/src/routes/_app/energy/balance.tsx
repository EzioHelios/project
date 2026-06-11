import { createFileRoute } from "@tanstack/react-router"

import { EnergyBalancePanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/balance")({
  component: EnergyBalancePage,
})

function EnergyBalancePage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="能效平衡与优化" />
      <EnergyBalancePanel />
    </PageContainer>
  )
}
