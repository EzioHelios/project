import { createFileRoute } from "@tanstack/react-router"

import { EnergyBalancePanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/balance")({
  component: EnergyBalancePage,
})

function EnergyBalancePage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="能效平衡与优化" description="用平衡表、损耗诊断和整改入口定位能效问题，支撑后续优化闭环。" />
      <EnergyBalancePanel />
    </PageContainer>
  )
}
