import { createFileRoute } from "@tanstack/react-router"

import { EnergyBenchmarkSettingsPanel } from "@/components/carbon/energy-benchmark-settings-panel"

export const Route = createFileRoute("/_app/data/energy-benchmark")({
  component: EnergyBenchmarkSettingsPanel,
})
