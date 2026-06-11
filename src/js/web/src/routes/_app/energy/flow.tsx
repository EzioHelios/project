import { createFileRoute } from "@tanstack/react-router"

import { EnergyFlowPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/flow")({
  component: EnergyFlowPage,
})

function EnergyFlowPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="能流分析" description="展示能源输入、分配、利用链路，并通过节点和关键链路钻取能耗来源。" />
      <EnergyFlowPanel />
    </PageContainer>
  )
}
