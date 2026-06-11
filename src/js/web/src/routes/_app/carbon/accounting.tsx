import { createFileRoute } from "@tanstack/react-router"

import {
  AccountingOverviewPanel,
  CarbonAccountingResultsPanel,
  PendingReviewPanel,
  Scope1AccountingPanel,
  Scope2AccountingPanel,
  Scope3AccountingPanel,
} from "@/components/carbon/accounting-panels"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export const Route = createFileRoute("/_app/carbon/accounting")({
  component: CarbonAccountingPage,
})

function CarbonAccountingPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="碳排放管理" title="碳排放核算" description="组织碳排放核算业务页，集中承载 Scope1/2/3 填报、核算结果和待审核处理。" />
      <PageSection>
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList className="grid w-full grid-cols-2 lg:grid-cols-6">
            <TabsTrigger value="overview">核算总览</TabsTrigger>
            <TabsTrigger value="scope1">Scope1 填报</TabsTrigger>
            <TabsTrigger value="scope2">Scope2 填报</TabsTrigger>
            <TabsTrigger value="scope3">Scope3 填报</TabsTrigger>
            <TabsTrigger value="results">核算结果</TabsTrigger>
            <TabsTrigger value="pending">待审核</TabsTrigger>
          </TabsList>
          <TabsContent value="overview">
            <AccountingOverviewPanel />
          </TabsContent>
          <TabsContent value="scope1">
            <Scope1AccountingPanel />
          </TabsContent>
          <TabsContent value="scope2">
            <Scope2AccountingPanel />
          </TabsContent>
          <TabsContent value="scope3">
            <Scope3AccountingPanel />
          </TabsContent>
          <TabsContent value="results">
            <CarbonAccountingResultsPanel />
          </TabsContent>
          <TabsContent value="pending">
            <PendingReviewPanel />
          </TabsContent>
        </Tabs>
      </PageSection>
    </PageContainer>
  )
}
