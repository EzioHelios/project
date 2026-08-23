import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon/")({
  beforeLoad: () => {
    throw redirect({
      to: "/carbon/organization/overview",
      search: { scope2: "location", grain: "month", page: 1, pageSize: 25, sortBy: "period_start", sortOrder: "desc" },
    })
  },
})
