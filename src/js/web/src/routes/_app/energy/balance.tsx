import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { EnergyBalancePanel } from "@/components/carbon/energy-balance-panel"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/balance")({
  component: EnergyBalancePage,
})

function EnergyBalancePage() {
  return (
    <PageContainer className="flex-1" maxWidth="full">
      <EnergyBalancePanel header={<AdminPageHeader title="能量平衡" />} />
    </PageContainer>
  )
}
