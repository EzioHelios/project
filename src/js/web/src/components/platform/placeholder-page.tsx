import { AdminEmptyState, AdminPageHeader, AdminPanel } from "@/components/admin-ui"
import { PageContainer, PageSection } from "@/components/ui/page-layout"

export function PlaceholderPage({ title, description }: { eyebrow: string; title: string; description?: string }) {
  return (
    <PageContainer className="flex-1 space-y-4">
      <AdminPageHeader title={title} />
      <PageSection>
        <AdminPanel title="待接入">
          <AdminEmptyState title={description ?? "该模块暂无可操作数据"} />
        </AdminPanel>
      </PageSection>
    </PageContainer>
  )
}
