import { createFileRoute } from "@tanstack/react-router"

import { UnderConstructionModule } from "@/components/carbon/under-construction-module"
import { PageContainer, PageHeader, PageSection } from "@/components/ui/page-layout"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AuditLogPanel } from "@/routes/_app/carbon-mgmt/audit"
import { PendingReviewPanel } from "@/routes/_app/carbon-mgmt/pending"
import { QualityTracePage } from "@/routes/_app/energy-carbon/quality"

export const Route = createFileRoute("/_app/carbon/verification")({
  component: CarbonVerificationPage,
})

function CarbonVerificationPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="碳排放管理" title="碳核查支撑" description="按核查材料视角组织凭证、追溯、质量问题、审核日志和报告输出，不再作为泛化质量看板。" />
      <PageSection>
        <Tabs defaultValue="issues" className="space-y-4">
          <TabsList className="grid w-full grid-cols-2 lg:grid-cols-6">
            <TabsTrigger value="evidence">凭证清单</TabsTrigger>
            <TabsTrigger value="trace">过程追溯</TabsTrigger>
            <TabsTrigger value="issues">质量问题</TabsTrigger>
            <TabsTrigger value="audit">审核日志</TabsTrigger>
            <TabsTrigger value="package">核查材料包</TabsTrigger>
            <TabsTrigger value="export">报告导出</TabsTrigger>
          </TabsList>
          <TabsContent value="evidence">
            <PendingReviewPanel />
          </TabsContent>
          <TabsContent value="trace">
            <QualityTracePage embedded />
          </TabsContent>
          <TabsContent value="issues">
            <QualityTracePage embedded />
          </TabsContent>
          <TabsContent value="audit">
            <AuditLogPanel />
          </TabsContent>
          <TabsContent value="package">
            <UnderConstructionModule
              guideTitle="核查材料包"
              moduleType="业务办理型"
              plannedTabs={["凭证汇总", "核算过程", "审核留痕", "问题整改", "材料打包"]}
              dataDependencies={["碳排放核算记录", "审核日志", "质量问题记录", "电表和业务台账凭证"]}
              currentFoundation={["已有待审核记录", "已有质量追溯链路", "已有审核操作日志"]}
              nextTodos={["定义材料包目录结构", "补充凭证附件关系", "生成核查材料包下载任务"]}
              status="建设中"
            />
          </TabsContent>
          <TabsContent value="export">
            <UnderConstructionModule
              guideTitle="核查报告导出"
              moduleType="业务办理型"
              plannedTabs={["报告模板", "数据校验", "报告预览", "导出记录"]}
              dataDependencies={["核查材料包", "企业基本信息", "组织边界", "碳排放核算结果"]}
              currentFoundation={["已有企业信息台账", "已有核算结果和审核日志"]}
              nextTodos={["建立报告模板", "补充导出 API", "记录导出版本和操作人"]}
              status="待开发"
            />
          </TabsContent>
        </Tabs>
      </PageSection>
    </PageContainer>
  )
}
