import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { PermissionCenterNav } from "@/components/admin/permission-center-nav"
import { AdminEmptyState, AdminPageHeader, AdminPanel, MetricStrip, MetricTile } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { SkeletonCard } from "@/components/ui/skeleton"
import { useAdminUpdateUser, useAdminUser } from "@/lib/api/hooks/admin"

export const Route = createFileRoute("/_app/admin/users/$userId")({
  component: AdminUserDetailPage,
})

function AdminUserDetailPage() {
  const { userId } = Route.useParams()
  const { data, isLoading, isError } = useAdminUser(userId)
  const updateUser = useAdminUpdateUser(userId)

  if (isLoading) {
    return (
      <PageContainer className="flex-1 space-y-4">
        <AdminPageHeader title="用户详情" />
        <PermissionCenterNav />
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
          title="用户详情"
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link to="/admin/users">
                <ArrowLeft className="mr-2 h-4 w-4" /> 返回用户列表
              </Link>
            </Button>
          }
        />
        <PermissionCenterNav />
        <PageSection>
          <AdminPanel title="用户信息">
            <AdminEmptyState title="用户数据加载失败" className="min-h-32" />
          </AdminPanel>
        </PageSection>
      </PageContainer>
    )
  }

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader
        title={data.name ?? data.email}
        actions={
          <Button variant="outline" size="sm" asChild>
            <Link to="/admin/users">
              <ArrowLeft className="mr-2 h-4 w-4" /> 返回用户列表
            </Link>
          </Button>
        }
      />
      <PermissionCenterNav />
      <PageSection>
        <AdminPanel title="用户信息" contentClassName="space-y-4">
          <MetricStrip className="xl:grid-cols-3">
            <MetricTile label="邮箱" value={data.email} />
            <MetricTile label="用户名" value={data.username ?? "-"} />
            <MetricTile label="状态" value={data.isActive ? "启用" : "停用"} tone={data.isActive ? "success" : "warning"} />
          </MetricStrip>
          <div className="grid gap-3 text-sm md:grid-cols-3">
            <DetailField label="超级管理员" value={data.isSuperuser ? "是" : "否"} />
            <DetailField label="已验证" value={data.isVerified ? "是" : "否"} />
            <DetailField label="已启用 MFA" value={data.isTwoFactorEnabled ? "是" : "否"} />
          </div>
          <div className="border-border/70 border-t pt-4">
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => updateUser.mutate({ is_active: !data.isActive })} disabled={updateUser.isPending}>
                {data.isActive ? "停用" : "启用"}
              </Button>
              <Button variant="outline" onClick={() => updateUser.mutate({ is_superuser: !data.isSuperuser })} disabled={updateUser.isPending}>
                {data.isSuperuser ? "取消超级管理员" : "设为超级管理员"}
              </Button>
              <Button variant="outline" onClick={() => updateUser.mutate({ is_verified: !data.isVerified })} disabled={updateUser.isPending}>
                {data.isVerified ? "标记未验证" : "标记已验证"}
              </Button>
            </div>
          </div>
        </AdminPanel>
      </PageSection>
    </PageContainer>
  )
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border/70 bg-background/70 px-3 py-2.5">
      <div className="text-[0.72rem] font-medium text-muted-foreground">{label}</div>
      <div className="mt-1 min-h-5 break-words font-medium text-sm">{value}</div>
    </div>
  )
}
