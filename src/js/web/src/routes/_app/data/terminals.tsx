import { createFileRoute } from "@tanstack/react-router"
import { TerminalsWorkbenchPage } from "@/components/platform/master-data-workbench"

export const Route = createFileRoute("/_app/data/terminals")({
  component: TerminalsWorkbenchPage,
})
