import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/energy/")({
  beforeLoad: () => {
    throw redirect({ to: "/energy/consumption" })
  },
})
