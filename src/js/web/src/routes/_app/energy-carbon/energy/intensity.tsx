import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/energy-carbon/energy/intensity")({
  beforeLoad: () => {
    throw redirect({ to: "/energy/intensity" })
  },
  component: EmptyRoute,
})

function EmptyRoute() {
  return null
}
