import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { CarbonAssetsPanel } from "@/components/carbon/carbon-assets-panel"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/assets")({
  component: CarbonAssetsPage,
})

function CarbonAssetsPage() {
  return (
    <PageContainer className="flex-1" maxWidth="full">
      <CarbonAssetsPanel header={<AdminPageHeader title="碳资产管理" />} />
    </PageContainer>
  )
}
