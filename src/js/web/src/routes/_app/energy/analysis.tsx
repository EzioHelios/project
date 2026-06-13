import { createFileRoute } from "@tanstack/react-router"
import { AdminPageHeader } from "@/components/admin-ui"
import { EnergyAnalysisPanel } from "@/components/carbon/energy-guide-pages"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/analysis")({
  component: EnergyAnalysisPage,
})

function EnergyAnalysisPage() {
  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="4xl">
      <AdminPageHeader title="用能分析" />
      <EnergyAnalysisPanel />
    </PageContainer>
  )
}
