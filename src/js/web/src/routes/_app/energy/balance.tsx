import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { EnergyBalancePanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/balance")({
  component: EnergyBalancePage,
})

function EnergyBalancePage() {
  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <EnergyBalancePanel header={<AdminPageHeader title="能效平衡与优化" />} />
    </PageContainer>
  )
}
