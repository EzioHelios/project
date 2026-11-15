import { createFileRoute } from "@tanstack/react-router"
import { EnergyEntryPage } from "@/components/energy/energy-entry-page"

export const Route = createFileRoute("/_app/data/energy-consumption")({ component: EnergyEntryPage })
