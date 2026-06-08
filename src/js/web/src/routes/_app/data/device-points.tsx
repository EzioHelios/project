import { createFileRoute } from "@tanstack/react-router"
import { DevicePointsWorkbenchPage } from "@/components/platform/master-data-workbench"

export const Route = createFileRoute("/_app/data/device-points")({
  component: DevicePointsWorkbenchPage,
})
