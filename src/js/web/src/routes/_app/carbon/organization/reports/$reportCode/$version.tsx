import { createFileRoute } from "@tanstack/react-router"

import { InventoryReportDetailPage } from "@/components/carbon/inventory-report-management"

export const Route = createFileRoute("/_app/carbon/organization/reports/$reportCode/$version")({
  component: ReportRoute,
})

function ReportRoute() {
  const { reportCode, version } = Route.useParams()
  return <InventoryReportDetailPage reportCode={reportCode} version={Number(version)} />
}
