import { createFileRoute, Outlet } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/energy-carbon")({
  component: EnergyCarbonLegacyLayout,
})

function EnergyCarbonLegacyLayout() {
  return <Outlet />
}

export default EnergyCarbonLegacyLayout
