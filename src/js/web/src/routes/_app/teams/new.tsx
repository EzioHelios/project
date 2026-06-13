import { createFileRoute } from "@tanstack/react-router"
import { AdminPageHeader, AdminPanel } from "@/components/admin-ui"
import { CreateTeamForm } from "@/components/teams/create-team-form"
import { PageContainer, PageSection } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/teams/new")({
  component: NewTeamPage,
})

function NewTeamPage() {
  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="新建团队" />

      <PageSection className="max-w-3xl">
        <AdminPanel title="团队信息">
          <CreateTeamForm />
        </AdminPanel>
      </PageSection>
    </PageContainer>
  )
}
