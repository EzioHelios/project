import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { PermissionCenterNav } from "@/components/admin/permission-center-nav"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"
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
      <PageContainer className="flex-1 space-y-8">
        <PageHeader eyebrow="权限中心" title="用户详情" />
        <PermissionCenterNav />
        <PageSection>
          <SkeletonCard />
        </PageSection>
      </PageContainer>
    )
  }

  if (isError || !data) {
    return (
      <PageContainer className="flex-1 space-y-8">
        <PageHeader
          eyebrow="权限中心"
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
          <Card>
            <CardHeader>
              <CardTitle>用户信息</CardTitle>
            </CardHeader>
            <CardContent className="text-muted-foreground">用户数据加载失败，请稍后重试。</CardContent>
          </Card>
        </PageSection>
      </PageContainer>
    )
  }

  return (
    <PageContainer className="flex-1 space-y-8">
      <PageHeader
        eyebrow="权限中心"
        title={data.name ?? data.email}
        description="管理用户账号状态和权限。"
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
        <Card>
          <CardContent className="space-y-4">
            <div className="grid gap-3 text-sm md:grid-cols-2">
              <div>
                <p className="text-muted-foreground">邮箱</p>
                <p>{data.email}</p>
              </div>
              <div>
                <p className="text-muted-foreground">用户名</p>
                <p>{data.username ?? "—"}</p>
              </div>
              <div>
                <p className="text-muted-foreground">状态</p>
                <p>{data.isActive ? "启用" : "停用"}</p>
              </div>
              <div>
                <p className="text-muted-foreground">超级管理员</p>
                <p>{data.isSuperuser ? "是" : "否"}</p>
              </div>
              <div>
                <p className="text-muted-foreground">已验证</p>
                <p>{data.isVerified ? "是" : "否"}</p>
              </div>
              <div>
                <p className="text-muted-foreground">已启用 MFA</p>
                <p>{data.isTwoFactorEnabled ? "是" : "否"}</p>
              </div>
            </div>
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
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}
