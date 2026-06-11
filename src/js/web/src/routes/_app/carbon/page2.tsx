import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon/page2")({
  beforeLoad: () => {
    throw redirect({ to: "/bigscreen/intro" })
  },
})
