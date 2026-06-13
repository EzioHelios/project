import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import { EnergyBenchmarkPanel } from "@/components/carbon/energy-benchmark-panel"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/benchmark")({
  component: EnergyBenchmarkPage,
})

function EnergyBenchmarkPage() {
  return (
    <PageContainer className="flex-1" maxWidth="4xl">
      <EnergyBenchmarkPanel header={<AdminPageHeader title="能效对标" />} />
    </PageContainer>
  )
}
