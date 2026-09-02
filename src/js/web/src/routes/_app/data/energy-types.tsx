import { createFileRoute } from "@tanstack/react-router"
import { EnergyTypesPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/energy-types")({
  component: EnergyTypesPage,
})
