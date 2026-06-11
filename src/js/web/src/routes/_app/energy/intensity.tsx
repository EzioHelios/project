import { createFileRoute } from "@tanstack/react-router"

import { EnergyIntensityPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/intensity")({
  component: EnergyIntensityPage,
})

function EnergyIntensityPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="能源消费量和强度计算" description="汇总能源消费量、折标口径和强度指标，明确计算结果来自哪些账本与采集来源。" />
      <EnergyIntensityPanel />
    </PageContainer>
  )
}
