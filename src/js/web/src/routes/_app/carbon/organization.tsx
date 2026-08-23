import { createFileRoute, Outlet } from "@tanstack/react-router"

import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/organization")({ component: OrganizationCarbonLayout })

function OrganizationCarbonLayout() {
  return (
    <PageContainer className="flex-1" maxWidth="full">
      <Outlet />
    </PageContainer>
  )
}
