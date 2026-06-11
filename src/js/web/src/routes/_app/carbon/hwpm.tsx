import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon/hwpm")({
  beforeLoad: () => {
    throw redirect({ to: "/bigscreen/overview" })
  },
})
