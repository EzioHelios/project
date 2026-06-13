import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { AdminNav } from "@/components/admin/admin-nav"
import { AdminEmptyState, AdminPageHeader, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { SkeletonCard } from "@/components/ui/skeleton"
import { useAdminTeam, useAdminUpdateTeam } from "@/lib/api/hooks/admin"

export const Route = createFileRoute("/_app/admin/teams/$teamId")({
  component: AdminTeamDetailPage,
})

function AdminTeamDetailPage() {
  const { teamId } = Route.useParams()
  const { data, isLoading, isError } = useAdminTeam(teamId)
  const updateTeam = useAdminUpdateTeam(teamId)

  if (isLoading) {
    return (
      <PageContainer className="flex-1 space-y-4">
        <AdminPageHeader title="团队详情" />
        <AdminNav />
        <PageSection>
          <SkeletonCard />
        </PageSection>
      </PageContainer>
    )
  }

  if (isError || !data) {
    return (
      <PageContainer className="flex-1 space-y-4">
        <AdminPageHeader
          title="团队详情"
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link to="/admin/teams">
                <ArrowLeft className="mr-2 h-4 w-4" /> 返回团队列表
              </Link>
            </Button>
          }
        />
        <AdminNav />
        <PageSection>
          <AdminPanel title="团队信息">
            <AdminEmptyState title="团队数据加载失败" className="min-h-32" />
          </AdminPanel>
        </PageSection>
      </PageContainer>
    )
  }

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader
        title={data.name}
        actions={
          <Button variant="outline" size="sm" asChild>
            <Link to="/admin/teams">
              <ArrowLeft className="mr-2 h-4 w-4" /> 返回团队列表
            </Link>
          </Button>
        }
      />
      <AdminNav />
      <PageSection>
        <AdminPanel title="团队信息" contentClassName="space-y-4">
          <MetricStrip className="xl:grid-cols-4">
            <MetricTile label="标识" value={data.slug} />
            <MetricTile label="负责人" value={data.ownerEmail ?? "-"} />
            <MetricTile label="成员数" value={data.memberCount ?? 0} />
            <MetricTile label="状态" value={data.isActive ? "启用" : "停用"} tone={data.isActive ? "success" : "warning"} />
          </MetricStrip>
          <div className="border-border/70 border-t pt-4">
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => updateTeam.mutate({ is_active: !data.isActive })} disabled={updateTeam.isPending}>
                {data.isActive ? "停用" : "启用"}
              </Button>
            </div>
          </div>
        </AdminPanel>
      </PageSection>
    </PageContainer>
  )
}
