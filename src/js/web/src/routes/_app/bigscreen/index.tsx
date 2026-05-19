import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/bigscreen/")({
  beforeLoad: () => {
    throw redirect({ to: "/bigscreen/overview" })
  },
  component: () => null,
})
