import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon/assets/")({
  beforeLoad: () => {
    throw redirect({ to: "/carbon/assets/overview" })
  },
})
