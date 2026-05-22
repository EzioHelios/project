import { createFileRoute } from "@tanstack/react-router"
import { DeviceTypesPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/device-types")({
  component: DeviceTypesPage,
})
