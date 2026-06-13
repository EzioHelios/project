import { createFileRoute } from "@tanstack/react-router"
import { AdminNav } from "@/components/admin/admin-nav"
import { TeamTable } from "@/components/admin/team-table"
import { AdminPageHeader } from "@/components/admin-ui"
import { PageContainer, PageSection } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/admin/teams/")({
  component: AdminTeamsPage,
})

function AdminTeamsPage() {
  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="Teams" />
      <AdminNav />
      <PageSection>
        <TeamTable />
      </PageSection>
    </PageContainer>
  )
}
