import { createFileRoute, Link } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { AdminPageHeader } from "@/components/admin-ui"
import { TeamList } from "@/components/teams/team-list"
import { Button } from "@/components/ui/button"
import { PageContainer, PageSection } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/teams/")({
  component: TeamsPage,
})

function TeamsPage() {
  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader
        title="团队管理"
        actions={
          <Button size="sm" asChild>
            <Link to="/teams/new">
              <Plus className="mr-2 h-4 w-4" /> 新建团队
            </Link>
          </Button>
        }
      />
      <PageSection>
        <TeamList />
      </PageSection>
    </PageContainer>
  )
}
