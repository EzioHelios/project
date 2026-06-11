import { createFileRoute } from "@tanstack/react-router"

import { UnderConstructionModule } from "@/components/carbon/under-construction-module"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/energy/budget")({
  component: EnergyBudgetPage,
})

function EnergyBudgetPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="能源管理" title="用能与碳排放预算管理" />
      <UnderConstructionModule
        guideTitle="用能与碳排放预算管理"
        moduleType="业务办理型"
        plannedTabs={["年度目标", "月度预算", "执行偏差", "预测超限", "调整审批"]}
        dataDependencies={["组织边界", "能源消费量和强度结果", "碳排放核算结果", "预算目标和审批规则"]}
        currentFoundation={["已有能源消费量趋势", "已有组织碳排核算记录", "已有审核流转组件"]}
        nextTodos={["建立年度和月度预算模型", "接入预测超限规则", "补充预算调整审批流"]}
        status="待开发"
      />
    </PageContainer>
  )
}
