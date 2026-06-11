import { createFileRoute } from "@tanstack/react-router"

import { EnergyAnalysisPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/analysis")({
  component: EnergyAnalysisPage,
})

function EnergyAnalysisPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="能源消费分析与用能策略推荐" description="围绕趋势、结构、异常排行和策略建议组织分析，发现问题后回到底座台账或告警处置。" />
      <EnergyAnalysisPanel />
    </PageContainer>
  )
}
