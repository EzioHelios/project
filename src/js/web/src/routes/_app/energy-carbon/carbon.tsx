import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/energy-carbon/carbon")({
  beforeLoad: () => {
    throw redirect({ to: "/carbon-mgmt/activities" })
  },
})
