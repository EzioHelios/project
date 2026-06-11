import { createFileRoute } from "@tanstack/react-router"

import { EnergyConsumptionPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/consumption")({
  component: EnergyConsumptionPage,
})

function EnergyConsumptionPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="能耗查询" description="按区域、设备、能源来源和账期查询能耗原始记录，支撑后续计算、分析和核查。" />
      <EnergyConsumptionPanel />
    </PageContainer>
  )
}
