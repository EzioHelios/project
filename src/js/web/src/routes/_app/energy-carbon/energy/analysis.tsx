import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/energy-carbon/energy/analysis")({
  beforeLoad: () => {
    throw redirect({ to: "/energy/analysis" })
  },
  component: EmptyRoute,
})

function EmptyRoute() {
  return null
}
