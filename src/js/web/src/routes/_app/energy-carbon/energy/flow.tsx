import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/energy-carbon/energy/flow")({
  beforeLoad: () => {
    throw redirect({ to: "/energy/flow" })
  },
  component: EmptyRoute,
})

function EmptyRoute() {
  return null
}
