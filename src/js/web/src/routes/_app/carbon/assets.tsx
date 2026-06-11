import { createFileRoute } from "@tanstack/react-router"

import { UnderConstructionModule } from "@/components/carbon/under-construction-module"
import { PageContainer, PageHeader } from "@/components/ui/page-layout"

export const Route = createFileRoute("/_app/carbon/assets")({
  component: CarbonAssetsPage,
})

function CarbonAssetsPage() {
  return (
    <PageContainer className="flex-1 space-y-6" maxWidth="4xl">
      <PageHeader eyebrow="碳排放管理" title="碳资产管理" description="围绕配额、CCER/绿证、履约周期、交易模拟和风险预警建设碳资产管理能力。" />
      <UnderConstructionModule
        guideTitle="碳资产管理"
        moduleType="业务办理型"
        plannedTabs={["配额台账", "CCER/绿证", "履约周期", "交易模拟", "风险预警"]}
        dataDependencies={["组织碳排放核算结果", "年度履约边界", "配额和绿证台账", "市场价格数据"]}
        currentFoundation={["已有组织碳排放核算结果", "已有趋势和审核数据"]}
        nextTodos={["建立配额和绿证台账", "补充履约周期配置", "实现风险预警和交易模拟"]}
        status="待开发"
      />
    </PageContainer>
  )
}
