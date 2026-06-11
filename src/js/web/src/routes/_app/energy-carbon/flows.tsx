import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/energy-carbon/flows")({
  beforeLoad: () => {
    throw redirect({ to: "/energy/flow" })
  },
})
