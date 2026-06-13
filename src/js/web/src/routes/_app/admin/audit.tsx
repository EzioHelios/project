import { createFileRoute } from "@tanstack/react-router"
import { AuditLogTable } from "@/components/admin/audit-log-table"
import { PermissionCenterNav } from "@/components/admin/permission-center-nav"
import { AdminPageHeader } from "@/components/admin-ui"
import { PageContainer, PageSection } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/admin/audit")({
  component: AdminAuditPage,
})

function AdminAuditPage() {
  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title="审计日志" />
      <PermissionCenterNav />
      <PageSection>
        <AuditLogTable />
      </PageSection>
    </PageContainer>
  )
}
