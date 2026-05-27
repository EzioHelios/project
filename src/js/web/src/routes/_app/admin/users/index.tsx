import { createFileRoute } from "@tanstack/react-router"
import { PermissionCenterNav } from "@/components/admin/permission-center-nav"
import { UserTable } from "@/components/admin/user-table"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/admin/users/")({
  component: AdminUsersPage,
})

function AdminUsersPage() {
  return (
    <PageContainer className="flex-1 space-y-8">
      <PageHeader eyebrow="权限中心" title="用户管理" description="查看并管理系统用户。"></PageHeader>
      <PermissionCenterNav />
      <PageSection>
        <UserTable />
      </PageSection>
    </PageContainer>
  )
}
