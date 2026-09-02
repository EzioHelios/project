import { createFileRoute } from "@tanstack/react-router"

import { EnergyBudgetSettingsPanel } from "@/components/carbon/energy-budget-settings-panel"

export const Route = createFileRoute("/_app/data/energy-budget")({
  component: EnergyBudgetSettingsPanel,
})
