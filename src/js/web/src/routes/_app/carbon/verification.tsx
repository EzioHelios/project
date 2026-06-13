import { createFileRoute } from "@tanstack/react-router"

import { AdminPageHeader } from "@/components/admin-ui"
import {
  VerificationEvidencePanel,
  VerificationIssuesPanel,
  VerificationMaterialPackagePanel,
  VerificationProjectsPanel,
  VerificationReportPanel,
} from "@/components/carbon/verification-panels"
import { PageContainer, PageSection } from "@/components/ui/page-layout"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AuditLogPanel } from "@/routes/_app/carbon-mgmt/audit"
import { QualityTracePage } from "@/routes/_app/energy-carbon/quality"

export const Route = createFileRoute("/_app/carbon/verification")({
  component: CarbonVerificationPage,
})

function CarbonVerificationPage() {
  return (
    <PageContainer className="flex-1 space-y-4" maxWidth="4xl">
      <AdminPageHeader title="碳核查支撑" />
      <PageSection>
        <Tabs defaultValue="package" className="space-y-4">
          <TabsList className="grid w-full grid-cols-2 lg:grid-cols-7">
            <TabsTrigger value="projects">核查项目</TabsTrigger>
            <TabsTrigger value="evidence">凭证清单</TabsTrigger>
            <TabsTrigger value="trace">过程追溯</TabsTrigger>
            <TabsTrigger value="issues">质量问题</TabsTrigger>
            <TabsTrigger value="audit">审核日志</TabsTrigger>
            <TabsTrigger value="package">核查材料包</TabsTrigger>
            <TabsTrigger value="export">报告导出</TabsTrigger>
          </TabsList>
          <TabsContent value="projects">
            <VerificationProjectsPanel />
          </TabsContent>
          <TabsContent value="evidence">
            <VerificationEvidencePanel />
          </TabsContent>
          <TabsContent value="trace">
            <QualityTracePage embedded />
          </TabsContent>
          <TabsContent value="issues">
            <VerificationIssuesPanel />
          </TabsContent>
          <TabsContent value="audit">
            <AuditLogPanel />
          </TabsContent>
          <TabsContent value="package">
            <VerificationMaterialPackagePanel />
          </TabsContent>
          <TabsContent value="export">
            <VerificationReportPanel />
          </TabsContent>
        </Tabs>
      </PageSection>
    </PageContainer>
  )
}
