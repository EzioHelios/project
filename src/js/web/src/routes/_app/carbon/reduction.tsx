import { createFileRoute, Outlet } from "@tanstack/react-router"

import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/reduction")({ component: CarbonReductionLayout })

function CarbonReductionLayout() {
  return (
    <PageContainer className="flex-1" maxWidth="full">
      <Outlet />
    </PageContainer>
  )
}
