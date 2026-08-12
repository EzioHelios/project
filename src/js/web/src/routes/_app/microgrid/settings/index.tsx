import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/microgrid/settings/")({
  beforeLoad: () => {
    throw redirect({ to: "/microgrid/settings/assets" })
  },
})
