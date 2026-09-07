import { createFileRoute } from "@tanstack/react-router"

import { GhgActivityLedger } from "@/routes/_app/carbon-mgmt/activities"

export const Route = createFileRoute("/_app/carbon-mgmt/category/$categoryCode")({
  component: GhgCategoryActivityPage,
})

function GhgCategoryActivityPage() {
  const { categoryCode } = Route.useParams()
  return <GhgActivityLedger fixedCategoryCode={categoryCode} />
}
