import { createFileRoute } from "@tanstack/react-router"
import { PermissionCenterNav } from "@/components/admin/permission-center-nav"
import { AuditLogTable } from "@/components/admin/audit-log-table"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/admin/audit")({
  component: AdminAuditPage,
})

function AdminAuditPage() {
  return (
    <PageContainer className="flex-1 space-y-8">
      <PageHeader eyebrow="权限中心" title="审计日志" description="查看权限变更、登录操作和关键业务动作。" />
      <PermissionCenterNav />
      <PageSection>
        <AuditLogTable />
      </PageSection>
    </PageContainer>
  )
}
