import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon/page4")({
  beforeLoad: () => {
    throw redirect({ to: "/bigscreen/carbon" })
  },
})
