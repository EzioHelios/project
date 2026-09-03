import { createFileRoute, Outlet } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon/organization/reports")({
  component: ReportsRoute,
})

function ReportsRoute() {
  return <Outlet />
}
