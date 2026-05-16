import { createFileRoute, Link } from "@tanstack/react-router"

import { Scope2RecordsPanel } from "@/components/carbon/scope2-records-panel"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export const Route = createFileRoute("/_app/carbon-mgmt/scope2")({
  component: Scope2Page,
})

function Scope2Page() {
  return (
    <PageContainer className="flex-1 space-y-6">
      <PageHeader eyebrow="碳核算模型" title="[范围2] 用电核算" description="以电表月聚合为主来源进行范围2用电核算，账单补录与数据对账作为辅助视图。" />

      <PageSection>
        <Tabs defaultValue="records">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="records">核算记录</TabsTrigger>
            <TabsTrigger value="bill">账单补录</TabsTrigger>
            <TabsTrigger value="reconciliation">数据对账</TabsTrigger>
          </TabsList>

          <TabsContent value="records" className="pt-4">
            <Scope2RecordsPanel defaultSourceKind="meter_aggregate" />
          </TabsContent>

          <TabsContent value="bill" className="pt-4">
            <SubViewEntryCard
              title="账单补录"
              description="当电表数据缺失或需要补录人工账单时，从这里进入账单来源视图。"
              actionLabel="进入账单补录"
              to="/carbon-mgmt/scope2-bill"
            />
          </TabsContent>

          <TabsContent value="reconciliation" className="pt-4">
            <SubViewEntryCard
              title="数据对账"
              description="按账期比较账单总量与电表月聚合总量，用于核对差异和排查缺失点位。"
              actionLabel="进入数据对账"
              to="/carbon-mgmt/scope2-reconciliation"
            />
          </TabsContent>
        </Tabs>
      </PageSection>
    </PageContainer>
  )
}

function SubViewEntryCard({
  title,
  description,
  actionLabel,
  to,
}: {
  title: string
  description: string
  actionLabel: string
  to: "/carbon-mgmt/scope2-bill" | "/carbon-mgmt/scope2-reconciliation"
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild>
          <Link to={to}>{actionLabel}</Link>
        </Button>
      </CardContent>
    </Card>
  )
}
