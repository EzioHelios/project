import { createFileRoute } from "@tanstack/react-router"

import { EnergyBenchmarkPanel } from "@/components/carbon/energy-benchmark-panel"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/benchmark")({
  component: EnergyBenchmarkPage,
})

function EnergyBenchmarkPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="能效对标" />
      <EnergyBenchmarkPanel />
    </PageContainer>
  )
}
