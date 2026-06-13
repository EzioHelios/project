import { createFileRoute } from "@tanstack/react-router"

import { CarbonAssetsPanel } from "@/components/carbon/carbon-assets-panel"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/assets")({
  component: CarbonAssetsPage,
})

function CarbonAssetsPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="full">
      <PageHeader eyebrow="碳排放管理" title="碳资产管理" />
      <CarbonAssetsPanel />
    </PageContainer>
  )
}
