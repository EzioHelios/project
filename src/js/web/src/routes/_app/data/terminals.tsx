import { createFileRoute } from "@tanstack/react-router"
import { TerminalsPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/terminals")({
  component: TerminalsPage,
})
