import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon/map")({
  beforeLoad: () => {
    throw redirect({ to: "/bigscreen/overview" })
  },
})
