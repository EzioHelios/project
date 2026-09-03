import { createFileRoute } from "@tanstack/react-router"

import { InventoryReportLedgerPage } from "@/components/carbon/inventory-report-management"

export const Route = createFileRoute("/_app/carbon/organization/reports/")({
  component: InventoryReportLedgerPage,
})
