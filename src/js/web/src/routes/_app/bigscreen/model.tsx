import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/bigscreen/model")({
  component: BigscreenModelPage,
})

function BigscreenModelPage() {
  return null
}
