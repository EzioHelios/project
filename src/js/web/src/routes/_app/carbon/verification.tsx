import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { AdminPageHeader, AdminPageScaffold, AdminTabsList } from "@/components/admin-ui"
import {
  VerificationAuditPanel,
  VerificationEvidencePanel,
  VerificationIssuesPanel,
  VerificationMaterialPackagePanel,
  VerificationProjectsPanel,
  VerificationReportPanel,
  VerificationTracePanel,
} from "@/components/carbon/verification-panels"
import { PageContainer } from "@/components/ui/page-layout"
import { Tabs, TabsContent, TabsTrigger } from "@/components/ui/tabs"

export const Route = createFileRoute("/_app/carbon/verification")({
  component: CarbonVerificationPage,
})

function CarbonVerificationPage() {
  const [projectId, setProjectId] = useState<number>()
  return (
    <PageContainer className="min-w-0 flex-1" maxWidth="4xl">
      <Tabs defaultValue="projects" className="space-y-4">
        <AdminPageScaffold
          header={<AdminPageHeader title="碳核查支撑" />}
          tabs={
            <AdminTabsList>
              <TabsTrigger value="projects">核查项目</TabsTrigger>
              <TabsTrigger value="evidence">证据资料</TabsTrigger>
              <TabsTrigger value="work">核查工作</TabsTrigger>
              <TabsTrigger value="delivery">报告与材料</TabsTrigger>
            </AdminTabsList>
          }
        >
          <TabsContent value="projects">
            <VerificationProjectsPanel selectedProjectId={projectId} onProjectSelect={setProjectId} />
          </TabsContent>
          <TabsContent value="evidence">
            <VerificationEvidencePanel projectId={projectId} />
          </TabsContent>
          <TabsContent value="work">
            <Tabs defaultValue="trace" className="space-y-4">
              <AdminTabsList>
                <TabsTrigger value="trace">过程追溯</TabsTrigger>
                <TabsTrigger value="issues">质量问题</TabsTrigger>
                <TabsTrigger value="audit">审核日志</TabsTrigger>
              </AdminTabsList>
              <TabsContent value="trace">
                <VerificationTracePanel projectId={projectId} />
              </TabsContent>
              <TabsContent value="issues">
                <VerificationIssuesPanel projectId={projectId} />
              </TabsContent>
              <TabsContent value="audit">
                <VerificationAuditPanel projectId={projectId} />
              </TabsContent>
            </Tabs>
          </TabsContent>
          <TabsContent value="delivery">
            <Tabs defaultValue="package" className="space-y-4">
              <AdminTabsList>
                <TabsTrigger value="package">核查材料包</TabsTrigger>
                <TabsTrigger value="export">报告导出</TabsTrigger>
              </AdminTabsList>
              <TabsContent value="package">
                <VerificationMaterialPackagePanel projectId={projectId} />
              </TabsContent>
              <TabsContent value="export">
                <VerificationReportPanel projectId={projectId} />
              </TabsContent>
            </Tabs>
          </TabsContent>
        </AdminPageScaffold>
      </Tabs>
    </PageContainer>
  )
}
