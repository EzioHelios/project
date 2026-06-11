import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon/page3")({
  beforeLoad: () => {
    throw redirect({ to: "/bigscreen/power" })
  },
})
