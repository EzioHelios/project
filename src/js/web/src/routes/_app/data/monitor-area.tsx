import { createFileRoute } from "@tanstack/react-router"
import { MonitorAreaWorkbenchPage } from "@/components/platform/master-data-workbench"

export const Route = createFileRoute("/_app/data/monitor-area")({
  component: MonitorAreaWorkbenchPage,
})
