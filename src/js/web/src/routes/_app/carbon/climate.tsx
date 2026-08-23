import { createFileRoute, Outlet } from "@tanstack/react-router"

import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/climate")({ component: ClimateGovernanceLayout })

function ClimateGovernanceLayout() {
  return (
    <PageContainer className="flex-1" maxWidth="full">
      <Outlet />
    </PageContainer>
  )
}
