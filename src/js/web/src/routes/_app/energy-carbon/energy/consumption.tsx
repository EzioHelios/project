import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/energy-carbon/energy/consumption")({
  beforeLoad: () => {
    throw redirect({ to: "/energy/consumption" })
  },
  component: EmptyRoute,
})

function EmptyRoute() {
  return null
}
