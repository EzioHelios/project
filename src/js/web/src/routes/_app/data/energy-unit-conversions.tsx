import { createFileRoute } from "@tanstack/react-router"
import { EnergyUnitConversionsPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/energy-unit-conversions")({
  component: EnergyUnitConversionsPage,
})
