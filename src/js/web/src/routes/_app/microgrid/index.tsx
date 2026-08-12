import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/microgrid/")({
  beforeLoad: () => {
    throw redirect({ to: "/microgrid/overview" })
  },
})
