import { createFileRoute } from "@tanstack/react-router"

import { Scope2RecordsPanel } from "@/components/carbon/scope2-records-panel"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon-mgmt/scope2-records")({
  component: Scope2RecordsPage,
})

function Scope2RecordsPage() {
  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="碳核算模型" title="[范围2] 用电核算记录" description="统一查看人工账单与电表月聚合形成的范围2用电核算记录。" />
      <PageSection>
        <Scope2RecordsPanel defaultSourceKind="meter_aggregate" />
      </PageSection>
    </PageContainer>
  )
}
