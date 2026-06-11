import { createFileRoute, Outlet } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon")({
  component: CarbonLayout,
})

function CarbonLayout() {
  return <Outlet />
}

export default CarbonLayout
