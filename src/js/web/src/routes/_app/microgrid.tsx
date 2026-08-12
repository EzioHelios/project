import { createFileRoute, Outlet } from "@tanstack/react-router"
import { PageContainer } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/microgrid")({ component: MicrogridLayout })

function MicrogridLayout() {
  return (
    <PageContainer className="flex-1" maxWidth="full">
      <Outlet />
    </PageContainer>
  )
}
