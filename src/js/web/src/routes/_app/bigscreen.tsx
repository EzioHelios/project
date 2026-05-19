import { createFileRoute } from "@tanstack/react-router"

import { BigscreenLayout } from "@/components/bigscreen/layout"

export const Route = createFileRoute("/_app/bigscreen")({
  component: BigscreenLayout,
})
