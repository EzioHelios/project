import { createFileRoute } from "@tanstack/react-router"
import { DevicePointsPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/device-points")({
  component: DevicePointsPage,
})
