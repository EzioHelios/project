import { createFileRoute } from "@tanstack/react-router"

import { EnergyAnalysisPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/analysis")({
  component: EnergyAnalysisPage,
})

function EnergyAnalysisPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="能源消费分析与用能策略推荐" />
      <EnergyAnalysisPanel />
    </PageContainer>
  )
}
