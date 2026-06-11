import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon-mgmt/verification")({
  beforeLoad: () => {
    throw redirect({ to: "/carbon/verification" })
  },
})
