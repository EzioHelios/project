import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { CarbonAccountingResultsPanel } from "@/components/carbon/accounting-panels"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/ledger")({
  component: CarbonLedgerPage,
})

function CarbonLedgerPage() {
  return (
    <PageContainer className="flex-1" maxWidth="full">
      <AdminPageHeader title="碳排放台账" />
      <CarbonAccountingResultsPanel />
    </PageContainer>
  )
}
