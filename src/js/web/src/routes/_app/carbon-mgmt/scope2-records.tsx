import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { Scope2RecordsPanel } from "@/components/carbon/scope2-records-panel"
import { PageContainer, PageSection } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon-mgmt/scope2-records")({
  component: Scope2RecordsPage,
})

function Scope2RecordsPage() {
  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="[范围2] 用电核算记录" />
      <PageSection>
        <Scope2RecordsPanel defaultSourceKind="meter_aggregate" />
      </PageSection>
    </PageContainer>
  )
}
