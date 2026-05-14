import { createFileRoute } from "@tanstack/react-router"
import { MonitorAreaPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/monitor-area")({
  component: MonitorAreaPage,
})
