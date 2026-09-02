import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/carbon-mgmt/")({
  beforeLoad: () => {
    throw redirect({ to: "/carbon-mgmt/workbench" })
  },
})
