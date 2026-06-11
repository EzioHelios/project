import { createFileRoute } from "@tanstack/react-router"

import { UnderConstructionModule } from "@/components/carbon/under-construction-module"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/supply-chain")({
  component: SupplyChainCarbonPage,
})

function SupplyChainCarbonPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="碳排放管理" title="供应链碳管理" description="围绕供应商档案、填报任务、数据审核、披露和供应链分析建设协同管理能力。" />
      <UnderConstructionModule
        guideTitle="供应链碳管理"
        moduleType="业务办理型"
        plannedTabs={["供应商档案", "填报任务", "数据审核", "下游披露", "供应链分析"]}
        dataDependencies={["供应商档案", "租户/团队权限", "外购运输记录", "产品碳足迹结果", "供应商填报数据"]}
        currentFoundation={["已有多租户团队能力", "已有外购运输 Scope3 记录", "已有审核流转组件"]}
        nextTodos={["建立供应商任务模型", "实现外部填报入口", "补充数据审核和披露流程"]}
        status="建设中"
      />
    </PageContainer>
  )
}
