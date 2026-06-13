import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import { PermissionCenterNav } from "@/components/admin/permission-center-nav"
import { AdminPageHeader } from "@/components/admin-ui"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { SkeletonTable } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAdminUsers } from "@/lib/api/hooks/admin"
import { useAuthStore } from "@/lib/auth"

export const Route = createFileRoute("/_app/auth/users")({
  component: UsersManagePage,
})

function UsersManagePage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = useAdminUsers(page, 25)

  if (!user?.isSuperuser) {
    return (
      <PageContainer className="flex-1 space-y-4">
        <AdminPageHeader title="用户管理" meta="仅管理员可用" />
        <PermissionCenterNav />
        <PageSection>
          <Card>
            <CardHeader>
              <CardTitle>无权限</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              当前账号没有“用户管理”权限。
              <Button variant="outline" size="sm" onClick={() => navigate({ to: "/home" as const })}>
                返回首页
              </Button>
            </CardContent>
          </Card>
        </PageSection>
      </PageContainer>
    )
  }

  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="用户管理" />
      <PermissionCenterNav />
      <PageSection>
        {isLoading && <SkeletonTable rows={6} />}
        {!isLoading && (isError || !data) && (
          <Card>
            <CardHeader>
              <CardTitle>用户列表</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">用户数据加载失败，请稍后重试。</CardContent>
          </Card>
        )}
        {!isLoading && !isError && data && (
          <Card>
            <CardHeader>
              <CardTitle>用户列表</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>姓名</TableHead>
                    <TableHead>邮箱</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>角色</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-muted-foreground">
                        暂无用户
                      </TableCell>
                    </TableRow>
                  )}
                  {data.items.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell>{u.name ?? u.email}</TableCell>
                      <TableCell className="text-muted-foreground">{u.email}</TableCell>
                      <TableCell>{u.isActive ? "启用" : "停用"}</TableCell>
                      <TableCell>{u.isSuperuser ? "管理员" : "普通用户"}</TableCell>
                      <TableCell className="text-right">
                        <Button asChild variant="outline" size="sm">
                          <Link to="/admin/users/$userId" params={{ userId: u.id }}>
                            查看
                          </Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">
                  第 {page} 页 / 共 {Math.max(1, Math.ceil(data.total / 25))} 页（共 {data.total} 条）
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
                    上一页
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.min(Math.max(1, Math.ceil(data.total / 25)), p + 1))}
                    disabled={page >= Math.max(1, Math.ceil(data.total / 25))}
                  >
                    下一页
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </PageSection>
    </PageContainer>
  )
}
