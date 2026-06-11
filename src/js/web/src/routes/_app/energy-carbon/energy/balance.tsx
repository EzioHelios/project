import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/energy-carbon/energy/balance")({
  beforeLoad: () => {
    throw redirect({ to: "/energy/balance" })
  },
  component: EmptyRoute,
})

function EmptyRoute() {
  return null
}
