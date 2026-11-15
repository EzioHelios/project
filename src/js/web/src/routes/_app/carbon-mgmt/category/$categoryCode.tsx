import { createFileRoute } from "@tanstack/react-router"

import { GhgActivityLedger, ghgLedgerSearchSchema } from "@/routes/_app/carbon-mgmt/activities"

export const Route = createFileRoute("/_app/carbon-mgmt/category/$categoryCode")({
  validateSearch: (search) => ghgLedgerSearchSchema.parse(search),
  component: GhgCategoryActivityPage,
})

function GhgCategoryActivityPage() {
  const { categoryCode } = Route.useParams()
  const { inventory, batch, record } = Route.useSearch()
  return <GhgActivityLedger key={categoryCode} fixedCategoryCode={categoryCode} initialInventoryCode={inventory} initialBatchCode={batch} initialRecordCode={record} />
}
