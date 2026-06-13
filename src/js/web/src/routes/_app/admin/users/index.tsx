import { createFileRoute } from "@tanstack/react-router"
import { PermissionCenterNav } from "@/components/admin/permission-center-nav"
import { UserTable } from "@/components/admin/user-table"
import { AdminPageHeader } from "@/components/admin-ui"
import { PageContainer, PageSection } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/admin/users/")({
  component: AdminUsersPage,
})

function AdminUsersPage() {
  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="用户管理" />
      <PermissionCenterNav />
      <PageSection>
        <UserTable />
      </PageSection>
    </PageContainer>
  )
}
