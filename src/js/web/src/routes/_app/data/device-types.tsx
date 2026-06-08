import { createFileRoute } from "@tanstack/react-router"
import { DeviceTypesWorkbenchPage } from "@/components/platform/master-data-workbench"

export const Route = createFileRoute("/_app/data/device-types")({
  component: DeviceTypesWorkbenchPage,
})
