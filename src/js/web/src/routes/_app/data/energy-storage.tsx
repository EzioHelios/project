import { createFileRoute } from "@tanstack/react-router"
import { EnergyStoragePage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/energy-storage")({
  component: EnergyStoragePage,
})
