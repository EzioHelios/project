import { createFileRoute, Outlet } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon-mgmt")({
  component: CarbonMgmtLegacyLayout,
})

function CarbonMgmtLegacyLayout() {
  return <Outlet />
}

export default CarbonMgmtLegacyLayout
