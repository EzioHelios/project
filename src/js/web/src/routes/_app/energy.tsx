import { createFileRoute, Outlet } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/energy")({
  component: EnergyLayout,
})

function EnergyLayout() {
  return <Outlet />
}

export default EnergyLayout
